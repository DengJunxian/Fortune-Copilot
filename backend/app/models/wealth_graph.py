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
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    AssetPurposeDimension,
    ComplexityLevel,
    FinancialEntityType,
    OwnershipType,
    RiskLevel,
)
from app.models.base import Base
from app.models.common import RecordMixin
from app.models.finance import MONEY, RATIO

QUANTITY = Numeric(28, 8)


class FinancialEntity(RecordMixin, Base):
    __tablename__ = "financial_entities"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "external_reference",
            name="uq_financial_entities_household_external_reference",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[FinancialEntityType] = mapped_column(
        Enum(FinancialEntityType, native_enum=False, length=24), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(64), default="CN", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class FinancialAccount(RecordMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "external_reference",
            name="uq_financial_accounts_household_external_reference",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_entity_id: Mapped[str] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_type: Mapped[str] = mapped_column(String(64), nullable=False)
    account_wrapper: Mapped[AccountWrapper] = mapped_column(
        Enum(AccountWrapper, native_enum=False, length=32),
        default=AccountWrapper.ORDINARY,
        nullable=False,
    )
    jurisdiction: Mapped[str] = mapped_column(String(64), default="CN", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    restriction_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Position(RecordMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("legacy_asset_id", name="uq_positions_legacy_asset_id"),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    owner_entity_id: Mapped[str] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    legacy_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    enterprise_id: Mapped[str | None] = mapped_column(
        ForeignKey("enterprise_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    instrument_type: Mapped[AssetCategory] = mapped_column(
        Enum(AssetCategory, native_enum=False, length=40), nullable=False
    )
    instrument_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY, nullable=True)
    acquisition_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    market_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    purpose_dimension: Mapped[AssetPurposeDimension] = mapped_column(
        Enum(AssetPurposeDimension, native_enum=False, length=16), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    liquidity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    complexity_level: Mapped[ComplexityLevel] = mapped_column(
        Enum(ComplexityLevel, native_enum=False, length=24), nullable=False
    )
    principal_loss_possible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    legally_principal_guaranteed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lock_up: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    withdrawable_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class OwnershipEdge(RecordMixin, Base):
    __tablename__ = "ownership_edges"
    __table_args__ = (
        UniqueConstraint(
            "owner_entity_id",
            "owned_entity_id",
            "ownership_type",
            "effective_from",
            name="uq_ownership_edges_effective_relation",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_entity_id: Mapped[str] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owned_entity_id: Mapped[str] = mapped_column(
        ForeignKey("financial_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ownership_type: Mapped[OwnershipType] = mapped_column(
        Enum(OwnershipType, native_enum=False, length=32), nullable=False
    )
    ownership_ratio: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
