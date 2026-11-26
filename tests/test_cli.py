import io
import json

from fin_qa_eval.cli import main


def test_validate_qc_grade_and_report(tmp_path, gold_path, bad_path, pred_path) -> None:
    assert main(["validate", "--data", str(gold_path)]) == 0
    assert main(["qc", "--data", str(gold_path)]) == 0
    assert main(["qc", "--data", str(bad_path)]) == 1
    assert main(["validate", "--data", str(bad_path)]) == 1
    assert main(["grade", "--data", str(gold_path), "--pred", str(pred_path)]) == 0
    assert (
        main(
            [
                "grade",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--fail-under",
                "0.99",
            ]
        )
        == 1
    )
    out = tmp_path / "scoreboard.md"
    assert (
        main(
            [
                "report",
                "--data",
                str(gold_path),
                "--pred",
                str(pred_path),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    text = out.read_text(encoding="utf-8")
    assert "综合 overall" in text
    assert "按公司" in text
    assert "按错误类型" in text
    metric_at = text.index("## 按指标 / By metric")
    error_at = text.index("## 按错误类型 / By error type")
    for heading in (
        "## 按口径范围 / By scope",
        "## 按会计基础 / By basis",
        "## 按利润视角 / By profit view",
        "## 按含税口径 / By tax",
        "## 按单位 / By unit",
    ):
        assert metric_at < text.index(heading) < error_at

    buf = io.StringIO()
    assert (
        main(
            [
                "grade",
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
    assert {"consolidated", "parent"} <= set(payload["summary"]["by_scope"])
    assert "(none)" in payload["summary"]["by_profit_view"]
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id["xlkj-2024q3-revenue"]["scope"] == "consolidated"
    assert by_id["xlkj-2024q3-revenue"]["profit_view"] == "(none)"
    assert by_id["xlkj-2024q3-revenue"]["unit"] == "CNY_hundred_million"


def test_stats_command(gold_path) -> None:
    buf = io.StringIO()
    assert main(["stats", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert "items=38" in text
    assert "by_scope" in text

    buf = io.StringIO()
    assert main(["stats", "--data", str(gold_path), "--format", "json"], stdout=buf) == 0
    payload = json.loads(buf.getvalue())
    assert payload["n"] == 38


def test_list_distractors_command(gold_path) -> None:
    buf = io.StringIO()
    assert main(["list-distractors", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert "items=38" in text
    assert "listed=6" in text
    assert "with_distractors=6" in text
    assert "without_distractors=32" in text

    buf = io.StringIO()
    assert main(["list-distractors", "--data", str(gold_path), "--format", "json"], stdout=buf) == 0
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n"] == 38
    assert payload["summary"]["n_listed"] == 6
    assert payload["summary"]["n_with_distractors"] == 6
    assert payload["by_reason"][0]["key"] == "parent_scope"


def test_list_items_command(gold_path) -> None:
    buf = io.StringIO()
    assert main(["list-items", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert "items=38" in text
    assert "listed=38" in text

    buf = io.StringIO()
    assert main(["list-items", "--data", str(gold_path), "--format", "json"], stdout=buf) == 0
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n"] == 38
    assert payload["summary"]["n_listed"] == 38


def test_list_evidence_command(gold_path) -> None:
    buf = io.StringIO()
    assert main(["list-evidence", "--data", str(gold_path)], stdout=buf) == 0
    text = buf.getvalue()
    assert "items=38" in text
    assert "listed=38" in text
    assert "with_evidence=38" in text
    assert "without_evidence=0" in text
    assert "contained=38" in text
    assert "not_contained=0" in text
    assert "sources=8" in text
    assert "src-bcyy-2024fy n=8" in text
    assert "【虚构示例" not in text

    buf = io.StringIO()
    assert main(["list-evidence", "--data", str(gold_path), "--format", "json"], stdout=buf) == 0
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n"] == 38
    assert payload["summary"]["n_listed"] == 38
    assert payload["summary"]["n_with_evidence"] == 38
    assert payload["summary"]["n_contained"] == 38
    assert payload["summary"]["n_not_contained"] == 0
    assert payload["summary"]["n_sources"] == 8
    assert payload["by_source"][0] == {"key": "src-bcyy-2024fy", "n": 8}
    assert len(payload["by_source"]) == 8
    assert len(payload["items"]) == 38


def test_list_predictions_command(gold_path, pred_path) -> None:
    buf = io.StringIO()
    assert main(
        ["list-predictions", "--data", str(gold_path), "--pred", str(pred_path)],
        stdout=buf,
    ) == 0
    text = buf.getvalue()
    assert "gold=38" in text
    assert "pred=38" in text
    assert "listed=38" in text
    assert "covered=38" in text
    assert "missing_gold=0" in text

    buf = io.StringIO()
    assert main(
        [
            "list-predictions",
            "--data",
            str(gold_path),
            "--pred",
            str(pred_path),
            "--format",
            "json",
        ],
        stdout=buf,
    ) == 0
    payload = json.loads(buf.getvalue())
    assert payload["summary"]["n_gold"] == 38
    assert payload["summary"]["n_pred"] == 38
    assert payload["summary"]["n_gold_covered"] == 38
    assert payload["summary"]["n_gold_missing"] == 0
    assert payload["missing_gold"] == []
