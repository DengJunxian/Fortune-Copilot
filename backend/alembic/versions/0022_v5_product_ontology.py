"""Add the V5 buy-side product ontology and evidence snapshots.

Revision ID: 0022_v5_product_ontology
Revises: 0021_v5_cfs_orchestration
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import ProductFamily, ProductRiskLevel

revision: str = "0022_v5_product_ontology"
down_revision: str | None = "0021_v5_cfs_orchestration"
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


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column("issuer", sa.String(160), server_default="unknown", nullable=False)
        )
        batch.add_column(
            sa.Column("jurisdiction", sa.String(64), server_default="CN", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "product_family",
                sa.Enum(ProductFamily, native_enum=False, length=40),
                server_default=ProductFamily.CASH_MANAGEMENT.name,
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("product_subtype", sa.String(80), server_default="unknown", nullable=False)
        )
        batch.add_column(sa.Column("all_in_cost", sa.Numeric(9, 6), nullable=True))
        batch.add_column(
            sa.Column(
                "distribution_incentive_disclosure",
                sa.String(800),
                server_default="未披露",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "conflict_of_interest_flag", sa.Boolean(), server_default="0", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "professional_review_required",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("client_role_in_cfs", sa.JSON(), server_default="[]", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "classification_version",
                sa.String(64),
                server_default="legacy-v1",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("evidence_json", sa.JSON(), server_default="{}", nullable=False)
        )

    op.create_table(
        "product_snapshots",
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("sale_status", sa.String(40), nullable=False),
        sa.Column(
            "risk_level",
            sa.Enum(ProductRiskLevel, native_enum=False, length=8),
            nullable=False,
        ),
        sa.Column("fee_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("liquidity_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("terms_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(1200), nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_version", sa.String(96), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "snapshot_hash",
            name="uq_product_snapshots_product_hash",
        ),
    )
    for column in (
        "product_id",
        "as_of_date",
        "sale_status",
        "channel",
        "snapshot_hash",
        "is_deleted",
    ):
        op.create_index(f"ix_product_snapshots_{column}", "product_snapshots", [column])


def downgrade() -> None:
    for column in reversed(
        ("product_id", "as_of_date", "sale_status", "channel", "snapshot_hash", "is_deleted")
    ):
        op.drop_index(f"ix_product_snapshots_{column}", table_name="product_snapshots")
    op.drop_table("product_snapshots")
    with op.batch_alter_table("products") as batch:
        for column in (
            "evidence_json",
            "classification_version",
            "client_role_in_cfs",
            "professional_review_required",
            "conflict_of_interest_flag",
            "distribution_incentive_disclosure",
            "all_in_cost",
            "product_subtype",
            "product_family",
            "jurisdiction",
            "issuer",
        ):
            batch.drop_column(column)
