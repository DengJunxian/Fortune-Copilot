from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from app.domain.enums import BehaviorInterventionStatus, BehaviorSessionStatus, RiskLevel
from app.schemas.records import reject_binary_float

StrictRatio = Annotated[
    Decimal,
    BeforeValidator(reject_binary_float),
    Field(ge=0, le=1, max_digits=9, decimal_places=6),
]


class QuestionnaireDimensionOut(BaseModel):
    code: str
    name: str
    prompt: str
    low_label: str
    high_label: str
    weight: StrictRatio


class ExperimentOptionOut(BaseModel):
    code: str
    label: str


class BehaviorExperimentOut(BaseModel):
    code: str
    name: str
    scenario: str
    options: list[ExperimentOptionOut]


class BiasDefinitionOut(BaseModel):
    code: str
    name: str
    description: str


class InterventionDefinitionOut(BaseModel):
    code: str
    name: str
    trigger_biases: list[str]
    scenario_code: str
    action_instruction: str


class ABVariantOut(BaseModel):
    code: str
    name: str
    description: str


class BehaviorCatalogResponse(BaseModel):
    rule_version: str
    formula_version: str
    experiment_version: str
    ab_framework_version: str
    source_type: Literal["internal_demo"] = "internal_demo"
    source_summary: str
    questionnaire_dimensions: list[QuestionnaireDimensionOut]
    experiments: list[BehaviorExperimentOut]
    bias_definitions: list[BiasDefinitionOut]
    intervention_definitions: list[InterventionDefinitionOut]
    ab_variants: list[ABVariantOut]
    required_experiment_count: Literal[6] = 6
    behavior_boundary: str


class BehaviorQuestionnaireInput(BaseModel):
    risk_willingness: StrictRatio
    loss_tolerance_claim: StrictRatio
    investment_experience: StrictRatio
    knowledge: StrictRatio
    trading_frequency: StrictRatio
    attention: StrictRatio
    goal_discipline: StrictRatio


class StartBehaviorSessionRequest(BaseModel):
    analysis_date: date | None = None
    experiment_key: str = Field(default="behavior_nudge_main", min_length=1, max_length=64)
    questionnaire: BehaviorQuestionnaireInput


class RecordBehaviorResponseRequest(BaseModel):
    choice_code: str = Field(min_length=1, max_length=64)
    response_time_ms: int = Field(ge=100, le=600_000)
    modification_count: int = Field(default=0, ge=0, le=100)


class BehaviorResponseOut(BaseModel):
    response_id: str
    experiment_code: str
    choice_code: str
    choice_label: str
    response_time_ms: int
    modification_count: int
    consistency_score: StrictRatio
    answered_at: datetime
    evidence: str


class BiasEvidenceOut(BaseModel):
    source: str
    source_label: str
    observation: str
    contribution: StrictRatio


class BiasScoreOut(BaseModel):
    code: str
    name: str
    description: str
    score: StrictRatio
    severity: Literal["low", "watch", "high"]
    evidence: list[BiasEvidenceOut]
    explanation: str


class DualProfileOut(BaseModel):
    objective_capacity_score: StrictRatio
    objective_capacity_limit: RiskLevel
    questionnaire_score: StrictRatio
    questionnaire_claim_limit: RiskLevel
    experiment_score: StrictRatio
    experiment_limit: RiskLevel
    behavioral_limit_before_capacity: RiskLevel
    effective_risk_limit: RiskLevel
    risk_downshifted: bool
    conflict_detected: bool
    conflict_codes: list[str]
    explanation: str
    capacity_source_record_id: str


class BehaviorInterventionOut(BaseModel):
    intervention_id: str | None
    code: str
    name: str
    status: BehaviorInterventionStatus
    trigger_biases: list[str]
    scenario_code: str
    linked_goal_id: str | None
    linked_goal_name: str | None
    personalized_message: str
    action_instruction: str
    cooling_period_hours: int | None
    starts_at: datetime | None
    eligible_at: datetime | None
    completed_at: datetime | None
    dismissed_at: datetime | None
    assigned_variant: str
    audit_note: str


class BehaviorProfileMeta(BaseModel):
    household_id: str
    household_code: str
    household_name: str
    analysis_date: date
    data_as_of: date
    source: Literal["completed_session", "synthetic_behavior_input"]
    source_type: Literal["synthetic_or_authorized_test_data"] = "synthetic_or_authorized_test_data"
    rule_version: str
    formula_version: str
    experiment_version: str
    input_version: str
    calculation_source: Literal["deterministic_behavior_engine"] = "deterministic_behavior_engine"


class BehaviorProfileOut(BaseModel):
    meta: BehaviorProfileMeta
    dual_profile: DualProfileOut
    biases: list[BiasScoreOut]
    interventions: list[BehaviorInterventionOut]
    responses: list[BehaviorResponseOut]
    assigned_variant: str
    assigned_variant_name: str
    average_response_time_ms: int
    total_modification_count: int
    overall_consistency_score: StrictRatio
    limitations: list[str]


class BehaviorSessionOut(BaseModel):
    session_id: str
    household_id: str
    status: BehaviorSessionStatus
    information_status: Literal["collecting", "sufficient", "exited"]
    answered_count: int
    required_count: Literal[6] = 6
    remaining_experiment_codes: list[str]
    assigned_variant: str
    assigned_variant_name: str
    experiment_key: str
    questionnaire_score: StrictRatio
    questionnaire_claim_limit: RiskLevel
    objective_capacity_limit: RiskLevel
    effective_risk_limit: RiskLevel | None
    started_at: datetime
    completed_at: datetime | None
    exited_at: datetime | None
    responses: list[BehaviorResponseOut]
    profile: BehaviorProfileOut | None = None


class BehaviorOverviewResponse(BaseModel):
    household_id: str
    information_status: Literal["sufficient", "insufficient"]
    information_message: str
    profile: BehaviorProfileOut | None
    latest_session: BehaviorSessionOut | None
    can_start_experiment: bool
    authorization_basis: str | None
    limitations: list[str]


class ExitBehaviorSessionResponse(BaseModel):
    session_id: str
    status: Literal["exited"] = "exited"
    exited_at: datetime
    audit_event_id: str
    message: str


class InterventionActionRequest(BaseModel):
    action: Literal["complete", "dismiss"]
    reason_code: str = Field(default="user_choice", min_length=1, max_length=64)


class ABVariantMetricOut(BaseModel):
    variant_code: str
    variant_name: str
    assigned_count: int
    completed_count: int
    exited_count: int
    completion_rate: StrictRatio | None
    average_response_time_ms: int | None
    risk_downshift_count: int
    intervention_completed_count: int


class BehaviorABFrameworkResponse(BaseModel):
    framework_version: str
    experiment_key: str
    eligible_data_policy: str
    variants: list[ABVariantOut]
    metrics: list[ABVariantMetricOut]
    metric_definitions: dict[str, str]
    privacy_note: str
