# Examples

`predictions.jsonl` is the offline fixture model **fixture-extractor-v1**. It answers most of the synthetic items correctly and misses the traps on purpose:

| Item | What the fixture does |
| --- | --- |
| `xlkj-2024q3-revenue` | Answers the parent-company figure (口径 / scope) |
| `chry-2024h1-revenue` | Answers tax-inclusive sales instead of ex-tax revenue |
| `bcyy-2024fy-revenue-wanyuan` | Copies 356.2 into 万元 and drops the 亿→万 factor |
| `ccsc-2024q3-revenue` | Treats 18,950 百万元 as 18,950 亿元 |
| `qhne-2024fy-ocf` | Drops the minus sign on operating cash flow |
| `bcyy-2024fy-revenue-yoy` | Reports 4.50% instead of 4.73% |
| `wtjj-2023fy-revenue` | Right number, evidence string that is not in the snippet |
| `blsp-2024fy-net-profit` | Refuses a small but disclosed profit |
| `lqwl-2025q1-ocf` | Invents a cash-flow number that was not disclosed |
| `lqwl-2025q1-unit-ambiguous` | Assumes the unitless 7.6 is 亿元 |

Regenerate the scoreboard from the repo root:

```bash
fin-qa-eval grade --pred examples/predictions.jsonl
fin-qa-eval report --pred examples/predictions.jsonl --out examples/scoreboard.md
fin-qa-eval compare --pred-a examples/predictions.jsonl --pred-b examples/predictions.jsonl
```

`compare` reports score deltas and primary-error changes. The command above compares the fixture to itself, so the deltas are zero.

`quickstart.sh` installs the package and runs validate, qc, grade, and report.
