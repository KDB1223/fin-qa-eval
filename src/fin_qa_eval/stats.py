"""Inventory coverage of a gold eval set.

No predictions, no grading, and no network. :func:`collect_stats` counts
items and builds histograms for companies, metrics, periods, units, 口径
fields (``scope``, ``basis``, ``profit_view``, ``tax``), language, and
refusal reasons.

Each histogram is a list of buckets sorted by ``n`` descending, then by
key ascending. A missing key sorts as empty, so it comes first when
counts tie. A bucket is::

    {"key": <str or None>, "n": <int>, "n_answerable": <int>, "n_unanswerable": <int>}

``key`` is JSON ``null`` when the field is missing or null, and text
renders that as ``(none)``. ``by_refusal_reason`` drops null reasons so
answerable rows are not given a fake refusal label. ``by_language`` is
omitted when no item carries the field.

:func:`render_stats_text` prints the same bucket order in the compact
style used by ``grade`` and ``compare``.
"""

from __future__ import annotations

from typing import Any, Optional

# Printed in this order. ``by_language`` is included only when present.
HISTOGRAMS = (
    "by_company",
    "by_metric",
    "by_period",
    "by_unit",
    "by_scope",
    "by_basis",
    "by_profit_view",
    "by_tax",
    "by_refusal_reason",
    "by_language",
)

# (histogram name, nested field path, drop null keys)
_FIELDS: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("by_company", ("company",), False),
    ("by_metric", ("metric",), False),
    ("by_period", ("report_period",), False),
    ("by_unit", ("unit",), False),
    ("by_scope", ("convention", "scope"), False),
    ("by_basis", ("convention", "basis"), False),
    ("by_profit_view", ("convention", "profit_view"), False),
    ("by_tax", ("convention", "tax"), False),
    ("by_refusal_reason", ("reference", "refusal_reason"), True),
)


def collect_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the coverage payload described in the module docstring."""

    answerable = [_is_answerable(item) for item in items]
    n_answerable = sum(answerable)
    payload: dict[str, Any] = {
        "n": len(items),
        "n_answerable": n_answerable,
        "n_unanswerable": len(items) - n_answerable,
    }
    for name, path, drop_null in _FIELDS:
        keys = [_bucket_key(_nested(item, path)) for item in items]
        payload[name] = _histogram(keys, answerable, drop_null=drop_null)
    if any("language" in item for item in items):
        keys = [
            _bucket_key(item["language"]) if "language" in item else None
            for item in items
        ]
        payload["by_language"] = _histogram(keys, answerable)
    return payload


def render_stats_text(report: dict[str, Any]) -> str:
    """Compact text inventory. Null keys print as ``(none)``."""

    lines = [
        "stats items={n} answerable={answerable} unanswerable={unanswerable}".format(
            n=report["n"],
            answerable=report["n_answerable"],
            unanswerable=report["n_unanswerable"],
        )
    ]
    for name in HISTOGRAMS:
        rows = report.get(name)
        if rows is None:
            continue
        lines.append(f"{name}:")
        for row in rows:
            lines.append(f"  {_text_label(row['key'])} n={row['n']}")
    return "\n".join(lines) + "\n"


def _is_answerable(item: dict[str, Any]) -> bool:
    reference = item.get("reference")
    if not isinstance(reference, dict):
        return False
    return reference.get("answerable") is True


def _nested(item: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = item
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _bucket_key(value: Any) -> Optional[str]:
    """Histogram key. A missing value stays ``None`` so JSON emits ``null``."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _histogram(
    keys: list[Optional[str]],
    answerable: list[bool],
    *,
    drop_null: bool = False,
) -> list[dict[str, Any]]:
    counts: dict[Optional[str], list[int]] = {}
    for key, is_answerable in zip(keys, answerable):
        if drop_null and key is None:
            continue
        slot = counts.setdefault(key, [0, 0])
        slot[0] += 1
        if is_answerable:
            slot[1] += 1
    rows = [
        {
            "key": key,
            "n": n,
            "n_answerable": n_answerable,
            "n_unanswerable": n - n_answerable,
        }
        for key, (n, n_answerable) in counts.items()
    ]
    rows.sort(key=_sort_key)
    return rows


def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
    """Count descending, then key ascending. A null key sorts as empty."""

    key = row["key"]
    return (-row["n"], "" if key is None else str(key))


def _text_label(key: Optional[str]) -> str:
    if key is None:
        return "(none)"
    return key
