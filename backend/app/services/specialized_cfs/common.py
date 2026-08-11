from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.domain.enums import CashFlowFrequency, CurrencyExposureHorizon

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def annualize(amount: Decimal, frequency: CashFlowFrequency) -> Decimal:
    multiplier = {
        CashFlowFrequency.MONTHLY: Decimal("12"),
        CashFlowFrequency.QUARTERLY: Decimal("4"),
        CashFlowFrequency.ANNUAL: Decimal("1"),
        CashFlowFrequency.ONE_TIME: Decimal("0"),
        CashFlowFrequency.IRREGULAR: Decimal("1"),
    }[frequency]
    return money(amount * multiplier)


def age_on(birth_date: date, as_of: date) -> int:
    before_birthday = (as_of.month, as_of.day) < (birth_date.month, birth_date.day)
    return as_of.year - birth_date.year - before_birthday


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def exposure_horizon(
    analysis_date: date,
    target_date: date | None,
    *,
    short_term_days: int,
    medium_term_days: int,
) -> CurrencyExposureHorizon:
    if target_date is None:
        return CurrencyExposureHorizon.CURRENT
    days = (target_date - analysis_date).days
    if days <= short_term_days:
        return CurrencyExposureHorizon.SHORT_TERM
    if days <= medium_term_days:
        return CurrencyExposureHorizon.MEDIUM_TERM
    return CurrencyExposureHorizon.LONG_TERM
