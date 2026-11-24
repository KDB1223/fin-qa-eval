"""Prediction-file coverage inventory. Grades nothing and writes nothing."""

from __future__ import annotations

import io
import json
from pathlib import Path

from fin_qa_eval.cli import main
from fin_qa_eval.graders import prediction_refused
from fin_qa_eval.list_predictions import collect_list_predictions, render_list_predictions_text
from fin_qa_eval.loader import load_jsonl

_ROW_KEYS = [
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
]

_SUMMARY_KEYS = [
    "n_gold",
    "n_pred",
    "n_gold_covered",
    "n_gold_missing",
    "n_missing_id",
    "n_unknown",
    "n_duplicate",
    "n_listed",
    "n_refused",
    "n_with_value",
    "n_with_evidence",
    "n_in_gold",
]

# Two gold rows share gold-a. The first one supplies company, period, and metric.
# gold-c is a usable id with no prediction. Empty and missing gold ids are not
# listed in missing_gold, but they still count toward n_gold.
_GOLD = [
    {
        "id": "gold-a",
        "company": "甲 公司",
        "report_period": "2024Q3",
        "metric": "net=profit",
    },
    {
        "id": "gold-b",
        "company": "乙公司",
        "report_period": "2024FY",
        "metric": "revenue",
    },
    {
        "id": "gold-a",
        "company": "后来的甲",
        "report_period": "1999Q1",
        "metric": "other",
    },
    {
        "id": "gold-c",
        "company": "丙公司",
        "report_period": "2025Q1",
        "metric": "ocf",
    },
    {
        "id": "gold-d",
        "company": "丁公司",
        "report_period": "2024H1",
        "metric": "ocf",
    },
    {"id": "", "company": "空id"},
    {"company": "无id"},
]

_PRED = [
    {
        "id": "gold-a",
        "answer": "128.6亿元",
        "value": 128.6,
        "unit": "CNY_hundred_million",
        "evidence": "合并",
        "refused": False,
    },
    {
        "answer": "no id here",
        "value": 1,
        "unit": "CNY",
        "evidence": "e",
    },
    {
        "id": "gold-a",
        "answer": "后来的",
        "value": 1,
        "unit": "CNY",
        "evidence": "另一处",
        "refused": False,
    },
    {
        "id": "unknown-1",
        "answer": "9亿元",
        "value": 9,
        "unit": "CNY",
        "evidence": "x",
        "refused": False,
    },
    {
        "id": "unknown-1",
        "answer": "again",
        "value": 9,
        "unit": "CNY",
        "evidence": "x",
    },
    {"id": "", "answer": "empty id", "value": 2, "evidence": "e"},
    {"id": None, "answer": "null id", "value": 0, "evidence": "  "},
    {"id": 7, "answer": "numeric id", "evidence": ""},
    {
        "id": "gold-b",
        "answer": "128.6亿元",
        "refused": True,
        "value": None,
        "unit": None,
        "evidence": "",
    },
    {"id": "phrase", "answer": "证据不足"},
    {
        "id": "phrase-false",
        "answer": "拒答",
        "refused": False,
        "value": 1,
        "unit": "percent",
        "evidence": "有证据",
    },
    {
        "id": "gold-d",
        "answer": "   ",
        "value": 0,
        "unit": "",
        "evidence": "  证据  ",
    },
]

_JOIN_A = {
    "company": "甲 公司",
    "report_period": "2024Q3",
    "metric": "net=profit",
}

_NO_GOLD = {"company": None, "report_period": None, "metric": None}


def _row(
    row_id: str | None,
    *,
    in_gold: bool = False,
    unknown: bool = False,
    duplicate: bool = False,
    refused: bool = False,
    has_value: bool = False,
    unit: str | None = None,
    has_evidence: bool = False,
    has_answer: bool = False,
    company: str | None = None,
    report_period: str | None = None,
    metric: str | None = None,
) -> dict:
    return {
        "id": row_id,
        "in_gold": in_gold,
        "unknown": unknown,
        "duplicate": duplicate,
        "refused": refused,
        "has_value": has_value,
        "unit": unit,
        "has_evidence": has_evidence,
        "has_answer": has_answer,
        "company": company,
        "report_period": report_period,
        "metric": metric,
    }


_EXPECTED = [
    _row(
        "gold-a",
        in_gold=True,
        has_value=True,
        unit="CNY_hundred_million",
        has_evidence=True,
        has_answer=True,
        **_JOIN_A,
    ),
    _row(
        None,
        has_value=True,
        unit="CNY",
        has_evidence=True,
        has_answer=True,
        **_NO_GOLD,
    ),
    _row(
        "gold-a",
        in_gold=True,
        duplicate=True,
        has_value=True,
        unit="CNY",
        has_evidence=True,
        has_answer=True,
        **_JOIN_A,
    ),
    _row(
        "unknown-1",
        unknown=True,
        has_value=True,
        unit="CNY",
        has_evidence=True,
        has_answer=True,
        **_NO_GOLD,
    ),
    _row(
        "unknown-1",
        unknown=True,
        duplicate=True,
        has_value=True,
        unit="CNY",
        has_evidence=True,
        has_answer=True,
        **_NO_GOLD,
    ),
    _row(None, has_value=True, has_evidence=True, has_answer=True, **_NO_GOLD),
    _row(None, has_value=True, has_answer=True, **_NO_GOLD),
    _row(None, has_answer=True, **_NO_GOLD),
    _row(
        "gold-b",
        in_gold=True,
        refused=True,
        has_answer=True,
        company="乙公司",
        report_period="2024FY",
        metric="revenue",
    ),
    _row("phrase", unknown=True, refused=True, has_answer=True, **_NO_GOLD),
    _row(
        "phrase-false",
        unknown=True,
        has_value=True,
        unit="percent",
        has_evidence=True,
        has_answer=True,
        **_NO_GOLD,
    ),
    _row(
        "gold-d",
        in_gold=True,
        has_value=True,
        unit="",
        has_evidence=True,
        has_answer=False,
        company="丁公司",
        report_period="2024H1",
        metric="ocf",
    ),
]

_UNFILTERED_SUMMARY = {
    "n_gold": 7,
    "n_pred": 12,
    "n_gold_covered": 3,
    "n_gold_missing": 4,
    "n_missing_id": 4,
    "n_unknown": 4,
    "n_duplicate": 2,
    "n_listed": 12,
    "n_refused": 2,
    "n_with_value": 9,
    "n_with_evidence": 8,
    "n_in_gold": 4,
}


def test_shipped_predictions_cover_the_gold_set(gold_path: Path, pred_path: Path) -> None:
    gold = load_jsonl(gold_path)
    predictions = load_jsonl(pred_path)
    report = collect_list_predictions(
        gold,
        predictions,
        data_name="data/samples/eval_set.jsonl",
        pred_name="examples/predictions.jsonl",
    )
    summary = report["summary"]
    assert summary["n_gold"] == 38
    assert summary["n_pred"] == 38
    assert summary["n_gold_covered"] == 38
    assert summary["n_gold_missing"] == 0
    assert summary["n_listed"] == 38
    assert summary["n_in_gold"] == 38
    assert summary["n_unknown"] == 0
    assert summary["n_missing_id"] == 0
    assert summary["n_duplicate"] == 0
    assert summary["n_refused"] == 5
    assert summary["n_with_value"] == 33
    assert summary["n_with_evidence"] == 37
    assert report["missing_gold"] == []
    assert report["filters"] == {"id": None, "company": None, "kind": None}
    assert [row["id"] for row in report["predictions"]] == [item["id"] for item in gold]
    assert [row["id"] for row in report["predictions"]] == [item["id"] for item in predictions]
    gold_by_id = {item["id"]: item for item in gold}
    for row, prediction in zip(report["predictions"], predictions):
        assert list(row) == _ROW_KEYS
        assert row["in_gold"] is True
        assert row["unknown"] is False
        assert row["duplicate"] is False
        assert row["refused"] is prediction_refused(prediction)
        gold_item = gold_by_id[row["id"]]
        assert row["company"] == gold_item["company"]
        assert row["report_period"] == gold_item["report_period"]
        assert row["metric"] == gold_item["metric"]

    text = render_list_predictions_text(report)
    assert text.startswith(
        "list-predictions gold=38 pred=38 listed=38 covered=38 missing_gold=0 "
        "unknown=0 missing_id=0 duplicate=0 refused=5 with_value=33 with_evidence=37\n"
    )
    assert "filters " not in text
    assert "no predictions" not in text
    assert "\nmissing_gold\n" not in text
    assert "None" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    lines = text.splitlines()
    assert len(lines) == 39
    assert lines[1] == (
        "xlkj-2024q3-revenue in_gold=true unknown=false duplicate=false "
        "refused=false has_value=true unit=CNY_hundred_million has_evidence=true "
        "has_answer=true company=星澜科技 period=2024Q3 metric=revenue"
    )
    refused_line = next(line for line in lines if line.startswith("xlkj-2024q3-deducted-np "))
    assert "refused=true" in refused_line
    assert "has_value=false" in refused_line
    assert "unit=(none)" in refused_line


def test_json_format_matches_collector(
    repo_root: Path, gold_path: Path, pred_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(repo_root)
    code, raw = _run(["list-predictions", "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    assert "星澜科技" in raw
    assert "\\u" not in raw
    payload = json.loads(raw)
    expected = collect_list_predictions(
        load_jsonl(gold_path),
        load_jsonl(pred_path),
        data_name="data/samples/eval_set.jsonl",
        pred_name="examples/predictions.jsonl",
    )
    assert payload == expected
    assert payload["data"] == "data/samples/eval_set.jsonl"
    assert payload["pred"] == "examples/predictions.jsonl"
    assert list(payload) == ["data", "pred", "summary", "filters", "missing_gold", "predictions"]
    assert list(payload["summary"]) == _SUMMARY_KEYS
    assert list(payload["filters"]) == ["id", "company", "kind"]
    assert list(payload["predictions"][0]) == _ROW_KEYS
    assert payload["summary"]["n_gold_missing"] == 0
    assert payload["summary"]["n_pred"] == 38
    assert payload["summary"]["n_gold_covered"] == 38


def test_fixture_rows_keep_file_order_flags_and_first_gold_item(tmp_path: Path) -> None:
    gold_file, pred_file = _write_pair(tmp_path)
    report = collect_list_predictions(
        _GOLD,
        _PRED,
        data_name="gold.jsonl",
        pred_name="pred.jsonl",
    )
    assert report["summary"] == _UNFILTERED_SUMMARY
    assert report["missing_gold"] == ["gold-c"]
    assert report["predictions"] == _EXPECTED
    for row in report["predictions"]:
        assert list(row) == _ROW_KEYS
    by_flags = report["predictions"]
    assert by_flags[0]["duplicate"] is False
    assert by_flags[2]["id"] == "gold-a"
    assert by_flags[2]["duplicate"] is True
    assert by_flags[2]["company"] == "甲 公司"
    assert by_flags[2]["company"] != "后来的甲"
    assert by_flags[1]["id"] is None
    assert by_flags[1]["duplicate"] is False
    assert by_flags[1]["unknown"] is False
    assert by_flags[1]["in_gold"] is False
    for prediction, row in zip(_PRED, report["predictions"]):
        assert row["refused"] is prediction_refused(prediction)
    assert prediction_refused(_PRED[9]) is True
    assert prediction_refused(_PRED[10]) is False

    code, raw = _run(
        ["list-predictions", "--data", str(gold_file), "--pred", str(pred_file), "--format", "json"]
    )
    assert code == 0
    payload = json.loads(raw)
    assert payload["summary"] == _UNFILTERED_SUMMARY
    assert payload["predictions"] == _EXPECTED
    assert payload["missing_gold"] == ["gold-c"]
    assert "后来的甲" not in raw
    assert "甲 公司" in raw
    assert "\\u" not in raw

    text = render_list_predictions_text(report)
    assert text == _unfiltered_text()
    assert "(none)" in text
    assert "true" in text
    assert "false" in text
    assert "None" not in text


def test_empty_pred_file_marks_every_shipped_gold_id_missing(
    gold_path: Path, tmp_path: Path
) -> None:
    pred_file = tmp_path / "empty.jsonl"
    pred_file.write_text("# no predictions yet\n\n", encoding="utf-8")
    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_path),
            "--pred",
            str(pred_file),
            "--format",
            "json",
        ]
    )
    assert code == 0
    payload = json.loads(raw)
    gold = load_jsonl(gold_path)
    assert payload["summary"]["n_gold"] == 38
    assert payload["summary"]["n_pred"] == 0
    assert payload["summary"]["n_gold_covered"] == 0
    assert payload["summary"]["n_gold_missing"] == 38
    assert payload["summary"]["n_listed"] == 0
    assert payload["summary"]["n_missing_id"] == 0
    assert payload["summary"]["n_unknown"] == 0
    assert payload["summary"]["n_duplicate"] == 0
    assert payload["summary"]["n_refused"] == 0
    assert payload["summary"]["n_with_value"] == 0
    assert payload["summary"]["n_with_evidence"] == 0
    assert payload["summary"]["n_in_gold"] == 0
    assert payload["predictions"] == []
    assert payload["missing_gold"] == [item["id"] for item in gold]

    code, text = _run(["list-predictions", "--data", str(gold_path), "--pred", str(pred_file)])
    assert code == 0
    assert text.startswith(
        "list-predictions gold=38 pred=0 listed=0 covered=0 missing_gold=38 "
        "unknown=0 missing_id=0 duplicate=0 refused=0 with_value=0 with_evidence=0\n"
    )
    assert "no predictions\n" in text
    assert "\nmissing_gold\n" in text
    listed, section = text.split("\nmissing_gold\n", 1)
    assert listed.endswith("no predictions")
    assert section.splitlines() == [item["id"] for item in gold]


def test_empty_gold_and_empty_pred_print_no_predictions(tmp_path: Path) -> None:
    gold_file = tmp_path / "gold.jsonl"
    pred_file = tmp_path / "pred.jsonl"
    gold_file.write_text("", encoding="utf-8")
    pred_file.write_text("", encoding="utf-8")
    code, text = _run(["list-predictions", "--data", str(gold_file), "--pred", str(pred_file)])
    assert code == 0
    assert text == (
        "list-predictions gold=0 pred=0 listed=0 covered=0 missing_gold=0 "
        "unknown=0 missing_id=0 duplicate=0 refused=0 with_value=0 with_evidence=0\n"
        "no predictions\n"
    )
    assert all(line != "missing_gold" for line in text.splitlines())

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
        ]
    )
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    payload = json.loads(raw)
    assert payload["summary"]["n_gold"] == 0
    assert payload["summary"]["n_pred"] == 0
    assert payload["missing_gold"] == []
    assert payload["predictions"] == []
    assert payload["filters"] == {"id": None, "company": None, "kind": None}


def test_blank_ids_are_not_duplicates_of_each_other(tmp_path: Path) -> None:
    gold = [
        {"id": " ", "company": "空格", "report_period": "2024", "metric": "m"},
        {"id": "dup", "metric": "first"},
        {"id": "dup", "company": "第二", "report_period": "1999", "metric": "second"},
    ]
    predictions = [
        {"id": " ", "answer": "1", "value": 1, "unit": "CNY", "evidence": "1"},
        {"id": " "},
        {"id": ""},
        {"id": None},
        {},
        {"id": 1, "answer": "one"},
        {"id": 1, "answer": "again"},
        {"id": "dup", "value": 1, "answer": "1", "evidence": "1", "unit": "CNY"},
        {"id": "flag-string", "refused": "true", "answer": "12亿元", "value": 12},
        {"id": "english", "answer": "Insufficient Evidence"},
    ]
    assert prediction_refused(predictions[-2]) is False
    assert prediction_refused(predictions[-1]) is True
    gold_file, pred_file = _write_pair(tmp_path, gold=gold, predictions=predictions)
    code, raw = _run(
        ["list-predictions", "--data", str(gold_file), "--pred", str(pred_file), "--format", "json"]
    )
    assert code == 0
    payload = json.loads(raw)
    rows = payload["predictions"]
    assert [row["id"] for row in rows] == [" ", " ", None, None, None, None, None, "dup", "flag-string", "english"]
    assert rows[0]["in_gold"] is True
    assert rows[0]["duplicate"] is False
    assert rows[0]["company"] == "空格"
    assert rows[1]["duplicate"] is True
    assert rows[1]["in_gold"] is True
    assert all(row["duplicate"] is False and row["unknown"] is False and row["in_gold"] is False for row in rows[2:7])
    assert rows[7]["company"] is None
    assert rows[7]["report_period"] is None
    assert rows[7]["metric"] == "first"
    assert rows[8]["refused"] is False
    assert rows[8]["unknown"] is True
    assert rows[8]["has_value"] is True
    assert rows[9]["refused"] is True
    assert rows[9]["unknown"] is True
    assert payload["summary"]["n_missing_id"] == 5
    assert payload["summary"]["n_duplicate"] == 1
    text = render_list_predictions_text(
        collect_list_predictions(gold, predictions, data_name="g", pred_name="p")
    )
    assert text.splitlines()[1].startswith('(none) ') is False
    assert text.splitlines()[1].startswith('" " ')


def test_filters_are_exact_and_keep_coverage_counts(tmp_path: Path) -> None:
    gold_file, pred_file = _write_pair(tmp_path)

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--id",
            "gold-a",
        ]
    )
    assert code == 0
    by_id = json.loads(raw)
    assert by_id["summary"]["n_listed"] == 2
    assert by_id["summary"]["n_pred"] == 12
    assert by_id["summary"]["n_duplicate"] == 2
    assert by_id["summary"]["n_unknown"] == 4
    assert by_id["summary"]["n_missing_id"] == 4
    assert by_id["summary"]["n_gold_missing"] == 4
    assert by_id["summary"]["n_in_gold"] == 2
    assert by_id["summary"]["n_refused"] == 0
    assert [row["duplicate"] for row in by_id["predictions"]] == [False, True]
    assert by_id["missing_gold"] == ["gold-c"]
    assert by_id["filters"] == {"id": "gold-a", "company": None, "kind": None}

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--company",
            "甲 公司",
        ]
    )
    assert code == 0
    by_company = json.loads(raw)
    assert [row["id"] for row in by_company["predictions"]] == ["gold-a", "gold-a"]
    assert by_company["summary"]["n_listed"] == 2
    assert by_company["summary"]["n_in_gold"] == 2
    assert by_company["summary"]["n_unknown"] == 4
    assert by_company["missing_gold"] == ["gold-c"]
    assert by_company["filters"]["company"] == "甲 公司"

    code, text = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--company",
            "甲 公司",
        ]
    )
    assert code == 0
    assert 'filters company="甲 公司"\n' in text
    assert 'metric="net=profit"' in text
    assert text.endswith("missing_gold\ngold-c\n")

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--company",
            "后来的甲",
        ]
    )
    assert code == 0
    missed = json.loads(raw)
    assert missed["predictions"] == []
    assert missed["summary"]["n_listed"] == 0
    assert missed["summary"]["n_refused"] == 0
    assert missed["summary"]["n_with_value"] == 0
    assert missed["summary"]["n_with_evidence"] == 0
    assert missed["summary"]["n_in_gold"] == 0
    assert missed["summary"]["n_gold_missing"] == 4
    assert missed["summary"]["n_unknown"] == 4
    assert missed["missing_gold"] == ["gold-c"]

    code, text = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--company",
            "后来的甲",
        ]
    )
    assert code == 0
    assert text == (
        "list-predictions gold=7 pred=12 listed=0 covered=3 missing_gold=4 "
        "unknown=4 missing_id=4 duplicate=2 refused=0 with_value=0 with_evidence=0\n"
        "filters company=后来的甲\n"
        "no predictions\n"
        "missing_gold\n"
        "gold-c\n"
    )

    code, text = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--company",
            "甲",
        ]
    )
    assert code == 0
    assert "no predictions\n" in text
    assert text.endswith("missing_gold\ngold-c\n")

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--kind",
            "duplicate",
        ]
    )
    assert code == 0
    duplicates = json.loads(raw)
    assert [row["id"] for row in duplicates["predictions"]] == ["gold-a", "unknown-1"]
    assert all(row["duplicate"] is True for row in duplicates["predictions"])
    assert duplicates["predictions"][0]["in_gold"] is True
    assert duplicates["predictions"][1]["unknown"] is True
    assert duplicates["summary"]["n_listed"] == 2
    assert duplicates["summary"]["n_duplicate"] == 2
    assert duplicates["summary"]["n_in_gold"] == 1

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--kind",
            "unknown",
        ]
    )
    assert code == 0
    unknown = json.loads(raw)
    assert [row["id"] for row in unknown["predictions"]] == [
        "unknown-1",
        "unknown-1",
        "phrase",
        "phrase-false",
    ]
    assert all(row["unknown"] is True for row in unknown["predictions"])
    assert unknown["summary"]["n_listed"] == 4
    assert unknown["summary"]["n_unknown"] == 4

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--kind",
            "missing_id",
        ]
    )
    assert code == 0
    missing = json.loads(raw)
    assert len(missing["predictions"]) == 4
    assert all(row["id"] is None for row in missing["predictions"])
    assert all(row["duplicate"] is False for row in missing["predictions"])
    assert missing["summary"]["n_listed"] == 4
    assert missing["summary"]["n_missing_id"] == 4
    assert missing["summary"]["n_in_gold"] == 0

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--kind",
            "in_gold",
        ]
    )
    assert code == 0
    in_gold = json.loads(raw)
    assert [row["id"] for row in in_gold["predictions"]] == ["gold-a", "gold-a", "gold-b", "gold-d"]
    assert in_gold["summary"]["n_listed"] == 4
    assert in_gold["summary"]["n_in_gold"] == 4
    assert in_gold["summary"]["n_refused"] == 1

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--kind",
            "refused",
        ]
    )
    assert code == 0
    refused = json.loads(raw)
    assert [row["id"] for row in refused["predictions"]] == ["gold-b", "phrase"]
    assert refused["predictions"][0]["refused"] is True
    assert refused["predictions"][0]["has_value"] is False
    assert refused["predictions"][0]["unit"] is None
    assert refused["predictions"][0]["has_evidence"] is False
    assert refused["predictions"][1]["refused"] is True
    assert refused["predictions"][1]["unknown"] is True
    assert refused["summary"]["n_listed"] == 2
    assert refused["summary"]["n_refused"] == 2
    assert refused["summary"]["n_with_value"] == 0
    assert refused["summary"]["n_with_evidence"] == 0
    assert refused["summary"]["n_in_gold"] == 1
    assert refused["summary"]["n_unknown"] == 4
    assert refused["missing_gold"] == ["gold-c"]

    code, text = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--kind",
            "refused",
        ]
    )
    assert code == 0
    assert text == (
        "list-predictions gold=7 pred=12 listed=2 covered=3 missing_gold=4 "
        "unknown=4 missing_id=4 duplicate=2 refused=2 with_value=0 with_evidence=0\n"
        "filters kind=refused\n"
        "gold-b in_gold=true unknown=false duplicate=false refused=true "
        "has_value=false unit=(none) has_evidence=false has_answer=true "
        "company=乙公司 period=2024FY metric=revenue\n"
        "phrase in_gold=false unknown=true duplicate=false refused=true "
        "has_value=false unit=(none) has_evidence=false has_answer=true "
        "company=(none) period=(none) metric=(none)\n"
        "missing_gold\n"
        "gold-c\n"
    )

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--id",
            "gold-a",
            "--kind",
            "duplicate",
        ]
    )
    assert code == 0
    both = json.loads(raw)
    assert len(both["predictions"]) == 1
    assert both["predictions"][0]["duplicate"] is True
    assert both["predictions"][0]["id"] == "gold-a"
    assert both["filters"] == {"id": "gold-a", "company": None, "kind": "duplicate"}
    assert both["missing_gold"] == ["gold-c"]

    code, text = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--id",
            "gold-a",
            "--company",
            "乙公司",
        ]
    )
    assert code == 0
    assert "filters id=gold-a company=乙公司\n" in text
    assert "no predictions\n" in text
    assert text.endswith("missing_gold\ngold-c\n")

    code, raw = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--format",
            "json",
            "--company",
            "乙公司",
            "--kind",
            "refused",
        ]
    )
    assert code == 0
    company_kind = json.loads(raw)
    assert [row["id"] for row in company_kind["predictions"]] == ["gold-b"]
    assert company_kind["summary"]["n_listed"] == 1
    assert company_kind["summary"]["n_refused"] == 1
    assert company_kind["summary"]["n_gold_covered"] == 3

    code, text = _run(
        [
            "list-predictions",
            "--data",
            str(gold_file),
            "--pred",
            str(pred_file),
            "--id",
            "",
        ]
    )
    assert code == 0
    assert "no predictions\n" in text


def test_load_errors_exit_2(tmp_path: Path, capsys) -> None:
    pred_file = tmp_path / "pred.jsonl"
    pred_file.write_text("{}\n", encoding="utf-8")
    code = main(
        ["list-predictions", "--data", str(tmp_path / "missing.jsonl"), "--pred", str(pred_file)]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")

    gold_file = tmp_path / "gold.jsonl"
    gold_file.write_text("{}\n", encoding="utf-8")
    code = main(
        ["list-predictions", "--data", str(gold_file), "--pred", str(tmp_path / "no-pred.jsonl")]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    assert main(["list-predictions", "--data", str(gold_file), "--pred", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")


def test_schema_is_not_loaded_and_command_does_not_grade_or_write(
    tmp_path: Path, gold_path: Path, pred_path: Path, monkeypatch
) -> None:
    loaded: list[Path] = []
    real_load = load_jsonl

    def spy(path: Path) -> list[dict]:
        loaded.append(Path(path))
        return real_load(path)

    def fail_grade(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("list-predictions must not grade")

    def fail_schema(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("list-predictions must not load a schema")

    monkeypatch.setattr("fin_qa_eval.cli.load_jsonl", spy)
    monkeypatch.setattr("fin_qa_eval.cli.grade", fail_grade)
    monkeypatch.setattr("fin_qa_eval.graders.grade", fail_grade)
    monkeypatch.setattr("fin_qa_eval.cli.load_schema", fail_schema)
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    code = main(
        [
            "list-predictions",
            "--data",
            str(gold_path),
            "--pred",
            str(pred_path),
            "--schema",
            str(tmp_path / "no-such-schema.json"),
        ],
        stdout=buf,
    )
    assert code == 0
    text = buf.getvalue()
    assert text.startswith(
        "list-predictions gold=38 pred=38 listed=38 covered=38 missing_gold=0 "
        "unknown=0 missing_id=0 duplicate=0 refused=5 with_value=33 with_evidence=37\n"
    )
    assert loaded == [gold_path, pred_path]
    assert list(tmp_path.iterdir()) == []


def _unfiltered_text() -> str:
    rows = [
        (
            'gold-a in_gold=true unknown=false duplicate=false refused=false '
            'has_value=true unit=CNY_hundred_million has_evidence=true has_answer=true '
            'company="甲 公司" period=2024Q3 metric="net=profit"'
        ),
        (
            "(none) in_gold=false unknown=false duplicate=false refused=false "
            "has_value=true unit=CNY has_evidence=true has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            'gold-a in_gold=true unknown=false duplicate=true refused=false '
            'has_value=true unit=CNY has_evidence=true has_answer=true '
            'company="甲 公司" period=2024Q3 metric="net=profit"'
        ),
        (
            "unknown-1 in_gold=false unknown=true duplicate=false refused=false "
            "has_value=true unit=CNY has_evidence=true has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            "unknown-1 in_gold=false unknown=true duplicate=true refused=false "
            "has_value=true unit=CNY has_evidence=true has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            "(none) in_gold=false unknown=false duplicate=false refused=false "
            "has_value=true unit=(none) has_evidence=true has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            "(none) in_gold=false unknown=false duplicate=false refused=false "
            "has_value=true unit=(none) has_evidence=false has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            "(none) in_gold=false unknown=false duplicate=false refused=false "
            "has_value=false unit=(none) has_evidence=false has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            "gold-b in_gold=true unknown=false duplicate=false refused=true "
            "has_value=false unit=(none) has_evidence=false has_answer=true "
            "company=乙公司 period=2024FY metric=revenue"
        ),
        (
            "phrase in_gold=false unknown=true duplicate=false refused=true "
            "has_value=false unit=(none) has_evidence=false has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            "phrase-false in_gold=false unknown=true duplicate=false refused=false "
            "has_value=true unit=percent has_evidence=true has_answer=true "
            "company=(none) period=(none) metric=(none)"
        ),
        (
            'gold-d in_gold=true unknown=false duplicate=false refused=false '
            'has_value=true unit="" has_evidence=true has_answer=false '
            "company=丁公司 period=2024H1 metric=ocf"
        ),
    ]
    header = (
        "list-predictions gold=7 pred=12 listed=12 covered=3 missing_gold=4 "
        "unknown=4 missing_id=4 duplicate=2 refused=2 with_value=9 with_evidence=8\n"
    )
    return header + "\n".join(rows) + "\nmissing_gold\ngold-c\n"


def _write_pair(
    tmp_path: Path,
    *,
    gold: list[dict] | None = None,
    predictions: list[dict] | None = None,
) -> tuple[Path, Path]:
    gold_file = tmp_path / "gold.jsonl"
    pred_file = tmp_path / "pred.jsonl"
    _write_jsonl(gold_file, _GOLD if gold is None else gold)
    _write_jsonl(pred_file, _PRED if predictions is None else predictions)
    return gold_file, pred_file


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(argv, stdout=buf)
    return code, buf.getvalue()
