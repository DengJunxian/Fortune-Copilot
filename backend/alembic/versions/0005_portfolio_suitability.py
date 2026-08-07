"""Add the Mock product catalog, portfolio evidence and suitability chain.

Revision ID: 0005_portfolio_suitability
Revises: 0004_dynamic_planning
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_portfolio_suitability"
down_revision: str | None = "0004_dynamic_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(
            sa.Column(
                "asset_class",
                sa.String(length=48),
                server_default="cash_equivalent",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("term_months", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("minimum_holding_months", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("redemption_rules", sa.String(length=800), server_default="", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "annual_fee_rate",
                sa.Numeric(precision=9, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "underlying_assets", sa.JSON(), server_default=sa.text("'[]'"), nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "historical_volatility_min",
                sa.Numeric(precision=9, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "historical_volatility_max",
                sa.Numeric(precision=9, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "suitable_accounts", sa.JSON(), server_default=sa.text("'[]'"), nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "guarantee_disclosure", sa.String(length=800), server_default="", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "non_guaranteed_disclosure",
                sa.String(length=800),
                server_default="",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "complexity_level", sa.String(length=24), server_default="basic", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "catalog_version", sa.String(length=32), server_default="unknown", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("professional_only", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("education_only", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False)
        )

    with op.batch_alter_table("portfolio_plans") as batch_op:
        batch_op.add_column(sa.Column("recommendation_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "tactical_allocations", sa.JSON(), server_default=sa.text("'{}'"), nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("product_mappings", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("rebalancing", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
        for name in (
            "investment_amount",
            "simulated_range_low",
            "simulated_range_high",
            "extreme_loss_amount",
            "annual_fee_estimate",
        ):
            batch_op.add_column(
                sa.Column(
                    name,
                    sa.Numeric(precision=20, scale=2),
                    server_default="0",
                    nullable=False,
                )
            )
        batch_op.add_column(
            sa.Column(
                "objective_score",
                sa.Numeric(precision=24, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        for name in ("goal_success_probability", "max_drawdown_ratio", "liquidity_score"):
            batch_op.add_column(
                sa.Column(
                    name,
                    sa.Numeric(precision=9, scale=6),
                    server_default="0",
                    nullable=False,
                )
            )
        batch_op.add_column(
            sa.Column(
                "suitability_decision",
                sa.String(length=24),
                server_default="education_only",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "solver_method", sa.String(length=48), server_default="unknown", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "solver_status", sa.String(length=32), server_default="unknown", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("random_seed", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "solver_parameters", sa.JSON(), server_default=sa.text("'{}'"), nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "input_version", sa.String(length=64), server_default="unknown", nullable=False
            )
        )
        batch_op.add_column(sa.Column("rule_version_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "calculation_source",
                sa.String(length=40),
                server_default="deterministic_tools",
                nullable=False,
            )
        )
        batch_op.create_index(
            "ix_portfolio_plans_recommendation_id", ["recommendation_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_portfolio_plans_recommendation_id",
            "recommendations",
            ["recommendation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_portfolio_plans_rule_version_id",
            "rule_versions",
            ["rule_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(
            sa.Column("evidence", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )

    op.create_table(
        "suitability_checks",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_plan_id", sa.String(length=36), nullable=True),
        sa.Column("recommendation_id", sa.String(length=36), nullable=True),
        sa.Column("gate", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("check_version", sa.String(length=64), nullable=False),
        sa.Column("input_version", sa.String(length=64), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("rule_version_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("data_source", sa.String(length=64), nullable=False),
        sa.Column("is_user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portfolio_plan_id"], ["portfolio_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_suitability_checks_household_id", "suitability_checks", ["household_id"], unique=False
    )
    op.create_index(
        "ix_suitability_checks_portfolio_plan_id",
        "suitability_checks",
        ["portfolio_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_suitability_checks_recommendation_id",
        "suitability_checks",
        ["recommendation_id"],
        unique=False,
    )
    op.create_index(
        "ix_suitability_checks_is_deleted", "suitability_checks", ["is_deleted"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_suitability_checks_is_deleted", table_name="suitability_checks")
    op.drop_index("ix_suitability_checks_recommendation_id", table_name="suitability_checks")
    op.drop_index("ix_suitability_checks_portfolio_plan_id", table_name="suitability_checks")
    op.drop_index("ix_suitability_checks_household_id", table_name="suitability_checks")
    op.drop_table("suitability_checks")

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_column("evidence")

    with op.batch_alter_table("portfolio_plans") as batch_op:
        batch_op.drop_constraint("fk_portfolio_plans_rule_version_id", type_="foreignkey")
        batch_op.drop_constraint("fk_portfolio_plans_recommendation_id", type_="foreignkey")
        batch_op.drop_index("ix_portfolio_plans_recommendation_id")
        for name in (
            "calculation_source",
            "rule_version_id",
            "input_version",
            "solver_parameters",
            "random_seed",
            "solver_status",
            "solver_method",
            "suitability_decision",
            "liquidity_score",
            "annual_fee_estimate",
            "max_drawdown_ratio",
            "extreme_loss_amount",
            "simulated_range_high",
            "simulated_range_low",
            "goal_success_probability",
            "objective_score",
            "investment_amount",
            "rebalancing",
            "product_mappings",
            "tactical_allocations",
            "recommendation_id",
        ):
            batch_op.drop_column(name)

    with op.batch_alter_table("products") as batch_op:
        for name in (
            "enabled",
            "education_only",
            "professional_only",
            "catalog_version",
            "complexity_level",
            "non_guaranteed_disclosure",
            "guarantee_disclosure",
            "suitable_accounts",
            "historical_volatility_max",
            "historical_volatility_min",
            "underlying_assets",
            "annual_fee_rate",
            "redemption_rules",
            "minimum_holding_months",
            "term_months",
            "asset_class",
        ):
            batch_op.drop_column(name)
