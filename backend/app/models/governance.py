from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    AuditEventType,
    ComplexityLevel,
    LiquidityLevel,
    PlanWorkflowState,
    ProductFamily,
    ProductRiskLevel,
    RecommendationStatus,
    SimulationStatus,
)
from app.models.base import Base
from app.models.common import RecordMixin


class Product(RecordMixin, Base):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_type: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(48), default="cash_equivalent", nullable=False)
    risk_level: Mapped[ProductRiskLevel] = mapped_column(
        Enum(ProductRiskLevel, native_enum=False, length=8), nullable=False
    )
    liquidity_level: Mapped[LiquidityLevel] = mapped_column(
        Enum(LiquidityLevel, native_enum=False, length=24), nullable=False
    )
    minimum_investment: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_holding_months: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    redemption_rules: Mapped[str] = mapped_column(String(800), default="", nullable=False)
    annual_fee_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), default=0, nullable=False)
    underlying_assets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    historical_volatility_min: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), default=0, nullable=False
    )
    historical_volatility_max: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), default=0, nullable=False
    )
    suitable_accounts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    principal_guaranteed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guarantee_basis: Mapped[str | None] = mapped_column(String(300), nullable=True)
    guarantee_disclosure: Mapped[str] = mapped_column(String(800), default="", nullable=False)
    non_guaranteed_disclosure: Mapped[str] = mapped_column(String(800), default="", nullable=False)
    complexity_level: Mapped[ComplexityLevel] = mapped_column(
        Enum(ComplexityLevel, native_enum=False, length=24),
        default=ComplexityLevel.BASIC,
        nullable=False,
    )
    catalog_version: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    professional_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    education_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    terms: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    account_wrappers: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["ordinary"], nullable=False
    )
    principal_loss_possible: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    legally_principal_guaranteed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    liquidity_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lock_up: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    withdrawable_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    volatility: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), default=0, nullable=False
    )
    sale_status: Mapped[str] = mapped_column(
        String(40), default="available", nullable=False
    )
    channel: Mapped[str] = mapped_column(String(48), default="demo_catalog", nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    snapshot_version: Mapped[str] = mapped_column(
        String(64), default="unknown", nullable=False
    )
    issuer: Mapped[str] = mapped_column(String(160), default="unknown", nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(64), default="CN", nullable=False)
    product_family: Mapped[ProductFamily] = mapped_column(
        Enum(ProductFamily, native_enum=False, length=40),
        default=ProductFamily.CASH_MANAGEMENT,
        nullable=False,
    )
    product_subtype: Mapped[str] = mapped_column(String(80), default="unknown", nullable=False)
    all_in_cost: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    distribution_incentive_disclosure: Mapped[str] = mapped_column(
        String(800), default="未披露", nullable=False
    )
    conflict_of_interest_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    professional_review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    client_role_in_cfs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    classification_version: Mapped[str] = mapped_column(
        String(64), default="legacy-v1", nullable=False
    )
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ProductSnapshot(RecordMixin, Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "snapshot_hash",
            name="uq_product_snapshots_product_hash",
        ),
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sale_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_level: Mapped[ProductRiskLevel] = mapped_column(
        Enum(ProductRiskLevel, native_enum=False, length=8), nullable=False
    )
    fee_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    liquidity_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    terms_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(1200), nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_version: Mapped[str] = mapped_column(String(96), nullable=False)


class PolicyDocument(RecordMixin, Base):
    __tablename__ = "policy_documents"

    code: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="uncategorized", nullable=False)
    document_version: Mapped[str] = mapped_column(String(64), default="legacy", nullable=False)
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="controlled_local", nullable=False)
    applicable_audiences: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    applicable_regions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    last_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    controlled_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ScenarioDefinition(RecordMixin, Base):
    __tablename__ = "scenario_definitions"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(String(800), nullable=False)
    scenario_version: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    is_composable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="internal_demo", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SimulationRun(RecordMixin, Base):
    __tablename__ = "simulation_runs"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("scenario_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    household_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, native_enum=False, length=16),
        default=SimulationStatus.QUEUED,
        nullable=False,
        index=True,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scenario_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    path_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    horizon_months: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_step_months: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    result_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    parameter_hash: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )
    calculation_source: Mapped[str] = mapped_column(
        String(40), default="deterministic_simulation_engine", nullable=False
    )
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Recommendation(RecordMixin, Base):
    __tablename__ = "recommendations"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, native_enum=False, length=24), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    structured_advice: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    suitability_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rule_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="SET NULL"), nullable=True
    )
    methodology_version: Mapped[str] = mapped_column(
        String(64), default="unknown", nullable=False
    )
    decision_evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    decision_hash: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    client_profile_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    wealth_need_set_hash: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    liability_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    twin_snapshot_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    enterprise_snapshot_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    cfs_solution_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    calibration_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    monitoring_trigger_id: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )


class ActionItem(RecordMixin, Base):
    __tablename__ = "action_items"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "action_code",
            name="uq_action_items_household_action_code",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    advisor_trigger_id: Mapped[str | None] = mapped_column(
        ForeignKey("advisor_triggers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_code: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    action_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    do_not_sell_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_specialist: Mapped[str | None] = mapped_column(String(40), nullable=True)
    group_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deferred_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PlanReport(RecordMixin, Base):
    __tablename__ = "plan_reports"
    __table_args__ = (
        CheckConstraint(
            "chapter_count = 8",
            name="ck_plan_reports_chapter_count_eight",
        ),
        UniqueConstraint(
            "household_id",
            "sequence",
            name="uq_plan_reports_household_sequence",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    parent_report_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_reports.id", ondelete="SET NULL"), nullable=True
    )
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    workflow_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_workflow_versions.id", ondelete="SET NULL"), nullable=True
    )
    report_version: Mapped[str] = mapped_column(String(64), nullable=False)
    chapter_count: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    structured_report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consistency_status: Mapped[str] = mapped_column(String(32), nullable=False)
    generation_trigger: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    generation_reason: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    input_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    planning_rule_version: Mapped[str] = mapped_column(
        String(64), default="unknown", nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(
        String(64), default="unknown", nullable=False
    )
    decision_hash: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    decision_evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    client_profile_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    wealth_need_set_hash: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    liability_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    twin_snapshot_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    enterprise_snapshot_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    cfs_solution_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    calibration_version: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    monitoring_trigger_id: Mapped[str | None] = mapped_column(
        String(96), nullable=True, index=True
    )
    portfolio_rule_version: Mapped[str] = mapped_column(
        String(64), default="unknown", nullable=False
    )
    twin_result_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), default="mock", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    knowledge_version: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    product_catalog_version: Mapped[str] = mapped_column(
        String(64), default="unknown", nullable=False
    )
    publication_status: Mapped[str] = mapped_column(
        String(32), default="draft", nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_gate_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    watermark: Mapped[str] = mapped_column(
        String(120), default="客户财务规划草稿／待客户经理复核", nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class AdvisorReview(RecordMixin, Base):
    __tablename__ = "advisor_reviews"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_reports.id", ondelete="SET NULL"), nullable=True
    )
    advisor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    comments: Mapped[str] = mapped_column(String(1000), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CustomerConfirmation(RecordMixin, Base):
    __tablename__ = "customer_confirmations"

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_reports.id", ondelete="SET NULL"), nullable=True
    )
    member_id: Mapped[str | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL"), nullable=True
    )
    confirmation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PlanWorkflowVersion(RecordMixin, Base):
    """Immutable plan snapshot used by the advisor/compliance/client workflow."""

    __tablename__ = "plan_workflow_versions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'calculated', 'suitability_checked', "
            "'advisor_reviewed', 'compliance_reviewed', 'customer_confirmed', "
            "'active', 'superseded')",
            name="ck_plan_workflow_state",
        ),
        UniqueConstraint("workflow_id", "sequence", name="uq_plan_workflow_sequence"),
        Index(
            "ix_plan_workflow_household_current",
            "household_id",
            "is_current",
        ),
    )

    household_id: Mapped[str] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prior_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("plan_workflow_versions.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[PlanWorkflowState] = mapped_column(
        Enum(
            PlanWorkflowState,
            values_callable=lambda enum_type: [member.value for member in enum_type],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_candidate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recommendation_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    suitability_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    communication_draft: Mapped[str] = mapped_column(Text, default="", nullable=False)
    advisor_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    compliance_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    customer_confirmation: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    submitted_for_compliance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    input_version: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    model_version: Mapped[str] = mapped_column(
        String(64), default="mock-template-v1", nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(
        String(64), default="advisor-draft-v1", nullable=False
    )
    knowledge_version: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    product_catalog_version: Mapped[str] = mapped_column(
        String(64), default="pending", nullable=False
    )
    before_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    after_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)


class AuditEvent(RecordMixin, Base):
    __tablename__ = "audit_events"

    household_id: Mapped[str | None] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, native_enum=False, length=40), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelRun(RecordMixin, Base):
    __tablename__ = "model_runs"

    household_id: Mapped[str | None] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    task: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    redacted_input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RuleVersion(RecordMixin, Base):
    __tablename__ = "rule_versions"

    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    semantic_version: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_summary: Mapped[str] = mapped_column(String(800), nullable=False)
