"""Add security, privacy, evaluation and release-gate records.

Revision ID: 0012_security_privacy_quality
Revises: 0011_report_uniqueness
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_security_privacy_quality"
down_revision: str | None = "0011_report_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _record_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="CNY", nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("data_source", sa.String(length=64), server_default="system", nullable=False),
        sa.Column("is_user_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _record_indexes(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_is_deleted"), table, ["is_deleted"], unique=False)


def upgrade() -> None:
    with op.batch_alter_table("plan_reports") as batch:
        batch.add_column(
            sa.Column(
                "publication_status",
                sa.String(length=32),
                server_default="draft",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("quality_gate_run_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_plan_reports_publication_status", ["publication_status"])

    op.create_table(
        "identity_access_grants",
        *_record_columns(),
        sa.Column("actor_subject_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("allowed_actions", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(length=240), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_subject_hash",
            "household_id",
            "actor_role",
            name="uq_identity_access_actor_household_role",
        ),
    )
    _record_indexes("identity_access_grants")
    op.create_index(
        op.f("ix_identity_access_grants_actor_subject_hash"),
        "identity_access_grants",
        ["actor_subject_hash"],
    )
    op.create_index(
        op.f("ix_identity_access_grants_household_id"),
        "identity_access_grants",
        ["household_id"],
    )

    op.create_table(
        "privacy_requests",
        *_record_columns(),
        sa.Column("household_id", sa.String(length=36), nullable=True),
        sa.Column("household_ref_hash", sa.String(length=64), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("reason_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_by_hash", sa.String(length=64), nullable=False),
        sa.Column("confirmation_method", sa.String(length=64), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _record_indexes("privacy_requests")
    for column in ("household_id", "household_ref_hash", "request_type", "status"):
        op.create_index(op.f(f"ix_privacy_requests_{column}"), "privacy_requests", [column])

    op.create_table(
        "quality_gate_runs",
        *_record_columns(),
        sa.Column("household_id", sa.String(length=36), nullable=True),
        sa.Column("report_id", sa.String(length=36), nullable=True),
        sa.Column("gate_version", sa.String(length=64), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("gate_results", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("evaluated_by_hash", sa.String(length=64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["plan_reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _record_indexes("quality_gate_runs")
    op.create_index(
        op.f("ix_quality_gate_runs_household_id"),
        "quality_gate_runs",
        ["household_id"],
    )
    op.create_index(op.f("ix_quality_gate_runs_report_id"), "quality_gate_runs", ["report_id"])

    op.create_table(
        "evaluation_runs",
        *_record_columns(),
        sa.Column("suite_version", sa.String(length=64), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("cases", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _record_indexes("evaluation_runs")
    op.create_index(op.f("ix_evaluation_runs_environment"), "evaluation_runs", ["environment"])


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("quality_gate_runs")
    op.drop_table("privacy_requests")
    op.drop_table("identity_access_grants")
    with op.batch_alter_table("plan_reports") as batch:
        batch.drop_index("ix_plan_reports_publication_status")
        batch.drop_column("quality_gate_run_id")
        batch.drop_column("published_at")
        batch.drop_column("publication_status")
