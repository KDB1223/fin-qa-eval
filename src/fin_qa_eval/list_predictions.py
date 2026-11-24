"""Inventory a prediction file against a gold eval set.

No model calls, no grading, and no writes. :func:`collect_list_predictions`
walks prediction rows in file order, including rows with a missing id and
duplicate ids. It does not drop rows the way :func:`fin_qa_eval.graders.grade`
does (that grader keeps the last row for an id).

- ``data``, ``pred``: display paths of the gold file and the prediction file.
- ``summary`` counts, before filters: ``n_gold`` (gold item count),
  ``n_pred`` (prediction row count), ``n_gold_covered`` (distinct usable gold
  ids that appear at least once on a prediction row with a usable id),
  ``n_gold_missing`` (``n_gold - n_gold_covered``), ``n_missing_id``,
  ``n_unknown``, and ``n_duplicate``.
- ``summary`` counts, after filters: ``n_listed``, and among listed rows only
  ``n_refused``, ``n_with_value``, ``n_with_evidence``, and ``n_in_gold``.
- ``filters``: ``id``, ``company``, and ``kind``. Unset filters are JSON
  ``null``. Filters are ANDed exact matches. ``kind`` is one of
  ``in_gold``, ``unknown``, ``missing_id``, ``duplicate``, or ``refused``.
- ``missing_gold``: usable gold ids with no usable matching prediction, in
  gold file order. Each id is listed once, at its first gold row. This list
  is not affected by row filters. A gold row whose id is missing, empty, or
  not a string has no id to list; it still counts in ``n_gold`` and therefore
  in ``n_gold_missing``. Duplicate gold ids count once toward
  ``n_gold_covered`` and once in this list.
- ``predictions``: listed rows in file order. Keys, in order: ``id``,
  ``in_gold``, ``unknown``, ``duplicate``, ``refused``, ``has_value``,
  ``unit``, ``has_evidence``, ``has_answer``, ``company``, ``report_period``,
  ``metric``.

A usable id is a non-empty string, the same rule ``grade`` uses. A missing,
empty, or non-string id is JSON ``null``. It counts as ``missing_id``, is
not ``in_gold``, is not ``unknown``, and is not a duplicate of other
missing-id rows. ``in_gold`` is true only when that usable id appears on a
gold item. ``unknown`` is true when the usable id is not in the gold set.
``duplicate`` is true when the usable id already appeared earlier in the
prediction file; the first occurrence is not a duplicate. If gold repeats an
id, company, period, and metric come from the first gold item with that id.
Rows that are not in gold have those three fields as JSON ``null``.

``refused`` reuses :func:`fin_qa_eval.graders.prediction_refused`.
``has_value`` is true when ``value`` is not ``None``. ``unit`` uses the same
missing/null handling as ``list-items``. ``has_evidence`` and ``has_answer``
are true when the stripped text is non-empty.

:func:`render_list_predictions_text` prints that payload in the compact
style used by ``list-items``. Nulls print as ``(none)``. Booleans print as
``true`` / ``false``. An empty listed set prints ``no predictions``. When
``missing_gold`` is non-empty, a ``missing_gold`` section follows the row
section, one id per line. That section is omitted when the list is empty,
and it is not hidden by row filters.
"""

from __future__ import annotations

from typing import Any, Optional

from fin_qa_eval.graders import prediction_refused

KINDS = ("in_gold", "unknown", "missing_id", "duplicate", "refused")

_FILTER_NAMES = ("id", "company", "kind")

_ROW_KEYS = (
    "id",
    "in_gold",
    "unknown",
    "duplicate",
    "refused",
    "has_value",
    "unit",
    "has_evidence",
    "has_answer",
    "company",
    "report_period",
    "metric",
)


def collect_list_predictions(
    gold_items: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    data_name: str,
    pred_name: str,
    item_id: Optional[str] = None,
    company: Optional[str] = None,
    kind: Optional[str] = None,
) -> dict[str, Any]:
    """Build the prediction inventory described in the module docstring."""

    if kind is not None and kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")

    gold_by_id: dict[str, dict[str, Any]] = {}
    gold_ids_in_order: list[str] = []
    for item in gold_items:
        gold_id = _usable_id(item)
        if gold_id is None or gold_id in gold_by_id:
            continue
        gold_by_id[gold_id] = item
        gold_ids_in_order.append(gold_id)

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        pred_id = _usable_id(prediction)
        duplicate = pred_id is not None and pred_id in seen
        if pred_id is not None:
            seen.add(pred_id)
        rows.append(_prediction_row(prediction, pred_id, duplicate, gold_by_id))

    pred_ids = seen
    covered = [gold_id for gold_id in gold_ids_in_order if gold_id in pred_ids]
    missing_gold = [gold_id for gold_id in gold_ids_in_order if gold_id not in pred_ids]
    n_gold_covered = len(covered)

    listed = [
        row
        for row in rows
        if _selected(row, item_id=item_id, company=company, kind=kind)
    ]
    return {
        "data": data_name,
        "pred": pred_name,
        "summary": {
            "n_gold": len(gold_items),
            "n_pred": len(predictions),
            "n_gold_covered": n_gold_covered,
            "n_gold_missing": len(gold_items) - n_gold_covered,
            "n_missing_id": sum(1 for row in rows if row["id"] is None),
            "n_unknown": sum(1 for row in rows if row["unknown"]),
            "n_duplicate": sum(1 for row in rows if row["duplicate"]),
            "n_listed": len(listed),
            "n_refused": sum(1 for row in listed if row["refused"]),
            "n_with_value": sum(1 for row in listed if row["has_value"]),
            "n_with_evidence": sum(1 for row in listed if row["has_evidence"]),
            "n_in_gold": sum(1 for row in listed if row["in_gold"]),
        },
        "filters": {
            "id": item_id,
            "company": company,
            "kind": kind,
        },
        "missing_gold": missing_gold,
        "predictions": listed,
    }


def render_list_predictions_text(report: dict[str, Any]) -> str:
    """Compact inventory. An empty listed set prints ``no predictions``."""

    summary = report["summary"]
    lines = [
        (
            "list-predictions gold={n_gold} pred={n_pred} listed={n_listed} "
            "covered={covered} missing_gold={missing_gold} unknown={unknown} "
            "missing_id={missing_id} duplicate={duplicate} refused={refused} "
            "with_value={with_value} with_evidence={with_evidence}"
        ).format(
            n_gold=summary["n_gold"],
            n_pred=summary["n_pred"],
            n_listed=summary["n_listed"],
            covered=summary["n_gold_covered"],
            missing_gold=summary["n_gold_missing"],
            unknown=summary["n_unknown"],
            missing_id=summary["n_missing_id"],
            duplicate=summary["n_duplicate"],
            refused=summary["n_refused"],
            with_value=summary["n_with_value"],
            with_evidence=summary["n_with_evidence"],
        )
    ]
    filters = _filter_line(report.get("filters") or {})
    if filters:
        lines.append(filters)
    rows = report.get("predictions") or []
    if not rows:
        lines.append("no predictions")
    else:
        for row in rows:
            lines.append(_prediction_line(row))
    missing_gold = report.get("missing_gold") or []
    if missing_gold:
        lines.append("missing_gold")
        for gold_id in missing_gold:
            lines.append(_text_value(gold_id))
    return "\n".join(lines) + "\n"


def _usable_id(row: dict[str, Any]) -> Optional[str]:
    """Non-empty string id, or ``None``. Same rule as ``grade``."""

    row_id = row.get("id")
    if isinstance(row_id, str) and row_id:
        return row_id
    return None


def _prediction_row(
    prediction: dict[str, Any],
    pred_id: Optional[str],
    duplicate: bool,
    gold_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gold = gold_by_id.get(pred_id) if pred_id is not None else None
    in_gold = gold is not None
    if in_gold:
        company = _optional_str(gold.get("company"))
        period = _optional_str(gold.get("report_period"))
        metric = _optional_str(gold.get("metric"))
    else:
        company = None
        period = None
        metric = None
    row = {
        "id": pred_id,
        "in_gold": in_gold,
        "unknown": pred_id is not None and not in_gold,
        "duplicate": duplicate,
        "refused": prediction_refused(prediction),
        "has_value": prediction.get("value") is not None,
        "unit": _optional_str(prediction.get("unit")),
        "has_evidence": _nonempty_text(prediction.get("evidence")),
        "has_answer": _nonempty_text(prediction.get("answer")),
        "company": company,
        "report_period": period,
        "metric": metric,
    }
    return {key: row[key] for key in _ROW_KEYS}


def _selected(
    row: dict[str, Any],
    *,
    item_id: Optional[str],
    company: Optional[str],
    kind: Optional[str],
) -> bool:
    if item_id is not None and row["id"] != item_id:
        return False
    if company is not None and row["company"] != company:
        return False
    if kind == "in_gold":
        return bool(row["in_gold"])
    if kind == "unknown":
        return bool(row["unknown"])
    if kind == "missing_id":
        return row["id"] is None
    if kind == "duplicate":
        return bool(row["duplicate"])
    if kind == "refused":
        return bool(row["refused"])
    return True


def _nonempty_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _optional_str(value: Any) -> Optional[str]:
    """JSON string, or ``None`` when the field is missing or null."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _filter_line(filters: dict[str, Any]) -> Optional[str]:
    parts: list[str] = []
    for name in _FILTER_NAMES:
        value = filters.get(name)
        if value is None:
            continue
        parts.append(f"{name}={_text_value(value)}")
    if not parts:
        return None
    return "filters " + " ".join(parts)


def _prediction_line(row: dict[str, Any]) -> str:
    return (
        "{id} in_gold={in_gold} unknown={unknown} duplicate={duplicate} "
        "refused={refused} has_value={has_value} unit={unit} "
        "has_evidence={has_evidence} has_answer={has_answer} "
        "company={company} period={period} metric={metric}"
    ).format(
        id=_text_value(row["id"]),
        in_gold=_text_value(row["in_gold"]),
        unknown=_text_value(row["unknown"]),
        duplicate=_text_value(row["duplicate"]),
        refused=_text_value(row["refused"]),
        has_value=_text_value(row["has_value"]),
        unit=_text_value(row["unit"]),
        has_evidence=_text_value(row["has_evidence"]),
        has_answer=_text_value(row["has_answer"]),
        company=_text_value(row["company"]),
        period=_text_value(row["report_period"]),
        metric=_text_value(row["metric"]),
    )


def _text_value(value: Any) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return _quote(str(value))


def _quote(text: str) -> str:
    if text == "":
        return '""'
    if any(ch.isspace() for ch in text) or "=" in text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text
