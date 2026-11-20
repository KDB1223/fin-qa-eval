"""Gold-item inventory. Counts and ids come from the shipped eval set."""

from __future__ import annotations

import io
import json
from pathlib import Path

from fin_qa_eval.cli import main
from fin_qa_eval.list_items import collect_list_items, render_list_items_text
from fin_qa_eval.loader import load_jsonl

_ITEM_KEYS = [
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
]

_BANNED = {
    "question",
    "source_text",
    "evidence_span",
    "distractors",
    "value",
    "display",
    "notes",
    "tags",
    "source_id",
}


def test_shipped_eval_set_lists_items_in_file_order(gold_path: Path) -> None:
    gold = load_jsonl(gold_path)
    report = collect_list_items(gold, data_name="data/samples/eval_set.jsonl")
    assert report["summary"] == {
        "n": 38,
        "n_listed": 38,
        "n_answerable": 32,
        "n_unanswerable": 6,
    }
    assert report["filters"] == {
        "company": None,
        "metric": None,
        "period": None,
        "id": None,
        "refusal": None,
    }
    assert [row["id"] for row in report["items"]] == [item["id"] for item in gold]
    assert report["items"][0]["id"] == "xlkj-2024q3-revenue"
    for row in report["items"]:
        assert list(row) == _ITEM_KEYS
        assert _BANNED.isdisjoint(row)

    xlkj = report["items"][0]
    assert xlkj == {
        "id": "xlkj-2024q3-revenue",
        "company": "星澜科技",
        "report_period": "2024Q3",
        "metric": "revenue",
        "scope": "consolidated",
        "basis": "gaap",
        "profit_view": None,
        "tax": "ex_tax",
        "unit": "CNY_hundred_million",
        "language": "zh",
        "answerable": True,
        "refusal_reason": None,
    }
    ambiguous = _by_id(report, "lqwl-2025q1-unit-ambiguous")
    assert ambiguous["answerable"] is False
    assert ambiguous["refusal_reason"] == "unit_ambiguous"
    assert ambiguous["company"] == "岚桥物流"
    assert ambiguous["metric"] == "net_profit"
    assert ambiguous["profit_view"] == "net"
    deducted = _by_id(report, "xlkj-2024q3-deducted-np")
    assert deducted["answerable"] is False
    assert deducted["refusal_reason"] == "insufficient_evidence"

    text = render_list_items_text(report)
    assert text.startswith("list-items items=38 listed=38 answerable=32 unanswerable=6\n")
    assert "filters " not in text
    assert "None" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    lines = text.splitlines()
    assert len(lines) == 39
    assert lines[1] == (
        "xlkj-2024q3-revenue company=星澜科技 period=2024Q3 metric=revenue "
        "scope=consolidated basis=gaap profit_view=(none) tax=ex_tax "
        "unit=CNY_hundred_million language=zh answerable=true refusal_reason=(none)"
    )
    ambiguous_line = next(line for line in lines if line.startswith("lqwl-2025q1-unit-ambiguous "))
    assert "answerable=false" in ambiguous_line
    assert "refusal_reason=unit_ambiguous" in ambiguous_line
    assert "profit_view=net" in ambiguous_line


def test_json_format_matches_collector(repo_root: Path, gold_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    code, raw = _run(["list-items", "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    assert "None" not in raw
    assert "星澜科技" in raw
    assert '"profit_view": null' in raw
    assert '"answerable": false' in raw
    payload = json.loads(raw)
    expected = collect_list_items(
        load_jsonl(gold_path),
        data_name="data/samples/eval_set.jsonl",
    )
    assert payload == expected
    assert payload["data"] == "data/samples/eval_set.jsonl"
    assert list(payload) == ["data", "summary", "filters", "items"]
    assert list(payload["summary"]) == ["n", "n_listed", "n_answerable", "n_unanswerable"]
    assert list(payload["filters"]) == ["company", "metric", "period", "id", "refusal"]
    assert list(payload["items"][0]) == _ITEM_KEYS


def test_filters_are_exact_and_anded(gold_path: Path) -> None:
    gold = load_jsonl(gold_path)

    code, raw = _run(
        ["list-items", "--data", str(gold_path), "--format", "json", "--company", "星澜科技"]
    )
    assert code == 0
    company = json.loads(raw)
    assert company["summary"]["n"] == 38
    assert company["summary"]["n_listed"] == 6
    assert company["summary"]["n_answerable"] == 5
    assert company["summary"]["n_unanswerable"] == 1
    assert [row["id"] for row in company["items"]] == [
        item["id"] for item in gold if item["company"] == "星澜科技"
    ]
    assert company["filters"] == {
        "company": "星澜科技",
        "metric": None,
        "period": None,
        "id": None,
        "refusal": None,
    }
    assert all(row["company"] == "星澜科技" for row in company["items"])

    code, raw = _run(
        ["list-items", "--data", str(gold_path), "--format", "json", "--metric", "revenue"]
    )
    assert code == 0
    metric = json.loads(raw)
    assert [row["id"] for row in metric["items"]] == [
        item["id"] for item in gold if item["metric"] == "revenue"
    ]
    assert metric["summary"]["n_listed"] == 11
    assert metric["filters"]["metric"] == "revenue"

    code, raw = _run(
        ["list-items", "--data", str(gold_path), "--format", "json", "--period", "2024Q3"]
    )
    assert code == 0
    period = json.loads(raw)
    assert [row["id"] for row in period["items"]] == [
        item["id"] for item in gold if item["report_period"] == "2024Q3"
    ]
    assert period["summary"]["n_listed"] == 9
    assert period["filters"]["period"] == "2024Q3"

    code, raw = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--id",
            "xlkj-2024q3-revenue",
        ]
    )
    assert code == 0
    one = json.loads(raw)
    assert [row["id"] for row in one["items"]] == ["xlkj-2024q3-revenue"]
    assert one["summary"]["n"] == 38
    assert one["summary"]["n_listed"] == 1
    assert one["summary"]["n_answerable"] == 1
    assert one["summary"]["n_unanswerable"] == 0
    assert one["filters"]["id"] == "xlkj-2024q3-revenue"

    code, raw = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--refusal",
            "unit_ambiguous",
        ]
    )
    assert code == 0
    refused = json.loads(raw)
    assert [row["id"] for row in refused["items"]] == ["lqwl-2025q1-unit-ambiguous"]
    assert refused["items"][0]["answerable"] is False
    assert refused["items"][0]["refusal_reason"] == "unit_ambiguous"
    assert refused["summary"]["n_listed"] == 1
    assert refused["summary"]["n_answerable"] == 0
    assert refused["summary"]["n_unanswerable"] == 1

    code, raw = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--company",
            "星澜科技",
            "--metric",
            "revenue",
            "--period",
            "2024Q3",
        ]
    )
    assert code == 0
    combined = json.loads(raw)
    assert [row["id"] for row in combined["items"]] == ["xlkj-2024q3-revenue"]
    assert combined["summary"]["n_listed"] == 1
    assert combined["filters"]["company"] == "星澜科技"
    assert combined["filters"]["metric"] == "revenue"
    assert combined["filters"]["period"] == "2024Q3"

    code, text = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--refusal",
            "insufficient_evidence",
            "--company",
            "星澜科技",
        ]
    )
    assert code == 0
    assert text.startswith("list-items items=38 listed=1 answerable=0 unanswerable=1\n")
    assert "filters company=星澜科技 refusal=insufficient_evidence\n" in text
    assert "xlkj-2024q3-deducted-np " in text
    assert "lqwl-2025q1-ocf" not in text

    code, text = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--refusal",
            "unit_ambiguous",
            "--company",
            "星澜科技",
        ]
    )
    assert code == 0
    assert text == (
        "list-items items=38 listed=0 answerable=0 unanswerable=0\n"
        "filters company=星澜科技 refusal=unit_ambiguous\n"
        "no items\n"
    )

    code, text = _run(["list-items", "--data", str(gold_path), "--company", "星澜"])
    assert code == 0
    assert "listed=0" in text
    assert "filters company=星澜\n" in text
    assert "no items" in text
    assert "xlkj-2024q3-revenue" not in text

    code, raw = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--company",
            "不存在公司",
            "--metric",
            "not-a-metric",
            "--period",
            "1999Q1",
            "--id",
            "missing-id",
            "--refusal",
            "not-a-reason",
        ]
    )
    assert code == 0
    empty = json.loads(raw)
    assert empty["summary"]["n"] == 38
    assert empty["summary"]["n_listed"] == 0
    assert empty["summary"]["n_answerable"] == 0
    assert empty["summary"]["n_unanswerable"] == 0
    assert empty["items"] == []
    assert "None" not in raw

    code, text = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--company",
            "no such co",
            "--metric",
            "a=b",
        ]
    )
    assert code == 0
    assert text.startswith("list-items items=38 listed=0 answerable=0 unanswerable=0\n")
    assert 'filters company="no such co" metric="a=b"\n' in text
    assert text.endswith("no items\n")
    assert not text.endswith("\n\n")


def test_schema_flag_is_accepted_and_unused(tmp_path: Path, gold_path: Path) -> None:
    code, text = _run(
        [
            "list-items",
            "--data",
            str(gold_path),
            "--schema",
            str(tmp_path / "no-such-schema.json"),
        ]
    )
    assert code == 0
    assert text.startswith("list-items items=38 listed=38 answerable=32 unanswerable=6\n")


def test_missing_data_file_exits_2(tmp_path: Path, capsys) -> None:
    code = main(["list-items", "--data", str(tmp_path / "missing.jsonl")])
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    assert main(["list-items", "--data", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")


def test_empty_file_prints_no_items(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    code, text = _run(["list-items", "--data", str(path)])
    assert code == 0
    assert text == "list-items items=0 listed=0 answerable=0 unanswerable=0\nno items\n"

    code, raw = _run(["list-items", "--data", str(path), "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    payload = json.loads(raw)
    assert payload["summary"] == {
        "n": 0,
        "n_listed": 0,
        "n_answerable": 0,
        "n_unanswerable": 0,
    }
    assert payload["items"] == []


def test_missing_convention_null_fields_and_refusal(tmp_path: Path) -> None:
    path = tmp_path / "tiny.jsonl"
    rows = [
        {
            "id": "bare-1",
            "company": "甲 公司",
            "report_period": "2024FY",
            "metric": "revenue",
            "unit": "CNY_hundred_million",
            "reference": {"answerable": True},
        },
        {
            "id": "null-conv",
            "company": "乙公司",
            "report_period": "2024Q3",
            "metric": "net_profit",
            "unit": None,
            "language": None,
            "convention": {
                "scope": None,
                "basis": None,
                "profit_view": None,
                "tax": None,
            },
            "reference": {"answerable": True, "refusal_reason": None},
        },
        {
            "id": "refuse-1",
            "company": "丙公司",
            "report_period": "2025Q1",
            "metric": "net_profit",
            "unit": "CNY_hundred_million",
            "language": "en",
            "convention": {
                "scope": "consolidated",
                "basis": "gaap",
                "profit_view": None,
                "tax": None,
            },
            "reference": {"answerable": False, "refusal_reason": "unit_ambiguous"},
        },
        {
            "id": "strict-1",
            "company": "丁公司",
            "reference": {"answerable": "true", "refusal_reason": "insufficient_evidence"},
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    code, text = _run(["list-items", "--data", str(path)])
    assert code == 0
    assert text == (
        "list-items items=4 listed=4 answerable=2 unanswerable=2\n"
        "bare-1 company=\"甲 公司\" period=2024FY metric=revenue "
        "scope=(none) basis=(none) profit_view=(none) tax=(none) "
        "unit=CNY_hundred_million language=(none) answerable=true refusal_reason=(none)\n"
        "null-conv company=乙公司 period=2024Q3 metric=net_profit "
        "scope=(none) basis=(none) profit_view=(none) tax=(none) "
        "unit=(none) language=(none) answerable=true refusal_reason=(none)\n"
        "refuse-1 company=丙公司 period=2025Q1 metric=net_profit "
        "scope=consolidated basis=gaap profit_view=(none) tax=(none) "
        "unit=CNY_hundred_million language=en answerable=false refusal_reason=unit_ambiguous\n"
        "strict-1 company=丁公司 period=(none) metric=(none) "
        "scope=(none) basis=(none) profit_view=(none) tax=(none) "
        "unit=(none) language=(none) answerable=false refusal_reason=insufficient_evidence\n"
    )
    assert "None" not in text

    code, raw = _run(["list-items", "--data", str(path), "--format", "json"])
    assert code == 0
    assert "None" not in raw
    assert '"scope": null' in raw
    assert '"language": null' in raw
    assert '"language": "en"' in raw
    payload = json.loads(raw)
    assert payload["data"].endswith("tiny.jsonl")
    by_id = {row["id"]: row for row in payload["items"]}
    assert by_id["bare-1"]["scope"] is None
    assert by_id["bare-1"]["language"] is None
    assert by_id["bare-1"]["answerable"] is True
    assert by_id["bare-1"]["refusal_reason"] is None
    assert by_id["null-conv"]["basis"] is None
    assert by_id["null-conv"]["profit_view"] is None
    assert by_id["null-conv"]["tax"] is None
    assert by_id["null-conv"]["unit"] is None
    assert by_id["null-conv"]["language"] is None
    assert by_id["refuse-1"]["answerable"] is False
    assert by_id["refuse-1"]["refusal_reason"] == "unit_ambiguous"
    assert by_id["refuse-1"]["language"] == "en"
    assert by_id["strict-1"]["answerable"] is False
    assert payload["summary"]["n_answerable"] == 2
    assert payload["summary"]["n_unanswerable"] == 2


def test_list_items_writes_nothing_and_needs_no_pred(
    tmp_path: Path, gold_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    assert main(["list-items", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert text.startswith("list-items items=38 listed=38 answerable=32 unanswerable=6\n")
    assert list(tmp_path.iterdir()) == []


def _by_id(report: dict, item_id: str) -> dict:
    for row in report["items"]:
        if row["id"] == item_id:
            return row
    raise AssertionError(f"missing item {item_id}")


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(argv, stdout=buf)
    return code, buf.getvalue()
