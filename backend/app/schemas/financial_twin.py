from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.domain.enums import (
    FinancialEventDomain,
    FinancialEventStatus,
    HouseholdSnapshotStatus,
    LifeEventType,
    RiskLevel,
    WealthNeedStatus,
    WealthNeedType,
)
from app.schemas.records import Money, Ratio, RecordOut, reject_binary_float

SignedMoney = Annotated[
    Decimal,
    BeforeValidator(reject_binary_float),
    Field(max_digits=20, decimal_places=2),
]
IncomeChangeRatio = Annotated[
    Decimal,
    BeforeValidator(reject_binary_float),
    Field(ge=Decimal("-1"), le=Decimal("1"), max_digits=9, decimal_places=6),
]


class LifeEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    life_event_type: Literal[LifeEventType.SALARY_CHANGE] = LifeEventType.SALARY_CHANGE
    event_date: date
    member_id: str | None = None
    income_source_ids: list[str] = Field(default_factory=list, max_length=20)
    income_change_ratio: IncomeChangeRatio
    source_reference: str = Field(
        default="client-confirmed-life-event", min_length=1, max_length=160
    )
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    is_user_confirmed: Literal[True]

    @model_validator(mode="after")
    def validate_change(self) -> LifeEventCreate:
        if self.income_change_ratio == 0:
            raise ValueError("收入变动比例不能为 0")
        if len(self.income_source_ids) != len(set(self.income_source_ids)):
            raise ValueError("收入来源不能重复")
        return self


class TwinIncomeState(BaseModel):
    id: str
    member_id: str | None
    name: str
    annual_amount: Money


class TwinFactState(BaseModel):
    household_code: str
    household_name: str
    members: list[dict[str, str | None]]
    incomes: list[TwinIncomeState]
    annual_income: Money
    annual_expenses: Money
    total_assets: Money
    total_liabilities: Money
    net_worth: SignedMoney


class TwinProfileState(BaseModel):
    profile_version: int | None
    lifecycle_stage: str | None
    wealth_tier: str | None
    service_complexity: str | None
    risk_capacity: RiskLevel | None
    risk_willingness: RiskLevel | None
    behavior_limit: RiskLevel | None
    status: str


class TwinNeedState(BaseModel):
    id: str
    need_type: WealthNeedType
    priority: int
    status: WealthNeedStatus
    target_amount: Money
    minimum_amount: Money


class TwinLiabilityState(BaseModel):
    stream_count: int = Field(ge=0)
    cashflow_count: int = Field(ge=0)
    target_total: Money
    prepared_total: Money
    funding_gap: Money
    next_due_date: date | None


class TwinRiskBudgetState(BaseModel):
    risk_capacity: RiskLevel | None
    risk_willingness: RiskLevel | None
    behavior_limit: RiskLevel | None
    eligible_long_term_capital: Money
    formally_eligible: bool
    decision: Literal["eligible", "repair_first"]
    enterprise_dependency_score: Ratio | None = None
    enterprise_dependency_level: str | None = None
    economic_equity_exposure: Money = Decimal("0.00")
    remaining_incremental_equity_capacity: Money = Decimal("0.00")
    additional_equity_risk_allowed: bool = True
    enterprise_constraints: list[str] = Field(default_factory=list)


class TwinCFSState(BaseModel):
    status: Literal["not_enabled", "available"]
    score: Decimal | None = None
    explanation: str


class TwinMonitoringState(BaseModel):
    status: Literal["not_enabled", "evaluated"]
    alerts: list[str] = Field(default_factory=list)


class HouseholdTwinState(BaseModel):
    facts: TwinFactState
    profile: TwinProfileState
    needs: list[TwinNeedState]
    liability: TwinLiabilityState
    risk_budget: TwinRiskBudgetState
    cfs: TwinCFSState
    monitoring: TwinMonitoringState


class HouseholdSnapshotOut(RecordOut):
    household_id: str
    parent_snapshot_id: str | None
    source_financial_snapshot_id: str | None
    snapshot_date: date
    event_cursor: int
    financial_graph_version: str
    profile_version: int | None
    need_version: str
    liability_version: str
    input_hash: str
    snapshot_hash: str
    status: HouseholdSnapshotStatus
    state: HouseholdTwinState


class SnapshotSummary(BaseModel):
    id: str
    snapshot_date: date
    event_cursor: int
    snapshot_hash: str


class FactChange(BaseModel):
    code: str
    label: str
    before: str | None
    after: str | None
    direction: Literal["increased", "decreased", "changed", "added", "removed"]


class NeedChange(BaseModel):
    need_type: WealthNeedType
    change_type: Literal["added", "removed", "changed"]
    before_status: WealthNeedStatus | None = None
    after_status: WealthNeedStatus | None = None
    before_target_amount: Money | None = None
    after_target_amount: Money | None = None


class ProfileChange(BaseModel):
    changed: bool
    before_version: int | None
    after_version: int | None
    changed_fields: list[str] = Field(default_factory=list)


class RiskBudgetChange(BaseModel):
    changed: bool
    before: TwinRiskBudgetState | None
    after: TwinRiskBudgetState


class CFSChange(BaseModel):
    changed: bool
    before: TwinCFSState | None
    after: TwinCFSState


class SnapshotComparison(BaseModel):
    from_snapshot_id: str | None
    to_snapshot_id: str
    changed_facts: list[FactChange]
    changed_needs: list[NeedChange]
    changed_profile: ProfileChange
    changed_risk_budget: RiskBudgetChange
    changed_cfs: CFSChange
    has_material_change: bool


class WealthTwinMeta(BaseModel):
    household_id: str
    analysis_date: date
    snapshot_count: int = Field(ge=1)
    event_count: int = Field(ge=0)
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"


class WealthTwinResponse(BaseModel):
    meta: WealthTwinMeta
    current: HouseholdSnapshotOut
    previous: SnapshotSummary | None
    comparison: SnapshotComparison


class LifeEventOut(RecordOut):
    household_id: str
    financial_event_id: str
    member_id: str | None
    life_event_type: LifeEventType
    event_date: date
    expected_financial_impact: SignedMoney
    metadata_json: dict[str, Any]


class FinancialEventOut(RecordOut):
    household_id: str
    event_domain: FinancialEventDomain
    event_type: str
    effective_at: datetime
    recorded_at: datetime
    source_kind: str
    source_reference: str
    confirmation_status: FinancialEventStatus
    payload: dict[str, Any]
    event_hash: str
    processed_snapshot_id: str | None
    life_event: LifeEventOut | None = None


class EventTimelineResponse(BaseModel):
    household_id: str
    events: list[FinancialEventOut]
    total: int = Field(ge=0)


class LifeEventProcessResponse(BaseModel):
    event: FinancialEventOut
    snapshot: HouseholdSnapshotOut
    comparison: SnapshotComparison
    idempotent_replay: bool
