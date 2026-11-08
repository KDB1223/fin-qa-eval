from fin_qa_eval.graders import grade
from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.report import format_score, render_grade_report


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
