from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import CashFlowFrequency, GoalRigidity, LiabilityStreamType
from app.models.base import Base
from app.models.common import RecordMixin
from app.models.finance import MONEY, RATIO


class LiabilityStream(RecordMixin, Base):
    """A dated household obligation derived from, but not replacing, legacy goals."""

    __tablename__ = "liability_streams"
    __table_args__ = (
        UniqueConstraint("source_goal_id", name="uq_liability_streams_source_goal"),
        UniqueConstraint(
            "source_responsibility_id",
            name="uq_liability_streams_source_responsibility",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wealth_need_id: Mapped[str | None] = mapped_column(
        ForeignKey("wealth_needs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_goal_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_responsibility_id: Mapped[str | None] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    beneficiary_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    stream_type: Mapped[LiabilityStreamType] = mapped_column(
        Enum(LiabilityStreamType, native_enum=False, length=32), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    frequency: Mapped[CashFlowFrequency] = mapped_column(
        Enum(CashFlowFrequency, native_enum=False, length=16), nullable=False
    )
    base_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    inflation_index_code: Mapped[str] = mapped_column(String(40), nullable=False)
    annual_growth_assumption: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    rigidity: Mapped[GoalRigidity] = mapped_column(
        Enum(GoalRigidity, native_enum=False, length=16), nullable=False
    )
    deferrable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    funding_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    fallback_action: Mapped[str] = mapped_column(String(500), nullable=False)
    stream_version: Mapped[str] = mapped_column(String(64), nullable=False)


class LiabilityStreamCashflow(RecordMixin, Base):
    __tablename__ = "liability_stream_cashflows"
    __table_args__ = (
        UniqueConstraint(
            "liability_stream_id",
            "sequence",
            name="uq_liability_stream_cashflows_sequence",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    liability_stream_id: Mapped[str] = mapped_column(
        ForeignKey("liability_streams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False)
