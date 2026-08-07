from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import CashFlowFrequency

ZERO = Decimal("0")
ONE = Decimal("1")
TWELVE = Decimal("12")
MONEY_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.000001")
DISPLAY_QUANTUM = Decimal("0.01")

FREQUENCY_MULTIPLIERS = {
    CashFlowFrequency.MONTHLY: Decimal("12"),
    CashFlowFrequency.QUARTERLY: Decimal("4"),
    CashFlowFrequency.ANNUAL: Decimal("1"),
    CashFlowFrequency.ONE_TIME: Decimal("1"),
    CashFlowFrequency.IRREGULAR: Decimal("1"),
}


def annualize(amount: Decimal, frequency: CashFlowFrequency) -> Decimal:
    return money(amount * FREQUENCY_MULTIPLIERS[frequency])


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def display_number(value: Decimal) -> Decimal:
    return value.quantize(DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)


def safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return ratio(numerator / denominator)


def years_between(start: date, end: date) -> Decimal:
    if end <= start:
        return ZERO
    return display_number(Decimal((end - start).days) / Decimal("365.25"))


def format_money(value: Decimal) -> str:
    return f"{money(value):,.2f}"


def format_ratio(value: Decimal) -> str:
    return f"{ratio(value) * Decimal('100'):.1f}%"
