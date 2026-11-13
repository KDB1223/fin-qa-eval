"""Diff two graded prediction files on the same gold set.

``pred_a`` is the baseline and ``pred_b`` is the candidate. Scores come from
:func:`fin_qa_eval.graders.grade`; this module does not reimplement
tolerances or error tags. An item is improved when the candidate overall is
higher, regressed when it is lower, and unchanged otherwise. Overall is the
mean of the three dimension scores already stored on each item.

:func:`compare_grades` returns a JSON-ready dict with a stable key order:

- ``gold``, ``pred_a``, ``pred_b``: display paths
- ``baseline`` and ``candidate``: ``n``, ``n_full_credit``, ``overall``,
  ``numeric_accuracy``, ``evidence_consistency``, ``refusal_appropriateness``
- ``delta``: candidate minus baseline for those same keys
- ``counts``: ``improved``, ``regressed``, ``unchanged``,
  ``primary_error_changed``
- ``transitions``: objects ``{"from", "to", "count"}`` for items whose
  primary error changed, sorted by count descending, then ``from``, then
  ``to``. A missing primary error is JSON ``null`` and sorts as empty.
- ``improved`` and ``regressed``: objects with ``id``, ``company``,
  ``overall_a``, ``overall_b``, ``delta``, ``primary_error_a``, and
  ``primary_error_b``, sorted by absolute overall delta descending, then id
- ``warnings``: grader warnings for each file, under ``a`` and ``b``

Both grade outputs should come from the same gold list. Items are paired by
id. Displayed scores use :func:`fin_qa_eval.report.format_score`. Deltas use
the same four-decimal half-up rounding and gain a leading ``+`` when the
rounded value is positive.
"""

from __future__ import annotations

from typing import Any, Optional

from fin_qa_eval.graders import GradeOutput, ItemResult
from fin_qa_eval.report import format_score

SUMMARY_KEYS = (
    "n",
    "n_full_credit",
    "overall",
    "numeric_accuracy",
    "evidence_consistency",
    "refusal_appropriateness",
)


def format_delta(value: float) -> str:
    """Signed four-decimal half-up delta. A rounded zero stays ``0.0000``."""

    text = format_score(value)
    if text.startswith("-") or text == "0.0000":
        return text
    return f"+{text}"


def compare_grades(
    baseline: GradeOutput,
    candidate: GradeOutput,
    *,
    gold_name: str,
    pred_a_name: str,
    pred_b_name: str,
) -> dict[str, Any]:
    """Build the comparison payload described in the module docstring."""

    summary_a = _pick_summary(baseline.summary())
    summary_b = _pick_summary(candidate.summary())
    improved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    unchanged = 0
    transition_counts: dict[tuple[Optional[str], Optional[str]], int] = {}
    changed = 0
    for row_a, row_b in _pairs(baseline, candidate):
        if row_a.primary_error != row_b.primary_error:
            changed += 1
            key = (row_a.primary_error, row_b.primary_error)
            transition_counts[key] = transition_counts.get(key, 0) + 1
        if row_b.overall > row_a.overall:
            improved.append(_item_row(row_a, row_b))
        elif row_b.overall < row_a.overall:
            regressed.append(_item_row(row_a, row_b))
        else:
            unchanged += 1
    improved.sort(key=_item_sort_key)
    regressed.sort(key=_item_sort_key)
    transitions = [
        {"from": src, "to": dst, "count": count}
        for (src, dst), count in sorted(transition_counts.items(), key=_transition_sort_key)
    ]
    return {
        "gold": gold_name,
        "pred_a": pred_a_name,
        "pred_b": pred_b_name,
        "baseline": summary_a,
        "candidate": summary_b,
        "delta": {key: summary_b[key] - summary_a[key] for key in SUMMARY_KEYS},
        "counts": {
            "improved": len(improved),
            "regressed": len(regressed),
            "unchanged": unchanged,
            "primary_error_changed": changed,
        },
        "transitions": transitions,
        "improved": improved,
        "regressed": regressed,
        "warnings": {"a": list(baseline.warnings), "b": list(candidate.warnings)},
    }


def is_regression(report: dict[str, Any]) -> bool:
    """True when candidate overall drops or any item overall decreases."""

    if report["delta"]["overall"] < 0:
        return True
    return report["counts"]["regressed"] > 0


def render_compare_text(report: dict[str, Any]) -> str:
    """Compact scoreboard plus the improved and regressed item lists."""

    lines = [
        f"gold: {report['gold']}",
        f"pred_a: {report['pred_a']}",
        f"pred_b: {report['pred_b']}",
        _summary_line("baseline", report["baseline"]),
        _summary_line("candidate", report["candidate"]),
        _delta_line(report["delta"]),
    ]
    for warning in report["warnings"]["a"]:
        lines.append(f"warning A: {warning}")
    for warning in report["warnings"]["b"]:
        lines.append(f"warning B: {warning}")
    counts = report["counts"]
    lines.append(
        "items improved={improved} regressed={regressed} unchanged={unchanged} "
        "primary_error_changed={changed}".format(
            improved=counts["improved"],
            regressed=counts["regressed"],
            unchanged=counts["unchanged"],
            changed=counts["primary_error_changed"],
        )
    )
    lines.extend(_text_transitions(report["transitions"]))
    lines.extend(_text_items("improved", report["improved"]))
    lines.extend(_text_items("regressed", report["regressed"]))
    return "\n".join(lines) + "\n"


def render_compare_markdown(report: dict[str, Any]) -> str:
    """Bilingual Markdown comparison. Chinese headings come first."""

    baseline = report["baseline"]
    candidate = report["candidate"]
    delta = report["delta"]
    counts = report["counts"]
    lines: list[str] = [
        "# fin-qa-eval 对比报告 / Compare report",
        "",
        "> Synthetic demo data only. Scores are computed offline and do not call a model API.",
        "> 数据为虚构示例。评分在本地完成，不调用模型 API。",
        "",
        f"- Gold: `{report['gold']}`",
        f"- Pred A (baseline): `{report['pred_a']}`",
        f"- Pred B (candidate): `{report['pred_b']}`",
        "",
        "## 总表 / Scoreboard",
        "",
        "| 维度 Dimension | A 基线 baseline | B 候选 candidate | B-A |",
        "| --- | ---: | ---: | ---: |",
        _markdown_count_row("题数 n", baseline, candidate, delta, "n"),
        _markdown_count_row("满分 n_full_credit", baseline, candidate, delta, "n_full_credit"),
        _markdown_score_row(
            "数值准确 numeric_accuracy",
            baseline,
            candidate,
            delta,
            "numeric_accuracy",
        ),
        _markdown_score_row(
            "证据一致 evidence_consistency",
            baseline,
            candidate,
            delta,
            "evidence_consistency",
        ),
        _markdown_score_row(
            "拒答合理 refusal_appropriateness",
            baseline,
            candidate,
            delta,
            "refusal_appropriateness",
        ),
        _markdown_score_row("综合 overall", baseline, candidate, delta, "overall", bold=True),
        "",
    ]
    if report["warnings"]["a"] or report["warnings"]["b"]:
        lines.extend(["## 警告 / Warnings", ""])
        lines.extend(f"- A: {warning}" for warning in report["warnings"]["a"])
        lines.extend(f"- B: {warning}" for warning in report["warnings"]["b"])
        lines.append("")
    lines.extend(
        [
            "## 变动计数 / Change counts",
            "",
            "一条样本按综合分比较。综合分是数值、证据、拒答三个维度的算术平均。",
            "An item is improved when the candidate overall is higher and regressed when it is lower.",
            "",
            f"- 提升 improved: {counts['improved']}",
            f"- 回退 regressed: {counts['regressed']}",
            f"- 不变 unchanged: {counts['unchanged']}",
            f"- 主错误变化 primary_error changed: {counts['primary_error_changed']}",
            "",
            "## 主错误迁移 / Primary-error transitions",
            "",
            "只列出主错误发生变化的题目。空值表示没有主错误（满分或未打上标签）。",
            "Only items whose primary error changed are listed. An empty cell means no primary error.",
            "",
            "| 从 From | 到 To | 条数 Count |",
            "| --- | --- | ---: |",
        ]
    )
    if report["transitions"]:
        for row in report["transitions"]:
            lines.append(
                f"| {_markdown_error(row['from'])} | {_markdown_error(row['to'])} | {row['count']} |"
            )
    else:
        lines.append("| (none) |  | 0 |")
    lines.append("")
    lines.extend(_markdown_items("提升 / Improved", report["improved"]))
    lines.extend(_markdown_items("回退 / Regressed", report["regressed"]))
    return "\n".join(lines).rstrip() + "\n"


def _pick_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: summary[key] for key in SUMMARY_KEYS}


def _pairs(
    baseline: GradeOutput,
    candidate: GradeOutput,
) -> list[tuple[ItemResult, ItemResult]]:
    by_id = {row.id: row for row in candidate.results}
    return [(row, by_id[row.id]) for row in baseline.results if row.id in by_id]


def _item_row(row_a: ItemResult, row_b: ItemResult) -> dict[str, Any]:
    return {
        "id": row_a.id,
        "company": row_a.company,
        "overall_a": row_a.overall,
        "overall_b": row_b.overall,
        "delta": row_b.overall - row_a.overall,
        "primary_error_a": row_a.primary_error,
        "primary_error_b": row_b.primary_error,
    }


def _item_sort_key(row: dict[str, Any]) -> tuple[float, str]:
    return (-abs(row["delta"]), row["id"])


def _transition_sort_key(
    item: tuple[tuple[Optional[str], Optional[str]], int],
) -> tuple[int, str, str]:
    """Count descending, then from, then to. A missing error sorts as empty."""

    (src, dst), count = item
    return (-count, src or "", dst or "")


def _summary_line(label: str, summary: dict[str, Any]) -> str:
    return (
        "{label} n={n} full_credit={full} overall={overall} "
        "numeric={numeric} evidence={evidence} refusal={refusal}"
    ).format(
        label=label,
        n=summary["n"],
        full=summary["n_full_credit"],
        overall=format_score(summary["overall"]),
        numeric=format_score(summary["numeric_accuracy"]),
        evidence=format_score(summary["evidence_consistency"]),
        refusal=format_score(summary["refusal_appropriateness"]),
    )


def _delta_line(delta: dict[str, Any]) -> str:
    return (
        "delta n={n} full_credit={full} overall={overall} "
        "numeric={numeric} evidence={evidence} refusal={refusal}"
    ).format(
        n=_format_count_delta(delta["n"]),
        full=_format_count_delta(delta["n_full_credit"]),
        overall=format_delta(delta["overall"]),
        numeric=format_delta(delta["numeric_accuracy"]),
        evidence=format_delta(delta["evidence_consistency"]),
        refusal=format_delta(delta["refusal_appropriateness"]),
    )


def _format_count_delta(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def _error_label(value: Optional[str]) -> str:
    return value if value else "(none)"


def _text_transitions(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["transitions: (none)"]
    lines = ["transitions:"]
    for row in rows:
        lines.append(
            "  {src} -> {dst} count={count}".format(
                src=_error_label(row["from"]),
                dst=_error_label(row["to"]),
                count=row["count"],
            )
        )
    return lines


def _text_items(title: str, rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return [f"{title}: (none)"]
    lines = [f"{title}:"]
    for row in rows:
        lines.append(
            "  {id} {company} overall {left} -> {right} primary {src} -> {dst}".format(
                id=row["id"],
                company=row["company"],
                left=format_score(row["overall_a"]),
                right=format_score(row["overall_b"]),
                src=_error_label(row["primary_error_a"]),
                dst=_error_label(row["primary_error_b"]),
            )
        )
    return lines


def _markdown_count_row(
    label: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    delta: dict[str, Any],
    key: str,
) -> str:
    return (
        f"| {label} | {baseline[key]} | {candidate[key]} | {_format_count_delta(delta[key])} |"
    )


def _markdown_score_row(
    label: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    delta: dict[str, Any],
    key: str,
    *,
    bold: bool = False,
) -> str:
    cells = [
        label,
        format_score(baseline[key]),
        format_score(candidate[key]),
        format_delta(delta[key]),
    ]
    if bold:
        cells = [f"**{cell}**" for cell in cells]
    return "| " + " | ".join(cells) + " |"


def _markdown_error(value: Optional[str]) -> str:
    return value if value else "—"


def _markdown_items(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| id | 公司 Company | 综合 A | 综合 B | 主错误 A | 主错误 B |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    if not rows:
        lines.append("| (none) |  |  |  |  |  |")
    else:
        for row in rows:
            lines.append(
                "| {id} | {company} | {left} | {right} | {src} | {dst} |".format(
                    id=row["id"],
                    company=_cell(str(row["company"])),
                    left=format_score(row["overall_a"]),
                    right=format_score(row["overall_b"]),
                    src=_markdown_error(row["primary_error_a"]),
                    dst=_markdown_error(row["primary_error_b"]),
                )
            )
    lines.append("")
    return lines


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
