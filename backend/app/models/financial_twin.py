from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
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
    FinancialEventDomain,
    FinancialEventStatus,
    HouseholdSnapshotStatus,
    LifeEventType,
)
from app.models.base import Base
from app.models.common import RecordMixin


class HouseholdSnapshot(RecordMixin, Base):
    __tablename__ = "household_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "event_cursor",
            name="uq_household_snapshots_event_cursor",
        ),
        UniqueConstraint(
            "snapshot_hash",
            name="uq_household_snapshots_snapshot_hash",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_financial_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_cursor: Mapped[int] = mapped_column(Integer, nullable=False)
    financial_graph_version: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    need_version: Mapped[str] = mapped_column(String(64), nullable=False)
    liability_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[HouseholdSnapshotStatus] = mapped_column(
        Enum(HouseholdSnapshotStatus, native_enum=False, length=16),
        default=HouseholdSnapshotStatus.ACTIVE,
        nullable=False,
        index=True,
    )


class FinancialEvent(RecordMixin, Base):
    __tablename__ = "financial_events"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "event_hash",
            name="uq_financial_events_household_hash",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_domain: Mapped[FinancialEventDomain] = mapped_column(
        Enum(FinancialEventDomain, native_enum=False, length=24), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    confirmation_status: Mapped[FinancialEventStatus] = mapped_column(
        Enum(FinancialEventStatus, native_enum=False, length=16),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    processed_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )


class LifeEvent(RecordMixin, Base):
    __tablename__ = "life_events"
    __table_args__ = (
        UniqueConstraint("financial_event_id", name="uq_life_events_financial_event"),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    financial_event_id: Mapped[str] = mapped_column(
        ForeignKey("financial_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    life_event_type: Mapped[LifeEventType] = mapped_column(
        Enum(LifeEventType, native_enum=False, length=32), nullable=False, index=True
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_financial_impact: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
