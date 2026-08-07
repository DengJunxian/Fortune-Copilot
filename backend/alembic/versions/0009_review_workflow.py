"""Add immutable plan review workflow versions.

Revision ID: 0009_review_workflow
Revises: 0008_trusted_ai
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_review_workflow"
down_revision: str | None = "0008_trusted_ai"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_workflow_versions",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("prior_version_id", sa.String(length=36), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("selected_candidate", sa.String(length=32), nullable=True),
        sa.Column("recommendation_snapshot", sa.JSON(), nullable=False),
        sa.Column("suitability_snapshot", sa.JSON(), nullable=False),
        sa.Column("communication_draft", sa.Text(), nullable=False),
        sa.Column("advisor_decision", sa.String(length=40), nullable=True),
        sa.Column("compliance_decision", sa.String(length=40), nullable=True),
        sa.Column("customer_confirmation", sa.JSON(), nullable=False),
        sa.Column("submitted_for_compliance", sa.Boolean(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("input_version", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("knowledge_version", sa.String(length=64), nullable=False),
        sa.Column("product_catalog_version", sa.String(length=64), nullable=False),
        sa.Column("before_hash", sa.String(length=64), nullable=False),
        sa.Column("after_hash", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=False),
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
        sa.CheckConstraint(
            "state IN ('draft', 'calculated', 'suitability_checked', "
            "'advisor_reviewed', 'compliance_reviewed', 'customer_confirmed', "
            "'active', 'superseded')",
            name="ck_plan_workflow_state",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prior_version_id"],
            ["plan_workflow_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "sequence", name="uq_plan_workflow_sequence"),
    )
    op.create_index(
        "ix_plan_workflow_versions_household_id",
        "plan_workflow_versions",
        ["household_id"],
    )
    op.create_index(
        "ix_plan_workflow_versions_workflow_id",
        "plan_workflow_versions",
        ["workflow_id"],
    )
    op.create_index(
        "ix_plan_workflow_versions_state",
        "plan_workflow_versions",
        ["state"],
    )
    op.create_index(
        "ix_plan_workflow_versions_is_current",
        "plan_workflow_versions",
        ["is_current"],
    )
    op.create_index(
        "ix_plan_workflow_versions_request_id",
        "plan_workflow_versions",
        ["request_id"],
    )
    op.create_index(
        "ix_plan_workflow_versions_is_deleted",
        "plan_workflow_versions",
        ["is_deleted"],
    )
    op.create_index(
        "ix_plan_workflow_household_current",
        "plan_workflow_versions",
        ["household_id", "is_current"],
    )


def downgrade() -> None:
    op.drop_table("plan_workflow_versions")
