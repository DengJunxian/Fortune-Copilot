"""Add the V5 household financial graph and backfill legacy assets.

Revision ID: 0016_v5_financial_graph_core
Revises: 0015_fortune_copilot_v4
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    AssetPurposeDimension,
    ComplexityLevel,
    FinancialEntityType,
    OwnershipType,
    RiskLevel,
)

revision: str = "0016_v5_financial_graph_core"
down_revision: str | None = "0015_fortune_copilot_v4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _record_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("currency", sa.String(3), server_default="CNY", nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("data_source", sa.String(64), server_default="user", nullable=False),
        sa.Column("is_user_confirmed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _base_values(
    *,
    record_id: str,
    currency: str,
    valuation_date: date | None,
    confirmed: bool,
    now: datetime,
) -> dict[str, object]:
    return {
        "id": record_id,
        "currency": currency,
        "valuation_date": valuation_date,
        "data_source": "v5_backfill_0016",
        "is_user_confirmed": confirmed,
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
        "deleted_at": None,
    }


def _backfill_financial_graph() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    households = sa.Table("households", metadata, autoload_with=bind)
    members = sa.Table("household_members", metadata, autoload_with=bind)
    assets = sa.Table("assets", metadata, autoload_with=bind)
    entities = sa.Table("financial_entities", metadata, autoload_with=bind)
    accounts = sa.Table("financial_accounts", metadata, autoload_with=bind)
    positions = sa.Table("positions", metadata, autoload_with=bind)
    edges = sa.Table("ownership_edges", metadata, autoload_with=bind)

    now = datetime.now(UTC)
    household_rows = bind.execute(
        sa.select(households).where(households.c.is_deleted.is_(False))
    ).mappings()
    for household in household_rows:
        household_id = str(household["id"])
        household_entity_id = str(uuid4())
        account_id = str(uuid4())
        currency = str(household["currency"] or "CNY")
        valuation_date = household["valuation_date"]
        confirmed = bool(household["is_user_confirmed"])
        bind.execute(
            entities.insert().values(
                **_base_values(
                    record_id=household_entity_id,
                    currency=currency,
                    valuation_date=valuation_date,
                    confirmed=confirmed,
                    now=now,
                ),
                household_id=household_id,
                entity_type=FinancialEntityType.HOUSEHOLD.name,
                display_name=str(household["name"]),
                jurisdiction="CN",
                external_reference=f"legacy:household:{household_id}",
                metadata_json={
                    "region": household["region"],
                    "legacy_version": household["version"],
                },
            )
        )
        bind.execute(
            accounts.insert().values(
                **_base_values(
                    record_id=account_id,
                    currency=currency,
                    valuation_date=valuation_date,
                    confirmed=confirmed,
                    now=now,
                ),
                household_id=household_id,
                owner_entity_id=household_entity_id,
                provider_name="Legacy household register",
                account_type="legacy_aggregate",
                account_wrapper=AccountWrapper.ORDINARY.name,
                jurisdiction="CN",
                external_reference=f"legacy:assets:{household_id}",
                restriction_json={"compatibility_projection": True},
            )
        )

        member_entities: dict[str, str] = {}
        member_rows = bind.execute(
            sa.select(members).where(
                members.c.household_id == household_id,
                members.c.is_deleted.is_(False),
            )
        ).mappings()
        for member in member_rows:
            member_id = str(member["id"])
            member_entity_id = str(uuid4())
            member_entities[member_id] = member_entity_id
            bind.execute(
                entities.insert().values(
                    **_base_values(
                        record_id=member_entity_id,
                        currency=str(member["currency"] or currency),
                        valuation_date=member["valuation_date"],
                        confirmed=bool(member["is_user_confirmed"]),
                        now=now,
                    ),
                    household_id=household_id,
                    entity_type=FinancialEntityType.PERSON.name,
                    display_name=str(member["display_name"]),
                    jurisdiction="CN",
                    external_reference=f"legacy:member:{member_id}",
                    metadata_json={
                        "relationship": member["relationship"],
                        "legacy_version": member["version"],
                    },
                )
            )
            bind.execute(
                edges.insert().values(
                    **_base_values(
                        record_id=str(uuid4()),
                        currency=currency,
                        valuation_date=member["valuation_date"],
                        confirmed=bool(member["is_user_confirmed"]),
                        now=now,
                    ),
                    household_id=household_id,
                    owner_entity_id=household_entity_id,
                    owned_entity_id=member_entity_id,
                    ownership_type=OwnershipType.HOUSEHOLD_MEMBER.name,
                    ownership_ratio=None,
                    effective_from=None,
                    effective_to=None,
                    evidence_json={"legacy_member_id": member_id},
                )
            )

        asset_rows = bind.execute(
            sa.select(assets).where(
                assets.c.household_id == household_id,
                assets.c.is_deleted.is_(False),
            )
        ).mappings()
        for asset in asset_rows:
            asset_id = str(asset["id"])
            owner_member_id = (
                str(asset["owner_member_id"]) if asset["owner_member_id"] is not None else None
            )
            evidence_fields = (
                "subcategory",
                "liquidity_level",
                "purpose",
                "pledged",
                "ownership",
                "property_use",
                "account_wrapper",
                "volatility",
                "product_complexity",
                "institution_type",
                "household_role",
                "region_code",
                "owner_member_id",
                "version",
            )
            evidence = {key: _json_value(asset[key]) for key in evidence_fields}
            evidence["legacy_asset_id"] = asset_id
            evidence["legacy_created_at"] = _json_value(asset["created_at"])
            bind.execute(
                positions.insert().values(
                    **_base_values(
                        record_id=str(uuid4()),
                        currency=str(asset["currency"] or currency),
                        valuation_date=asset["valuation_date"],
                        confirmed=bool(asset["is_user_confirmed"]),
                        now=now,
                    ),
                    household_id=household_id,
                    account_id=account_id,
                    owner_entity_id=member_entities.get(owner_member_id, household_entity_id),
                    product_id=None,
                    legacy_asset_id=asset_id,
                    instrument_type=str(asset["category"]),
                    instrument_code=None,
                    name=str(asset["name"]),
                    quantity=None,
                    acquisition_cost=asset["acquisition_cost"],
                    market_value=asset["market_value"],
                    purpose_dimension=str(asset["purpose_dimension"]),
                    risk_level=str(asset["risk_level"]),
                    liquidity_days=int(asset["liquidity_days"]),
                    complexity_level=str(asset["product_complexity"]),
                    principal_loss_possible=bool(asset["principal_loss_possible"]),
                    legally_principal_guaranteed=bool(
                        asset["legally_principal_guaranteed"]
                    ),
                    lock_up=bool(asset["lock_up"]),
                    withdrawable_date=asset["withdrawable_date"],
                    source_kind=str(asset["source_kind"]),
                    evidence_json=evidence,
                )
            )


def upgrade() -> None:
    op.create_table(
        "financial_entities",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(FinancialEntityType, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("jurisdiction", sa.String(64), server_default="CN", nullable=False),
        sa.Column("external_reference", sa.String(200), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "external_reference",
            name="uq_financial_entities_household_external_reference",
        ),
    )
    op.create_index("ix_financial_entities_household_id", "financial_entities", ["household_id"])
    op.create_index("ix_financial_entities_entity_type", "financial_entities", ["entity_type"])
    op.create_index("ix_financial_entities_is_deleted", "financial_entities", ["is_deleted"])

    op.create_table(
        "financial_accounts",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("owner_entity_id", sa.String(36), nullable=False),
        sa.Column("provider_name", sa.String(160), nullable=False),
        sa.Column("account_type", sa.String(64), nullable=False),
        sa.Column(
            "account_wrapper",
            sa.Enum(AccountWrapper, native_enum=False, length=32),
            server_default="ORDINARY",
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String(64), server_default="CN", nullable=False),
        sa.Column("external_reference", sa.String(200), nullable=True),
        sa.Column("restriction_json", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["owner_entity_id"], ["financial_entities.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "household_id",
            "external_reference",
            name="uq_financial_accounts_household_external_reference",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_accounts_household_id", "financial_accounts", ["household_id"])
    op.create_index(
        "ix_financial_accounts_owner_entity_id",
        "financial_accounts",
        ["owner_entity_id"],
    )
    op.create_index("ix_financial_accounts_is_deleted", "financial_accounts", ["is_deleted"])

    op.create_table(
        "positions",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("owner_entity_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=True),
        sa.Column("legacy_asset_id", sa.String(36), nullable=True),
        sa.Column(
            "instrument_type",
            sa.Enum(AssetCategory, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("instrument_code", sa.String(80), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=True),
        sa.Column("acquisition_cost", sa.Numeric(20, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "purpose_dimension",
            sa.Enum(AssetPurposeDimension, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "risk_level",
            sa.Enum(RiskLevel, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("liquidity_days", sa.Integer(), nullable=False),
        sa.Column(
            "complexity_level",
            sa.Enum(ComplexityLevel, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("principal_loss_possible", sa.Boolean(), nullable=False),
        sa.Column("legally_principal_guaranteed", sa.Boolean(), nullable=False),
        sa.Column("lock_up", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("withdrawable_date", sa.Date(), nullable=True),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("evidence_json", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["financial_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["owner_entity_id"], ["financial_entities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["legacy_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_asset_id", name="uq_positions_legacy_asset_id"),
    )
    op.create_index("ix_positions_household_id", "positions", ["household_id"])
    op.create_index("ix_positions_account_id", "positions", ["account_id"])
    op.create_index("ix_positions_owner_entity_id", "positions", ["owner_entity_id"])
    op.create_index("ix_positions_is_deleted", "positions", ["is_deleted"])

    op.create_table(
        "ownership_edges",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("owner_entity_id", sa.String(36), nullable=False),
        sa.Column("owned_entity_id", sa.String(36), nullable=False),
        sa.Column(
            "ownership_type",
            sa.Enum(OwnershipType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("ownership_ratio", sa.Numeric(9, 6), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["owner_entity_id"], ["financial_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owned_entity_id"], ["financial_entities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_entity_id",
            "owned_entity_id",
            "ownership_type",
            "effective_from",
            name="uq_ownership_edges_effective_relation",
        ),
    )
    op.create_index("ix_ownership_edges_household_id", "ownership_edges", ["household_id"])
    op.create_index("ix_ownership_edges_owner_entity_id", "ownership_edges", ["owner_entity_id"])
    op.create_index("ix_ownership_edges_owned_entity_id", "ownership_edges", ["owned_entity_id"])
    op.create_index("ix_ownership_edges_is_deleted", "ownership_edges", ["is_deleted"])

    _backfill_financial_graph()


def downgrade() -> None:
    op.drop_index("ix_ownership_edges_is_deleted", table_name="ownership_edges")
    op.drop_index("ix_ownership_edges_owned_entity_id", table_name="ownership_edges")
    op.drop_index("ix_ownership_edges_owner_entity_id", table_name="ownership_edges")
    op.drop_index("ix_ownership_edges_household_id", table_name="ownership_edges")
    op.drop_table("ownership_edges")
    op.drop_index("ix_positions_is_deleted", table_name="positions")
    op.drop_index("ix_positions_owner_entity_id", table_name="positions")
    op.drop_index("ix_positions_account_id", table_name="positions")
    op.drop_index("ix_positions_household_id", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_financial_accounts_is_deleted", table_name="financial_accounts")
    op.drop_index("ix_financial_accounts_owner_entity_id", table_name="financial_accounts")
    op.drop_index("ix_financial_accounts_household_id", table_name="financial_accounts")
    op.drop_table("financial_accounts")
    op.drop_index("ix_financial_entities_is_deleted", table_name="financial_entities")
    op.drop_index("ix_financial_entities_entity_type", table_name="financial_entities")
    op.drop_index("ix_financial_entities_household_id", table_name="financial_entities")
    op.drop_table("financial_entities")
