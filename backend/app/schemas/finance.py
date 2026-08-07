from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import Field, model_validator

from app.domain.enums import (
    AssetCategory,
    CashFlowFrequency,
    ExpenseCategory,
    ExpenseNecessity,
    GoalRigidity,
    GoalType,
    IncomeType,
    InsuranceType,
    LiabilityCategory,
    LiquidityLevel,
    PropertyUse,
    RateType,
    RiskLevel,
)
from app.schemas.records import (
    Money,
    Ratio,
    RecordInput,
    RecordOut,
    RecordUpdate,
    SignedRatio,
)


class IncomeSourceCreate(RecordInput):
    member_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    income_type: IncomeType = IncomeType.OTHER
    amount: Money
    frequency: CashFlowFrequency
    stability: Ratio
    volatility: Ratio
    interruption_probability: Ratio
    cycle_correlation: SignedRatio
    source_concentration: Ratio
    is_sustainable: bool = True


class IncomeSourceUpdate(RecordUpdate):
    member_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    income_type: IncomeType | None = None
    amount: Money | None = None
    frequency: CashFlowFrequency | None = None
    stability: Ratio | None = None
    volatility: Ratio | None = None
    interruption_probability: Ratio | None = None
    cycle_correlation: SignedRatio | None = None
    source_concentration: Ratio | None = None
    is_sustainable: bool | None = None


class IncomeSourceOut(RecordOut):
    household_id: str
    member_id: str | None
    name: str
    income_type: IncomeType
    amount: Money
    frequency: CashFlowFrequency
    stability: Ratio
    volatility: Ratio
    interruption_probability: Ratio
    cycle_correlation: SignedRatio
    source_concentration: Ratio
    is_sustainable: bool


class ExpenseItemCreate(RecordInput):
    member_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    amount: Money
    frequency: CashFlowFrequency
    necessity: ExpenseNecessity
    compressible_ratio: Ratio
    seasonality: dict[str, Any] = Field(default_factory=dict)
    category: ExpenseCategory


class ExpenseItemUpdate(RecordUpdate):
    member_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Money | None = None
    frequency: CashFlowFrequency | None = None
    necessity: ExpenseNecessity | None = None
    compressible_ratio: Ratio | None = None
    seasonality: dict[str, Any] | None = None
    category: ExpenseCategory | None = None


class ExpenseItemOut(RecordOut):
    household_id: str
    member_id: str | None
    name: str
    amount: Money
    frequency: CashFlowFrequency
    necessity: ExpenseNecessity
    compressible_ratio: Ratio
    seasonality: dict[str, Any]
    category: ExpenseCategory


class AssetCreate(RecordInput):
    owner_member_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    category: AssetCategory
    subcategory: str | None = Field(default=None, max_length=80)
    acquisition_cost: Money
    market_value: Money
    liquidity_days: int = Field(ge=0, le=36500)
    liquidity_level: LiquidityLevel
    risk_level: RiskLevel
    purpose: str = Field(min_length=1, max_length=160)
    pledged: bool = False
    ownership: str = Field(min_length=1, max_length=80)
    property_use: PropertyUse = PropertyUse.NOT_PROPERTY


class AssetUpdate(RecordUpdate):
    owner_member_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: AssetCategory | None = None
    subcategory: str | None = Field(default=None, max_length=80)
    acquisition_cost: Money | None = None
    market_value: Money | None = None
    liquidity_days: int | None = Field(default=None, ge=0, le=36500)
    liquidity_level: LiquidityLevel | None = None
    risk_level: RiskLevel | None = None
    purpose: str | None = Field(default=None, min_length=1, max_length=160)
    pledged: bool | None = None
    ownership: str | None = Field(default=None, min_length=1, max_length=80)
    property_use: PropertyUse | None = None


class AssetOut(RecordOut):
    household_id: str
    owner_member_id: str | None
    name: str
    category: AssetCategory
    subcategory: str | None
    acquisition_cost: Money
    market_value: Money
    liquidity_days: int
    liquidity_level: LiquidityLevel
    risk_level: RiskLevel
    purpose: str
    pledged: bool
    ownership: str
    property_use: PropertyUse


class LiabilityCreate(RecordInput):
    borrower_member_id: str | None = None
    linked_asset_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    category: LiabilityCategory
    outstanding_balance: Money
    annual_interest_rate: Ratio
    monthly_payment: Money
    maturity_date: date | None = None
    rate_type: RateType
    prepayment_cost: Money
    is_high_interest: bool = False


class LiabilityUpdate(RecordUpdate):
    borrower_member_id: str | None = None
    linked_asset_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: LiabilityCategory | None = None
    outstanding_balance: Money | None = None
    annual_interest_rate: Ratio | None = None
    monthly_payment: Money | None = None
    maturity_date: date | None = None
    rate_type: RateType | None = None
    prepayment_cost: Money | None = None
    is_high_interest: bool | None = None


class LiabilityOut(RecordOut):
    household_id: str
    borrower_member_id: str | None
    linked_asset_id: str | None
    name: str
    category: LiabilityCategory
    outstanding_balance: Money
    annual_interest_rate: Ratio
    monthly_payment: Money
    maturity_date: date | None
    rate_type: RateType
    prepayment_cost: Money
    is_high_interest: bool


class InsurancePolicyCreate(RecordInput):
    insured_member_id: str
    name: str = Field(min_length=1, max_length=160)
    policy_type: InsuranceType
    coverage_amount: Money
    annual_premium: Money
    start_date: date
    end_date: date | None = None
    deductible: Money
    waiting_period_days: int = Field(ge=0, le=3650)
    guaranteed_benefit: Money
    non_guaranteed_benefit: Money
    cash_value: Money

    @model_validator(mode="after")
    def validate_term(self) -> InsurancePolicyCreate:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("保险终止日期不得早于生效日期")
        return self


class InsurancePolicyUpdate(RecordUpdate):
    insured_member_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    policy_type: InsuranceType | None = None
    coverage_amount: Money | None = None
    annual_premium: Money | None = None
    start_date: date | None = None
    end_date: date | None = None
    deductible: Money | None = None
    waiting_period_days: int | None = Field(default=None, ge=0, le=3650)
    guaranteed_benefit: Money | None = None
    non_guaranteed_benefit: Money | None = None
    cash_value: Money | None = None


class InsurancePolicyOut(RecordOut):
    household_id: str
    insured_member_id: str
    name: str
    policy_type: InsuranceType
    coverage_amount: Money
    annual_premium: Money
    start_date: date
    end_date: date | None
    deductible: Money
    waiting_period_days: int
    guaranteed_benefit: Money
    non_guaranteed_benefit: Money
    cash_value: Money


class FinancialGoalCreate(RecordInput):
    name: str = Field(min_length=1, max_length=160)
    goal_type: GoalType
    target_amount: Money
    target_date: date
    rigidity: GoalRigidity
    priority: int = Field(ge=1, le=100)
    can_defer: bool = False
    minimum_acceptable_amount: Money
    prepared_amount: Money
    annual_cost_growth_rate: Ratio

    @model_validator(mode="after")
    def validate_amounts(self) -> FinancialGoalCreate:
        if self.minimum_acceptable_amount > self.target_amount:
            raise ValueError("最低可接受金额不得高于目标金额")
        return self


class FinancialGoalUpdate(RecordUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    goal_type: GoalType | None = None
    target_amount: Money | None = None
    target_date: date | None = None
    rigidity: GoalRigidity | None = None
    priority: int | None = Field(default=None, ge=1, le=100)
    can_defer: bool | None = None
    minimum_acceptable_amount: Money | None = None
    prepared_amount: Money | None = None
    annual_cost_growth_rate: Ratio | None = None


class FinancialGoalOut(RecordOut):
    household_id: str
    name: str
    goal_type: GoalType
    target_amount: Money
    target_date: date
    rigidity: GoalRigidity
    priority: int
    can_defer: bool
    minimum_acceptable_amount: Money
    prepared_amount: Money
    annual_cost_growth_rate: Ratio


class SocialSecurityAccountCreate(RecordInput):
    member_id: str
    account_type: str = Field(min_length=1, max_length=64)
    balance: Money
    annual_personal_contribution: Money
    annual_employer_contribution: Money
    benefit_region: str = Field(min_length=1, max_length=120)
