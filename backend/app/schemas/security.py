from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import ActorRole


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoSessionRequest(StrictRequest):
    actor_id: str = Field(min_length=1, max_length=80)
    role: ActorRole


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    actor_id: str
    role: ActorRole
    household_ids: list[str]
    issued_at: datetime
    expires_at: datetime
    demo_only: Literal[True] = True


class ConsentScenario(BaseModel):
    code: str
    label: str
    scopes: list[str]
    sensitive: bool
    purpose: str
    required_acknowledgement: str


class ConsentCatalogResponse(BaseModel):
    version: str
    scenarios: list[ConsentScenario]
    minimum_necessary_rule: str
    sensitive_data_rule: str


class PrivacyExportRequest(StrictRequest):
    reason: str = Field(min_length=2, max_length=500)


class PrivacyDeletionRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    household_code_confirmation: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=2, max_length=500)


class PrivacyRequestOut(BaseModel):
    request_id: str
    household_id: str | None
    request_type: Literal["export", "erase"]
    status: Literal["completed", "rejected"]
    scope: list[str]
    confirmation_method: str
    completed_at: datetime | None
    result_summary: dict[str, Any]
    boundary_note: str


class PrivacyExportResponse(BaseModel):
    request: PrivacyRequestOut
    package_version: str
    exported_at: datetime
    household_ref: str
    data: dict[str, Any]
    boundary_note: str


class FileInspectionResponse(BaseModel):
    filename_hash: str
    media_type: str
    bytes_read: int
    sha256: str
    status: Literal["clean", "quarantined"]
    injection_evidence: list[str]
    persisted: Literal[False] = False
    boundary_note: str


class QualityGateItem(BaseModel):
    code: Literal[
        "data_integrity",
        "calculation",
        "goals",
        "family_safety",
        "customer_suitability",
        "product_suitability",
        "fact_citations",
        "numeric_consistency",
        "prohibited_language",
        "human_review",
    ]
    label: str
    status: Literal["pass", "block"]
    explanation: str
    evidence: list[str] = Field(default_factory=list)


class QualityGateResponse(BaseModel):
    gate_run_id: str
    report_id: str
    household_id: str
    gate_version: str
    environment: str
    passed: bool
    gates: list[QualityGateItem] = Field(min_length=10, max_length=10)
    evaluated_at: datetime
    calculation_source: Literal["deterministic_release_gate"] = "deterministic_release_gate"
    boundary_note: str


class QualityGateEvaluateRequest(StrictRequest):
    human_review_completed: bool = False
    reason: str = Field(default="发布前质量门禁复核", min_length=2, max_length=500)


class PublishReportRequest(StrictRequest):
    expected_report_sequence: int = Field(ge=1)
    human_review_completed: bool
    reason: str = Field(min_length=2, max_length=500)


class PublishReportResponse(BaseModel):
    report_id: str
    publication_status: Literal["published"]
    published_at: datetime
    gate: QualityGateResponse
    watermark: str
    boundary_note: str


class AdversarialCaseResult(BaseModel):
    code: str
    title: str
    passed: bool
    expected: str
    observed: str
    evidence: list[str]


class EvaluationMetrics(BaseModel):
    environment: Literal["test"] = "test"
    calculation_correctness_pct: str
    citation_coverage_pct: str
    unsupported_fact_rate_pct: str
    suitability_block_rate_pct: str
    prompt_injection_block_rate_pct: str
    report_consistency_pct: str
    runtime_ms: int = Field(ge=0)
    failure_rate_pct: str
    adversarial_passed: int = Field(ge=0)
    adversarial_total: int = Field(ge=0)
    not_production_metric: Literal[True] = True


class EvaluationResponse(BaseModel):
    run_id: str
    suite_version: str
    passed: bool
    cases: list[AdversarialCaseResult]
    metrics: EvaluationMetrics
    started_at: datetime
    completed_at: datetime
    boundary_note: str


class SecurityDashboardResponse(BaseModel):
    environment: Literal["test"] = "test"
    generated_at: datetime
    latest_evaluation: EvaluationResponse | None
    model_run_counts: dict[str, int]
    privacy_request_counts: dict[str, int]
    quality_gate_counts: dict[str, int]
    controls: list[dict[str, str | bool]]
    boundary_note: str


class ModelRunSummary(BaseModel):
    run_id: str
    household_id: str | None
    task: str
    provider: str
    model_name: str
    degraded: bool
    started_at: datetime
    completed_at: datetime | None
    input_fields: list[str]
    prompt_injection_detected: bool
    human_review_required: bool


class ModelRunListResponse(BaseModel):
    items: list[ModelRunSummary]
    total: int
    boundary_note: str
