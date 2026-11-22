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
