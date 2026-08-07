"""Persist client KYC and dynamic four-account preferences.

Revision ID: 0014_fortune_copilot_kyc
Revises: 0013_demo_release
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_fortune_copilot_kyc"
down_revision: str | None = "0013_demo_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("households") as batch:
        batch.add_column(
            sa.Column(
                "planning_preferences",
                sa.JSON(),
                server_default="{}",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("households") as batch:
        batch.drop_column("planning_preferences")
