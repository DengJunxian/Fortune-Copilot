from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: Any = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class DependencyStatus(BaseModel):
    status: str
    detail: str


class HealthResponse(BaseModel):
    status: str
    version: str
    runtime_mode: str
    mock_mode: bool
    database: DependencyStatus


class LivenessResponse(BaseModel):
    status: Literal["alive"] = "alive"
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    runtime_mode: str
    database: DependencyStatus
    production_integrations_ready: bool
    blocking_dependencies: list[str] = Field(default_factory=list)
    boundary_note: str


class Capability(BaseModel):
    id: str
    status: str
    implementation: str
    notes: str


class CapabilitiesResponse(BaseModel):
    version: str
    runtime_mode: str
    mock_mode: bool
    database: DependencyStatus
    portals: list[str] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
