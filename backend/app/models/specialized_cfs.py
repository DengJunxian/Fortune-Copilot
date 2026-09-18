from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    CFSTimeHorizon,
    CurrencyExposureDirection,
    CurrencyExposureHorizon,
    CurrencyExposureType,
    InstitutionalEntitlementType,
    ProfessionalReferralUrgency,
    SpecializedComplexity,
    TrustSuccessionNeedType,
)
from app.models.base import Base
from app.models.common import RecordMixin
from app.models.finance import MONEY, RATIO


class InstitutionalEntitlement(RecordMixin, Base):
    __tablename__ = "institutional_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "member_id",
            "entitlement_type",
            "source_kind",
            name="uq_institutional_entitlement_source",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entitlement_type: Mapped[InstitutionalEntitlementType] = mapped_column(
        Enum(InstitutionalEntitlementType, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    expected_income: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    start_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    guaranteed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lock_up: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CurrencyExposure(RecordMixin, Base):
    __tablename__ = "currency_exposures"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "entity_id",
            "currency",
            "exposure_type",
            "direction",
            "horizon",
            name="uq_currency_exposure_bucket",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    exposure_type: Mapped[CurrencyExposureType] = mapped_column(
        Enum(CurrencyExposureType, native_enum=False, length=32), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    direction: Mapped[CurrencyExposureDirection] = mapped_column(
        Enum(CurrencyExposureDirection, native_enum=False, length=16), nullable=False
    )
    horizon: Mapped[CurrencyExposureHorizon] = mapped_column(
        Enum(CurrencyExposureHorizon, native_enum=False, length=16), nullable=False
    )
    source_record_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class TrustSuccessionNeed(RecordMixin, Base):
    __tablename__ = "trust_succession_needs"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "need_type",
            name="uq_trust_succession_need_type",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    need_type: Mapped[TrustSuccessionNeedType] = mapped_column(
        Enum(TrustSuccessionNeedType, native_enum=False, length=40),
        nullable=False,
        index=True,
    )
    beneficiaries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    assets_in_scope: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    enterprise_in_scope: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    urgency: Mapped[ProfessionalReferralUrgency] = mapped_column(
        Enum(ProfessionalReferralUrgency, native_enum=False, length=16), nullable=False
    )
    complexity: Mapped[SpecializedComplexity] = mapped_column(
        Enum(SpecializedComplexity, native_enum=False, length=16), nullable=False
    )
    professional_review_required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PhilanthropyGoal(RecordMixin, Base):
    __tablename__ = "philanthropy_goals"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "target_cause",
            "time_horizon",
            name="uq_philanthropy_goal_cause_horizon",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    annual_budget: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    target_cause: Mapped[str] = mapped_column(String(160), nullable=False)
    funding_asset: Mapped[str | None] = mapped_column(String(160), nullable=True)
    time_horizon: Mapped[CFSTimeHorizon] = mapped_column(
        Enum(CFSTimeHorizon, native_enum=False, length=24), nullable=False
    )
    family_participation: Mapped[str] = mapped_column(String(240), nullable=False)
    governance_preference: Mapped[str] = mapped_column(String(240), nullable=False)
    professional_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
