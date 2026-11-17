from fin_qa_eval.graders import grade, grade_item, summarize
from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.report import format_score, render_grade_report

_CONVENTION_SECTIONS = (
    ("by_scope", "按口径范围 / By scope"),
    ("by_basis", "按会计基础 / By basis"),
    ("by_profit_view", "按利润视角 / By profit view"),
    ("by_tax", "按含税口径 / By tax"),
    ("by_unit", "按单位 / By unit"),
)


def test_fixture_scoreboard_is_stable(gold_path, pred_path) -> None:
    gold = load_jsonl(gold_path)
    preds = load_jsonl(pred_path)
    first = grade(gold, preds)
    second = grade(gold, preds)
    assert [row.to_dict() for row in first.results] == [row.to_dict() for row in second.results]
    summary = first.summary()
    assert summary["n"] == len(gold)
    assert format_score(summary["overall"]) == "0.8421"
    assert format_score(summary["numeric_accuracy"]) == "0.7632"
    assert format_score(summary["evidence_consistency"]) == "0.8421"
    assert format_score(summary["refusal_appropriateness"]) == "0.9211"
    assert summary["n_full_credit"] == 28

    by_id = {row.id: row for row in first.results}
    assert by_id["xlkj-2024q3-revenue"].primary_error == "convention_mismatch"
    assert by_id["chry-2024h1-revenue"].primary_error == "convention_mismatch"
    assert by_id["bcyy-2024fy-revenue-yoy"].primary_error == "numeric_mismatch"
    assert by_id["bcyy-2024fy-revenue-wanyuan"].primary_error == "unit_scale_error"
    assert by_id["ccsc-2024q3-revenue"].primary_error == "unit_scale_error"
    assert by_id["qhne-2024fy-ocf"].primary_error == "sign_error"
    assert by_id["wtjj-2023fy-revenue"].primary_error == "evidence_not_in_source"
    assert by_id["blsp-2024fy-net-profit"].primary_error == "over_refusal"
    assert by_id["lqwl-2025q1-ocf"].primary_error == "under_refusal"
    assert by_id["lqwl-2025q1-unit-ambiguous"].primary_error == "under_refusal"
    assert by_id["xlkj-2024q3-deducted-np"].overall == 1.0
    assert by_id["qhne-2024fy-ocf-yoy"].overall == 1.0
    assert by_id["lqwl-2025q1-annual-revenue"].overall == 1.0
    assert by_id["ccsc-2024q3-net-profit"].overall == 1.0

    report = render_grade_report(first, gold_name=str(gold_path), pred_name="fixture-extractor-v1")
    assert "数值准确 numeric_accuracy" in report
    assert "0.8421" in report
    assert "星澜科技" in report
    assert "convention_mismatch" in report
    assert "改进清单" in report
    assert "synthetic" in report.lower() or "虚构" in report
    _assert_section_order(report)


def test_convention_rollups_follow_gold(gold_path, pred_path, repo_root) -> None:
    gold = load_jsonl(gold_path)
    preds = load_jsonl(pred_path)
    graded = grade(gold, preds)
    summary = graded.summary()
    assert format_score(summary["overall"]) == "0.8421"
    assert format_score(summary["numeric_accuracy"]) == "0.7632"
    assert format_score(summary["evidence_consistency"]) == "0.8421"
    assert format_score(summary["refusal_appropriateness"]) == "0.9211"

    company_shape = set(next(iter(summary["by_company"].values())))
    for field, key in (
        ("scope", "by_scope"),
        ("basis", "by_basis"),
        ("profit_view", "by_profit_view"),
        ("tax", "by_tax"),
    ):
        labels = [_convention_label(item, field) for item in gold]
        assert set(summary[key]) == set(labels)
        assert list(summary[key]) == sorted(summary[key])
        for label, row in summary[key].items():
            assert set(row) == company_shape
            assert row["n"] == labels.count(label)
    unit_labels = [_bucket_label(item.get("unit")) for item in gold]
    assert set(summary["by_unit"]) == set(unit_labels)
    assert list(summary["by_unit"]) == sorted(summary["by_unit"])
    for label, row in summary["by_unit"].items():
        assert set(row) == company_shape
        assert row["n"] == unit_labels.count(label)
    assert {"consolidated", "parent"} <= set(summary["by_scope"])
    assert "(none)" in summary["by_profit_view"]
    assert "(none)" in summary["by_tax"]
    assert "None" not in summary["by_profit_view"]
    assert "None" not in summary["by_tax"]
    revenue = [row for row in graded.results if row.metric == "revenue"]
    assert revenue
    assert {row.profit_view for row in revenue} == {"(none)"}

    sample = next(row for row in graded.results if row.id == "xlkj-2024q3-revenue")
    dumped = sample.to_dict()
    assert dumped["scope"] == "consolidated"
    assert dumped["basis"] == "gaap"
    assert dumped["profit_view"] == "(none)"
    assert dumped["tax"] == "ex_tax"
    assert dumped["unit"] == "CNY_hundred_million"

    report = render_grade_report(
        graded,
        gold_name="data/samples/eval_set.jsonl",
        pred_name="examples/predictions.jsonl",
    )
    _assert_section_order(report)
    for key, heading in _CONVENTION_SECTIONS:
        section = _section(report, heading)
        for name, row in summary[key].items():
            assert _group_line(name, row) in section
    scoreboard = (repo_root / "examples" / "scoreboard.md").read_text(encoding="utf-8")
    assert scoreboard == report


def test_missing_convention_and_empty_summary_use_none_bucket() -> None:
    empty = summarize([])
    assert empty["n"] == 0
    assert empty["overall"] == 0.0
    for key in (
        "by_metric",
        "by_company",
        "by_period",
        "by_scope",
        "by_basis",
        "by_profit_view",
        "by_tax",
        "by_unit",
        "by_error",
    ):
        assert empty[key] == {}

    gold = {
        "id": "missing-conv",
        "company": "甲公司",
        "report_period": "2024FY",
        "metric": "revenue",
        "reference": {"answerable": False},
        "source_text": "【虚构示例】",
        "evidence_span": "",
    }
    missing = grade_item(gold, None)
    assert missing.to_dict()["scope"] == "(none)"
    assert missing.basis == "(none)"
    assert missing.profit_view == "(none)"
    assert missing.tax == "(none)"
    assert missing.unit == "(none)"

    gold["convention"] = {"scope": None, "basis": None, "profit_view": None, "tax": None}
    gold["unit"] = None
    nulled = grade_item(gold, None)
    assert nulled.to_dict()["scope"] == "(none)"
    assert nulled.to_dict()["unit"] == "(none)"
    summary = summarize([nulled])
    assert set(summary["by_scope"]) == {"(none)"}
    assert set(summary["by_unit"]) == {"(none)"}
    assert "None" not in summary["by_scope"]
    bucket = summary["by_tax"]["(none)"]
    assert bucket["n"] == 1
    assert bucket["top_error"] == "missing_prediction"
    assert set(bucket) == set(next(iter(summary["by_company"].values())))


def _bucket_label(value: object) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, str):
        return value
    return str(value)


def _convention_label(item: dict, name: str) -> str:
    convention = item.get("convention")
    if not isinstance(convention, dict):
        return "(none)"
    return _bucket_label(convention.get(name))


def _assert_section_order(report: str) -> None:
    headings = [
        "按公司 / By company",
        "按报告期 / By report period",
        "按指标 / By metric",
        *(heading for _, heading in _CONVENTION_SECTIONS),
        "按错误类型 / By error type",
    ]
    cursor = -1
    for heading in headings:
        position = report.index(f"## {heading}")
        assert position > cursor
        cursor = position


def _section(report: str, heading: str) -> str:
    start = report.index(f"## {heading}")
    end = report.index("\n## ", start + 1)
    return report[start:end]


def _group_line(name: str, row: dict) -> str:
    top = row["top_error"] or "—"
    return (
        f"| {name} | {row['n']} | {format_score(row['overall'])} | "
        f"{format_score(row['numeric_accuracy'])} | "
        f"{format_score(row['evidence_consistency'])} | "
        f"{format_score(row['refusal_appropriateness'])} | "
        f"{row['n_full_credit']} | {top} |"
    )
