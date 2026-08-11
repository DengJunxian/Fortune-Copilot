from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.trust import ToolCallEvidence

type BoundedAgentCode = Literal[
    "intake",
    "goal",
    "household_analyst",
    "scenario",
    "product_research",
    "advisor_copilot",
]


class AgentToolOut(BaseModel):
    code: str
    description: str
    read_only: bool
    requires_confirmation: bool


class BoundedAgentSpecOut(BaseModel):
    code: BoundedAgentCode
    name: str
    purpose: str
    allowed_tools: list[str] = Field(min_length=1)
    prohibited_actions: list[str] = Field(min_length=1)
    timeout_seconds: int = Field(ge=1, le=60)
    failure_fallback: str


class AgentToolRegistryResponse(BaseModel):
    registry_version: str
    agent_count: Literal[6] = 6
    tools: list[AgentToolOut]
    agents: list[BoundedAgentSpecOut]
    enforcement: Literal["deny_by_default"] = "deny_by_default"
    persistence: Literal["existing_agent_run_tables"] = "existing_agent_run_tables"
    boundary_note: str


class BoundedAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_code: BoundedAgentCode
    message: str = Field(min_length=2, max_length=2000)
    analysis_date: date | None = None
    product_codes: list[str] = Field(default_factory=list, max_length=12)
    maximum_results: int = Field(default=3, ge=1, le=5)


class AgentGuardrailIssue(BaseModel):
    code: str
    severity: Literal["block"] = "block"
    message: str
    action: Literal["fail_closed", "deterministic_tool_required"]


class BoundedAgentRunResponse(BaseModel):
    run_id: str
    step_id: str
    household_id: str
    agent_code: BoundedAgentCode
    status: Literal["completed", "degraded", "blocked"]
    registry_version: str
    allowed_tools: list[str]
    tool_calls: list[ToolCallEvidence]
    output: dict[str, Any]
    guardrail_issues: list[AgentGuardrailIssue]
    requires_confirmation: bool
    requires_human_review: bool
    persisted_to_existing_agent_tables: Literal[True] = True
    started_at: datetime
    completed_at: datetime
    boundary_note: str
