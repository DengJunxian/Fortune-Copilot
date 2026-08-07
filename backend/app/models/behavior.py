from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import BehaviorInterventionStatus, BehaviorSessionStatus, RiskLevel
from app.models.base import Base
from app.models.common import RecordMixin

RATIO = Numeric(9, 6)


class BehaviorExperimentSession(RecordMixin, Base):
    __tablename__ = "behavior_experiment_sessions"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("behavior_assessments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[BehaviorSessionStatus] = mapped_column(
        Enum(BehaviorSessionStatus, native_enum=False, length=16),
        default=BehaviorSessionStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    questionnaire: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    questionnaire_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    experiment_score: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    objective_capacity_limit: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    questionnaire_claim_limit: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    experiment_limit: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=True
    )
    effective_risk_limit: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=True
    )
    information_status: Mapped[str] = mapped_column(
        String(24), default="collecting", nullable=False
    )
    assigned_variant: Mapped[str] = mapped_column(String(64), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    experiment_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )
    calculation_source: Mapped[str] = mapped_column(
        String(48), default="deterministic_behavior_engine", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BehaviorExperimentResponse(RecordMixin, Base):
    __tablename__ = "behavior_experiment_responses"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "experiment_code", name="uq_behavior_response_session_experiment"
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("behavior_experiment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_code: Mapped[str] = mapped_column(String(64), nullable=False)
    choice_code: Mapped[str] = mapped_column(String(64), nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    modification_count: Mapped[int] = mapped_column(Integer, nullable=False)
    consistency_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BehaviorBiasFinding(RecordMixin, Base):
    __tablename__ = "behavior_bias_findings"
    __table_args__ = (
        UniqueConstraint("session_id", "bias_code", name="uq_behavior_bias_session_code"),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("behavior_experiment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bias_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[str] = mapped_column(String(800), nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    source_experiment_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class BehaviorIntervention(RecordMixin, Base):
    __tablename__ = "behavior_interventions"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "intervention_code", name="uq_behavior_intervention_session_code"
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("behavior_experiment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_goal_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_goals.id", ondelete="SET NULL"), nullable=True
    )
    intervention_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[BehaviorInterventionStatus] = mapped_column(
        Enum(BehaviorInterventionStatus, native_enum=False, length=16),
        default=BehaviorInterventionStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    trigger_biases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scenario_code: Mapped[str] = mapped_column(String(80), nullable=False)
    personalized_message: Mapped[str] = mapped_column(String(1000), nullable=False)
    action_instruction: Mapped[str] = mapped_column(String(800), nullable=False)
    cooling_period_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_variant: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BehaviorExperimentAssignment(RecordMixin, Base):
    __tablename__ = "behavior_experiment_assignments"
    __table_args__ = (UniqueConstraint("session_id", name="uq_behavior_assignment_session"),)

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("behavior_experiment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_key: Mapped[str] = mapped_column(String(64), nullable=False)
    framework_version: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assignment_method: Mapped[str] = mapped_column(String(64), nullable=False)
    assignment_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    eligible_data: Mapped[bool] = mapped_column(Boolean, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
