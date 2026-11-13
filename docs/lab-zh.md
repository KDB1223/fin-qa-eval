# 实验：财务报告问答的口径、证据与拒答

本实验用 **fin-qa-eval** 做一次离线评测。数据全部是虚构示例，公司名和数字都不能当成真实披露。实验不需要 API key，评分在本机完成，重复运行结果相同。

## 你要带走的三件事

1. 财务抽取题先写清 **口径**：合并还是母公司、GAAP 还是扣非、不含税还是含税、归母净利润还是别的利润。
2. 数值对不对，要在 **单位换算之后** 再比；证据必须是原文里的连续片段。
3. 片段里没有这个口径、期间或单位时，正确行为是 **拒答**，不是找一个邻近数字填上。

## 背景

同一段季报里经常并排出现：

- 合并营业收入 128.6 亿元，母公司营业收入 86.2 亿元
- 不含税营业收入 92.4 亿元，含税销售额 104.4 亿元
- 18,950 百万元，题目却要亿元
- 经营现金流 −3.8 亿元
- “净利润 7.6”，但单位在没附上的附注里

模型如果只抓“最大的那个数”或“第一个数”，分数会掉在固定的错误类型上：`convention_mismatch`、`unit_scale_error`、`sign_error`、`under_refusal`。这个工具把这些类型分开记，方便改数据，也方便改提示词。

## 环境

在仓库根目录。若 `fin-qa-eval` 不在 `PATH` 上，把下面的命令换成 `python3 -m fin_qa_eval`。

```bash
python3 -m pip install -e ".[dev]"
fin-qa-eval validate
fin-qa-eval qc
fin-qa-eval grade --pred examples/predictions.jsonl
fin-qa-eval report --pred examples/predictions.jsonl --out examples/scoreboard.md
```

`validate` 只看 JSON Schema。`qc` 额外检查重复、证据是否真的在片段里、单位是否把“18.3亿元”标成了“18.3万元”。`data/fixtures/bad_samples.jsonl` 是故意写坏的，`qc` 应该以退出码 1 结束。

## 任务 A — 读一条样本

打开 `data/samples/eval_set.jsonl`，找到 `xlkj-2024q3-revenue`。对照着写：

| 字段 | 这条样本里是什么 |
| --- | --- |
| 期间 `report_period` |  |
| 指标 `metric` |  |
| 口径 `convention` |  |
| 单位 `unit` |  |
| 证据 `evidence_span` |  |
| 干扰项 `distractors` |  |
| 参考答案 |  |

再打开 `data/schema/field_conventions.yaml`，用自己的话解释 `scope`、`basis`、`profit_view`、`tax` 各管什么。

## 任务 B — 看质检在抓什么

```bash
fin-qa-eval qc --data data/fixtures/bad_samples.jsonl
```

为下面每个代码写一句“它在防止什么”：

- `duplicate_id` / `duplicate_question`
- `evidence_not_in_source`
- `unit_anomaly`
- `unanswerable_has_value`
- `distractor_equals_gold`
- `not_synthetic`

通过标准：能指出对应的那一行 id，而不是只复述报错英文。

## 任务 C — 读错误归因

`examples/predictions.jsonl` 是一个写死的提取器 `fixture-extractor-v1`，不是在线模型。打开 `examples/scoreboard.md`（没有就用任务开头的命令生成），回答：

1. 三个维度里，哪一个最低？
2. `星澜科技` 和 `澄海乳业` 的主错误为什么是口径，而不是普通算错？
3. `赤川半导体` 的收入题为什么是 `unit_scale_error`？1 亿元等于多少百万元？
4. `青禾新能源` 的经营现金流为什么是 `sign_error`，而它的同比百分比题却应该拒答？
5. `白露食品` 的净利润题模型拒答了。这是 `over_refusal` 还是 `under_refusal`？
6. `岚桥物流` 有两道应该拒答的题被填了数字。证据维度为什么拿不到分？

## 任务 D — 自己改三道预测

复制 `examples/predictions.jsonl` 为 `examples/my_predictions.jsonl`，只改下面三行，其余保持不动：

1. `xlkj-2024q3-revenue`：改成合并口径 128.6 亿元，证据用原文里的那一句。
2. `bcyy-2024fy-revenue-wanyuan`：把 356.2 亿元换算成万元。
3. `lqwl-2025q1-ocf`：改为拒答，不要编造现金流。

然后：

```bash
fin-qa-eval grade --pred examples/my_predictions.jsonl
fin-qa-eval report --pred examples/my_predictions.jsonl --out examples/my_report.md
fin-qa-eval compare --pred-a examples/predictions.jsonl --pred-b examples/my_predictions.jsonl
```

写出改分前后的综合分。综合分应高于 fixture 的 0.8421。`compare` 会列出提升和退步的题目，不用对照两次 grade 或 report。说明你没有靠修改金标来提分。

## 任务 E — 写一段提示词

针对你在任务 C 里看到的错误，写不超过 150 字的中文提示词，必须包含：

- 先声明口径（合并/母公司、不含税、归母或扣非）
- 答案单位与换算
- 证据逐字复制
- 什么情况下拒答（未披露、单位不明、期间超出片段、同比基数不为正）

把这段提示词和 `examples/my_report.md` 里的改进清单对照，标出清单里你已经覆盖和还没覆盖的条目。

## 实验报告建议结构

1. 口径四元组各举一个本数据集中的例子
2. 质检失败代码与对应 id
3. fixture 三维分数和两道错例
4. 你修改后的分数
5. 提示词全文
6. 一句诚信声明：本实验数字均为虚构

## 思考题

1. 如果综合分把拒答维度拿掉，只平均数值和证据，`blsp-2024fy-net-profit` 的过度拒答还会被看见吗？
2. 证据用“包含数字”而不要求对齐金标跨度，含税销售额那道题会怎样被放过？
3. 为什么比较期现金流为 −1.2 亿元时，本项目不计算同比百分比？
4. 把真实年报贴进 `source_text` 会同时违反哪两条项目约定？

## 参考命令

```bash
fin-qa-eval validate --format json
fin-qa-eval qc --format json
fin-qa-eval grade --pred examples/predictions.jsonl --format json
```

评分只读本地 JSONL。不要把金标答案写进提示词再拿去测同一套题，那不是这个实验要测的能力。
