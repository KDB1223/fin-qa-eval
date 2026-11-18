"""Inventory items that did not receive full credit.

Scores come from :func:`fin_qa_eval.graders.grade`. This module does not
re-score. An item is a failure when ``overall < 1.0``, the same cut as the
report's 错例 table. Partial credit counts. A gold id with no prediction is
already scored zero by the grader and is included.

The payload joins each failing :class:`~fin_qa_eval.graders.ItemResult` with
the gold reference and the prediction the grader used (last duplicate id
wins). Resolved amounts use :func:`resolve_prediction_amount`. Refusal uses
:func:`prediction_refused`.

:func:`collect_failures` returns a JSON-ready dict:

- ``gold``, ``pred``: display paths
- ``summary``: ``n`` and ``n_full_credit`` describe the whole grade.
  ``n_failures`` and ``by_primary_error`` describe the ``failures`` list
  after filters. With no filters, ``n == n_failures + n_full_credit``.
  ``by_primary_error`` is sorted by count descending, then code ascending.
- ``filters``: ``error``, ``company``, and ``id``. Unset filters are JSON
  ``null``. Filters are ANDed.
- ``failures``: one object per miss, sorted by overall ascending, then id.
  Passing items are omitted. Each object carries id, company, period,
  metric, 口径 (``scope``, ``basis``, ``profit_view``, ``tax``), unit, the
  three dimension scores and overall, ``primary_error``, ``errors``, a
  ``gold`` reference (answerable, value, unit, display, refusal_reason),
  and a ``prediction`` (``missing``, ``refused``, resolved value and unit,
  raw ``answer``).
- ``warnings``: grader warnings, copied unchanged.

:func:`render_failures_text` prints that payload in a stable, compact form.
An empty failure list prints ``no failures``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fin_qa_eval.graders import (
    GradeOutput,
    ItemResult,
    prediction_refused,
    resolve_prediction_amount,
)
from fin_qa_eval.report import format_score


def collect_failures(
    graded: GradeOutput,
    gold_items: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    gold_name: str,
    pred_name: str,
    error: Optional[str] = None,
    company: Optional[str] = None,
    item_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build the failure inventory described in the module docstring."""

    if len(gold_items) != len(graded.results):
        raise ValueError(
            f"gold items ({len(gold_items)}) and grade results ({len(graded.results)}) differ"
        )
    pred_by_id = _predictions_by_id(predictions)
    failures: list[dict[str, Any]] = []
    for gold, result in zip(gold_items, graded.results):
        if not result.overall < 1.0:
            continue
        if not _selected(result, error=error, company=company, item_id=item_id):
            continue
        failures.append(_failure_row(result, gold, pred_by_id.get(result.id)))
    failures.sort(key=lambda row: (row["overall"], row["id"]))
    n_full_credit = sum(1 for row in graded.results if row.overall == 1.0)
    return {
        "gold": gold_name,
        "pred": pred_name,
        "summary": {
            "n": len(graded.results),
            "n_failures": len(failures),
            "n_full_credit": n_full_credit,
            "by_primary_error": _by_primary_error(failures),
        },
        "filters": {"error": error, "company": company, "id": item_id},
        "failures": failures,
        "warnings": list(graded.warnings),
    }


def render_failures_text(report: dict[str, Any]) -> str:
    """Compact inventory. An empty list ends with ``no failures``."""

    summary = report["summary"]
    lines = [
        "failures items={n} failures={n_failures} full_credit={full}".format(
            n=summary["n"],
            n_failures=summary["n_failures"],
            full=summary["n_full_credit"],
        ),
        _primary_line(summary["by_primary_error"]),
    ]
    filters = _filter_line(report.get("filters") or {})
    if filters:
        lines.append(filters)
    for warning in report.get("warnings") or []:
        lines.append(f"warning: {warning}")
    failures = report["failures"]
    if not failures:
        lines.append("no failures")
        return "\n".join(lines) + "\n"
    for row in failures:
        lines.append("")
        lines.extend(_item_lines(row))
    return "\n".join(lines) + "\n"


def _predictions_by_id(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Last duplicate id wins, matching :func:`fin_qa_eval.graders.grade`."""

    chosen: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        pred_id = prediction.get("id")
        if isinstance(pred_id, str) and pred_id:
            chosen[pred_id] = prediction
    return chosen


def _selected(
    result: ItemResult,
    *,
    error: Optional[str],
    company: Optional[str],
    item_id: Optional[str],
) -> bool:
    if item_id is not None and result.id != item_id:
        return False
    if company is not None and result.company != company:
        return False
    if error is not None and result.primary_error != error and error not in result.errors:
        return False
    return True


def _failure_row(
    result: ItemResult,
    gold: dict[str, Any],
    prediction: Optional[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": result.id,
        "company": result.company,
        "report_period": result.report_period,
        "metric": result.metric,
        "scope": result.scope,
        "basis": result.basis,
        "profit_view": result.profit_view,
        "tax": result.tax,
        "unit": result.unit,
        "overall": result.overall,
        "numeric_accuracy": result.numeric_accuracy,
        "evidence_consistency": result.evidence_consistency,
        "refusal_appropriateness": result.refusal_appropriateness,
        "primary_error": result.primary_error,
        "errors": list(result.errors),
        "gold": _gold_view(gold),
        "prediction": _prediction_view(prediction),
    }


def _gold_view(gold: dict[str, Any]) -> dict[str, Any]:
    reference = gold.get("reference")
    if not isinstance(reference, dict):
        reference = {}
    return {
        "answerable": bool(reference.get("answerable")),
        "value": reference.get("value"),
        "unit": reference.get("unit"),
        "display": reference.get("display"),
        "refusal_reason": reference.get("refusal_reason"),
    }


def _prediction_view(prediction: Optional[dict[str, Any]]) -> dict[str, Any]:
    if prediction is None:
        return {
            "missing": True,
            "refused": None,
            "value": None,
            "unit": None,
            "answer": None,
        }
    parsed = resolve_prediction_amount(prediction)
    answer = prediction.get("answer")
    if answer is not None and not isinstance(answer, str):
        answer = str(answer)
    return {
        "missing": False,
        "refused": prediction_refused(prediction),
        "value": None if parsed is None else _json_number(parsed.value),
        "unit": None if parsed is None else parsed.unit,
        "answer": answer,
    }


def _by_primary_error(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        code = row.get("primary_error")
        if not isinstance(code, str) or not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return dict(ordered)


def _json_number(value: Decimal) -> int | float:
    """JSON number for a resolved amount. Integrals stay integers."""

    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _primary_line(counts: dict[str, int]) -> str:
    if not counts:
        return "by_primary_error: (none)"
    body = " ".join(f"{code}={count}" for code, count in counts.items())
    return f"by_primary_error: {body}"


def _filter_line(filters: dict[str, Any]) -> Optional[str]:
    parts: list[str] = []
    for name in ("error", "company", "id"):
        value = filters.get(name)
        if value is None:
            continue
        parts.append(f"{name}={_text_value(value)}")
    if not parts:
        return None
    return "filters " + " ".join(parts)


def _item_lines(row: dict[str, Any]) -> list[str]:
    errors = row["errors"]
    error_text = ",".join(errors) if errors else "(none)"
    head = (
        "{id} company={company} period={period} metric={metric} "
        "scope={scope} basis={basis} profit_view={profit_view} tax={tax} unit={unit} "
        "overall={overall} numeric_accuracy={numeric} evidence_consistency={evidence} "
        "refusal_appropriateness={refusal} primary_error={primary} errors={errors}"
    ).format(
        id=row["id"],
        company=_text_value(row["company"]),
        period=_text_value(row["report_period"]),
        metric=_text_value(row["metric"]),
        scope=_text_value(row["scope"]),
        basis=_text_value(row["basis"]),
        profit_view=_text_value(row["profit_view"]),
        tax=_text_value(row["tax"]),
        unit=_text_value(row["unit"]),
        overall=format_score(row["overall"]),
        numeric=format_score(row["numeric_accuracy"]),
        evidence=format_score(row["evidence_consistency"]),
        refusal=format_score(row["refusal_appropriateness"]),
        primary=_text_value(row["primary_error"]),
        errors=error_text,
    )
    gold = row["gold"]
    gold_line = (
        "  gold answerable={answerable} value={value} unit={unit} "
        "display={display} refusal_reason={reason}"
    ).format(
        answerable=_text_value(gold["answerable"]),
        value=_text_value(gold["value"]),
        unit=_text_value(gold["unit"]),
        display=_text_value(gold["display"]),
        reason=_text_value(gold["refusal_reason"]),
    )
    pred = row["prediction"]
    pred_line = (
        "  pred missing={missing} refused={refused} value={value} unit={unit} answer={answer}"
    ).format(
        missing=_text_value(pred["missing"]),
        refused=_text_value(pred["refused"]),
        value=_text_value(pred["value"]),
        unit=_text_value(pred["unit"]),
        answer=_text_value(pred["answer"]),
    )
    return [head, gold_line, pred_line]


def _text_value(value: Any) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, float):
        return _decimal_text(Decimal(str(value)))
    if isinstance(value, int):
        return str(value)
    return _quote(str(value))


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _quote(text: str) -> str:
    if text == "":
        return '""'
    if any(ch.isspace() for ch in text) or "=" in text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text
