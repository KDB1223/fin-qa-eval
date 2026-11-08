"""Quality checks for an eval set.

Schema validation answers "is this row shaped correctly?". These checks
answer "is the row safe to grade?": duplicate ids, duplicate questions,
evidence that is not actually in the snippet, unit slips where the written
digits match but the unit does not, and unanswerable rows that still carry
a number.

Every shipped row must be marked ``synthetic: true``. This package does not
accept scraped filings.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from fin_qa_eval.schema import schema_errors
from fin_qa_eval.units import (
    KNOWN_UNITS,
    is_money,
    is_percent,
    infer_yoy_percent,
    parse_amounts,
    same_family,
    to_decimal,
    values_close,
)

REQUIRED_FIELDS = (
    "id",
    "company",
    "ticker",
    "report_period",
    "metric",
    "convention",
    "unit",
    "question",
    "source_id",
    "source_text",
    "evidence_span",
    "reference",
    "synthetic",
    "language",
    "tags",
)

METRICS = frozenset(
    {
        "revenue",
        "net_profit",
        "operating_cashflow",
        "revenue_yoy",
        "net_profit_yoy",
        "operating_cashflow_yoy",
    }
)
PERIOD_RE = re.compile(r"^20\d{2}(?:FY|H1|H2|Q[1-4])$")
REFUSAL_REASONS = frozenset(
    {
        "insufficient_evidence",
        "unit_ambiguous",
        "convention_conflict",
        "out_of_scope",
    }
)


@dataclass(frozen=True)
class Issue:
    """One QC finding. Severity ``error`` fails the command."""

    code: str
    message: str
    item_id: Optional[str] = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "item_id": self.item_id,
            "message": self.message,
        }


@dataclass
class QCReport:
    items_checked: int
    issues: list[Issue] = field(default_factory=list)
    boundary_counts: dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def codes(self) -> list[str]:
        return sorted({issue.code for issue in self.issues if issue.severity == "error"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items_checked,
            "ok": self.ok,
            "error_count": self.error_count,
            "boundary": self.boundary_counts,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def norm_text(value: str) -> str:
    """Ignore whitespace and common fullwidth punctuation when comparing spans."""

    text = value.strip().lower()
    for src, dst in (
        ("，", ","),
        ("。", "."),
        ("：", ":"),
        ("；", ";"),
        ("（", "("),
        ("）", ")"),
        ("％", "%"),
    ):
        text = text.replace(src, dst)
    return re.sub(r"\s+", "", text)


def norm_question(question: str) -> str:
    text = norm_text(question)
    return re.sub(r"[?？。.!！]", "", text)


def evidence_contained(span: str, source: str) -> bool:
    if not span:
        return False
    return span in source or norm_text(span) in norm_text(source)


def run_qc(items: list[dict[str, Any]], schema: dict[str, Any]) -> QCReport:
    issues: list[Issue] = []
    for message in schema_errors(items, schema):
        issues.append(Issue("schema_violation", message, item_id=_id_from_message(message)))
    issues.extend(semantic_issues(items))
    return QCReport(
        items_checked=len(items),
        issues=issues,
        boundary_counts=boundary_counts(items),
    )


def boundary_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("boundary:"):
                counts[tag.split(":", 1)[1]] += 1
    return dict(sorted(counts.items()))


def semantic_issues(items: list[dict[str, Any]]) -> list[Issue]:
    issues: list[Issue] = []
    seen_ids: dict[str, int] = {}
    seen_questions: dict[str, str] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(Issue("schema_violation", f"item[{index}] is not an object"))
            continue
        item_id = item.get("id") if isinstance(item.get("id"), str) else None
        label = item_id or f"item[{index}]"
        issues.extend(_missing_fields(item, label))
        if item_id:
            if item_id in seen_ids:
                issues.append(
                    Issue(
                        "duplicate_id",
                        f"{item_id} repeats row {seen_ids[item_id]}",
                        item_id=item_id,
                    )
                )
            else:
                seen_ids[item_id] = index
        question = item.get("question")
        if isinstance(question, str) and question.strip():
            key = norm_question(question)
            if key in seen_questions:
                issues.append(
                    Issue(
                        "duplicate_question",
                        f"question repeats {seen_questions[key]}",
                        item_id=item_id,
                    )
                )
            else:
                seen_questions[key] = item_id or f"item[{index}]"
        issues.extend(_check_row(item, item_id))
    return issues


def _missing_fields(item: dict[str, Any], label: str) -> list[Issue]:
    missing = [name for name in REQUIRED_FIELDS if name not in item]
    if not missing:
        return []
    return [
        Issue(
            "missing_field",
            f"{label} missing {', '.join(missing)}",
            item_id=item.get("id") if isinstance(item.get("id"), str) else None,
        )
    ]


def _check_row(item: dict[str, Any], item_id: Optional[str]) -> list[Issue]:
    issues: list[Issue] = []
    if item.get("synthetic") is not True:
        issues.append(
            Issue(
                "not_synthetic",
                "row must set synthetic=true; this toolkit ships invented figures only",
                item_id=item_id,
            )
        )
    period = item.get("report_period")
    if isinstance(period, str) and period and not PERIOD_RE.match(period):
        issues.append(Issue("bad_period", f"unrecognized report_period {period}", item_id=item_id))
    metric = item.get("metric")
    if isinstance(metric, str) and metric and metric not in METRICS:
        issues.append(Issue("unknown_metric", f"unknown metric {metric}", item_id=item_id))
    unit = item.get("unit")
    if isinstance(unit, str) and unit and unit not in KNOWN_UNITS:
        issues.append(Issue("unknown_unit", f"unknown unit {unit}", item_id=item_id))

    reference = item.get("reference")
    if not isinstance(reference, dict):
        return issues
    answerable = reference.get("answerable")
    source = item.get("source_text") if isinstance(item.get("source_text"), str) else ""
    span = item.get("evidence_span") if isinstance(item.get("evidence_span"), str) else ""

    if answerable is True:
        if reference.get("refusal_reason") not in (None,):
            issues.append(
                Issue(
                    "answerable_has_refusal",
                    "answerable rows must set refusal_reason to null",
                    item_id=item_id,
                )
            )
        if reference.get("value") is None or reference.get("unit") is None:
            issues.append(
                Issue(
                    "answerable_missing_value",
                    "answerable rows need reference.value and reference.unit",
                    item_id=item_id,
                )
            )
        if not span:
            issues.append(Issue("evidence_missing", "answerable row has an empty evidence span", item_id=item_id))
        elif not evidence_contained(span, source):
            issues.append(
                Issue(
                    "evidence_not_in_source",
                    "evidence_span is not contained in source_text",
                    item_id=item_id,
                )
            )
        if (
            reference.get("value") is not None
            and reference.get("unit") is not None
            and span
            and evidence_contained(span, source)
        ):
            issues.extend(_value_issues(item, item_id))
        if isinstance(unit, str) and isinstance(reference.get("unit"), str) and unit != reference.get("unit"):
            issues.append(
                Issue(
                    "unit_field_mismatch",
                    f"item.unit {unit} != reference.unit {reference.get('unit')}",
                    item_id=item_id,
                )
            )
    elif answerable is False:
        if reference.get("value") is not None:
            issues.append(
                Issue(
                    "unanswerable_has_value",
                    "unanswerable rows must set reference.value to null",
                    item_id=item_id,
                )
            )
        reason = reference.get("refusal_reason")
        if reason not in REFUSAL_REASONS:
            issues.append(
                Issue(
                    "missing_refusal_reason",
                    "unanswerable rows need a refusal_reason",
                    item_id=item_id,
                )
            )
        if span and not evidence_contained(span, source):
            issues.append(
                Issue(
                    "evidence_not_in_source",
                    "evidence_span is not contained in source_text",
                    item_id=item_id,
                )
            )

    issues.extend(_distractor_issues(item, item_id))
    return issues


def _value_issues(item: dict[str, Any], item_id: Optional[str]) -> list[Issue]:
    reference = item["reference"]
    ref_value = to_decimal(reference["value"])
    ref_unit = reference["unit"]
    if ref_unit not in KNOWN_UNITS:
        return [Issue("unknown_unit", f"reference.unit {ref_unit}", item_id=item_id)]
    amounts = parse_amounts(item.get("evidence_span") or "")
    if _value_supported(item, ref_value, ref_unit, amounts):
        return []
    if _looks_like_unit_slip(ref_value, ref_unit, amounts):
        return [
            Issue(
                "unit_anomaly",
                "evidence digits match the reference but the unit scale does not",
                item_id=item_id,
            )
        ]
    if not amounts:
        return [Issue("evidence_no_amount", "evidence span contains no parseable amount", item_id=item_id)]
    return [
        Issue(
            "value_conflict",
            "reference value is not supported by the evidence span after unit normalization",
            item_id=item_id,
        )
    ]


def _value_supported(
    item: dict[str, Any],
    ref_value: Any,
    ref_unit: str,
    amounts: list[Any],
) -> bool:
    for amount in amounts:
        if values_close(ref_value, ref_unit, amount.value, amount.unit):
            return True
    metric = item.get("metric") or ""
    if ref_unit == "percent" or (isinstance(metric, str) and metric.endswith("_yoy")):
        money = [amount for amount in amounts if is_money(amount.unit)]
        if len(money) >= 2:
            yoy = infer_yoy_percent(money[0], money[1])
            if yoy is not None and is_percent(ref_unit) and values_close(ref_value, "percent", yoy, "percent"):
                return True
    return False


def _looks_like_unit_slip(ref_value: Any, ref_unit: str, amounts: list[Any]) -> bool:
    if ref_value == 0:
        return False
    for amount in amounts:
        if amount.unit == ref_unit or not same_family(amount.unit, ref_unit):
            continue
        if abs(abs(amount.value) - abs(ref_value)) / abs(ref_value) <= to_decimal("0.01"):
            if not values_close(ref_value, ref_unit, amount.value, amount.unit):
                return True
    return False


def _distractor_issues(item: dict[str, Any], item_id: Optional[str]) -> list[Issue]:
    distractors = item.get("distractors") or []
    if not distractors:
        return []
    if not isinstance(distractors, list):
        return [Issue("schema_violation", "distractors must be a list", item_id=item_id)]
    source = item.get("source_text") if isinstance(item.get("source_text"), str) else ""
    reference = item.get("reference") if isinstance(item.get("reference"), dict) else {}
    issues: list[Issue] = []
    for distractor in distractors:
        if not isinstance(distractor, dict):
            continue
        span = distractor.get("span") or ""
        if span and not evidence_contained(span, source):
            issues.append(
                Issue(
                    "distractor_not_in_source",
                    "distractor span is not contained in source_text",
                    item_id=item_id,
                )
            )
        if (
            reference.get("answerable") is True
            and reference.get("value") is not None
            and reference.get("unit")
            and distractor.get("value") is not None
            and distractor.get("unit")
        ):
            try:
                close = values_close(
                    to_decimal(reference["value"]),
                    reference["unit"],
                    to_decimal(distractor["value"]),
                    distractor["unit"],
                )
            except Exception:
                close = False
            if close:
                issues.append(
                    Issue(
                        "distractor_equals_gold",
                        f"distractor {distractor.get('reason')} matches the reference value",
                        item_id=item_id,
                    )
                )
    return issues


def _id_from_message(message: str) -> Optional[str]:
    match = re.search(r"id=([^\s]+)", message)
    if match and match.group(1) != "?":
        return match.group(1)
    return None
