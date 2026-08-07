"""Add reproducible wealth-twin simulation evidence and staged run state.

Revision ID: 0006_wealth_twin_simulation
Revises: 0005_portfolio_suitability
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_wealth_twin_simulation"
down_revision: str | None = "0005_portfolio_suitability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # scenario_definitions is the parent of simulation_runs.  Native ADD
    # COLUMN preserves the parent table and therefore works even when child
    # rows already exist in a persisted SQLite demo volume.
    op.add_column(
        "scenario_definitions",
        sa.Column(
            "scenario_version", sa.String(length=32), server_default="unknown", nullable=False
        ),
    )
    op.add_column(
        "scenario_definitions",
        sa.Column("is_composable", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "scenario_definitions",
        sa.Column(
            "source_type", sa.String(length=32), server_default="internal_demo", nullable=False
        ),
    )
    op.add_column(
        "scenario_definitions",
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    with op.batch_alter_table("simulation_runs") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=16), server_default="QUEUED", nullable=False)
        )
        batch_op.add_column(
            sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("scenario_codes", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("path_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("horizon_months", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("time_step_months", sa.Integer(), server_default="1", nullable=False)
        )
        for name in ("input_version", "formula_version", "result_version", "parameter_hash"):
            batch_op.add_column(
                sa.Column(name, sa.String(length=64), server_default="unknown", nullable=False)
            )
        batch_op.add_column(sa.Column("rule_version_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "calculation_source",
                sa.String(length=40),
                server_default="deterministic_simulation_engine",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("cancel_requested", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("error_code", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_simulation_runs_status", ["status"], unique=False)
        batch_op.create_foreign_key(
            "fk_simulation_runs_rule_version_id",
            "rule_versions",
            ["rule_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("simulation_runs") as batch_op:
        batch_op.drop_constraint("fk_simulation_runs_rule_version_id", type_="foreignkey")
        batch_op.drop_index("ix_simulation_runs_status")
        for name in (
            "error_code",
            "completed_at",
            "started_at",
            "cancel_requested",
            "calculation_source",
            "rule_version_id",
            "parameter_hash",
            "result_version",
            "formula_version",
            "input_version",
            "time_step_months",
            "horizon_months",
            "path_count",
            "scenario_codes",
            "progress_percent",
            "status",
        ):
            batch_op.drop_column(name)

    # Rebuilding this parent table in SQLite fails when populated
    # simulation_runs still reference it.  SQLite 3.35+ and PostgreSQL both
    # support DROP COLUMN directly, which preserves the existing parent table
    # and its inbound foreign-key references.
    for name in ("enabled", "source_type", "is_composable", "scenario_version"):
        op.drop_column("scenario_definitions", name)
