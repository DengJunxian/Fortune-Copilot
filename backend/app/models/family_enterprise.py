from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    CashFlowFrequency,
    EnterpriseCashflowStability,
    EnterpriseCashflowType,
    EnterpriseEventStatus,
    EnterpriseEventType,
    EnterpriseGuaranteeType,
    EnterpriseInstrumentType,
    EnterpriseListedStatus,
    EnterpriseStage,
    EnterpriseType,
    EnterpriseValuationMethod,
    EvidenceConfidence,
)
from app.models.base import Base
from app.models.common import RecordMixin
from app.models.finance import MONEY

ENTERPRISE_RATIO = Numeric(12, 6)


class EnterpriseProfile(RecordMixin, Base):
    __tablename__ = "enterprise_profiles"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry: Mapped[str] = mapped_column(String(120), nullable=False)
    stage: Mapped[EnterpriseStage] = mapped_column(
        Enum(EnterpriseStage, native_enum=False, length=24), nullable=False, index=True
    )
    jurisdiction: Mapped[str] = mapped_column(String(64), nullable=False)
    listed_status: Mapped[EnterpriseListedStatus] = mapped_column(
        Enum(EnterpriseListedStatus, native_enum=False, length=16), nullable=False, index=True
    )
    enterprise_type: Mapped[EnterpriseType] = mapped_column(
        Enum(EnterpriseType, native_enum=False, length=32), nullable=False
    )


class EnterpriseOwnership(RecordMixin, Base):
    __tablename__ = "enterprise_ownerships"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "owner_entity_id",
            "instrument_type",
            "vesting_date",
            name="uq_enterprise_ownership_instrument",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[str] = mapped_column(
        ForeignKey("enterprise_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_entity_id: Mapped[str] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ownership_ratio: Mapped[Decimal] = mapped_column(ENTERPRISE_RATIO, nullable=False)
    voting_ratio: Mapped[Decimal] = mapped_column(ENTERPRISE_RATIO, nullable=False)
    instrument_type: Mapped[EnterpriseInstrumentType] = mapped_column(
        Enum(EnterpriseInstrumentType, native_enum=False, length=32), nullable=False
    )
    vesting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lockup_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class EnterpriseValuation(RecordMixin, Base):
    __tablename__ = "enterprise_valuations"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "valuation_date",
            "valuation_method",
            name="uq_enterprise_valuation_basis",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[str] = mapped_column(
        ForeignKey("enterprise_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equity_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    valuation_method: Mapped[EnterpriseValuationMethod] = mapped_column(
        Enum(EnterpriseValuationMethod, native_enum=False, length=32), nullable=False
    )
    confidence: Mapped[EvidenceConfidence] = mapped_column(
        Enum(EvidenceConfidence, native_enum=False, length=16), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class EnterpriseCashflow(RecordMixin, Base):
    __tablename__ = "enterprise_cashflows"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "member_id",
            "cashflow_type",
            "frequency",
            name="uq_enterprise_cashflow_source",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[str] = mapped_column(
        ForeignKey("enterprise_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cashflow_type: Mapped[EnterpriseCashflowType] = mapped_column(
        Enum(EnterpriseCashflowType, native_enum=False, length=32), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    frequency: Mapped[CashFlowFrequency] = mapped_column(
        Enum(CashFlowFrequency, native_enum=False, length=16), nullable=False
    )
    stability: Mapped[EnterpriseCashflowStability] = mapped_column(
        Enum(EnterpriseCashflowStability, native_enum=False, length=16), nullable=False
    )


class EnterpriseGuarantee(RecordMixin, Base):
    __tablename__ = "enterprise_guarantees"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "member_id",
            "guarantee_type",
            "expiry_date",
            name="uq_enterprise_guarantee_exposure",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[str] = mapped_column(
        ForeignKey("enterprise_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    guarantee_type: Mapped[EnterpriseGuaranteeType] = mapped_column(
        Enum(EnterpriseGuaranteeType, native_enum=False, length=32), nullable=False
    )
    guaranteed_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    outstanding_exposure: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class EnterpriseLiquidityEvent(RecordMixin, Base):
    __tablename__ = "enterprise_liquidity_events"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "event_type",
            "expected_date",
            name="uq_enterprise_liquidity_event",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_id: Mapped[str] = mapped_column(
        ForeignKey("enterprise_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[EnterpriseEventType] = mapped_column(
        Enum(EnterpriseEventType, native_enum=False, length=32), nullable=False, index=True
    )
    expected_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    estimated_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    probability: Mapped[Decimal] = mapped_column(ENTERPRISE_RATIO, nullable=False)
    lockup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[EnterpriseEventStatus] = mapped_column(
        Enum(EnterpriseEventStatus, native_enum=False, length=16), nullable=False, index=True
    )
