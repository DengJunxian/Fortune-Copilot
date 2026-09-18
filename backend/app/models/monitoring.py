from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    AdvisorTriggerStatus,
    BehaviorObservationType,
    MonitoringAlertStatus,
    MonitoringCadence,
    MonitoringComparator,
    MonitoringPolicyType,
    MonitoringSeverity,
    RiskLimitEffect,
)
from app.models.base import Base
from app.models.common import RecordMixin


class MonitoringPolicy(RecordMixin, Base):
    __tablename__ = "monitoring_policies"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "policy_type",
            "rule_version",
            name="uq_monitoring_policy_household_type_version",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_type: Mapped[MonitoringPolicyType] = mapped_column(
        Enum(MonitoringPolicyType, native_enum=False, length=40), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(String(80), nullable=False)
    comparator: Mapped[MonitoringComparator] = mapped_column(
        Enum(MonitoringComparator, native_enum=False, length=32), nullable=False
    )
    threshold: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cadence: Mapped[MonitoringCadence] = mapped_column(
        Enum(MonitoringCadence, native_enum=False, length=24), nullable=False
    )
    severity: Mapped[MonitoringSeverity] = mapped_column(
        Enum(MonitoringSeverity, native_enum=False, length=16), nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)


class MonitoringAlert(RecordMixin, Base):
    __tablename__ = "monitoring_alerts"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    monitoring_policy_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    financial_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trigger_reason: Mapped[str] = mapped_column(String(800), nullable=False)
    client_impact: Mapped[str] = mapped_column(String(800), nullable=False)
    severity: Mapped[MonitoringSeverity] = mapped_column(
        Enum(MonitoringSeverity, native_enum=False, length=16), nullable=False, index=True
    )
    recommended_action: Mapped[str] = mapped_column(String(1000), nullable=False)
    do_not_sell_flag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    required_specialist: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[MonitoringAlertStatus] = mapped_column(
        Enum(MonitoringAlertStatus, native_enum=False, length=16),
        default=MonitoringAlertStatus.OPEN,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdvisorTrigger(RecordMixin, Base):
    __tablename__ = "advisor_triggers"
    __table_args__ = (
        UniqueConstraint(
            "monitoring_alert_id",
            "trigger_type",
            name="uq_advisor_trigger_alert_type",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    monitoring_alert_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_alerts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    urgency: Mapped[MonitoringSeverity] = mapped_column(
        Enum(MonitoringSeverity, native_enum=False, length=16), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(800), nullable=False)
    required_role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    follow_up_due: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[AdvisorTriggerStatus] = mapped_column(
        Enum(AdvisorTriggerStatus, native_enum=False, length=16),
        default=AdvisorTriggerStatus.OPEN,
        nullable=False,
        index=True,
    )


class BehaviorObservation(RecordMixin, Base):
    __tablename__ = "behavior_observations"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "observation_type",
            "observed_at",
            "source_reference",
            name="uq_behavior_observation_source",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    financial_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    observation_type: Mapped[BehaviorObservationType] = mapped_column(
        Enum(BehaviorObservationType, native_enum=False, length=40), nullable=False, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    signal_strength: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    risk_limit_effect: Mapped[RiskLimitEffect] = mapped_column(
        Enum(RiskLimitEffect, native_enum=False, length=16), nullable=False
    )
    hard_facts_changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
