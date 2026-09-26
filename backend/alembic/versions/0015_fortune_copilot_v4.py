"""Add Fortune Copilot V4 methodology, asset tags, responsibilities and evidence.

Revision ID: 0015_fortune_copilot_v4
Revises: 0014_fortune_copilot_kyc
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    AccountWrapper,
    AssetPurposeDimension,
    ComplexityLevel,
    GoalRigidity,
)

revision: str = "0015_fortune_copilot_v4"
down_revision: str | None = "0014_fortune_copilot_kyc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.add_column(
            sa.Column(
                "purpose_dimension",
                sa.Enum(AssetPurposeDimension, native_enum=False, length=16),
                server_default="STABLE",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "account_wrapper",
                sa.Enum(AccountWrapper, native_enum=False, length=32),
                server_default="ORDINARY",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("principal_loss_possible", sa.Boolean(), server_default="1", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "legally_principal_guaranteed",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("lock_up", sa.Boolean(), server_default="0", nullable=False))
        batch.add_column(sa.Column("withdrawable_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("volatility", sa.Numeric(9, 6), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "product_complexity",
                sa.Enum(ComplexityLevel, native_enum=False, length=24),
                server_default="BASIC",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("institution_type", sa.String(48), server_default="ordinary", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "source_kind", sa.String(40), server_default="user_self_report", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "household_role", sa.String(40), server_default="household_shared", nullable=False
            )
        )
        batch.add_column(sa.Column("region_code", sa.String(24), nullable=True))

    op.execute(
        "UPDATE assets SET account_wrapper = 'PERSONAL_PENSION', lock_up = TRUE, "
        "institution_type = 'personal_pension', purpose_dimension = 'STABLE' "
        "WHERE category = 'PENSION_ACCOUNT'"
    )
    op.execute(
        "UPDATE assets SET purpose_dimension = 'DAILY' "
        "WHERE category IN ('CASH', 'DEMAND_DEPOSIT', 'MONEY_MARKET')"
    )
    op.execute(
        "UPDATE assets SET purpose_dimension = 'GROWTH' "
        "WHERE category IN ('PUBLIC_FUND', 'EQUITY_FUND', 'STOCK', 'TRUST', "
        "'INVESTMENT_PROPERTY')"
    )
    op.execute(
        "UPDATE assets SET purpose_dimension = 'PROTECTION', account_wrapper = 'INSURANCE' "
        "WHERE category = 'INSURANCE_CASH_VALUE'"
    )
    op.execute(
        "UPDATE assets SET legally_principal_guaranteed = TRUE, principal_loss_possible = FALSE "
        "WHERE category IN ('DEMAND_DEPOSIT', 'TIME_DEPOSIT')"
    )

    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column(
                "account_wrappers", sa.JSON(), server_default='["ordinary"]', nullable=False
            )
        )
        batch.add_column(
            sa.Column("principal_loss_possible", sa.Boolean(), server_default="1", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "legally_principal_guaranteed",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("liquidity_days", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("lock_up", sa.Boolean(), server_default="0", nullable=False))
        batch.add_column(sa.Column("withdrawable_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("volatility", sa.Numeric(9, 6), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("sale_status", sa.String(24), server_default="available", nullable=False)
        )
        batch.add_column(
            sa.Column("channel", sa.String(48), server_default="demo_catalog", nullable=False)
        )
        batch.add_column(
            sa.Column("source_reference", sa.String(500), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column("snapshot_version", sa.String(64), server_default="unknown", nullable=False)
        )
    op.execute(
        "UPDATE products SET legally_principal_guaranteed = principal_guaranteed, "
        "principal_loss_possible = CASE WHEN principal_guaranteed = TRUE THEN FALSE ELSE TRUE END, "
        "snapshot_version = catalog_version"
    )

    with op.batch_alter_table("recommendations") as batch:
        batch.add_column(
            sa.Column(
                "methodology_version", sa.String(64), server_default="unknown", nullable=False
            )
        )
        batch.add_column(
            sa.Column("decision_evidence", sa.JSON(), server_default="{}", nullable=False)
        )
        batch.add_column(
            sa.Column("decision_hash", sa.String(64), server_default="pending", nullable=False)
        )

    with op.batch_alter_table("account_bucket_plans") as batch:
        batch.add_column(
            sa.Column("residual_long_term_ratio", sa.Numeric(9, 6), nullable=True)
        )

    with op.batch_alter_table("plan_reports") as batch:
        batch.add_column(
            sa.Column(
                "methodology_version", sa.String(64), server_default="unknown", nullable=False
            )
        )
        batch.add_column(
            sa.Column("decision_hash", sa.String(64), server_default="pending", nullable=False)
        )

    op.create_table(
        "responsibilities",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("responsible_member_id", sa.String(36), nullable=True),
        sa.Column("beneficiary", sa.String(120), nullable=False),
        sa.Column("responsibility_type", sa.String(48), nullable=False),
        sa.Column("target_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("minimum_acceptable_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column(
            "rigidity",
            sa.Enum(GoalRigidity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("deferrable", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("annual_growth_assumption", sa.Numeric(9, 6), nullable=False),
        sa.Column("prepared_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("institutional_coverage", sa.Numeric(20, 2), nullable=False),
        sa.Column("funding_source", sa.String(120), nullable=False),
        sa.Column("source_goal_id", sa.String(36), nullable=True),
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
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["responsible_member_id"], ["household_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_goal_id"], ["financial_goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_responsibilities_household_id", "responsibilities", ["household_id"], unique=False
    )
    op.create_index(
        "ix_responsibilities_is_deleted", "responsibilities", ["is_deleted"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_responsibilities_is_deleted", table_name="responsibilities")
    op.drop_index("ix_responsibilities_household_id", table_name="responsibilities")
    op.drop_table("responsibilities")
    with op.batch_alter_table("plan_reports") as batch:
        batch.drop_column("decision_hash")
        batch.drop_column("methodology_version")
    with op.batch_alter_table("account_bucket_plans") as batch:
        batch.drop_column("residual_long_term_ratio")
    with op.batch_alter_table("recommendations") as batch:
        batch.drop_column("decision_hash")
        batch.drop_column("decision_evidence")
        batch.drop_column("methodology_version")
    with op.batch_alter_table("products") as batch:
        for column in (
            "snapshot_version",
            "source_reference",
            "channel",
            "sale_status",
            "volatility",
            "withdrawable_date",
            "lock_up",
            "liquidity_days",
            "legally_principal_guaranteed",
            "principal_loss_possible",
            "account_wrappers",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("assets") as batch:
        for column in (
            "region_code",
            "household_role",
            "source_kind",
            "institution_type",
            "product_complexity",
            "volatility",
            "withdrawable_date",
            "lock_up",
            "legally_principal_guaranteed",
            "principal_loss_possible",
            "account_wrapper",
            "purpose_dimension",
        ):
            batch.drop_column(column)
