from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from app.domain.enums import SimulationStatus
from app.schemas.records import Money, Ratio, SignedRatio, reject_binary_float

SignedMoney = Annotated[
    Decimal,
    BeforeValidator(reject_binary_float),
    Field(max_digits=20, decimal_places=2),
]


class AssetReturnOverride(BaseModel):
    expected_annual_return: Decimal | None = Field(
        default=None,
        gt=Decimal("-1"),
        lt=Decimal("1"),
    )
    annual_volatility: Decimal | None = Field(default=None, ge=0, le=Decimal("2"))


class AssumptionOverrides(BaseModel):
    inflation_rate: Decimal | None = Field(default=None, ge=0, le=Decimal("0.20"))
    income_growth_rate: Decimal | None = Field(
        default=None,
        ge=Decimal("-0.20"),
        le=Decimal("0.20"),
    )
    asset_assumptions: dict[str, AssetReturnOverride] = Field(default_factory=dict)
    correlation_matrix: list[list[Decimal]] | None = None


class ScenarioOverrides(BaseModel):
    unemployment_months: int | None = Field(default=None, ge=0, le=36)
    income_reduction_ratio: Ratio | None = None
    medical_shock_amount: Money | None = None
    education_overrun_amount: Money | None = None
    property_value_change_ratio: SignedRatio | None = None
    mortgage_rate_change: SignedRatio | None = None


class PlanAdjustments(BaseModel):
    primary_retirement_age: int | None = Field(default=None, ge=45, le=75)
    additional_monthly_savings: Money = Decimal("0.00")
    equity_ratio: Ratio | None = None
    liquidity_reallocation_amount: Money = Decimal("0.00")


class FamilyEventInput(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    start_month: int = Field(ge=1, le=720)
    duration_months: int = Field(default=1, ge=1, le=720)
    one_time_cost: Money = Decimal("0.00")
    monthly_income_loss: Money = Decimal("0.00")
    monthly_expense_increase: Money = Decimal("0.00")


class TwinRunRequest(BaseModel):
    analysis_date: date | None = None
    seed: int = Field(default=20260804, ge=0, le=2_147_483_647)
    path_count: int = Field(default=500, ge=100, le=5000)
    horizon_years: int = Field(default=30, ge=5, le=60)
    output_interval_months: Literal[1, 3, 6, 12] = 12
    scenario_codes: list[str] = Field(
        default_factory=lambda: ["unemployment_equity_down_30"],
        min_length=1,
        max_length=6,
    )
    scenario_overrides: ScenarioOverrides = Field(default_factory=ScenarioOverrides)
    plan_adjustments: PlanAdjustments = Field(default_factory=PlanAdjustments)
    assumption_overrides: AssumptionOverrides = Field(default_factory=AssumptionOverrides)
    family_events: list[FamilyEventInput] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_request(self) -> TwinRunRequest:
        if len(self.scenario_codes) != len(set(self.scenario_codes)):
            raise ValueError("压力场景代码不能重复")
        return self


class ScenarioDefinitionOut(BaseModel):
    code: str
    name: str
    category: str
    description: str
    parameters: dict[str, object]
    explanation: str
    scenario_version: str
    source_type: Literal["internal_demo"] = "internal_demo"
    is_composable: bool
    enabled: bool


class ScenarioCatalogResponse(BaseModel):
    scenario_version: str
    source_type: Literal["internal_demo"] = "internal_demo"
    source_summary: str
    scenario_count: int
    scenarios: list[ScenarioDefinitionOut]


class MemberState(BaseModel):
    member_id: str
    name: str
    relationship: str
    age_at_start: Decimal
    recorded_retirement_age: int | None


class GoalState(BaseModel):
    goal_id: str
    name: str
    goal_type: str
    due_month: int
    current_amount: Money
    prepared_amount: Money
    annual_cost_growth_rate: Decimal


class InitialTwinState(BaseModel):
    members: list[MemberState]
    annual_income: Money
    annual_expenses_excluding_debt_service: Money
    annual_essential_expenses_excluding_debt_service: Money
    monthly_compressible_expenses: Money
    asset_buckets: dict[str, Money]
    total_assets: Money
    total_liabilities: Money
    medical_coverage_available: Money
    medical_deductible: Money
    pension_annual_contributions: Money
    goals: list[GoalState]
    source_record_ids: list[str]
    counting_note: str


class ResolvedAssumptionSnapshot(BaseModel):
    seed: int
    path_count: int
    horizon_months: int
    time_step_months: int
    output_interval_months: int
    inflation_rate: Decimal
    income_growth_rate: Decimal
    asset_classes: list[str]
    asset_assumptions: dict[str, dict[str, Decimal]]
    correlation_matrix: list[list[Decimal]]
    property_assumption: dict[str, Decimal]
    pension_assumption: dict[str, Decimal]
    scenario_codes: list[str]
    scenario_parameters: dict[str, object]
    plan_adjustments: PlanAdjustments
    family_events: list[FamilyEventInput]
    parameter_hash: str
    source_type: Literal["internal_demo"] = "internal_demo"


class FanPoint(BaseModel):
    month: int
    date: date
    primary_age: Decimal
    p10: SignedMoney
    p25: SignedMoney
    p50: SignedMoney
    p75: SignedMoney
    p90: SignedMoney
    median_liquid_assets: Money
    median_long_term_assets: Money
    median_liabilities: Money


class GoalSimulationOutcome(BaseModel):
    goal_id: str
    name: str
    due_month: int
    required_amount: Money
    success_probability: Ratio
    failure_probability: Ratio
    median_shortfall: Money


class FailureTimeBucket(BaseModel):
    year: int
    path_count: int
    probability: Ratio
    most_common_goal: str | None


class WorstPath(BaseModel):
    path_id: int
    ending_net_worth: SignedMoney
    minimum_net_worth: SignedMoney
    first_failed_goal: str | None
    first_failure_month: int | None
    depletion_month: int | None
    forced_sale_amount: Money
    total_goal_shortfall: Money
    explanation: str


class DistributionValidation(BaseModel):
    all_values_finite: bool
    primary_income_paid_during_interruption_max: Money
    goal_spending_events_applied: int
    common_random_numbers: bool


class SimulationDistribution(BaseModel):
    label: str
    path_count: int
    horizon_months: int
    goal_success_probability: Ratio
    depletion_probability: Ratio
    forced_sale_probability: Ratio
    median_forced_sale_amount: Money
    ending_net_worth_median: SignedMoney
    ending_net_worth_p10: SignedMoney
    total_goal_shortfall_median: Money
    required_additional_monthly_savings: Money
    fan: list[FanPoint]
    goal_outcomes: list[GoalSimulationOutcome]
    failure_time_distribution: list[FailureTimeBucket]
    worst_paths: list[WorstPath]
    validation: DistributionValidation


class ScenarioImpact(BaseModel):
    scenario_code: str
    name: str
    emergency_support_months: Decimal
    first_failed_goal: str | None
    forced_sale_probability: Ratio
    median_forced_sale_amount: Money
    insurance_coverage_applied: Money
    remaining_medical_gap: Money
    retirement_delay_needed: bool
    suggested_retirement_delay_years: int
    monthly_compressible_expenses: Money
    required_additional_monthly_savings: Money
    baseline_goal_success_probability: Ratio
    scenario_goal_success_probability: Ratio
    success_probability_change: Decimal
    applicable: bool
    explanation: str


class TwinComparison(BaseModel):
    baseline_success_probability: Ratio
    original_stress_success_probability: Ratio
    optimized_stress_success_probability: Ratio
    stress_change: Decimal
    optimization_change: Decimal
    baseline_forced_sale_probability: Ratio
    original_forced_sale_probability: Ratio
    optimized_forced_sale_probability: Ratio
    liquidity_reallocation_amount: Money
    avoided_forced_sale_probability: Decimal
    stress_not_better_than_baseline: bool
    positive_override_explanation: str | None
    liquidity_explanation: str


class TwinResultMeta(BaseModel):
    run_id: str
    household_id: str
    household_code: str
    analysis_date: date
    data_as_of: date
    input_version: str
    rule_code: str
    rule_version: str
    formula_version: str
    engine_version: str
    result_version: str
    scenario_version: str
    calculation_source: Literal["deterministic_simulation_engine"] = (
        "deterministic_simulation_engine"
    )
    synthetic_data: bool
    currency: str


class TwinResult(BaseModel):
    meta: TwinResultMeta
    initial_state: InitialTwinState
    assumptions: ResolvedAssumptionSnapshot
    baseline: SimulationDistribution
    original_stress: SimulationDistribution
    optimized_stress: SimulationDistribution
    scenario_impacts: list[ScenarioImpact]
    comparison: TwinComparison
    limitations: list[str]
    counting_note: str


class TwinRunStatusResponse(BaseModel):
    run_id: str
    household_id: str
    status: SimulationStatus
    progress_percent: int = Field(ge=0, le=100)
    phase: str
    scenario_codes: list[str]
    path_count: int
    horizon_months: int
    seed: int
    input_version: str
    rule_version: str
    engine_version: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancel_requested: bool
    audit_event_id: str | None = None
    error_code: str | None
    result: TwinResult | None = None
