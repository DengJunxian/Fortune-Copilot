from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import EmploymentStability
from app.schemas.financial_analysis import FinancialAnalysisResponse
from app.schemas.planning import PlanningResponse
from app.schemas.records import Money, Ratio

PlanningScope = Literal["individual", "family"]
CityTier = Literal["tier_one_or_new_tier_one", "developed_city", "other_city"]
InvestmentExperience = Literal["none", "basic", "experienced"]
RiskPreference = Literal["conservative", "balanced", "growth"]
LossTolerance = Literal["low", "medium", "high"]
FundsSource = Literal[
    "salary",
    "business",
    "accumulated_savings",
    "property_income",
    "investment_income",
    "family_support",
    "other",
]
PersonalPensionStatus = Literal["opened", "not_opened", "not_sure"]


def _default_funds_sources() -> list[FundsSource]:
    return ["salary"]
AssetIntakeCategory = Literal[
    "cash_and_equivalents",
    "time_deposit_and_bank_wealth",
    "non_bank_financial",
    "primary_residence",
    "investment_property",
    "vehicle_and_other",
]
LiabilityIntakeCategory = Literal[
    "mortgage",
    "auto_loan",
    "consumer_loan",
    "credit_card_unpaid",
    "non_bank_loan",
    "other",
]
IncomeIntakeCategory = Literal[
    "self_employment",
    "spouse_employment",
    "asset_income",
    "rental_income",
    "other",
]
ExpenseIntakeCategory = Literal[
    "living",
    "parent_support",
    "child_education",
    "insurance_premium",
    "debt_service",
    "other",
]

RatioMetricId = Literal[
    "liquidity_reserve_months",
    "debt_to_asset_ratio",
    "savings_ratio",
    "debt_service_burden_ratio",
    "investable_assets_to_net_worth",
    "property_to_assets_ratio",
]

RATIO_METRIC_IDS: tuple[RatioMetricId, ...] = (
    "liquidity_reserve_months",
    "debt_to_asset_ratio",
    "savings_ratio",
    "debt_service_burden_ratio",
    "investable_assets_to_net_worth",
    "property_to_assets_ratio",
)


class KycProfile(BaseModel):
    """Minimum KYC facts needed for account-level suitability calculations."""

    model_config = ConfigDict(extra="forbid")

    city_tier: CityTier = "developed_city"
    growth_entry_threshold: Money = Field(
        default=Decimal("500000.00"), ge=Decimal("300000"), le=Decimal("1000000")
    )
    investment_experience: InvestmentExperience = "basic"
    risk_preference: RiskPreference = "balanced"
    loss_tolerance: LossTolerance = "medium"
    investment_horizon_years: int = Field(default=5, ge=1, le=30)
    funds_sources: list[FundsSource] = Field(
        default_factory=_default_funds_sources, min_length=1, max_length=7
    )
    personal_pension_status: PersonalPensionStatus = "not_sure"


class IntakeMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    relationship: str = Field(min_length=1, max_length=40)
    birth_date: date
    occupation: str | None = Field(default=None, max_length=120)
    employment_stability: EmploymentStability = EmploymentStability.MEDIUM
    expected_retirement_age: int | None = Field(default=None, ge=45, le=80)


class IntakeAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: AssetIntakeCategory
    label: str = Field(min_length=1, max_length=120)
    amount: Money


class IntakeLiability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: LiabilityIntakeCategory
    label: str = Field(min_length=1, max_length=120)
    balance: Money
    monthly_payment: Money = Field(default=Decimal("0"))
    annual_interest_rate: Ratio = Field(default=Decimal("0"))


class IntakeIncome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: IncomeIntakeCategory
    label: str = Field(min_length=1, max_length=120)
    annual_amount: Money


class IntakeExpense(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ExpenseIntakeCategory
    label: str = Field(min_length=1, max_length=120)
    annual_amount: Money


class PlanningIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planning_scope: PlanningScope
    case_name: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=120)
    kyc: KycProfile = Field(default_factory=KycProfile)
    members: list[IntakeMember] = Field(min_length=1, max_length=8)
    assets: list[IntakeAsset] = Field(min_length=1, max_length=30)
    liabilities: list[IntakeLiability] = Field(default_factory=list, max_length=30)
    incomes: list[IntakeIncome] = Field(min_length=1, max_length=20)
    expenses: list[IntakeExpense] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_household_intake(self) -> PlanningIntakeRequest:
        if not any(item.relationship == "本人" for item in self.members):
            raise ValueError("家庭成员中必须包含本人")
        if self.planning_scope == "individual" and len(self.members) != 1:
            raise ValueError("个人规划只能包含本人")
        if sum(item.annual_amount for item in self.incomes) <= 0:
            raise ValueError("年收入合计必须大于零")
        return self


class PlanningIntakeResponse(BaseModel):
    household_id: str
    analysis: FinancialAnalysisResponse


class RatioExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        default="请用通俗、克制的语言解释这些已经计算完成的家庭财务比率。",
        min_length=1,
        max_length=240,
    )


class RatioExplanationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: RatioMetricId
    interpretation: str = Field(min_length=1, max_length=360)
    focus: str = Field(min_length=1, max_length=240)
    next_step: str = Field(min_length=1, max_length=240)


class RatioExplanationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RatioExplanationItem] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_exact_metric_set(self) -> RatioExplanationOutput:
        actual = [item.metric_id for item in self.items]
        if len(set(actual)) != len(actual) or set(actual) != set(RATIO_METRIC_IDS):
            raise ValueError("比率解释必须完整且不得重复")
        return self


class RatioExplanationResponse(BaseModel):
    provider: str
    model: str
    used_external_model: bool
    degraded: bool
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    items: list[RatioExplanationItem]


class NarrativeGoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    goal_type: str = Field(min_length=1, max_length=40)
    target_amount: Money
    target_date: date
    prepared_amount: Money = Decimal("0")
    rigidity: str = Field(default="important", min_length=1, max_length=24)


class NarrativeMajorExpenseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    target_amount: Money
    target_date: date
    prepared_amount: Money = Decimal("0")
    planned_source: str = Field(default="待确定", min_length=1, max_length=120)


class PlanNarrativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goals: list[NarrativeGoalInput] = Field(default_factory=list, max_length=20)
    major_expenses: list[NarrativeMajorExpenseInput] = Field(
        default_factory=list, max_length=20
    )


class PlanNarrativeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family_analysis: str = Field(min_length=1, max_length=1200)
    goal_analysis: str = Field(min_length=1, max_length=1200)
    major_expense_analysis: str = Field(min_length=1, max_length=1200)
    statement_analysis: str = Field(min_length=1, max_length=1200)
    ratio_analysis_summary: str = Field(min_length=1, max_length=1200)
    four_account_analysis: str = Field(min_length=1, max_length=1600)
    review_triggers: list[str] = Field(min_length=3, max_length=6)


class PlanNarrativeResponse(BaseModel):
    provider: str
    model: str
    used_external_model: bool
    degraded: bool
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    planning: PlanningResponse
    narrative: PlanNarrativeOutput
