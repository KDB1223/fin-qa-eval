"""Markdown error-attribution reports and a data/prompt checklist."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fin_qa_eval.graders import GradeOutput, ItemResult
from fin_qa_eval.qc import QCReport

# Triggered only when the matching error is present. Wording is bilingual
# because the dataset is Chinese-first and the README is English.
_CHECKLIST = {
    "unit_scale_error": {
        "data": "为同一事实保留万元与亿元两种表述，并在参考答案里写好换算后的值。 / Keep the same fact in 万元 and 亿元, with the reference already converted.",
        "prompt": "先抄写题目要求的单位，再写出换算因子（1亿元 = 10,000万元 = 100百万元）后作答。 / Restate the unit the question asks for, then show the conversion factor before the number.",
    },
    "convention_mismatch": {
        "data": "在金标证据旁保留对照干扰项：合并/母公司、含税/不含税、归母/扣非。 / Keep contrastive distractors beside the gold span (scope, tax, attributable vs. deducted).",
        "prompt": "作答前绑定口径：scope、basis、profit_view。片段只有另一种口径时拒答，不要改用相邻数字。 / Bind scope, basis, and profit view. If the snippet only has another 口径, refuse.",
    },
    "sign_error": {
        "data": "保留现金流为负、利润同比为负的样本，避免数据集只有正数。 / Keep negative cash flow and negative YoY rows so the set is not all positive.",
        "prompt": "保留原文中的负号、下降、亏损；净额为负时不要取绝对值。 / Keep minus signs and words such as 下降 or 亏损. Do not abs() a net outflow.",
    },
    "numeric_mismatch": {
        "data": "同比题写明比较期在前还是本期在前；需要计算的题标注 requires_calculation。 / State which amount is current vs. prior, and tag rows that require a calculation.",
        "prompt": "同比百分比 = (本期 − 比较期) / 比较期，四舍五入到 0.01 个百分点。基数≤0 时按口径拒答。 / YoY = (current − prior) / prior, half-up to 0.01pp. Refuse when the base is not positive.",
    },
    "evidence_not_in_source": {
        "data": "证据跨度必须是 source_text 的连续子串，QC 会拦截写不回去的 span。 / Evidence spans must be exact substrings; QC rejects spans that cannot be copied back.",
        "prompt": "证据必须从片段逐字复制，不要改写数字或单位。 / Copy the evidence span verbatim from the snippet. Do not paraphrase the number.",
    },
    "evidence_missing": {
        "data": "可答题的 evidence_span 不能为空。 / Answerable rows need a non-empty evidence span.",
        "prompt": "每个数值答案都附上支持它的原句。 / Attach the supporting sentence to every numeric answer.",
    },
    "evidence_wrong_span": {
        "data": "一题只保留一个金标跨度，其余数字放进 distractors。 / One gold span per item; put the other figures in distractors.",
        "prompt": "引用的句子必须包含所答数字，且与题目的口径一致。 / The quoted sentence must contain the answered number and the requested 口径.",
    },
    "evidence_overclaim": {
        "data": "拒答题写清缺失的是期间、口径还是单位，方便对照 refusal_reason。 / State whether a refusal case lacks the period, the 口径, or the unit.",
        "prompt": "证据不够时输出拒答及原因，不要用片段里的其他数字填空。 / When evidence is insufficient, refuse with a reason. Do not fill the blank with a nearby number.",
    },
    "over_refusal": {
        "data": "可答题的片段里金标数字必须出现，避免模型被训练成一律拒答。 / The gold number must actually appear, so models are not pushed to refuse everything.",
        "prompt": "只有在期间、口径或单位无法唯一确定时才拒答。 / Refuse only when the period, 口径, or unit cannot be uniquely determined.",
    },
    "under_refusal": {
        "data": "保留证据不足、越界期间、单位不明、负基数同比这几类边界。 / Keep insufficient-evidence, out-of-period, ambiguous-unit, and negative-base YoY boundaries.",
        "prompt": "若题目要求的口径在片段中不存在，拒答并给出 refusal_reason，不要编造数值。 / If the requested 口径 is absent, refuse with a reason. Do not invent a figure.",
    },
    "unparseable_answer": {
        "data": "参考答案同时给出 value、unit 与 display。 / Ship value, unit, and display together on the reference.",
        "prompt": "输出结构化 value 与 unit；中文答案写成「128.6亿元」或「同比-13.99%」。 / Emit structured value and unit. Chinese answers look like 128.6亿元 or 同比-13.99%.",
    },
    "missing_prediction": {
        "data": "评分文件应按金标 id 对齐，漏 id 会被记 0 分。 / Prediction files should cover every gold id; a missing id scores 0.",
        "prompt": "对每道题都给出答案或拒答，不要跳题。 / Answer or refuse every item. Do not skip ids.",
    },
}


def format_score(value: float) -> str:
    """Four decimal places, half-up, stable across machines."""

    quantized = Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return f"{quantized:.4f}"


def render_grade_report(
    graded: GradeOutput,
    *,
    gold_name: str,
    pred_name: str,
) -> str:
    summary = graded.summary()
    lines: list[str] = [
        "# fin-qa-eval 评分报告 / Grade report",
        "",
        "> Synthetic demo data only. Scores are computed offline and do not call a model API.",
        "> 数据为虚构示例。评分在本地完成，不调用模型 API。",
        "",
        f"- Gold: `{gold_name}`",
        f"- Predictions: `{pred_name}`",
        f"- Items: {summary['n']}",
        f"- Full credit: {summary['n_full_credit']} / {summary['n']}",
        "",
        "## 总表 / Scoreboard",
        "",
        "| 维度 Dimension | 得分 Score |",
        "| --- | ---: |",
        f"| 数值准确 numeric_accuracy | {format_score(summary['numeric_accuracy'])} |",
        f"| 证据一致 evidence_consistency | {format_score(summary['evidence_consistency'])} |",
        f"| 拒答合理 refusal_appropriateness | {format_score(summary['refusal_appropriateness'])} |",
        f"| **综合 overall** | **{format_score(summary['overall'])}** |",
        "",
    ]
    if graded.warnings:
        lines.extend(["## 警告 / Warnings", ""])
        lines.extend(f"- {warning}" for warning in graded.warnings)
        lines.append("")
    lines.extend(_group_section("按公司 / By company", summary["by_company"]))
    lines.extend(_group_section("按报告期 / By report period", summary["by_period"]))
    lines.extend(_group_section("按指标 / By metric", summary["by_metric"]))
    lines.extend(_error_section(summary["by_error"]))
    lines.extend(_failure_section(graded.results))
    lines.extend(_checklist_section(summary["by_error"]))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_qc_report(report: QCReport, *, data_name: str) -> str:
    lines = [
        "# fin-qa-eval 质检报告 / QC report",
        "",
        f"- Data: `{data_name}`",
        f"- Items: {report.items_checked}",
        f"- Errors: {report.error_count}",
        f"- Status: {'PASS' if report.ok else 'FAIL'}",
        "",
        "## 边界样本 / Boundary inventory",
        "",
        "| 边界 Boundary | 条数 Count |",
        "| --- | ---: |",
    ]
    if report.boundary_counts:
        for name, count in report.boundary_counts.items():
            lines.append(f"| {name} | {count} |")
    else:
        lines.append("| (none) | 0 |")
    lines.extend(["", "## 问题 / Issues", ""])
    if not report.issues:
        lines.append("无错误。No errors.")
    else:
        lines.extend(
            [
                "| 代码 Code | 严重性 | id | 说明 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for issue in report.issues:
            lines.append(
                f"| {issue.code} | {issue.severity} | {issue.item_id or ''} | {_cell(issue.message)} |"
            )
    lines.append("")
    return "\n".join(lines)


def _group_section(title: str, grouped: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| 分组 Group | n | 综合 overall | 数值 | 证据 | 拒答 | 满分 | 主要错误 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, row in grouped.items():
        top = row["top_error"] or "—"
        lines.append(
            "| {name} | {n} | {overall} | {numeric} | {evidence} | {refusal} | {full} | {top} |".format(
                name=_cell(name),
                n=row["n"],
                overall=format_score(row["overall"]),
                numeric=format_score(row["numeric_accuracy"]),
                evidence=format_score(row["evidence_consistency"]),
                refusal=format_score(row["refusal_appropriateness"]),
                full=row["n_full_credit"],
                top=top,
            )
        )
    lines.append("")
    return lines


def _error_section(counts: dict[str, int]) -> list[str]:
    lines = [
        "## 按错误类型 / By error type",
        "",
        "一条样本可以带多个错误标签。分数只由三个维度决定，错误标签用于归因。",
        "An item may carry more than one error tag. Scores come only from the three dimensions.",
        "",
        "| 错误类型 Error | 条数 Count |",
        "| --- | ---: |",
    ]
    if not counts:
        lines.append("| (none) | 0 |")
    else:
        for code, count in counts.items():
            lines.append(f"| {code} | {count} |")
    lines.append("")
    return lines


def _failure_section(results: list[ItemResult]) -> list[str]:
    failures = [row for row in results if row.overall < 1.0]
    failures.sort(key=lambda row: (row.overall, row.id))
    lines = [
        "## 错例 / Failures",
        "",
        "| id | 公司 | 期间 | 指标 | 综合 | 主错误 | 全部错误 |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    if not failures:
        lines.append("| (none) |  |  |  |  |  |  |")
    else:
        for row in failures:
            lines.append(
                "| {id} | {company} | {period} | {metric} | {overall} | {primary} | {errors} |".format(
                    id=row.id,
                    company=_cell(row.company),
                    period=row.report_period,
                    metric=row.metric,
                    overall=format_score(row.overall),
                    primary=row.primary_error or "",
                    errors=", ".join(row.errors),
                )
            )
    lines.append("")
    return lines


def _checklist_section(counts: dict[str, int]) -> list[str]:
    lines = [
        "## 改进清单 / Improvement checklist",
        "",
        "### 数据 Data",
        "",
        "- 全部样本保持 `synthetic: true`，公司与数字均为虚构，不写入真实披露原文。 / Keep every row synthetic. Do not paste proprietary filings.",
        "- 新增题目前先跑 `fin-qa-eval qc`，确认没有重复题、单位异常和证据落空。 / Run `fin-qa-eval qc` before adding rows.",
    ]
    prompts = [
        "- 输出里同时给出 value、unit、evidence；拒答时给出原因，不要只写「不知道」。 / Emit value, unit, and evidence. A refusal needs a reason, not a bare shrug.",
    ]
    data_lines: list[str] = []
    for code in counts:
        advice = _CHECKLIST.get(code)
        if not advice:
            continue
        data_lines.append(f"- ({code}) {advice['data']}")
        prompts.append(f"- ({code}) {advice['prompt']}")
    lines.extend(data_lines)
    lines.extend(["", "### 提示词 Prompts", ""])
    lines.extend(prompts)
    return lines


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def qc_status_line(report: QCReport) -> str:
    boundary = ", ".join(f"{name}={count}" for name, count in report.boundary_counts.items()) or "none"
    state = "PASS" if report.ok else "FAIL"
    return (
        f"qc {state}: items={report.items_checked} errors={report.error_count} "
        f"boundary: {boundary}"
    )

