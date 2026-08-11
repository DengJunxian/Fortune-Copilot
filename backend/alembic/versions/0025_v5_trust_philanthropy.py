"""Add V5 trust, succession and philanthropy needs.

Revision ID: 0025_v5_trust_philanthropy
Revises: 0024_v5_retirement_cross_border
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    CFSTimeHorizon,
    ProfessionalReferralUrgency,
    SpecializedComplexity,
    TrustSuccessionNeedType,
)

revision: str = "0025_v5_trust_philanthropy"
down_revision: str | None = "0024_v5_retirement_cross_border"
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
        "trust_succession_needs",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column(
            "need_type",
            sa.Enum(TrustSuccessionNeedType, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("beneficiaries", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("assets_in_scope", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("enterprise_in_scope", sa.JSON(), server_default="[]", nullable=False),
        sa.Column(
            "urgency",
            sa.Enum(ProfessionalReferralUrgency, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "complexity",
            sa.Enum(SpecializedComplexity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "professional_review_required",
            sa.Boolean(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "need_type",
            name="uq_trust_succession_need_type",
        ),
    )
    _indexes("trust_succession_needs", "household_id", "need_type")

    op.create_table(
        "philanthropy_goals",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("annual_budget", sa.Numeric(20, 2), nullable=False),
        sa.Column("target_cause", sa.String(160), nullable=False),
        sa.Column("funding_asset", sa.String(160), nullable=True),
        sa.Column(
            "time_horizon",
            sa.Enum(CFSTimeHorizon, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("family_participation", sa.String(240), nullable=False),
        sa.Column("governance_preference", sa.String(240), nullable=False),
        sa.Column(
            "professional_review_required",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "target_cause",
            "time_horizon",
            name="uq_philanthropy_goal_cause_horizon",
        ),
    )
    _indexes("philanthropy_goals", "household_id")


def downgrade() -> None:
    for table, columns in (
        ("philanthropy_goals", ("household_id",)),
        ("trust_succession_needs", ("household_id", "need_type")),
    ):
        for column in reversed((*columns, "is_deleted")):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
