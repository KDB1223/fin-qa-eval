# fin-qa-eval

[![CI](https://github.com/KDB1223/fin-qa-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/KDB1223/fin-qa-eval/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Offline eval set and grader for Chinese financial-report QA.** It scores numeric accuracy, evidence consistency, and whether a refusal was earned — and it treats 口径 (consolidation scope, GAAP vs. deducted profit, tax, attributable profit) as data, not as a prompt afterthought.

No API keys. The same prediction file always produces the same scoreboard.

中文说明：[README.zh-CN.md](README.zh-CN.md) · 课程实验：[docs/lab-zh.md](docs/lab-zh.md)

> **Synthetic demo data.** Companies, tickers, and figures are invented. Every snippet starts with `【虚构示例，非真实披露】` and every row sets `"synthetic": true`. This is not a scrape of real filings.

## Quickstart

From a checkout, about a minute, offline:

```bash
python3 -m pip install -e ".[dev]"
python3 -m fin_qa_eval validate
python3 -m fin_qa_eval qc
python3 -m fin_qa_eval grade --pred examples/predictions.jsonl
python3 -m fin_qa_eval report --pred examples/predictions.jsonl --out examples/scoreboard.md
```

`fin-qa-eval` is the same console script once it is on `PATH`. `examples/quickstart.sh` runs the same steps and checks that the planted bad file exits 1.

`validate` checks the JSON Schema. `qc` adds duplicate detection, evidence containment, and unit anomalies. `stats` inventories gold-set coverage. `list-items` lists each gold item. `list-distractors` lists the 口径 trap figures in `distractors[]`. `list-predictions` checks whether a prediction file covers the gold set before grading. `grade` / `report` score a prediction JSONL. Grading does not call a model.

## Fixture scoreboard

`examples/predictions.jsonl` is **fixture-extractor-v1**, a deterministic stand-in that answers most items and misses the traps on purpose. Full report: [examples/scoreboard.md](examples/scoreboard.md).

| Dimension | Score |
| --- | ---: |
| 数值准确 numeric accuracy | 0.7632 |
| 证据一致 evidence consistency | 0.8421 |
| 拒答合理 refusal appropriateness | 0.9211 |
| **Overall** | **0.8421** |

38 items, 28 at full credit. Overall is the unweighted mean of the three dimensions.

| Company | n | Overall | Top error |
| --- | ---: | ---: | --- |
| 北辰医药 Beichen Pharma | 8 | 0.9167 | unit_scale_error |
| 岚桥物流 Lanqiao Logistics | 4 | 0.5000 | under_refusal |
| 星澜科技 Xinglan Tech | 6 | 0.8889 | convention_mismatch |
| 梧桐家居 Wutong Home | 2 | 0.8333 | evidence_not_in_source |
| 澄海乳业 Chenghai Dairy | 4 | 0.8333 | convention_mismatch |
| 白露食品 Bailu Foods | 5 | 0.8000 | over_refusal |
| 赤川半导体 Chichuan Semi | 3 | 0.8889 | unit_scale_error |
| 青禾新能源 Qinghe Energy | 6 | 0.9444 | sign_error |

| Error type | Items |
| --- | ---: |
| convention_mismatch (口径) | 2 |
| unit_scale_error | 2 |
| under_refusal | 2 |
| evidence_overclaim | 2 |
| numeric_mismatch | 1 |
| sign_error | 1 |
| over_refusal | 1 |
| evidence_not_in_source | 1 |

What those rows are doing:

| id | Failure |
| --- | --- |
| `xlkj-2024q3-revenue` | Answered parent-company revenue 86.2 instead of consolidated 128.6 |
| `chry-2024h1-revenue` | Answered tax-inclusive sales 104.4 instead of ex-tax revenue 92.4 |
| `bcyy-2024fy-revenue-wanyuan` | Copied 356.2 into 万元; 356.2 亿元 is 3,562,000 万元 |
| `ccsc-2024q3-revenue` | Treated 18,950 百万元 as 18,950 亿元 (100×) |
| `qhne-2024fy-ocf` | Dropped the minus on −3.8 亿元 of operating cash flow |
| `blsp-2024fy-net-profit` | Refused a disclosed 0.82 亿元 profit |
| `lqwl-2025q1-ocf` | Invented a cash-flow figure the snippet does not contain |
| `lqwl-2025q1-unit-ambiguous` | Assumed unitless “7.6” means 亿元 |

## Why 口径 is a field

Each item binds the answer to a convention, not only to a metric name:

| Field | Values | What goes wrong if you skip it |
| --- | --- | --- |
| `scope` | `consolidated`, `parent` | 合并 128.6 vs 母公司 86.2 |
| `basis` | `gaap`, `non_gaap` | 归母净利润 vs 扣非 |
| `profit_view` | `attributable`, `net`, `operating` | 归母 vs 营业利润 |
| `tax` | `ex_tax`, `inc_tax` | 不含税营业收入 vs 含税销售额 |
| `unit` | 元 / 万元 / 百万元 / 亿元 / percent | same digits, wrong scale |

Distractors sit in `distractors[]` with a reason (`parent_scope`, `tax_inclusive`, `overseas_only`, …). If a prediction matches a distractor after unit normalization, the error is `convention_mismatch`, not a generic numeric miss. Definitions live in [`data/schema/field_conventions.yaml`](data/schema/field_conventions.yaml).

YoY is a percentage-point number (`+14.41`, not `0.1441`), half-up to 0.01. The evidence lists the current amount first and the comparison amount second. A non-positive comparison base is **not** a ratio in this project: the item is unanswerable with `convention_conflict` (see Qinghe’s negative operating cash flow).

## Task shape

```json
{
  "id": "xlkj-2024q3-revenue",
  "company": "星澜科技",
  "report_period": "2024Q3",
  "metric": "revenue",
  "convention": {"scope": "consolidated", "basis": "gaap", "profit_view": null, "tax": "ex_tax"},
  "unit": "CNY_hundred_million",
  "question": "按合并口径、不含税，星澜科技2024年第三季度营业收入是多少？",
  "source_id": "src-xlkj-2024q3",
  "evidence_span": "公司合并口径实现营业收入128.6亿元",
  "reference": {"answerable": true, "value": 128.6, "unit": "CNY_hundred_million", "display": "128.6亿元", "refusal_reason": null},
  "synthetic": true
}
```

The shipped set has 38 items across revenue, net profit, operating cash flow, and their YoY changes, including unit-conversion items and refusal boundaries (`insufficient_evidence`, `unit_ambiguous`, `convention_conflict`, `out_of_scope`). Schema: [`data/schema/eval_item.schema.json`](data/schema/eval_item.schema.json).

A prediction is one JSON object per line:

```json
{"id": "xlkj-2024q3-revenue", "answer": "128.6亿元", "value": 128.6, "unit": "CNY_hundred_million", "evidence": "公司合并口径实现营业收入128.6亿元", "refused": false}
```

`value` + `unit` win when present. Otherwise the grader parses the first amount in `answer` (`128.6亿元`, `同比下降13.99%`, `-3.8亿元`). `refused: true` or a refusal phrase (`拒答`, `未披露`, `证据不足`, `insufficient evidence`) is a refusal. Evidence must be a span of `source_text`, not a paraphrase.

Tolerances: money matches within 0.1% or 1 CNY after conversion to yuan; YoY matches within 0.05 percentage point. Factors of 10, 100, 1e3, 1e4, 1e6, or 1e8 are labeled `unit_scale_error`.

## Commands

| Command | Exit 0 | Exit 1 |
| --- | --- | --- |
| `fin-qa-eval validate` | Schema holds | Any schema error |
| `fin-qa-eval qc` | Schema and semantic checks hold | Duplicates, missing fields, bad evidence, unit anomalies, non-synthetic rows |
| `fin-qa-eval grade --pred FILE` | File graded | Only with `--fail-under X` when overall &lt; X |
| `fin-qa-eval report --pred FILE --out report.md` | Markdown written | — |
| `fin-qa-eval failures --pred FILE` | Inventory printed | — |
| `fin-qa-eval compare --pred-a A --pred-b B` | Both files graded | With `--fail-on-regression`, candidate overall is lower or any item overall decreases |
| `fin-qa-eval stats` | Eval file loaded | — |
| `fin-qa-eval list-items` | Eval file loaded | — |
| `fin-qa-eval list-distractors` | Eval file loaded | — |
| `fin-qa-eval list-predictions --pred FILE` | Inventory printed | — |

`grade --format json` and `report` roll scores up by company, period, and metric, and also by 口径 (`scope`, `basis`, `profit_view`, `tax`) and unit. `compare` grades both prediction files offline and reports B-A score deltas, which items improved or regressed, and how primary errors moved. `stats` is an inventory of the gold set, not a grade: companies, metrics, periods, units, 口径 (`scope`, `basis`, `profit_view`, `tax`), language, and refusal boundaries. It does not read a prediction file.

`failures` lists items with overall below 1, joined to the gold reference and the prediction that was graded (value, unit, and raw answer). Partial credit counts. It is an inventory, not a gate: exit 0 even when there are misses. `--fail-under` stays on `grade`. A load error still exits 2. Filters `--error`, `--company`, and `--id` are ANDed; a filter that matches nothing still exits 0 and prints `no failures`. `--format json` prints summary counts and the failure objects only.

`list-items` inventories each gold item (id, company, period, metric, 口径, unit, and whether it is answerable or a refusal) without grading or reading a prediction file. Filters `--company`, `--metric`, `--period`, `--id`, and `--refusal` are ANDed; a filter that matches nothing still exits 0 and prints `no items`. `--format json` prints the summary and the listed items. A load error exits 2.

`list-distractors` inventories each 口径 trap in `distractors[]` (item id, company, period, metric, reason, value, unit, and span) without grading or reading a prediction file. Items are walked in file order, and each distractor object is one row. A missing field, a non-list, or an empty list adds no rows. A non-object entry is skipped and does not by itself count as a trap. `n` is the loaded item count. `n_with_distractors` and `n_without_distractors` partition those loaded items and stay put when filters are applied. `n_listed` and `by_reason` describe the rows that remain; reason counts are sorted by count descending, then reason ascending. Filters `--reason`, `--company`, `--metric`, and `--id` are ANDed exact matches; a filter that matches nothing still exits 0 and prints `no distractors`. `--format json` prints the summary, filters, reason counts, and the listed distractors. A load error exits 2.

`list-predictions` inventories a prediction JSONL against the gold set without grading. It does not call a model, write a file, or run the graders, and it does not change scores. Prediction rows stay in file order, including a missing id and a repeated id. `grade` drops a row with no usable id and keeps the last row for a duplicate id; this command lists every row and flags only the later copies. A usable id is a non-empty string. `in_gold` is true only when that id is on a gold item. `unknown` is a usable id that is not in the gold set. `missing_gold` lists gold ids with no usable prediction, in gold file order, and row filters do not hide it. `n_gold`, `n_pred`, `n_gold_covered`, `n_gold_missing`, `n_missing_id`, `n_unknown`, and `n_duplicate` describe the loaded files. `n_listed`, `n_refused`, `n_with_value`, `n_with_evidence`, and `n_in_gold` describe the rows that remain. Refusal uses the grader's `prediction_refused` check. Filters `--id`, `--company`, and `--kind` (`in_gold`, `unknown`, `missing_id`, `duplicate`, `refused`) are ANDed exact matches. A filter that matches nothing still exits 0 and prints `no predictions`. Exit 0 after a successful inventory, including an empty prediction file, unknown ids, or duplicates. `--fail-under` stays on `grade`. A load error exits 2. `--format json` prints the summary, filters, missing gold ids, and the listed rows.

```bash
fin-qa-eval stats
fin-qa-eval list-items
fin-qa-eval list-items --company 星澜科技
fin-qa-eval list-distractors
fin-qa-eval list-distractors --reason parent_scope
fin-qa-eval list-predictions --pred examples/predictions.jsonl
fin-qa-eval list-predictions --pred examples/predictions.jsonl --kind unknown
fin-qa-eval qc --data data/fixtures/bad_samples.jsonl   # expected exit 1
fin-qa-eval grade --pred examples/predictions.jsonl --format json
fin-qa-eval failures --pred examples/predictions.jsonl
fin-qa-eval failures --pred examples/predictions.jsonl --error convention_mismatch
fin-qa-eval compare --pred-a examples/predictions.jsonl --pred-b examples/predictions.jsonl
```

`data/fixtures/bad_samples.jsonl` plants duplicate ids, duplicate questions, a missing field, an evidence span that is not in the snippet, a 亿元 figure stored as 万元, an unanswerable row that still has a number, a distractor equal to the gold value, and a row with `synthetic: false`.

## Architecture

```
data/schema/eval_item.schema.json     task schema
data/schema/field_conventions.yaml    口径, units, YoY rules
data/samples/eval_set.jsonl           38 synthetic items
data/fixtures/bad_samples.jsonl       QC must fail
data/materialize.py                   readable catalog; regenerates the JSONL
examples/predictions.jsonl            fixture-extractor-v1
examples/scoreboard.md                attribution report
src/fin_qa_eval/
  units.py      parse 亿元/万元/% ; normalize; label scale and sign errors
  schema.py     JSON Schema + conventions YAML
  qc.py         duplicates, missing fields, evidence, unit anomalies
  graders.py    numeric_accuracy, evidence_consistency, refusal_appropriateness; 口径 and unit rollups
  report.py     company / period / metric / 口径 / unit / error tables + data & prompt checklist
  failures.py   items that missed full credit, with gold and predicted values
  compare.py    score deltas and primary-error changes between two prediction files
  stats.py      gold-set coverage: companies, 口径, refusal boundaries
  list_items.py gold-set item inventory: id, 口径, answerable/refusal
  list_distractors.py gold-set 口径 trap inventory: reason, value, unit, span
  list_predictions.py prediction coverage: in-gold, unknown, duplicate, refusal
  cli.py        validate, qc, grade, report, failures, compare, stats, list-items, list-distractors, list-predictions
```

The report’s checklist is driven by the error tags actually present, split into data fixes and prompt fixes. It is a short list, not a second model.

## Tests

GitHub Actions runs pytest on Python 3.10, 3.11, and 3.12, then `validate`, `qc`, `stats`, `grade`, `failures`, and `list-predictions`, and asserts that the bad fixture still fails QC. Nothing in CI needs a key.

```bash
pytest
```

## Layout for contributors

Add items in `data/materialize.py`, run `python3 data/materialize.py`, and keep `pytest` green. Rules and the synthetic-data policy are in [CONTRIBUTING.md](CONTRIBUTING.md). A course lab that walks through QC, the scoreboard, and a three-row rescore is in [docs/lab-zh.md](docs/lab-zh.md).

## License

MIT. The dataset is original synthetic text written for this repository.
