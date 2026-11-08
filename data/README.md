# Data

Everything in this directory is **synthetic demo data**. Company names, tickers, and figures were invented for this toolkit. Snippets are marked `【虚构示例，非真实披露】` and every row sets `"synthetic": true`.

Do not replace these rows with text copied from real annual reports, exchange filings, or paid databases.

| Path | Role |
| --- | --- |
| `schema/eval_item.schema.json` | JSON Schema for one eval item |
| `schema/field_conventions.yaml` | 口径: scope, basis, profit view, tax, units, YoY rounding |
| `samples/eval_set.jsonl` | Graded eval set (one JSON object per line) |
| `fixtures/bad_samples.jsonl` | Planted defects. `fin-qa-eval qc` must fail here |
| `materialize.py` | Readable catalog that regenerates the JSONL files |

`examples/predictions.jsonl` is a deterministic fake extractor (`fixture-extractor-v1`) used to show a stable scoreboard. It is not a model output from an API.
