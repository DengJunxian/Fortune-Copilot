from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import (
    ClientProfileStatus,
    ComplexityBand,
    GoalRigidity,
    LifecycleStage,
    PensionStage,
    ProfileTagSeverity,
    RiskLevel,
    ServiceComplexity,
    WealthNeedStatus,
    WealthNeedType,
    WealthTier,
)
from app.schemas.records import Money, Ratio, RecordOut


class ProfileDataGap(BaseModel):
    code: str
    label: str
    detail: str
    action: str


class ProfileTagDraft(BaseModel):
    tag_code: str
    tag_category: str
    value: str
    confidence: Ratio
    severity: ProfileTagSeverity
    source_record_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ProfileCalculation(BaseModel):
    lifecycle_stage: LifecycleStage
    wealth_tier: WealthTier
    service_complexity: ServiceComplexity
    risk_capacity: RiskLevel
    risk_willingness: RiskLevel
    behavior_limit: RiskLevel
    enterprise_dependency_level: ComplexityBand
    cross_border_complexity: ComplexityBand
    succession_complexity: ComplexityBand
    pension_stage: PensionStage
    completeness_score: Ratio
    data_gaps: list[ProfileDataGap]
    profile_hash: str
    source_snapshot_id: str
    status: ClientProfileStatus
    explanation: dict[str, Any]
    tags: list[ProfileTagDraft]
    rule_version: str
    formula_version: str


class ClientWealthProfileOut(RecordOut):
    household_id: str
    profile_version: int
    source_snapshot_id: str
    rule_version: str
    formula_version: str
    lifecycle_stage: LifecycleStage
    wealth_tier: WealthTier
    service_complexity: ServiceComplexity
    risk_capacity: RiskLevel
    risk_willingness: RiskLevel
    behavior_limit: RiskLevel
    enterprise_dependency_level: ComplexityBand
    cross_border_complexity: ComplexityBand
    succession_complexity: ComplexityBand
    pension_stage: PensionStage
    completeness_score: Ratio
    data_gaps: list[ProfileDataGap]
    profile_hash: str
    status: ClientProfileStatus
    explanation: dict[str, Any]


class ClientProfileTagOut(RecordOut):
    household_id: str
    profile_id: str
    tag_code: str
    tag_category: str
    value: str
    confidence: Ratio
    severity: ProfileTagSeverity
    source_record_ids: list[str]
    evidence: dict[str, Any]


class ClientProfileMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    input_version: int
    source_snapshot_id: str
    rule_version: str
    formula_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    synthetic_data: bool


class ClientProfileResponse(BaseModel):
    meta: ClientProfileMeta
    profile: ClientWealthProfileOut
    tags: list[ClientProfileTagOut]


class WealthNeedDraft(BaseModel):
    need_type: WealthNeedType
    beneficiary_entity_id: str | None = None
    target_amount: Money
    minimum_amount: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    start_date: date
    end_date: date | None = None
    rigidity: GoalRigidity
    priority: int = Field(ge=1)
    status: WealthNeedStatus
    confidence: Ratio
    professional_review_required: bool
    source_kind: str
    source_record_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    hard_constraint: bool
    priority_score: Ratio
    priority_reason: str


class WealthNeedOut(RecordOut):
    household_id: str
    profile_id: str
    need_type: WealthNeedType
    beneficiary_entity_id: str | None
    target_amount: Money
    minimum_amount: Money
    start_date: date
    end_date: date | None
    rigidity: GoalRigidity
    priority: int
    status: WealthNeedStatus
    confidence: Ratio
    professional_review_required: bool
    source_kind: str
    source_record_ids: list[str]
    evidence: dict[str, Any]


class WealthNeedPriorityOut(RecordOut):
    household_id: str
    wealth_need_id: str
    priority_rank: int
    hard_constraint: bool
    priority_score: Ratio
    reason: str
    rule_version: str


class WealthNeedsMeta(BaseModel):
    household_id: str
    profile_id: str
    profile_hash: str
    analysis_date: date
    data_as_of: date | None
    rule_version: str
    formula_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    professional_review_count: int = Field(ge=0)


class WealthNeedsResponse(BaseModel):
    meta: WealthNeedsMeta
    needs: list[WealthNeedOut]
    priorities: list[WealthNeedPriorityOut]


def quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))
