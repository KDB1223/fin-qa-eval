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

`validate` checks the JSON Schema. `qc` adds duplicate detection, evidence containment, and unit anomalies. `grade` / `report` score a prediction JSONL. Grading does not call a model.

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

```bash
fin-qa-eval qc --data data/fixtures/bad_samples.jsonl   # expected exit 1
fin-qa-eval grade --pred examples/predictions.jsonl --format json
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
  graders.py    numeric_accuracy, evidence_consistency, refusal_appropriateness
  report.py     company / period / metric / error tables + data & prompt checklist
  cli.py        validate, qc, grade, report
```

The report’s checklist is driven by the error tags actually present, split into data fixes and prompt fixes. It is a short list, not a second model.

## Tests

GitHub Actions runs pytest on Python 3.10, 3.11, and 3.12, then `validate`, `qc`, `grade`, and asserts that the bad fixture still fails QC. Nothing in CI needs a key.

```bash
pytest
```

## Layout for contributors

Add items in `data/materialize.py`, run `python3 data/materialize.py`, and keep `pytest` green. Rules and the synthetic-data policy are in [CONTRIBUTING.md](CONTRIBUTING.md). A course lab that walks through QC, the scoreboard, and a three-row rescore is in [docs/lab-zh.md](docs/lab-zh.md).

## License

MIT. The dataset is original synthetic text written for this repository.
