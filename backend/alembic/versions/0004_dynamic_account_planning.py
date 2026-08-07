"""Add auditable dynamic account planning fields.

Revision ID: 0004_dynamic_planning
Revises: 0003_financial_engine
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_dynamic_planning"
down_revision: str | None = "0003_financial_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("account_bucket_plans") as batch_op:
        batch_op.add_column(sa.Column("recommendation_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("sequence", sa.Integer(), server_default="0", nullable=False))
        for column_name in (
            "current_amount",
            "target_amount",
            "gap_amount",
            "recommended_range_min",
            "recommended_range_max",
            "annual_cost_amount",
            "coverage_gap_amount",
        ):
            batch_op.add_column(
                sa.Column(
                    column_name,
                    sa.Numeric(precision=20, scale=2),
                    server_default="0",
                    nullable=False,
                )
            )
        for column_name in (
            "total_asset_ratio",
            "investable_asset_ratio",
            "annual_surplus_ratio",
        ):
            batch_op.add_column(
                sa.Column(column_name, sa.Numeric(precision=9, scale=6), nullable=True)
            )
        batch_op.add_column(
            sa.Column(
                "plan_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "input_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "calculation_source",
                sa.String(length=40),
                server_default="deterministic_tools",
                nullable=False,
            )
        )
        batch_op.create_index(
            "ix_account_bucket_plans_recommendation_id",
            ["recommendation_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_account_bucket_plans_recommendation_id",
            "recommendations",
            ["recommendation_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("account_bucket_plans") as batch_op:
        batch_op.drop_constraint(
            "fk_account_bucket_plans_recommendation_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_account_bucket_plans_recommendation_id")
        for column_name in (
            "calculation_source",
            "input_version",
            "plan_version",
            "annual_surplus_ratio",
            "investable_asset_ratio",
            "total_asset_ratio",
            "coverage_gap_amount",
            "annual_cost_amount",
            "recommended_range_max",
            "recommended_range_min",
            "gap_amount",
            "target_amount",
            "current_amount",
            "sequence",
            "recommendation_id",
        ):
            batch_op.drop_column(column_name)
