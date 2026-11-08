"""Command line for validate, qc, grade, and report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence, TextIO

from fin_qa_eval import __version__
from fin_qa_eval.graders import grade
from fin_qa_eval.loader import LoadError, load_jsonl
from fin_qa_eval.paths import demo_predictions_path, gold_path, schema_path
from fin_qa_eval.qc import run_qc
from fin_qa_eval.report import format_score, qc_status_line, render_grade_report, render_qc_report
from fin_qa_eval.schema import SchemaLoadError, load_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fin-qa-eval",
        description=(
            "Offline eval toolkit for Chinese financial-report QA. "
            "Validates the task schema, runs quality checks, and grades "
            "predictions on numeric accuracy, evidence consistency, and refusal."
        ),
    )
    parser.add_argument("--version", action="version", version=f"fin-qa-eval {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate eval items against the JSON Schema")
    _add_data_args(validate, default_data=None)
    validate.add_argument("--format", choices=("text", "json"), default="text")
    validate.set_defaults(func=cmd_validate)

    qc = sub.add_parser("qc", help="Schema plus duplicate, evidence, and unit checks")
    _add_data_args(qc, default_data=None)
    qc.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    qc.set_defaults(func=cmd_qc)

    grade_cmd = sub.add_parser("grade", help="Grade a prediction JSONL file offline")
    _add_data_args(grade_cmd, default_data=None)
    grade_cmd.add_argument(
        "--pred",
        type=Path,
        default=None,
        help="Prediction JSONL (default: examples/predictions.jsonl)",
    )
    grade_cmd.add_argument("--format", choices=("text", "json"), default="text")
    grade_cmd.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write the full per-item grade JSON to this path",
    )
    grade_cmd.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit 1 when overall score is below this threshold",
    )
    grade_cmd.set_defaults(func=cmd_grade)

    report = sub.add_parser("report", help="Write a Markdown error-attribution report")
    _add_data_args(report, default_data=None)
    report.add_argument("--pred", type=Path, default=None)
    report.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Markdown output path (default: stdout)",
    )
    report.set_defaults(func=cmd_report)
    return parser


def _add_data_args(parser: argparse.ArgumentParser, default_data: Optional[Path]) -> None:
    parser.add_argument(
        "--data",
        type=Path,
        default=default_data,
        help="Eval JSONL (default: data/samples/eval_set.jsonl)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="JSON Schema path (default: data/schema/eval_item.schema.json)",
    )


def main(argv: Optional[Sequence[str]] = None, stdout: Optional[TextIO] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = stdout or sys.stdout
    try:
        return int(args.func(args, out))
    except (LoadError, SchemaLoadError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def cmd_validate(args: argparse.Namespace, stdout: TextIO) -> int:
    data_file = _gold(args)
    items = load_jsonl(data_file)
    schema = load_schema(args.schema or schema_path())
    report = run_qc(items, schema)
    schema_only = [issue for issue in report.issues if issue.code == "schema_violation"]
    if args.format == "json":
        payload = {
            "data": _display_path(data_file),
            "items": len(items),
            "ok": not schema_only,
            "errors": [issue.to_dict() for issue in schema_only],
        }
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    elif schema_only:
        print(f"validate FAIL: {len(schema_only)} schema errors in {data_file}", file=stdout)
        for issue in schema_only:
            print(f"  {issue.message}", file=stdout)
    else:
        print(f"validate PASS: {len(items)} items in {data_file}", file=stdout)
    return 1 if schema_only else 0


def cmd_qc(args: argparse.Namespace, stdout: TextIO) -> int:
    data_file = _gold(args)
    items = load_jsonl(data_file)
    schema = load_schema(args.schema or schema_path())
    report = run_qc(items, schema)
    if args.format == "json":
        payload = report.to_dict()
        payload["data"] = _display_path(data_file)
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    elif args.format == "markdown":
        stdout.write(render_qc_report(report, data_name=_display_path(data_file)))
    else:
        print(qc_status_line(report), file=stdout)
        if not report.ok:
            for issue in report.issues:
                if issue.severity != "error":
                    continue
                ident = issue.item_id or "-"
                print(f"  [{issue.code}] {ident}: {issue.message}", file=stdout)
    return 0 if report.ok else 1


def cmd_grade(args: argparse.Namespace, stdout: TextIO) -> int:
    data_file = _gold(args)
    pred_file = _pred(args)
    graded = grade(load_jsonl(data_file), load_jsonl(pred_file))
    summary = graded.summary()
    payload = {
        "gold": _display_path(data_file),
        "predictions": _display_path(pred_file),
        "summary": summary,
        "warnings": graded.warnings,
        "items": [row.to_dict() for row in graded.results],
    }
    if args.json_out:
        _write_json(args.json_out, payload)
    if args.format == "json":
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        print(
            "grade items={n} full_credit={full} overall={overall} "
            "numeric={numeric} evidence={evidence} refusal={refusal}".format(
                n=summary["n"],
                full=summary["n_full_credit"],
                overall=format_score(summary["overall"]),
                numeric=format_score(summary["numeric_accuracy"]),
                evidence=format_score(summary["evidence_consistency"]),
                refusal=format_score(summary["refusal_appropriateness"]),
            ),
            file=stdout,
        )
        for warning in graded.warnings:
            print(f"warning: {warning}", file=stdout)
    if args.fail_under is not None and summary["overall"] < args.fail_under:
        return 1
    return 0


def cmd_report(args: argparse.Namespace, stdout: TextIO) -> int:
    data_file = _gold(args)
    pred_file = _pred(args)
    graded = grade(load_jsonl(data_file), load_jsonl(pred_file))
    text = render_grade_report(
        graded,
        gold_name=_display_path(data_file),
        pred_name=_display_path(pred_file),
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=stdout)
    else:
        stdout.write(text)
    return 0


def _gold(args: argparse.Namespace) -> Path:
    return args.data or gold_path()


def _pred(args: argparse.Namespace) -> Path:
    if args.pred:
        return args.pred
    demo = demo_predictions_path()
    if demo.is_file():
        return demo
    raise LoadError("pass --pred; examples/predictions.jsonl was not found")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)
