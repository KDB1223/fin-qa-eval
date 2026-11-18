"""Failure inventory. Counts and error tags come from the shipped fixture."""

from __future__ import annotations

import io
import json
from pathlib import Path

from fin_qa_eval.cli import main
from fin_qa_eval.failures import collect_failures, render_failures_text
from fin_qa_eval.graders import grade
from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.report import format_score

# Same order as the report 错例 table: overall ascending, then id.
_FIXTURE_FAILURES = (
    "blsp-2024fy-net-profit",
    "lqwl-2025q1-ocf",
    "lqwl-2025q1-unit-ambiguous",
    "chry-2024h1-revenue",
    "xlkj-2024q3-revenue",
    "bcyy-2024fy-revenue-wanyuan",
    "bcyy-2024fy-revenue-yoy",
    "ccsc-2024q3-revenue",
    "qhne-2024fy-ocf",
    "wtjj-2023fy-revenue",
)

_PRIMARY = {
    "xlkj-2024q3-revenue": "convention_mismatch",
    "chry-2024h1-revenue": "convention_mismatch",
    "bcyy-2024fy-revenue-wanyuan": "unit_scale_error",
    "ccsc-2024q3-revenue": "unit_scale_error",
    "qhne-2024fy-ocf": "sign_error",
    "blsp-2024fy-net-profit": "over_refusal",
    "lqwl-2025q1-ocf": "under_refusal",
    "lqwl-2025q1-unit-ambiguous": "under_refusal",
    "bcyy-2024fy-revenue-yoy": "numeric_mismatch",
    "wtjj-2023fy-revenue": "evidence_not_in_source",
}


def test_fixture_failures_join_gold_and_prediction(gold_path: Path, pred_path: Path) -> None:
    gold = load_jsonl(gold_path)
    preds = load_jsonl(pred_path)
    graded = grade(gold, preds)
    summary = graded.summary()
    assert format_score(summary["overall"]) == "0.8421"
    assert format_score(summary["numeric_accuracy"]) == "0.7632"
    assert format_score(summary["evidence_consistency"]) == "0.8421"
    assert format_score(summary["refusal_appropriateness"]) == "0.9211"
    assert summary["n_full_credit"] == 28

    report = collect_failures(
        graded,
        gold,
        preds,
        gold_name="data/samples/eval_set.jsonl",
        pred_name="examples/predictions.jsonl",
    )
    assert report["gold"] == "data/samples/eval_set.jsonl"
    assert report["pred"] == "examples/predictions.jsonl"
    assert report["summary"]["n"] == 38
    assert report["summary"]["n_failures"] == 10
    assert report["summary"]["n_full_credit"] == 28
    assert report["summary"]["n"] == (
        report["summary"]["n_failures"] + report["summary"]["n_full_credit"]
    )
    assert report["summary"]["by_primary_error"] == {
        "convention_mismatch": 2,
        "under_refusal": 2,
        "unit_scale_error": 2,
        "evidence_not_in_source": 1,
        "numeric_mismatch": 1,
        "over_refusal": 1,
        "sign_error": 1,
    }
    assert report["filters"] == {"error": None, "company": None, "id": None}
    assert [row["id"] for row in report["failures"]] == list(_FIXTURE_FAILURES)
    by_id = {row["id"]: row for row in report["failures"]}
    for item_id, primary in _PRIMARY.items():
        assert by_id[item_id]["primary_error"] == primary
        assert primary in by_id[item_id]["errors"]

    xlkj = by_id["xlkj-2024q3-revenue"]
    assert xlkj["company"] == "星澜科技"
    assert xlkj["report_period"] == "2024Q3"
    assert xlkj["metric"] == "revenue"
    assert xlkj["scope"] == "consolidated"
    assert xlkj["basis"] == "gaap"
    assert xlkj["profit_view"] == "(none)"
    assert xlkj["tax"] == "ex_tax"
    assert xlkj["unit"] == "CNY_hundred_million"
    assert format_score(xlkj["overall"]) == "0.3333"
    assert xlkj["numeric_accuracy"] == 0.0
    assert xlkj["evidence_consistency"] == 0.0
    assert xlkj["refusal_appropriateness"] == 1.0
    assert xlkj["gold"] == {
        "answerable": True,
        "value": 128.6,
        "unit": "CNY_hundred_million",
        "display": "128.6亿元",
        "refusal_reason": None,
    }
    assert xlkj["prediction"]["missing"] is False
    assert xlkj["prediction"]["refused"] is False
    assert xlkj["prediction"]["value"] == 86.2
    assert xlkj["prediction"]["unit"] == "CNY_hundred_million"
    assert xlkj["prediction"]["answer"] == "86.2亿元"

    chry = by_id["chry-2024h1-revenue"]
    assert chry["tax"] == "ex_tax"
    assert chry["gold"]["value"] == 92.4
    assert chry["gold"]["unit"] == "CNY_hundred_million"
    assert chry["prediction"]["value"] == 104.4
    assert chry["prediction"]["answer"] == "104.4亿元"

    wanyuan = by_id["bcyy-2024fy-revenue-wanyuan"]
    assert wanyuan["unit"] == "CNY_ten_thousand"
    assert wanyuan["gold"]["value"] == 3562000
    assert wanyuan["gold"]["unit"] == "CNY_ten_thousand"
    assert wanyuan["prediction"]["value"] == 356.2
    assert wanyuan["prediction"]["unit"] == "CNY_ten_thousand"
    assert format_score(wanyuan["overall"]) == "0.6667"

    ccsc = by_id["ccsc-2024q3-revenue"]
    assert ccsc["gold"]["value"] == 189.5
    assert ccsc["prediction"]["value"] == 18950
    assert ccsc["prediction"]["unit"] == "CNY_hundred_million"

    ocf = by_id["qhne-2024fy-ocf"]
    assert ocf["gold"]["value"] == -3.8
    assert ocf["prediction"]["value"] == 3.8
    assert ocf["prediction"]["refused"] is False

    refused = by_id["blsp-2024fy-net-profit"]
    assert refused["overall"] == 0.0
    assert refused["gold"]["answerable"] is True
    assert refused["gold"]["value"] == 0.82
    assert refused["prediction"]["refused"] is True
    assert refused["prediction"]["value"] is None
    assert refused["prediction"]["answer"] == "拒答：利润过小无法确认"

    invented = by_id["lqwl-2025q1-ocf"]
    assert invented["errors"] == ["under_refusal", "evidence_overclaim"]
    assert invented["gold"]["answerable"] is False
    assert invented["gold"]["value"] is None
    assert invented["gold"]["refusal_reason"] == "insufficient_evidence"
    assert invented["prediction"]["refused"] is False
    assert invented["prediction"]["value"] == 12
    assert invented["prediction"]["unit"] == "CNY_hundred_million"

    ambiguous = by_id["lqwl-2025q1-unit-ambiguous"]
    assert "under_refusal" in ambiguous["errors"]
    assert "evidence_overclaim" in ambiguous["errors"]
    assert ambiguous["gold"]["refusal_reason"] == "unit_ambiguous"
    assert ambiguous["prediction"]["value"] == 7.6

    yoy = by_id["bcyy-2024fy-revenue-yoy"]
    assert yoy["gold"]["value"] == 4.73
    assert yoy["prediction"]["value"] == 4.5
    assert format_score(yoy["overall"]) == "0.6667"

    full_credit = {row.id for row in graded.results if row.overall == 1.0}
    assert full_credit.isdisjoint({row["id"] for row in report["failures"]})
    assert "xlkj-2024q3-revenue-yoy" in full_credit

    text = render_failures_text(report)
    assert text.startswith(
        "failures items=38 failures=10 full_credit=28\n"
        "by_primary_error: convention_mismatch=2 under_refusal=2 unit_scale_error=2 "
        "evidence_not_in_source=1 numeric_mismatch=1 over_refusal=1 sign_error=1\n"
    )
    assert "no failures" not in text
    ids_in_order = [block.split()[0] for block in text.strip().split("\n\n")[1:]]
    assert ids_in_order == list(_FIXTURE_FAILURES)
    xlkj_block = next(block for block in text.split("\n\n") if block.startswith("xlkj-2024q3-revenue "))
    assert "scope=consolidated" in xlkj_block
    assert "basis=gaap" in xlkj_block
    assert "profit_view=(none)" in xlkj_block
    assert "tax=ex_tax" in xlkj_block
    assert "unit=CNY_hundred_million" in xlkj_block
    assert "overall=0.3333" in xlkj_block
    assert "numeric_accuracy=0.0000" in xlkj_block
    assert "evidence_consistency=0.0000" in xlkj_block
    assert "refusal_appropriateness=1.0000" in xlkj_block
    assert "primary_error=convention_mismatch" in xlkj_block
    assert "errors=convention_mismatch" in xlkj_block
    assert "gold answerable=true value=128.6 unit=CNY_hundred_million display=128.6亿元 refusal_reason=(none)" in xlkj_block
    assert "pred missing=false refused=false value=86.2 unit=CNY_hundred_million answer=86.2亿元" in xlkj_block
    lqwl_block = next(block for block in text.split("\n\n") if block.startswith("lqwl-2025q1-ocf "))
    assert "errors=under_refusal,evidence_overclaim" in lqwl_block
    assert "refusal_reason=insufficient_evidence" in lqwl_block
    assert render_failures_text(report) == text


def test_failures_command_json_and_filters(gold_path: Path, pred_path: Path) -> None:
    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--format",
                "json",
            ],
            stdout=buf,
        )
        == 0
    )
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n_failures"] == 10
    assert len(payload["failures"]) == 10
    assert "xlkj-2024q3-net-profit" not in {row["id"] for row in payload["failures"]}

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--format",
                "json",
                "--error",
                "convention_mismatch",
            ],
            stdout=buf,
        )
        == 0
    )
    filtered = json.loads(buf.getvalue())
    assert [row["id"] for row in filtered["failures"]] == [
        "chry-2024h1-revenue",
        "xlkj-2024q3-revenue",
    ]
    assert filtered["summary"]["n"] == 38
    assert filtered["summary"]["n_full_credit"] == 28
    assert filtered["summary"]["n_failures"] == 2
    assert filtered["summary"]["by_primary_error"] == {"convention_mismatch": 2}
    assert filtered["filters"]["error"] == "convention_mismatch"

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--format",
                "json",
                "--error",
                "evidence_overclaim",
            ],
            stdout=buf,
        )
        == 0
    )
    secondary = json.loads(buf.getvalue())
    assert [row["id"] for row in secondary["failures"]] == [
        "lqwl-2025q1-ocf",
        "lqwl-2025q1-unit-ambiguous",
    ]
    assert secondary["summary"]["by_primary_error"] == {"under_refusal": 2}

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--format",
                "json",
                "--error",
                "unit_scale_error",
                "--company",
                "北辰医药",
            ],
            stdout=buf,
        )
        == 0
    )
    combined = json.loads(buf.getvalue())
    assert [row["id"] for row in combined["failures"]] == ["bcyy-2024fy-revenue-wanyuan"]
    assert combined["filters"] == {
        "error": "unit_scale_error",
        "company": "北辰医药",
        "id": None,
    }

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--error",
                "convention_mismatch",
                "--id",
                "xlkj-2024q3-revenue",
            ],
            stdout=buf,
        )
        == 0
    )
    text = buf.getvalue()
    assert "xlkj-2024q3-revenue " in text
    assert "chry-2024h1-revenue" not in text
    assert "filters error=convention_mismatch id=xlkj-2024q3-revenue" in text

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--error",
                "sign_error",
                "--company",
                "星澜科技",
            ],
            stdout=buf,
        )
        == 0
    )
    empty = buf.getvalue()
    assert "failures items=38 failures=0 full_credit=28" in empty
    assert "by_primary_error: (none)" in empty
    assert empty.strip().endswith("no failures")
    assert "qhne-2024fy-ocf" not in empty

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--company",
                "北辰",
            ],
            stdout=buf,
        )
        == 0
    )
    assert buf.getvalue().strip().endswith("no failures")

    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--id",
                "xlkj-2024q3-revenue-yoy",
            ],
            stdout=buf,
        )
        == 0
    )
    assert "no failures" in buf.getvalue()
    assert "xlkj-2024q3-revenue " not in buf.getvalue()


def test_all_correct_prints_no_failures(tmp_path: Path) -> None:
    gold_file = tmp_path / "gold.jsonl"
    pred_file = tmp_path / "pred.jsonl"
    _write_jsonl(gold_file, [_answerable("ok-1")])
    _write_jsonl(pred_file, [_correct_pred("ok-1")])
    buf = io.StringIO()
    assert (
        main(
            ["failures", "--data", str(gold_file), "--pred", str(pred_file)],
            stdout=buf,
        )
        == 0
    )
    text = buf.getvalue()
    assert text.startswith("failures items=1 failures=0 full_credit=1\n")
    assert "by_primary_error: (none)\n" in text
    assert text.strip().endswith("no failures")
    assert "ok-1 company=" not in text


def test_partial_credit_and_missing_prediction(tmp_path: Path) -> None:
    gold = _answerable("span-1")
    gold["source_text"] = "【虚构示例】营业收入1.0亿元，另有说明。"
    wrong_span = _correct_pred("span-1")
    wrong_span["evidence"] = "另有说明"
    missing_gold = _answerable("gone-1")
    gold_file = tmp_path / "gold.jsonl"
    pred_file = tmp_path / "pred.jsonl"
    _write_jsonl(gold_file, [gold, missing_gold])
    _write_jsonl(pred_file, [wrong_span])
    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_file),
                "--pred",
                str(pred_file),
                "--format",
                "json",
            ],
            stdout=buf,
        )
        == 0
    )
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n"] == 2
    assert payload["summary"]["n_full_credit"] == 0
    assert payload["summary"]["n_failures"] == 2
    by_id = {row["id"]: row for row in payload["failures"]}
    assert by_id["span-1"]["primary_error"] == "evidence_wrong_span"
    assert by_id["span-1"]["evidence_consistency"] == 0.5
    assert by_id["span-1"]["overall"] < 1.0
    assert by_id["span-1"]["prediction"]["value"] == 1
    assert by_id["gone-1"]["primary_error"] == "missing_prediction"
    assert by_id["gone-1"]["overall"] == 0.0
    assert by_id["gone-1"]["prediction"]["missing"] is True
    assert by_id["gone-1"]["prediction"]["refused"] is None
    assert by_id["gone-1"]["gold"]["value"] == 1.0
    text = render_failures_text(payload)
    assert "pred missing=true refused=(none)" in text
    assert "primary_error=missing_prediction" in text


def test_duplicate_prediction_shows_the_graded_value() -> None:
    gold = [_answerable("dup-1")]
    predictions = [
        {
            "id": "dup-1",
            "answer": "86.2亿元",
            "value": 86.2,
            "unit": "CNY_hundred_million",
            "evidence": "营业收入1.0亿元",
            "refused": False,
        },
        _correct_pred("dup-1"),
    ]
    graded = grade(gold, predictions)
    report = collect_failures(
        graded,
        gold,
        predictions,
        gold_name="gold.jsonl",
        pred_name="pred.jsonl",
    )
    assert report["summary"]["n_failures"] == 0
    assert report["warnings"] == ["duplicate prediction for dup-1; last one wins"]
    text = render_failures_text(report)
    assert "no failures" in text
    assert "warning: duplicate prediction for dup-1; last one wins" in text

    predictions.reverse()
    graded = grade(gold, predictions)
    report = collect_failures(
        graded,
        gold,
        predictions,
        gold_name="gold.jsonl",
        pred_name="pred.jsonl",
    )
    assert report["failures"][0]["prediction"]["value"] == 86.2
    assert report["failures"][0]["primary_error"] == "numeric_mismatch"


def test_missing_pred_file_exits_2(tmp_path: Path, gold_path: Path, capsys) -> None:
    code = main(
        ["failures", "--data", str(gold_path), "--pred", str(tmp_path / "missing.jsonl")]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert captured.out == ""

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    assert main(["failures", "--data", str(gold_path), "--pred", str(bad)]) == 2


def test_schema_flag_is_accepted_and_unused(tmp_path: Path, gold_path: Path, pred_path: Path) -> None:
    buf = io.StringIO()
    assert (
        main(
            [
                "failures",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--schema",
                str(tmp_path / "no-such-schema.json"),
            ],
            stdout=buf,
        )
        == 0
    )
    assert "failures items=38 failures=10 full_credit=28" in buf.getvalue()


def test_default_pred_path(monkeypatch, repo_root: Path, gold_path: Path) -> None:
    monkeypatch.chdir(repo_root)
    buf = io.StringIO()
    assert main(["failures", "--data", str(gold_path), "--format", "json"], stdout=buf) == 0
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n_failures"] == 10
    assert payload["pred"].endswith("examples/predictions.jsonl")


def _answerable(item_id: str) -> dict:
    return {
        "id": item_id,
        "company": "甲公司",
        "report_period": "2024FY",
        "metric": "revenue",
        "unit": "CNY_hundred_million",
        "convention": {
            "scope": "consolidated",
            "basis": "gaap",
            "profit_view": None,
            "tax": "ex_tax",
        },
        "source_text": "【虚构示例】营业收入1.0亿元",
        "evidence_span": "营业收入1.0亿元",
        "reference": {
            "answerable": True,
            "value": 1.0,
            "unit": "CNY_hundred_million",
            "display": "1.0亿元",
            "refusal_reason": None,
        },
    }


def _correct_pred(item_id: str) -> dict:
    return {
        "id": item_id,
        "answer": "1.0亿元",
        "value": 1.0,
        "unit": "CNY_hundred_million",
        "evidence": "营业收入1.0亿元",
        "refused": False,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(text, encoding="utf-8")
