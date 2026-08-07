from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.common import RecordMixin


class IdentityAccessGrant(RecordMixin, Base):
    """Pseudonymous identity-zone link to a financial household object."""

    __tablename__ = "identity_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "actor_subject_hash",
            "household_id",
            "actor_role",
            name="uq_identity_access_actor_household_role",
        ),
    )

    actor_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    purpose: Mapped[str] = mapped_column(String(240), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrivacyRequest(RecordMixin, Base):
    __tablename__ = "privacy_requests"

    household_id: Mapped[str | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL"), nullable=True, index=True
    )
    household_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reason_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmation_method: Mapped[str] = mapped_column(String(64), nullable=False)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QualityGateRun(RecordMixin, Base):
    __tablename__ = "quality_gate_runs"

    household_id: Mapped[str | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL"), nullable=True, index=True
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    gate_version: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evaluated_by_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvaluationRun(RecordMixin, Base):
    __tablename__ = "evaluation_runs"

    suite_version: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
