"""Add deterministic financial analysis fields.

Revision ID: 0003_financial_engine
Revises: 0002_domain_models
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_financial_engine"
down_revision: str | None = "0002_domain_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("income_sources") as batch_op:
        batch_op.add_column(
            sa.Column(
                "income_type",
                sa.String(length=32),
                server_default="other",
                nullable=False,
            )
        )

    with op.batch_alter_table("financial_snapshots") as batch_op:
        batch_op.add_column(sa.Column("rule_version_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "calculation_source",
                sa.String(length=40),
                server_default="deterministic_tools",
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            "fk_financial_snapshots_rule_version_id",
            "rule_versions",
            ["rule_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("financial_metrics") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Numeric(precision=24, scale=6),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("unit", sa.String(length=24), server_default="number", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=24),
                server_default="not_evaluated",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("is_applicable", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "threshold_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("financial_metrics") as batch_op:
        batch_op.drop_column("threshold_version")
        batch_op.drop_column("is_applicable")
        batch_op.drop_column("status")
        batch_op.drop_column("unit")
        batch_op.alter_column(
            "value",
            existing_type=sa.Numeric(precision=24, scale=6),
            nullable=False,
        )

    with op.batch_alter_table("financial_snapshots") as batch_op:
        batch_op.drop_constraint(
            "fk_financial_snapshots_rule_version_id",
            type_="foreignkey",
        )
        batch_op.drop_column("calculation_source")
        batch_op.drop_column("rule_version_id")

    with op.batch_alter_table("income_sources") as batch_op:
        batch_op.drop_column("income_type")
