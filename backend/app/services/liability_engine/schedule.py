from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.domain.enums import CashFlowFrequency, GoalRigidity, LiabilityStreamType
from app.schemas.liability import LiabilityCashflowDraft

_CENT = Decimal("0.01")


class SchedulableStream(Protocol):
    name: str
    stream_type: LiabilityStreamType
    start_date: date
    end_date: date | None
    frequency: CashFlowFrequency
    base_amount: Decimal
    minimum_amount: Decimal
    annual_growth_assumption: Decimal
    inflation_index_code: str
    rigidity: GoalRigidity
    deferrable: bool
    funding_sources: list[dict[str, object]]
    stream_version: str


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _due_dates(stream: SchedulableStream) -> list[date]:
    end_date = stream.end_date or stream.start_date
    if stream.frequency in {CashFlowFrequency.ONE_TIME, CashFlowFrequency.IRREGULAR}:
        return [stream.start_date]
    interval = {
        CashFlowFrequency.MONTHLY: 1,
        CashFlowFrequency.QUARTERLY: 3,
        CashFlowFrequency.ANNUAL: 12,
    }[stream.frequency]
    dates: list[date] = []
    index = 0
    while True:
        due_date = _add_months(stream.start_date, interval * index)
        if due_date > end_date:
            break
        dates.append(due_date)
        index += 1
    return dates or [stream.start_date]


def _funding_total(stream: SchedulableStream, key: str) -> Decimal | None:
    for item in stream.funding_sources:
        raw = item.get(key)
        if raw is not None:
            return Decimal(str(raw))
    return None


def build_schedule(stream: SchedulableStream, formula_version: str) -> list[LiabilityCashflowDraft]:
    due_dates = _due_dates(stream)
    target_total = _funding_total(stream, "target_total")
    minimum_total = _funding_total(stream, "minimum_total")
    rows: list[LiabilityCashflowDraft] = []
    target_running = Decimal("0.00")
    minimum_running = Decimal("0.00")
    for index, due_date in enumerate(due_dates):
        anniversary_years = max(
            0,
            due_date.year
            - stream.start_date.year
            - ((due_date.month, due_date.day) < (stream.start_date.month, stream.start_date.day)),
        )
        growth_factor = (Decimal("1") + stream.annual_growth_assumption) ** anniversary_years
        target_amount = _money(stream.base_amount * growth_factor)
        minimum_amount = _money(stream.minimum_amount * growth_factor)
        if index == len(due_dates) - 1:
            if target_total is not None:
                target_amount = _money(max(Decimal("0"), target_total - target_running))
            if minimum_total is not None:
                minimum_amount = _money(max(Decimal("0"), minimum_total - minimum_running))
        target_running += target_amount
        minimum_running += minimum_amount
        rows.append(
            LiabilityCashflowDraft(
                due_date=due_date,
                target_amount=target_amount,
                minimum_amount=min(minimum_amount, target_amount),
                sequence=index + 1,
                calculation_version=f"{formula_version}:{stream.stream_version[:12]}",
            )
        )
    return rows
