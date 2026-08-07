from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.auth import ActorRole
from app.domain.enums import (
    PlanWorkflowAction,
    PlanWorkflowState,
    PortfolioCandidateType,
    SuitabilityDecision,
    SuitabilityStatus,
)
from app.schemas.records import Money, Ratio

WORKFLOW_STATE_ORDER: tuple[PlanWorkflowState, ...] = (
    PlanWorkflowState.DRAFT,
    PlanWorkflowState.CALCULATED,
    PlanWorkflowState.SUITABILITY_CHECKED,
    PlanWorkflowState.ADVISOR_REVIEWED,
    PlanWorkflowState.COMPLIANCE_REVIEWED,
    PlanWorkflowState.CUSTOMER_CONFIRMED,
    PlanWorkflowState.ACTIVE,
    PlanWorkflowState.SUPERSEDED,
)


class WorkflowVersionLedger(BaseModel):
    input_version: str
    rule_version: str
    model_version: str
    prompt_version: str
    knowledge_version: str
    product_catalog_version: str


class PlanWorkflowVersionOut(BaseModel):
    id: str
    workflow_id: str
    household_id: str
    version_number: int = Field(ge=1)
    cycle: int = Field(ge=1)
    prior_version_id: str | None
    state: PlanWorkflowState
    action: PlanWorkflowAction
    reason: str
    actor_id: str
    actor_role: ActorRole
    selected_candidate: PortfolioCandidateType | None
    recommendation_snapshot: dict[str, object]
    suitability_snapshot: dict[str, object]
    communication_draft: str
    advisor_decision: str | None
    compliance_decision: str | None
    customer_confirmation: dict[str, object]
    submitted_for_compliance: bool
    requires_human_review: bool
    is_current: bool
    versions: WorkflowVersionLedger
    before_hash: str
    after_hash: str
    request_id: str
    created_at: datetime


class PlanWorkflowResponse(BaseModel):
    workflow_id: str
    household_id: str
    current: PlanWorkflowVersionOut
    versions: list[PlanWorkflowVersionOut]
    state_order: list[PlanWorkflowState]
    next_actions: list[PlanWorkflowAction]
    traceable: Literal[True] = True


class CreatePlanWorkflowRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class WorkflowActionRequest(BaseModel):
    action: PlanWorkflowAction
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=500)
    selected_candidate: PortfolioCandidateType | None = None
    communication_draft: str | None = Field(default=None, max_length=5000)
    advisor_note: str | None = Field(default=None, max_length=1000)
    compliance_note: str | None = Field(default=None, max_length=1000)
    manual_high_risk_confirmed: bool = False
    human_review_completed: bool = False
    customer_name: str | None = Field(default=None, min_length=2, max_length=80)
    acknowledgements: list[Literal["risk_read", "mock_understood", "not_guaranteed"]] = Field(
        default_factory=list
    )
    replacement_workflow_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def validate_action_fields(self) -> WorkflowActionRequest:
        if (
            self.action
            in {
                PlanWorkflowAction.ADVISOR_REVIEW,
                PlanWorkflowAction.REVISE_ADVICE,
            }
            and self.selected_candidate is None
        ):
            raise ValueError("顾问审核或修改建议必须选择一套确定性候选方案")
        if self.action == PlanWorkflowAction.CUSTOMER_CONFIRM:
            if self.customer_name is None:
                raise ValueError("客户确认必须填写演示签署姓名")
            if set(self.acknowledgements) != {
                "risk_read",
                "mock_understood",
                "not_guaranteed",
            }:
                raise ValueError("客户确认必须逐项勾选风险、Mock 与非保本边界")
        return self


class MockBankEntry(BaseModel):
    record_id: str
    display_name: str
    amount: Money
    amount_role: Literal[
        "asset",
        "liability",
        "coverage",
        "cashflow_in",
        "cashflow_out",
        "information_only",
    ]
    source_record_ids: list[str]
    details: dict[str, object] = Field(default_factory=dict)
    boundary_note: str


class MockBankInterface(BaseModel):
    code: Literal[
        "accounts",
        "credit_cards",
        "mortgages",
        "wealth_management",
        "funds",
        "insurance",
        "personal_pension",
        "cash_flow",
    ]
    label: str
    status: Literal["available", "empty"]
    entries: list[MockBankEntry]


class MockBankSnapshot(BaseModel):
    adapter: Literal["mock_bank_adapter"] = "mock_bank_adapter"
    adapter_version: str
    mock: Literal[True] = True
    official_connection: Literal[False] = False
    household_id: str
    household_code: str
    data_as_of: date
    interfaces: list[MockBankInterface] = Field(min_length=8, max_length=8)
    reconciled_asset_total: Money
    reconciled_liability_total: Money
    credit_limit_in_total_assets: Literal[False] = False
    source: Literal["synthetic_household_records"] = "synthetic_household_records"
    boundary_note: str


class AdvisorHouseholdSummary(BaseModel):
    household_id: str
    household_code: str
    household_name: str
    lifecycle_stage: str
    region: str
    data_as_of: date
    net_worth: Money
    annual_surplus: Money
    anomaly_count: int = Field(ge=0)
    goal_conflict_count: int = Field(ge=0)
    highest_attention: Literal["normal", "attention", "warning", "critical"]
    workflow_id: str | None
    workflow_state: PlanWorkflowState | None
    workflow_version: int | None
    signature_status: Literal["not_ready", "pending", "confirmed", "active"]
    synthetic_data: bool


class AdvisorHouseholdList(BaseModel):
    generated_at: datetime
    calculation_source: Literal["deterministic_advisor_queue"] = "deterministic_advisor_queue"
    items: list[AdvisorHouseholdSummary]


class AdvisorCandidateSummary(BaseModel):
    candidate_type: PortfolioCandidateType
    name: str
    decision: SuitabilityDecision
    investment_amount: Money
    expected_nominal_return: Ratio
    max_drawdown_estimate: Ratio
    extreme_loss_amount: Money
    liquidity_score: Ratio
    annual_fee_estimate: Money
    product_type_reasons: list[str]
    primary_risks: list[str]


class AdvisorDossier(BaseModel):
    generated_at: datetime
    household: AdvisorHouseholdSummary
    members: list[dict[str, object]]
    premeeting_questions: list[str]
    financial_anomalies: list[dict[str, object]]
    goal_conflicts: list[dict[str, object]]
    candidates: list[AdvisorCandidateSummary] = Field(min_length=3, max_length=3)
    risk_and_liquidity_notes: list[str]
    suggested_communication_draft: str
    communication_source: Literal["editable_mock_template"] = "editable_mock_template"
    monthly_review_reminders: list[dict[str, object]]
    mock_bank: MockBankSnapshot
    boundary_note: str


class ComplianceControl(BaseModel):
    code: str
    category: Literal[
        "family_suitability",
        "customer_suitability",
        "product_suitability",
        "prohibited_wording",
        "numeric_consistency",
        "source_integrity",
        "model_governance",
        "authorization",
        "version_integrity",
        "anomalous_recommendation",
    ]
    status: Literal["pass", "warning", "block", "information"]
    title: str
    explanation: str
    rule: str
    source_record_ids: list[str] = Field(default_factory=list)


class ComplianceEvidence(BaseModel):
    workflow_id: str
    version_id: str
    version_number: int
    household_id: str
    overall_decision: Literal["pass", "block", "human_review"]
    controls: list[ComplianceControl]
    three_gate_statuses: dict[str, SuitabilityStatus]
    blocked_codes: list[str]
    warning_codes: list[str]
    prohibited_phrases: list[str]
    numeric_ledger: dict[str, str]
    security_events: list[dict[str, object]]
    versions: WorkflowVersionLedger
    hash_chain_verified: bool
    explanation: str


class ComplianceQueueItem(BaseModel):
    workflow_id: str
    household_id: str
    household_code: str
    household_name: str
    version_id: str
    version_number: int
    state: PlanWorkflowState
    submitted_for_compliance: bool
    requires_human_review: bool
    selected_candidate: PortfolioCandidateType | None
    created_at: datetime
    blocked_count: int
    warning_count: int
    recommendation_reason: str


class ComplianceQueue(BaseModel):
    generated_at: datetime
    items: list[ComplianceQueueItem]


class ComplaintReplayRequest(BaseModel):
    version_id: str = Field(min_length=36, max_length=36)
    reason: str = Field(min_length=2, max_length=500)


class ComplaintReplayResponse(BaseModel):
    replay_id: str
    workflow_id: str
    requested_version_id: str
    household_id: str
    generated_at: datetime
    request_id: str
    timeline: list[dict[str, object]]
    audit_events: list[dict[str, object]]
    integrity_status: Literal["verified"] = "verified"
    package_hash: str
    boundary_note: str


class WorkflowAuditPackage(BaseModel):
    package_version: str
    generated_at: datetime
    workflow_id: str
    household_id: str
    versions: list[PlanWorkflowVersionOut]
    audit_events: list[dict[str, object]]
    hash_chain_verified: bool
    package_hash: str
    exported_by: str
    exported_role: ActorRole
    request_id: str
    boundary_note: str
