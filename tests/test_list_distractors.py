"""口径 trap inventory. Counts and values come from the shipped eval set."""

from __future__ import annotations

import io
import json
from pathlib import Path

from fin_qa_eval.cli import main
from fin_qa_eval.list_distractors import collect_list_distractors, render_list_distractors_text
from fin_qa_eval.loader import load_jsonl

_ROW_KEYS = [
    "id",
    "company",
    "report_period",
    "metric",
    "reason",
    "value",
    "unit",
    "span",
]

_SHIPPED = [
    {
        "id": "xlkj-2024q3-revenue",
        "company": "星澜科技",
        "report_period": "2024Q3",
        "metric": "revenue",
        "reason": "parent_scope",
        "value": 86.2,
        "unit": "CNY_hundred_million",
        "span": "母公司营业收入86.2亿元",
    },
    {
        "id": "xlkj-2024q3-revenue-yoy",
        "company": "星澜科技",
        "report_period": "2024Q3",
        "metric": "revenue_yoy",
        "reason": "prior_period",
        "value": 112.4,
        "unit": "CNY_hundred_million",
        "span": "上年同期112.4亿元",
    },
    {
        "id": "bcyy-2024fy-revenue",
        "company": "北辰医药",
        "report_period": "2024FY",
        "metric": "revenue",
        "reason": "parent_scope",
        "value": 210.4,
        "unit": "CNY_hundred_million",
        "span": "母公司营业收入210.4亿元",
    },
    {
        "id": "bcyy-2024fy-parent-revenue",
        "company": "北辰医药",
        "report_period": "2024FY",
        "metric": "revenue",
        "reason": "consolidated_scope",
        "value": 356.2,
        "unit": "CNY_hundred_million",
        "span": "2024年公司合并营业收入356.2亿元",
    },
    {
        "id": "chry-2024h1-revenue",
        "company": "澄海乳业",
        "report_period": "2024H1",
        "metric": "revenue",
        "reason": "tax_inclusive",
        "value": 104.4,
        "unit": "CNY_hundred_million",
        "span": "含税销售额104.4亿元",
    },
    {
        "id": "wtjj-2023fy-revenue",
        "company": "梧桐家居",
        "report_period": "2023FY",
        "metric": "revenue",
        "reason": "overseas_only",
        "value": 12.1,
        "unit": "CNY_hundred_million",
        "span": "其中境外收入12.1亿元",
    },
]

_SHIPPED_BY_REASON = [
    {"key": "parent_scope", "n": 2},
    {"key": "consolidated_scope", "n": 1},
    {"key": "overseas_only", "n": 1},
    {"key": "prior_period", "n": 1},
    {"key": "tax_inclusive", "n": 1},
]

_OPEN_FILTERS = {"reason": None, "company": None, "metric": None, "id": None}


def test_shipped_eval_set_lists_distractors_in_file_order(gold_path: Path) -> None:
    gold = load_jsonl(gold_path)
    report = collect_list_distractors(gold, data_name="data/samples/eval_set.jsonl")
    assert report["summary"] == {
        "n": 38,
        "n_listed": 6,
        "n_with_distractors": 6,
        "n_without_distractors": 32,
    }
    assert report["summary"]["n_with_distractors"] + report["summary"]["n_without_distractors"] == 38
    assert report["filters"] == _OPEN_FILTERS
    assert report["by_reason"] == _SHIPPED_BY_REASON
    assert report["distractors"] == _SHIPPED
    for row in report["distractors"]:
        assert list(row) == _ROW_KEYS
        assert isinstance(row["value"], float)
    listed_ids = {row["id"] for row in report["distractors"]}
    assert "bcyy-2024fy-parent-np" not in listed_ids
    assert "xlkj-2024q3-deducted-np" not in listed_ids
    assert sum(1 for item in gold if item.get("id") not in listed_ids) == 32

    text = render_list_distractors_text(report)
    assert text == (
        "list-distractors items=38 listed=6 with_distractors=6 without_distractors=32\n"
        "xlkj-2024q3-revenue company=星澜科技 period=2024Q3 metric=revenue "
        "reason=parent_scope value=86.2 unit=CNY_hundred_million span=母公司营业收入86.2亿元\n"
        "xlkj-2024q3-revenue-yoy company=星澜科技 period=2024Q3 metric=revenue_yoy "
        "reason=prior_period value=112.4 unit=CNY_hundred_million span=上年同期112.4亿元\n"
        "bcyy-2024fy-revenue company=北辰医药 period=2024FY metric=revenue "
        "reason=parent_scope value=210.4 unit=CNY_hundred_million span=母公司营业收入210.4亿元\n"
        "bcyy-2024fy-parent-revenue company=北辰医药 period=2024FY metric=revenue "
        "reason=consolidated_scope value=356.2 unit=CNY_hundred_million "
        "span=2024年公司合并营业收入356.2亿元\n"
        "chry-2024h1-revenue company=澄海乳业 period=2024H1 metric=revenue "
        "reason=tax_inclusive value=104.4 unit=CNY_hundred_million span=含税销售额104.4亿元\n"
        "wtjj-2023fy-revenue company=梧桐家居 period=2023FY metric=revenue "
        "reason=overseas_only value=12.1 unit=CNY_hundred_million span=其中境外收入12.1亿元\n"
    )
    assert "filters " not in text
    assert "None" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert len(text.splitlines()) == 7


def test_json_format_matches_collector(repo_root: Path, gold_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    code, raw = _run(["list-distractors", "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    assert "None" not in raw
    assert "母公司营业收入86.2亿元" in raw
    assert '"reason": "parent_scope"' in raw
    payload = json.loads(raw)
    expected = collect_list_distractors(
        load_jsonl(gold_path),
        data_name="data/samples/eval_set.jsonl",
    )
    assert payload == expected
    assert payload["data"] == "data/samples/eval_set.jsonl"
    assert list(payload) == ["data", "summary", "filters", "by_reason", "distractors"]
    assert list(payload["summary"]) == [
        "n",
        "n_listed",
        "n_with_distractors",
        "n_without_distractors",
    ]
    assert list(payload["filters"]) == ["reason", "company", "metric", "id"]
    assert list(payload["distractors"][0]) == _ROW_KEYS
    assert payload["distractors"][0]["value"] == 86.2
    assert payload["by_reason"][0] == {"key": "parent_scope", "n": 2}


def test_filters_are_exact_and_anded(gold_path: Path) -> None:
    code, raw = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--reason",
            "parent_scope",
        ]
    )
    assert code == 0
    reason = json.loads(raw)
    assert reason["summary"]["n"] == 38
    assert reason["summary"]["n_listed"] == 2
    assert reason["summary"]["n_with_distractors"] == 6
    assert reason["summary"]["n_without_distractors"] == 32
    assert [row["id"] for row in reason["distractors"]] == [
        "xlkj-2024q3-revenue",
        "bcyy-2024fy-revenue",
    ]
    assert reason["by_reason"] == [{"key": "parent_scope", "n": 2}]
    assert reason["filters"]["reason"] == "parent_scope"
    assert reason["filters"]["company"] is None

    code, raw = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--company",
            "星澜科技",
        ]
    )
    assert code == 0
    company = json.loads(raw)
    assert [row["id"] for row in company["distractors"]] == [
        "xlkj-2024q3-revenue",
        "xlkj-2024q3-revenue-yoy",
    ]
    assert company["summary"]["n_listed"] == 2
    assert company["summary"]["n_with_distractors"] == 6
    assert company["filters"]["company"] == "星澜科技"
    assert company["by_reason"] == [
        {"key": "parent_scope", "n": 1},
        {"key": "prior_period", "n": 1},
    ]

    code, raw = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--metric",
            "revenue",
        ]
    )
    assert code == 0
    metric = json.loads(raw)
    assert [row["id"] for row in metric["distractors"]] == [
        "xlkj-2024q3-revenue",
        "bcyy-2024fy-revenue",
        "bcyy-2024fy-parent-revenue",
        "chry-2024h1-revenue",
        "wtjj-2023fy-revenue",
    ]
    assert metric["summary"]["n_listed"] == 5
    assert "xlkj-2024q3-revenue-yoy" not in {row["id"] for row in metric["distractors"]}

    code, raw = _run(
        [
            "list-distractors",
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
    assert one["distractors"] == [_SHIPPED[0]]
    assert one["summary"]["n"] == 38
    assert one["summary"]["n_listed"] == 1
    assert one["summary"]["n_with_distractors"] == 6
    assert one["filters"]["id"] == "xlkj-2024q3-revenue"

    code, raw = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--id",
            "xlkj-2024q3-revenue",
            "--company",
            "星澜科技",
            "--metric",
            "revenue",
            "--reason",
            "parent_scope",
        ]
    )
    assert code == 0
    combined = json.loads(raw)
    assert [row["id"] for row in combined["distractors"]] == ["xlkj-2024q3-revenue"]
    assert combined["summary"]["n_listed"] == 1
    assert combined["filters"] == {
        "reason": "parent_scope",
        "company": "星澜科技",
        "metric": "revenue",
        "id": "xlkj-2024q3-revenue",
    }

    code, text = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--id",
            "chry-2024h1-revenue",
            "--reason",
            "tax_inclusive",
        ]
    )
    assert code == 0
    assert text.startswith(
        "list-distractors items=38 listed=1 with_distractors=6 without_distractors=32\n"
    )
    assert "filters reason=tax_inclusive id=chry-2024h1-revenue\n" in text
    assert "chry-2024h1-revenue " in text
    assert "xlkj-2024q3-revenue " not in text

    code, text = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--reason",
            "parent_scope",
            "--company",
            "澄海乳业",
        ]
    )
    assert code == 0
    assert text == (
        "list-distractors items=38 listed=0 with_distractors=6 without_distractors=32\n"
        "filters reason=parent_scope company=澄海乳业\n"
        "no distractors\n"
    )

    code, text = _run(["list-distractors", "--data", str(gold_path), "--company", "星澜"])
    assert code == 0
    assert "listed=0" in text
    assert "filters company=星澜\n" in text
    assert "no distractors" in text
    assert "xlkj-2024q3-revenue" not in text

    code, raw = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--format",
            "json",
            "--reason",
            "not-a-reason",
            "--company",
            "不存在公司",
            "--metric",
            "not-a-metric",
            "--id",
            "missing-id",
        ]
    )
    assert code == 0
    empty = json.loads(raw)
    assert empty["summary"]["n"] == 38
    assert empty["summary"]["n_listed"] == 0
    assert empty["summary"]["n_with_distractors"] == 6
    assert empty["summary"]["n_without_distractors"] == 32
    assert empty["by_reason"] == []
    assert empty["distractors"] == []
    assert "None" not in raw

    code, text = _run(
        [
            "list-distractors",
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
        "list-distractors items=38 listed=0 with_distractors=6 without_distractors=32\n"
    )
    assert 'filters company="no such co" metric="a=b"\n' in text
    assert text.endswith("no distractors\n")
    assert not text.endswith("\n\n")


def test_schema_flag_is_accepted_and_unused(tmp_path: Path, gold_path: Path) -> None:
    code, text = _run(
        [
            "list-distractors",
            "--data",
            str(gold_path),
            "--schema",
            str(tmp_path / "no-such-schema.json"),
        ]
    )
    assert code == 0
    assert text.startswith(
        "list-distractors items=38 listed=6 with_distractors=6 without_distractors=32\n"
    )


def test_missing_data_file_exits_2(tmp_path: Path, capsys) -> None:
    code = main(["list-distractors", "--data", str(tmp_path / "missing.jsonl")])
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    assert main(["list-distractors", "--data", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")


def test_empty_file_prints_no_distractors(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    code, text = _run(["list-distractors", "--data", str(path)])
    assert code == 0
    assert text == (
        "list-distractors items=0 listed=0 with_distractors=0 without_distractors=0\n"
        "no distractors\n"
    )

    code, raw = _run(["list-distractors", "--data", str(path), "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    payload = json.loads(raw)
    assert payload["summary"] == {
        "n": 0,
        "n_listed": 0,
        "n_with_distractors": 0,
        "n_without_distractors": 0,
    }
    assert payload["by_reason"] == []
    assert payload["distractors"] == []
    assert payload["filters"] == _OPEN_FILTERS


def test_items_without_distractors_and_non_dict_entries(tmp_path: Path) -> None:
    path = tmp_path / "tiny.jsonl"
    rows = [
        {"id": "no-field", "company": "甲", "report_period": "2024Q3", "metric": "revenue"},
        {"id": "null-field", "company": "甲", "distractors": None},
        {"id": "string-field", "company": "甲", "distractors": "parent_scope"},
        {"id": "dict-field", "company": "甲", "distractors": {"reason": "parent_scope", "value": 9}},
        {"id": "empty", "company": "甲", "distractors": []},
        {"id": "scalars", "company": "甲", "distractors": ["nope", 1, None, ["nested"]]},
        {
            "id": "mixed",
            "company": "甲 公司",
            "distractors": [
                "skip",
                {
                    "reason": "parent_scope",
                    "value": 1.5,
                    "unit": "CNY",
                    "span": "甲 公司收入",
                },
                {"reason": None, "value": None, "span": ""},
            ],
        },
        {
            "id": "two",
            "company": "乙 公司",
            "report_period": "2024FY",
            "metric": "a=b",
            "distractors": [
                {"reason": "prior_period", "value": 10, "unit": "percent", "span": "上年"},
                {
                    "reason": "absolute_change",
                    "value": 2,
                    "unit": "CNY_million",
                    "span": "增加 2",
                },
            ],
        },
        {"id": "blank", "distractors": [{}]},
        {
            "id": "bool-value",
            "distractors": [
                {"reason": "wrong_unit_scale", "value": True, "unit": "CNY", "span": "x"}
            ],
        },
    ]
    path.write_text(
        "# comment\n\n" + "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    code, text = _run(["list-distractors", "--data", str(path)])
    assert code == 0
    assert text == (
        "list-distractors items=10 listed=6 with_distractors=4 without_distractors=6\n"
        "mixed company=\"甲 公司\" period=(none) metric=(none) "
        "reason=parent_scope value=1.5 unit=CNY span=\"甲 公司收入\"\n"
        "mixed company=\"甲 公司\" period=(none) metric=(none) "
        "reason=(none) value=(none) unit=(none) span=\"\"\n"
        "two company=\"乙 公司\" period=2024FY metric=\"a=b\" "
        "reason=prior_period value=10 unit=percent span=上年\n"
        "two company=\"乙 公司\" period=2024FY metric=\"a=b\" "
        "reason=absolute_change value=2 unit=CNY_million span=\"增加 2\"\n"
        "blank company=(none) period=(none) metric=(none) "
        "reason=(none) value=(none) unit=(none) span=(none)\n"
        "bool-value company=(none) period=(none) metric=(none) "
        "reason=wrong_unit_scale value=true unit=CNY span=x\n"
    )
    assert "None" not in text
    assert "no-field" not in text
    assert "scalars" not in text
    assert "dict-field" not in text

    code, raw = _run(["list-distractors", "--data", str(path), "--format", "json"])
    assert code == 0
    assert "None" not in raw
    payload = json.loads(raw)
    assert payload["data"].endswith("tiny.jsonl")
    assert payload["summary"] == {
        "n": 10,
        "n_listed": 6,
        "n_with_distractors": 4,
        "n_without_distractors": 6,
    }
    assert payload["by_reason"] == [
        {"key": None, "n": 2},
        {"key": "absolute_change", "n": 1},
        {"key": "parent_scope", "n": 1},
        {"key": "prior_period", "n": 1},
        {"key": "wrong_unit_scale", "n": 1},
    ]
    by_id: dict[str, list[dict]] = {}
    for row in payload["distractors"]:
        by_id.setdefault(row["id"], []).append(row)
    assert set(by_id) == {"mixed", "two", "blank", "bool-value"}
    assert by_id["mixed"][0]["value"] == 1.5
    assert isinstance(by_id["mixed"][0]["value"], float)
    assert by_id["mixed"][1]["reason"] is None
    assert by_id["mixed"][1]["value"] is None
    assert by_id["mixed"][1]["unit"] is None
    assert by_id["mixed"][1]["span"] == ""
    assert by_id["two"][0]["value"] == 10
    assert isinstance(by_id["two"][0]["value"], int)
    assert by_id["blank"][0]["id"] == "blank"
    assert by_id["blank"][0]["company"] is None
    assert by_id["blank"][0]["span"] is None
    assert by_id["bool-value"][0]["value"] is True

    code, raw = _run(
        [
            "list-distractors",
            "--data",
            str(path),
            "--format",
            "json",
            "--company",
            "甲 公司",
            "--reason",
            "parent_scope",
        ]
    )
    assert code == 0
    filtered = json.loads(raw)
    assert filtered["summary"]["n"] == 10
    assert filtered["summary"]["n_listed"] == 1
    assert filtered["summary"]["n_with_distractors"] == 4
    assert filtered["summary"]["n_without_distractors"] == 6
    assert [row["id"] for row in filtered["distractors"]] == ["mixed"]
    assert filtered["distractors"][0]["reason"] == "parent_scope"
    assert filtered["by_reason"] == [{"key": "parent_scope", "n": 1}]

    code, text = _run(
        ["list-distractors", "--data", str(path), "--reason", "absolute_change", "--id", "mixed"]
    )
    assert code == 0
    assert text == (
        "list-distractors items=10 listed=0 with_distractors=4 without_distractors=6\n"
        "filters reason=absolute_change id=mixed\n"
        "no distractors\n"
    )


def test_list_distractors_writes_nothing_and_needs_no_pred(
    tmp_path: Path, gold_path: Path, monkeypatch
) -> None:
    loaded: list[Path] = []
    real_load = load_jsonl

    def spy(path: Path) -> list[dict]:
        loaded.append(Path(path))
        return real_load(path)

    def fail_grade(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("list-distractors must not grade")

    monkeypatch.setattr("fin_qa_eval.cli.load_jsonl", spy)
    monkeypatch.setattr("fin_qa_eval.cli.grade", fail_grade)
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    assert main(["list-distractors", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert text.startswith(
        "list-distractors items=38 listed=6 with_distractors=6 without_distractors=32\n"
    )
    assert loaded == [gold_path]
    assert list(tmp_path.iterdir()) == []


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(argv, stdout=buf)
    return code, buf.getvalue()
