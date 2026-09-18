"""Add V5 China calibration dataset and parameter registries.

Revision ID: 0027_v5_calibration_registry
Revises: 0026_v5_monitoring_and_triggers
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import CalibrationMode

revision: str = "0027_v5_calibration_registry"
down_revision: str | None = "0026_v5_monitoring_and_triggers"
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
        "calibration_datasets",
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column(
            "mode",
            sa.Enum(CalibrationMode, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("source", sa.String(240), nullable=False),
        sa.Column("source_reference", sa.String(600), nullable=False),
        sa.Column("population", sa.String(240), nullable=False),
        sa.Column("sample_period", sa.String(160), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source_version", sa.String(120), nullable=False),
        sa.Column("license_or_access_note", sa.Text(), nullable=False),
        sa.Column("limitations", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("data_quality", sa.String(100), nullable=False),
        *_record_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "source_version", name="uq_calibration_dataset_code_version"),
    )
    _indexes("calibration_datasets", "code", "mode", "effective_date", "source_version")

    op.create_table(
        "calibration_parameters",
        sa.Column("dataset_id", sa.String(36), nullable=False),
        sa.Column("parameter_code", sa.String(160), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=False),
        sa.Column("lower_bound", sa.Numeric(20, 8), nullable=True),
        sa.Column("upper_bound", sa.Numeric(20, 8), nullable=True),
        sa.Column("estimation_method", sa.String(240), nullable=False),
        sa.Column("segment", sa.String(100), nullable=False),
        sa.Column("region", sa.String(40), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("parameter_version", sa.String(120), nullable=False),
        sa.Column("confidence", sa.Numeric(9, 6), nullable=False),
        sa.Column("limitations", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("metadata_snapshot", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["dataset_id"], ["calibration_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_id",
            "parameter_code",
            "segment",
            "region",
            "effective_from",
            "parameter_version",
            name="uq_calibration_parameter_scope_version",
        ),
    )
    _indexes(
        "calibration_parameters",
        "dataset_id",
        "parameter_code",
        "segment",
        "region",
        "effective_from",
    )


def downgrade() -> None:
    for table, columns in (
        (
            "calibration_parameters",
            ("dataset_id", "parameter_code", "segment", "region", "effective_from"),
        ),
        (
            "calibration_datasets",
            ("code", "mode", "effective_date", "source_version"),
        ),
    ):
        for column in (*columns, "is_deleted"):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
