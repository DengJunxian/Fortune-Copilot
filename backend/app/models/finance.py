from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

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
from app.models.base import Base
from app.models.common import RecordMixin

MONEY = Numeric(20, 2)
RATIO = Numeric(9, 6)


class IncomeSource(RecordMixin, Base):
    __tablename__ = "income_sources"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    income_type: Mapped[IncomeType] = mapped_column(
        Enum(IncomeType, native_enum=False, length=32),
        default=IncomeType.OTHER,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    frequency: Mapped[CashFlowFrequency] = mapped_column(
        Enum(CashFlowFrequency, native_enum=False, length=16), nullable=False
    )
    stability: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    volatility: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    interruption_probability: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    cycle_correlation: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    source_concentration: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    is_sustainable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExpenseItem(RecordMixin, Base):
    __tablename__ = "expense_items"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    frequency: Mapped[CashFlowFrequency] = mapped_column(
        Enum(CashFlowFrequency, native_enum=False, length=16), nullable=False
    )
    necessity: Mapped[ExpenseNecessity] = mapped_column(
        Enum(ExpenseNecessity, native_enum=False, length=16), nullable=False
    )
    compressible_ratio: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    seasonality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, native_enum=False, length=32), nullable=False
    )


class Asset(RecordMixin, Base):
    __tablename__ = "assets"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[AssetCategory] = mapped_column(
        Enum(AssetCategory, native_enum=False, length=40), nullable=False
    )
    subcategory: Mapped[str | None] = mapped_column(String(80), nullable=True)
    acquisition_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    market_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    liquidity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    liquidity_level: Mapped[LiquidityLevel] = mapped_column(
        Enum(LiquidityLevel, native_enum=False, length=24), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    pledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ownership: Mapped[str] = mapped_column(String(80), nullable=False)
    property_use: Mapped[PropertyUse] = mapped_column(
        Enum(PropertyUse, native_enum=False, length=24),
        default=PropertyUse.NOT_PROPERTY,
        nullable=False,
    )


class Liability(RecordMixin, Base):
    __tablename__ = "liabilities"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    borrower_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    linked_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[LiabilityCategory] = mapped_column(
        Enum(LiabilityCategory, native_enum=False, length=32), nullable=False
    )
    outstanding_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_interest_rate: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    monthly_payment: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rate_type: Mapped[RateType] = mapped_column(
        Enum(RateType, native_enum=False, length=16), nullable=False
    )
    prepayment_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    is_high_interest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class InsurancePolicy(RecordMixin, Base):
    __tablename__ = "insurance_policies"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insured_member_id: Mapped[str] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    policy_type: Mapped[InsuranceType] = mapped_column(
        Enum(InsuranceType, native_enum=False, length=24), nullable=False
    )
    coverage_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_premium: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deductible: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    waiting_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    guaranteed_benefit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    non_guaranteed_benefit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cash_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class SocialSecurityAccount(RecordMixin, Base):
    __tablename__ = "social_security_accounts"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(64), nullable=False)
    balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_personal_contribution: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_employer_contribution: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    benefit_region: Mapped[str] = mapped_column(String(120), nullable=False)


class FinancialGoal(RecordMixin, Base):
    __tablename__ = "financial_goals"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    goal_type: Mapped[GoalType] = mapped_column(
        Enum(GoalType, native_enum=False, length=32), nullable=False
    )
    target_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    rigidity: Mapped[GoalRigidity] = mapped_column(
        Enum(GoalRigidity, native_enum=False, length=16), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    can_defer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimum_acceptable_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    prepared_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    annual_cost_growth_rate: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
