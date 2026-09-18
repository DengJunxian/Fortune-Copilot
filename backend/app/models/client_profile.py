from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    ClientProfileStatus,
    ComplexityBand,
    GoalRigidity,
    LifecycleStage,
    PensionStage,
    ProfileTagSeverity,
    RiskLevel,
    ServiceComplexity,
    WealthNeedStatus,
    WealthNeedType,
    WealthTier,
)
from app.models.base import Base
from app.models.common import RecordMixin
from app.models.finance import MONEY, RATIO


class ClientWealthProfile(RecordMixin, Base):
    __tablename__ = "client_wealth_profiles"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "profile_version",
            name="uq_client_wealth_profiles_household_version",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_snapshot_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(
        Enum(LifecycleStage, native_enum=False, length=40), nullable=False
    )
    wealth_tier: Mapped[WealthTier] = mapped_column(
        Enum(WealthTier, native_enum=False, length=32), nullable=False
    )
    service_complexity: Mapped[ServiceComplexity] = mapped_column(
        Enum(ServiceComplexity, native_enum=False, length=24), nullable=False
    )
    risk_capacity: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    risk_willingness: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    behavior_limit: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    enterprise_dependency_level: Mapped[ComplexityBand] = mapped_column(
        Enum(ComplexityBand, native_enum=False, length=16), nullable=False
    )
    cross_border_complexity: Mapped[ComplexityBand] = mapped_column(
        Enum(ComplexityBand, native_enum=False, length=16), nullable=False
    )
    succession_complexity: Mapped[ComplexityBand] = mapped_column(
        Enum(ComplexityBand, native_enum=False, length=16), nullable=False
    )
    pension_stage: Mapped[PensionStage] = mapped_column(
        Enum(PensionStage, native_enum=False, length=24), nullable=False
    )
    completeness_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    data_gaps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[ClientProfileStatus] = mapped_column(
        Enum(ClientProfileStatus, native_enum=False, length=24), nullable=False, index=True
    )
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ClientProfileTag(RecordMixin, Base):
    __tablename__ = "client_profile_tags"
    __table_args__ = (
        UniqueConstraint("profile_id", "tag_code", name="uq_client_profile_tags_profile_code"),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("client_wealth_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    tag_category: Mapped[str] = mapped_column(String(48), nullable=False)
    value: Mapped[str] = mapped_column(String(240), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    severity: Mapped[ProfileTagSeverity] = mapped_column(
        Enum(ProfileTagSeverity, native_enum=False, length=16), nullable=False
    )
    source_record_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WealthNeed(RecordMixin, Base):
    __tablename__ = "wealth_needs"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("client_wealth_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    need_type: Mapped[WealthNeedType] = mapped_column(
        Enum(WealthNeedType, native_enum=False, length=40), nullable=False, index=True
    )
    beneficiary_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rigidity: Mapped[GoalRigidity] = mapped_column(
        Enum(GoalRigidity, native_enum=False, length=16), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[WealthNeedStatus] = mapped_column(
        Enum(WealthNeedStatus, native_enum=False, length=24), nullable=False, index=True
    )
    confidence: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    professional_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    source_record_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WealthNeedPriority(RecordMixin, Base):
    __tablename__ = "wealth_need_priorities"
    __table_args__ = (UniqueConstraint("wealth_need_id", name="uq_wealth_need_priorities_need"),)

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wealth_need_id: Mapped[str] = mapped_column(
        ForeignKey("wealth_needs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    hard_constraint: Mapped[bool] = mapped_column(Boolean, nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
