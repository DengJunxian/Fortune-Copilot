from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.common import RecordMixin


class DemoRun(RecordMixin, Base):
    """Durable orchestration ledger for the synthetic competition story."""

    __tablename__ = "demo_runs"
    __table_args__ = (
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_demo_runs_progress_percent",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    story_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recovered_from_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    offline_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    external_network_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentSuiteRun(RecordMixin, Base):
    """Test-only experiment ledger; it never represents production or bank outcomes."""

    __tablename__ = "experiment_suite_runs"

    suite_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    main_demo_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
