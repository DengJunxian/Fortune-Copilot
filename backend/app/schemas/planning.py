from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import AccountBucket, LifecycleStage
from app.schemas.records import Money

ConstraintStatus = Literal["pass", "limit", "block", "not_evaluated"]
GoalStatus = Literal["funded", "on_track", "gap", "conflict"]
DenominatorId = Literal[
    "total_assets",
    "investable_financial_assets",
    "annual_new_surplus",
]
WaterfallStatus = Literal[
    "covered",
    "partial",
    "unfunded",
    "cashflow_covered",
    "informational",
]


class PlanningMeta(BaseModel):
    household_id: str
    household_code: str
    analysis_date: date
    data_as_of: date
    input_version: str
    formula_version: str
    rule_code: str
    rule_version: str
    rule_source_type: Literal["internal_demo"] = "internal_demo"
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    currency: str
    synthetic_data: bool
    scenario_type: Literal["base", "counterfactual"]


class FactorEvidence(BaseModel):
    factor: str
    label: str
    observed_value: str
    adjustment_months: Decimal
    source_record_ids: list[str] = Field(default_factory=list)


class LifecycleAssessment(BaseModel):
    detected_stage: LifecycleStage
    recorded_stage: LifecycleStage
    effective_stage: LifecycleStage
    override_applied: bool
    dynamic_safety_months: Decimal
    base_safety_months: Decimal
    formula: str
    substitution: str
    explanation: str
    evidence: list[FactorEvidence]


class GoalProjection(BaseModel):
    goal_id: str
    name: str
    goal_type: str
    target_date: date
    adjusted_target_date: date
    months_remaining: int
    current_cost: Decimal
    future_amount: Decimal
    present_value: Decimal
    minimum_present_value: Decimal
    prepared_amount: Decimal
    funding_gap: Decimal
    minimum_funding_gap: Decimal
    monthly_required: Decimal
    annual_required: Decimal
    priority: int
    rigidity: str
    can_defer: bool
    annual_cost_growth_rate: Decimal
    status: GoalStatus
    formula: str
    substitution: str
    source_record_ids: list[str]


class ConflictAdjustment(BaseModel):
    action_code: str
    title: str
    detail: str
    affected_goal_ids: list[str]
    monthly_effect: Decimal
    preserves_minimum: bool


class GoalConflict(BaseModel):
    conflict_id: str
    severity: Literal["attention", "warning", "critical"]
    title: str
    detail: str
    affected_goal_ids: list[str]
    available_monthly_surplus: Decimal
    required_monthly_contribution: Decimal
    monthly_shortfall: Decimal
    adjustments: list[ConflictAdjustment]


class RatioMeasure(BaseModel):
    denominator_id: DenominatorId
    denominator_name: str
    denominator_value: Decimal
    ratio: Decimal | None
    applicable: bool
    reason: str


class ReferenceBand(BaseModel):
    denominator_id: DenominatorId
    denominator_name: str
    minimum_ratio: Decimal
    maximum_ratio: Decimal
    target_ratio: Decimal
    overall_minimum_ratio: Decimal
    overall_maximum_ratio: Decimal
    market_regime: Literal["favorable", "neutral", "defensive"]
    market_regime_label: str
    binding: bool
    conditions: list[str]
    explanation: str


class AccountAllocation(BaseModel):
    bucket: AccountBucket
    name: str
    sequence: int
    current_amount: Decimal
    target_amount: Decimal
    recommended_amount: Decimal
    recommended_range_min: Decimal
    recommended_range_max: Decimal
    gap_amount: Decimal
    annual_cost_amount: Decimal
    coverage_gap_amount: Decimal
    primary_denominator_name: str
    reference_band: ReferenceBand | None
    current_measures: list[RatioMeasure]
    target_measures: list[RatioMeasure]
    measures: list[RatioMeasure]
    formula: str
    substitution: str
    rationale: str
    constraint_ids: list[str]
    source_record_ids: list[str]
    product_education: list[str]


class WaterfallStep(BaseModel):
    sequence: int
    step_code: str
    name: str
    required_amount: Decimal
    allocated_amount: Decimal
    remaining_resources: Decimal
    status: WaterfallStatus
    formula: str
    explanation: str
    source_record_ids: list[str] = Field(default_factory=list)


class ConstraintResult(BaseModel):
    constraint_id: Literal[
        "capital_threshold",
        "liquidity",
        "debt",
        "protection",
        "horizon",
        "suitability",
        "behavior",
    ]
    constraint_type: Literal["hard", "soft"]
    name: str
    status: ConstraintStatus
    observed_value: str
    required_condition: str
    effect: str
    limits_growth: bool
    source_record_ids: list[str] = Field(default_factory=list)


class ActionDraft(BaseModel):
    priority: int
    action_code: str
    title: str
    detail: str
    amount: Decimal
    due_date: date | None
    account_bucket: AccountBucket | None
    source_record_ids: list[str] = Field(default_factory=list)


class DenominatorSummary(BaseModel):
    total_assets: Decimal
    investable_financial_assets: Decimal
    net_financial_assets_after_debt: Decimal
    growth_entry_threshold: Decimal
    annual_new_surplus: Decimal
    available_planning_resources: Decimal
    high_interest_debt_before_plan: Decimal
    high_interest_debt_after_counterfactual: Decimal
    same_period_cashflow_committed: Decimal


class GrowthEligibility(BaseModel):
    eligible: bool
    threshold: Decimal
    actual_ratio: Decimal | None
    denominator_name: str
    denominator_value: Decimal
    conditions: list[str]
    failed_conditions: list[str]
    explanation: str


class InvestmentLearningPlan(BaseModel):
    applicable: bool
    eligible: bool
    cap_ratio: Decimal
    recommended_ratio: Decimal | None
    recommended_amount: Decimal
    denominator_name: str
    denominator_value: Decimal
    conditions: list[str]
    failed_conditions: list[str]
    explanation: str


class GrowthBenchmark(BaseModel):
    benchmark_rate: Decimal
    components: dict[str, Decimal]
    formula: str
    explanation: str
    minimum_wage_is_cpi: Literal[False] = False
    is_return_guarantee: Literal[False] = False


class AppliedCounterfactual(BaseModel):
    emergency_fund_addition: Decimal
    high_interest_debt_reduction: Decimal
    protection_gap_reduction: Decimal
    monthly_savings_increase: Decimal
    goal_prepared_additions: dict[str, Decimal]
    defer_goal_ids: list[str]
    defer_months: int
    lifecycle_override: LifecycleStage | None


class PlanningResponse(BaseModel):
    meta: PlanningMeta
    lifecycle: LifecycleAssessment
    goals: list[GoalProjection]
    conflicts: list[GoalConflict]
    denominators: DenominatorSummary
    waterfall_steps: list[WaterfallStep]
    constraints: list[ConstraintResult]
    accounts: list[AccountAllocation]
    investment_learning: InvestmentLearningPlan
    growth_70: GrowthEligibility
    growth_benchmark: GrowthBenchmark
    actions: list[ActionDraft]
    applied_counterfactual: AppliedCounterfactual
    counting_note: str


class CounterfactualRequest(BaseModel):
    analysis_date: date | None = None
    emergency_fund_addition: Money = Decimal("0.00")
    high_interest_debt_reduction: Money = Decimal("0.00")
    protection_gap_reduction: Money = Decimal("0.00")
    monthly_savings_increase: Money = Decimal("0.00")
    goal_prepared_additions: dict[str, Money] = Field(default_factory=dict)
    defer_goal_ids: list[str] = Field(default_factory=list)
    defer_months: int = Field(default=0, ge=0, le=120)
    lifecycle_override: LifecycleStage | None = None

    @model_validator(mode="after")
    def validate_deferral(self) -> CounterfactualRequest:
        if self.defer_goal_ids and self.defer_months == 0:
            raise ValueError("选择延期目标时，延期月数必须大于 0")
        return self


class CounterfactualChange(BaseModel):
    code: str
    label: str
    before: Decimal | str | bool
    after: Decimal | str | bool
    delta: Decimal | None
    explanation: str


class CounterfactualResponse(BaseModel):
    base: PlanningResponse
    scenario: PlanningResponse
    changes: list[CounterfactualChange]
    explanation: str


class PersistedPlanningRun(BaseModel):
    recommendation_id: str
    account_plan_ids: list[str]
    action_item_ids: list[str]
    household_id: str
    input_version: str
    rule_version_id: str
    rule_version: str
    account_count: int
    action_count: int
    created_at: datetime
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
