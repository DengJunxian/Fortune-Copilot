from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    CFSComponentType,
    ComplexityLevel,
    LiquidityLevel,
    ProductEligibilityDecision,
    ProductFamily,
    ProductRiskLevel,
)
from app.schemas.records import Money, Ratio, RecordOut


class ProductSnapshotOut(RecordOut):
    product_id: str
    as_of_date: date
    sale_status: str
    risk_level: ProductRiskLevel
    fee_snapshot: dict[str, Any]
    liquidity_snapshot: dict[str, Any]
    terms_snapshot: dict[str, Any]
    channel: str
    source_reference: str
    evidence: list[dict[str, Any]]
    snapshot_hash: str
    snapshot_version: str


class ProductOntologyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    issuer: str
    jurisdiction: str
    currency: str
    product_family: ProductFamily
    product_subtype: str
    asset_class: str
    risk_level: ProductRiskLevel
    liquidity_level: LiquidityLevel
    minimum_investment: Money
    minimum_holding_months: int
    redemption_rules: str
    all_in_cost: Ratio | None
    distribution_incentive_disclosure: str
    conflict_of_interest_flag: bool
    professional_review_required: bool
    client_role_in_cfs: list[str]
    account_wrappers: list[str]
    complexity_level: ComplexityLevel
    principal_loss_possible: bool
    legally_principal_guaranteed: bool
    enabled: bool
    classification_version: str
    evidence_json: dict[str, Any]


class SnapshotFreshness(BaseModel):
    as_of_date: date
    age_days: int
    maximum_age_days: int
    stale: bool
    sale_status: str
    executable: bool


class ProductDetailResponse(BaseModel):
    product: ProductOntologyItem
    snapshot: ProductSnapshotOut
    freshness: SnapshotFreshness
    execution_boundary: str


class ProductSearchResponse(BaseModel):
    query: str | None
    taxonomy_version: str
    catalog_version: str
    catalog_as_of: date
    catalog_stale: bool
    executable_recommendations_allowed: bool
    product_count: int
    products: list[ProductOntologyItem]
    execution_boundary: str


class ProductRiskBudgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_risk_level: ProductRiskLevel
    additional_risk_allowed: bool
    remaining_capacity: Money = Decimal("0")


class ProductEligibilityContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    need: str = Field(min_length=1, max_length=80)
    risk_budget: ProductRiskBudgetInput
    account_wrapper: str = Field(default="ordinary", min_length=1, max_length=48)
    horizon_days: int = Field(ge=0, le=36500)
    maximum_lockup_days: int = Field(ge=0, le=36500)
    client_qualification: Literal["retail", "professional"] = "retail"
    channel: str = Field(default="icbc", min_length=1, max_length=64)
    analysis_date: date
    maximum_snapshot_age_days: int = Field(default=45, ge=1, le=366)
    product_mapping_allowed: bool = True
    existing_issuer_exposure: dict[str, Ratio] = Field(default_factory=dict)


class ProductEligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    context: ProductEligibilityContext


class ProductEligibilityResponse(BaseModel):
    product_id: str
    product_code: str
    snapshot_id: str
    decision: ProductEligibilityDecision
    eligible: bool
    executable: bool
    reasons: list[str]
    restrictions: list[str]
    freshness: SnapshotFreshness


class ProductRankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ProductEligibilityContext
    product_ids: list[str] = Field(default_factory=list, max_length=100)
    maximum_candidates: int = Field(default=3, ge=1, le=10)


class ProductScoreBreakdown(BaseModel):
    need_fit: Decimal
    hard_eligibility: Decimal
    liquidity_fit: Decimal
    risk_fit: Decimal
    goal_horizon_fit: Decimal
    all_in_cost: Decimal
    diversification: Decimal
    issuer_concentration: Decimal
    operational_simplicity: Decimal
    conflict_penalty: Decimal


class RankedProductCandidate(BaseModel):
    rank: int
    product: ProductOntologyItem
    snapshot: ProductSnapshotOut
    eligibility: ProductEligibilityResponse
    score: Decimal
    score_breakdown: ProductScoreBreakdown
    why_selected: list[str]
    why_not_other_candidates: list[str]


class ExcludedProductCandidate(BaseModel):
    product_id: str
    product_code: str
    product_name: str
    decision: ProductEligibilityDecision
    reasons: list[str]


class ProductFunnelStage(BaseModel):
    code: Literal[
        "sample_pool",
        "need_fit",
        "horizon_fit",
        "risk_suitability",
        "liquidity_fit",
        "quality_filters",
        "final_candidates",
    ]
    label: str
    count: int = Field(ge=0)


class ProductCandidateFunnel(BaseModel):
    stages: list[ProductFunnelStage] = Field(min_length=7, max_length=7)
    calculation_source: Literal["deterministic_product_engine"] = (
        "deterministic_product_engine"
    )
    explanation: str


class ProductRankResponse(BaseModel):
    result: Literal["ranked", "no_product"]
    need: str
    candidate_count: int
    candidates: list[RankedProductCandidate]
    excluded: list[ExcludedProductCandidate]
    funnel: ProductCandidateFunnel
    catalog_as_of: date
    catalog_stale: bool
    executable_recommendation_allowed: bool
    no_product_reason: str | None = None
    ranking_version: str = "buy-side-ranking-v1"
    execution_boundary: str


class CFSProductCandidateGroup(BaseModel):
    component_id: str
    component_type: CFSComponentType
    purpose: str
    result: Literal["ranked", "no_product"]
    candidates: list[RankedProductCandidate]
    excluded: list[ExcludedProductCandidate]
    funnel: ProductCandidateFunnel | None = None
    no_product_reason: str | None = None


class CFSProductCompositionResponse(BaseModel):
    household_id: str
    solution_id: str
    analysis_date: date
    catalog_as_of: date
    catalog_stale: bool
    executable_recommendation_allowed: bool
    groups: list[CFSProductCandidateGroup]
    execution_boundary: str
