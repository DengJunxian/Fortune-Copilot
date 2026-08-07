from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.financial_analysis import FinancialAnalysisResponse
from app.schemas.planning import PlanningResponse
from app.schemas.trust import KnowledgeCitation


class ClientJourneyStep(BaseModel):
    code: str
    label: str
    status: Literal["completed", "ready", "needs_action", "blocked"]
    reason: str
    action: str
    view: Literal[
        "family",
        "balance",
        "cashflow",
        "health",
        "accounts",
        "goals",
        "twin",
        "behavior",
        "report",
        "actions",
        "privacy",
    ]


class PrivacyConsentItem(BaseModel):
    id: str
    scopes: list[str]
    purpose: str
    granted_at: datetime
    withdrawn_at: datetime | None
    consent_version: str
    record_version: int
    status: Literal["active", "withdrawn"]
    withdrawal_allowed: bool
    scenario: str
    sensitive: bool
    explicit: bool
    minimum_necessary: bool


class ClientPrivacySummary(BaseModel):
    active_consent_count: int
    withdrawn_consent_count: int
    consents: list[PrivacyConsentItem]
    export_path: str
    delete_path: str
    deletion_mode: Literal["logical_erasure_with_confirmation"] = (
        "logical_erasure_with_confirmation"
    )
    human_review_path: str
    boundary_note: str


class ActionCalendarItem(BaseModel):
    code: str
    title: str
    detail: str
    why: str
    constraint_or_formula: str
    change_trigger: str
    risk_and_assumptions: str
    amount: str
    due_date: date | None
    priority: int
    source_record_ids: list[str]
    calculation_source: Literal["deterministic_planning_rules", "deterministic_review_schedule"]


class ActionCalendarGroup(BaseModel):
    code: Literal["immediate", "three_months", "one_year", "long_term", "next_12_months"]
    label: str
    description: str
    items: list[ActionCalendarItem]


class ClientReportChapter(BaseModel):
    number: int = Field(ge=1, le=8)
    title: str
    summary: str
    calculation_basis: list[str]
    citation_ids: list[str]
    status: Literal["ready", "pending_twin", "needs_review"]


class ClientReportPreview(BaseModel):
    report_version: str
    knowledge_retrieval_version: str
    title: str
    subtitle: str
    chapter_count: Literal[8] = 8
    chapters: list[ClientReportChapter] = Field(min_length=8, max_length=8)
    citations: list[KnowledgeCitation]
    generated_at: datetime
    data_as_of: date
    calculation_source: Literal["deterministic_client_experience_composer"] = (
        "deterministic_client_experience_composer"
    )
    boundary_note: str


class ClientDeliveryState(BaseModel):
    report: Literal["not_generated", "under_review", "client_ready"]
    workflow: Literal["not_created", "under_review", "client_ready"]
    actions: Literal["not_generated", "under_review", "client_ready"]
    explanation: str


class ClientExperienceResponse(BaseModel):
    household_id: str
    household_code: str
    household_name: str
    household_version: int
    synthetic_data: bool
    analysis_date: date
    data_as_of: date
    journey: list[ClientJourneyStep]
    privacy: ClientPrivacySummary
    action_calendar: list[ActionCalendarGroup]
    report: ClientReportPreview
    delivery: ClientDeliveryState
    calculation_versions: dict[str, str]
    state_catalog: list[str]
    mock_mode_supported: Literal[True] = True


class ClientDataExport(BaseModel):
    package_version: str
    exported_at: datetime
    household_id: str
    financial_analysis: FinancialAnalysisResponse
    planning: PlanningResponse
    client_experience: ClientExperienceResponse
    boundary_note: str


class ConsentWithdrawRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=300)


class HumanReviewRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    context: str = Field(default="client_privacy_center", min_length=2, max_length=120)


class HumanReviewResponse(BaseModel):
    request_id: str
    household_id: str
    status: Literal["queued"] = "queued"
    queue: Literal["demo_advisor_queue"] = "demo_advisor_queue"
    created_at: datetime
    message: str
