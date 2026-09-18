from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    CFSComponentStatus,
    CFSComponentType,
    CFSSolutionStatus,
    CFSTimeHorizon,
    ProfessionalReferralStatus,
    ProfessionalReferralUrgency,
    ProfessionalSpecialistType,
)
from app.models.base import Base
from app.models.common import RecordMixin
from app.models.finance import MONEY


class CFSSolution(RecordMixin, Base):
    __tablename__ = "cfs_solutions"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "solution_version",
            name="uq_cfs_solutions_household_version",
        ),
        UniqueConstraint(
            "household_id",
            "decision_hash",
            name="uq_cfs_solutions_household_decision_hash",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("client_wealth_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("household_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    solution_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CFSSolutionStatus] = mapped_column(
        Enum(CFSSolutionStatus, native_enum=False, length=24), nullable=False, index=True
    )
    need_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_budget_version: Mapped[str] = mapped_column(String(64), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    decision_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class CFSSolutionComponent(RecordMixin, Base):
    __tablename__ = "cfs_solution_components"
    __table_args__ = (
        UniqueConstraint(
            "solution_id",
            "wealth_need_id",
            "component_type",
            name="uq_cfs_component_solution_need_type",
        ),
    )

    solution_id: Mapped[str] = mapped_column(
        ForeignKey("cfs_solutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wealth_need_id: Mapped[str | None] = mapped_column(
        ForeignKey("wealth_needs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    component_type: Mapped[CFSComponentType] = mapped_column(
        Enum(CFSComponentType, native_enum=False, length=32), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    time_horizon: Mapped[CFSTimeHorizon] = mapped_column(
        Enum(CFSTimeHorizon, native_enum=False, length=24), nullable=False
    )
    recommended_action: Mapped[str] = mapped_column(String(800), nullable=False)
    product_mapping_allowed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    professional_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    required_specialist: Mapped[ProfessionalSpecialistType | None] = mapped_column(
        Enum(ProfessionalSpecialistType, native_enum=False, length=40), nullable=True
    )
    status: Mapped[CFSComponentStatus] = mapped_column(
        Enum(CFSComponentStatus, native_enum=False, length=40), nullable=False, index=True
    )
    rationale: Mapped[str] = mapped_column(String(1200), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ProfessionalServiceReferral(RecordMixin, Base):
    __tablename__ = "professional_service_referrals"
    __table_args__ = (
        UniqueConstraint(
            "solution_id",
            "component_id",
            "specialist_type",
            name="uq_professional_referral_component_specialist",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    solution_id: Mapped[str] = mapped_column(
        ForeignKey("cfs_solutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_id: Mapped[str] = mapped_column(
        ForeignKey("cfs_solution_components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    specialist_type: Mapped[ProfessionalSpecialistType] = mapped_column(
        Enum(ProfessionalSpecialistType, native_enum=False, length=40), nullable=False
    )
    trigger_reason: Mapped[str] = mapped_column(String(800), nullable=False)
    urgency: Mapped[ProfessionalReferralUrgency] = mapped_column(
        Enum(ProfessionalReferralUrgency, native_enum=False, length=16), nullable=False
    )
    status: Mapped[ProfessionalReferralStatus] = mapped_column(
        Enum(ProfessionalReferralStatus, native_enum=False, length=16),
        nullable=False,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
