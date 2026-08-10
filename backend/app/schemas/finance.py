from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    AssetPurposeDimension,
    CashFlowFrequency,
    ComplexityLevel,
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
    purpose_dimension: AssetPurposeDimension | None = None
    account_wrapper: AccountWrapper | None = None
    principal_loss_possible: bool | None = None
    legally_principal_guaranteed: bool | None = None
    lock_up: bool | None = None
    withdrawable_date: date | None = None
    volatility: Ratio = Decimal("0")
    product_complexity: ComplexityLevel = ComplexityLevel.BASIC
    institution_type: str = Field(default="ordinary", min_length=1, max_length=48)
    source_kind: str = Field(default="user_self_report", min_length=1, max_length=40)
    household_role: str = Field(default="household_shared", min_length=1, max_length=40)
    region_code: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def assign_three_dimension_tags(self) -> AssetCreate:
        daily = {
            AssetCategory.CASH,
            AssetCategory.DEMAND_DEPOSIT,
            AssetCategory.MONEY_MARKET,
        }
        growth = {
            AssetCategory.PUBLIC_FUND,
            AssetCategory.EQUITY_FUND,
            AssetCategory.STOCK,
            AssetCategory.TRUST,
            AssetCategory.INVESTMENT_PROPERTY,
        }
        if self.purpose_dimension is None:
            self.purpose_dimension = (
                AssetPurposeDimension.DAILY
                if self.category in daily
                else AssetPurposeDimension.GROWTH
                if self.category in growth
                else AssetPurposeDimension.PROTECTION
                if self.category == AssetCategory.INSURANCE_CASH_VALUE
                else AssetPurposeDimension.STABLE
            )
        if self.account_wrapper is None:
            self.account_wrapper = (
                AccountWrapper.PERSONAL_PENSION
                if self.category == AssetCategory.PENSION_ACCOUNT
                else AccountWrapper.DEMAND_ACCOUNT
                if self.category in {AssetCategory.CASH, AssetCategory.DEMAND_DEPOSIT}
                else AccountWrapper.INSURANCE
                if self.category == AssetCategory.INSURANCE_CASH_VALUE
                else AccountWrapper.ORDINARY
            )
        legal_guarantee = self.category in {
            AssetCategory.DEMAND_DEPOSIT,
            AssetCategory.TIME_DEPOSIT,
        }
        if self.legally_principal_guaranteed is None:
            self.legally_principal_guaranteed = legal_guarantee
        if self.principal_loss_possible is None:
            self.principal_loss_possible = not legal_guarantee
        if self.lock_up is None:
            self.lock_up = self.category == AssetCategory.PENSION_ACCOUNT
        if self.legally_principal_guaranteed and self.principal_loss_possible:
            raise ValueError("法律属性保证本金的资产不能同时标记本金可损失")
        return self


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
    purpose_dimension: AssetPurposeDimension | None = None
    account_wrapper: AccountWrapper | None = None
    principal_loss_possible: bool | None = None
    legally_principal_guaranteed: bool | None = None
    lock_up: bool | None = None
    withdrawable_date: date | None = None
    volatility: Ratio | None = None
    product_complexity: ComplexityLevel | None = None
    institution_type: str | None = Field(default=None, min_length=1, max_length=48)
    source_kind: str | None = Field(default=None, min_length=1, max_length=40)
    household_role: str | None = Field(default=None, min_length=1, max_length=40)
    region_code: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def validate_principal_risk_tags(self) -> AssetUpdate:
        if self.legally_principal_guaranteed is True and self.principal_loss_possible is True:
            raise ValueError("法律属性保证本金的资产不能同时标记本金可损失")
        return self


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
    purpose_dimension: AssetPurposeDimension
    account_wrapper: AccountWrapper
    principal_loss_possible: bool
    legally_principal_guaranteed: bool
    lock_up: bool
    withdrawable_date: date | None
    volatility: Ratio
    product_complexity: ComplexityLevel
    institution_type: str
    source_kind: str
    household_role: str
    region_code: str | None


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
