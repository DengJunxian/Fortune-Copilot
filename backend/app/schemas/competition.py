from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Money = Decimal
Ratio = Decimal
GoalType = Literal[
    "emergency_fund",
    "housing",
    "education",
    "retirement",
    "entrepreneurship",
    "major_purchase",
    "wealth_transfer",
    "other",
]


class PersonalProfile(BaseModel):
    customer_id: str
    name: str
    age: int = Field(ge=18, le=120)
    city: str
    occupation: str
    employment_type: Literal["salaried", "public_sector", "business_owner", "retired", "other"]
    marital_status: Literal["single", "married", "divorced", "widowed"]


class FamilyMember(BaseModel):
    relationship: str
    age: int = Field(ge=0, le=120)
    financially_dependent: bool = False


class FamilyProfile(BaseModel):
    members: list[FamilyMember] = Field(min_length=1)
    dependent_count: int = Field(ge=0)
    has_minor_child: bool
    has_elder_support: bool


class IncomeProfile(BaseModel):
    annual_income: Money = Field(gt=0)
    spouse_annual_income: Money = Field(ge=0)
    passive_annual_income: Money = Field(ge=0)
    stability_score: Ratio = Field(ge=0, le=1)
    concentration_score: Ratio = Field(ge=0, le=1)

    @property
    def household_annual_income(self) -> Decimal:
        return self.annual_income + self.spouse_annual_income + self.passive_annual_income


class ExpenseProfile(BaseModel):
    essential_monthly_expense: Money = Field(gt=0)
    discretionary_monthly_expense: Money = Field(ge=0)
    annual_special_expense: Money = Field(ge=0)

    @property
    def annual_expense(self) -> Decimal:
        return (self.essential_monthly_expense + self.discretionary_monthly_expense) * Decimal(
            "12"
        ) + self.annual_special_expense


class Asset(BaseModel):
    asset_id: str
    name: str
    category: Literal[
        "cash",
        "deposit",
        "fixed_income",
        "fund",
        "equity",
        "pension",
        "insurance_cash_value",
        "primary_residence",
        "investment_property",
        "business_equity",
        "vehicle",
        "other",
    ]
    market_value: Money = Field(ge=0)
    liquidity_days: int = Field(ge=0)
    is_financial_asset: bool
    is_investment_asset: bool
    pledged: bool = False


class Liability(BaseModel):
    liability_id: str
    name: str
    category: Literal["mortgage", "consumer", "auto", "credit_card", "business", "other"]
    outstanding_balance: Money = Field(ge=0)
    annual_interest_rate: Ratio = Field(ge=0, le=1)
    monthly_payment: Money = Field(ge=0)
    remaining_months: int = Field(ge=0)


class Insurance(BaseModel):
    policy_id: str
    name: str
    protection_type: Literal["life", "critical_illness", "medical", "accident", "annuity"]
    coverage_amount: Money = Field(ge=0)
    annual_premium: Money = Field(ge=0)
    insured_relationship: str


class CashFlow(BaseModel):
    annual_income: Money
    annual_expense: Money
    annual_debt_service: Money
    annual_surplus: Money


class RiskProfile(BaseModel):
    tolerance_score: Ratio = Field(ge=0, le=1)
    maximum_acceptable_loss: Ratio = Field(gt=0, le=1)
    investment_knowledge_score: Ratio = Field(ge=0, le=1)
    loss_reaction: Literal["sell_all", "reduce", "hold", "buy_more"]


class BehaviorEvidence(BaseModel):
    signal: Literal[
        "panic_sale",
        "hold_loser",
        "follow_crowd",
        "excessive_trading",
        "recent_return_anchor",
        "chase_top_performer",
    ]
    observation: str
    observed_on: date


class BehaviorProfile(BaseModel):
    evidence: list[BehaviorEvidence] = Field(default_factory=list)


class FinancialGoal(BaseModel):
    goal_id: str
    name: str
    goal_type: GoalType
    target_amount: Money = Field(gt=0)
    target_date: date
    current_assets: Money = Field(ge=0)
    monthly_contribution: Money = Field(ge=0)
    expected_return: Ratio = Field(ge=-1, le=1)
    inflation_rate: Ratio = Field(ge=-1, le=1)
    priority: int = Field(ge=1, le=10)
    success_probability: Ratio | None = Field(default=None, ge=0, le=1)


class ProductHolding(BaseModel):
    holding_id: str
    product_id: str
    product_name: str
    product_type: str
    market_value: Money = Field(ge=0)
    risk_level: int = Field(ge=1, le=5)
    liquidity_days: int = Field(ge=0)


class Portfolio(BaseModel):
    holdings: list[ProductHolding] = Field(default_factory=list)
    total_market_value: Money = Field(ge=0)


class WealthClientModel(BaseModel):
    personal_profile: PersonalProfile
    family_profile: FamilyProfile
    income_profile: IncomeProfile
    expense_profile: ExpenseProfile
    assets: list[Asset] = Field(min_length=1)
    liabilities: list[Liability] = Field(default_factory=list)
    insurance: list[Insurance] = Field(default_factory=list)
    risk_profile: RiskProfile
    behavior_profile: BehaviorProfile
    financial_goals: list[FinancialGoal] = Field(min_length=1)
    portfolio: Portfolio


class FamilyBalanceSheet(BaseModel):
    total_assets: Money
    financial_assets: Money
    total_liabilities: Money
    net_worth: Money
    liquid_assets: Money
    investment_assets: Money
    monthly_cash_flow: Money
    debt_to_income_ratio: Ratio
    emergency_fund_months: Ratio
    asset_concentration: Ratio
    insurance_protection_gap: Money
    accounting_identity: str


class WealthAccount(BaseModel):
    code: Literal["liquidity", "protection", "liability_goal_matching", "growth"]
    chinese_name: str
    target_amount: Money
    share_of_financial_assets: Ratio
    drivers: list[str]
    explanation: str


class GoalPlan(BaseModel):
    goal_id: str
    name: str
    future_value: Money
    projected_assets: Money
    required_monthly_saving: Money
    allocated_monthly_saving: Money
    funding_gap: Money
    success_probability: Ratio
    coordination_status: Literal["funded", "on_track", "resource_constrained"]
    formula_trace: list[str]


class RiskBudget(BaseModel):
    risk_capacity: Ratio
    risk_tolerance: Ratio
    risk_requirement: Ratio
    effective_risk_budget: Ratio
    maximum_portfolio_volatility: Ratio
    maximum_cvar_loss: Ratio
    risk_level: int = Field(ge=1, le=5)
    binding_dimension: Literal["capacity", "tolerance"]
    requirement_conflict: bool
    evidence: list[str]


class QuantAsset(BaseModel):
    asset_class: str
    expected_return: Ratio
    volatility: Ratio = Field(gt=0)
    liquidity_score: Ratio = Field(ge=0, le=1)
    lockup_days: int = Field(ge=0)
    min_weight: Ratio = Field(default=Decimal("0"), ge=0, le=1)
    max_weight: Ratio = Field(default=Decimal("1"), ge=0, le=1)
    risk_budget_share: Ratio | None = Field(default=None, ge=0, le=1)
    market_weight: Ratio = Field(default=Decimal("0"), ge=0, le=1)
    scenarios: list[Ratio] = Field(min_length=5)


class QuantConstraints(BaseModel):
    cash_asset_class: str = "cash_equivalent"
    minimum_cash: Ratio = Field(ge=0, le=1)
    maximum_asset_exposure: Ratio = Field(gt=0, le=1)
    minimum_liquidity_score: Ratio = Field(ge=0, le=1)
    maximum_volatility: Ratio = Field(gt=0, le=1)
    maximum_cvar_loss: Ratio = Field(gt=0, le=1)
    goal_horizon_days: int = Field(gt=0)
    allowed_asset_classes: list[str] = Field(min_length=1)
    long_only: Literal[True] = True
    grid_step: Ratio = Field(default=Decimal("0.05"), gt=0, le=Decimal("0.25"))


class QuantRequest(BaseModel):
    assets: list[QuantAsset] = Field(min_length=2, max_length=8)
    correlation_matrix: list[list[Ratio]]
    risk_free_rate: Ratio = Decimal("0.015")
    target_return: Ratio = Decimal("0.04")
    constraints: QuantConstraints
    black_litterman_views: dict[str, Ratio] = Field(default_factory=dict)
    view_confidences: dict[str, Ratio] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dimensions(self) -> QuantRequest:
        size = len(self.assets)
        if len(self.correlation_matrix) != size or any(
            len(row) != size for row in self.correlation_matrix
        ):
            raise ValueError("correlation_matrix dimensions must match assets")
        names = {item.asset_class for item in self.assets}
        if len(names) != size:
            raise ValueError("asset_class must be unique")
        if self.constraints.cash_asset_class not in names:
            raise ValueError("cash_asset_class must exist in assets")
        return self


class QuantMetrics(BaseModel):
    expected_return: Ratio
    volatility: Ratio
    sharpe_ratio: Ratio
    cvar_loss: Ratio
    max_drawdown: Ratio
    liquidity_score: Ratio


class QuantMethodResult(BaseModel):
    method: Literal["mean_variance", "risk_parity", "cvar", "black_litterman"]
    status: Literal["optimal", "fallback"]
    weights: dict[str, Ratio]
    metrics: QuantMetrics
    objective_value: Ratio
    evaluated_candidates: int
    rejection_counts: dict[str, int]
    binding_constraints: list[str]
    explanation: list[str]


class QuantComparison(BaseModel):
    input_hash: str
    engine_version: str
    selected_method: str
    selection_reason: str
    methods: list[QuantMethodResult]
    immutable_trace: dict[str, object]


class ProductSchema(BaseModel):
    product_id: str
    product_name: str
    product_type: str
    asset_class: str
    risk_level: int = Field(ge=1, le=5)
    expected_return: Ratio
    volatility: Ratio = Field(ge=0)
    liquidity_days: int = Field(ge=0)
    duration_months: int = Field(ge=0)
    minimum_investment: Money = Field(ge=0)
    fees: Ratio = Field(ge=0, le=1)
    suitable_customer: list[int] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    is_demo: Literal[True] = True


class ComplianceCheck(BaseModel):
    product_id: str
    passed: bool
    violations: list[str]
    checked_rules: list[str]


class ProductRecommendation(BaseModel):
    product: ProductSchema
    target_weight: Ratio
    target_amount: Money
    rank_score: Ratio
    compliance: ComplianceCheck
    why_selected: list[str]


class ProductPipeline(BaseModel):
    stages: list[str]
    recommendations: list[ProductRecommendation]
    rejected_products: list[ComplianceCheck]
    suitability_violation_rate: Ratio
    no_executable_product: bool


class BehavioralFinding(BaseModel):
    bias: Literal[
        "loss_aversion",
        "disposition_effect",
        "herding",
        "overconfidence",
        "recency_bias",
        "performance_chasing",
    ]
    evidence: list[str]
    risk: str
    intervention: str


class Citation(BaseModel):
    citation_id: str
    title: str
    source_type: Literal["official_snapshot", "internal_demo"]
    source_uri: str
    excerpt: str


class HumanEscalation(BaseModel):
    required: bool
    triggers: list[str]
    service_level: Literal["routine", "priority", "urgent"]
    next_best_action: str


class CompetitionDemoResponse(BaseModel):
    demo_status: Literal["synthetic_demo"] = "synthetic_demo"
    bank_connection: Literal[False] = False
    client: WealthClientModel
    balance_sheet: FamilyBalanceSheet
    cash_flow: CashFlow
    wealth_accounts: list[WealthAccount]
    goals: list[GoalPlan]
    risk_budget: RiskBudget
    quant: QuantComparison
    product_pipeline: ProductPipeline
    behavior_findings: list[BehavioralFinding]
    citations: list[Citation]
    advisor_summary: list[str]
    rm_copilot: dict[str, object]
    human_escalation: HumanEscalation
    audit: dict[str, object]
