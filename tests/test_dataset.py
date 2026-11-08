from __future__ import annotations

import importlib.util
from pathlib import Path

from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.qc import run_qc
from fin_qa_eval.schema import load_conventions, load_schema


def _materialize(repo_root: Path):
    path = repo_root / "data" / "materialize.py"
    spec = importlib.util.spec_from_file_location("fin_qa_eval_materialize", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_matches_committed_jsonl(repo_root: Path, gold_path: Path, bad_path: Path, pred_path: Path) -> None:
    module = _materialize(repo_root)
    assert gold_path.read_text(encoding="utf-8") == module.rendered_gold()
    assert bad_path.read_text(encoding="utf-8") == module.rendered_bad()
    assert pred_path.read_text(encoding="utf-8") == module.rendered_predictions()


def test_gold_set_is_synthetic_and_covers_the_task(gold_path: Path) -> None:
    items = load_jsonl(gold_path)
    assert 30 <= len(items) <= 45
    assert len({item["id"] for item in items}) == len(items)
    companies = {item["company"] for item in items}
    assert companies == {
        "星澜科技",
        "北辰医药",
        "澄海乳业",
        "青禾新能源",
        "梧桐家居",
        "赤川半导体",
        "白露食品",
        "岚桥物流",
    }
    metrics = {item["metric"] for item in items}
    assert {
        "revenue",
        "net_profit",
        "operating_cashflow",
        "revenue_yoy",
        "net_profit_yoy",
        "operating_cashflow_yoy",
    } <= metrics
    assert all(item["synthetic"] is True for item in items)
    assert all(item["source_text"].startswith("【虚构示例，非真实披露】") for item in items)
    assert any(item["language"] == "en" for item in items)
    assert sum(1 for item in items if not item["reference"]["answerable"]) >= 5
    assert any(item["reference"].get("value") is not None and item["reference"]["value"] < 0 for item in items)
    boundaries = [
        tag
        for item in items
        for tag in item["tags"]
        if tag.startswith("boundary:")
    ]
    assert "boundary:unit_conversion" in boundaries
    assert "boundary:insufficient_evidence" in boundaries
    assert "boundary:unit_ambiguous" in boundaries
    assert "boundary:convention_conflict" in boundaries
    assert "boundary:out_of_scope" in boundaries
    for item in items:
        span = item["evidence_span"]
        if span:
            assert span in item["source_text"]
        for distractor in item.get("distractors") or []:
            assert distractor["span"] in item["source_text"]


def test_gold_passes_qc_and_conventions_load(gold_path: Path) -> None:
    items = load_jsonl(gold_path)
    report = run_qc(items, load_schema())
    assert report.ok, [issue.to_dict() for issue in report.issues]
    assert report.boundary_counts["unit_conversion"] >= 1
    conventions = load_conventions()
    assert conventions["conventions"]["scope"]["consolidated"]["zh"] == "合并口径"
    assert conventions["rounding"]["tie_break"] == "half_up"
