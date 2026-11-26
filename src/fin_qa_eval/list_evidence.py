"""Inventory each gold item's evidence binding.

No predictions, no grading, and no network. :func:`collect_list_evidence`
walks the loaded JSONL in file order and returns one row per gold item,
including a missing or empty evidence span. ``source_text`` is not copied
into the payload.

- ``data``: display path of the gold file.
- ``summary``:
  - ``n``: loaded item count, before filters.
  - ``n_listed``: rows after filters.
  - ``n_with_evidence``: listed rows whose ``evidence_span`` is a non-empty
    string.
  - ``n_without_evidence``: the rest of the listed rows
    (``n_listed - n_with_evidence``).
  - ``n_contained``: listed rows whose span is contained in ``source_text``.
  - ``n_not_contained``: listed rows whose span is not contained, including
    missing and empty spans. With ``n_contained`` this partitions
    ``n_listed``.
  - ``n_sources``: distinct non-empty string ``source_id`` values among
    listed rows. A missing, empty, or non-string id does not count.
  With no filters, ``n == n_listed``.
- ``filters``: ``company``, ``metric``, ``period``, ``id``, ``source``, and
  ``kind``. Unset filters are JSON ``null``. Filters are ANDed exact
  matches. ``kind`` is one of ``with_evidence``, ``missing_evidence``,
  ``contained``, or ``not_contained``. ``not_contained`` keeps a non-empty
  span that fails containment. An empty or missing span is
  ``missing_evidence``, not that kind. ``contained`` is the helper's true
  result, which already requires a non-empty span.
- ``by_source``: histogram of ``source_id`` over the listed rows. Buckets
  are ``{"key": <str or None>, "n": <int>}``, sorted by ``n`` descending,
  then by key ascending. A missing, empty, or non-string source id is JSON
  ``null`` and sorts as empty. Same shape as ``list-distractors``
  ``by_reason``.
- ``items``: one object per listed row, in file order. Keys, in order:
  id, company, period (``report_period``), metric, ``source_id``,
  ``source_chars``, ``has_evidence``, ``evidence_span``, ``evidence_chars``,
  ``contained``, and ``answerable``.

``source_id`` is a non-empty string, otherwise JSON ``null``.
``source_chars`` is the character length of ``source_text`` when that field
is a string, otherwise ``0``. ``has_evidence`` is true only when
``evidence_span`` is a non-empty string. ``evidence_span`` keeps a string,
including ``""``; a missing or non-string field is JSON ``null``.
``evidence_chars`` is the length of that string, otherwise ``0``.
``contained`` calls :func:`fin_qa_eval.qc.evidence_contained` on the string
values, treating a missing or non-string field as ``""``. An empty span is
not contained, which is the helper's own rule. ``answerable`` is true only
when ``reference.answerable is True``, the same rule as ``list-items`` and
``stats``.

This inventory is not a gate. Missing spans and spans that are not
contained stay in the report. ``qc`` remains the pass/fail check.

:func:`render_list_evidence_text` prints that payload in the compact style
used by ``list-items``. Null fields print as ``(none)``. An empty item list
prints ``no items``. When rows remain, a ``by_source`` section in the same
bucket order sits between the filters line and the item lines.
"""

from __future__ import annotations

from typing import Any, Optional

from fin_qa_eval.qc import evidence_contained

KINDS = ("with_evidence", "missing_evidence", "contained", "not_contained")

_FILTER_NAMES = ("company", "metric", "period", "id", "source", "kind")

_ROW_KEYS = (
    "id",
    "company",
    "report_period",
    "metric",
    "source_id",
    "source_chars",
    "has_evidence",
    "evidence_span",
    "evidence_chars",
    "contained",
    "answerable",
)


def collect_list_evidence(
    items: list[dict[str, Any]],
    *,
    data_name: str,
    company: Optional[str] = None,
    metric: Optional[str] = None,
    period: Optional[str] = None,
    item_id: Optional[str] = None,
    source: Optional[str] = None,
    kind: Optional[str] = None,
) -> dict[str, Any]:
    """Build the evidence inventory described in the module docstring."""

    if kind is not None and kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")

    rows = [_item_row(item) for item in items]
    listed = [
        row
        for row in rows
        if _selected(
            row,
            company=company,
            metric=metric,
            period=period,
            item_id=item_id,
            source=source,
            kind=kind,
        )
    ]
    n_with_evidence = sum(1 for row in listed if row["has_evidence"])
    n_contained = sum(1 for row in listed if row["contained"])
    return {
        "data": data_name,
        "summary": {
            "n": len(items),
            "n_listed": len(listed),
            "n_with_evidence": n_with_evidence,
            "n_without_evidence": len(listed) - n_with_evidence,
            "n_contained": n_contained,
            "n_not_contained": len(listed) - n_contained,
            "n_sources": len({row["source_id"] for row in listed if row["source_id"]}),
        },
        "filters": {
            "company": company,
            "metric": metric,
            "period": period,
            "id": item_id,
            "source": source,
            "kind": kind,
        },
        "by_source": _source_histogram([row["source_id"] for row in listed]),
        "items": listed,
    }


def render_list_evidence_text(report: dict[str, Any]) -> str:
    """Compact inventory. An empty list ends with ``no items``."""

    summary = report["summary"]
    lines = [
        (
            "list-evidence items={n} listed={n_listed} "
            "with_evidence={with_evidence} without_evidence={without_evidence} "
            "contained={contained} not_contained={not_contained} sources={sources}"
        ).format(
            n=summary["n"],
            n_listed=summary["n_listed"],
            with_evidence=summary["n_with_evidence"],
            without_evidence=summary["n_without_evidence"],
            contained=summary["n_contained"],
            not_contained=summary["n_not_contained"],
            sources=summary["n_sources"],
        )
    ]
    filters = _filter_line(report.get("filters") or {})
    if filters:
        lines.append(filters)
    items = report.get("items") or []
    if not items:
        lines.append("no items")
        return "\n".join(lines) + "\n"
    lines.extend(_by_source_lines(report.get("by_source") or []))
    for row in items:
        lines.append(_item_line(row))
    return "\n".join(lines) + "\n"


def _item_row(item: dict[str, Any]) -> dict[str, Any]:
    span_raw = item.get("evidence_span")
    source_raw = item.get("source_text")
    span = span_raw if isinstance(span_raw, str) else ""
    source = source_raw if isinstance(source_raw, str) else ""
    evidence_span = span_raw if isinstance(span_raw, str) else None
    row = {
        "id": _optional_str(item.get("id")),
        "company": _optional_str(item.get("company")),
        "report_period": _optional_str(item.get("report_period")),
        "metric": _optional_str(item.get("metric")),
        "source_id": _source_id(item.get("source_id")),
        "source_chars": len(source_raw) if isinstance(source_raw, str) else 0,
        "has_evidence": isinstance(span_raw, str) and span_raw != "",
        "evidence_span": evidence_span,
        "evidence_chars": len(evidence_span) if evidence_span is not None else 0,
        "contained": evidence_contained(span, source),
        "answerable": _is_answerable(item),
    }
    return {key: row[key] for key in _ROW_KEYS}


def _source_id(value: Any) -> Optional[str]:
    """Non-empty string source id, or ``None``."""

    if isinstance(value, str) and value:
        return value
    return None


def _is_answerable(item: dict[str, Any]) -> bool:
    """True only when ``reference.answerable is True``. Same rule as stats."""

    reference = item.get("reference")
    if not isinstance(reference, dict):
        return False
    return reference.get("answerable") is True


def _selected(
    row: dict[str, Any],
    *,
    company: Optional[str],
    metric: Optional[str],
    period: Optional[str],
    item_id: Optional[str],
    source: Optional[str],
    kind: Optional[str],
) -> bool:
    if company is not None and row["company"] != company:
        return False
    if metric is not None and row["metric"] != metric:
        return False
    if period is not None and row["report_period"] != period:
        return False
    if item_id is not None and row["id"] != item_id:
        return False
    if source is not None and row["source_id"] != source:
        return False
    if kind == "with_evidence":
        return bool(row["has_evidence"])
    if kind == "missing_evidence":
        return not row["has_evidence"]
    if kind == "contained":
        return bool(row["contained"])
    if kind == "not_contained":
        return bool(row["has_evidence"]) and not row["contained"]
    return True


def _source_histogram(source_ids: list[Optional[str]]) -> list[dict[str, Any]]:
    counts: dict[Optional[str], int] = {}
    for source_id in source_ids:
        counts[source_id] = counts.get(source_id, 0) + 1
    rows = [{"key": key, "n": n} for key, n in counts.items()]
    rows.sort(key=_source_sort_key)
    return rows


def _source_sort_key(row: dict[str, Any]) -> tuple[int, str]:
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


def _by_source_lines(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["by_source:"]
    for row in rows:
        lines.append(f"  {_text_value(row['key'])} n={row['n']}")
    return lines


def _item_line(row: dict[str, Any]) -> str:
    return (
        "{id} company={company} period={period} metric={metric} "
        "source_id={source_id} source_chars={source_chars} "
        "has_evidence={has_evidence} evidence_span={evidence_span} "
        "evidence_chars={evidence_chars} contained={contained} "
        "answerable={answerable}"
    ).format(
        id=_text_value(row["id"]),
        company=_text_value(row["company"]),
        period=_text_value(row["report_period"]),
        metric=_text_value(row["metric"]),
        source_id=_text_value(row["source_id"]),
        source_chars=_text_value(row["source_chars"]),
        has_evidence=_text_value(row["has_evidence"]),
        evidence_span=_text_value(row["evidence_span"]),
        evidence_chars=_text_value(row["evidence_chars"]),
        contained=_text_value(row["contained"]),
        answerable=_text_value(row["answerable"]),
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
