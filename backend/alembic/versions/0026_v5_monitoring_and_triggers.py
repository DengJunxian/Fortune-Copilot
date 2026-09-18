"""Add V5 monitoring, behavior observations and advisor triggers.

Revision ID: 0026_v5_monitoring_and_triggers
Revises: 0025_v5_trust_philanthropy
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.domain.enums import (
    AdvisorTriggerStatus,
    BehaviorObservationType,
    MonitoringAlertStatus,
    MonitoringCadence,
    MonitoringComparator,
    MonitoringPolicyType,
    MonitoringSeverity,
    RiskLimitEffect,
)

revision: str = "0026_v5_monitoring_and_triggers"
down_revision: str | None = "0025_v5_trust_philanthropy"
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
        "monitoring_policies",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column(
            "policy_type",
            sa.Enum(MonitoringPolicyType, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("metric", sa.String(80), nullable=False),
        sa.Column(
            "comparator",
            sa.Enum(MonitoringComparator, native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("threshold", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "cadence",
            sa.Enum(MonitoringCadence, native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(MonitoringSeverity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("rule_version", sa.String(64), nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "policy_type",
            "rule_version",
            name="uq_monitoring_policy_household_type_version",
        ),
    )
    _indexes("monitoring_policies", "household_id", "policy_type", "severity", "active")

    op.create_table(
        "monitoring_alerts",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("monitoring_policy_id", sa.String(36), nullable=False),
        sa.Column("financial_event_id", sa.String(36), nullable=True),
        sa.Column("trigger_reason", sa.String(800), nullable=False),
        sa.Column("client_impact", sa.String(800), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(MonitoringSeverity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("recommended_action", sa.String(1000), nullable=False),
        sa.Column("do_not_sell_flag", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("required_specialist", sa.String(40), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "status",
            sa.Enum(MonitoringAlertStatus, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["monitoring_policy_id"], ["monitoring_policies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["financial_event_id"], ["financial_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "monitoring_alerts",
        "household_id",
        "monitoring_policy_id",
        "financial_event_id",
        "severity",
        "status",
    )

    op.create_table(
        "advisor_triggers",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("monitoring_alert_id", sa.String(36), nullable=False),
        sa.Column("trigger_type", sa.String(64), nullable=False),
        sa.Column(
            "urgency",
            sa.Enum(MonitoringSeverity, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("reason", sa.String(800), nullable=False),
        sa.Column("required_role", sa.String(32), nullable=False),
        sa.Column("follow_up_due", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(AdvisorTriggerStatus, native_enum=False, length=16),
            nullable=False,
        ),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["monitoring_alert_id"], ["monitoring_alerts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "monitoring_alert_id",
            "trigger_type",
            name="uq_advisor_trigger_alert_type",
        ),
    )
    _indexes(
        "advisor_triggers",
        "household_id",
        "monitoring_alert_id",
        "trigger_type",
        "urgency",
        "required_role",
        "follow_up_due",
        "status",
    )

    op.create_table(
        "behavior_observations",
        sa.Column("household_id", sa.String(36), nullable=False),
        sa.Column("financial_event_id", sa.String(36), nullable=True),
        sa.Column(
            "observation_type",
            sa.Enum(BehaviorObservationType, native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_strength", sa.Numeric(9, 6), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "risk_limit_effect",
            sa.Enum(RiskLimitEffect, native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("hard_facts_changed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("source_reference", sa.String(160), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), server_default="{}", nullable=False),
        *_record_columns(),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["financial_event_id"], ["financial_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "observation_type",
            "observed_at",
            "source_reference",
            name="uq_behavior_observation_source",
        ),
    )
    _indexes(
        "behavior_observations",
        "household_id",
        "financial_event_id",
        "observation_type",
        "observed_at",
    )

    with op.batch_alter_table("action_items") as batch_op:
        batch_op.add_column(sa.Column("advisor_trigger_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("action_type", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("do_not_sell_flag", sa.Boolean(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("required_specialist", sa.String(40), nullable=True))
        batch_op.create_foreign_key(
            "fk_action_items_advisor_trigger_id",
            "advisor_triggers",
            ["advisor_trigger_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_action_items_advisor_trigger_id", ["advisor_trigger_id"])
        batch_op.create_index("ix_action_items_action_type", ["action_type"])


def downgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.drop_index("ix_action_items_action_type")
        batch_op.drop_index("ix_action_items_advisor_trigger_id")
        batch_op.drop_constraint("fk_action_items_advisor_trigger_id", type_="foreignkey")
        batch_op.drop_column("required_specialist")
        batch_op.drop_column("do_not_sell_flag")
        batch_op.drop_column("action_type")
        batch_op.drop_column("advisor_trigger_id")

    for table, columns in (
        (
            "behavior_observations",
            ("household_id", "financial_event_id", "observation_type", "observed_at"),
        ),
        (
            "advisor_triggers",
            (
                "household_id",
                "monitoring_alert_id",
                "trigger_type",
                "urgency",
                "required_role",
                "follow_up_due",
                "status",
            ),
        ),
        (
            "monitoring_alerts",
            (
                "household_id",
                "monitoring_policy_id",
                "financial_event_id",
                "severity",
                "status",
            ),
        ),
        ("monitoring_policies", ("household_id", "policy_type", "severity", "active")),
    ):
        for column in reversed((*columns, "is_deleted")):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
