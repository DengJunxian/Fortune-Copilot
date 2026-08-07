from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_household_access
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import AuditEventType, MarketScenario, PlanWorkflowState, SimulationStatus
from app.models.common import new_id, utc_now
from app.models.governance import (
    ActionItem,
    AdvisorReview,
    AuditEvent,
    CustomerConfirmation,
    PlanReport,
    PlanWorkflowVersion,
    SimulationRun,
)
from app.schemas.formal_report import (
    FormalReportDocument,
    FormalReportSummary,
    ReportActionList,
    ReportActionOut,
    ReportActionUpdateRequest,
    ReportActionUpdateResponse,
    ReportExecutionMetrics,
    ReportGenerationChain,
    ReportGenerationRequest,
    ReportRecalculationRequest,
    ReportSourceClaim,
    ReportStatus,
)
from app.schemas.trust import KnowledgeCitation, KnowledgeSearchRequest
from app.schemas.twin import TwinResult, TwinRunRequest
from app.services.behavior.engine import behavior_overview
from app.services.client_experience import build_action_calendar
from app.services.financial.engine import analyze_household
from app.services.financial.facts import load_household_facts
from app.services.fund_advisory.engine import advise_household
from app.services.planning.engine import plan_household
from app.services.portfolio.engine import portfolio_household
from app.services.reporting.composer import compose_formal_report
from app.services.security.model_risk import record_model_run
from app.services.trust.knowledge import load_knowledge_dataset, search_knowledge
from app.services.twin.engine import advance_twin_run, start_twin_run

REPORT_ENGINE_VERSION = "formal-report-service-v1.0.0"
ACTION_ENGINE_VERSION = "formal-report-action-calendar-v1.0.0"
MODEL_VERSION = "mock-template-no-numeric-authority-v1.0.0"
PROMPT_VERSION = "formal-eight-chapter-contract-v1.0.0"
GROUP_ORDER = {
    "immediate": 1,
    "three_months": 2,
    "one_year": 3,
    "long_term": 4,
    "next_12_months": 5,
}
CLIENT_READY_STATES = {
    PlanWorkflowState.COMPLIANCE_REVIEWED,
    PlanWorkflowState.CUSTOMER_CONFIRMED,
    PlanWorkflowState.ACTIVE,
    PlanWorkflowState.SUPERSEDED,
}


def _json_hash(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _report_hash(document: FormalReportDocument) -> str:
    payload = document.model_dump(mode="json")
    payload["report_hash"] = "pending"
    return _json_hash(payload)


def _latest_report(session: Session, household_id: str) -> PlanReport | None:
    return session.scalar(
        select(PlanReport)
        .where(
            PlanReport.household_id == household_id,
            PlanReport.is_deleted.is_(False),
        )
        .order_by(PlanReport.sequence.desc(), PlanReport.created_at.desc())
    )


def _current_workflow(session: Session, household_id: str) -> PlanWorkflowVersion | None:
    return session.scalar(
        select(PlanWorkflowVersion)
        .where(
            PlanWorkflowVersion.household_id == household_id,
            PlanWorkflowVersion.is_current.is_(True),
            PlanWorkflowVersion.is_deleted.is_(False),
        )
        .order_by(PlanWorkflowVersion.sequence.desc())
    )


def _document(record: PlanReport) -> FormalReportDocument:
    try:
        return FormalReportDocument.model_validate(record.structured_report)
    except ValueError as exc:
        raise AppError(
            "report_snapshot_invalid",
            "正式规划书快照未通过八章结构校验",
            status_code=500,
            details={"report_id": record.id},
        ) from exc


def report_summary(record: PlanReport) -> FormalReportSummary:
    document = _document(record)
    base = f"/api/v1/reports/{record.id}"
    return FormalReportSummary(
        report_id=record.id,
        household_id=record.household_id,
        sequence=record.sequence,
        report_version=record.report_version,
        parent_report_id=record.parent_report_id,
        workflow_id=record.workflow_id,
        workflow_version_id=record.workflow_version_id,
        status=document.status,
        consistency_status=document.consistency_status,
        generation_trigger=cast(Any, record.generation_trigger),
        generated_at=record.generated_at,
        data_as_of=document.data_as_of,
        report_hash=record.report_hash,
        watermark=record.watermark,
        html_url=f"{base}/html",
        pdf_url=f"{base}/pdf",
    )


def get_current_formal_report(
    session: Session,
    household_id: str,
) -> FormalReportDocument | None:
    load_household_facts(session, household_id)
    record = _latest_report(session, household_id)
    return _document(record) if record is not None else None


def get_formal_report(session: Session, report_id: str) -> FormalReportDocument:
    record = session.scalar(
        select(PlanReport).where(
            PlanReport.id == report_id,
            PlanReport.is_deleted.is_(False),
        )
    )
    if record is None:
        raise AppError("report_not_found", "找不到正式规划书", status_code=404)
    return _document(record)


def require_formal_report_visibility(
    document: FormalReportDocument,
    actor: ActorContext,
) -> FormalReportDocument:
    """Keep pre-compliance workflow snapshots out of the client surface."""

    require_household_access(actor, document.household_id)

    if actor.role == "client" and document.status == "workflow_linked":
        raise AppError(
            "report_not_ready_for_client",
            "正式规划书仍在顾问／合规内部审核，尚未向客户发布",
            status_code=403,
            details={"report_id": document.report_id, "status": document.status},
        )
    return document


def get_report_record(session: Session, report_id: str) -> PlanReport:
    record = session.scalar(
        select(PlanReport).where(
            PlanReport.id == report_id,
            PlanReport.is_deleted.is_(False),
        )
    )
    if record is None:
        raise AppError("report_not_found", "找不到正式规划书", status_code=404)
    return record


def _latest_compatible_twin(
    session: Session,
    household_id: str,
    analysis_date: date,
    planning_input_version: str,
) -> TwinResult | None:
    runs = session.scalars(
        select(SimulationRun)
        .where(
            SimulationRun.household_id == household_id,
            SimulationRun.status == SimulationStatus.COMPLETED,
            SimulationRun.is_deleted.is_(False),
        )
        .order_by(SimulationRun.completed_at.desc(), SimulationRun.created_at.desc())
    ).all()
    for run in runs:
        if run.valuation_date != analysis_date:
            continue
        if run.inputs.get("planning_input_version") != planning_input_version:
            continue
        result = run.outputs.get("result")
        if isinstance(result, dict):
            return TwinResult.model_validate(result)
    return None


def _ensure_twin(
    session: Session,
    household_id: str,
    analysis_date: date,
    planning_input_version: str,
    actor: ActorContext,
    settings: Settings,
) -> TwinResult:
    existing = _latest_compatible_twin(
        session,
        household_id,
        analysis_date,
        planning_input_version,
    )
    if existing is not None:
        return existing
    status = start_twin_run(
        session,
        household_id,
        TwinRunRequest(
            analysis_date=analysis_date,
            path_count=100,
            horizon_years=30,
            output_interval_months=12,
            scenario_codes=["unemployment_equity_down_30"],
        ),
        actor,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.twin_rules_path,
    )
    for _ in range(8):
        if status.status == SimulationStatus.COMPLETED and status.result is not None:
            return status.result
        status = advance_twin_run(
            session,
            household_id,
            status.run_id,
            actor,
            settings.twin_rules_path,
        )
    raise AppError(
        "report_twin_incomplete",
        "正式规划书所需的数字孪生未在限定步骤内完成",
        status_code=500,
        details={"run_id": status.run_id, "status": status.status.value},
    )


def _knowledge_bundle(
    session: Session,
    settings: Settings,
    as_of_date: date,
) -> tuple[list[KnowledgeCitation], list[ReportSourceClaim], str]:
    queries = (
        ("personal_pension", "个人养老金参加、产品目录、缴费税务与领取有哪些边界"),
        ("product_suitability", "银行理财风险揭示、投资者适当性与非保本边界"),
        ("insurance_disclosure", "人身保险保证利益、非保证利益、等待期与转保披露"),
        ("consumer_protection", "消费者权益、人工复核、投诉与高风险建议处理边界"),
    )
    citation_map: dict[str, KnowledgeCitation] = {}
    claims: list[ReportSourceClaim] = []
    seen_claims: set[tuple[str, tuple[str, ...]]] = set()
    retrieval_version = "unknown"
    for category, query in queries:
        result = search_knowledge(
            session,
            settings.knowledge_base_path,
            KnowledgeSearchRequest(
                query=query,
                as_of_date=as_of_date,
                categories=[category],
                limit=4,
            ),
        )
        retrieval_version = result.retrieval_version
        for citation in result.citations:
            citation_map[citation.citation_id] = citation
        for claim in result.claims:
            key = (claim.text, tuple(claim.citation_ids))
            if key in seen_claims:
                continue
            seen_claims.add(key)
            claims.append(ReportSourceClaim(text=claim.text, citation_ids=claim.citation_ids))
    dataset = load_knowledge_dataset(settings.knowledge_base_path)
    return (
        list(citation_map.values()),
        claims,
        f"{dataset.dataset_version}+{retrieval_version}",
    )


def _action_metrics(items: list[ActionItem]) -> ReportExecutionMetrics:
    counts = {status: 0 for status in ("open", "completed", "deferred", "not_applicable")}
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
    total = sum(counts.values())
    completion = Decimal(counts["completed"]) / Decimal(total) if total else Decimal("0")
    return ReportExecutionMetrics(
        total=total,
        open=counts["open"],
        completed=counts["completed"],
        deferred=counts["deferred"],
        not_applicable=counts["not_applicable"],
        completion_ratio=f"{completion * Decimal('100'):.2f}%",
    )


def _action_out(item: ActionItem) -> ReportActionOut:
    evidence = item.evidence
    action_code = item.action_code
    group_code = item.group_code
    if action_code is None or group_code is None:
        raise AppError(
            "report_action_invalid",
            "正式报告行动缺少稳定代码或时间分组",
            status_code=500,
            details={"action_id": item.id},
        )
    return ReportActionOut.model_validate(
        {
            "id": item.id,
            "action_code": action_code,
            "group_code": group_code,
            "title": item.title,
            "detail": str(evidence.get("detail", "请按家庭事实完成并留存核对记录。")),
            "why": str(evidence.get("why", "来自确定性规划与复盘规则。")),
            "completion_criteria": str(
                evidence.get("completion_criteria", "家庭确认完成并在下次复盘核对。")
            ),
            "review_cycle": str(evidence.get("review_cycle", "下次月度复盘")),
            "amount": str(evidence.get("amount", "0.00")),
            "due_date": item.due_date,
            "priority": int(evidence.get("priority", 1)),
            "status": item.status,
            "completed_at": item.completed_at,
            "deferred_until": item.deferred_until,
            "status_reason": item.status_reason,
            "record_version": item.version,
            "calculation_source": str(
                evidence.get("calculation_source", "deterministic_planning_rules")
            ),
        }
    )


def _current_action_items(session: Session, household_id: str) -> list[ActionItem]:
    items = list(
        session.scalars(
            select(ActionItem).where(
                ActionItem.household_id == household_id,
                ActionItem.data_source == ACTION_ENGINE_VERSION,
                ActionItem.is_deleted.is_(False),
            )
        ).all()
    )
    return sorted(
        items,
        key=lambda item: (
            GROUP_ORDER.get(item.group_code or "", 99),
            int(item.evidence.get("priority", 999)),
            item.due_date or date.max,
            item.id,
        ),
    )


def _sync_actions(
    session: Session,
    household_id: str,
    report_id: str,
    currency: str,
    valuation_date: date,
    calendar: list[Any],
) -> list[ActionItem]:
    existing = {
        item.action_code: item
        for item in _current_action_items(session, household_id)
        if item.action_code is not None
    }
    for group in calendar:
        for draft in group.items:
            completion = (
                "记录本月家庭事实核对结果；如有变化，创建新快照并完成重算。"
                if group.code == "next_12_months"
                else "家庭确认动作已完成并留存凭证；下次复盘核对对应事实或余额。"
            )
            review_cycle = (
                "按到期月复盘"
                if group.code == "next_12_months"
                else "完成后复核，并在下一次月度复盘再次确认"
            )
            evidence = {
                **draft.model_dump(mode="json"),
                "group_label": group.label,
                "group_description": group.description,
                "completion_criteria": completion,
                "review_cycle": review_cycle,
            }
            record = existing.get(draft.code)
            if record is None:
                record = ActionItem(
                    household_id=household_id,
                    recommendation_id=None,
                    report_id=report_id,
                    action_code=draft.code,
                    group_code=group.code,
                    title=draft.title,
                    due_date=draft.due_date,
                    status="open",
                    owner_role="client",
                    evidence=evidence,
                    currency=currency,
                    valuation_date=valuation_date,
                    data_source=ACTION_ENGINE_VERSION,
                    is_user_confirmed=False,
                )
                session.add(record)
                existing[draft.code] = record
            else:
                changed = (
                    record.title != draft.title
                    or record.due_date != draft.due_date
                    or record.group_code != group.code
                    or record.evidence != evidence
                )
                if changed:
                    record.title = draft.title
                    record.due_date = draft.due_date
                    record.group_code = group.code
                    record.evidence = evidence
                    record.version += 1
    session.flush()
    return _current_action_items(session, household_id)


def _status_for_workflow(
    workflow: PlanWorkflowVersion | None,
) -> tuple[ReportStatus, str, str | None]:
    if workflow is None:
        return "draft_requires_human_review", "客户财务规划草稿／待客户经理复核", None
    label = f"{workflow.workflow_id[:8]}·V{workflow.sequence}·{workflow.state.value}"
    if workflow.state in CLIENT_READY_STATES:
        return "client_ready", "已完成内部复核／可向客户提供", label
    return "workflow_linked", "客户财务规划／内部复核中", label


def _attach_review_records(
    session: Session,
    workflow: PlanWorkflowVersion | None,
    report: PlanReport,
) -> None:
    if workflow is None:
        return
    if workflow.state in {
        PlanWorkflowState.ADVISOR_REVIEWED,
        *CLIENT_READY_STATES,
    }:
        review = session.scalar(
            select(AdvisorReview)
            .where(
                AdvisorReview.household_id == report.household_id,
                AdvisorReview.report_id.is_(None),
                AdvisorReview.is_deleted.is_(False),
            )
            .order_by(AdvisorReview.reviewed_at.desc())
        )
        if review is not None:
            review.report_id = report.id
            review.version += 1
    confirmation = session.scalar(
        select(CustomerConfirmation)
        .where(
            CustomerConfirmation.household_id == report.household_id,
            CustomerConfirmation.report_id.is_(None),
            CustomerConfirmation.is_deleted.is_(False),
        )
        .order_by(CustomerConfirmation.confirmed_at.desc())
    )
    if (
        confirmation is not None
        and confirmation.evidence.get("workflow_id") == workflow.workflow_id
    ):
        confirmation.report_id = report.id
        confirmation.version += 1


def _compose_and_stage_report(
    session: Session,
    household_id: str,
    request: ReportGenerationRequest,
    actor: ActorContext,
    settings: Settings,
) -> PlanReport:
    facts = load_household_facts(session, household_id)
    workflow = _current_workflow(session, household_id)
    if (
        actor.role == "client"
        and workflow is not None
        and workflow.state not in CLIENT_READY_STATES
    ):
        raise AppError(
            "report_not_ready_for_client",
            "当前方案仍在顾问／合规内部审核，客户暂不能生成关联正式规划书",
            status_code=403,
            details={"workflow_id": workflow.workflow_id, "state": workflow.state.value},
        )
    analysis_date = request.analysis_date or date.today()
    analysis = analyze_household(
        session,
        household_id,
        settings.financial_rules_path,
        analysis_date,
    )
    plan = plan_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        analysis_date,
    )
    portfolio = portfolio_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        analysis_date,
        MarketScenario.NEUTRAL,
    )
    fund_advisory = advise_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        settings.fund_advisory_catalog_path,
        analysis_date,
        icbc_only=True,
    )
    twin = _ensure_twin(
        session,
        household_id,
        analysis_date,
        plan.meta.input_version,
        actor,
        settings,
    )
    behavior = behavior_overview(session, household_id, settings.behavior_rules_path)
    citations, claims, knowledge_version = _knowledge_bundle(
        session,
        settings,
        analysis_date,
    )
    previous = _latest_report(session, household_id)
    if request.expected_report_sequence is not None:
        actual = previous.sequence if previous is not None else None
        if actual != request.expected_report_sequence:
            raise AppError(
                "report_version_conflict",
                "正式规划书已产生新版本，请刷新后重试",
                status_code=409,
                details={"expected": request.expected_report_sequence, "actual": actual},
            )
    sequence = 1 if previous is None else previous.sequence + 1
    generated_at = utc_now()
    status, watermark, workflow_label = _status_for_workflow(workflow)
    report_id = new_id()
    record = PlanReport(
        id=report_id,
        household_id=household_id,
        sequence=sequence,
        parent_report_id=previous.id if previous else None,
        workflow_id=workflow.workflow_id if workflow else None,
        workflow_version_id=workflow.id if workflow else None,
        report_version=f"formal-report-v1.0.0-r{sequence}",
        chapter_count=8,
        structured_report={},
        generated_at=generated_at,
        consistency_status="building",
        generation_trigger=request.trigger,
        generation_reason=request.reason,
        report_hash="pending",
        input_version=plan.meta.input_version,
        formula_version=analysis.meta.formula_version,
        planning_rule_version=plan.meta.rule_version,
        portfolio_rule_version=portfolio.meta.rule_version,
        twin_result_version=twin.meta.result_version,
        model_version=MODEL_VERSION,
        prompt_version=PROMPT_VERSION,
        knowledge_version=knowledge_version,
        product_catalog_version=portfolio.meta.catalog_version,
        watermark=watermark,
        is_current=True,
        currency=facts.currency,
        valuation_date=analysis.meta.data_as_of,
        data_source=REPORT_ENGINE_VERSION,
        is_user_confirmed=False,
    )
    session.add(record)
    session.flush()
    calendar = build_action_calendar(plan, analysis_date)
    action_records = _sync_actions(
        session,
        household_id,
        report_id,
        facts.currency,
        analysis.meta.data_as_of,
        calendar,
    )
    action_out = [_action_out(item) for item in action_records]
    metrics = _action_metrics(action_records)
    document = compose_formal_report(
        report_id=report_id,
        sequence=sequence,
        parent_report_id=record.parent_report_id,
        workflow_id=record.workflow_id,
        workflow_version_id=record.workflow_version_id,
        workflow_state=workflow.state.value if workflow else None,
        workflow_version_label=workflow_label,
        status=status,
        watermark=watermark,
        trigger=request.trigger,
        reason=request.reason,
        generated_at=generated_at,
        facts=facts,
        analysis=analysis,
        plan=plan,
        portfolio=portfolio,
        fund_advisory=fund_advisory,
        twin=twin,
        behavior=behavior,
        actions=action_out,
        execution_metrics=metrics,
        citations=citations,
        sourced_claims=claims,
        knowledge_version=knowledge_version,
        model_version=MODEL_VERSION,
        prompt_version=PROMPT_VERSION,
    )
    report_hash = _report_hash(document)
    document = document.model_copy(update={"report_hash": report_hash})
    document = FormalReportDocument.model_validate(document.model_dump(mode="json"))
    record.structured_report = document.model_dump(mode="json")
    record.consistency_status = document.consistency_status
    record.report_hash = report_hash
    if previous is not None:
        previous.is_current = False
    _attach_review_records(session, workflow, record)
    record_model_run(
        session,
        household_id=household_id,
        actor=actor,
        provider="deterministic_composer",
        model_name=MODEL_VERSION,
        task="report",
        prompt_version=PROMPT_VERSION,
        inputs={
            "verified_fact_refs": [analysis.meta.input_version, plan.meta.input_version],
            "citation_ids": [item.citation_id for item in document.citations],
            "risk_flags": [
                item.code for item in document.consistency_checks if item.status != "passed"
            ],
        },
        output={
            "report_hash": report_hash,
            "chapter_count": document.chapter_count,
            "consistency_status": document.consistency_status,
        },
        started_at=generated_at,
        degraded=document.consistency_status != "passed",
        human_review_required=document.status == "draft_requires_human_review",
        fallback_reason=(
            "controlled_source_or_consistency_review_required"
            if document.consistency_status != "passed"
            else None
        ),
    )
    event_type = (
        AuditEventType.REPORT_GENERATED
        if sequence == 1 and request.trigger == "manual"
        else AuditEventType.REPORT_RECALCULATED
    )
    session.add(
        AuditEvent(
            household_id=household_id,
            event_type=event_type,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="PlanReport",
            entity_id=record.id,
            event_version=sequence,
            summary=f"生成正式八章规划书 R{sequence}：{request.trigger}",
            evidence={
                "report_id": record.id,
                "sequence": sequence,
                "parent_report_id": record.parent_report_id,
                "report_hash": report_hash,
                "workflow_id": record.workflow_id,
                "workflow_version_id": record.workflow_version_id,
                "trigger": request.trigger,
                "reason": request.reason,
                "consistency_status": document.consistency_status,
                "numeric_claim_count": len(document.numeric_ledger),
                "citation_count": len(document.citations),
                "chapter_count": document.chapter_count,
                "versions": document.versions.model_dump(mode="json"),
            },
            occurred_at=generated_at,
            valuation_date=analysis.meta.data_as_of,
            data_source=REPORT_ENGINE_VERSION,
            is_user_confirmed=actor.role == "client",
        )
    )
    return record


def generate_formal_report(
    session: Session,
    household_id: str,
    request: ReportGenerationRequest,
    actor: ActorContext,
    settings: Settings,
) -> FormalReportDocument:
    try:
        record = _compose_and_stage_report(session, household_id, request, actor, settings)
        session.commit()
        session.refresh(record)
        return _document(record)
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "report_write_conflict",
            "正式规划书写入冲突，请刷新后重试",
            status_code=409,
        ) from exc
    except Exception:
        session.rollback()
        raise


def recalculate_formal_report(
    session: Session,
    household_id: str,
    request: ReportRecalculationRequest,
    actor: ActorContext,
    settings: Settings,
) -> FormalReportDocument:
    return generate_formal_report(
        session,
        household_id,
        ReportGenerationRequest(
            analysis_date=request.analysis_date,
            trigger=request.trigger,
            reason=request.reason,
            expected_report_sequence=request.expected_report_sequence,
        ),
        actor,
        settings,
    )


def list_report_actions(session: Session, household_id: str) -> ReportActionList:
    load_household_facts(session, household_id)
    current = _latest_report(session, household_id)
    items = _current_action_items(session, household_id)
    return ReportActionList(
        household_id=household_id,
        report_id=current.id if current else None,
        report_sequence=current.sequence if current else None,
        items=[_action_out(item) for item in items],
        metrics=_action_metrics(items),
    )


def update_report_action(
    session: Session,
    household_id: str,
    action_code: str,
    request: ReportActionUpdateRequest,
    actor: ActorContext,
    settings: Settings,
) -> ReportActionUpdateResponse:
    current = _latest_report(session, household_id)
    if current is None:
        raise AppError(
            "report_required_for_action",
            "请先一键生成正式规划书，再更新行动状态",
            status_code=409,
        )
    item = session.scalar(
        select(ActionItem).where(
            ActionItem.household_id == household_id,
            ActionItem.action_code == action_code,
            ActionItem.data_source == ACTION_ENGINE_VERSION,
            ActionItem.is_deleted.is_(False),
        )
    )
    if item is None:
        raise AppError("report_action_not_found", "找不到正式报告行动", status_code=404)
    if item.version != request.expected_version:
        raise AppError(
            "action_version_conflict",
            "行动状态已变化，请刷新后重试",
            status_code=409,
            details={"expected": request.expected_version, "actual": item.version},
        )
    if (
        request.status == "deferred"
        and request.deferred_until is not None
        and request.deferred_until <= (current.valuation_date or date.today())
    ):
        raise AppError(
            "deferred_date_invalid",
            "延期日期必须晚于当前报告数据日",
            status_code=422,
        )
    previous_status = item.status
    changed_at = utc_now()
    item.status = request.status
    item.status_reason = request.reason
    item.status_changed_at = changed_at
    item.completed_at = changed_at if request.status == "completed" else None
    item.deferred_until = request.deferred_until if request.status == "deferred" else None
    item.is_user_confirmed = actor.role == "client"
    item.version += 1
    next_record = _compose_and_stage_report(
        session,
        household_id,
        ReportGenerationRequest(
            analysis_date=current.valuation_date,
            trigger="action_status_change",
            reason=f"行动 {item.title}：{previous_status} → {request.status}；{request.reason}",
            expected_report_sequence=current.sequence,
        ),
        actor,
        settings,
    )
    next_document = _document(next_record)
    session.add(
        AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.REPORT_ACTION_UPDATED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="ActionItem",
            entity_id=item.id,
            event_version=item.version,
            summary=f"行动 {action_code}：{previous_status} → {request.status}",
            evidence={
                "action_code": action_code,
                "before": previous_status,
                "after": request.status,
                "reason": request.reason,
                "deferred_until": (
                    request.deferred_until.isoformat() if request.deferred_until else None
                ),
                "new_report_id": next_record.id,
                "new_report_sequence": next_record.sequence,
                "execution_metrics": next_document.execution_metrics.model_dump(mode="json"),
            },
            occurred_at=changed_at,
            valuation_date=next_record.valuation_date,
            data_source=ACTION_ENGINE_VERSION,
            is_user_confirmed=actor.role == "client",
        )
    )
    try:
        session.commit()
        session.refresh(item)
        session.refresh(next_record)
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "action_update_conflict",
            "行动更新与报告重算冲突，请刷新后重试",
            status_code=409,
        ) from exc
    return ReportActionUpdateResponse(
        action=_action_out(item),
        metrics=_document(next_record).execution_metrics,
        report=report_summary(next_record),
    )


def report_generation_chain(
    session: Session,
    household_id: str,
) -> ReportGenerationChain:
    load_household_facts(session, household_id)
    records = list(
        session.scalars(
            select(PlanReport)
            .where(
                PlanReport.household_id == household_id,
                PlanReport.is_deleted.is_(False),
            )
            .order_by(PlanReport.sequence)
        ).all()
    )
    expected_parent: str | None = None
    verified = True
    for index, record in enumerate(records, start=1):
        document = _document(record)
        verified = verified and record.sequence == index
        verified = verified and record.parent_report_id == expected_parent
        verified = verified and record.report_hash == _report_hash(document)
        expected_parent = record.id
    event_ids = list(
        session.scalars(
            select(AuditEvent.id)
            .where(
                AuditEvent.household_id == household_id,
                AuditEvent.entity_type.in_(["PlanReport", "ActionItem"]),
                AuditEvent.event_type.in_(
                    [
                        AuditEventType.REPORT_GENERATED,
                        AuditEventType.REPORT_RECALCULATED,
                        AuditEventType.REPORT_ACTION_UPDATED,
                        AuditEventType.REPORT_EXPORT_SUCCEEDED,
                        AuditEventType.REPORT_EXPORT_FAILED,
                    ]
                ),
                AuditEvent.is_deleted.is_(False),
            )
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        ).all()
    )
    return ReportGenerationChain(
        household_id=household_id,
        current_report_id=records[-1].id if records else None,
        chain_verified=verified,
        items=[report_summary(item) for item in records],
        audit_event_ids=event_ids,
        boundary_note=(
            "链条只追加报告快照与行动审计；历史结构化报告不被新数据、月度复盘或重大事件覆盖。"
        ),
    )


def record_export_event(
    session: Session,
    record: PlanReport,
    actor: ActorContext,
    *,
    export_format: str,
    succeeded: bool,
    diagnostics: dict[str, object],
) -> str:
    event = AuditEvent(
        household_id=record.household_id,
        event_type=(
            AuditEventType.REPORT_EXPORT_SUCCEEDED
            if succeeded
            else AuditEventType.REPORT_EXPORT_FAILED
        ),
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="PlanReport",
        entity_id=record.id,
        event_version=record.sequence,
        summary=(
            f"正式规划书 R{record.sequence} {export_format.upper()} "
            f"{'导出成功' if succeeded else '导出失败'}"
        ),
        evidence={
            "report_id": record.id,
            "report_hash": record.report_hash,
            "format": export_format,
            "succeeded": succeeded,
            "diagnostics": diagnostics,
        },
        occurred_at=utc_now(),
        valuation_date=record.valuation_date,
        data_source=REPORT_ENGINE_VERSION,
        is_user_confirmed=False,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event.id
