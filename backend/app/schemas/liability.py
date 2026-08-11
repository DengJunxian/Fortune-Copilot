from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import CashFlowFrequency, GoalRigidity, LiabilityStreamType
from app.schemas.records import Money, Ratio, RecordInput, RecordOut


class LiabilityFundingSource(BaseModel):
    source_type: str = Field(min_length=1, max_length=48)
    source_id: str | None = Field(default=None, max_length=80)
    amount: Money = Decimal("0")
    note: str = Field(default="", max_length=240)


class LiabilityStreamCreate(RecordInput):
    wealth_need_id: str | None = None
    beneficiary_entity_id: str | None = None
    name: str = Field(min_length=1, max_length=160)
    stream_type: LiabilityStreamType
    start_date: date
    end_date: date | None = None
    frequency: CashFlowFrequency
    base_amount: Money
    minimum_amount: Money
    inflation_index_code: str = Field(min_length=1, max_length=40)
    annual_growth_assumption: Ratio = Decimal("0")
    rigidity: GoalRigidity
    deferrable: bool = False
    funding_sources: list[LiabilityFundingSource] = Field(default_factory=list)
    fallback_action: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_stream(self) -> LiabilityStreamCreate:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("负债流结束日期不得早于开始日期")
        if self.minimum_amount > self.base_amount:
            raise ValueError("最低金额不得高于基准金额")
        if self.frequency == CashFlowFrequency.ONE_TIME and (
            self.end_date is not None and self.end_date != self.start_date
        ):
            raise ValueError("一次性负债流的开始和结束日期必须一致")
        if not self.is_user_confirmed:
            raise ValueError("新增自定义负债流必须由用户确认")
        return self


class LiabilityStreamDraft(BaseModel):
    wealth_need_id: str | None = None
    source_goal_id: str | None = None
    source_responsibility_id: str | None = None
    beneficiary_entity_id: str | None = None
    name: str
    stream_type: LiabilityStreamType
    currency: str
    start_date: date
    end_date: date | None
    frequency: CashFlowFrequency
    base_amount: Money
    minimum_amount: Money
    inflation_index_code: str
    annual_growth_assumption: Ratio
    rigidity: GoalRigidity
    deferrable: bool
    funding_sources: list[dict[str, Any]] = Field(default_factory=list)
    fallback_action: str
    stream_version: str
    data_source: str
    is_user_confirmed: bool


class LiabilityCashflowDraft(BaseModel):
    due_date: date
    target_amount: Money
    minimum_amount: Money
    sequence: int = Field(ge=1)
    calculation_version: str


class LiabilityStreamCashflowOut(RecordOut):
    household_id: str
    liability_stream_id: str
    due_date: date
    target_amount: Money
    minimum_amount: Money
    sequence: int
    calculation_version: str


class LiabilityStreamOut(RecordOut):
    household_id: str
    wealth_need_id: str | None
    source_goal_id: str | None
    source_responsibility_id: str | None
    beneficiary_entity_id: str | None
    name: str
    stream_type: LiabilityStreamType
    start_date: date
    end_date: date | None
    frequency: CashFlowFrequency
    base_amount: Money
    minimum_amount: Money
    inflation_index_code: str
    annual_growth_assumption: Ratio
    rigidity: GoalRigidity
    deferrable: bool
    funding_sources: list[dict[str, Any]]
    fallback_action: str
    stream_version: str


class LiabilityCalendarEntry(BaseModel):
    stream: LiabilityStreamOut
    cashflows: list[LiabilityStreamCashflowOut]
    target_total: Money
    minimum_total: Money
    prepared_amount: Money
    funding_gap: Money


class LiabilityCalendarSummary(BaseModel):
    stream_count: int = Field(ge=0)
    cashflow_count: int = Field(ge=0)
    target_total: Money
    minimum_total: Money
    prepared_total: Money
    funding_gap: Money
    next_due_date: date | None


class LiabilityCalendarMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    rule_version: str
    formula_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    adapter_sources: list[Literal["financial_goals", "responsibilities"]]


class LiabilityCalendarResponse(BaseModel):
    meta: LiabilityCalendarMeta
    summary: LiabilityCalendarSummary
    entries: list[LiabilityCalendarEntry]


class LiabilityStreamCreateResponse(BaseModel):
    meta: LiabilityCalendarMeta
    entry: LiabilityCalendarEntry
