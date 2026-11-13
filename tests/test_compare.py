import io
import json
from pathlib import Path

from fin_qa_eval.cli import main
from fin_qa_eval.compare import (
    SUMMARY_KEYS,
    compare_grades,
    format_delta,
    is_regression,
    render_compare_text,
)
from fin_qa_eval.graders import GradeOutput, ItemResult
from fin_qa_eval.report import format_score

_REVENUE_ID = "xlkj-2024q3-revenue"
_GOLD_EVIDENCE = "公司合并口径实现营业收入128.6亿元"


def test_format_delta_signs() -> None:
    assert format_delta(0.0) == "0.0000"
    assert format_delta(0.5) == "+0.5000"
    assert format_delta(-0.5) == "-0.5000"
    assert format_delta(0.00005) == "+0.0001"
    assert format_delta(-0.00005) == "-0.0001"
    assert format_delta(0.00001) == "0.0000"
    assert format_delta(1 / 38) == "+0.0263"


def test_compare_identical_file_is_zero(gold_path: Path, pred_path: Path) -> None:
    code, text = _run(
        [
            "compare",
            "--data",
            str(gold_path),
            "--pred-a",
            str(pred_path),
            "--pred-b",
            str(pred_path),
            "--fail-on-regression",
        ]
    )
    assert code == 0
    assert "improved=0" in text
    assert "regressed=0" in text
    assert "overall=0.0000" in text
    assert "transitions: (none)" in text
    assert "improved: (none)" in text
    assert "regressed: (none)" in text

    code, payload_text = _run(
        [
            "compare",
            "--data",
            str(gold_path),
            "--pred-a",
            str(pred_path),
            "--pred-b",
            str(pred_path),
            "--format",
            "json",
        ]
    )
    assert code == 0
    payload = json.loads(payload_text)
    assert payload["gold"].endswith("eval_set.jsonl")
    assert payload["pred_a"].endswith("predictions.jsonl")
    assert payload["pred_b"].endswith("predictions.jsonl")
    assert format_score(payload["baseline"]["overall"]) == "0.8421"
    for key in SUMMARY_KEYS:
        assert payload["delta"][key] == 0
    assert payload["counts"]["improved"] == 0
    assert payload["counts"]["regressed"] == 0
    assert payload["counts"]["unchanged"] == payload["baseline"]["n"]
    assert payload["counts"]["primary_error_changed"] == 0
    assert payload["transitions"] == []
    assert payload["improved"] == []
    assert payload["regressed"] == []


def test_compare_fixed_item_improves(tmp_path: Path, gold_path: Path, pred_path: Path) -> None:
    fixed = _with_revenue_fix(pred_path, tmp_path / "fixed.jsonl")
    code, payload_text = _run(
        [
            "compare",
            "--data",
            str(gold_path),
            "--pred-a",
            str(pred_path),
            "--pred-b",
            str(fixed),
            "--format",
            "json",
            "--fail-on-regression",
        ]
    )
    assert code == 0
    payload = json.loads(payload_text)
    assert payload["delta"]["overall"] > 0
    assert payload["delta"]["numeric_accuracy"] > 0
    assert payload["delta"]["evidence_consistency"] > 0
    assert payload["delta"]["refusal_appropriateness"] == 0
    assert payload["delta"]["n_full_credit"] == 1
    assert payload["counts"]["improved"] == 1
    assert payload["counts"]["regressed"] == 0
    assert [row["id"] for row in payload["regressed"]] == []
    assert payload["transitions"] == [
        {"from": "convention_mismatch", "to": None, "count": 1},
    ]
    improved = payload["improved"]
    assert [row["id"] for row in improved] == [_REVENUE_ID]
    row = improved[0]
    assert row["company"] == "星澜科技"
    assert row["overall_a"] < row["overall_b"] == 1.0
    assert row["primary_error_a"] == "convention_mismatch"
    assert row["primary_error_b"] is None

    code, text = _run(
        [
            "compare",
            "--data",
            str(gold_path),
            "--pred-a",
            str(pred_path),
            "--pred-b",
            str(fixed),
        ]
    )
    assert code == 0
    improved_at = text.index("improved:")
    regressed_at = text.index("regressed:")
    assert _REVENUE_ID in text[improved_at:regressed_at]
    assert _REVENUE_ID not in text[regressed_at:]


def test_compare_fail_on_regression(tmp_path: Path, gold_path: Path, pred_path: Path) -> None:
    fixed = _with_revenue_fix(pred_path, tmp_path / "fixed.jsonl")
    argv = [
        "compare",
        "--data",
        str(gold_path),
        "--pred-a",
        str(fixed),
        "--pred-b",
        str(pred_path),
        "--format",
        "json",
    ]
    code, _ = _run(argv)
    assert code == 0
    code, payload_text = _run(argv + ["--fail-on-regression"])
    assert code == 1
    payload = json.loads(payload_text)
    assert payload["delta"]["overall"] < 0
    assert [row["id"] for row in payload["regressed"]] == [_REVENUE_ID]
    assert payload["improved"] == []
    assert {"from": None, "to": "convention_mismatch", "count": 1} in payload["transitions"]


def test_compare_markdown_out(tmp_path: Path, gold_path: Path, pred_path: Path) -> None:
    fixed = _with_revenue_fix(pred_path, tmp_path / "fixed_predictions.jsonl")
    out = tmp_path / "nested" / "compare.md"
    code, stdout = _run(
        [
            "compare",
            "--data",
            str(gold_path),
            "--pred-a",
            str(pred_path),
            "--pred-b",
            str(fixed),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    json_text, wrote_line, trailing = stdout.rsplit("\n", 2)
    assert trailing == ""
    assert wrote_line == f"wrote {out}"
    payload = json.loads(json_text)
    assert payload["improved"][0]["id"] == _REVENUE_ID

    text = out.read_text(encoding="utf-8")
    assert "总表 / Scoreboard" in text
    assert "综合 overall" in text
    assert "Synthetic demo data only" in text
    assert "虚构示例" in text
    assert "offline" in text
    assert "examples/predictions.jsonl" in text or str(pred_path) in text
    assert "fixed_predictions.jsonl" in text
    assert _REVENUE_ID in text


def test_compare_missing_prediction_exits_2(tmp_path: Path, gold_path: Path, pred_path: Path) -> None:
    code, _ = _run(
        [
            "compare",
            "--data",
            str(gold_path),
            "--pred-a",
            str(pred_path),
            "--pred-b",
            str(tmp_path / "missing.jsonl"),
        ]
    )
    assert code == 2


def test_compare_sorts_transitions_and_items() -> None:
    baseline = GradeOutput(
        results=[
            _row("a", 0.0, "numeric_mismatch"),
            _row("b", 0.0, "numeric_mismatch"),
            _row("c", 1.0, None),
            _row("d", 0.5, "unit_scale_error"),
            _row("e", 0.0, "sign_error"),
        ]
    )
    candidate = GradeOutput(
        results=[
            _row("a", 0.5, None),
            _row("b", 0.2, None),
            _row("c", 0.5, "over_refusal"),
            _row("d", 0.5, "evidence_missing"),
            _row("e", 0.5, "sign_error"),
        ]
    )
    report = compare_grades(
        baseline,
        candidate,
        gold_name="gold.jsonl",
        pred_a_name="a.jsonl",
        pred_b_name="b.jsonl",
    )
    assert report["transitions"] == [
        {"from": "numeric_mismatch", "to": None, "count": 2},
        {"from": None, "to": "over_refusal", "count": 1},
        {"from": "unit_scale_error", "to": "evidence_missing", "count": 1},
    ]
    assert [row["id"] for row in report["improved"]] == ["a", "e", "b"]
    assert [row["id"] for row in report["regressed"]] == ["c"]
    assert report["counts"] == {
        "improved": 3,
        "regressed": 1,
        "unchanged": 1,
        "primary_error_changed": 4,
    }
    assert report["delta"]["overall"] > 0
    assert is_regression(report)
    assert "a 星澜科技 overall 0.0000 -> 0.5000 primary numeric_mismatch -> (none)" in render_compare_text(
        report
    )


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = main(argv, stdout=buf)
    return code, buf.getvalue()


def _with_revenue_fix(src: Path, dest: Path) -> Path:
    lines_out: list[str] = []
    for raw in src.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            lines_out.append(raw)
            continue
        row = json.loads(stripped)
        if row.get("id") == _REVENUE_ID:
            row["answer"] = "128.6亿元"
            row["value"] = 128.6
            row["unit"] = "CNY_hundred_million"
            row["evidence"] = _GOLD_EVIDENCE
            row["refused"] = False
        lines_out.append(json.dumps(row, ensure_ascii=False))
    dest.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return dest


def _row(item_id: str, overall: float, primary: str | None) -> ItemResult:
    return ItemResult(
        id=item_id,
        company="星澜科技",
        report_period="2024Q3",
        metric="revenue",
        language="zh",
        answerable=True,
        numeric_accuracy=overall,
        evidence_consistency=overall,
        refusal_appropriateness=overall,
        overall=overall,
        errors=[primary] if primary else [],
        primary_error=primary,
    )
