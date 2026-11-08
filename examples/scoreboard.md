# fin-qa-eval 评分报告 / Grade report

> Synthetic demo data only. Scores are computed offline and do not call a model API.
> 数据为虚构示例。评分在本地完成，不调用模型 API。

- Gold: `data/samples/eval_set.jsonl`
- Predictions: `examples/predictions.jsonl`
- Items: 38
- Full credit: 28 / 38

## 总表 / Scoreboard

| 维度 Dimension | 得分 Score |
| --- | ---: |
| 数值准确 numeric_accuracy | 0.7632 |
| 证据一致 evidence_consistency | 0.8421 |
| 拒答合理 refusal_appropriateness | 0.9211 |
| **综合 overall** | **0.8421** |

## 按公司 / By company

| 分组 Group | n | 综合 overall | 数值 | 证据 | 拒答 | 满分 | 主要错误 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 北辰医药 | 8 | 0.9167 | 0.7500 | 1.0000 | 1.0000 | 6 | unit_scale_error |
| 岚桥物流 | 4 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 2 | under_refusal |
| 星澜科技 | 6 | 0.8889 | 0.8333 | 0.8333 | 1.0000 | 5 | convention_mismatch |
| 梧桐家居 | 2 | 0.8333 | 1.0000 | 0.5000 | 1.0000 | 1 | evidence_not_in_source |
| 澄海乳业 | 4 | 0.8333 | 0.7500 | 0.7500 | 1.0000 | 3 | convention_mismatch |
| 白露食品 | 5 | 0.8000 | 0.8000 | 0.8000 | 0.8000 | 4 | over_refusal |
| 赤川半导体 | 3 | 0.8889 | 0.6667 | 1.0000 | 1.0000 | 2 | unit_scale_error |
| 青禾新能源 | 6 | 0.9444 | 0.8333 | 1.0000 | 1.0000 | 5 | sign_error |

## 按报告期 / By report period

| 分组 Group | n | 综合 overall | 数值 | 证据 | 拒答 | 满分 | 主要错误 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2023FY | 2 | 0.8333 | 1.0000 | 0.5000 | 1.0000 | 1 | evidence_not_in_source |
| 2024FY | 19 | 0.8947 | 0.7895 | 0.9474 | 0.9474 | 15 | over_refusal |
| 2024H1 | 4 | 0.8333 | 0.7500 | 0.7500 | 1.0000 | 3 | convention_mismatch |
| 2024Q3 | 9 | 0.8889 | 0.7778 | 0.8889 | 1.0000 | 7 | convention_mismatch |
| 2025Q1 | 4 | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 2 | under_refusal |

## 按指标 / By metric

| 分组 Group | n | 综合 overall | 数值 | 证据 | 拒答 | 满分 | 主要错误 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| net_profit | 11 | 0.8182 | 0.8182 | 0.8182 | 0.8182 | 9 | under_refusal |
| net_profit_yoy | 3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 3 | — |
| operating_cashflow | 6 | 0.7778 | 0.6667 | 0.8333 | 0.8333 | 4 | under_refusal |
| operating_cashflow_yoy | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 2 | — |
| revenue | 11 | 0.7879 | 0.6364 | 0.7273 | 1.0000 | 6 | convention_mismatch |
| revenue_yoy | 5 | 0.9333 | 0.8000 | 1.0000 | 1.0000 | 4 | numeric_mismatch |

## 按错误类型 / By error type

一条样本可以带多个错误标签。分数只由三个维度决定，错误标签用于归因。
An item may carry more than one error tag. Scores come only from the three dimensions.

| 错误类型 Error | 条数 Count |
| --- | ---: |
| convention_mismatch | 2 |
| evidence_overclaim | 2 |
| under_refusal | 2 |
| unit_scale_error | 2 |
| evidence_not_in_source | 1 |
| numeric_mismatch | 1 |
| over_refusal | 1 |
| sign_error | 1 |

## 错例 / Failures

| id | 公司 | 期间 | 指标 | 综合 | 主错误 | 全部错误 |
| --- | --- | --- | --- | ---: | --- | --- |
| blsp-2024fy-net-profit | 白露食品 | 2024FY | net_profit | 0.0000 | over_refusal | over_refusal |
| lqwl-2025q1-ocf | 岚桥物流 | 2025Q1 | operating_cashflow | 0.0000 | under_refusal | under_refusal, evidence_overclaim |
| lqwl-2025q1-unit-ambiguous | 岚桥物流 | 2025Q1 | net_profit | 0.0000 | under_refusal | under_refusal, evidence_overclaim |
| chry-2024h1-revenue | 澄海乳业 | 2024H1 | revenue | 0.3333 | convention_mismatch | convention_mismatch |
| xlkj-2024q3-revenue | 星澜科技 | 2024Q3 | revenue | 0.3333 | convention_mismatch | convention_mismatch |
| bcyy-2024fy-revenue-wanyuan | 北辰医药 | 2024FY | revenue | 0.6667 | unit_scale_error | unit_scale_error |
| bcyy-2024fy-revenue-yoy | 北辰医药 | 2024FY | revenue_yoy | 0.6667 | numeric_mismatch | numeric_mismatch |
| ccsc-2024q3-revenue | 赤川半导体 | 2024Q3 | revenue | 0.6667 | unit_scale_error | unit_scale_error |
| qhne-2024fy-ocf | 青禾新能源 | 2024FY | operating_cashflow | 0.6667 | sign_error | sign_error |
| wtjj-2023fy-revenue | 梧桐家居 | 2023FY | revenue | 0.6667 | evidence_not_in_source | evidence_not_in_source |

## 改进清单 / Improvement checklist

### 数据 Data

- 全部样本保持 `synthetic: true`，公司与数字均为虚构，不写入真实披露原文。 / Keep every row synthetic. Do not paste proprietary filings.
- 新增题目前先跑 `fin-qa-eval qc`，确认没有重复题、单位异常和证据落空。 / Run `fin-qa-eval qc` before adding rows.
- (convention_mismatch) 在金标证据旁保留对照干扰项：合并/母公司、含税/不含税、归母/扣非。 / Keep contrastive distractors beside the gold span (scope, tax, attributable vs. deducted).
- (evidence_overclaim) 拒答题写清缺失的是期间、口径还是单位，方便对照 refusal_reason。 / State whether a refusal case lacks the period, the 口径, or the unit.
- (under_refusal) 保留证据不足、越界期间、单位不明、负基数同比这几类边界。 / Keep insufficient-evidence, out-of-period, ambiguous-unit, and negative-base YoY boundaries.
- (unit_scale_error) 为同一事实保留万元与亿元两种表述，并在参考答案里写好换算后的值。 / Keep the same fact in 万元 and 亿元, with the reference already converted.
- (evidence_not_in_source) 证据跨度必须是 source_text 的连续子串，QC 会拦截写不回去的 span。 / Evidence spans must be exact substrings; QC rejects spans that cannot be copied back.
- (numeric_mismatch) 同比题写明比较期在前还是本期在前；需要计算的题标注 requires_calculation。 / State which amount is current vs. prior, and tag rows that require a calculation.
- (over_refusal) 可答题的片段里金标数字必须出现，避免模型被训练成一律拒答。 / The gold number must actually appear, so models are not pushed to refuse everything.
- (sign_error) 保留现金流为负、利润同比为负的样本，避免数据集只有正数。 / Keep negative cash flow and negative YoY rows so the set is not all positive.

### 提示词 Prompts

- 输出里同时给出 value、unit、evidence；拒答时给出原因，不要只写「不知道」。 / Emit value, unit, and evidence. A refusal needs a reason, not a bare shrug.
- (convention_mismatch) 作答前绑定口径：scope、basis、profit_view。片段只有另一种口径时拒答，不要改用相邻数字。 / Bind scope, basis, and profit view. If the snippet only has another 口径, refuse.
- (evidence_overclaim) 证据不够时输出拒答及原因，不要用片段里的其他数字填空。 / When evidence is insufficient, refuse with a reason. Do not fill the blank with a nearby number.
- (under_refusal) 若题目要求的口径在片段中不存在，拒答并给出 refusal_reason，不要编造数值。 / If the requested 口径 is absent, refuse with a reason. Do not invent a figure.
- (unit_scale_error) 先抄写题目要求的单位，再写出换算因子（1亿元 = 10,000万元 = 100百万元）后作答。 / Restate the unit the question asks for, then show the conversion factor before the number.
- (evidence_not_in_source) 证据必须从片段逐字复制，不要改写数字或单位。 / Copy the evidence span verbatim from the snippet. Do not paraphrase the number.
- (numeric_mismatch) 同比百分比 = (本期 − 比较期) / 比较期，四舍五入到 0.01 个百分点。基数≤0 时按口径拒答。 / YoY = (current − prior) / prior, half-up to 0.01pp. Refuse when the base is not positive.
- (over_refusal) 只有在期间、口径或单位无法唯一确定时才拒答。 / Refuse only when the period, 口径, or unit cannot be uniquely determined.
- (sign_error) 保留原文中的负号、下降、亏损；净额为负时不要取绝对值。 / Keep minus signs and words such as 下降 or 亏损. Do not abs() a net outflow.
