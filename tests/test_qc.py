from fin_qa_eval.loader import load_jsonl
from fin_qa_eval.qc import run_qc
from fin_qa_eval.schema import load_schema


def test_bad_fixtures_expose_each_planted_defect(bad_path) -> None:
    report = run_qc(load_jsonl(bad_path), load_schema())
    assert not report.ok
    codes = set(report.codes())
    expected = {
        "duplicate_id",
        "duplicate_question",
        "missing_field",
        "schema_violation",
        "evidence_not_in_source",
        "unit_anomaly",
        "unanswerable_has_value",
        "answerable_missing_value",
        "distractor_equals_gold",
        "not_synthetic",
        "unknown_metric",
        "missing_refusal_reason",
    }
    assert expected <= codes
