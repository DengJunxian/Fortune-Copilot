"""Add searchable Decision Evidence V2 bindings.

Revision ID: 0023_v5_decision_evidence_v2
Revises: 0022_v5_product_ontology
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_v5_decision_evidence_v2"
down_revision: str | None = "0022_v5_product_ontology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCHABLE_COLUMNS = (
    "client_profile_version",
    "wealth_need_set_hash",
    "liability_version",
    "twin_snapshot_version",
    "enterprise_snapshot_version",
    "cfs_solution_id",
    "calibration_version",
    "monitoring_trigger_id",
)


def upgrade() -> None:
    for table_name in ("recommendations", "plan_reports"):
        with op.batch_alter_table(table_name) as batch:
            for column_name in SEARCHABLE_COLUMNS:
                length = 36 if column_name == "cfs_solution_id" else 96
                batch.add_column(sa.Column(column_name, sa.String(length), nullable=True))
        for column_name in SEARCHABLE_COLUMNS:
            op.create_index(
                f"ix_{table_name}_{column_name}",
                table_name,
                [column_name],
            )

    with op.batch_alter_table("plan_reports") as batch:
        batch.add_column(
            sa.Column(
                "decision_evidence",
                sa.JSON(),
                server_default="{}",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("plan_reports") as batch:
        batch.drop_column("decision_evidence")

    for table_name in ("plan_reports", "recommendations"):
        for column_name in reversed(SEARCHABLE_COLUMNS):
            op.drop_index(f"ix_{table_name}_{column_name}", table_name=table_name)
        with op.batch_alter_table(table_name) as batch:
            for column_name in reversed(SEARCHABLE_COLUMNS):
                batch.drop_column(column_name)
