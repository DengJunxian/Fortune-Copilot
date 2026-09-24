"""Add V5 liability streams and dated cashflows.

Revision ID: 0018_v5_liability_streams_eltc
Revises: 0017_v5_client_profile_and_needs
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import CashFlowFrequency, GoalRigidity, LiabilityStreamType

revision: str = "0018_v5_liability_streams_eltc"
down_revision: str | None = "0017_v5_client_profile_and_needs"
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
    # Alembic's default version column is VARCHAR(32). Later descriptive
    # revision IDs exceed that limit; PostgreSQL enforces it, unlike SQLite.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
    op.create_table(
        "liability_streams",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("wealth_need_id", sa.String(36), nullable=True),
        sa.Column("source_goal_id", sa.String(36), nullable=True),
        sa.Column("source_responsibility_id", sa.String(36), nullable=True),
        sa.Column("beneficiary_entity_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column(
            "stream_type",
            sa.Enum(LiabilityStreamType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "frequency",
            sa.Enum(CashFlowFrequency, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("base_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("inflation_index_code", sa.String(40), nullable=False),
        sa.Column("annual_growth_assumption", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "rigidity",
            sa.Enum(GoalRigidity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("deferrable", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("funding_sources", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("fallback_action", sa.String(500), nullable=False),
        sa.Column("stream_version", sa.String(64), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wealth_need_id"], ["wealth_needs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_goal_id"], ["financial_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_responsibility_id"], ["responsibilities.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["beneficiary_entity_id"], ["financial_entities.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_goal_id", name="uq_liability_streams_source_goal"),
        sa.UniqueConstraint(
            "source_responsibility_id",
            name="uq_liability_streams_source_responsibility",
        ),
    )
    op.create_index("ix_liability_streams_household_id", "liability_streams", ["household_id"])
    op.create_index("ix_liability_streams_wealth_need_id", "liability_streams", ["wealth_need_id"])
    op.create_index("ix_liability_streams_source_goal_id", "liability_streams", ["source_goal_id"])
    op.create_index(
        "ix_liability_streams_source_responsibility_id",
        "liability_streams",
        ["source_responsibility_id"],
    )
    op.create_index(
        "ix_liability_streams_beneficiary_entity_id",
        "liability_streams",
        ["beneficiary_entity_id"],
    )
    op.create_index("ix_liability_streams_stream_type", "liability_streams", ["stream_type"])
    op.create_index("ix_liability_streams_is_deleted", "liability_streams", ["is_deleted"])

    op.create_table(
        "liability_stream_cashflows",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("liability_stream_id", sa.String(36), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("target_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["liability_stream_id"], ["liability_streams.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "liability_stream_id",
            "sequence",
            name="uq_liability_stream_cashflows_sequence",
        ),
    )
    op.create_index(
        "ix_liability_stream_cashflows_household_id",
        "liability_stream_cashflows",
        ["household_id"],
    )
    op.create_index(
        "ix_liability_stream_cashflows_liability_stream_id",
        "liability_stream_cashflows",
        ["liability_stream_id"],
    )
    op.create_index(
        "ix_liability_stream_cashflows_due_date",
        "liability_stream_cashflows",
        ["due_date"],
    )
    op.create_index(
        "ix_liability_stream_cashflows_is_deleted",
        "liability_stream_cashflows",
        ["is_deleted"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_liability_stream_cashflows_is_deleted",
        table_name="liability_stream_cashflows",
    )
    op.drop_index(
        "ix_liability_stream_cashflows_due_date",
        table_name="liability_stream_cashflows",
    )
    op.drop_index(
        "ix_liability_stream_cashflows_liability_stream_id",
        table_name="liability_stream_cashflows",
    )
    op.drop_index(
        "ix_liability_stream_cashflows_household_id",
        table_name="liability_stream_cashflows",
    )
    op.drop_table("liability_stream_cashflows")
    op.drop_index("ix_liability_streams_is_deleted", table_name="liability_streams")
    op.drop_index("ix_liability_streams_stream_type", table_name="liability_streams")
    op.drop_index("ix_liability_streams_beneficiary_entity_id", table_name="liability_streams")
    op.drop_index("ix_liability_streams_source_responsibility_id", table_name="liability_streams")
    op.drop_index("ix_liability_streams_source_goal_id", table_name="liability_streams")
    op.drop_index("ix_liability_streams_wealth_need_id", table_name="liability_streams")
    op.drop_index("ix_liability_streams_household_id", table_name="liability_streams")
    op.drop_table("liability_streams")
