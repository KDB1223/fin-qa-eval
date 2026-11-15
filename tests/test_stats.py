"""Coverage inventory for the gold set. Counts come from the shipped file."""

from __future__ import annotations

import io
import json
from pathlib import Path

from fin_qa_eval.cli import main
from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.stats import HISTOGRAMS, collect_stats, render_stats_text


def test_shipped_eval_set_coverage(gold_path: Path) -> None:
    report = collect_stats(load_jsonl(gold_path))
    assert report["n"] == 38
    assert report["n_answerable"] == 32
    assert report["n_unanswerable"] == 6
    assert _pairs(report["by_company"]) == [
        ("北辰医药", 8),
        ("星澜科技", 6),
        ("青禾新能源", 6),
        ("白露食品", 5),
        ("岚桥物流", 4),
        ("澄海乳业", 4),
        ("赤川半导体", 3),
        ("梧桐家居", 2),
    ]
    assert _bucket(report["by_company"], "北辰医药")["n_answerable"] == 7
    assert _bucket(report["by_company"], "北辰医药")["n_unanswerable"] == 1
    assert _pairs(report["by_metric"]) == [
        ("net_profit", 11),
        ("revenue", 11),
        ("operating_cashflow", 6),
        ("revenue_yoy", 5),
        ("net_profit_yoy", 3),
        ("operating_cashflow_yoy", 2),
    ]
    assert _pairs(report["by_period"]) == [
        ("2024FY", 19),
        ("2024Q3", 9),
        ("2024H1", 4),
        ("2025Q1", 4),
        ("2023FY", 2),
    ]
    assert _pairs(report["by_unit"]) == [
        ("CNY_hundred_million", 26),
        ("percent", 10),
        ("CNY_ten_thousand", 2),
    ]
    assert _pairs(report["by_scope"]) == [("consolidated", 36), ("parent", 2)]
    assert _pairs(report["by_basis"]) == [("gaap", 37), ("non_gaap", 1)]
    assert _bucket(report["by_basis"], "non_gaap")["n_answerable"] == 0
    assert _bucket(report["by_basis"], "non_gaap")["n_unanswerable"] == 1
    assert _pairs(report["by_profit_view"]) == [(None, 24), ("attributable", 13), ("net", 1)]
    assert _pairs(report["by_tax"]) == [(None, 22), ("ex_tax", 16)]
    assert _bucket(report["by_tax"], None)["n_answerable"] == 17
    assert _bucket(report["by_tax"], None)["n_unanswerable"] == 5
    assert all(row["key"] != "inc_tax" for row in report["by_tax"])
    assert _pairs(report["by_refusal_reason"]) == [
        ("insufficient_evidence", 3),
        ("convention_conflict", 1),
        ("out_of_scope", 1),
        ("unit_ambiguous", 1),
    ]
    assert all(row["key"] is not None for row in report["by_refusal_reason"])
    assert sum(row["n"] for row in report["by_refusal_reason"]) == report["n_unanswerable"]
    assert _pairs(report["by_language"]) == [("zh", 37), ("en", 1)]
    for name in HISTOGRAMS:
        _assert_sorted(report[name])

    text = render_stats_text(report)
    assert text.startswith("stats items=38 answerable=32 unanswerable=6\n")
    assert "by_company:\n  北辰医药 n=8\n" in text
    assert "  梧桐家居 n=2\n" in text
    assert "by_scope:\n  consolidated n=36\n  parent n=2\n" in text
    assert "by_basis:\n  gaap n=37\n  non_gaap n=1\n" in text
    assert "by_profit_view:\n  (none) n=24\n  attributable n=13\n  net n=1\n" in text
    assert "by_tax:\n  (none) n=22\n  ex_tax n=16\n" in text
    assert (
        "by_refusal_reason:\n"
        "  insufficient_evidence n=3\n"
        "  convention_conflict n=1\n"
        "  out_of_scope n=1\n"
        "  unit_ambiguous n=1\n"
    ) in text
    assert "by_language:\n  zh n=37\n  en n=1\n" in text
    assert "None" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_small_fixture_null_convention_and_refusal(tmp_path: Path) -> None:
    path = tmp_path / "tiny.jsonl"
    rows = [
        _item(company="甲公司", answerable=True, tax=None, reason=None, language="zh"),
        _item(
            company="甲公司",
            answerable=True,
            tax="ex_tax",
            reason=None,
            scope="parent",
            language="zh",
        ),
        _item(
            company="乙公司",
            answerable=False,
            tax=None,
            reason="insufficient_evidence",
            language="en",
        ),
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    code, text = _run(["stats", "--data", str(path)])
    assert code == 0
    assert text.startswith("stats items=3 answerable=2 unanswerable=1\n")
    assert "by_company:\n  甲公司 n=2\n  乙公司 n=1\n" in text
    assert "by_tax:\n  (none) n=2\n  ex_tax n=1\n" in text
    assert "by_refusal_reason:\n  insufficient_evidence n=1\n" in text
    assert "None" not in text

    code, raw = _run(["stats", "--data", str(path), "--format", "json"])
    assert code == 0
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    assert '"key": null' in raw
    assert "None" not in raw
    payload = json.loads(raw)
    assert payload["n"] == 3
    assert payload["n_answerable"] == 2
    assert payload["n_unanswerable"] == 1
    assert payload["data"].endswith("tiny.jsonl")
    assert _pairs(payload["by_company"]) == [("甲公司", 2), ("乙公司", 1)]
    assert _bucket(payload["by_company"], "甲公司")["n_answerable"] == 2
    assert _pairs(payload["by_tax"]) == [(None, 2), ("ex_tax", 1)]
    assert _pairs(payload["by_scope"]) == [("consolidated", 2), ("parent", 1)]
    assert _pairs(payload["by_refusal_reason"]) == [("insufficient_evidence", 1)]
    assert _pairs(payload["by_language"]) == [("zh", 2), ("en", 1)]


def test_sorts_by_count_then_key() -> None:
    report = collect_stats(
        [
            _item(company="b", metric="revenue", tax=None),
            _item(company="a", metric="net_profit", tax="ex_tax"),
            _item(company="b", metric="revenue", tax="ex_tax"),
        ]
    )
    assert [row["key"] for row in report["by_company"]] == ["b", "a"]
    assert [row["key"] for row in report["by_metric"]] == ["revenue", "net_profit"]
    tied = collect_stats(
        [
            _item(company="b", tax=None),
            _item(company="a", tax="ex_tax"),
        ]
    )
    assert [row["key"] for row in tied["by_company"]] == ["a", "b"]
    assert [row["key"] for row in tied["by_tax"]] == [None, "ex_tax"]
    text = render_stats_text(tied)
    assert "by_company:\n  a n=1\n  b n=1\n" in text
    assert "by_tax:\n  (none) n=1\n  ex_tax n=1\n" in text


def test_missing_convention_and_null_refusal() -> None:
    bare = _item(company="丙公司", answerable=True, tax="ex_tax")
    del bare["convention"]
    refused = _item(company="丁公司", answerable=False, tax=None, reason=None)
    report = collect_stats([bare, refused])
    assert report["n_answerable"] == 1
    assert report["n_unanswerable"] == 1
    assert _pairs(report["by_scope"]) == [(None, 1), ("consolidated", 1)]
    assert report["by_tax"] == [
        {"key": None, "n": 2, "n_answerable": 1, "n_unanswerable": 1}
    ]
    assert report["by_refusal_reason"] == []
    text = render_stats_text(report)
    assert "by_scope:\n  (none) n=1\n  consolidated n=1\n" in text
    assert "by_refusal_reason:\nby_language:\n" in text


def test_omits_language_when_the_field_is_absent() -> None:
    report = collect_stats([_item(company="甲公司", include_language=False)])
    assert "by_language" not in report
    assert "by_language" not in render_stats_text(report)

    mixed = collect_stats(
        [
            _item(company="甲公司", language="en"),
            _item(company="乙公司", include_language=False),
        ]
    )
    assert [row["key"] for row in mixed["by_language"]] == [None, "en"]


def test_stats_ignores_schema_and_missing_file_exits_2(tmp_path: Path, gold_path: Path) -> None:
    code, text = _run(
        [
            "stats",
            "--data",
            str(gold_path),
            "--schema",
            str(tmp_path / "no-such-schema.json"),
        ]
    )
    assert code == 0
    assert "items=38" in text
    assert "by_scope" in text

    code, text = _run(["stats", "--data", str(tmp_path / "missing.jsonl")])
    assert code == 2
    assert text == ""


def test_stats_default_data_path(repo_root: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    code, raw = _run(["stats", "--format", "json"])
    assert code == 0
    payload = json.loads(raw)
    assert payload["n"] == 38
    assert payload["data"] == "data/samples/eval_set.jsonl"
    assert list(payload)[:4] == ["data", "n", "n_answerable", "n_unanswerable"]
    assert '"key": null' in raw
    assert "北辰医药" in raw


def _item(
    *,
    company: str,
    answerable: bool = True,
    tax: str | None = None,
    reason: str | None = None,
    language: str | None = "zh",
    include_language: bool = True,
    scope: str | None = "consolidated",
    metric: str = "revenue",
    period: str = "2024FY",
    unit: str = "CNY_hundred_million",
    basis: str = "gaap",
    profit_view: str | None = None,
) -> dict:
    item: dict = {
        "company": company,
        "metric": metric,
        "report_period": period,
        "unit": unit,
        "convention": {
            "scope": scope,
            "basis": basis,
            "profit_view": profit_view,
            "tax": tax,
        },
        "reference": {"answerable": answerable, "refusal_reason": reason},
    }
    if include_language:
        item["language"] = language
    return item


def _pairs(rows: list[dict]) -> list[tuple[str | None, int]]:
    return [(row["key"], row["n"]) for row in rows]


def _bucket(rows: list[dict], key: str | None) -> dict:
    for row in rows:
        if row["key"] == key:
            return row
    raise AssertionError(f"missing bucket {key!r}")


def _assert_sorted(rows: list[dict]) -> None:
    decorated = [(-row["n"], "" if row["key"] is None else row["key"]) for row in rows]
    assert decorated == sorted(decorated)


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(argv, stdout=buf)
    return code, buf.getvalue()
