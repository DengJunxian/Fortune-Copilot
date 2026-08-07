"""Add formal report snapshots and persistent action lifecycle.

Revision ID: 0010_formal_reports
Revises: 0009_review_workflow
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_formal_reports"
down_revision: str | None = "0009_review_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("plan_reports") as batch:
        batch.add_column(sa.Column("sequence", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("parent_report_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("workflow_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("workflow_version_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column(
                "generation_trigger", sa.String(length=32), server_default="manual", nullable=False
            )
        )
        batch.add_column(
            sa.Column("generation_reason", sa.String(length=500), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column("report_hash", sa.String(length=64), server_default="pending", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "input_version", sa.String(length=64), server_default="unknown", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "formula_version", sa.String(length=64), server_default="unknown", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "planning_rule_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "portfolio_rule_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "twin_result_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("model_version", sa.String(length=64), server_default="mock", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "prompt_version", sa.String(length=64), server_default="unknown", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "knowledge_version", sa.String(length=64), server_default="unknown", nullable=False
            )
        )
        batch.add_column(
            sa.Column(
                "product_catalog_version",
                sa.String(length=64),
                server_default="unknown",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "watermark",
                sa.String(length=120),
                server_default="竞赛原型／待人工复核",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.create_foreign_key(
            "fk_plan_reports_parent",
            "plan_reports",
            ["parent_report_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_plan_reports_workflow_version",
            "plan_workflow_versions",
            ["workflow_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_plan_reports_sequence", ["sequence"])
        batch.create_index("ix_plan_reports_workflow_id", ["workflow_id"])
        batch.create_index("ix_plan_reports_is_current", ["is_current"])

    with op.batch_alter_table("action_items") as batch:
        batch.add_column(sa.Column("report_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("action_code", sa.String(length=96), nullable=True))
        batch.add_column(sa.Column("group_code", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("deferred_until", sa.Date(), nullable=True))
        batch.add_column(sa.Column("status_reason", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_action_items_report", "plan_reports", ["report_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_action_items_report_id", ["report_id"])
        batch.create_index("ix_action_items_action_code", ["action_code"])


def downgrade() -> None:
    with op.batch_alter_table("action_items") as batch:
        batch.drop_index("ix_action_items_action_code")
        batch.drop_index("ix_action_items_report_id")
        batch.drop_constraint("fk_action_items_report", type_="foreignkey")
        for name in (
            "status_changed_at",
            "status_reason",
            "deferred_until",
            "completed_at",
            "group_code",
            "action_code",
            "report_id",
        ):
            batch.drop_column(name)

    with op.batch_alter_table("plan_reports") as batch:
        batch.drop_index("ix_plan_reports_is_current")
        batch.drop_index("ix_plan_reports_workflow_id")
        batch.drop_index("ix_plan_reports_sequence")
        batch.drop_constraint("fk_plan_reports_workflow_version", type_="foreignkey")
        batch.drop_constraint("fk_plan_reports_parent", type_="foreignkey")
        for name in (
            "is_current",
            "watermark",
            "product_catalog_version",
            "knowledge_version",
            "prompt_version",
            "model_version",
            "twin_result_version",
            "portfolio_rule_version",
            "planning_rule_version",
            "formula_version",
            "input_version",
            "report_hash",
            "generation_reason",
            "generation_trigger",
            "workflow_version_id",
            "workflow_id",
            "parent_report_id",
            "sequence",
        ):
            batch.drop_column(name)
