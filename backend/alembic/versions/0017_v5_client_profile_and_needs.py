"""Add dynamic client wealth profiles, evidence tags and wealth needs.

Revision ID: 0017_v5_client_profile_and_needs
Revises: 0016_v5_financial_graph_core
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    ClientProfileStatus,
    ComplexityBand,
    GoalRigidity,
    LifecycleStage,
    PensionStage,
    ProfileTagSeverity,
    RiskLevel,
    ServiceComplexity,
    WealthNeedStatus,
    WealthNeedType,
    WealthTier,
)

revision: str = "0017_v5_client_profile_and_needs"
down_revision: str | None = "0016_v5_financial_graph_core"
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
        "client_wealth_profiles",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.String(80), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("formula_version", sa.String(64), nullable=False),
        sa.Column(
            "lifecycle_stage",
            sa.Enum(LifecycleStage, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column(
            "wealth_tier",
            sa.Enum(WealthTier, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "service_complexity",
            sa.Enum(ServiceComplexity, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column(
            "risk_capacity",
            sa.Enum(RiskLevel, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "risk_willingness",
            sa.Enum(RiskLevel, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "behavior_limit",
            sa.Enum(RiskLevel, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "enterprise_dependency_level",
            sa.Enum(ComplexityBand, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "cross_border_complexity",
            sa.Enum(ComplexityBand, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "succession_complexity",
            sa.Enum(ComplexityBand, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "pension_stage",
            sa.Enum(PensionStage, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("completeness_score", sa.Numeric(9, 6), nullable=False),
        sa.Column("data_gaps", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("profile_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(ClientProfileStatus, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("explanation", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "profile_version",
            name="uq_client_wealth_profiles_household_version",
        ),
    )
    op.create_index(
        "ix_client_wealth_profiles_household_id",
        "client_wealth_profiles",
        ["household_id"],
    )
    op.create_index(
        "ix_client_wealth_profiles_profile_hash",
        "client_wealth_profiles",
        ["profile_hash"],
    )
    op.create_index(
        "ix_client_wealth_profiles_status",
        "client_wealth_profiles",
        ["status"],
    )
    op.create_index(
        "ix_client_wealth_profiles_is_deleted",
        "client_wealth_profiles",
        ["is_deleted"],
    )

    op.create_table(
        "client_profile_tags",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("tag_code", sa.String(80), nullable=False),
        sa.Column("tag_category", sa.String(48), nullable=False),
        sa.Column("value", sa.String(240), nullable=False),
        sa.Column("confidence", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(ProfileTagSeverity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("source_record_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["client_wealth_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "tag_code",
            name="uq_client_profile_tags_profile_code",
        ),
    )
    op.create_index("ix_client_profile_tags_household_id", "client_profile_tags", ["household_id"])
    op.create_index("ix_client_profile_tags_profile_id", "client_profile_tags", ["profile_id"])
    op.create_index("ix_client_profile_tags_tag_code", "client_profile_tags", ["tag_code"])
    op.create_index("ix_client_profile_tags_is_deleted", "client_profile_tags", ["is_deleted"])

    op.create_table(
        "wealth_needs",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column(
            "need_type",
            sa.Enum(WealthNeedType, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("beneficiary_entity_id", sa.String(36), nullable=True),
        sa.Column("target_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "rigidity",
            sa.Enum(GoalRigidity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(WealthNeedStatus, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "professional_review_required",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(48), nullable=False),
        sa.Column("source_record_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["client_wealth_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["beneficiary_entity_id"], ["financial_entities.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wealth_needs_household_id", "wealth_needs", ["household_id"])
    op.create_index("ix_wealth_needs_profile_id", "wealth_needs", ["profile_id"])
    op.create_index("ix_wealth_needs_need_type", "wealth_needs", ["need_type"])
    op.create_index(
        "ix_wealth_needs_beneficiary_entity_id",
        "wealth_needs",
        ["beneficiary_entity_id"],
    )
    op.create_index("ix_wealth_needs_status", "wealth_needs", ["status"])
    op.create_index("ix_wealth_needs_is_deleted", "wealth_needs", ["is_deleted"])

    op.create_table(
        "wealth_need_priorities",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("wealth_need_id", sa.String(36), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("hard_constraint", sa.Boolean(), nullable=False),
        sa.Column("priority_score", sa.Numeric(9, 6), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wealth_need_id"], ["wealth_needs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wealth_need_id", name="uq_wealth_need_priorities_need"),
    )
    op.create_index(
        "ix_wealth_need_priorities_household_id",
        "wealth_need_priorities",
        ["household_id"],
    )
    op.create_index(
        "ix_wealth_need_priorities_wealth_need_id",
        "wealth_need_priorities",
        ["wealth_need_id"],
    )
    op.create_index(
        "ix_wealth_need_priorities_is_deleted",
        "wealth_need_priorities",
        ["is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_wealth_need_priorities_is_deleted", table_name="wealth_need_priorities")
    op.drop_index(
        "ix_wealth_need_priorities_wealth_need_id",
        table_name="wealth_need_priorities",
    )
    op.drop_index(
        "ix_wealth_need_priorities_household_id",
        table_name="wealth_need_priorities",
    )
    op.drop_table("wealth_need_priorities")
    op.drop_index("ix_wealth_needs_is_deleted", table_name="wealth_needs")
    op.drop_index("ix_wealth_needs_status", table_name="wealth_needs")
    op.drop_index("ix_wealth_needs_beneficiary_entity_id", table_name="wealth_needs")
    op.drop_index("ix_wealth_needs_need_type", table_name="wealth_needs")
    op.drop_index("ix_wealth_needs_profile_id", table_name="wealth_needs")
    op.drop_index("ix_wealth_needs_household_id", table_name="wealth_needs")
    op.drop_table("wealth_needs")
    op.drop_index("ix_client_profile_tags_is_deleted", table_name="client_profile_tags")
    op.drop_index("ix_client_profile_tags_tag_code", table_name="client_profile_tags")
    op.drop_index("ix_client_profile_tags_profile_id", table_name="client_profile_tags")
    op.drop_index("ix_client_profile_tags_household_id", table_name="client_profile_tags")
    op.drop_table("client_profile_tags")
    op.drop_index("ix_client_wealth_profiles_is_deleted", table_name="client_wealth_profiles")
    op.drop_index("ix_client_wealth_profiles_status", table_name="client_wealth_profiles")
    op.drop_index("ix_client_wealth_profiles_profile_hash", table_name="client_wealth_profiles")
    op.drop_index("ix_client_wealth_profiles_household_id", table_name="client_wealth_profiles")
    op.drop_table("client_wealth_profiles")
