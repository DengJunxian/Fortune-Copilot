from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class PersonaDatasetQuality(BaseModel):
    household_count: int = Field(ge=0)
    persona_count: int = Field(ge=0)
    enterprise_extension_count: int = Field(ge=0)
    unique_household_code_rate: Decimal = Field(ge=0, le=1)
    unique_profile_code_rate: Decimal = Field(ge=0, le=1)
    required_collection_completeness_rate: Decimal = Field(ge=0, le=1)
    reference_integrity_rate: Decimal = Field(ge=0, le=1)
    passed: bool
    evidence: dict[str, Any]


class GoldenAssertionResult(BaseModel):
    code: str
    path: str
    operator: str
    expected: Any
    actual: Any
    passed: bool


class PersonaPipelineResult(BaseModel):
    household_id: str
    household_code: str
    passed: bool
    profile_completeness: Decimal = Field(ge=0, le=1)
    wealth_need_types: list[str]
    liability_stream_types: list[str]
    cfs_component_types: list[str]
    monitoring_alert_types: list[str]
    specialist_types: list[str]
    no_action_required: bool
    additional_risk_allowed: bool
    decision_replay: bool
    financial_correct: bool
    normalized_outcome: dict[str, Any]
    assertions: list[GoldenAssertionResult]


class ReleaseBenchmarkMetric(BaseModel):
    code: Literal[
        "profile_completeness",
        "wealth_need_coverage",
        "cfs_coverage",
        "no_action_correctness",
        "product_ranking_conflict_independence",
        "advisor_trigger_precision",
        "invalid_alert_rate",
        "decision_replay",
        "financial_correctness",
    ]
    value: Decimal = Field(ge=0, le=1)
    threshold: Decimal = Field(ge=0, le=1)
    comparator: Literal["gte", "lte"]
    passed: bool
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    evidence: dict[str, Any]


class PersonaReleaseResponse(BaseModel):
    benchmark_version: str
    dataset_version: str
    golden_version: str
    analysis_date: date
    passed: bool
    dataset_quality: PersonaDatasetQuality
    personas: list[PersonaPipelineResult] = Field(min_length=8, max_length=8)
    metrics: list[ReleaseBenchmarkMetric] = Field(min_length=9, max_length=9)
    generated_at: datetime
    calculation_source: Literal["deterministic_v5_release_pipeline"] = (
        "deterministic_v5_release_pipeline"
    )
    external_network_calls: Literal[0] = 0
    boundary: str


class FounderStoryStage(BaseModel):
    code: str
    label: str
    passed: bool
    evidence: dict[str, Any]


class FounderStoryResponse(BaseModel):
    story_version: str
    household_id: str
    household_code: Literal["DEMO_D"] = "DEMO_D"
    passed: bool
    stages: list[FounderStoryStage] = Field(min_length=14, max_length=14)
    initial_snapshot_id: str
    funding_snapshot_id: str
    confirmed_snapshot_id: str
    workflow_id: str
    cfs_solution_id: str
    generated_at: datetime
    external_network_calls: Literal[0] = 0
    boundary: str
