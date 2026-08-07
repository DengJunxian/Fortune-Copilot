"""Add controlled knowledge, intake drafts and agent orchestration evidence.

Revision ID: 0008_trusted_ai
Revises: 0007_behavior_finance
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_trusted_ai"
down_revision: str | None = "0007_behavior_finance"
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
    op.add_column("policy_documents", sa.Column("code", sa.String(length=80), nullable=True))
    op.add_column(
        "policy_documents",
        sa.Column("category", sa.String(length=80), server_default="uncategorized", nullable=False),
    )
    op.add_column(
        "policy_documents",
        sa.Column(
            "document_version", sa.String(length=64), server_default="legacy", nullable=False
        ),
    )
    op.add_column(
        "policy_documents",
        sa.Column(
            "source_type", sa.String(length=40), server_default="controlled_local", nullable=False
        ),
    )
    op.add_column(
        "policy_documents",
        sa.Column(
            "applicable_audiences",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "policy_documents",
        sa.Column("applicable_regions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column(
        "policy_documents",
        sa.Column("content", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("policy_documents", sa.Column("last_verified_date", sa.Date(), nullable=True))
    op.add_column(
        "policy_documents",
        sa.Column("controlled_snapshot", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_policy_documents_code", "policy_documents", ["code"], unique=True)

    op.create_table(
        "knowledge_chunks",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("page_ref", sa.String(length=80), nullable=True),
        sa.Column("paragraph_ref", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("security_status", sa.String(length=24), nullable=False),
        sa.Column("security_evidence", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["document_id"], ["policy_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_code", "knowledge_chunks", ["code"], unique=True)
    op.create_index("ix_knowledge_chunks_security_status", "knowledge_chunks", ["security_status"])
    _record_indexes("knowledge_chunks")

    op.create_table(
        "intake_drafts",
        sa.Column("household_id", sa.String(length=36), nullable=True),
        sa.Column("source_text_hash", sa.String(length=64), nullable=False),
        sa.Column("redacted_preview", sa.String(length=240), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("confirmed_values", sa.JSON(), nullable=False),
        sa.Column("contains_untrusted_instruction", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intake_drafts_household_id", "intake_drafts", ["household_id"])
    op.create_index("ix_intake_drafts_status", "intake_drafts", ["status"])
    _record_indexes("intake_drafts")

    op.create_table(
        "agent_orchestration_runs",
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("request_kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_state", sa.String(length=64), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("redacted_input", sa.JSON(), nullable=False),
        sa.Column("structured_output", sa.JSON(), nullable=False),
        sa.Column("numeric_ledger", sa.JSON(), nullable=False),
        sa.Column("citation_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("blocked_issues", sa.JSON(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("degraded", sa.Boolean(), nullable=False),
        sa.Column("orchestrator_version", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_orchestration_runs_household_id",
        "agent_orchestration_runs",
        ["household_id"],
    )
    op.create_index("ix_agent_orchestration_runs_status", "agent_orchestration_runs", ["status"])
    _record_indexes("agent_orchestration_runs")

    op.create_table(
        "agent_step_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("household_id", sa.String(length=36), nullable=False),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_schema_name", sa.String(length=120), nullable=False),
        sa.Column("output_schema_name", sa.String(length=120), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("structured_output", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("prohibitions_checked", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("degraded", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_orchestration_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "agent_code", name="uq_agent_step_run_agent"),
    )
    op.create_index("ix_agent_step_runs_run_id", "agent_step_runs", ["run_id"])
    op.create_index("ix_agent_step_runs_household_id", "agent_step_runs", ["household_id"])
    op.create_index("ix_agent_step_runs_agent_code", "agent_step_runs", ["agent_code"])
    op.create_index("ix_agent_step_runs_status", "agent_step_runs", ["status"])
    _record_indexes("agent_step_runs")


def downgrade() -> None:
    op.drop_table("agent_step_runs")
    op.drop_table("agent_orchestration_runs")
    op.drop_table("intake_drafts")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_policy_documents_code", table_name="policy_documents")
    op.drop_column("policy_documents", "controlled_snapshot")
    op.drop_column("policy_documents", "last_verified_date")
    op.drop_column("policy_documents", "content")
    op.drop_column("policy_documents", "applicable_regions")
    op.drop_column("policy_documents", "applicable_audiences")
    op.drop_column("policy_documents", "source_type")
    op.drop_column("policy_documents", "document_version")
    op.drop_column("policy_documents", "category")
    op.drop_column("policy_documents", "code")
