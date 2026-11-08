"""Parse and normalize Chinese financial amounts.

Money is normalized to CNY. Year-over-year rates are percentage points as
written: ``同比增长12.5%`` is ``+12.5``, ``同比下降3.2%`` is ``-3.2``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

# Canonical unit → multiplier into CNY.
MONEY_TO_CNY: dict[str, Decimal] = {
    "CNY": Decimal(1),
    "CNY_thousand": Decimal(1_000),
    "CNY_ten_thousand": Decimal(10_000),
    "CNY_million": Decimal(1_000_000),
    "CNY_hundred_million": Decimal(100_000_000),
}

PERCENT_UNITS = frozenset({"percent"})
MONEY_UNITS = frozenset(MONEY_TO_CNY)
KNOWN_UNITS = MONEY_UNITS | PERCENT_UNITS

# Longer phrases must be tried first so 元 does not swallow 亿元.
_UNIT_PATTERN = (
    r"亿元|百万元|万元|千元|元|个百分点|%|％"
)
_UNIT_TO_CODE = {
    "亿元": "CNY_hundred_million",
    "百万元": "CNY_million",
    "万元": "CNY_ten_thousand",
    "千元": "CNY_thousand",
    "元": "CNY",
    "个百分点": "percent",
    "%": "percent",
    "％": "percent",
}
_NEGATIVE_WORDS = ("下降", "减少", "降低", "下滑", "亏损")

_AMOUNT_RE = re.compile(
    rf"(?P<signword>{'|'.join(_NEGATIVE_WORDS)})?\s*"
    rf"(?P<num>[-+]?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?)\s*"
    rf"(?P<unit>{_UNIT_PATTERN})"
)

# Relative tolerance on money after conversion to CNY, with a 1 CNY floor.
MONEY_REL_TOL = Decimal("0.001")
MONEY_ABS_TOL = Decimal("1")
# YoY answers are rounded half-up to 0.01 percentage point; allow 0.05.
PERCENT_ABS_TOL = Decimal("0.05")

_SCALE_FACTORS = (
    Decimal(10),
    Decimal(100),
    Decimal(1_000),
    Decimal(10_000),
    Decimal(1_000_000),
    Decimal(100_000_000),
)


class UnitError(ValueError):
    """Raised when a unit code is unknown or incompatible."""


@dataclass(frozen=True)
class ParsedAmount:
    """A signed number attached to a canonical unit."""

    value: Decimal
    unit: str
    raw: str


def is_money(unit: str) -> bool:
    return unit in MONEY_UNITS


def is_percent(unit: str) -> bool:
    return unit in PERCENT_UNITS


def same_family(left: str, right: str) -> bool:
    return (is_money(left) and is_money(right)) or (is_percent(left) and is_percent(right))


def to_decimal(value: float | int | str | Decimal) -> Decimal:
    """Convert JSON numbers without binary float residue when possible."""

    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def to_cny(value: Decimal, unit: str) -> Decimal:
    if unit not in MONEY_TO_CNY:
        raise UnitError(f"not a money unit: {unit}")
    return value * MONEY_TO_CNY[unit]


def to_base(value: Decimal, unit: str) -> Decimal:
    """Money → CNY. Percent → the percentage-point number itself."""

    if is_money(unit):
        return to_cny(value, unit)
    if is_percent(unit):
        return value
    raise UnitError(f"unknown unit: {unit}")


def round_half_up(value: Decimal, places: int = 2) -> Decimal:
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def parse_amounts(text: str) -> list[ParsedAmount]:
    """Extract every number-with-unit phrase from ``text``.

    A leading 下降 / 减少 / 降低 / 下滑 / 亏损 flips a positive number
    negative. An explicit minus sign is kept either way.
    """

    if not text:
        return []
    found: list[ParsedAmount] = []
    for match in _AMOUNT_RE.finditer(text):
        raw_num = match.group("num").replace(",", "")
        number = Decimal(raw_num)
        if match.group("signword") and number > 0:
            number = -number
        unit = _UNIT_TO_CODE[match.group("unit")]
        found.append(ParsedAmount(value=number, unit=unit, raw=match.group(0)))
    return found


def parse_first_amount(text: str) -> Optional[ParsedAmount]:
    amounts = parse_amounts(text)
    return amounts[0] if amounts else None


def values_close(
    left_value: Decimal,
    left_unit: str,
    right_value: Decimal,
    right_unit: str,
) -> bool:
    """Whether two amounts match after unit normalization."""

    if not same_family(left_unit, right_unit):
        return False
    left = to_base(left_value, left_unit)
    right = to_base(right_value, right_unit)
    if is_percent(left_unit):
        return abs(left - right) <= PERCENT_ABS_TOL
    tolerance = max(MONEY_ABS_TOL, abs(left) * MONEY_REL_TOL)
    return abs(left - right) <= tolerance


def infer_yoy_percent(current: ParsedAmount, prior: ParsedAmount) -> Optional[Decimal]:
    """YoY percent, half-up to 2 decimals.

    The project convention refuses a percent YoY when the comparison base is
    zero or negative, or when the current amount is negative. Callers that
    need that case should mark the item unanswerable with
    ``convention_conflict`` rather than invent a ratio.
    """

    if not is_money(current.unit) or not is_money(prior.unit):
        return None
    current_cny = to_cny(current.value, current.unit)
    prior_cny = to_cny(prior.value, prior.unit)
    if prior_cny <= 0 or current_cny < 0:
        return None
    raw = (current_cny - prior_cny) / prior_cny * Decimal(100)
    return round_half_up(raw, 2)


def classify_mismatch(
    gold_value: Decimal,
    gold_unit: str,
    pred_value: Decimal,
    pred_unit: str,
) -> str:
    """Label a numeric miss as sign, scale, or a plain mismatch.

    Scale covers the usual 口径 slip of dropping or adding 万 / 亿
    (factors of 10, 100, 1e3, 1e4, 1e6, 1e8) after both sides are in CNY.
    """

    if not same_family(gold_unit, pred_unit):
        return "numeric_mismatch"
    gold = to_base(gold_value, gold_unit)
    pred = to_base(pred_value, pred_unit)
    if gold == 0 or pred == 0:
        return "numeric_mismatch"
    if (gold > 0) != (pred > 0) and values_close(abs(gold), "CNY" if is_money(gold_unit) else "percent", abs(pred), "CNY" if is_money(gold_unit) else "percent"):
        return "sign_error"
    ratio = abs(pred / gold)
    for factor in _SCALE_FACTORS:
        inverse = Decimal(1) / factor
        if _ratio_close(ratio, factor) or _ratio_close(ratio, inverse):
            return "unit_scale_error"
    return "numeric_mismatch"


def _ratio_close(ratio: Decimal, factor: Decimal) -> bool:
    if factor == 0:
        return False
    return abs(ratio - factor) / factor <= Decimal("0.02")
