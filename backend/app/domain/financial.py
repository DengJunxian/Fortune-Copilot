from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import (
    AssetCategory,
    CashFlowFrequency,
    EmploymentStability,
    ExpenseCategory,
    ExpenseNecessity,
    GoalRigidity,
    GoalType,
    IncomeType,
    InsuranceType,
    LiabilityCategory,
    LifecycleStage,
    LiquidityLevel,
    PropertyUse,
    RateType,
    RiskLevel,
)


@dataclass(frozen=True, slots=True)
class MemberFact:
    id: str
    display_name: str
    relationship: str
    birth_date: date
    occupation: str | None
    employment_stability: EmploymentStability
    expected_retirement_age: int | None
    health_risk_level: RiskLevel
    version: int


@dataclass(frozen=True, slots=True)
class IncomeFact:
    id: str
    member_id: str | None
    name: str
    income_type: IncomeType
    amount: Decimal
    frequency: CashFlowFrequency
    stability: Decimal
    volatility: Decimal
    interruption_probability: Decimal
    cycle_correlation: Decimal
    source_concentration: Decimal
    is_sustainable: bool
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class ExpenseFact:
    id: str
    member_id: str | None
    name: str
    amount: Decimal
    frequency: CashFlowFrequency
    necessity: ExpenseNecessity
    compressible_ratio: Decimal
    category: ExpenseCategory
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class AssetFact:
    id: str
    name: str
    category: AssetCategory
    subcategory: str | None
    acquisition_cost: Decimal
    market_value: Decimal
    liquidity_days: int
    liquidity_level: LiquidityLevel
    risk_level: RiskLevel
    purpose: str
    pledged: bool
    property_use: PropertyUse
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class LiabilityFact:
    id: str
    name: str
    category: LiabilityCategory
    outstanding_balance: Decimal
    annual_interest_rate: Decimal
    monthly_payment: Decimal
    maturity_date: date | None
    rate_type: RateType
    prepayment_cost: Decimal
    linked_asset_id: str | None
    is_high_interest: bool
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class InsuranceFact:
    id: str
    insured_member_id: str
    name: str
    policy_type: InsuranceType
    coverage_amount: Decimal
    annual_premium: Decimal
    start_date: date
    end_date: date | None
    deductible: Decimal
    waiting_period_days: int
    guaranteed_benefit: Decimal
    non_guaranteed_benefit: Decimal
    cash_value: Decimal
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class SocialSecurityFact:
    id: str
    member_id: str
    account_type: str
    balance: Decimal
    annual_personal_contribution: Decimal
    annual_employer_contribution: Decimal
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class GoalFact:
    id: str
    name: str
    goal_type: GoalType
    target_amount: Decimal
    target_date: date
    rigidity: GoalRigidity
    priority: int
    can_defer: bool
    minimum_acceptable_amount: Decimal
    prepared_amount: Decimal
    annual_cost_growth_rate: Decimal
    valuation_date: date | None
    version: int


@dataclass(frozen=True, slots=True)
class RiskAssessmentFact:
    id: str
    capacity_score: Decimal
    willingness_score: Decimal
    knowledge_score: Decimal
    behavior_score: Decimal
    final_risk_limit: RiskLevel
    version: int


@dataclass(frozen=True, slots=True)
class BehaviorAssessmentFact:
    id: str
    questionnaire_score: Decimal
    experiment_score: Decimal
    final_behavior_limit: RiskLevel
    detected_biases: tuple[str, ...]
    version: int


@dataclass(frozen=True, slots=True)
class HouseholdFacts:
    id: str
    code: str
    name: str
    lifecycle_stage: LifecycleStage
    region: str
    currency: str
    data_source: str
    is_user_confirmed: bool
    is_synthetic: bool
    version: int
    planning_preferences: dict[str, object]
    members: tuple[MemberFact, ...]
    incomes: tuple[IncomeFact, ...]
    expenses: tuple[ExpenseFact, ...]
    assets: tuple[AssetFact, ...]
    liabilities: tuple[LiabilityFact, ...]
    insurance_policies: tuple[InsuranceFact, ...]
    social_security_accounts: tuple[SocialSecurityFact, ...]
    goals: tuple[GoalFact, ...]
    risk_assessments: tuple[RiskAssessmentFact, ...]
    behavior_assessments: tuple[BehaviorAssessmentFact, ...]
