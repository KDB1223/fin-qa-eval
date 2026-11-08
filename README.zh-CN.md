# fin-qa-eval

[![CI](https://github.com/KDB1223/fin-qa-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/KDB1223/fin-qa-eval/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**面向中文财务报告问答的离线评测集和打分器。** 三个维度：数值准确、证据一致、拒答合理。口径（合并/母公司、GAAP/扣非、含税/不含税、归母净利润）写在字段里，混用会被单独记成 `convention_mismatch`，而不是含糊的“算错了”。

不需要 API key。同一份预测文件，分数永远一样。

English: [README.md](README.md) · 课程实验：[docs/lab-zh.md](docs/lab-zh.md)

> **虚构示例数据。** 公司、代码和数字都是编的。每段原文以 `【虚构示例，非真实披露】` 开头，每条样本 `"synthetic": true`。这里没有真实年报摘录。

## 一分钟跑通

在仓库根目录：

```bash
python3 -m pip install -e ".[dev]"
python3 -m fin_qa_eval validate
python3 -m fin_qa_eval qc
python3 -m fin_qa_eval grade --pred examples/predictions.jsonl
python3 -m fin_qa_eval report --pred examples/predictions.jsonl --out examples/scoreboard.md
```

安装进 `PATH` 之后，命令就是 `fin-qa-eval`。`examples/quickstart.sh` 会再确认坏样本的退出码是 1。

| 命令 | 做什么 |
| --- | --- |
| `validate` | 只做 JSON Schema |
| `qc` | 再加上重复题、缺字段、证据不在原文、单位把亿元标成万元 |
| `grade` | 对预测 JSONL 打三维分 |
| `report` | 按公司 / 报告期 / 指标 / 错误类型写 Markdown，并给数据和提示词清单 |

## 示例记分板

`examples/predictions.jsonl` 是写死的 **fixture-extractor-v1**，用来展示陷阱，不是某个在线模型的输出。完整报告在 [examples/scoreboard.md](examples/scoreboard.md)。

| 维度 | 得分 |
| --- | ---: |
| 数值准确 | 0.7632 |
| 证据一致 | 0.8421 |
| 拒答合理 | 0.9211 |
| **综合** | **0.8421** |

38 题，28 题满分。综合分是三个维度的算术平均。

| 公司 | 题数 | 综合 | 主要错误 |
| --- | ---: | ---: | --- |
| 北辰医药 | 8 | 0.9167 | unit_scale_error |
| 岚桥物流 | 4 | 0.5000 | under_refusal |
| 星澜科技 | 6 | 0.8889 | convention_mismatch |
| 梧桐家居 | 2 | 0.8333 | evidence_not_in_source |
| 澄海乳业 | 4 | 0.8333 | convention_mismatch |
| 白露食品 | 5 | 0.8000 | over_refusal |
| 赤川半导体 | 3 | 0.8889 | unit_scale_error |
| 青禾新能源 | 6 | 0.9444 | sign_error |

| 错误类型 | 条数 | 在本数据集里的意思 |
| --- | ---: | --- |
| convention_mismatch | 2 | 答了另一种口径：母公司收入，或含税销售额 |
| unit_scale_error | 2 | 数字搬过去了，万/亿/百万没有换算 |
| under_refusal | 2 | 该拒答时编了一个数 |
| evidence_overclaim | 2 | 拒答题却拿片段里的字当证据 |
| sign_error | 1 | 经营现金流 −3.8 被答成 +3.8 |
| over_refusal | 1 | 0.82 亿元已经写明，却拒答 |
| numeric_mismatch | 1 | 同比 4.73% 被答成 4.50% |
| evidence_not_in_source | 1 | 数字对，证据不是原文子串 |

## 口径怎么写进数据

每道题的 `convention` 固定四件事：

| 字段 | 取值 | 不写清楚时会抓错的数 |
| --- | --- | --- |
| `scope` | 合并 `consolidated` / 母公司 `parent` | 128.6 亿元 vs 86.2 亿元 |
| `basis` | GAAP `gaap` / 扣非 `non_gaap` | 归母净利润 vs 扣非未披露 |
| `profit_view` | 归母 `attributable` / 净利润 `net` / 营业利润 `operating` | 利润口径 |
| `tax` | 不含税 `ex_tax` / 含税 `inc_tax` | 92.4 亿元 vs 104.4 亿元 |

邻近的错误数字放在 `distractors` 里，并标上原因（`parent_scope`、`tax_inclusive`、`overseas_only`、`prior_period` 等）。预测值在单位换算后贴上干扰项，就记 `convention_mismatch`。字段说明见 [`data/schema/field_conventions.yaml`](data/schema/field_conventions.yaml)。

同比是百分数本身：`+14.41` 表示增长 14.41%，不是 0.1441。四舍五入（half-up）到 0.01 个百分点。证据里先写本期、再写比较期。比较期小于等于 0 时，本项目不计算百分比，样本标成拒答，原因是 `convention_conflict`。

金额先换到元再比较，相对误差 0.1% 或绝对误差 1 元以内算对。同比绝对误差 0.05 个百分点以内算对。差 10、100、1千、1万、1百万、1亿倍，记 `unit_scale_error`。

## 一条样本长什么样

```json
{
  "id": "xlkj-2024q3-revenue",
  "company": "星澜科技",
  "report_period": "2024Q3",
  "metric": "revenue",
  "convention": {"scope": "consolidated", "basis": "gaap", "profit_view": null, "tax": "ex_tax"},
  "unit": "CNY_hundred_million",
  "question": "按合并口径、不含税，星澜科技2024年第三季度营业收入是多少？",
  "evidence_span": "公司合并口径实现营业收入128.6亿元",
  "reference": {"answerable": true, "value": 128.6, "unit": "CNY_hundred_million", "display": "128.6亿元", "refusal_reason": null},
  "synthetic": true
}
```

评测集 38 题，覆盖营业收入、净利润、经营现金流以及同比，并包含单位换算和拒答边界：证据不足、单位不明、口径冲突、期间超出片段。Schema 在 [`data/schema/eval_item.schema.json`](data/schema/eval_item.schema.json)。

预测文件同样是 JSONL。给了 `value` 和 `unit` 就用它们；否则从 `answer` 里解析第一个带单位的数字。拒答可以设 `refused: true`，或在答案里写「拒答 / 未披露 / 证据不足」。证据必须是 `source_text` 的连续片段。

```json
{"id": "xlkj-2024q3-revenue", "answer": "128.6亿元", "value": 128.6, "unit": "CNY_hundred_million", "evidence": "公司合并口径实现营业收入128.6亿元", "refused": false}
```

## 质检会拦住什么

`data/fixtures/bad_samples.jsonl` 是故意写坏的，`qc` 必须失败（退出码 1）。里面有：

- 重复 `id`、重复问法
- 缺 `question`
- 证据不在原文里
- 证据写「18.3亿元」，参考答案却标成 18.3 万元
- 拒答题还填着数值、没有拒答原因
- 干扰项和金标一样，陷阱失效
- `synthetic` 不是 `true`
- 未知指标 `ebitda`

正式评测集 `data/samples/eval_set.jsonl` 上，`validate` 和 `qc` 都应该通过。

## 代码地图

```
data/schema/          JSON Schema 与口径说明
data/samples/         38 条虚构评测题
data/fixtures/        质检必须失败的坏样本
data/materialize.py   可读的数据源，用来重新生成 JSONL
examples/             fixture 预测与评分报告
src/fin_qa_eval/
  units.py            解析亿元、万元、百分比，换算并标记数量级/符号错误
  schema.py           读 Schema
  qc.py               重复、缺失、证据、单位异常
  graders.py          三个评分维度
  report.py           归因表和改进清单
  cli.py              validate / qc / grade / report
```

报告末尾的改进清单按本次出现的错误类型生成，分成「数据」和「提示词」两节。例如单位错误会要求提示词写出「1亿元 = 10,000万元 = 100百万元」。

## 测试

GitHub Actions 在 Python 3.10、3.11、3.12 上跑 `pytest`，再跑 `validate`、`qc`、`grade`，并检查坏样本的退出码是 1。CI 不需要密钥。

```bash
pytest
```

新增题目改 `data/materialize.py`，然后 `python3 data/materialize.py`。约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。想把这套题当一次实验课，看 [docs/lab-zh.md](docs/lab-zh.md)。

## 许可

MIT。数据集是为本仓库写的虚构文本。
