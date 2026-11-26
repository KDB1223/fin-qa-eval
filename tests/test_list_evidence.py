"""Evidence-binding inventory. Counts and spans come from the shipped eval set."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from fin_qa_eval.cli import main
from fin_qa_eval.list_evidence import collect_list_evidence, render_list_evidence_text
from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.qc import evidence_contained, norm_text

_ROW_KEYS = [
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
]

_SUMMARY_KEYS = [
    "n",
    "n_listed",
    "n_with_evidence",
    "n_without_evidence",
    "n_contained",
    "n_not_contained",
    "n_sources",
]

_FILTER_KEYS = ["company", "metric", "period", "id", "source", "kind"]

_OPEN_FILTERS = {
    "company": None,
    "metric": None,
    "period": None,
    "id": None,
    "source": None,
    "kind": None,
}

_SHIPPED_BY_SOURCE = [
    {"key": "src-bcyy-2024fy", "n": 8},
    {"key": "src-qhne-2024fy", "n": 6},
    {"key": "src-xlkj-2024q3", "n": 6},
    {"key": "src-blsp-2024fy", "n": 5},
    {"key": "src-chry-2024h1", "n": 4},
    {"key": "src-lqwl-2025q1", "n": 4},
    {"key": "src-ccsc-2024q3", "n": 3},
    {"key": "src-wtjj-2023fy", "n": 2},
]

_SHIPPED_HEADER = (
    "list-evidence items=38 listed=38 with_evidence=38 without_evidence=0 "
    "contained=38 not_contained=0 sources=8"
)


def test_shipped_eval_set_lists_evidence_in_file_order(gold_path: Path) -> None:
    gold = load_jsonl(gold_path)
    report = collect_list_evidence(gold, data_name="data/samples/eval_set.jsonl")
    assert report["summary"] == {
        "n": 38,
        "n_listed": 38,
        "n_with_evidence": 38,
        "n_without_evidence": 0,
        "n_contained": 38,
        "n_not_contained": 0,
        "n_sources": 8,
    }
    assert report["filters"] == _OPEN_FILTERS
    assert report["by_source"] == _SHIPPED_BY_SOURCE
    assert [row["id"] for row in report["items"]] == [item["id"] for item in gold]
    for item, row in zip(gold, report["items"]):
        assert list(row) == _ROW_KEYS
        span = item["evidence_span"] if isinstance(item.get("evidence_span"), str) else ""
        source = item["source_text"] if isinstance(item.get("source_text"), str) else ""
        assert row["contained"] is evidence_contained(span, source)
        assert row["source_id"] == item["source_id"]
        assert row["source_chars"] == len(item["source_text"])
        assert row["has_evidence"] is True
        assert row["evidence_span"] == item["evidence_span"]
        assert row["evidence_chars"] == len(item["evidence_span"])
        assert "source_text" not in row
        assert "question" not in row

    first = gold[0]
    assert report["items"][0] == {
        "id": "xlkj-2024q3-revenue",
        "company": "星澜科技",
        "report_period": "2024Q3",
        "metric": "revenue",
        "source_id": "src-xlkj-2024q3",
        "source_chars": len(first["source_text"]),
        "has_evidence": True,
        "evidence_span": "公司合并口径实现营业收入128.6亿元",
        "evidence_chars": len("公司合并口径实现营业收入128.6亿元"),
        "contained": True,
        "answerable": True,
    }
    unanswerable = [row for row in report["items"] if not row["answerable"]]
    assert len(unanswerable) == 6
    assert all(row["has_evidence"] and row["contained"] and row["evidence_span"] for row in unanswerable)

    text = render_list_evidence_text(report)
    lines = text.splitlines()
    assert lines[0] == _SHIPPED_HEADER
    assert "filters " not in text
    assert "None" not in text
    assert "【虚构示例" not in text
    assert "source_text=" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert lines[1] == "by_source:"
    assert lines[2:10] == [
        "  src-bcyy-2024fy n=8",
        "  src-qhne-2024fy n=6",
        "  src-xlkj-2024q3 n=6",
        "  src-blsp-2024fy n=5",
        "  src-chry-2024h1 n=4",
        "  src-lqwl-2025q1 n=4",
        "  src-ccsc-2024q3 n=3",
        "  src-wtjj-2023fy n=2",
    ]
    assert len(lines) == 48
    assert lines[10] == (
        "xlkj-2024q3-revenue company=星澜科技 period=2024Q3 metric=revenue "
        "source_id=src-xlkj-2024q3 source_chars=168 has_evidence=true "
        "evidence_span=公司合并口径实现营业收入128.6亿元 evidence_chars=19 "
        "contained=true answerable=true"
    )


def test_json_format_matches_collector(repo_root: Path, gold_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    code, raw = _run(["list-evidence", "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    assert "None" not in raw
    assert "【虚构示例" not in raw
    assert "公司合并口径实现营业收入128.6亿元" in raw
    payload = json.loads(raw)
    expected = collect_list_evidence(
        load_jsonl(gold_path),
        data_name="data/samples/eval_set.jsonl",
    )
    assert payload == expected
    assert payload["data"] == "data/samples/eval_set.jsonl"
    assert list(payload) == ["data", "summary", "filters", "by_source", "items"]
    assert list(payload["summary"]) == _SUMMARY_KEYS
    assert list(payload["filters"]) == _FILTER_KEYS
    assert list(payload["by_source"][0]) == ["key", "n"]
    assert payload["by_source"][0] == {"key": "src-bcyy-2024fy", "n": 8}
    assert list(payload["items"][0]) == _ROW_KEYS
    assert "source_text" not in payload["items"][0]


def test_filters_are_exact_and_anded(gold_path: Path) -> None:
    gold = load_jsonl(gold_path)

    code, raw = _run(
        ["list-evidence", "--data", str(gold_path), "--format", "json", "--company", "星澜科技"]
    )
    assert code == 0
    company = json.loads(raw)
    assert company["summary"]["n"] == 38
    assert company["summary"]["n_listed"] == 6
    assert company["summary"]["n_with_evidence"] == 6
    assert company["summary"]["n_contained"] == 6
    assert company["summary"]["n_sources"] == 1
    assert [row["id"] for row in company["items"]] == [
        item["id"] for item in gold if item["company"] == "星澜科技"
    ]
    assert company["by_source"] == [{"key": "src-xlkj-2024q3", "n": 6}]
    assert company["filters"]["company"] == "星澜科技"
    assert company["filters"]["source"] is None

    code, raw = _run(
        ["list-evidence", "--data", str(gold_path), "--format", "json", "--metric", "revenue"]
    )
    assert code == 0
    metric = json.loads(raw)
    assert [row["id"] for row in metric["items"]] == [
        item["id"] for item in gold if item["metric"] == "revenue"
    ]
    assert metric["summary"]["n_listed"] == 11
    assert metric["filters"]["metric"] == "revenue"

    code, raw = _run(
        ["list-evidence", "--data", str(gold_path), "--format", "json", "--period", "2024Q3"]
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
            "list-evidence",
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
    assert one["summary"]["n_sources"] == 1
    assert one["filters"]["id"] == "xlkj-2024q3-revenue"

    code, raw = _run(
        [
            "list-evidence",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--source",
            "src-bcyy-2024fy",
        ]
    )
    assert code == 0
    source = json.loads(raw)
    assert source["summary"]["n_listed"] == 8
    assert source["summary"]["n_sources"] == 1
    assert source["by_source"] == [{"key": "src-bcyy-2024fy", "n": 8}]
    assert all(row["source_id"] == "src-bcyy-2024fy" for row in source["items"])
    assert source["filters"]["source"] == "src-bcyy-2024fy"

    code, raw = _run(
        ["list-evidence", "--data", str(gold_path), "--format", "json", "--kind", "with_evidence"]
    )
    assert code == 0
    with_evidence = json.loads(raw)
    assert with_evidence["summary"]["n_listed"] == 38
    assert with_evidence["filters"]["kind"] == "with_evidence"

    code, raw = _run(
        ["list-evidence", "--data", str(gold_path), "--format", "json", "--kind", "contained"]
    )
    assert code == 0
    contained = json.loads(raw)
    assert contained["summary"]["n_listed"] == 38
    assert contained["summary"]["n_contained"] == 38
    assert contained["filters"]["kind"] == "contained"

    code, raw = _run(
        [
            "list-evidence",
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
            "--id",
            "xlkj-2024q3-revenue",
            "--source",
            "src-xlkj-2024q3",
            "--kind",
            "contained",
        ]
    )
    assert code == 0
    combined = json.loads(raw)
    assert [row["id"] for row in combined["items"]] == ["xlkj-2024q3-revenue"]
    assert combined["summary"]["n_listed"] == 1
    assert combined["filters"] == {
        "company": "星澜科技",
        "metric": "revenue",
        "period": "2024Q3",
        "id": "xlkj-2024q3-revenue",
        "source": "src-xlkj-2024q3",
        "kind": "contained",
    }

    code, text = _run(
        [
            "list-evidence",
            "--data",
            str(gold_path),
            "--company",
            "星澜科技",
            "--source",
            "src-xlkj-2024q3",
        ]
    )
    assert code == 0
    assert text.startswith(
        "list-evidence items=38 listed=6 with_evidence=6 without_evidence=0 "
        "contained=6 not_contained=0 sources=1\n"
    )
    assert "filters company=星澜科技 source=src-xlkj-2024q3\n" in text
    assert "by_source:\n  src-xlkj-2024q3 n=6\n" in text
    assert "xlkj-2024q3-revenue " in text
    assert "bcyy-2024fy-revenue " not in text

    code, text = _run(
        [
            "list-evidence",
            "--data",
            str(gold_path),
            "--company",
            "星澜科技",
            "--source",
            "src-bcyy-2024fy",
        ]
    )
    assert code == 0
    assert text == (
        "list-evidence items=38 listed=0 with_evidence=0 without_evidence=0 "
        "contained=0 not_contained=0 sources=0\n"
        "filters company=星澜科技 source=src-bcyy-2024fy\n"
        "no items\n"
    )

    code, text = _run(["list-evidence", "--data", str(gold_path), "--kind", "missing_evidence"])
    assert code == 0
    assert text == (
        "list-evidence items=38 listed=0 with_evidence=0 without_evidence=0 "
        "contained=0 not_contained=0 sources=0\n"
        "filters kind=missing_evidence\n"
        "no items\n"
    )

    code, text = _run(["list-evidence", "--data", str(gold_path), "--kind", "not_contained"])
    assert code == 0
    assert "listed=0" in text
    assert "filters kind=not_contained\n" in text
    assert text.endswith("no items\n")
    assert "by_source:" not in text

    code, text = _run(["list-evidence", "--data", str(gold_path), "--company", "星澜"])
    assert code == 0
    assert "listed=0" in text
    assert "filters company=星澜\n" in text
    assert "no items" in text
    assert "xlkj-2024q3-revenue" not in text

    code, text = _run(["list-evidence", "--data", str(gold_path), "--source", "src-xlkj"])
    assert code == 0
    assert "listed=0" in text
    assert "filters source=src-xlkj\n" in text
    assert "src-xlkj-2024q3" not in text

    code, raw = _run(
        [
            "list-evidence",
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
            "--source",
            "src-missing",
            "--kind",
            "contained",
        ]
    )
    assert code == 0
    empty = json.loads(raw)
    assert empty["summary"]["n"] == 38
    assert empty["summary"]["n_listed"] == 0
    assert empty["summary"]["n_with_evidence"] == 0
    assert empty["summary"]["n_without_evidence"] == 0
    assert empty["summary"]["n_contained"] == 0
    assert empty["summary"]["n_not_contained"] == 0
    assert empty["summary"]["n_sources"] == 0
    assert empty["by_source"] == []
    assert empty["items"] == []
    assert "None" not in raw

    code, text = _run(
        [
            "list-evidence",
            "--data",
            str(gold_path),
            "--company",
            "no such co",
            "--metric",
            "a=b",
        ]
    )
    assert code == 0
    assert text.startswith(
        "list-evidence items=38 listed=0 with_evidence=0 without_evidence=0 "
        "contained=0 not_contained=0 sources=0\n"
    )
    assert 'filters company="no such co" metric="a=b"\n' in text
    assert text.endswith("no items\n")
    assert not text.endswith("\n\n")


def test_schema_flag_is_accepted_and_unused(tmp_path: Path, gold_path: Path) -> None:
    code, text = _run(
        [
            "list-evidence",
            "--data",
            str(gold_path),
            "--schema",
            str(tmp_path / "no-such-schema.json"),
        ]
    )
    assert code == 0
    assert text.startswith(_SHIPPED_HEADER + "\n")


def test_missing_data_file_exits_2(tmp_path: Path, capsys) -> None:
    code = main(["list-evidence", "--data", str(tmp_path / "missing.jsonl")])
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    assert main(["list-evidence", "--data", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")


def test_empty_file_prints_no_items(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    code, text = _run(["list-evidence", "--data", str(path)])
    assert code == 0
    assert text == (
        "list-evidence items=0 listed=0 with_evidence=0 without_evidence=0 "
        "contained=0 not_contained=0 sources=0\n"
        "no items\n"
    )

    code, raw = _run(["list-evidence", "--data", str(path), "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    payload = json.loads(raw)
    assert payload["summary"] == {
        "n": 0,
        "n_listed": 0,
        "n_with_evidence": 0,
        "n_without_evidence": 0,
        "n_contained": 0,
        "n_not_contained": 0,
        "n_sources": 0,
    }
    assert payload["by_source"] == []
    assert payload["items"] == []
    assert payload["filters"] == _OPEN_FILTERS


def test_fields_containment_and_shared_sources(tmp_path: Path) -> None:
    path = tmp_path / "tiny.jsonl"
    rows = [
        {
            "id": "literal",
            "company": "甲公司",
            "report_period": "2024FY",
            "metric": "revenue",
            "source_id": "src-a",
            "source_text": "营业收入128.6亿元。",
            "evidence_span": "营业收入128.6亿元",
            "reference": {"answerable": True},
        },
        {
            "id": "spaces",
            "company": "甲 公司",
            "report_period": "2024FY",
            "metric": "revenue",
            "source_id": "src-a",
            "source_text": "营业收入128.6亿元。",
            "evidence_span": "营业收入 128.6 亿元",
            "reference": {"answerable": True},
        },
        {
            "id": "fullwidth",
            "company": "乙公司",
            "report_period": "2024H1",
            "metric": "net_profit",
            "source_id": "src-b",
            "source_text": "净利率12.5%。",
            "evidence_span": "净利率12.5％",
            "reference": {"answerable": True},
        },
        {
            "id": "missing-span",
            "company": "乙公司",
            "report_period": "2024H1",
            "metric": "ocf",
            "source_id": "src-b",
            "source_text": "经营活动现金流未披露。",
            "reference": {"answerable": False, "refusal_reason": "insufficient_evidence"},
        },
        {
            "id": "empty-span",
            "company": "丙公司",
            "report_period": "2025Q1",
            "metric": "revenue",
            "source_id": "src-c",
            "source_text": "有原文",
            "evidence_span": "",
            "reference": {"answerable": False},
        },
        {
            "id": "not-in-source",
            "company": "丙公司",
            "report_period": "2025Q1",
            "metric": "net_profit",
            "source_id": "src-c",
            "source_text": "营业收入10亿元",
            "evidence_span": "并不存在的句子",
            "reference": {"answerable": True},
        },
        {
            "id": "non-string-span",
            "company": "丁公司",
            "report_period": "2023FY",
            "metric": "a=b",
            "source_id": "",
            "source_text": "数字12.5亿元",
            "evidence_span": 12.5,
            "reference": {"answerable": "true"},
        },
        {
            "id": "non-string-source",
            "company": "丁公司",
            "source_id": 7,
            "source_text": {"text": "nope"},
            "evidence_span": "营业收入",
        },
        {
            "source_text": "",
            "source_id": None,
            "evidence_span": "x",
        },
        {
            "id": "ws-span",
            "company": "甲公司",
            "source_id": "src space",
            "source_text": "营业收入128.6亿元",
            "evidence_span": "  ",
        },
        {
            "id": "quote-span",
            "source_id": "src-b",
            "source_text": '他说"甲 乙"。',
            "evidence_span": '他说"甲 乙"',
            "reference": {"answerable": True},
        },
        {
            "id": "eq-span",
            "company": "戊公司",
            "source_id": "src-d",
            "source_text": "a=b成立",
            "evidence_span": "a=b",
        },
        {
            "id": "no-source-id",
            "company": "己公司",
            "source_text": "收入1亿元",
            "evidence_span": "收入1亿元",
            "reference": {"answerable": True},
        },
    ]
    path.write_text(
        "# comment\n\n" + "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    spaces_span = "营业收入 128.6 亿元"
    spaces_source = "营业收入128.6亿元。"
    assert spaces_span not in spaces_source
    assert norm_text(spaces_span) in norm_text(spaces_source)
    assert evidence_contained(spaces_span, spaces_source) is True

    fullwidth_span = "净利率12.5％"
    fullwidth_source = "净利率12.5%。"
    assert fullwidth_span not in fullwidth_source
    assert norm_text(fullwidth_span) in norm_text(fullwidth_source)
    assert evidence_contained(fullwidth_span, fullwidth_source) is True

    ws_span = "  "
    ws_source = "营业收入128.6亿元"
    assert ws_span not in ws_source
    assert evidence_contained(ws_span, ws_source) is True

    code, text = _run(["list-evidence", "--data", str(path)])
    assert code == 0
    assert text == (
        "list-evidence items=13 listed=13 with_evidence=10 without_evidence=3 "
        "contained=7 not_contained=6 sources=5\n"
        "by_source:\n"
        "  (none) n=4\n"
        "  src-b n=3\n"
        "  src-a n=2\n"
        "  src-c n=2\n"
        '  "src space" n=1\n'
        "  src-d n=1\n"
        "literal company=甲公司 period=2024FY metric=revenue source_id=src-a "
        "source_chars=12 has_evidence=true evidence_span=营业收入128.6亿元 "
        "evidence_chars=11 contained=true answerable=true\n"
        'spaces company="甲 公司" period=2024FY metric=revenue source_id=src-a '
        'source_chars=12 has_evidence=true evidence_span="营业收入 128.6 亿元" '
        "evidence_chars=13 contained=true answerable=true\n"
        "fullwidth company=乙公司 period=2024H1 metric=net_profit source_id=src-b "
        "source_chars=9 has_evidence=true evidence_span=净利率12.5％ "
        "evidence_chars=8 contained=true answerable=true\n"
        "missing-span company=乙公司 period=2024H1 metric=ocf source_id=src-b "
        "source_chars=11 has_evidence=false evidence_span=(none) evidence_chars=0 "
        "contained=false answerable=false\n"
        "empty-span company=丙公司 period=2025Q1 metric=revenue source_id=src-c "
        'source_chars=3 has_evidence=false evidence_span="" evidence_chars=0 '
        "contained=false answerable=false\n"
        "not-in-source company=丙公司 period=2025Q1 metric=net_profit source_id=src-c "
        "source_chars=8 has_evidence=true evidence_span=并不存在的句子 "
        "evidence_chars=7 contained=false answerable=true\n"
        'non-string-span company=丁公司 period=2023FY metric="a=b" source_id=(none) '
        "source_chars=8 has_evidence=false evidence_span=(none) evidence_chars=0 "
        "contained=false answerable=false\n"
        "non-string-source company=丁公司 period=(none) metric=(none) source_id=(none) "
        "source_chars=0 has_evidence=true evidence_span=营业收入 evidence_chars=4 "
        "contained=false answerable=false\n"
        "(none) company=(none) period=(none) metric=(none) source_id=(none) "
        "source_chars=0 has_evidence=true evidence_span=x evidence_chars=1 "
        "contained=false answerable=false\n"
        'ws-span company=甲公司 period=(none) metric=(none) source_id="src space" '
        'source_chars=11 has_evidence=true evidence_span="  " evidence_chars=2 '
        "contained=true answerable=false\n"
        "quote-span company=(none) period=(none) metric=(none) source_id=src-b "
        'source_chars=8 has_evidence=true evidence_span="他说\\"甲 乙\\"" '
        "evidence_chars=7 contained=true answerable=true\n"
        "eq-span company=戊公司 period=(none) metric=(none) source_id=src-d "
        'source_chars=5 has_evidence=true evidence_span="a=b" evidence_chars=3 '
        "contained=true answerable=false\n"
        "no-source-id company=己公司 period=(none) metric=(none) source_id=(none) "
        "source_chars=5 has_evidence=true evidence_span=收入1亿元 evidence_chars=5 "
        "contained=true answerable=true\n"
    )
    assert "None" not in text
    assert "经营活动现金流未披露" not in text
    assert "数字12.5亿元" not in text
    assert "source_text" not in text

    code, raw = _run(["list-evidence", "--data", str(path), "--format", "json"])
    assert code == 0
    assert "None" not in raw
    payload = json.loads(raw)
    assert payload["data"].endswith("tiny.jsonl")
    assert list(payload) == ["data", "summary", "filters", "by_source", "items"]
    assert payload["summary"] == {
        "n": 13,
        "n_listed": 13,
        "n_with_evidence": 10,
        "n_without_evidence": 3,
        "n_contained": 7,
        "n_not_contained": 6,
        "n_sources": 5,
    }
    assert payload["summary"]["n_with_evidence"] + payload["summary"]["n_without_evidence"] == 13
    assert payload["summary"]["n_contained"] + payload["summary"]["n_not_contained"] == 13
    assert payload["by_source"] == [
        {"key": None, "n": 4},
        {"key": "src-b", "n": 3},
        {"key": "src-a", "n": 2},
        {"key": "src-c", "n": 2},
        {"key": "src space", "n": 1},
        {"key": "src-d", "n": 1},
    ]
    assert "7" not in {row["key"] for row in payload["by_source"]}
    by_id = {row["id"]: row for row in payload["items"]}
    assert by_id["spaces"]["contained"] is True
    assert by_id["spaces"]["evidence_span"] == spaces_span
    assert by_id["spaces"]["contained"] is evidence_contained(spaces_span, spaces_source)
    assert by_id["fullwidth"]["contained"] is evidence_contained(fullwidth_span, fullwidth_source)
    assert by_id["missing-span"]["has_evidence"] is False
    assert by_id["missing-span"]["evidence_span"] is None
    assert by_id["missing-span"]["evidence_chars"] == 0
    assert by_id["missing-span"]["contained"] is False
    assert by_id["missing-span"]["answerable"] is False
    assert by_id["empty-span"]["has_evidence"] is False
    assert by_id["empty-span"]["evidence_span"] == ""
    assert by_id["empty-span"]["evidence_chars"] == 0
    assert by_id["empty-span"]["contained"] is False
    assert by_id["not-in-source"]["has_evidence"] is True
    assert by_id["not-in-source"]["contained"] is False
    assert by_id["non-string-span"]["evidence_span"] is None
    assert by_id["non-string-span"]["source_id"] is None
    assert by_id["non-string-span"]["has_evidence"] is False
    assert by_id["non-string-span"]["contained"] is False
    assert by_id["non-string-span"]["answerable"] is False
    assert by_id["non-string-source"]["source_id"] is None
    assert by_id["non-string-source"]["source_chars"] == 0
    assert by_id["non-string-source"]["contained"] is False
    assert by_id["non-string-source"]["answerable"] is False
    assert by_id[None]["source_id"] is None
    assert by_id[None]["source_chars"] == 0
    assert by_id[None]["evidence_span"] == "x"
    assert by_id[None]["contained"] is False
    assert by_id["ws-span"]["has_evidence"] is True
    assert by_id["ws-span"]["evidence_span"] == "  "
    assert by_id["ws-span"]["contained"] is evidence_contained(ws_span, ws_source)
    assert by_id["ws-span"]["source_id"] == "src space"
    assert by_id["no-source-id"]["source_id"] is None
    assert by_id["no-source-id"]["contained"] is True
    assert by_id["no-source-id"]["answerable"] is True
    for row in payload["items"]:
        assert list(row) == _ROW_KEYS
        assert "source_text" not in row

    code, raw = _run(
        ["list-evidence", "--data", str(path), "--format", "json", "--kind", "not_contained"]
    )
    assert code == 0
    missed = json.loads(raw)
    assert [row["id"] for row in missed["items"]] == [
        "not-in-source",
        "non-string-source",
        None,
    ]
    assert missed["summary"]["n"] == 13
    assert missed["summary"]["n_listed"] == 3
    assert missed["summary"]["n_with_evidence"] == 3
    assert missed["summary"]["n_without_evidence"] == 0
    assert missed["summary"]["n_contained"] == 0
    assert missed["summary"]["n_not_contained"] == 3
    assert missed["summary"]["n_sources"] == 1
    assert missed["by_source"] == [{"key": None, "n": 2}, {"key": "src-c", "n": 1}]
    assert "missing-span" not in {row["id"] for row in missed["items"]}
    assert "empty-span" not in {row["id"] for row in missed["items"]}
    assert "non-string-span" not in {row["id"] for row in missed["items"]}

    code, raw = _run(
        ["list-evidence", "--data", str(path), "--format", "json", "--kind", "missing_evidence"]
    )
    assert code == 0
    missing = json.loads(raw)
    assert [row["id"] for row in missing["items"]] == [
        "missing-span",
        "empty-span",
        "non-string-span",
    ]
    assert missing["summary"]["n_listed"] == 3
    assert missing["summary"]["n_without_evidence"] == 3
    assert missing["summary"]["n_not_contained"] == 3
    assert missing["summary"]["n_contained"] == 0

    code, raw = _run(
        ["list-evidence", "--data", str(path), "--format", "json", "--kind", "contained"]
    )
    assert code == 0
    kept = json.loads(raw)
    assert [row["id"] for row in kept["items"]] == [
        "literal",
        "spaces",
        "fullwidth",
        "ws-span",
        "quote-span",
        "eq-span",
        "no-source-id",
    ]
    assert kept["summary"]["n_listed"] == 7
    assert kept["summary"]["n_contained"] == 7
    assert kept["summary"]["n_not_contained"] == 0

    code, raw = _run(
        [
            "list-evidence",
            "--data",
            str(path),
            "--format",
            "json",
            "--company",
            "丙公司",
            "--metric",
            "net_profit",
            "--kind",
            "not_contained",
            "--source",
            "src-c",
        ]
    )
    assert code == 0
    combined = json.loads(raw)
    assert [row["id"] for row in combined["items"]] == ["not-in-source"]
    assert combined["summary"]["n"] == 13
    assert combined["summary"]["n_listed"] == 1
    assert combined["summary"]["n_sources"] == 1
    assert combined["filters"] == {
        "company": "丙公司",
        "metric": "net_profit",
        "period": None,
        "id": None,
        "source": "src-c",
        "kind": "not_contained",
    }

    code, text = _run(
        [
            "list-evidence",
            "--data",
            str(path),
            "--company",
            "甲公司",
            "--kind",
            "missing_evidence",
        ]
    )
    assert code == 0
    assert text == (
        "list-evidence items=13 listed=0 with_evidence=0 without_evidence=0 "
        "contained=0 not_contained=0 sources=0\n"
        "filters company=甲公司 kind=missing_evidence\n"
        "no items\n"
    )

    code, text = _run(["list-evidence", "--data", str(path), "--company", "甲"])
    assert code == 0
    assert "listed=0" in text
    assert "no items" in text
    assert "literal " not in text


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        collect_list_evidence([], data_name="x", kind="nope")

    with pytest.raises(SystemExit) as exc:
        main(["list-evidence", "--kind", "nope"])
    assert exc.value.code == 2


def test_list_evidence_writes_nothing_and_needs_no_pred(
    tmp_path: Path, gold_path: Path, monkeypatch
) -> None:
    loaded: list[Path] = []
    real_load = load_jsonl

    def spy(path: Path) -> list[dict]:
        loaded.append(Path(path))
        return real_load(path)

    def fail_grade(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("list-evidence must not grade")

    def fail_qc(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("list-evidence must not run qc")

    monkeypatch.setattr("fin_qa_eval.cli.load_jsonl", spy)
    monkeypatch.setattr("fin_qa_eval.cli.grade", fail_grade)
    monkeypatch.setattr("fin_qa_eval.cli.run_qc", fail_qc)
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    assert main(["list-evidence", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert text.startswith(_SHIPPED_HEADER + "\n")
    assert loaded == [gold_path]
    assert list(tmp_path.iterdir()) == []


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(argv, stdout=buf)
    return code, buf.getvalue()
