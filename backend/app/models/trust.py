from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AgentStepStatus, IntakeDraftStatus, OrchestrationStatus
from app.models.base import Base
from app.models.common import RecordMixin


class KnowledgeChunk(RecordMixin, Base):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    page_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    paragraph_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    security_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    security_evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class IntakeDraft(RecordMixin, Base):
    __tablename__ = "intake_drafts"

    household_id: Mapped[str | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    redacted_preview: Mapped[str] = mapped_column(String(240), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[IntakeDraftStatus] = mapped_column(
        Enum(IntakeDraftStatus, native_enum=False, length=24), nullable=False, index=True
    )
    extracted_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    missing_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    confirmed_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    contains_untrusted_instruction: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentOrchestrationRun(RecordMixin, Base):
    __tablename__ = "agent_orchestration_runs"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[OrchestrationStatus] = mapped_column(
        Enum(OrchestrationStatus, native_enum=False, length=16), nullable=False, index=True
    )
    current_state: Mapped[str] = mapped_column(String(64), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    redacted_input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    numeric_ledger: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    citation_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    blocked_issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    orchestrator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentStepRun(RecordMixin, Base):
    __tablename__ = "agent_step_runs"
    __table_args__ = (UniqueConstraint("run_id", "agent_code", name="uq_agent_step_run_agent"),)

    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_orchestration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AgentStepStatus] = mapped_column(
        Enum(AgentStepStatus, native_enum=False, length=16), nullable=False, index=True
    )
    input_schema_name: Mapped[str] = mapped_column(String(120), nullable=False)
    output_schema_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    citations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    prohibitions_checked: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
