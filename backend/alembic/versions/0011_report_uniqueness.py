"""Enforce household-local report and action identities.

Revision ID: 0011_report_uniqueness
Revises: 0010_formal_reports
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_report_uniqueness"
down_revision: str | None = "0010_formal_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("plan_reports") as batch:
        batch.create_unique_constraint(
            "uq_plan_reports_household_sequence",
            ["household_id", "sequence"],
        )
    with op.batch_alter_table("action_items") as batch:
        batch.create_unique_constraint(
            "uq_action_items_household_action_code",
            ["household_id", "action_code"],
        )


def downgrade() -> None:
    with op.batch_alter_table("action_items") as batch:
        batch.drop_constraint("uq_action_items_household_action_code", type_="unique")
    with op.batch_alter_table("plan_reports") as batch:
        batch.drop_constraint("uq_plan_reports_household_sequence", type_="unique")
