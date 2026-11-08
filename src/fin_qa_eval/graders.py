"""Deterministic graders for numeric accuracy, evidence, and refusal.

No model is called. A prediction is a JSON object with an ``id`` and either
structured ``value`` / ``unit`` fields or a Chinese answer string such as
``128.6亿元`` or ``拒答：片段未披露``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from fin_qa_eval.qc import evidence_contained, norm_text
from fin_qa_eval.units import (
    KNOWN_UNITS,
    ParsedAmount,
    classify_mismatch,
    parse_first_amount,
    to_decimal,
    values_close,
)

REFUSAL_RE = re.compile(
    r"拒答|无法回答|无法确定|证据不足|未披露|不足以回答|不足以确定|不宜计算|"
    r"拒绝回答|insufficient evidence|cannot be determined|not disclosed|refuse",
    re.IGNORECASE,
)

# First match becomes the primary error so attribution tables partition items.
ERROR_PRIORITY = (
    "missing_prediction",
    "under_refusal",
    "over_refusal",
    "convention_mismatch",
    "unit_scale_error",
    "sign_error",
    "numeric_mismatch",
    "unparseable_answer",
    "evidence_not_in_source",
    "evidence_missing",
    "evidence_wrong_span",
    "evidence_overclaim",
)

DIMENSIONS = (
    "numeric_accuracy",
    "evidence_consistency",
    "refusal_appropriateness",
)


@dataclass
class ItemResult:
    id: str
    company: str
    report_period: str
    metric: str
    language: str
    answerable: bool
    numeric_accuracy: float
    evidence_consistency: float
    refusal_appropriateness: float
    overall: float
    errors: list[str] = field(default_factory=list)
    primary_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "company": self.company,
            "report_period": self.report_period,
            "metric": self.metric,
            "language": self.language,
            "answerable": self.answerable,
            "numeric_accuracy": self.numeric_accuracy,
            "evidence_consistency": self.evidence_consistency,
            "refusal_appropriateness": self.refusal_appropriateness,
            "overall": self.overall,
            "errors": list(self.errors),
            "primary_error": self.primary_error,
        }


@dataclass
class GradeOutput:
    results: list[ItemResult]
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return summarize(self.results)


def grade(gold_items: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> GradeOutput:
    """Grade predictions against gold. Missing ids score zero on every dimension."""

    pred_by_id: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for prediction in predictions:
        pred_id = prediction.get("id")
        if not isinstance(pred_id, str) or not pred_id:
            warnings.append("prediction without id was ignored")
            continue
        if pred_id in pred_by_id:
            warnings.append(f"duplicate prediction for {pred_id}; last one wins")
        pred_by_id[pred_id] = prediction

    results = [grade_item(item, pred_by_id.get(str(item.get("id")))) for item in gold_items]
    return GradeOutput(results=results, warnings=warnings)


def grade_item(gold: dict[str, Any], prediction: Optional[dict[str, Any]]) -> ItemResult:
    item_id = str(gold.get("id"))
    if prediction is None:
        return _result(gold, 0.0, 0.0, 0.0, ["missing_prediction"])

    answerable = bool(gold.get("reference", {}).get("answerable"))
    refused = prediction_refused(prediction)
    errors: list[str] = []

    if answerable and refused:
        refusal = 0.0
        errors.append("over_refusal")
    elif answerable and not refused:
        refusal = 1.0
    elif (not answerable) and refused:
        refusal = 1.0
    else:
        refusal = 0.0
        errors.append("under_refusal")

    numeric, numeric_errors = _score_numeric(gold, prediction, answerable, refused)
    evidence, evidence_errors = _score_evidence(gold, prediction, answerable, refused)
    errors.extend(numeric_errors)
    errors.extend(evidence_errors)
    unique = _unique(errors)
    return _result(gold, numeric, evidence, refusal, unique)


def prediction_refused(prediction: dict[str, Any]) -> bool:
    flag = prediction.get("refused")
    if flag is True:
        return True
    if flag is False:
        return False
    return bool(REFUSAL_RE.search(str(prediction.get("answer") or "")))


def resolve_prediction_amount(prediction: dict[str, Any]) -> Optional[ParsedAmount]:
    """Prefer structured value/unit. Fall back to the first amount in ``answer``."""

    if prediction.get("value") is not None and prediction.get("unit"):
        unit = str(prediction["unit"])
        if unit not in KNOWN_UNITS:
            return None
        return ParsedAmount(
            value=to_decimal(prediction["value"]),
            unit=unit,
            raw=str(prediction.get("answer") or ""),
        )
    return parse_first_amount(str(prediction.get("answer") or ""))


def summarize(results: list[ItemResult]) -> dict[str, Any]:
    if not results:
        return {
            "n": 0,
            "n_full_credit": 0,
            "numeric_accuracy": 0.0,
            "evidence_consistency": 0.0,
            "refusal_appropriateness": 0.0,
            "overall": 0.0,
            "by_metric": {},
            "by_company": {},
            "by_period": {},
            "by_error": {},
        }
    summary = {
        "n": len(results),
        "n_full_credit": sum(1 for row in results if row.overall == 1.0),
        "numeric_accuracy": _mean(row.numeric_accuracy for row in results),
        "evidence_consistency": _mean(row.evidence_consistency for row in results),
        "refusal_appropriateness": _mean(row.refusal_appropriateness for row in results),
        "overall": _mean(row.overall for row in results),
        "by_metric": _group(results, lambda row: row.metric),
        "by_company": _group(results, lambda row: row.company),
        "by_period": _group(results, lambda row: row.report_period),
        "by_error": dict(_error_counts(results)),
    }
    return summary


def _score_numeric(
    gold: dict[str, Any],
    prediction: dict[str, Any],
    answerable: bool,
    refused: bool,
) -> tuple[float, list[str]]:
    if not answerable:
        return (1.0 if refused else 0.0), []
    if refused:
        return 0.0, []
    reference = gold["reference"]
    parsed = resolve_prediction_amount(prediction)
    if parsed is None:
        return 0.0, ["unparseable_answer"]
    gold_value = to_decimal(reference["value"])
    gold_unit = str(reference["unit"])
    if values_close(gold_value, gold_unit, parsed.value, parsed.unit):
        return 1.0, []
    if _matches_distractor(gold, parsed):
        return 0.0, ["convention_mismatch"]
    return 0.0, [classify_mismatch(gold_value, gold_unit, parsed.value, parsed.unit)]


def _score_evidence(
    gold: dict[str, Any],
    prediction: dict[str, Any],
    answerable: bool,
    refused: bool,
) -> tuple[float, list[str]]:
    source = str(gold.get("source_text") or "")
    gold_span = str(gold.get("evidence_span") or "")
    predicted = str(prediction.get("evidence") or "").strip()

    if not answerable:
        if not refused:
            return 0.0, ["evidence_overclaim"]
        if not predicted or evidence_contained(predicted, source):
            return 1.0, []
        return 0.0, ["evidence_not_in_source"]

    if refused:
        return 0.0, []
    if not predicted:
        return 0.0, ["evidence_missing"]
    if not evidence_contained(predicted, source):
        return 0.0, ["evidence_not_in_source"]
    if _spans_align(predicted, gold_span):
        return 1.0, []
    if any(_spans_align(predicted, str(item.get("span") or "")) for item in gold.get("distractors") or []):
        return 0.0, ["convention_mismatch"]
    return 0.5, ["evidence_wrong_span"]


def _matches_distractor(gold: dict[str, Any], parsed: ParsedAmount) -> bool:
    for distractor in gold.get("distractors") or []:
        if not isinstance(distractor, dict):
            continue
        if distractor.get("value") is None or not distractor.get("unit"):
            continue
        if values_close(
            to_decimal(distractor["value"]),
            str(distractor["unit"]),
            parsed.value,
            parsed.unit,
        ):
            return True
    return False


def _spans_align(left: str, right: str) -> bool:
    if not left or not right:
        return False
    a = norm_text(left)
    b = norm_text(right)
    return a in b or b in a


def _result(
    gold: dict[str, Any],
    numeric: float,
    evidence: float,
    refusal: float,
    errors: list[str],
) -> ItemResult:
    reference = gold.get("reference") or {}
    return ItemResult(
        id=str(gold.get("id")),
        company=str(gold.get("company") or ""),
        report_period=str(gold.get("report_period") or ""),
        metric=str(gold.get("metric") or ""),
        language=str(gold.get("language") or ""),
        answerable=bool(reference.get("answerable")),
        numeric_accuracy=numeric,
        evidence_consistency=evidence,
        refusal_appropriateness=refusal,
        overall=(numeric + evidence + refusal) / 3,
        errors=errors,
        primary_error=_primary(errors),
    )


def _primary(errors: list[str]) -> Optional[str]:
    for code in ERROR_PRIORITY:
        if code in errors:
            return code
    return errors[0] if errors else None


def _unique(errors: list[str]) -> list[str]:
    seen: list[str] = []
    for code in errors:
        if code not in seen:
            seen.append(code)
    return seen


def _mean(values: Any) -> float:
    seq = list(values)
    if not seq:
        return 0.0
    return float(sum(seq) / len(seq))


def _group(results: list[ItemResult], key: Any) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[ItemResult]] = defaultdict(list)
    for row in results:
        buckets[str(key(row))].append(row)
    grouped: dict[str, dict[str, Any]] = {}
    for name in sorted(buckets):
        rows = buckets[name]
        grouped[name] = {
            "n": len(rows),
            "overall": _mean(row.overall for row in rows),
            "numeric_accuracy": _mean(row.numeric_accuracy for row in rows),
            "evidence_consistency": _mean(row.evidence_consistency for row in rows),
            "refusal_appropriateness": _mean(row.refusal_appropriateness for row in rows),
            "n_full_credit": sum(1 for row in rows if row.overall == 1.0),
            "top_error": _top_error(rows),
        }
    return grouped


def _error_counts(results: list[ItemResult]) -> list[tuple[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    for row in results:
        for code in row.errors:
            counts[code] += 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ordered


def _top_error(rows: list[ItemResult]) -> Optional[str]:
    """Most common primary error. Ties break by grader priority, not spelling."""

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.primary_error:
            counts[row.primary_error] += 1
    if not counts:
        return None

    def sort_key(code: str) -> tuple[int, int]:
        priority = ERROR_PRIORITY.index(code) if code in ERROR_PRIORITY else len(ERROR_PRIORITY)
        return (-counts[code], priority)

    return min(counts, key=sort_key)
