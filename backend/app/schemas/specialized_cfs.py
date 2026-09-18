from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import (
    CFSTimeHorizon,
    CurrencyExposureDirection,
    CurrencyExposureHorizon,
    CurrencyExposureType,
    InstitutionalEntitlementType,
    ProfessionalReferralStatus,
    ProfessionalReferralUrgency,
    ProfessionalSpecialistType,
    SpecializedComplexity,
    TrustSuccessionNeedType,
)
from app.schemas.records import Money, RecordOut


class SpecializedResponseMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    input_hash: str
    rule_version: str
    formula_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"


class ProfessionalRoute(BaseModel):
    need: str
    complexity: SpecializedComplexity
    complexity_gate_passed: bool
    specialist_type: ProfessionalSpecialistType | None
    referral_id: str | None
    referral_status: ProfessionalReferralStatus | None
    advisor_workflow_status: Literal[
        "not_required",
        "cfs_required",
        "referral_open",
        "in_progress",
        "completed",
    ]
    reason: str
    boundary: str


class InstitutionalEntitlementOut(RecordOut):
    household_id: str
    member_id: str | None
    entitlement_type: InstitutionalEntitlementType
    balance: Money
    expected_income: Money
    start_age: int | None
    start_date: date | None
    end_date: date | None
    guaranteed: bool
    indexed: bool
    lock_up: bool
    source_kind: str
    confidence: Decimal = Field(ge=0, le=1)
    evidence: dict[str, object]


class RetirementLiabilityBreakdown(BaseModel):
    basic_retirement_liability: Money
    medical_liability: Money
    long_term_care_liability: Money
    improved_retirement_goal: Money
    retirement_start_date: date | None
    retirement_years: int


class RetirementGapOutput(BaseModel):
    retirement_floor: Money
    guaranteed_income: Money
    income_gap: Money
    longevity_gap: Money
    liquidity_gap: Money


class RetirementPlanResponse(BaseModel):
    meta: SpecializedResponseMeta
    has_retirement_need: bool
    liabilities: RetirementLiabilityBreakdown
    entitlements: list[InstitutionalEntitlementOut]
    output: RetirementGapOutput
    route: ProfessionalRoute
    assumptions: list[str]
    boundary: str


class CurrencyExposureOut(RecordOut):
    household_id: str
    entity_id: str | None
    exposure_type: CurrencyExposureType
    amount: Money
    direction: CurrencyExposureDirection
    horizon: CurrencyExposureHorizon
    source_record_ids: list[str]


class CurrencyExposureSummary(BaseModel):
    currency: str
    inflow: Money
    outflow: Money
    net_exposure: Decimal = Field(max_digits=20, decimal_places=2)
    source_count: int


class CurrencyExposureResponse(BaseModel):
    meta: SpecializedResponseMeta
    base_currency: str
    material_exposure_detected: bool
    exposures: list[CurrencyExposureOut]
    summaries: list[CurrencyExposureSummary]
    route: ProfessionalRoute
    detection_notes: list[str]
    boundary: str


class TrustSuccessionNeedOut(RecordOut):
    household_id: str
    need_type: TrustSuccessionNeedType
    beneficiaries: list[dict[str, object]]
    assets_in_scope: list[dict[str, object]]
    enterprise_in_scope: list[str]
    urgency: ProfessionalReferralUrgency
    complexity: SpecializedComplexity
    professional_review_required: bool
    evidence: dict[str, object]


class TrustSuccessionResponse(BaseModel):
    meta: SpecializedResponseMeta
    need_detected: bool
    outcome: Literal["NO_NEED_DETECTED", "NEED_DETECTED", "EXPERT_REVIEW_REQUIRED"]
    needs: list[TrustSuccessionNeedOut]
    routes: list[ProfessionalRoute]
    boundary: str


class PhilanthropyGoalOut(RecordOut):
    household_id: str
    annual_budget: Money
    target_cause: str
    funding_asset: str | None
    time_horizon: CFSTimeHorizon
    family_participation: str
    governance_preference: str
    professional_review_required: bool


class PhilanthropyGoalsResponse(BaseModel):
    meta: SpecializedResponseMeta
    has_explicit_goal: bool
    goals: list[PhilanthropyGoalOut]
    route: ProfessionalRoute
    boundary: str
