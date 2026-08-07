"""Add complete-demo and experiment-suite ledgers.

Revision ID: 0013_demo_release
Revises: 0012_security_privacy_quality
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_demo_release"
down_revision: str | None = "0012_security_privacy_quality"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _record_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="CNY", nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("data_source", sa.String(length=64), server_default="system", nullable=False),
        sa.Column("is_user_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _record_indexes(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_is_deleted"), table, ["is_deleted"], unique=False)


def upgrade() -> None:
    op.create_table(
        "demo_runs",
        *_record_columns(),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("story_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stages", sa.JSON(), nullable=False),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("recovered_from_run_id", sa.String(length=36), nullable=True),
        sa.Column("offline_mode", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "external_network_required", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_demo_runs_progress_percent",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _record_indexes("demo_runs")
    op.create_index(op.f("ix_demo_runs_household_id"), "demo_runs", ["household_id"])
    op.create_index(op.f("ix_demo_runs_status"), "demo_runs", ["status"])

    op.create_table(
        "experiment_suite_runs",
        *_record_columns(),
        sa.Column("suite_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("passed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cases", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("main_demo_run_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["main_demo_run_id"], ["demo_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _record_indexes("experiment_suite_runs")
    op.create_index(
        op.f("ix_experiment_suite_runs_suite_version"),
        "experiment_suite_runs",
        ["suite_version"],
    )
    op.create_index(
        op.f("ix_experiment_suite_runs_status"), "experiment_suite_runs", ["status"]
    )
    op.create_index(
        op.f("ix_experiment_suite_runs_main_demo_run_id"),
        "experiment_suite_runs",
        ["main_demo_run_id"],
    )


def downgrade() -> None:
    op.drop_table("experiment_suite_runs")
    op.drop_table("demo_runs")
