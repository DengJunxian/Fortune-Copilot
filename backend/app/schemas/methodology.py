from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MethodologyArticleOut(BaseModel):
    code: str
    title: str
    rule: str
    hard: bool


class ThresholdFactorEvidence(BaseModel):
    factor: str
    observed_value: str
    adjustment_amount: Decimal
    explanation: str
    source_record_ids: list[str] = Field(default_factory=list)


class RegionalGrowthThresholdAssessment(BaseModel):
    policy_version: str
    region_code: str
    region_name: str
    city_tier: str
    policy_minimum: Decimal
    recommended_minimum: Decimal
    recommended_maximum: Decimal
    customer_selected_threshold: Decimal
    effective_threshold: Decimal
    explanation: str
    evidence: list[ThresholdFactorEvidence]

    @model_validator(mode="after")
    def enforce_floor_and_band(self) -> RegionalGrowthThresholdAssessment:
        if self.effective_threshold < self.policy_minimum:
            raise ValueError("有效启动线不得低于政策安全底线")
        if self.recommended_minimum > self.recommended_maximum:
            raise ValueError("系统建议区间无效")
        return self


class RegionalMinimumWagePoint(BaseModel):
    date: date
    monthly_amount: Decimal


class RegionalMinimumWageSnapshotOut(BaseModel):
    region_code: str
    region_name: str
    values: list[RegionalMinimumWagePoint]
    cagr: Decimal
    period_years: Decimal
    status: Literal["available", "degraded", "fallback"]
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
    is_cpi: Literal[False] = False


class PurchasingPowerComponent(BaseModel):
    code: Literal[
        "official_cpi_trend",
        "family_weighted_expense_inflation",
        "regional_minimum_wage_cagr",
    ]
    label: str
    rate: Decimal
    data_as_of: date
    source: str
    version: str
    status: Literal["available", "degraded", "fallback"] = "available"
    is_cpi: bool


class PurchasingPowerHurdle(BaseModel):
    version: str
    rate: Decimal
    formula: str
    components: list[PurchasingPowerComponent]
    explanation: str
    minimum_wage_is_cpi: Literal[False] = False
    is_return_guarantee: Literal[False] = False


class MarketRegimeSnapshotOut(BaseModel):
    snapshot_version: str
    regime: Literal["favorable", "neutral", "defensive"]
    label: str
    valuation_date: date
    effective_from: date
    effective_to: date | None
    source: str
    methodology: str
    evidence: list[str]
    rule_version: str
    approved_by: str
    is_demo: bool
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    lineage: str
    customer_editable: Literal[False] = False
    llm_generated: Literal[False] = False


class AssetLiquiditySummary(BaseModel):
    daily_liquid_assets: Decimal
    liquid_stable_assets: Decimal
    withdrawable_institutional_assets: Decimal
    locked_institutional_assets: Decimal
    growth_assets: Decimal
    locked_asset_ids: list[str]
    withdrawable_asset_ids: list[str]
    explanation: str


class ResponsibilityEntry(BaseModel):
    responsibility_id: str
    responsible_member_id: str | None
    beneficiary: str
    responsibility_type: str
    target_amount: Decimal
    minimum_acceptable_amount: Decimal
    target_date: date
    rigidity: str
    deferrable: bool
    annual_growth_assumption: Decimal
    prepared_amount: Decimal
    institutional_coverage: Decimal
    funding_source: str
    source_record_ids: list[str]


class ResponsibilityLedger(BaseModel):
    version: str
    entries: list[ResponsibilityEntry]
    total_target_amount: Decimal
    total_minimum_amount: Decimal
    total_prepared_amount: Decimal
    total_institutional_coverage: Decimal
    explanation: str


class RetirementIncomeFloorCoverage(BaseModel):
    required_annual_floor: Decimal | None
    covered_annual_income: Decimal | None
    coverage_ratio: Decimal | None
    status: Literal["available", "needs_review", "not_applicable"]
    explanation: str


class InstitutionalCoverageSummary(BaseModel):
    version: str
    social_security_balance: Decimal
    provident_fund_balance: Decimal
    enterprise_annuity_balance: Decimal
    occupational_annuity_balance: Decimal
    personal_pension_balance: Decimal
    locked_balance: Decimal
    withdrawable_balance: Decimal
    retirement_income_floor: RetirementIncomeFloorCoverage
    explanation: str


class PensionPolicySnapshotOut(BaseModel):
    policy_version: str
    annual_contribution_limit: Decimal
    withdrawal_tax_rate: Decimal
    effective_from: date
    effective_to: date | None
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


class PensionRiskAllocation(BaseModel):
    asset_id: str
    asset_name: str
    market_value: Decimal
    risk_level: str
    principal_loss_possible: bool
    liquidity_days: int
    lock_up: bool


class PersonalPensionPlan(BaseModel):
    policy: PensionPolicySnapshotOut
    eligibility_status: Literal["eligible", "not_eligible", "needs_review"]
    annual_contribution_amount: Decimal
    contribution_limit: Decimal
    contribution_progress_ratio: Decimal
    remaining_contribution_capacity: Decimal
    assumed_marginal_tax_rate: Decimal
    estimated_current_year_tax_benefit: Decimal
    account_balance: Decimal
    product_risk_allocation: list[PensionRiskAllocation]
    reminder_state: Literal["not_needed", "review_eligibility", "contribution_available"]
    retirement_projection_status: Literal["available", "needs_more_data"]
    explanation: str


class PropertyInvestmentPolicyOut(BaseModel):
    policy_version: str
    status: Literal["restricted_by_default", "review_required", "available"]
    valuation_date: date
    source: str
    is_demo: bool
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    lineage: str
    rules: list[str]


class FinancialJourneyAssessment(BaseModel):
    state: Literal[
        "financial_recovery",
        "wealth_accumulation",
        "wealth_growth",
        "complex_wealth_management",
    ]
    label: str
    investment_mode: Literal[
        "no_investment_sales",
        "safety_and_learning",
        "full_portfolio",
        "human_in_loop",
    ]
    explanation: str


class GRBDecisionState(BaseModel):
    code: Literal["grb"] = "grb"
    version: str
    formula: str
    goal_count: int = Field(ge=0)
    rigid_goal_count: int = Field(ge=0)
    nearest_goal_date: date | None
    goal_status: Literal["ready", "needs_input"]
    goal_summary: str
    risk_status: Literal["ready", "partial", "needs_input"]
    capacity_score: Decimal | None = Field(default=None, ge=0, le=1)
    willingness_score: Decimal | None = Field(default=None, ge=0, le=1)
    effective_risk_limit: str | None
    risk_summary: str
    behavior_status: Literal["ready", "partial", "needs_input"]
    revealed_behavior_score: Decimal | None = Field(default=None, ge=0, le=1)
    detected_biases: list[str]
    behavior_summary: str
    behavior_can_only_downshift: Literal[True] = True
    formal_suitability_required: Literal[True] = True


class MethodologyAssessment(BaseModel):
    framework_code: Literal["chfh"] = "chfh"
    framework_name: Literal["中国家庭财富健康理论"] = "中国家庭财富健康理论"
    optimization_objective: str
    methodology_code: str
    methodology_version: str
    formula_version: str
    public_data_snapshot_version: str
    constitution: list[MethodologyArticleOut]
    regional_threshold: RegionalGrowthThresholdAssessment
    market_regime: MarketRegimeSnapshotOut
    minimum_wage_snapshot: RegionalMinimumWageSnapshotOut
    purchasing_power_hurdle: PurchasingPowerHurdle
    responsibility_ledger: ResponsibilityLedger
    institutional_coverage: InstitutionalCoverageSummary
    personal_pension: PersonalPensionPlan
    property_policy: PropertyInvestmentPolicyOut
    financial_journey: FinancialJourneyAssessment
    grb: GRBDecisionState


class CurrentAllocationPlan(BaseModel):
    denominator_id: Literal["investable_financial_assets"] = "investable_financial_assets"
    current_investable_balance: Decimal
    debt_settlement_from_current_balance: Decimal
    current_balance_available_after_debt: Decimal
    explanation: str


class ContributionPlan(BaseModel):
    denominator_id: Literal["annual_new_surplus"] = "annual_new_surplus"
    annual_new_surplus: Decimal
    recorded_premium_reclassification: Decimal
    same_period_commitments: Decimal
    future_contribution_available: Decimal
    explanation: str


class ProtectionNeedLine(BaseModel):
    risk_code: str
    label: str
    required_coverage: Decimal
    existing_coverage: Decimal
    coverage_gap: Decimal
    annual_premium_cost: Decimal
    status: Literal["covered", "gap", "needs_review", "not_applicable"]
    quote_status: Literal["not_required", "product_quote_required"]
    explanation: str


class ProtectionPlan(BaseModel):
    version: str
    annual_premium_cost: Decimal
    premium_affordability_ratio: Decimal | None
    needs: list[ProtectionNeedLine]
    savings_and_protection_split_required: bool
    explanation: str


class DecisionEvidencePackage(BaseModel):
    evidence_version: str
    household_input_version: str
    methodology_version: str
    financial_rule_version: str
    planning_rule_version: str
    regional_parameter_version: str
    market_regime_version: str
    minimum_wage_snapshot_version: str
    public_data_snapshot_version: str
    pension_policy_version: str
    portfolio_version: str
    product_snapshot_version: str
    risk_assessment_version: str
    behavior_assessment_version: str
    llm_model_version: str | None
    llm_prompt_version: str | None
    hard_gate_results: dict[str, str]
    generated_at: datetime
    decision_hash: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"

    @model_validator(mode="after")
    def require_versions(self) -> DecisionEvidencePackage:
        required = {
            "household_input_version": self.household_input_version,
            "methodology_version": self.methodology_version,
            "financial_rule_version": self.financial_rule_version,
            "planning_rule_version": self.planning_rule_version,
            "regional_parameter_version": self.regional_parameter_version,
            "market_regime_version": self.market_regime_version,
            "minimum_wage_snapshot_version": self.minimum_wage_snapshot_version,
            "public_data_snapshot_version": self.public_data_snapshot_version,
            "pension_policy_version": self.pension_policy_version,
            "portfolio_version": self.portfolio_version,
            "product_snapshot_version": self.product_snapshot_version,
            "risk_assessment_version": self.risk_assessment_version,
            "behavior_assessment_version": self.behavior_assessment_version,
        }
        if any(not value or value == "unknown" for value in required.values()):
            raise ValueError("决策证据包的关键版本必须完整")
        return self
