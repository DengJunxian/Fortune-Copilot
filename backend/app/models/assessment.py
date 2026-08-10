from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    AccountBucket,
    PortfolioCandidateType,
    RiskLevel,
    SuitabilityDecision,
    SuitabilityGateType,
    SuitabilityStatus,
)
from app.models.base import Base
from app.models.common import RecordMixin

RATIO = Numeric(9, 6)
METRIC = Numeric(24, 6)


class RiskAssessment(RecordMixin, Base):
    __tablename__ = "risk_assessments"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capacity_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    willingness_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    knowledge_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    behavior_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    final_risk_limit: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    explanation: Mapped[str] = mapped_column(String(800), nullable=False)


class BehaviorAssessment(RecordMixin, Base):
    __tablename__ = "behavior_assessments"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    questionnaire_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    experiment_score: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    final_behavior_limit: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    detected_biases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    experiment_answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(String(800), nullable=False)


class FinancialSnapshot(RecordMixin, Base):
    __tablename__ = "financial_snapshots"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )
    calculation_source: Mapped[str] = mapped_column(
        String(40), default="deterministic_tools", nullable=False
    )
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class FinancialMetric(RecordMixin, Base):
    __tablename__ = "financial_metrics"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("financial_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_code: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(METRIC, nullable=True)
    numerator: Mapped[Decimal | None] = mapped_column(METRIC, nullable=True)
    denominator: Mapped[Decimal | None] = mapped_column(METRIC, nullable=True)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AccountBucketPlan(RecordMixin, Base):
    __tablename__ = "account_bucket_plans"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bucket: Mapped[AccountBucket] = mapped_column(
        Enum(AccountBucket, native_enum=False, length=32), nullable=False
    )
    sequence: Mapped[int] = mapped_column(default=0, nullable=False)
    denominator_name: Mapped[str] = mapped_column(String(80), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    allocation_ratio: Mapped[Decimal] = mapped_column(RATIO, nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    gap_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    recommended_range_min: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=0, nullable=False
    )
    recommended_range_max: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=0, nullable=False
    )
    annual_cost_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    coverage_gap_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    total_asset_ratio: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    investable_asset_ratio: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    annual_surplus_ratio: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    residual_long_term_ratio: Mapped[Decimal | None] = mapped_column(RATIO, nullable=True)
    plan_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    calculation_source: Mapped[str] = mapped_column(
        String(40), default="deterministic_tools", nullable=False
    )
    constraint_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )


class PortfolioPlan(RecordMixin, Base):
    __tablename__ = "portfolio_plans"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    candidate_type: Mapped[PortfolioCandidateType] = mapped_column(
        Enum(PortfolioCandidateType, native_enum=False, length=32), nullable=False
    )
    denominator_name: Mapped[str] = mapped_column(String(80), nullable=False)
    allocations: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    tactical_allocations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    product_mappings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    rebalancing: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    suitability_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    investment_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    objective_score: Mapped[Decimal] = mapped_column(METRIC, default=0, nullable=False)
    goal_success_probability: Mapped[Decimal] = mapped_column(RATIO, default=0, nullable=False)
    simulated_range_low: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    simulated_range_high: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    extreme_loss_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    max_drawdown_ratio: Mapped[Decimal] = mapped_column(RATIO, default=0, nullable=False)
    annual_fee_estimate: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0, nullable=False)
    liquidity_score: Mapped[Decimal] = mapped_column(RATIO, default=0, nullable=False)
    suitability_decision: Mapped[SuitabilityDecision] = mapped_column(
        Enum(SuitabilityDecision, native_enum=False, length=24), nullable=False
    )
    solver_method: Mapped[str] = mapped_column(String(48), nullable=False)
    solver_status: Mapped[str] = mapped_column(String(32), nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    solver_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )
    calculation_source: Mapped[str] = mapped_column(
        String(40), default="deterministic_tools", nullable=False
    )
    optimizer_version: Mapped[str] = mapped_column(String(64), nullable=False)


class SuitabilityCheck(RecordMixin, Base):
    __tablename__ = "suitability_checks"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("portfolio_plans.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    gate: Mapped[SuitabilityGateType] = mapped_column(
        Enum(SuitabilityGateType, native_enum=False, length=24), nullable=False
    )
    status: Mapped[SuitabilityStatus] = mapped_column(
        Enum(SuitabilityStatus, native_enum=False, length=16), nullable=False
    )
    decision: Mapped[SuitabilityDecision] = mapped_column(
        Enum(SuitabilityDecision, native_enum=False, length=24), nullable=False
    )
    check_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )
