from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class DemoHouseholdOut(BaseModel):
    household_id: str
    code: str
    name: str
    profile: str
    valuation_date: date | None


class DemoManifestResponse(BaseModel):
    release_version: str
    story_version: str
    dataset_version: str
    runtime_mode: str
    mock_mode: bool
    external_network_required: Literal[False] = False
    ready: bool
    seeded_household_count: int
    main_household_code: Literal["DEMO_B"] = "DEMO_B"
    households: list[DemoHouseholdOut]
    latest_run_id: str | None
    latest_run_status: str | None
    preheated: bool
    preheated_at: datetime | None
    cache_ttl_seconds: int
    release_assets: dict[str, bool]
    boundaries: list[str]


class DemoControlResponse(BaseModel):
    action: Literal["load", "reset"]
    dataset_version: str
    loaded: int
    skipped: int
    removed: int
    household_codes: list[str]
    cache_cleared: bool
    message: str


class DemoPreheatResponse(BaseModel):
    story_version: str
    status: Literal["ready"] = "ready"
    warmed_components: list[str]
    timings_ms: dict[str, int]
    cache_expires_at: datetime
    external_network_calls: Literal[0] = 0
    boundary_note: str


class DemoRunRequest(BaseModel):
    path_count: int | None = Field(default=None, ge=100, le=5000)
    force_recalculate: bool = False


class DemoStageOut(BaseModel):
    code: str
    label: str
    status: Literal["completed", "failed"]
    progress_percent: int = Field(ge=0, le=100)
    duration_ms: int = Field(ge=0)
    evidence: dict[str, Any]


class DemoRunResponse(BaseModel):
    run_id: str
    household_id: str
    household_code: str
    story_version: str
    status: Literal["running", "completed", "failed"]
    current_stage: str
    progress_percent: int = Field(ge=0, le=100)
    stages: list[DemoStageOut]
    artifacts: dict[str, Any]
    metrics: dict[str, Any]
    recovered_from_run_id: str | None
    offline_mode: bool
    external_network_required: Literal[False] = False
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    boundary_note: str


class FourAccountComparison(BaseModel):
    bucket: str
    name: str
    recommended_amount: Decimal
    gap_amount: Decimal


class FamilyComparisonRow(BaseModel):
    household_id: str
    code: str
    name: str
    profile: str
    lifecycle_stage: str
    total_assets: Decimal
    net_worth: Decimal
    annual_surplus: Decimal
    property_concentration: Decimal | None
    emergency_months: Decimal | None
    dynamic_safety_months: Decimal
    protection_gap: Decimal
    accounts: list[FourAccountComparison]
    candidate_decisions: dict[str, str]
    long_term_eligible_amount: Decimal
    configuration_signature: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"


class FamilyComparisonResponse(BaseModel):
    comparison_version: str
    generated_at: datetime
    analysis_date: date
    cache_status: Literal["hit", "miss"]
    rows: list[FamilyComparisonRow] = Field(min_length=3, max_length=3)
    unique_configuration_count: int
    fixed_ratio_model: Literal[False] = False
    conclusion: str
    boundary_note: str


class ExperimentCaseOut(BaseModel):
    code: str
    name: str
    status: Literal["passed", "protocol_ready", "failed"]
    measured: bool
    evidence: list[str]
    metrics: dict[str, Any] = Field(default_factory=dict)
    boundary_note: str


class ExperimentSuiteResponse(BaseModel):
    run_id: str
    suite_version: str
    status: Literal["completed"] = "completed"
    passed: bool
    main_demo_run_id: str | None
    cases: list[ExperimentCaseOut] = Field(min_length=7, max_length=7)
    metrics: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    environment: Literal["test"] = "test"
    real_bank_results_claimed: Literal[False] = False
    boundary_note: str
