"""Inventory 口径 trap figures stored on gold items.

No predictions, no grading, and no network. :func:`collect_list_distractors`
walks the loaded JSONL in file order. Within each item it walks
``distractors[]`` in listed order and returns one row per distractor object:

- ``data``: display path of the gold file
- ``summary``:
  - ``n``: loaded item count, before filters.
  - ``n_listed``: distractor rows after filters.
  - ``n_with_distractors``: loaded items that contain at least one
    distractor object, before filters. Row filters do not change it.
  - ``n_without_distractors``: the rest of the loaded items
    (``n - n_with_distractors``), also before filters.
- ``filters``: ``reason``, ``company``, ``metric``, and ``id``. Unset
  filters are JSON ``null``. Filters are ANDed exact matches.
- ``by_reason``: histogram of ``reason`` over the listed rows. Buckets are
  ``{"key": <str or None>, "n": <int>}``, sorted by ``n`` descending, then
  by key ascending. A missing reason is JSON ``null`` and sorts as empty.
- ``distractors``: one object per listed row, in file order. Each object
  carries the item id, company, period (``report_period``), metric, and the
  distractor's reason, value, unit, and span. Missing or null fields are
  JSON ``null``.

A missing ``distractors`` field, a non-list, or an empty list contributes
zero rows and the item counts as without distractors. A non-dict entry is
skipped: it is not a row, and it does not by itself make the item count as
having a distractor. A list of only non-dicts therefore counts as none.

:func:`render_list_distractors_text` prints that payload in the compact
style used by ``list-items``. Null fields print as ``(none)``. An empty
row list prints ``no distractors``. The reason histogram is part of the
JSON payload and is not repeated as extra text lines.
"""

from __future__ import annotations

from typing import Any, Optional

_FILTER_NAMES = ("reason", "company", "metric", "id")

_ROW_KEYS = (
    "id",
    "company",
    "report_period",
    "metric",
    "reason",
    "value",
    "unit",
    "span",
)


def collect_list_distractors(
    items: list[dict[str, Any]],
    *,
    data_name: str,
    reason: Optional[str] = None,
    company: Optional[str] = None,
    metric: Optional[str] = None,
    item_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build the distractor inventory described in the module docstring."""

    listed: list[dict[str, Any]] = []
    n_with = 0
    for item in items:
        entries = _distractor_entries(item)
        if entries:
            n_with += 1
        for entry in entries:
            if _selected(
                item,
                entry,
                reason=reason,
                company=company,
                metric=metric,
                item_id=item_id,
            ):
                listed.append(_row(item, entry))
    return {
        "data": data_name,
        "summary": {
            "n": len(items),
            "n_listed": len(listed),
            "n_with_distractors": n_with,
            "n_without_distractors": len(items) - n_with,
        },
        "filters": {
            "reason": reason,
            "company": company,
            "metric": metric,
            "id": item_id,
        },
        "by_reason": _reason_histogram([row["reason"] for row in listed]),
        "distractors": listed,
    }


def render_list_distractors_text(report: dict[str, Any]) -> str:
    """Compact inventory. An empty list ends with ``no distractors``."""

    summary = report["summary"]
    lines = [
        (
            "list-distractors items={n} listed={n_listed} "
            "with_distractors={with_distractors} without_distractors={without_distractors}"
        ).format(
            n=summary["n"],
            n_listed=summary["n_listed"],
            with_distractors=summary["n_with_distractors"],
            without_distractors=summary["n_without_distractors"],
        )
    ]
    filters = _filter_line(report.get("filters") or {})
    if filters:
        lines.append(filters)
    rows = report.get("distractors") or []
    if not rows:
        lines.append("no distractors")
        return "\n".join(lines) + "\n"
    for row in rows:
        lines.append(_distractor_line(row))
    return "\n".join(lines) + "\n"


def _distractor_entries(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Dict entries of ``distractors``, in listed order.

    A missing field, a non-list, or an empty list yields no entries. Non-dict
    entries are dropped rather than guessed.
    """

    raw = item.get("distractors")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _selected(
    item: dict[str, Any],
    entry: dict[str, Any],
    *,
    reason: Optional[str],
    company: Optional[str],
    metric: Optional[str],
    item_id: Optional[str],
) -> bool:
    if reason is not None and _optional_str(entry.get("reason")) != reason:
        return False
    if company is not None and _optional_str(item.get("company")) != company:
        return False
    if metric is not None and _optional_str(item.get("metric")) != metric:
        return False
    if item_id is not None and _optional_str(item.get("id")) != item_id:
        return False
    return True


def _row(item: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": _optional_str(item.get("id")),
        "company": _optional_str(item.get("company")),
        "report_period": _optional_str(item.get("report_period")),
        "metric": _optional_str(item.get("metric")),
        "reason": _optional_str(entry.get("reason")),
        "value": _optional_value(entry.get("value")),
        "unit": _optional_str(entry.get("unit")),
        "span": _optional_str(entry.get("span")),
    }
    return {key: row[key] for key in _ROW_KEYS}


def _reason_histogram(reasons: list[Optional[str]]) -> list[dict[str, Any]]:
    counts: dict[Optional[str], int] = {}
    for reason in reasons:
        counts[reason] = counts.get(reason, 0) + 1
    rows = [{"key": key, "n": n} for key, n in counts.items()]
    rows.sort(key=_reason_sort_key)
    return rows


def _reason_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    """Count descending, then key ascending. A null key sorts as empty."""

    key = row["key"]
    return (-row["n"], "" if key is None else str(key))


def _optional_str(value: Any) -> Optional[str]:
    """JSON string, or ``None`` when the field is missing or null."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _optional_value(value: Any) -> Any:
    """JSON number, bool, string, or ``None``.

    Missing or null stays ``None``. ``bool`` is checked before ``int`` so
    ``True`` is not stored as ``1``. Any other non-null value is stringified
    so the row stays JSON-safe.
    """

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
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


def _distractor_line(row: dict[str, Any]) -> str:
    return (
        "{id} company={company} period={period} metric={metric} "
        "reason={reason} value={value} unit={unit} span={span}"
    ).format(
        id=_text_value(row["id"]),
        company=_text_value(row["company"]),
        period=_text_value(row["report_period"]),
        metric=_text_value(row["metric"]),
        reason=_text_value(row["reason"]),
        value=_text_value(row["value"]),
        unit=_text_value(row["unit"]),
        span=_text_value(row["span"]),
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
