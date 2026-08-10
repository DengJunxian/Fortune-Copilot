from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    ComplexityLevel,
    LiquidityLevel,
    MarketScenario,
    PortfolioCandidateType,
    ProductRiskLevel,
    SuitabilityDecision,
    SuitabilityGateType,
    SuitabilityStatus,
)
from app.schemas.methodology import DecisionEvidencePackage
from app.schemas.records import Money, Ratio


class ProductCatalogItem(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    product_type: str = Field(min_length=1, max_length=80)
    asset_class: str = Field(min_length=1, max_length=48)
    risk_level: ProductRiskLevel
    term_months: int = Field(ge=0, le=1200)
    minimum_holding_months: int = Field(ge=0, le=1200)
    liquidity_level: LiquidityLevel
    redemption_rules: str = Field(min_length=1, max_length=800)
    annual_fee_rate: Ratio
    underlying_assets: list[str] = Field(min_length=1)
    historical_volatility_min: Ratio
    historical_volatility_max: Ratio
    minimum_investment: Money
    suitable_accounts: list[str]
    principal_guaranteed: bool
    guarantee_basis: str | None = Field(default=None, max_length=300)
    guarantee_disclosure: str = Field(min_length=1, max_length=800)
    non_guaranteed_disclosure: str = Field(min_length=1, max_length=800)
    complexity_level: ComplexityLevel
    professional_only: bool
    education_only: bool
    enabled: bool
    is_simulated: bool
    terms: dict[str, object] = Field(default_factory=dict)
    account_wrappers: list[str] = Field(default_factory=lambda: ["ordinary"])
    principal_loss_possible: bool | None = None
    legally_principal_guaranteed: bool | None = None
    liquidity_days: int = Field(default=0, ge=0, le=36500)
    lock_up: bool = False
    withdrawable_date: date | None = None
    volatility: Ratio = Decimal("0")
    sale_status: Literal["available", "unavailable", "education_only"] = "available"
    channel: str = "demo_catalog"
    source_reference: str = "Fortune Copilot internal demo catalog"
    snapshot_version: str = "mock-product-snapshot-v1.0.0"

    @model_validator(mode="after")
    def validate_product_boundaries(self) -> ProductCatalogItem:
        if self.legally_principal_guaranteed is None:
            self.legally_principal_guaranteed = self.principal_guaranteed
        if self.principal_loss_possible is None:
            self.principal_loss_possible = not self.legally_principal_guaranteed
        if self.legally_principal_guaranteed != self.principal_guaranteed:
            raise ValueError("兼容保本字段与法律本金保证标签必须一致")
        if self.legally_principal_guaranteed and self.principal_loss_possible:
            raise ValueError("法律本金保证产品不能同时标记本金可损失")
        if self.historical_volatility_min > self.historical_volatility_max:
            raise ValueError("产品波动区间下限不能高于上限")
        if not self.is_simulated:
            raise ValueError("比赛产品目录只允许明确标记为模拟产品")
        if (
            self.product_type
            in {
                "bank_wealth_management",
                "bond_fund",
                "short_bond_fund",
                "collective_fund_trust",
                "participating_life_insurance",
            }
            and self.principal_guaranteed
        ):
            raise ValueError("银行理财、债券基金、信托和分红险不得统一标记为保本")
        if self.education_only and self.enabled:
            raise ValueError("只读教育条目不得开启交易或自动匹配")
        return self


class ProductCatalogFile(BaseModel):
    catalog_code: str
    catalog_version: str
    data_date: date
    source: str
    source_summary: str
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    is_demo: bool
    lineage: str
    products: list[ProductCatalogItem] = Field(min_length=14)

    @model_validator(mode="after")
    def validate_unique_codes(self) -> ProductCatalogFile:
        codes = [item.code for item in self.products]
        if len(codes) != len(set(codes)):
            raise ValueError("模拟产品代码必须唯一")
        return self


class ProductOut(ProductCatalogItem):
    model_config = ConfigDict(from_attributes=True)

    id: str
    catalog_version: str
    data_date: date
    source: str
    snapshot_observed_at: date


class ProductCatalogResponse(BaseModel):
    catalog_code: str
    catalog_version: str
    data_date: date
    source_type: Literal["mock"] = "mock"
    source_summary: str
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    is_demo: bool
    lineage: str
    product_count: int
    products: list[ProductOut]
    professional_hedge_lab_enabled: bool = False
    snapshot_version: str
    snapshot_observed_at: date
    snapshot_age_days: int
    maximum_age_days: int
    catalog_stale: bool
    executable_recommendations_allowed: bool
    stale_action: Literal["block_executable_allow_education"]


class SuitabilityCheckItem(BaseModel):
    check_code: str
    label: str
    status: SuitabilityStatus
    observed_value: str
    rule: str
    reason: str
    source_record_ids: list[str] = Field(default_factory=list)


class SuitabilityGateResult(BaseModel):
    gate: SuitabilityGateType
    name: str
    status: SuitabilityStatus
    decision: SuitabilityDecision
    effective_risk_limit: ProductRiskLevel | None = None
    high_risk_cap: Ratio | None = None
    checks: list[SuitabilityCheckItem]
    failed_check_codes: list[str]
    explanation: str


class AllocationLine(BaseModel):
    asset_class: str
    asset_class_name: str
    ratio: Ratio
    amount: Money
    expected_nominal_return: Ratio
    cvar_loss: Ratio
    max_drawdown: Ratio
    liquidity_score: Ratio


class ProductMapping(BaseModel):
    asset_class: str
    asset_class_name: str
    allocation_ratio: Ratio
    allocation_amount: Money
    product_id: str | None
    product_code: str | None
    product_name: str
    product_type: str
    risk_level: ProductRiskLevel | None
    liquidity_level: LiquidityLevel | None
    decision: SuitabilityDecision
    reasons: list[str]
    is_mock: bool = True


class OptimizationDiagnostics(BaseModel):
    method: Literal["deterministic_grid_search", "rule_based_fallback"]
    status: Literal["optimal", "fallback", "infeasible"]
    optimizer_version: str
    random_seed: int
    grid_step: Ratio
    evaluated_candidates: int
    objective_score: Decimal
    parameter_hash: str
    parameters: dict[str, object]
    fallback_reason: str | None = None


class RebalanceLine(BaseModel):
    asset_class: str
    asset_class_name: str
    current_ratio: Ratio
    strategic_ratio: Ratio
    tactical_ratio: Ratio
    absolute_drift: Ratio
    relative_drift: Decimal | None = Field(default=None, ge=0)
    trigger: bool
    action: str


class RebalancePlan(BaseModel):
    market_scenario: MarketScenario
    status: Literal["within_band", "rebalance_due", "blocked_by_safety"]
    absolute_threshold: Ratio
    relative_threshold: Ratio
    maximum_tactical_shift: Ratio
    next_scheduled_review: date
    lines: list[RebalanceLine]
    explanation: str


class PortfolioCandidate(BaseModel):
    candidate_type: PortfolioCandidateType
    name: str
    decision: SuitabilityDecision
    investment_amount: Money
    strategic_allocations: list[AllocationLine]
    tactical_allocations: list[AllocationLine]
    expected_nominal_return: Ratio
    expected_real_return: Decimal
    goal_success_probability: Ratio
    simulation_method: Literal["deterministic_weighted_scenarios_not_monte_carlo"]
    simulation_horizon_months: int
    simulated_range_low: Money
    simulated_range_base: Money
    simulated_range_high: Money
    extreme_loss_ratio: Ratio
    extreme_loss_amount: Money
    max_drawdown_estimate: Ratio
    liquidity_score: Ratio
    liquidity_description: str
    annual_fee_rate: Ratio
    annual_fee_estimate: Money
    responsibility_breach_probability: Ratio
    purchasing_power_success_probability: Ratio
    liability_coverage: Ratio
    liquidity_shortfall: Ratio
    concentration: Ratio
    real_return_after_fee: Decimal
    applicable_conditions: list[str]
    primary_risks: list[str]
    why_not_other_candidates: str
    gates: list[SuitabilityGateResult]
    product_mappings: list[ProductMapping]
    optimization: OptimizationDiagnostics
    rebalancing: RebalancePlan


class PortfolioContext(BaseModel):
    current_growth_assets: Money
    eligible_long_term_amount: Money
    amount_to_restore_safety_layers: Money
    long_term_goal_present_value_gap: Money
    simulation_horizon_months: int
    annual_new_surplus: Money
    purchasing_power_hurdle: Ratio
    single_equity_amount: Money
    largest_single_security_ratio: Ratio
    single_equity_hhi: Ratio
    security_concentration_treatment: Literal["satellite_only"] = "satellite_only"
    counting_note: str


class PortfolioMeta(BaseModel):
    household_id: str
    household_code: str
    analysis_date: date
    data_as_of: date
    input_version: str
    formula_version: str
    rule_code: str
    rule_version: str
    optimizer_version: str
    catalog_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    currency: str = "CNY"
    synthetic_data: bool
    market_scenario: MarketScenario
    methodology_version: str
    market_regime_version: str
    product_snapshot_version: str


class EducationCard(BaseModel):
    code: str
    title: str
    summary: str
    points: list[str]


class HedgeLabBoundary(BaseModel):
    enabled: Literal[False] = False
    mode: Literal["read_only_education"] = "read_only_education"
    title: str
    reason: str
    prerequisites: list[str]


class PortfolioResponse(BaseModel):
    meta: PortfolioMeta
    context: PortfolioContext
    family_safety_gate: SuitabilityGateResult
    customer_suitability_gate: SuitabilityGateResult
    candidates: list[PortfolioCandidate] = Field(min_length=3, max_length=3)
    catalog: ProductCatalogResponse
    education_cards: list[EducationCard]
    professional_hedge_lab: HedgeLabBoundary
    decision_evidence: DecisionEvidencePackage
    counting_note: str


class SuitabilityProbeRequest(BaseModel):
    analysis_date: date | None = None
    investment_amount: Money
    target_horizon_months: int = Field(ge=1, le=1200)
    requested_high_risk_ratio: Ratio
    leverage_ratio: Ratio = Decimal("0")
    concentration_ratio: Ratio = Decimal("0")
    requested_product_codes: list[str] = Field(min_length=1, max_length=20)
    purpose: Literal[
        "long_term_growth",
        "tuition",
        "home_purchase",
        "retirement",
        "professional_hedge",
    ]


class SuitabilityProbeResponse(BaseModel):
    household_id: str
    decision: SuitabilityDecision
    gates: list[SuitabilityGateResult]
    failed_check_codes: list[str]
    audit_event_id: str
    rule_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    explanation: str


class PersistedPortfolioRun(BaseModel):
    recommendation_id: str
    portfolio_plan_ids: list[str]
    suitability_check_ids: list[str]
    household_id: str
    input_version: str
    rule_version_id: str
    rule_version: str
    candidate_count: int
    suitability_check_count: int
    created_at: datetime
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
