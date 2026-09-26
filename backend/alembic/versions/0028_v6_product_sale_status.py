"""Allow explicit channel-verification sale status on PostgreSQL.

Revision ID: 0028_v6_product_sale_status
Revises: 0027_v5_calibration_registry
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_v6_product_sale_status"
down_revision: str | None = "0027_v5_calibration_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.alter_column(
            "sale_status",
            existing_type=sa.String(24),
            type_=sa.String(40),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.alter_column(
            "sale_status",
            existing_type=sa.String(40),
            type_=sa.String(24),
            existing_nullable=False,
        )
