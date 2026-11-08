from decimal import Decimal

from fin_qa_eval.units import (
    classify_mismatch,
    infer_yoy_percent,
    parse_amounts,
    values_close,
)


def test_parse_yi_and_comma_grouped_million() -> None:
    amounts = parse_amounts("实现营业收入128.6亿元，另有18,950百万元。")
    assert [(str(item.value), item.unit) for item in amounts] == [
        ("128.6", "CNY_hundred_million"),
        ("18950", "CNY_million"),
    ]


def test_decline_flips_percent_negative() -> None:
    parsed = parse_amounts("同比下降13.99%，上年为增长4.73%")
    assert parsed[0].value == Decimal("-13.99")
    assert parsed[0].unit == "percent"
    assert parsed[1].value == Decimal("4.73")


def test_explicit_minus_cashflow() -> None:
    parsed = parse_amounts("经营活动产生的现金流量净额为-3.8亿元")
    assert parsed[0].value == Decimal("-3.8")
    assert parsed[0].unit == "CNY_hundred_million"


def test_unit_normalization_yi_equals_wan() -> None:
    assert values_close(
        Decimal("356.2"),
        "CNY_hundred_million",
        Decimal("3562000"),
        "CNY_ten_thousand",
    )


def test_yoy_half_up_and_scale_and_sign_labels() -> None:
    current, prior = parse_amounts("128.6亿元，上年同期112.4亿元")
    assert infer_yoy_percent(current, prior) == Decimal("14.41")
    assert (
        classify_mismatch(
            Decimal("189.5"),
            "CNY_hundred_million",
            Decimal("18950"),
            "CNY_hundred_million",
        )
        == "unit_scale_error"
    )
    assert (
        classify_mismatch(
            Decimal("-3.8"),
            "CNY_hundred_million",
            Decimal("3.8"),
            "CNY_hundred_million",
        )
        == "sign_error"
    )
    assert (
        classify_mismatch(Decimal("4.73"), "percent", Decimal("4.50"), "percent")
        == "numeric_mismatch"
    )
