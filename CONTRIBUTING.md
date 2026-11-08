# Contributing

Thanks for improving fin-qa-eval. The bar is small: synthetic data, a schema that makes 口径 explicit, and graders that stay deterministic.

## Setup

```bash
python -m pip install -e ".[dev]"
pytest
fin-qa-eval validate && fin-qa-eval qc
```

## Add an eval item

1. Edit the catalog in `data/materialize.py`. Companies and numbers must be invented. Start the snippet with `【虚构示例，非真实披露】` and keep `synthetic: true`.
2. Regenerate the JSONL files:

```bash
python data/materialize.py
```

3. `fin-qa-eval qc` must pass. Evidence spans are exact substrings. A YoY that you compute must use current-then-prior order and half-up rounding to 0.01 percentage point. If the comparison base is not positive, mark the item unanswerable with `convention_conflict` instead of inventing a ratio.
4. If you want the fixture scoreboard to stay a demo of the traps, add a row to `build_predictions`. Otherwise give the fixture a correct answer.
5. Run `pytest`. Update the scoreboard numbers in `README.md`, `README.zh-CN.md`, and `examples/scoreboard.md` when the fixture scores change. Commit the JSONL files together with the catalog.

## Do not

- Paste real filings, news articles, or database extracts.
- Add a network call to the grader. Grading stays offline.
- Weaken QC to hide a bad row. Fix the row or label the boundary case properly.

## Pull requests

Describe which metric, 口径, or error type you touched. GitHub Actions runs pytest on Python 3.10–3.12 and checks that `data/fixtures/bad_samples.jsonl` still fails QC.
