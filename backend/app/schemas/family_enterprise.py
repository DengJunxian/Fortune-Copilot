from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    CashFlowFrequency,
    ComplexityBand,
    EnterpriseCashflowStability,
    EnterpriseCashflowType,
    EnterpriseEventStatus,
    EnterpriseEventType,
    EnterpriseGuaranteeType,
    EnterpriseInstrumentType,
    EnterpriseListedStatus,
    EnterpriseStage,
    EnterpriseType,
    EnterpriseValuationMethod,
    EvidenceConfidence,
)
from app.schemas.records import Money, Ratio, RecordInput, RecordOut


class EnterpriseCreate(RecordInput):
    name: str = Field(min_length=1, max_length=160)
    industry: str = Field(min_length=1, max_length=120)
    stage: EnterpriseStage
    jurisdiction: str = Field(default="CN", min_length=2, max_length=64)
    listed_status: EnterpriseListedStatus
    enterprise_type: EnterpriseType
    is_user_confirmed: Literal[True]


class EnterpriseOwnershipDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_entity_id: str
    ownership_ratio: Ratio
    voting_ratio: Ratio
    instrument_type: EnterpriseInstrumentType
    vesting_date: date | None = None
    lockup_end_date: date | None = None


class EnterpriseValuationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valuation_date: date
    equity_value: Money
    valuation_method: EnterpriseValuationMethod
    confidence: EvidenceConfidence
    source_kind: str = Field(min_length=1, max_length=48)
    evidence: dict[str, Any] = Field(default_factory=dict)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")


class EnterpriseCashflowDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str | None = None
    cashflow_type: EnterpriseCashflowType
    amount: Money
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    frequency: CashFlowFrequency
    stability: EnterpriseCashflowStability


class EnterpriseGuaranteeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str | None = None
    guarantee_type: EnterpriseGuaranteeType
    guaranteed_amount: Money
    outstanding_exposure: Money
    expiry_date: date | None = None
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_exposure(self) -> EnterpriseGuaranteeDraft:
        if self.outstanding_exposure > self.guaranteed_amount:
            raise ValueError("未偿担保暴露不能高于担保额度")
        return self


class EnterpriseEventDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EnterpriseEventType
    expected_date: date
    estimated_value: Money
    probability: Ratio
    lockup: bool = False
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    status: EnterpriseEventStatus


class EnterpriseExposureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enterprise_id: str
    ownerships: list[EnterpriseOwnershipDraft] = Field(default_factory=list, max_length=50)
    valuations: list[EnterpriseValuationDraft] = Field(default_factory=list, max_length=20)
    cashflows: list[EnterpriseCashflowDraft] = Field(default_factory=list, max_length=50)
    guarantees: list[EnterpriseGuaranteeDraft] = Field(default_factory=list, max_length=50)
    liquidity_events: list[EnterpriseEventDraft] = Field(default_factory=list, max_length=50)
    source_reference: str = Field(
        default="client-confirmed-enterprise-exposure", min_length=1, max_length=160
    )
    is_user_confirmed: Literal[True]

    @model_validator(mode="after")
    def require_exposure(self) -> EnterpriseExposureCreate:
        if not any(
            (
                self.ownerships,
                self.valuations,
                self.cashflows,
                self.guarantees,
                self.liquidity_events,
            )
        ):
            raise ValueError("至少需要提供一项家企暴露资料")
        return self


class EnterpriseProfileOut(RecordOut):
    household_id: str
    name: str
    industry: str
    stage: EnterpriseStage
    jurisdiction: str
    listed_status: EnterpriseListedStatus
    enterprise_type: EnterpriseType


class EnterpriseOwnershipOut(RecordOut):
    household_id: str
    enterprise_id: str
    owner_entity_id: str
    ownership_ratio: Ratio
    voting_ratio: Ratio
    instrument_type: EnterpriseInstrumentType
    vesting_date: date | None
    lockup_end_date: date | None


class EnterpriseValuationOut(RecordOut):
    household_id: str
    enterprise_id: str
    equity_value: Money
    valuation_method: EnterpriseValuationMethod
    confidence: EvidenceConfidence
    source_kind: str
    evidence: dict[str, Any]


class EnterpriseCashflowOut(RecordOut):
    household_id: str
    enterprise_id: str
    member_id: str | None
    cashflow_type: EnterpriseCashflowType
    amount: Money
    frequency: CashFlowFrequency
    stability: EnterpriseCashflowStability


class EnterpriseGuaranteeOut(RecordOut):
    household_id: str
    enterprise_id: str
    member_id: str | None
    guarantee_type: EnterpriseGuaranteeType
    guaranteed_amount: Money
    outstanding_exposure: Money
    expiry_date: date | None


class EnterpriseEventOut(RecordOut):
    household_id: str
    enterprise_id: str
    event_type: EnterpriseEventType
    expected_date: date
    estimated_value: Money
    probability: Ratio
    lockup: bool
    status: EnterpriseEventStatus


class EnterpriseDetail(BaseModel):
    profile: EnterpriseProfileOut
    latest_valuation: EnterpriseValuationOut | None
    ownerships: list[EnterpriseOwnershipOut]
    cashflows: list[EnterpriseCashflowOut]
    guarantees: list[EnterpriseGuaranteeOut]
    liquidity_events: list[EnterpriseEventOut]
    household_owned_value: Money


class EnterpriseWealthSummary(BaseModel):
    household_wealth: Money
    financial_assets: Money
    property_assets: Money
    enterprise_wealth: Money
    economic_household_wealth: Money
    enterprise_wealth_ratio: Ratio


class EnterpriseDependencyComponent(BaseModel):
    code: Literal[
        "wealth_dependency",
        "income_dependency",
        "guarantee_dependency",
        "pledge_dependency",
        "currency_dependency",
    ]
    label: str
    ratio: Ratio
    weighted_score: Ratio
    numerator: Money
    denominator: Money
    explanation: str


class EnterpriseDependencyAssessment(BaseModel):
    components: list[EnterpriseDependencyComponent]
    score: Ratio
    level: ComplexityBand
    label: str
    regulatory_rating: Literal[False] = False
    disclaimer: str


class EnterpriseIncomeSummary(BaseModel):
    enterprise_annual_income: Money
    household_annual_income: Money
    dependency_ratio: Ratio
    low_stability_annual_income: Money


class EnterpriseGuaranteeSummary(BaseModel):
    guaranteed_amount: Money
    outstanding_exposure: Money
    active_count: int = Field(ge=0)


class EconomicCapitalExposure(BaseModel):
    unlisted_company_equity: Money
    listed_employer_stock: Money
    equity_incentives: Money
    liquid_securities_equity: Money
    enterprise_salary_and_dividend_dependency: Money
    guarantee_exposure: Money
    pledge_exposure: Money
    total_economic_equity_exposure: Money
    economic_equity_ratio: Ratio
    risk_budget_ceiling_ratio: Ratio
    risk_budget_ceiling_amount: Money
    remaining_incremental_equity_capacity: Money
    additional_equity_risk_allowed: bool
    explanation: str


class CFSImplication(BaseModel):
    status: Literal["not_enabled", "constraints_available"]
    constraints: list[str]
    explanation: str


class FamilyEnterpriseMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    input_hash: str
    rule_version: str
    formula_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"


class FamilyEnterpriseView(BaseModel):
    meta: FamilyEnterpriseMeta
    enterprises: list[EnterpriseDetail]
    wealth: EnterpriseWealthSummary
    income: EnterpriseIncomeSummary
    guarantees: EnterpriseGuaranteeSummary
    dependency: EnterpriseDependencyAssessment
    economic_capital: EconomicCapitalExposure
    liquidity_events: list[EnterpriseEventOut]
    cfs_implication: CFSImplication


class EnterpriseCreateResponse(BaseModel):
    enterprise: EnterpriseProfileOut
    financial_entity_id: str


class EnterpriseExposureResponse(BaseModel):
    view: FamilyEnterpriseView
    financial_event_ids: list[str]
    snapshot_id: str | None
    idempotent_replay: bool
