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
