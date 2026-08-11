"""Add the V5 persistent household financial twin.

Revision ID: 0019_v5_persistent_financial_twin
Revises: 0018_v5_liability_streams_eltc
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    FinancialEventDomain,
    FinancialEventStatus,
    HouseholdSnapshotStatus,
    LifeEventType,
)

revision: str = "0019_v5_persistent_financial_twin"
down_revision: str | None = "0018_v5_liability_streams_eltc"
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
    op.create_table(
        "household_snapshots",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("parent_snapshot_id", sa.String(36), nullable=True),
        sa.Column("source_financial_snapshot_id", sa.String(36), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("event_cursor", sa.Integer(), nullable=False),
        sa.Column("financial_graph_version", sa.String(64), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=True),
        sa.Column("need_version", sa.String(64), nullable=False),
        sa.Column("liability_version", sa.String(64), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(HouseholdSnapshotStatus, native_enum=False, length=16),
            nullable=False,
        ),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_snapshot_id"], ["household_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_financial_snapshot_id"],
            ["financial_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "event_cursor",
            name="uq_household_snapshots_event_cursor",
        ),
        sa.UniqueConstraint("snapshot_hash", name="uq_household_snapshots_snapshot_hash"),
    )
    for column in (
        "household_id",
        "parent_snapshot_id",
        "source_financial_snapshot_id",
        "snapshot_date",
        "input_hash",
        "snapshot_hash",
        "status",
        "is_deleted",
    ):
        op.create_index(f"ix_household_snapshots_{column}", "household_snapshots", [column])

    op.create_table(
        "financial_events",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column(
            "event_domain",
            sa.Enum(FinancialEventDomain, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("source_reference", sa.String(160), nullable=False),
        sa.Column(
            "confirmation_status",
            sa.Enum(FinancialEventStatus, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("processed_snapshot_id", sa.String(36), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["processed_snapshot_id"], ["household_snapshots.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "event_hash",
            name="uq_financial_events_household_hash",
        ),
    )
    for column in (
        "household_id",
        "event_domain",
        "event_type",
        "confirmation_status",
        "event_hash",
        "processed_snapshot_id",
        "is_deleted",
    ):
        op.create_index(f"ix_financial_events_{column}", "financial_events", [column])

    op.create_table(
        "life_events",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("financial_event_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column(
            "life_event_type",
            sa.Enum(LifeEventType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("expected_financial_impact", sa.Numeric(20, 2), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["financial_event_id"], ["financial_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["household_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("financial_event_id", name="uq_life_events_financial_event"),
    )
    for column in (
        "household_id",
        "financial_event_id",
        "member_id",
        "life_event_type",
        "event_date",
        "is_deleted",
    ):
        op.create_index(f"ix_life_events_{column}", "life_events", [column])

    with op.batch_alter_table("simulation_runs") as batch_op:
        batch_op.add_column(sa.Column("household_snapshot_id", sa.String(36), nullable=True))
        batch_op.create_index(
            "ix_simulation_runs_household_snapshot_id",
            ["household_snapshot_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_simulation_runs_household_snapshot_id",
            "household_snapshots",
            ["household_snapshot_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("simulation_runs") as batch_op:
        batch_op.drop_constraint("fk_simulation_runs_household_snapshot_id", type_="foreignkey")
        batch_op.drop_index("ix_simulation_runs_household_snapshot_id")
        batch_op.drop_column("household_snapshot_id")

    for column in reversed(
        (
            "household_id",
            "financial_event_id",
            "member_id",
            "life_event_type",
            "event_date",
            "is_deleted",
        )
    ):
        op.drop_index(f"ix_life_events_{column}", table_name="life_events")
    op.drop_table("life_events")
    for column in reversed(
        (
            "household_id",
            "event_domain",
            "event_type",
            "confirmation_status",
            "event_hash",
            "processed_snapshot_id",
            "is_deleted",
        )
    ):
        op.drop_index(f"ix_financial_events_{column}", table_name="financial_events")
    op.drop_table("financial_events")
    for column in reversed(
        (
            "household_id",
            "parent_snapshot_id",
            "source_financial_snapshot_id",
            "snapshot_date",
            "input_hash",
            "snapshot_hash",
            "status",
            "is_deleted",
        )
    ):
        op.drop_index(f"ix_household_snapshots_{column}", table_name="household_snapshots")
    op.drop_table("household_snapshots")
