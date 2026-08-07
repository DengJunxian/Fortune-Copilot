from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.domain.enums import EmploymentStability, LifecycleStage, RiskLevel
from app.models.base import Base
from app.models.common import RecordMixin


class Household(RecordMixin, Base):
    __tablename__ = "households"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(
        Enum(LifecycleStage, native_enum=False, length=40), nullable=False
    )
    region: Mapped[str] = mapped_column(String(120), nullable=False)
    demo_profile: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_synthetic: Mapped[bool] = mapped_column(default=False, nullable=False)
    planning_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    members: Mapped[list[HouseholdMember]] = orm_relationship(
        back_populates="household",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class HouseholdMember(RecordMixin, Base):
    __tablename__ = "household_members"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    relationship: Mapped[str] = mapped_column(String(40), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    occupation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employment_stability: Mapped[EmploymentStability] = mapped_column(
        Enum(EmploymentStability, native_enum=False, length=16), nullable=False
    )
    expected_retirement_age: Mapped[int | None] = mapped_column(nullable=True)
    health_risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16),
        default=RiskLevel.LOW,
        nullable=False,
    )

    household: Mapped[Household] = orm_relationship(back_populates="members")


class ConsentRecord(RecordMixin, Base):
    __tablename__ = "consent_records"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
