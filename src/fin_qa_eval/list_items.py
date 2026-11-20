"""Inventory each item in a gold eval set.

No predictions, no grading, and no network. :func:`collect_list_items`
walks the loaded JSONL in file order and returns a JSON-ready dict:

- ``data``: display path of the gold file
- ``summary``: ``n`` is the loaded count, before filters. ``n_listed``,
  ``n_answerable``, and ``n_unanswerable`` describe the rows that remain.
  Answerable counts use the same rule as ``stats``: ``reference.answerable
  is True``. With no filters, ``n == n_listed``.
- ``filters``: ``company``, ``metric``, ``period``, ``id``, and ``refusal``.
  Unset filters are JSON ``null``. Filters are ANDed exact matches.
- ``items``: one object per listed row, in file order. Each object carries
  id, company, period, metric, 口径 (``scope``, ``basis``, ``profit_view``,
  ``tax``), unit, language, ``answerable``, and ``refusal_reason``. Missing
  or null fields are JSON ``null``. Question text, source text, evidence,
  gold numbers, and distractors are omitted.

:func:`render_list_items_text` prints that payload in the compact style
used by ``stats`` and ``failures``. Null fields print as ``(none)``. An
empty item list prints ``no items``.
"""

from __future__ import annotations

from typing import Any, Optional

_FILTER_NAMES = ("company", "metric", "period", "id", "refusal")

_ITEM_KEYS = (
    "id",
    "company",
    "report_period",
    "metric",
    "scope",
    "basis",
    "profit_view",
    "tax",
    "unit",
    "language",
    "answerable",
    "refusal_reason",
)


def collect_list_items(
    items: list[dict[str, Any]],
    *,
    data_name: str,
    company: Optional[str] = None,
    metric: Optional[str] = None,
    period: Optional[str] = None,
    item_id: Optional[str] = None,
    refusal: Optional[str] = None,
) -> dict[str, Any]:
    """Build the item inventory described in the module docstring."""

    listed = [
        _item_row(item)
        for item in items
        if _selected(
            item,
            company=company,
            metric=metric,
            period=period,
            item_id=item_id,
            refusal=refusal,
        )
    ]
    n_answerable = sum(1 for row in listed if row["answerable"])
    return {
        "data": data_name,
        "summary": {
            "n": len(items),
            "n_listed": len(listed),
            "n_answerable": n_answerable,
            "n_unanswerable": len(listed) - n_answerable,
        },
        "filters": {
            "company": company,
            "metric": metric,
            "period": period,
            "id": item_id,
            "refusal": refusal,
        },
        "items": listed,
    }


def render_list_items_text(report: dict[str, Any]) -> str:
    """Compact inventory. An empty list ends with ``no items``."""

    summary = report["summary"]
    lines = [
        (
            "list-items items={n} listed={n_listed} "
            "answerable={answerable} unanswerable={unanswerable}"
        ).format(
            n=summary["n"],
            n_listed=summary["n_listed"],
            answerable=summary["n_answerable"],
            unanswerable=summary["n_unanswerable"],
        )
    ]
    filters = _filter_line(report.get("filters") or {})
    if filters:
        lines.append(filters)
    items = report.get("items") or []
    if not items:
        lines.append("no items")
        return "\n".join(lines) + "\n"
    for row in items:
        lines.append(_item_line(row))
    return "\n".join(lines) + "\n"


def _selected(
    item: dict[str, Any],
    *,
    company: Optional[str],
    metric: Optional[str],
    period: Optional[str],
    item_id: Optional[str],
    refusal: Optional[str],
) -> bool:
    if company is not None and _optional_str(item.get("company")) != company:
        return False
    if metric is not None and _optional_str(item.get("metric")) != metric:
        return False
    if period is not None and _optional_str(item.get("report_period")) != period:
        return False
    if item_id is not None and _optional_str(item.get("id")) != item_id:
        return False
    if refusal is not None and _refusal_reason(item) != refusal:
        return False
    return True


def _item_row(item: dict[str, Any]) -> dict[str, Any]:
    convention = item.get("convention")
    if not isinstance(convention, dict):
        convention = {}
    row = {
        "id": _optional_str(item.get("id")),
        "company": _optional_str(item.get("company")),
        "report_period": _optional_str(item.get("report_period")),
        "metric": _optional_str(item.get("metric")),
        "scope": _optional_str(convention.get("scope")),
        "basis": _optional_str(convention.get("basis")),
        "profit_view": _optional_str(convention.get("profit_view")),
        "tax": _optional_str(convention.get("tax")),
        "unit": _optional_str(item.get("unit")),
        "language": _optional_str(item["language"]) if "language" in item else None,
        "answerable": _is_answerable(item),
        "refusal_reason": _refusal_reason(item),
    }
    return {key: row[key] for key in _ITEM_KEYS}


def _is_answerable(item: dict[str, Any]) -> bool:
    """True only when ``reference.answerable is True``. Same rule as stats."""

    reference = item.get("reference")
    if not isinstance(reference, dict):
        return False
    return reference.get("answerable") is True


def _refusal_reason(item: dict[str, Any]) -> Optional[str]:
    reference = item.get("reference")
    if not isinstance(reference, dict):
        return None
    return _optional_str(reference.get("refusal_reason"))


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


def _item_line(row: dict[str, Any]) -> str:
    return (
        "{id} company={company} period={period} metric={metric} "
        "scope={scope} basis={basis} profit_view={profit_view} tax={tax} "
        "unit={unit} language={language} answerable={answerable} refusal_reason={reason}"
    ).format(
        id=_text_value(row["id"]),
        company=_text_value(row["company"]),
        period=_text_value(row["report_period"]),
        metric=_text_value(row["metric"]),
        scope=_text_value(row["scope"]),
        basis=_text_value(row["basis"]),
        profit_view=_text_value(row["profit_view"]),
        tax=_text_value(row["tax"]),
        unit=_text_value(row["unit"]),
        language=_text_value(row["language"]),
        answerable=_text_value(row["answerable"]),
        reason=_text_value(row["refusal_reason"]),
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
