"""Build the committed JSONL files from the synthetic catalog.

The JSONL files are the dataset. This script is the readable source for the
invented snippets, and a test checks that re-running it does not change the
files. Companies, tickers, and figures are fictional.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fin_qa_eval.units import infer_yoy_percent, is_money, parse_amounts
GOLD_PATH = ROOT / "data" / "samples" / "eval_set.jsonl"
BAD_PATH = ROOT / "data" / "fixtures" / "bad_samples.jsonl"
PRED_PATH = ROOT / "examples" / "predictions.jsonl"

YI = "CNY_hundred_million"
WAN = "CNY_ten_thousand"
PERCENT = "percent"

XLKJ = (
    "【虚构示例，非真实披露】星澜科技股份有限公司2024年第三季度报告节选："
    "报告期内，公司合并口径实现营业收入128.6亿元，上年同期112.4亿元；"
    "归属于上市公司股东的净利润18.3亿元，上年同期16.0亿元。"
    "经营活动产生的现金流量净额22.7亿元，上年同期19.5亿元。"
    "母公司营业收入86.2亿元。"
    "扣除非经常性损益后的净利润本期未披露。"
)
BCYY = (
    "【虚构示例，非真实披露】北辰医药股份有限公司2024年年度报告节选："
    "2024年公司合并营业收入356.2亿元，上年同期340.1亿元，同比增长4.73%；"
    "归属于上市公司股东的净利润41.8亿元，上年同期48.6亿元，同比下降13.99%；"
    "经营活动产生的现金流量净额53.0亿元，上年同期49.2亿元。"
    "母公司营业收入210.4亿元。母公司净利润未在本片段披露。"
)
CHRY = (
    "【虚构示例，非真实披露】澄海乳业股份有限公司2024年半年度报告节选："
    "2024年上半年，公司实现不含税营业收入92.4亿元，上年同期88.0亿元，同比增长5.00%；"
    "含税销售额104.4亿元。"
    "归属于上市公司股东的净利润6.15亿元。"
    "经营活动产生的现金流量净额8.40亿元。"
)
QHNE = (
    "【虚构示例，非真实披露】青禾新能源股份有限公司2024年年度报告节选："
    "合并营业收入210.0亿元，上年同期150.0亿元，同比增长40.00%；"
    "归属于上市公司股东的净利润12.6亿元，上年同期15.0亿元，同比下降16.00%。"
    "经营活动产生的现金流量净额为-3.8亿元，上年同期为-1.2亿元。"
    "公司披露口径注明：比较期基数为负时，不计算同比百分比。"
)
WTJJ = (
    "【虚构示例，非真实披露】梧桐家居股份有限公司2023年年度报告节选："
    "全年实现合并营业收入67.8亿元，其中境外收入12.1亿元；"
    "归属于上市公司股东的净利润4.2亿元。"
)
CCSC = (
    "【虚构示例，非真实披露】赤川半导体股份有限公司2024年第三季度报告节选："
    "合并营业收入18,950百万元；归属于上市公司股东的净利润2,130百万元；"
    "经营活动产生的现金流量净额2,560百万元。"
    "Chichuan Semiconductor (fictional) 2024 Q3: consolidated revenue RMB 18,950 million; "
    "net profit attributable to shareholders RMB 2,130 million; "
    "net cash from operating activities RMB 2,560 million."
)
BLSP = (
    "【虚构示例，非真实披露】白露食品股份有限公司2024年年度报告节选："
    "合并营业收入30.25亿元，上年同期29.80亿元；"
    "归属于上市公司股东的净利润0.82亿元，上年同期1.20亿元。"
    "上述净利润按亿元列示，折合8,200万元。"
)
LQWL = (
    "【虚构示例，非真实披露】岚桥物流股份有限公司2025年第一季度报告节选："
    "2025年1-3月合并营业收入45.3亿元。"
    "经营活动现金流量净额本片段未披露。"
    "全年数据尚未报告。"
    "另有附注残句：净利润7.6（单位见合并报表附注；本片段未给出元、万元或亿元）。"
)


def conv(scope: str = "consolidated", basis: str = "gaap", profit_view: Optional[str] = None, tax: Optional[str] = None) -> dict[str, Any]:
    return {"scope": scope, "basis": basis, "profit_view": profit_view, "tax": tax}


def answered(value: float, unit: str, display: str) -> dict[str, Any]:
    return {
        "answerable": True,
        "value": value,
        "unit": unit,
        "display": display,
        "refusal_reason": None,
    }


def refused(reason: str, display: str) -> dict[str, Any]:
    return {
        "answerable": False,
        "value": None,
        "unit": None,
        "display": display,
        "refusal_reason": reason,
    }


def yoy_reference(span: str) -> dict[str, Any]:
    money = [amount for amount in parse_amounts(span) if is_money(amount.unit)]
    if len(money) < 2:
        raise RuntimeError(f"need two money amounts to derive YoY: {span}")
    derived = infer_yoy_percent(money[0], money[1])
    if derived is None:
        raise RuntimeError(f"YoY undefined for span: {span}")
    return answered(_json_number(derived), PERCENT, f"同比{derived:+.2f}%")


def _json_number(value: Decimal) -> float | int:
    if value == value.to_integral():
        return int(value)
    return float(value)


def item(
    *,
    id: str,
    company: str,
    ticker: str,
    report_period: str,
    metric: str,
    unit: str,
    question: str,
    source_id: str,
    source_text: str,
    evidence_span: str,
    reference: dict[str, Any],
    convention: dict[str, Any],
    tags: list[str],
    notes: str,
    language: str = "zh",
    requires_calculation: bool = False,
    distractors: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    if evidence_span and evidence_span not in source_text:
        raise RuntimeError(f"{id}: evidence is not an exact substring")
    for distractor in distractors or []:
        if distractor["span"] not in source_text:
            raise RuntimeError(f"{id}: distractor not in source: {distractor['span']}")
    row: dict[str, Any] = {
        "id": id,
        "company": company,
        "ticker": ticker,
        "report_period": report_period,
        "metric": metric,
        "convention": convention,
        "unit": unit,
        "question": question,
        "source_id": source_id,
        "source_text": source_text,
        "evidence_span": evidence_span,
        "reference": reference,
        "requires_calculation": requires_calculation,
        "synthetic": True,
        "language": language,
        "tags": tags,
        "notes": notes,
    }
    if distractors:
        row["distractors"] = distractors
    return row


def build_gold() -> list[dict[str, Any]]:
    xlkj_rev_yoy_span = "公司合并口径实现营业收入128.6亿元，上年同期112.4亿元"
    xlkj_ocf_yoy_span = "经营活动产生的现金流量净额22.7亿元，上年同期19.5亿元"
    blsp_rev_yoy_span = "合并营业收入30.25亿元，上年同期29.80亿元"
    blsp_np_yoy_span = "归属于上市公司股东的净利润0.82亿元，上年同期1.20亿元"
    return [
        item(
            id="xlkj-2024q3-revenue",
            company="星澜科技",
            ticker="XLKJ",
            report_period="2024Q3",
            metric="revenue",
            unit=YI,
            question="按合并口径、不含税，星澜科技2024年第三季度营业收入是多少？",
            source_id="src-xlkj-2024q3",
            source_text=XLKJ,
            evidence_span="公司合并口径实现营业收入128.6亿元",
            reference=answered(128.6, YI, "128.6亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core", "boundary:scope_distractor"],
            notes="母公司营业收入86.2亿元是合并口径的干扰项。",
            distractors=[
                {"span": "母公司营业收入86.2亿元", "reason": "parent_scope", "value": 86.2, "unit": YI}
            ],
        ),
        item(
            id="xlkj-2024q3-revenue-yoy",
            company="星澜科技",
            ticker="XLKJ",
            report_period="2024Q3",
            metric="revenue_yoy",
            unit=PERCENT,
            question="星澜科技2024年第三季度合并营业收入同比增速是多少？请按百分比作答。",
            source_id="src-xlkj-2024q3",
            source_text=XLKJ,
            evidence_span=xlkj_rev_yoy_span,
            reference=yoy_reference(xlkj_rev_yoy_span),
            convention=conv(tax="ex_tax"),
            tags=["calc:yoy"],
            requires_calculation=True,
            notes="片段未印出百分比，需按(本期-比较期)/比较期计算，四舍五入到0.01。",
            distractors=[
                {"span": "上年同期112.4亿元", "reason": "prior_period", "value": 112.4, "unit": YI}
            ],
        ),
        item(
            id="xlkj-2024q3-net-profit",
            company="星澜科技",
            ticker="XLKJ",
            report_period="2024Q3",
            metric="net_profit",
            unit=YI,
            question="星澜科技2024年第三季度归属于上市公司股东的净利润是多少？请使用合并GAAP口径，不要回答扣非。",
            source_id="src-xlkj-2024q3",
            source_text=XLKJ,
            evidence_span="归属于上市公司股东的净利润18.3亿元",
            reference=answered(18.3, YI, "18.3亿元"),
            convention=conv(profit_view="attributable"),
            tags=["core"],
            notes="利润口径是归母净利润，不是扣非。",
        ),
        item(
            id="xlkj-2024q3-ocf",
            company="星澜科技",
            ticker="XLKJ",
            report_period="2024Q3",
            metric="operating_cashflow",
            unit=YI,
            question="星澜科技2024年第三季度经营活动产生的现金流量净额是多少？",
            source_id="src-xlkj-2024q3",
            source_text=XLKJ,
            evidence_span="经营活动产生的现金流量净额22.7亿元",
            reference=answered(22.7, YI, "22.7亿元"),
            convention=conv(),
            tags=["core"],
            notes="经营现金流取净额。",
        ),
        item(
            id="xlkj-2024q3-ocf-yoy",
            company="星澜科技",
            ticker="XLKJ",
            report_period="2024Q3",
            metric="operating_cashflow_yoy",
            unit=PERCENT,
            question="星澜科技2024年第三季度经营活动现金流量净额同比增速是多少？",
            source_id="src-xlkj-2024q3",
            source_text=XLKJ,
            evidence_span=xlkj_ocf_yoy_span,
            reference=yoy_reference(xlkj_ocf_yoy_span),
            convention=conv(),
            tags=["calc:yoy"],
            requires_calculation=True,
            notes="由22.7与19.5计算，比较期为正。",
        ),
        item(
            id="xlkj-2024q3-deducted-np",
            company="星澜科技",
            ticker="XLKJ",
            report_period="2024Q3",
            metric="net_profit",
            unit=YI,
            question="星澜科技2024年第三季度扣除非经常性损益后的净利润是多少？若片段未披露请拒答。",
            source_id="src-xlkj-2024q3",
            source_text=XLKJ,
            evidence_span="扣除非经常性损益后的净利润本期未披露。",
            reference=refused("insufficient_evidence", "拒答：片段未披露扣除非经常性损益后的净利润"),
            convention=conv(basis="non_gaap", profit_view="attributable"),
            tags=["boundary:insufficient_evidence"],
            notes="归母净利润已披露，但扣非未披露。不能用18.3亿元代替。",
        ),
        item(
            id="bcyy-2024fy-revenue",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="revenue",
            unit=YI,
            question="北辰医药2024年合并营业收入是多少？",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="2024年公司合并营业收入356.2亿元",
            reference=answered(356.2, YI, "356.2亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core", "boundary:scope_distractor"],
            notes="合并数，不是母公司210.4亿元。",
            distractors=[
                {"span": "母公司营业收入210.4亿元", "reason": "parent_scope", "value": 210.4, "unit": YI}
            ],
        ),
        item(
            id="bcyy-2024fy-revenue-yoy",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="revenue_yoy",
            unit=PERCENT,
            question="北辰医药2024年合并营业收入同比增速是多少？",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="2024年公司合并营业收入356.2亿元，上年同期340.1亿元，同比增长4.73%",
            reference=answered(4.73, PERCENT, "同比+4.73%"),
            convention=conv(tax="ex_tax"),
            tags=["core"],
            notes="片段已印出同比增长4.73%。",
        ),
        item(
            id="bcyy-2024fy-net-profit",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="net_profit",
            unit=YI,
            question="北辰医药2024年归属于上市公司股东的净利润是多少？",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="归属于上市公司股东的净利润41.8亿元",
            reference=answered(41.8, YI, "41.8亿元"),
            convention=conv(profit_view="attributable"),
            tags=["core"],
            notes="归母净利润。",
        ),
        item(
            id="bcyy-2024fy-net-profit-yoy",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="net_profit_yoy",
            unit=PERCENT,
            question="北辰医药2024年归母净利润同比变动是多少？下降请记为负数。",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="归属于上市公司股东的净利润41.8亿元，上年同期48.6亿元，同比下降13.99%",
            reference=answered(-13.99, PERCENT, "同比-13.99%"),
            convention=conv(profit_view="attributable"),
            tags=["core", "boundary:negative_value"],
            notes="下降记负号，不是绝对值。",
        ),
        item(
            id="bcyy-2024fy-ocf",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="operating_cashflow",
            unit=YI,
            question="北辰医药2024年经营活动产生的现金流量净额是多少？",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="经营活动产生的现金流量净额53.0亿元",
            reference=answered(53.0, YI, "53.0亿元"),
            convention=conv(),
            tags=["core"],
            notes="经营现金流净额。",
        ),
        item(
            id="bcyy-2024fy-revenue-wanyuan",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="revenue",
            unit=WAN,
            question="北辰医药2024年合并营业收入折合多少万元？请换算后作答。",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="2024年公司合并营业收入356.2亿元",
            reference=answered(3562000, WAN, "3,562,000万元"),
            convention=conv(tax="ex_tax"),
            tags=["boundary:unit_conversion"],
            notes="356.2亿元 = 3,562,000万元。只把356.2抄成万元是单位错误。",
        ),
        item(
            id="bcyy-2024fy-parent-revenue",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="revenue",
            unit=YI,
            question="北辰医药2024年母公司营业收入是多少？不要回答合并营业收入。",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="母公司营业收入210.4亿元",
            reference=answered(210.4, YI, "210.4亿元"),
            convention=conv(scope="parent", tax="ex_tax"),
            tags=["boundary:scope_distractor"],
            notes="题目指定母公司口径。",
            distractors=[
                {
                    "span": "2024年公司合并营业收入356.2亿元",
                    "reason": "consolidated_scope",
                    "value": 356.2,
                    "unit": YI,
                }
            ],
        ),
        item(
            id="bcyy-2024fy-parent-np",
            company="北辰医药",
            ticker="BCYY",
            report_period="2024FY",
            metric="net_profit",
            unit=YI,
            question="北辰医药2024年母公司净利润是多少？若片段只给出母公司营业收入、未给出母公司净利润，请拒答。",
            source_id="src-bcyy-2024fy",
            source_text=BCYY,
            evidence_span="母公司净利润未在本片段披露。",
            reference=refused("insufficient_evidence", "拒答：片段未披露母公司净利润"),
            convention=conv(scope="parent", profit_view="attributable"),
            tags=["boundary:insufficient_evidence", "boundary:scope_distractor"],
            notes="不能用合并归母净利润41.8亿元填母公司净利润。",
        ),
        item(
            id="chry-2024h1-revenue",
            company="澄海乳业",
            ticker="CHRY",
            report_period="2024H1",
            metric="revenue",
            unit=YI,
            question="澄海乳业2024年上半年不含税营业收入是多少？不要使用含税销售额。",
            source_id="src-chry-2024h1",
            source_text=CHRY,
            evidence_span="公司实现不含税营业收入92.4亿元",
            reference=answered(92.4, YI, "92.4亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core", "boundary:tax_distractor"],
            notes="含税销售额104.4亿元不是营业收入。",
            distractors=[
                {"span": "含税销售额104.4亿元", "reason": "tax_inclusive", "value": 104.4, "unit": YI}
            ],
        ),
        item(
            id="chry-2024h1-revenue-yoy",
            company="澄海乳业",
            ticker="CHRY",
            report_period="2024H1",
            metric="revenue_yoy",
            unit=PERCENT,
            question="澄海乳业2024年上半年不含税营业收入同比增速是多少？",
            source_id="src-chry-2024h1",
            source_text=CHRY,
            evidence_span="公司实现不含税营业收入92.4亿元，上年同期88.0亿元，同比增长5.00%",
            reference=answered(5.0, PERCENT, "同比+5.00%"),
            convention=conv(tax="ex_tax"),
            tags=["core"],
            notes="(92.4-88.0)/88.0 = 5.00%，与印出的增速一致。",
        ),
        item(
            id="chry-2024h1-net-profit",
            company="澄海乳业",
            ticker="CHRY",
            report_period="2024H1",
            metric="net_profit",
            unit=YI,
            question="澄海乳业2024年上半年归属于上市公司股东的净利润是多少？",
            source_id="src-chry-2024h1",
            source_text=CHRY,
            evidence_span="归属于上市公司股东的净利润6.15亿元",
            reference=answered(6.15, YI, "6.15亿元"),
            convention=conv(profit_view="attributable"),
            tags=["core"],
            notes="归母净利润。",
        ),
        item(
            id="chry-2024h1-ocf",
            company="澄海乳业",
            ticker="CHRY",
            report_period="2024H1",
            metric="operating_cashflow",
            unit=YI,
            question="澄海乳业2024年上半年经营活动产生的现金流量净额是多少？",
            source_id="src-chry-2024h1",
            source_text=CHRY,
            evidence_span="经营活动产生的现金流量净额8.40亿元",
            reference=answered(8.4, YI, "8.40亿元"),
            convention=conv(),
            tags=["core"],
            notes="8.40亿元。",
        ),
        item(
            id="qhne-2024fy-revenue",
            company="青禾新能源",
            ticker="QHNE",
            report_period="2024FY",
            metric="revenue",
            unit=YI,
            question="青禾新能源2024年合并营业收入是多少？",
            source_id="src-qhne-2024fy",
            source_text=QHNE,
            evidence_span="合并营业收入210.0亿元",
            reference=answered(210.0, YI, "210.0亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core"],
            notes="合并营业收入。",
        ),
        item(
            id="qhne-2024fy-revenue-yoy",
            company="青禾新能源",
            ticker="QHNE",
            report_period="2024FY",
            metric="revenue_yoy",
            unit=PERCENT,
            question="青禾新能源2024年合并营业收入同比增速是多少？",
            source_id="src-qhne-2024fy",
            source_text=QHNE,
            evidence_span="合并营业收入210.0亿元，上年同期150.0亿元，同比增长40.00%",
            reference=answered(40.0, PERCENT, "同比+40.00%"),
            convention=conv(tax="ex_tax"),
            tags=["core"],
            notes="印出同比增长40.00%。",
        ),
        item(
            id="qhne-2024fy-net-profit",
            company="青禾新能源",
            ticker="QHNE",
            report_period="2024FY",
            metric="net_profit",
            unit=YI,
            question="青禾新能源2024年归属于上市公司股东的净利润是多少？",
            source_id="src-qhne-2024fy",
            source_text=QHNE,
            evidence_span="归属于上市公司股东的净利润12.6亿元",
            reference=answered(12.6, YI, "12.6亿元"),
            convention=conv(profit_view="attributable"),
            tags=["core"],
            notes="归母净利润。",
        ),
        item(
            id="qhne-2024fy-net-profit-yoy",
            company="青禾新能源",
            ticker="QHNE",
            report_period="2024FY",
            metric="net_profit_yoy",
            unit=PERCENT,
            question="青禾新能源2024年归母净利润同比变动是多少？下降请记为负数。",
            source_id="src-qhne-2024fy",
            source_text=QHNE,
            evidence_span="归属于上市公司股东的净利润12.6亿元，上年同期15.0亿元，同比下降16.00%",
            reference=answered(-16.0, PERCENT, "同比-16.00%"),
            convention=conv(profit_view="attributable"),
            tags=["core", "boundary:negative_value"],
            notes="同比下降16.00%，答案为-16.00。",
        ),
        item(
            id="qhne-2024fy-ocf",
            company="青禾新能源",
            ticker="QHNE",
            report_period="2024FY",
            metric="operating_cashflow",
            unit=YI,
            question="青禾新能源2024年经营活动产生的现金流量净额是多少？请保留正负号。",
            source_id="src-qhne-2024fy",
            source_text=QHNE,
            evidence_span="经营活动产生的现金流量净额为-3.8亿元",
            reference=answered(-3.8, YI, "-3.8亿元"),
            convention=conv(),
            tags=["boundary:negative_value"],
            notes="经营现金流为净流出，答案必须为负。",
        ),
        item(
            id="qhne-2024fy-ocf-yoy",
            company="青禾新能源",
            ticker="QHNE",
            report_period="2024FY",
            metric="operating_cashflow_yoy",
            unit=PERCENT,
            question="青禾新能源2024年经营活动现金流量净额的同比百分比是多少？若公司口径规定比较期基数为负时不计算百分比，请拒答。",
            source_id="src-qhne-2024fy",
            source_text=QHNE,
            evidence_span="经营活动产生的现金流量净额为-3.8亿元，上年同期为-1.2亿元。公司披露口径注明：比较期基数为负时，不计算同比百分比。",
            reference=refused("convention_conflict", "拒答：比较期基数为负，按披露口径不计算同比百分比"),
            convention=conv(),
            tags=["boundary:convention_conflict", "boundary:negative_value"],
            notes="比较期-1.2亿元，百分比同比在本项目口径下无定义。",
        ),
        item(
            id="wtjj-2023fy-revenue",
            company="梧桐家居",
            ticker="WTJJ",
            report_period="2023FY",
            metric="revenue",
            unit=YI,
            question="梧桐家居2023年合并营业收入是多少？请回答总额，不要只回答境外收入。",
            source_id="src-wtjj-2023fy",
            source_text=WTJJ,
            evidence_span="全年实现合并营业收入67.8亿元",
            reference=answered(67.8, YI, "67.8亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core", "boundary:scope_distractor"],
            notes="境外收入12.1亿元只是总额的一部分。",
            distractors=[
                {"span": "其中境外收入12.1亿元", "reason": "overseas_only", "value": 12.1, "unit": YI}
            ],
        ),
        item(
            id="wtjj-2023fy-net-profit",
            company="梧桐家居",
            ticker="WTJJ",
            report_period="2023FY",
            metric="net_profit",
            unit=YI,
            question="梧桐家居2023年归属于上市公司股东的净利润是多少？",
            source_id="src-wtjj-2023fy",
            source_text=WTJJ,
            evidence_span="归属于上市公司股东的净利润4.2亿元",
            reference=answered(4.2, YI, "4.2亿元"),
            convention=conv(profit_view="attributable"),
            tags=["core"],
            notes="归母净利润。",
        ),
        item(
            id="ccsc-2024q3-revenue",
            company="赤川半导体",
            ticker="CCSC",
            report_period="2024Q3",
            metric="revenue",
            unit=YI,
            question="What was Chichuan Semiconductor's consolidated revenue in 2024 Q3, in hundred million yuan (亿元)?",
            source_id="src-ccsc-2024q3",
            source_text=CCSC,
            evidence_span="合并营业收入18,950百万元",
            reference=answered(189.5, YI, "189.5亿元"),
            convention=conv(tax="ex_tax"),
            language="en",
            tags=["boundary:unit_conversion", "bilingual"],
            notes="18,950百万元 = 189.5亿元。英文提问，证据在中文原句。",
        ),
        item(
            id="ccsc-2024q3-net-profit",
            company="赤川半导体",
            ticker="CCSC",
            report_period="2024Q3",
            metric="net_profit",
            unit=YI,
            question="赤川半导体2024年第三季度归属于上市公司股东的净利润折合多少亿元？",
            source_id="src-ccsc-2024q3",
            source_text=CCSC,
            evidence_span="归属于上市公司股东的净利润2,130百万元",
            reference=answered(21.3, YI, "21.3亿元"),
            convention=conv(profit_view="attributable"),
            tags=["boundary:unit_conversion"],
            notes="2,130百万元 = 21.3亿元。",
        ),
        item(
            id="ccsc-2024q3-ocf",
            company="赤川半导体",
            ticker="CCSC",
            report_period="2024Q3",
            metric="operating_cashflow",
            unit=YI,
            question="赤川半导体2024年第三季度经营活动现金流量净额折合多少亿元？",
            source_id="src-ccsc-2024q3",
            source_text=CCSC,
            evidence_span="经营活动产生的现金流量净额2,560百万元",
            reference=answered(25.6, YI, "25.6亿元"),
            convention=conv(),
            tags=["boundary:unit_conversion"],
            notes="2,560百万元 = 25.6亿元。",
        ),
        item(
            id="blsp-2024fy-revenue",
            company="白露食品",
            ticker="BLSP",
            report_period="2024FY",
            metric="revenue",
            unit=YI,
            question="白露食品2024年合并营业收入是多少？",
            source_id="src-blsp-2024fy",
            source_text=BLSP,
            evidence_span="合并营业收入30.25亿元",
            reference=answered(30.25, YI, "30.25亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core"],
            notes="合并营业收入。",
        ),
        item(
            id="blsp-2024fy-net-profit",
            company="白露食品",
            ticker="BLSP",
            report_period="2024FY",
            metric="net_profit",
            unit=YI,
            question="白露食品2024年归属于上市公司股东的净利润是多少亿元？",
            source_id="src-blsp-2024fy",
            source_text=BLSP,
            evidence_span="归属于上市公司股东的净利润0.82亿元",
            reference=answered(0.82, YI, "0.82亿元"),
            convention=conv(profit_view="attributable"),
            tags=["core"],
            notes="小额利润仍应作答，不能因为金额小而拒答。",
        ),
        item(
            id="blsp-2024fy-net-profit-wanyuan",
            company="白露食品",
            ticker="BLSP",
            report_period="2024FY",
            metric="net_profit",
            unit=WAN,
            question="白露食品2024年归母净利润折合多少万元？",
            source_id="src-blsp-2024fy",
            source_text=BLSP,
            evidence_span="归属于上市公司股东的净利润0.82亿元",
            reference=answered(8200, WAN, "8,200万元"),
            convention=conv(profit_view="attributable"),
            tags=["boundary:unit_conversion"],
            notes="0.82亿元 = 8,200万元，片段中两种单位同时出现且等价。",
        ),
        item(
            id="blsp-2024fy-revenue-yoy",
            company="白露食品",
            ticker="BLSP",
            report_period="2024FY",
            metric="revenue_yoy",
            unit=PERCENT,
            question="白露食品2024年合并营业收入同比增速是多少？片段未直接给出百分比。",
            source_id="src-blsp-2024fy",
            source_text=BLSP,
            evidence_span=blsp_rev_yoy_span,
            reference=yoy_reference(blsp_rev_yoy_span),
            convention=conv(tax="ex_tax"),
            tags=["calc:yoy"],
            requires_calculation=True,
            notes="由30.25与29.80计算。",
        ),
        item(
            id="blsp-2024fy-net-profit-yoy",
            company="白露食品",
            ticker="BLSP",
            report_period="2024FY",
            metric="net_profit_yoy",
            unit=PERCENT,
            question="白露食品2024年归母净利润同比变动是多少？下降请记为负数。",
            source_id="src-blsp-2024fy",
            source_text=BLSP,
            evidence_span=blsp_np_yoy_span,
            reference=yoy_reference(blsp_np_yoy_span),
            convention=conv(profit_view="attributable"),
            tags=["calc:yoy", "boundary:negative_value"],
            requires_calculation=True,
            notes="由0.82与1.20计算，结果为负。",
        ),
        item(
            id="lqwl-2025q1-revenue",
            company="岚桥物流",
            ticker="LQWL",
            report_period="2025Q1",
            metric="revenue",
            unit=YI,
            question="岚桥物流2025年第一季度合并营业收入是多少？",
            source_id="src-lqwl-2025q1",
            source_text=LQWL,
            evidence_span="2025年1-3月合并营业收入45.3亿元",
            reference=answered(45.3, YI, "45.3亿元"),
            convention=conv(tax="ex_tax"),
            tags=["core"],
            notes="仅有季度数。",
        ),
        item(
            id="lqwl-2025q1-ocf",
            company="岚桥物流",
            ticker="LQWL",
            report_period="2025Q1",
            metric="operating_cashflow",
            unit=YI,
            question="岚桥物流2025年第一季度经营活动现金流量净额是多少？若片段未披露请拒答。",
            source_id="src-lqwl-2025q1",
            source_text=LQWL,
            evidence_span="经营活动现金流量净额本片段未披露。",
            reference=refused("insufficient_evidence", "拒答：片段未披露经营活动现金流量净额"),
            convention=conv(),
            tags=["boundary:insufficient_evidence"],
            notes="未披露经营现金流。",
        ),
        item(
            id="lqwl-2025q1-annual-revenue",
            company="岚桥物流",
            ticker="LQWL",
            report_period="2025Q1",
            metric="revenue",
            unit=YI,
            question="岚桥物流2025年全年营业收入是多少？若片段只有第一季度，请拒答。",
            source_id="src-lqwl-2025q1",
            source_text=LQWL,
            evidence_span="全年数据尚未报告。",
            reference=refused("out_of_scope", "拒答：片段未覆盖2025年全年"),
            convention=conv(tax="ex_tax"),
            tags=["boundary:out_of_scope"],
            notes="45.3亿元是1-3月，不能当成全年。",
        ),
        item(
            id="lqwl-2025q1-unit-ambiguous",
            company="岚桥物流",
            ticker="LQWL",
            report_period="2025Q1",
            metric="net_profit",
            unit=YI,
            question="岚桥物流附注残句里的净利润7.6，按合并口径的精确金额是多少？若单位无法确定请拒答。",
            source_id="src-lqwl-2025q1",
            source_text=LQWL,
            evidence_span="净利润7.6（单位见合并报表附注；本片段未给出元、万元或亿元）。",
            reference=refused("unit_ambiguous", "拒答：数字7.6的单位无法确定"),
            convention=conv(profit_view="net"),
            tags=["boundary:unit_ambiguous"],
            notes="有数字但没有单位，不能默认成亿元。",
        ),
    ]


def build_predictions(gold: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """fixture-extractor-v1: mostly correct, fails the planted traps."""

    overrides = {
        "xlkj-2024q3-revenue": {
            "answer": "86.2亿元",
            "value": 86.2,
            "unit": YI,
            "evidence": "母公司营业收入86.2亿元",
            "refused": False,
        },
        "bcyy-2024fy-revenue-yoy": {
            "answer": "同比+4.50%",
            "value": 4.50,
            "unit": PERCENT,
            "evidence": "2024年公司合并营业收入356.2亿元，上年同期340.1亿元，同比增长4.73%",
            "refused": False,
        },
        "bcyy-2024fy-revenue-wanyuan": {
            "answer": "356.2万元",
            "value": 356.2,
            "unit": WAN,
            "evidence": "2024年公司合并营业收入356.2亿元",
            "refused": False,
        },
        "chry-2024h1-revenue": {
            "answer": "104.4亿元",
            "value": 104.4,
            "unit": YI,
            "evidence": "含税销售额104.4亿元",
            "refused": False,
        },
        "qhne-2024fy-ocf": {
            "answer": "3.8亿元",
            "value": 3.8,
            "unit": YI,
            "evidence": "经营活动产生的现金流量净额为-3.8亿元",
            "refused": False,
        },
        "wtjj-2023fy-revenue": {
            "answer": "67.8亿元",
            "value": 67.8,
            "unit": YI,
            "evidence": "收入很高67.8亿元",
            "refused": False,
        },
        "ccsc-2024q3-revenue": {
            "answer": "18950亿元",
            "value": 18950,
            "unit": YI,
            "evidence": "合并营业收入18,950百万元",
            "refused": False,
        },
        "blsp-2024fy-net-profit": {
            "answer": "拒答：利润过小无法确认",
            "value": None,
            "unit": None,
            "evidence": "",
            "refused": True,
        },
        "lqwl-2025q1-ocf": {
            "answer": "12.0亿元",
            "value": 12.0,
            "unit": YI,
            "evidence": "经营活动现金流量净额12.0亿元",
            "refused": False,
        },
        "lqwl-2025q1-unit-ambiguous": {
            "answer": "7.6亿元",
            "value": 7.6,
            "unit": YI,
            "evidence": "净利润7.6（单位见合并报表附注；本片段未给出元、万元或亿元）。",
            "refused": False,
        },
    }
    rows = []
    for gold_item in gold:
        reference = gold_item["reference"]
        if gold_item["id"] in overrides:
            body = overrides[gold_item["id"]]
        elif reference["answerable"]:
            body = {
                "answer": reference["display"],
                "value": reference["value"],
                "unit": reference["unit"],
                "evidence": gold_item["evidence_span"],
                "refused": False,
            }
        else:
            body = {
                "answer": reference["display"],
                "value": None,
                "unit": None,
                "evidence": gold_item["evidence_span"],
                "refused": True,
            }
        rows.append({"id": gold_item["id"], "model": "fixture-extractor-v1", **body})
    return rows


def _clone(row: dict[str, Any], **changes: Any) -> dict[str, Any]:
    cloned = json.loads(json.dumps(row))
    cloned.update(changes)
    return cloned


def build_bad_samples(gold: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Planted defects. `fin-qa-eval qc` must fail on this file."""

    template = gold[0]
    source = template["source_text"]
    valid = _clone(
        template,
        id="bad-valid-anchor",
        question="质检锚点：星澜科技2024年第三季度合并营业收入是多少？",
        notes="schema-valid anchor used only inside the bad fixture.",
        tags=["fixture"],
        distractors=[],
    )
    valid.pop("distractors", None)

    dup_a = _clone(
        valid,
        id="bad-dup-revenue",
        question="重复主键样本甲：星澜科技第三季度合并收入？",
    )
    dup_b = _clone(
        valid,
        id="bad-dup-revenue",
        question="重复主键样本乙：星澜科技第三季度合并收入是多少亿元？",
    )
    missing_question = _clone(valid, id="bad-missing-question", question="将被删除")
    del missing_question["question"]

    evidence_miss = _clone(
        valid,
        id="bad-evidence-miss",
        question="证据不在片段中的营业收入是多少？",
        evidence_span="营业收入999亿元",
    )
    unit_slip = _clone(
        valid,
        id="bad-unit-slip",
        question="把亿元误标成万元后，星澜科技净利润是多少？",
        metric="net_profit",
        unit=WAN,
        evidence_span="归属于上市公司股东的净利润18.3亿元",
        reference=answered(18.3, WAN, "18.3万元"),
        convention=conv(profit_view="attributable"),
        notes="数字同为18.3，但单位从亿元滑成万元。",
        tags=["fixture"],
    )
    same_q_a = _clone(
        valid,
        id="bad-same-question-a",
        question="这两行的问题文本完全一样，用来测重复题检测。",
    )
    same_q_b = _clone(
        valid,
        id="bad-same-question-b",
        question="这两行的问题文本完全一样，用来测重复题检测。",
    )
    unanswerable_value = _clone(
        valid,
        id="bad-unanswerable-value",
        question="这道拒答题却填了数值，应该被质检拦住。",
        evidence_span="扣除非经常性损益后的净利润本期未披露。",
        reference={
            "answerable": False,
            "value": 18.3,
            "unit": YI,
            "display": "18.3亿元",
            "refusal_reason": None,
        },
        tags=["fixture"],
    )
    unknown_metric = _clone(
        valid,
        id="bad-unknown-metric",
        question="未知指标EBITDA不应进入评测集。",
        metric="ebitda",
    )
    missing_value = _clone(
        valid,
        id="bad-missing-value",
        question="可答题却没有参考数值，应该失败。",
        reference={
            "answerable": True,
            "value": None,
            "unit": None,
            "display": "缺失",
            "refusal_reason": None,
        },
    )
    equal_distractor = _clone(
        valid,
        id="bad-distractor-equals-gold",
        question="干扰项与金标数值相同，陷阱失效。",
        distractors=[
            {
                "span": "公司合并口径实现营业收入128.6亿元",
                "reason": "parent_scope",
                "value": 128.6,
                "unit": YI,
            }
        ],
    )
    not_synthetic = _clone(
        valid,
        id="bad-not-synthetic",
        question="未标记虚构的样本必须被拒绝。",
        synthetic=False,
    )
    return [
        dup_a,
        dup_b,
        missing_question,
        evidence_miss,
        unit_slip,
        same_q_a,
        same_q_b,
        unanswerable_value,
        unknown_metric,
        missing_value,
        equal_distractor,
        not_synthetic,
    ]


def dump_jsonl(path: Path, rows: list[dict[str, Any]], header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [header]
    for row in rows:
        lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def rendered_gold() -> str:
    return _render(
        "# synthetic demo data — invented companies and figures, not real filings",
        build_gold(),
    )


def rendered_bad() -> str:
    return _render(
        "# planted defects for fin-qa-eval qc — do not grade this file",
        build_bad_samples(build_gold()),
    )


def rendered_predictions() -> str:
    gold = build_gold()
    return _render(
        "# fixture-extractor-v1 predictions for the synthetic demo set",
        build_predictions(gold),
    )


def _render(header: str, rows: list[dict[str, Any]]) -> str:
    lines = [header]
    lines.extend(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    return "\n".join(lines) + "\n"


def main() -> None:
    gold = build_gold()
    dump_jsonl(
        GOLD_PATH,
        gold,
        "# synthetic demo data — invented companies and figures, not real filings",
    )
    dump_jsonl(
        BAD_PATH,
        build_bad_samples(gold),
        "# planted defects for fin-qa-eval qc — do not grade this file",
    )
    dump_jsonl(
        PRED_PATH,
        build_predictions(gold),
        "# fixture-extractor-v1 predictions for the synthetic demo set",
    )
    print(f"wrote {len(gold)} gold items -> {GOLD_PATH}")
    print(f"wrote bad fixtures -> {BAD_PATH}")
    print(f"wrote predictions -> {PRED_PATH}")


if __name__ == "__main__":
    main()
