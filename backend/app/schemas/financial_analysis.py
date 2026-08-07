from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

MetricStatus = Literal[
    "strong",
    "healthy",
    "attention",
    "warning",
    "critical",
    "review",
    "not_applicable",
]
DiagnosticSeverity = Literal["info", "attention", "warning", "critical"]
ThresholdSourceType = Literal["official_rule", "industry_reference", "internal_demo"]


class AnalysisMeta(BaseModel):
    household_id: str
    household_code: str
    analysis_date: date
    data_as_of: date
    input_version: str
    formula_version: str
    rule_code: str
    rule_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    currency: str
    synthetic_data: bool


class MemberSummary(BaseModel):
    id: str
    display_name: str
    relationship: str
    age: int
    occupation: str | None
    employment_stability: str
    health_risk_level: str


class HouseholdProfile(BaseModel):
    name: str
    lifecycle_stage: str
    region: str
    members: list[MemberSummary]
    data_source: str
    is_user_confirmed: bool


class AssetStatementLine(BaseModel):
    id: str
    name: str
    category: str
    subcategory: str | None
    asset_group: str
    market_value: Decimal
    acquisition_cost: Decimal
    unrealized_change: Decimal
    liquidity_days: int
    liquidity_level: str
    property_use: str
    pledged: bool
    valuation_date: date | None


class LiabilityStatementLine(BaseModel):
    id: str
    name: str
    category: str
    outstanding_balance: Decimal
    annual_interest_rate: Decimal
    monthly_payment: Decimal
    scheduled_twelve_month_payment: Decimal
    maturity_date: date | None
    rate_type: str
    linked_asset_id: str | None
    is_high_interest: bool


class BalanceSheet(BaseModel):
    assets: list[AssetStatementLine]
    liabilities: list[LiabilityStatementLine]
    asset_totals_by_group: dict[str, Decimal]
    liability_totals_by_category: dict[str, Decimal]
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    accounting_identity: str


class CashFlowLine(BaseModel):
    id: str
    name: str
    category: str
    frequency: str
    original_amount: Decimal
    annual_amount: Decimal
    essential: bool
    compressible_amount: Decimal


class CashFlowStatement(BaseModel):
    income_lines: list[CashFlowLine]
    expense_lines: list[CashFlowLine]
    income_totals_by_type: dict[str, Decimal]
    expense_totals_by_category: dict[str, Decimal]
    annual_income: Decimal
    annual_expenses: Decimal
    annual_surplus: Decimal
    annual_basic_living_expenses: Decimal
    annual_essential_expenses: Decimal
    annual_fixed_expenses: Decimal
    annual_debt_service: Decimal
    annual_insurance_premiums: Decimal


class InsuranceStatementLine(BaseModel):
    id: str
    name: str
    policy_type: str
    insured_member_id: str
    insured_member_name: str
    coverage_amount: Decimal
    annual_premium: Decimal
    deductible: Decimal
    waiting_period_days: int
    start_date: date
    end_date: date | None
    guaranteed_benefit: Decimal
    non_guaranteed_benefit: Decimal
    cash_value: Decimal
    active_on_analysis_date: bool


class InsuranceStatement(BaseModel):
    policies: list[InsuranceStatementLine]
    coverage_by_policy_type: dict[str, Decimal]
    total_annual_premium: Decimal
    total_cash_value: Decimal
    counting_note: str


class GoalFundingLine(BaseModel):
    id: str
    name: str
    goal_type: str
    target_amount: Decimal
    target_date: date
    years_remaining: Decimal
    rigidity: str
    priority: int
    can_defer: bool
    minimum_acceptable_amount: Decimal
    prepared_amount: Decimal
    funding_gap: Decimal
    funding_ratio: Decimal | None
    annual_cost_growth_rate: Decimal


class GoalFundingStatement(BaseModel):
    goals: list[GoalFundingLine]
    total_target_amount: Decimal
    total_prepared_amount: Decimal
    total_funding_gap: Decimal


class LiquidityLine(BaseModel):
    asset_id: str
    name: str
    category: str
    market_value: Decimal
    liquidity_days: int
    liquidity_level: str
    liquidity_tier: str
    included_in_emergency_reserve: bool
    included_in_short_term_coverage: bool


class LiquidityMatrix(BaseModel):
    lines: list[LiquidityLine]
    totals_by_tier: dict[str, Decimal]
    emergency_liquid_assets: Decimal
    short_term_liquid_assets: Decimal
    twelve_month_liquid_assets: Decimal


class FinancialStatements(BaseModel):
    balance_sheet: BalanceSheet
    cash_flow: CashFlowStatement
    insurance: InsuranceStatement
    goal_funding: GoalFundingStatement
    liquidity: LiquidityMatrix


class MetricInput(BaseModel):
    key: str
    label: str
    value: Decimal
    unit: str
    source_record_ids: list[str] = Field(default_factory=list)


class MetricApplicability(BaseModel):
    applicable: bool
    reason: str


class ThresholdReference(BaseModel):
    reference_range: str
    source_type: ThresholdSourceType
    source_reference: str
    parameters: dict[str, str]


class MetricResult(BaseModel):
    metric_id: str
    name: str
    formula: str
    substitution: str
    inputs: list[MetricInput]
    result: Decimal | None
    numerator: Decimal | None
    denominator: Decimal | None
    unit: str
    threshold_version: str
    status: MetricStatus
    explanation_key: str
    data_as_of: date
    source_type: Literal["deterministic_derived"] = "deterministic_derived"
    applicability: MetricApplicability
    reference: ThresholdReference
    explanation: str
    actions: list[str] = Field(min_length=1)


class DiagnosticIssue(BaseModel):
    code: str
    severity: DiagnosticSeverity
    title: str
    detail: str
    related_record_ids: list[str] = Field(default_factory=list)
    action: str


class DataDiagnostics(BaseModel):
    completeness_score: Decimal
    passed_checks: int
    issue_count: int
    issues: list[DiagnosticIssue]


class ProtectionRisk(BaseModel):
    risk_code: str
    name: str
    required_amount: Decimal
    existing_coverage: Decimal
    coverage_ratio: Decimal | None
    gap: Decimal
    priority: int
    basis: str


class ProtectionAssessment(BaseModel):
    risks: list[ProtectionRisk]
    most_significant_risk: str
    coverage_ratio: Decimal | None
    protection_gap: Decimal
    annual_premium: Decimal
    premium_to_income_ratio: Decimal | None
    payment_pressure: str
    counting_note: str


class PurchasingPowerFactor(BaseModel):
    code: str
    name: str
    rate: Decimal
    source_type: ThresholdSourceType
    source_reference: str
    data_as_of: date
    note: str


class GoalCostFactor(BaseModel):
    goal_id: str
    goal_name: str
    goal_type: str
    annual_cost_growth_rate: Decimal
    target_date: date


class PurchasingPowerAssessment(BaseModel):
    official_cpi: PurchasingPowerFactor
    family_weighted_inflation: PurchasingPowerFactor
    goal_specific_cost_growth: list[GoalCostFactor]
    minimum_wage_catch_up: PurchasingPowerFactor
    minimum_wage_is_cpi: Literal[False] = False
    minimum_wage_is_return_guarantee: Literal[False] = False


class HealthDimension(BaseModel):
    code: str
    name: str
    score: Decimal = Field(ge=0, le=100)
    metric_ids: list[str]
    explanation: str
    is_regulatory_rating: Literal[False] = False


class FinancialAnalysisResponse(BaseModel):
    meta: AnalysisMeta
    profile: HouseholdProfile
    statements: FinancialStatements
    metrics: list[MetricResult]
    diagnostics: DataDiagnostics
    protection: ProtectionAssessment
    purchasing_power: PurchasingPowerAssessment
    health_dimensions: list[HealthDimension] = Field(min_length=7, max_length=7)


class StatementsResponse(BaseModel):
    meta: AnalysisMeta
    profile: HouseholdProfile
    statements: FinancialStatements


class MetricsResponse(BaseModel):
    meta: AnalysisMeta
    metrics: list[MetricResult]
    health_dimensions: list[HealthDimension] = Field(min_length=7, max_length=7)


class DiagnosticsResponse(BaseModel):
    meta: AnalysisMeta
    diagnostics: DataDiagnostics
    protection: ProtectionAssessment
    purchasing_power: PurchasingPowerAssessment


class PersistedAnalysisRun(BaseModel):
    snapshot_id: str
    household_id: str
    input_version: str
    rule_version_id: str
    rule_version: str
    metric_count: int
    created_at: datetime
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
