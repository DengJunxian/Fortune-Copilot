"""Add V5 retirement entitlements and cross-border exposure buckets.

Revision ID: 0024_v5_retirement_cross_border
Revises: 0023_v5_decision_evidence_v2
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    CurrencyExposureDirection,
    CurrencyExposureHorizon,
    CurrencyExposureType,
    InstitutionalEntitlementType,
)

revision: str = "0024_v5_retirement_cross_border"
down_revision: str | None = "0023_v5_decision_evidence_v2"
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


def _indexes(table: str, *columns: str) -> None:
    for column in (*columns, "is_deleted"):
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "institutional_entitlements",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column(
            "entitlement_type",
            sa.Enum(InstitutionalEntitlementType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("balance", sa.Numeric(20, 2), nullable=False),
        sa.Column("expected_income", sa.Numeric(20, 2), nullable=False),
        sa.Column("start_age", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("guaranteed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("indexed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("lock_up", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("source_kind", sa.String(48), nullable=False),
        sa.Column("confidence", sa.Numeric(9, 6), nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["household_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "member_id",
            "entitlement_type",
            "source_kind",
            name="uq_institutional_entitlement_source",
        ),
    )
    _indexes(
        "institutional_entitlements",
        "household_id",
        "member_id",
        "entitlement_type",
    )

    op.create_table(
        "currency_exposures",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column(
            "exposure_type",
            sa.Enum(CurrencyExposureType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "direction",
            sa.Enum(CurrencyExposureDirection, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "horizon",
            sa.Enum(CurrencyExposureHorizon, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("source_record_ids", sa.JSON(), server_default="[]", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["financial_entities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "entity_id",
            "currency",
            "exposure_type",
            "direction",
            "horizon",
            name="uq_currency_exposure_bucket",
        ),
    )
    _indexes(
        "currency_exposures",
        "household_id",
        "entity_id",
        "exposure_type",
    )


def downgrade() -> None:
    for table, columns in (
        ("currency_exposures", ("household_id", "entity_id", "exposure_type")),
        (
            "institutional_entitlements",
            ("household_id", "member_id", "entitlement_type"),
        ),
    ):
        for column in reversed((*columns, "is_deleted")):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
