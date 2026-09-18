from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    CFSComponentStatus,
    CFSComponentType,
    CFSSolutionStatus,
    CFSTimeHorizon,
    ProfessionalReferralStatus,
    ProfessionalReferralUrgency,
    ProfessionalSpecialistType,
    RiskLevel,
)
from app.schemas.records import Money, Ratio, RecordOut


class CFSComposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_snapshot_id: str | None = None
    is_user_confirmed: Literal[True]


class RiskBudgetFactor(BaseModel):
    code: Literal[
        "capacity",
        "willingness",
        "behavior",
        "existing_economic_exposure",
        "liquidity",
        "liability_rigidity",
        "time_horizon",
    ]
    label: str
    level: RiskLevel | None = None
    amount: Money = Decimal("0")
    ratio: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=6)
    explanation: str


class HouseholdRiskBudget(BaseModel):
    factors: list[RiskBudgetFactor]
    capacity: RiskLevel
    willingness: RiskLevel
    behavior: RiskLevel
    household_economic_risk_capacity: RiskLevel
    existing_economic_exposure: Money
    economic_exposure_ratio: Ratio
    liquidity_reserve_required: Money
    liquidity_gap: Money
    rigid_liability_target: Money
    rigid_liability_gap: Money
    shortest_time_horizon_days: int | None
    risk_ceiling_ratio: Ratio
    risk_ceiling_amount: Money
    remaining_risk_capacity: Money
    additional_risk_allowed: bool
    decision: Literal["open", "repair_first", "professional_only"]
    constraints: list[str]
    input_hash: str
    version: str
    explanation: str


class CFSSolutionOut(RecordOut):
    household_id: str
    profile_id: str
    source_snapshot_id: str
    solution_version: int
    status: CFSSolutionStatus
    need_set_hash: str
    risk_budget_version: str
    methodology_version: str
    summary: dict[str, Any]
    decision_hash: str


class CFSComponentOut(RecordOut):
    solution_id: str
    wealth_need_id: str | None
    component_type: CFSComponentType
    priority: int
    target_amount: Money
    minimum_amount: Money
    time_horizon: CFSTimeHorizon
    recommended_action: str
    product_mapping_allowed: bool
    professional_review_required: bool
    required_specialist: ProfessionalSpecialistType | None
    status: CFSComponentStatus
    rationale: str
    evidence: dict[str, Any]


class ProfessionalReferralOut(RecordOut):
    household_id: str
    solution_id: str
    component_id: str
    specialist_type: ProfessionalSpecialistType
    trigger_reason: str
    urgency: ProfessionalReferralUrgency
    status: ProfessionalReferralStatus
    due_date: date | None
    evidence: dict[str, Any]


class CFSOrchestrationStep(BaseModel):
    component_id: str
    purpose: str
    allowed_risk: RiskLevel
    deterministic_tool: Literal[
        "financial_health",
        "liability_calendar",
        "protection_planner",
        "pension_planner",
        "planning_waterfall",
        "portfolio_optimizer",
        "family_enterprise",
        "professional_routing",
        "no_action",
    ]
    status: Literal["ready", "blocked", "professional_review"]
    output_summary: str


class CFSResponseMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    source_snapshot_id: str
    rule_version: str
    formula_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    idempotent_replay: bool = False


class CFSSolutionResponse(BaseModel):
    meta: CFSResponseMeta
    solution: CFSSolutionOut
    components: list[CFSComponentOut]
    risk_budget: HouseholdRiskBudget
    orchestration: list[CFSOrchestrationStep]
    referrals: list[ProfessionalReferralOut]


class ProfessionalReferralCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solution_id: str
    component_id: str
    specialist_type: ProfessionalSpecialistType
    trigger_reason: str = Field(min_length=1, max_length=800)
    urgency: ProfessionalReferralUrgency
    due_date: date | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    is_user_confirmed: Literal[True]
