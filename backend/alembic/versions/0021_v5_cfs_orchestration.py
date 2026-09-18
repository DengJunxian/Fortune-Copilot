"""Add the V5 CFS composer and professional routing ledger.

Revision ID: 0021_v5_cfs_orchestration
Revises: 0020_v5_family_enterprise
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    CFSComponentStatus,
    CFSComponentType,
    CFSSolutionStatus,
    CFSTimeHorizon,
    ProfessionalReferralStatus,
    ProfessionalReferralUrgency,
    ProfessionalSpecialistType,
)

revision: str = "0021_v5_cfs_orchestration"
down_revision: str | None = "0020_v5_family_enterprise"
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


def _indexes(table: str, *columns: str) -> None:
    for column in (*columns, "is_deleted"):
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "cfs_solutions",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(36), nullable=False),
        sa.Column("solution_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(CFSSolutionStatus, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("need_set_hash", sa.String(64), nullable=False),
        sa.Column("risk_budget_version", sa.String(64), nullable=False),
        sa.Column("methodology_version", sa.String(64), nullable=False),
        sa.Column("summary", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("decision_hash", sa.String(64), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["client_wealth_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["household_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "solution_version",
            name="uq_cfs_solutions_household_version",
        ),
        sa.UniqueConstraint(
            "household_id",
            "decision_hash",
            name="uq_cfs_solutions_household_decision_hash",
        ),
    )
    _indexes(
        "cfs_solutions",
        "household_id",
        "profile_id",
        "source_snapshot_id",
        "status",
        "decision_hash",
    )

    op.create_table(
        "cfs_solution_components",
        sa.Column("solution_id", sa.String(36), nullable=False),
        sa.Column("wealth_need_id", sa.String(36), nullable=True),
        sa.Column(
            "component_type",
            sa.Enum(CFSComponentType, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("target_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("minimum_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "time_horizon",
            sa.Enum(CFSTimeHorizon, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("recommended_action", sa.String(800), nullable=False),
        sa.Column("product_mapping_allowed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "professional_review_required", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.Column(
            "required_specialist",
            sa.Enum(ProfessionalSpecialistType, native_enum=False, length=40),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(CFSComponentStatus, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("rationale", sa.String(1200), nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(
            ["solution_id"], ["cfs_solutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["wealth_need_id"], ["wealth_needs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "solution_id",
            "wealth_need_id",
            "component_type",
            name="uq_cfs_component_solution_need_type",
        ),
    )
    _indexes(
        "cfs_solution_components",
        "solution_id",
        "wealth_need_id",
        "component_type",
        "status",
    )

    op.create_table(
        "professional_service_referrals",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("solution_id", sa.String(36), nullable=False),
        sa.Column("component_id", sa.String(36), nullable=False),
        sa.Column(
            "specialist_type",
            sa.Enum(ProfessionalSpecialistType, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("trigger_reason", sa.String(800), nullable=False),
        sa.Column(
            "urgency",
            sa.Enum(ProfessionalReferralUrgency, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(ProfessionalReferralStatus, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["solution_id"], ["cfs_solutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["cfs_solution_components.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "solution_id",
            "component_id",
            "specialist_type",
            name="uq_professional_referral_component_specialist",
        ),
    )
    _indexes(
        "professional_service_referrals",
        "household_id",
        "solution_id",
        "component_id",
        "status",
    )


def downgrade() -> None:
    tables = (
        (
            "professional_service_referrals",
            ("household_id", "solution_id", "component_id", "status"),
        ),
        (
            "cfs_solution_components",
            ("solution_id", "wealth_need_id", "component_type", "status"),
        ),
        (
            "cfs_solutions",
            ("household_id", "profile_id", "source_snapshot_id", "status", "decision_hash"),
        ),
    )
    for table, columns in tables:
        for column in reversed((*columns, "is_deleted")):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
