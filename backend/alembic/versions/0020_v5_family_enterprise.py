"""Add the V5 family-enterprise financial twin.

Revision ID: 0020_v5_family_enterprise
Revises: 0019_v5_persistent_financial_twin
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

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

revision: str = "0020_v5_family_enterprise"
down_revision: str | None = "0019_v5_persistent_financial_twin"
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


def _record_indexes(table: str, *columns: str) -> None:
    for column in (*columns, "is_deleted"):
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "enterprise_profiles",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("industry", sa.String(120), nullable=False),
        sa.Column(
            "stage",
            sa.Enum(EnterpriseStage, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String(64), nullable=False),
        sa.Column(
            "listed_status",
            sa.Enum(EnterpriseListedStatus, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "enterprise_type",
            sa.Enum(EnterpriseType, native_enum=False, length=32),
            nullable=False,
        ),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _record_indexes("enterprise_profiles", "household_id", "stage", "listed_status")

    op.create_table(
        "enterprise_ownerships",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("enterprise_id", sa.String(36), nullable=False),
        sa.Column("owner_entity_id", sa.String(36), nullable=False),
        sa.Column("ownership_ratio", sa.Numeric(12, 6), nullable=False),
        sa.Column("voting_ratio", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "instrument_type",
            sa.Enum(EnterpriseInstrumentType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("vesting_date", sa.Date(), nullable=True),
        sa.Column("lockup_end_date", sa.Date(), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprise_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_entity_id"], ["financial_entities.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id",
            "owner_entity_id",
            "instrument_type",
            "vesting_date",
            name="uq_enterprise_ownership_instrument",
        ),
    )
    _record_indexes(
        "enterprise_ownerships", "household_id", "enterprise_id", "owner_entity_id"
    )

    op.create_table(
        "enterprise_valuations",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("enterprise_id", sa.String(36), nullable=False),
        sa.Column("equity_value", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "valuation_method",
            sa.Enum(EnterpriseValuationMethod, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Enum(EvidenceConfidence, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(48), nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprise_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id",
            "valuation_date",
            "valuation_method",
            name="uq_enterprise_valuation_basis",
        ),
    )
    _record_indexes("enterprise_valuations", "household_id", "enterprise_id")

    op.create_table(
        "enterprise_cashflows",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("enterprise_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column(
            "cashflow_type",
            sa.Enum(EnterpriseCashflowType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "frequency",
            sa.Enum(CashFlowFrequency, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "stability",
            sa.Enum(EnterpriseCashflowStability, native_enum=False, length=16),
            nullable=False,
        ),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprise_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["household_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id",
            "member_id",
            "cashflow_type",
            "frequency",
            name="uq_enterprise_cashflow_source",
        ),
    )
    _record_indexes(
        "enterprise_cashflows", "household_id", "enterprise_id", "member_id"
    )

    op.create_table(
        "enterprise_guarantees",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("enterprise_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column(
            "guarantee_type",
            sa.Enum(EnterpriseGuaranteeType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("guaranteed_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("outstanding_exposure", sa.Numeric(20, 2), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprise_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["household_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id",
            "member_id",
            "guarantee_type",
            "expiry_date",
            name="uq_enterprise_guarantee_exposure",
        ),
    )
    _record_indexes(
        "enterprise_guarantees", "household_id", "enterprise_id", "member_id"
    )

    op.create_table(
        "enterprise_liquidity_events",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("enterprise_id", sa.String(36), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(EnterpriseEventType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("expected_date", sa.Date(), nullable=False),
        sa.Column("estimated_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("probability", sa.Numeric(12, 6), nullable=False),
        sa.Column("lockup", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum(EnterpriseEventStatus, native_enum=False, length=16),
            nullable=False,
        ),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["enterprise_id"], ["enterprise_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id",
            "event_type",
            "expected_date",
            name="uq_enterprise_liquidity_event",
        ),
    )
    _record_indexes(
        "enterprise_liquidity_events",
        "household_id",
        "enterprise_id",
        "event_type",
        "expected_date",
        "status",
    )

    with op.batch_alter_table("positions") as batch_op:
        batch_op.add_column(sa.Column("enterprise_id", sa.String(36), nullable=True))
        batch_op.create_index("ix_positions_enterprise_id", ["enterprise_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_positions_enterprise_id",
            "enterprise_profiles",
            ["enterprise_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.drop_constraint("fk_positions_enterprise_id", type_="foreignkey")
        batch_op.drop_index("ix_positions_enterprise_id")
        batch_op.drop_column("enterprise_id")

    table_indexes = (
        (
            "enterprise_liquidity_events",
            ("household_id", "enterprise_id", "event_type", "expected_date", "status"),
        ),
        ("enterprise_guarantees", ("household_id", "enterprise_id", "member_id")),
        ("enterprise_cashflows", ("household_id", "enterprise_id", "member_id")),
        ("enterprise_valuations", ("household_id", "enterprise_id")),
        ("enterprise_ownerships", ("household_id", "enterprise_id", "owner_entity_id")),
        ("enterprise_profiles", ("household_id", "stage", "listed_status")),
    )
    for table, columns in table_indexes:
        for column in reversed((*columns, "is_deleted")):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
