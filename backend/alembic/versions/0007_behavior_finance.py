"""Add behavioral-finance experiment, bias, intervention and A/B evidence.

Revision ID: 0007_behavior_finance
Revises: 0006_wealth_twin_simulation
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_behavior_finance"
down_revision: str | None = "0006_wealth_twin_simulation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _record_columns() -> list[sa.Column[object]]:
    return [
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
    ]


def _record_indexes(table: str) -> None:
    op.create_index(f"ix_{table}_is_deleted", table, ["is_deleted"], unique=False)


def upgrade() -> None:
    op.create_table(
        "behavior_experiment_sessions",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("questionnaire", sa.JSON(), nullable=False),
        sa.Column("questionnaire_score", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("experiment_score", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("objective_capacity_limit", sa.String(length=16), nullable=False),
        sa.Column("questionnaire_claim_limit", sa.String(length=16), nullable=False),
        sa.Column("experiment_limit", sa.String(length=16), nullable=True),
        sa.Column("effective_risk_limit", sa.String(length=16), nullable=True),
        sa.Column("information_status", sa.String(length=24), nullable=False),
        sa.Column("assigned_variant", sa.String(length=64), nullable=False),
        sa.Column("experiment_key", sa.String(length=64), nullable=False),
        sa.Column("consent_basis", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("input_version", sa.String(length=64), nullable=False),
        sa.Column("formula_version", sa.String(length=64), nullable=False),
        sa.Column("experiment_version", sa.String(length=64), nullable=False),
        sa.Column("rule_version_id", sa.String(length=36), nullable=True),
        sa.Column("calculation_source", sa.String(length=48), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["behavior_assessments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_behavior_experiment_sessions_household_id",
        "behavior_experiment_sessions",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_experiment_sessions_assessment_id",
        "behavior_experiment_sessions",
        ["assessment_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_experiment_sessions_status",
        "behavior_experiment_sessions",
        ["status"],
        unique=False,
    )
    _record_indexes("behavior_experiment_sessions")

    op.create_table(
        "behavior_experiment_responses",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_code", sa.String(length=64), nullable=False),
        sa.Column("choice_code", sa.String(length=64), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=False),
        sa.Column("modification_count", sa.Integer(), nullable=False),
        sa.Column("consistency_score", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["behavior_experiment_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "experiment_code", name="uq_behavior_response_session_experiment"
        ),
    )
    op.create_index(
        "ix_behavior_experiment_responses_household_id",
        "behavior_experiment_responses",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_experiment_responses_session_id",
        "behavior_experiment_responses",
        ["session_id"],
        unique=False,
    )
    _record_indexes("behavior_experiment_responses")

    op.create_table(
        "behavior_bias_findings",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("bias_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("score", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("explanation", sa.String(length=800), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("source_experiment_codes", sa.JSON(), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["behavior_experiment_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "bias_code", name="uq_behavior_bias_session_code"),
    )
    op.create_index(
        "ix_behavior_bias_findings_household_id",
        "behavior_bias_findings",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_bias_findings_session_id",
        "behavior_bias_findings",
        ["session_id"],
        unique=False,
    )
    _record_indexes("behavior_bias_findings")

    op.create_table(
        "behavior_interventions",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("linked_goal_id", sa.String(length=36), nullable=True),
        sa.Column("intervention_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trigger_biases", sa.JSON(), nullable=False),
        sa.Column("scenario_code", sa.String(length=80), nullable=False),
        sa.Column("personalized_message", sa.String(length=1000), nullable=False),
        sa.Column("action_instruction", sa.String(length=800), nullable=False),
        sa.Column("cooling_period_hours", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_variant", sa.String(length=64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["behavior_experiment_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["linked_goal_id"], ["financial_goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "intervention_code", name="uq_behavior_intervention_session_code"
        ),
    )
    op.create_index(
        "ix_behavior_interventions_household_id",
        "behavior_interventions",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_interventions_session_id",
        "behavior_interventions",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_interventions_status",
        "behavior_interventions",
        ["status"],
        unique=False,
    )
    _record_indexes("behavior_interventions")

    op.create_table(
        "behavior_experiment_assignments",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_key", sa.String(length=64), nullable=False),
        sa.Column("framework_version", sa.String(length=64), nullable=False),
        sa.Column("variant_code", sa.String(length=64), nullable=False),
        sa.Column("assignment_method", sa.String(length=64), nullable=False),
        sa.Column("assignment_hash", sa.String(length=64), nullable=False),
        sa.Column("data_scope", sa.String(length=64), nullable=False),
        sa.Column("eligible_data", sa.Boolean(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["behavior_experiment_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_behavior_assignment_session"),
    )
    op.create_index(
        "ix_behavior_experiment_assignments_household_id",
        "behavior_experiment_assignments",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_experiment_assignments_session_id",
        "behavior_experiment_assignments",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_behavior_experiment_assignments_variant_code",
        "behavior_experiment_assignments",
        ["variant_code"],
        unique=False,
    )
    _record_indexes("behavior_experiment_assignments")


def downgrade() -> None:
    op.drop_table("behavior_experiment_assignments")
    op.drop_table("behavior_interventions")
    op.drop_table("behavior_bias_findings")
    op.drop_table("behavior_experiment_responses")
    op.drop_table("behavior_experiment_sessions")
