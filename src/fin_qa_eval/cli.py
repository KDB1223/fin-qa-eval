"""Command line for validate, qc, grade, report, failures, compare, stats, list-items, and list-distractors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence, TextIO

from fin_qa_eval import __version__
from fin_qa_eval.compare import (
    compare_grades,
    is_regression,
    render_compare_markdown,
    render_compare_text,
)
from fin_qa_eval.failures import collect_failures, render_failures_text
from fin_qa_eval.graders import grade
from fin_qa_eval.list_distractors import collect_list_distractors, render_list_distractors_text
from fin_qa_eval.list_items import collect_list_items, render_list_items_text
from fin_qa_eval.loader import LoadError, load_jsonl
from fin_qa_eval.paths import demo_predictions_path, gold_path, schema_path
from fin_qa_eval.qc import run_qc
from fin_qa_eval.report import format_score, qc_status_line, render_grade_report, render_qc_report
from fin_qa_eval.schema import SchemaLoadError, load_schema
from fin_qa_eval.stats import collect_stats, render_stats_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fin-qa-eval",
        description=(
            "Offline eval toolkit for Chinese financial-report QA. "
            "Validates the task schema, runs quality checks, and grades "
            "predictions on numeric accuracy, evidence consistency, and refusal. "
            "failures inventories items that missed full credit. "
            "compare diffs two prediction files on the same gold set. "
            "stats inventories gold-set coverage without grading. "
            "list-items inventories each gold item without grading. "
            "list-distractors inventories 口径 trap figures in distractors[] without grading."
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

    failures_cmd = sub.add_parser(
        "failures",
        help="Inventory items that missed full credit",
    )
    _add_data_args(failures_cmd, default_data=None)
    failures_cmd.add_argument(
        "--pred",
        type=Path,
        default=None,
        help="Prediction JSONL (default: examples/predictions.jsonl)",
    )
    failures_cmd.add_argument("--format", choices=("text", "json"), default="text")
    failures_cmd.add_argument(
        "--error",
        default=None,
        help="Keep failures whose primary_error or errors list contains this tag",
    )
    failures_cmd.add_argument(
        "--company",
        default=None,
        help="Keep failures whose company matches exactly",
    )
    failures_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Keep the failure with this item id",
    )
    failures_cmd.set_defaults(func=cmd_failures)

    compare = sub.add_parser(
        "compare",
        help="Compare two prediction JSONL files against the same gold set",
    )
    _add_data_args(compare, default_data=None)
    compare.add_argument(
        "--pred-a",
        type=Path,
        required=True,
        help="Baseline prediction JSONL",
    )
    compare.add_argument(
        "--pred-b",
        type=Path,
        required=True,
        help="Candidate prediction JSONL",
    )
    compare.add_argument("--format", choices=("text", "json"), default="text")
    compare.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write a Markdown comparison report to this path",
    )
    compare.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit 1 if candidate overall drops or any item overall decreases",
    )
    compare.set_defaults(func=cmd_compare)

    stats_cmd = sub.add_parser(
        "stats",
        help="Inventory gold-set coverage (companies, 口径, refusals)",
    )
    _add_data_args(stats_cmd, default_data=None)
    stats_cmd.add_argument("--format", choices=("text", "json"), default="text")
    stats_cmd.set_defaults(func=cmd_stats)

    list_items_cmd = sub.add_parser(
        "list-items",
        help="Inventory each gold item (id, 口径, answerable/refusal)",
    )
    _add_data_args(list_items_cmd, default_data=None)
    list_items_cmd.add_argument("--format", choices=("text", "json"), default="text")
    list_items_cmd.add_argument(
        "--company",
        default=None,
        help="Keep items whose company matches exactly",
    )
    list_items_cmd.add_argument(
        "--metric",
        default=None,
        help="Keep items whose metric matches exactly",
    )
    list_items_cmd.add_argument(
        "--period",
        default=None,
        help="Keep items whose report_period matches exactly",
    )
    list_items_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Keep the item with this id",
    )
    list_items_cmd.add_argument(
        "--refusal",
        default=None,
        help="Keep items whose reference.refusal_reason matches exactly",
    )
    list_items_cmd.set_defaults(func=cmd_list_items)

    list_distractors_cmd = sub.add_parser(
        "list-distractors",
        help="Inventory 口径 trap figures in each gold item's distractors",
    )
    _add_data_args(list_distractors_cmd, default_data=None)
    list_distractors_cmd.add_argument("--format", choices=("text", "json"), default="text")
    list_distractors_cmd.add_argument(
        "--reason",
        default=None,
        help="Keep distractors whose reason matches exactly",
    )
    list_distractors_cmd.add_argument(
        "--company",
        default=None,
        help="Keep distractors whose item company matches exactly",
    )
    list_distractors_cmd.add_argument(
        "--metric",
        default=None,
        help="Keep distractors whose item metric matches exactly",
    )
    list_distractors_cmd.add_argument(
        "--id",
        dest="item_id",
        default=None,
        help="Keep distractors whose item id matches exactly",
    )
    list_distractors_cmd.set_defaults(func=cmd_list_distractors)
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


def cmd_failures(args: argparse.Namespace, stdout: TextIO) -> int:
    """List misses. ``--schema`` is accepted and not loaded. Exit 0 even if some items failed."""

    data_file = _gold(args)
    pred_file = _pred(args)
    gold_items = load_jsonl(data_file)
    predictions = load_jsonl(pred_file)
    graded = grade(gold_items, predictions)
    payload = collect_failures(
        graded,
        gold_items,
        predictions,
        gold_name=_display_path(data_file),
        pred_name=_display_path(pred_file),
        error=args.error,
        company=args.company,
        item_id=args.item_id,
    )
    if args.format == "json":
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(render_failures_text(payload))
    return 0


def cmd_compare(args: argparse.Namespace, stdout: TextIO) -> int:
    data_file = _gold(args)
    pred_a = args.pred_a
    pred_b = args.pred_b
    gold_items = load_jsonl(data_file)
    graded_a = grade(gold_items, load_jsonl(pred_a))
    graded_b = grade(gold_items, load_jsonl(pred_b))
    report = compare_grades(
        graded_a,
        graded_b,
        gold_name=_display_path(data_file),
        pred_a_name=_display_path(pred_a),
        pred_b_name=_display_path(pred_b),
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_compare_markdown(report), encoding="utf-8")
    if args.format == "json":
        json.dump(report, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(render_compare_text(report))
    if args.out:
        print(f"wrote {args.out}", file=stdout)
    if args.fail_on_regression and is_regression(report):
        return 1
    return 0


def cmd_stats(args: argparse.Namespace, stdout: TextIO) -> int:
    """Count gold-set coverage. ``--schema`` is accepted and not loaded."""

    data_file = _gold(args)
    payload = {"data": _display_path(data_file), **collect_stats(load_jsonl(data_file))}
    if args.format == "json":
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(render_stats_text(payload))
    return 0


def cmd_list_items(args: argparse.Namespace, stdout: TextIO) -> int:
    """List gold items. ``--schema`` is accepted and not loaded. Does not grade."""

    data_file = _gold(args)
    payload = collect_list_items(
        load_jsonl(data_file),
        data_name=_display_path(data_file),
        company=args.company,
        metric=args.metric,
        period=args.period,
        item_id=args.item_id,
        refusal=args.refusal,
    )
    if args.format == "json":
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(render_list_items_text(payload))
    return 0


def cmd_list_distractors(args: argparse.Namespace, stdout: TextIO) -> int:
    """List distractor traps. ``--schema`` is accepted and not loaded. Does not grade."""

    data_file = _gold(args)
    payload = collect_list_distractors(
        load_jsonl(data_file),
        data_name=_display_path(data_file),
        reason=args.reason,
        company=args.company,
        metric=args.metric,
        item_id=args.item_id,
    )
    if args.format == "json":
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(render_list_distractors_text(payload))
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
