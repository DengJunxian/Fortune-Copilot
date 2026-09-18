from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, ActorRole, require_household_access, require_roles
from app.core.config import get_settings
from app.core.errors import AppError
from app.domain.enums import (
    AuditEventType,
    MarketScenario,
    PlanWorkflowAction,
    PlanWorkflowState,
    PortfolioCandidateType,
    SuitabilityDecision,
    SuitabilityStatus,
)
from app.models.common import new_id, utc_now
from app.models.family import ConsentRecord, Household
from app.models.governance import (
    AdvisorReview,
    AuditEvent,
    CustomerConfirmation,
    PlanWorkflowVersion,
)
from app.schemas.review_workflow import (
    WORKFLOW_STATE_ORDER,
    AdvisorCandidateSummary,
    AdvisorDossier,
    AdvisorHouseholdList,
    AdvisorHouseholdSummary,
    ComplaintReplayRequest,
    ComplaintReplayResponse,
    ComplianceControl,
    ComplianceEvidence,
    ComplianceQueue,
    ComplianceQueueItem,
    CreatePlanWorkflowRequest,
    PlanWorkflowResponse,
    PlanWorkflowVersionOut,
    WorkflowActionRequest,
    WorkflowAuditPackage,
    WorkflowVersionLedger,
)
from app.services.client_experience import build_client_experience
from app.services.crud import ensure_household
from app.services.financial.engine import analyze_household
from app.services.governance.evidence import (
    build_workflow_decision_evidence,
    refresh_workflow_decision_evidence,
)
from app.services.mock_bank import build_mock_bank_snapshot
from app.services.planning.engine import plan_household
from app.services.portfolio.engine import portfolio_household
from app.services.trust.knowledge import load_knowledge_dataset

WORKFLOW_ENGINE_VERSION = "plan-review-workflow-v1.0.0"
MODEL_VERSION = "mock-editable-template-v1.0.0"
PROMPT_VERSION = "advisor-communication-contract-v1.0.0"
EMPTY_HASH = hashlib.sha256(b"").hexdigest()

ADVISOR_ROLES: tuple[ActorRole, ...] = ("advisor", "admin")
COMPLIANCE_ROLES: tuple[ActorRole, ...] = ("compliance", "admin")
CLIENT_ROLES: tuple[ActorRole, ...] = ("client", "admin")
READ_ROLES: tuple[ActorRole, ...] = ("client", "advisor", "compliance", "admin")

STATE_ACTIONS: dict[PlanWorkflowState, tuple[PlanWorkflowAction, ...]] = {
    PlanWorkflowState.DRAFT: (PlanWorkflowAction.CALCULATE,),
    PlanWorkflowState.CALCULATED: (PlanWorkflowAction.SUITABILITY_CHECK,),
    PlanWorkflowState.SUITABILITY_CHECKED: (PlanWorkflowAction.ADVISOR_REVIEW,),
    PlanWorkflowState.ADVISOR_REVIEWED: (
        PlanWorkflowAction.REVISE_ADVICE,
        PlanWorkflowAction.EDIT_COMMUNICATION,
        PlanWorkflowAction.SUBMIT_COMPLIANCE,
        PlanWorkflowAction.COMPLIANCE_APPROVE,
        PlanWorkflowAction.COMPLIANCE_RETURN,
        PlanWorkflowAction.REQUIRE_HUMAN_REVIEW,
    ),
    PlanWorkflowState.COMPLIANCE_REVIEWED: (PlanWorkflowAction.CUSTOMER_CONFIRM,),
    PlanWorkflowState.CUSTOMER_CONFIRMED: (PlanWorkflowAction.ACTIVATE,),
    PlanWorkflowState.ACTIVE: (PlanWorkflowAction.SUPERSEDE,),
    PlanWorkflowState.SUPERSEDED: (),
}

ACTION_ROLES: dict[PlanWorkflowAction, tuple[ActorRole, ...]] = {
    PlanWorkflowAction.CALCULATE: ADVISOR_ROLES,
    PlanWorkflowAction.SUITABILITY_CHECK: ADVISOR_ROLES,
    PlanWorkflowAction.ADVISOR_REVIEW: ADVISOR_ROLES,
    PlanWorkflowAction.REVISE_ADVICE: ADVISOR_ROLES,
    PlanWorkflowAction.EDIT_COMMUNICATION: ADVISOR_ROLES,
    PlanWorkflowAction.SUBMIT_COMPLIANCE: ADVISOR_ROLES,
    PlanWorkflowAction.COMPLIANCE_APPROVE: COMPLIANCE_ROLES,
    PlanWorkflowAction.COMPLIANCE_RETURN: COMPLIANCE_ROLES,
    PlanWorkflowAction.REQUIRE_HUMAN_REVIEW: COMPLIANCE_ROLES,
    PlanWorkflowAction.CUSTOMER_CONFIRM: CLIENT_ROLES,
    PlanWorkflowAction.ACTIVATE: ADVISOR_ROLES,
    PlanWorkflowAction.SUPERSEDE: ADVISOR_ROLES,
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


def _hash_material(values: dict[str, object]) -> dict[str, object]:
    keys = (
        "workflow_id",
        "household_id",
        "sequence",
        "cycle",
        "prior_version_id",
        "state",
        "action",
        "reason",
        "actor_id",
        "actor_role",
        "selected_candidate",
        "recommendation_snapshot",
        "suitability_snapshot",
        "communication_draft",
        "advisor_decision",
        "compliance_decision",
        "customer_confirmation",
        "submitted_for_compliance",
        "requires_human_review",
        "input_version",
        "rule_version",
        "model_version",
        "prompt_version",
        "knowledge_version",
        "product_catalog_version",
        "before_hash",
        "request_id",
    )
    return {key: values[key] for key in keys}


def _record_values(record: PlanWorkflowVersion) -> dict[str, object]:
    return {
        "workflow_id": record.workflow_id,
        "household_id": record.household_id,
        "sequence": record.sequence,
        "cycle": record.cycle,
        "prior_version_id": record.prior_version_id,
        "state": record.state.value,
        "action": record.action,
        "reason": record.reason,
        "actor_id": record.actor_id,
        "actor_role": record.actor_role,
        "selected_candidate": record.selected_candidate,
        "recommendation_snapshot": record.recommendation_snapshot,
        "suitability_snapshot": record.suitability_snapshot,
        "communication_draft": record.communication_draft,
        "advisor_decision": record.advisor_decision,
        "compliance_decision": record.compliance_decision,
        "customer_confirmation": record.customer_confirmation,
        "submitted_for_compliance": record.submitted_for_compliance,
        "requires_human_review": record.requires_human_review,
        "input_version": record.input_version,
        "rule_version": record.rule_version,
        "model_version": record.model_version,
        "prompt_version": record.prompt_version,
        "knowledge_version": record.knowledge_version,
        "product_catalog_version": record.product_catalog_version,
        "before_hash": record.before_hash,
        "request_id": record.request_id,
    }


def _event_type(action: PlanWorkflowAction) -> AuditEventType:
    if action in {
        PlanWorkflowAction.COMPLIANCE_APPROVE,
        PlanWorkflowAction.COMPLIANCE_RETURN,
        PlanWorkflowAction.REQUIRE_HUMAN_REVIEW,
    }:
        return AuditEventType.COMPLIANCE_DECISION_RECORDED
    if action == PlanWorkflowAction.CUSTOMER_CONFIRM:
        return AuditEventType.CONFIRMATION_RECORDED
    return AuditEventType.PLAN_WORKFLOW_VERSIONED


def _audit_version(
    session: Session,
    version: PlanWorkflowVersion,
    actor: ActorContext,
) -> None:
    session.add(
        AuditEvent(
            household_id=version.household_id,
            event_type=_event_type(PlanWorkflowAction(version.action)),
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="PlanWorkflowVersion",
            entity_id=version.id,
            event_version=version.sequence,
            summary=(
                f"方案 {version.workflow_id[:8]} 生成第 {version.sequence} 版："
                f"{version.action} → {version.state.value}"
            ),
            evidence={
                "actor": actor.actor_id,
                "role": actor.role,
                "time": version.created_at.isoformat(),
                "action": version.action,
                "object": {
                    "workflow_id": version.workflow_id,
                    "version_id": version.id,
                    "version_number": version.sequence,
                    "state": version.state.value,
                },
                "before_hash": version.before_hash,
                "after_hash": version.after_hash,
                "reason": version.reason,
                "rule_version": version.rule_version,
                "model_version": version.model_version,
                "prompt_version": version.prompt_version,
                "knowledge_version": version.knowledge_version,
                "product_catalog_version": version.product_catalog_version,
                "request_id": version.request_id,
            },
            occurred_at=version.created_at,
            data_source=WORKFLOW_ENGINE_VERSION,
            is_user_confirmed=True,
        )
    )


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "workflow_conflict",
            "方案版本写入冲突，请刷新后重试",
            status_code=409,
        ) from exc


def _current_version(session: Session, workflow_id: str) -> PlanWorkflowVersion:
    version = session.scalar(
        select(PlanWorkflowVersion)
        .where(
            PlanWorkflowVersion.workflow_id == workflow_id,
            PlanWorkflowVersion.is_current.is_(True),
            PlanWorkflowVersion.is_deleted.is_(False),
        )
        .order_by(PlanWorkflowVersion.sequence.desc())
    )
    if version is None:
        raise AppError("workflow_not_found", "方案审核流不存在", status_code=404)
    return version


def _workflow_versions(session: Session, workflow_id: str) -> list[PlanWorkflowVersion]:
    return list(
        session.scalars(
            select(PlanWorkflowVersion)
            .where(
                PlanWorkflowVersion.workflow_id == workflow_id,
                PlanWorkflowVersion.is_deleted.is_(False),
            )
            .order_by(PlanWorkflowVersion.sequence)
        ).all()
    )


def _latest_household_version(
    session: Session,
    household_id: str,
) -> PlanWorkflowVersion | None:
    return session.scalar(
        select(PlanWorkflowVersion)
        .where(
            PlanWorkflowVersion.household_id == household_id,
            PlanWorkflowVersion.is_current.is_(True),
            PlanWorkflowVersion.is_deleted.is_(False),
        )
        .order_by(PlanWorkflowVersion.created_at.desc(), PlanWorkflowVersion.sequence.desc())
    )


def _active_consents(session: Session, household_id: str) -> list[ConsentRecord]:
    return list(
        session.scalars(
            select(ConsentRecord).where(
                ConsentRecord.household_id == household_id,
                ConsentRecord.withdrawn_at.is_(None),
                ConsentRecord.is_deleted.is_(False),
            )
        ).all()
    )


def _require_planning_consent(session: Session, household_id: str) -> None:
    consents = _active_consents(session, household_id)
    if not any({"profile", "finance", "risk"}.issubset(set(item.scopes)) for item in consents):
        raise AppError(
            "consent_required",
            "客户已撤回或尚未授予方案计算所需授权，审核流已阻断",
            status_code=409,
            details={"required_scopes": ["profile", "finance", "risk"]},
        )


def _new_version(
    session: Session,
    *,
    household_id: str,
    workflow_id: str,
    sequence: int,
    cycle: int,
    prior: PlanWorkflowVersion | None,
    state: PlanWorkflowState,
    action: PlanWorkflowAction,
    reason: str,
    actor: ActorContext,
    request_id: str,
    overrides: dict[str, object] | None = None,
) -> PlanWorkflowVersion:
    if prior is None:
        values: dict[str, object] = {
            "selected_candidate": None,
            "recommendation_snapshot": {},
            "suitability_snapshot": {},
            "communication_draft": "",
            "advisor_decision": None,
            "compliance_decision": None,
            "customer_confirmation": {},
            "submitted_for_compliance": False,
            "requires_human_review": False,
            "input_version": "pending",
            "rule_version": "pending",
            "model_version": MODEL_VERSION,
            "prompt_version": PROMPT_VERSION,
            "knowledge_version": "pending",
            "product_catalog_version": "pending",
        }
        before_hash = EMPTY_HASH
    else:
        values = {
            "selected_candidate": prior.selected_candidate,
            "recommendation_snapshot": copy.deepcopy(prior.recommendation_snapshot),
            "suitability_snapshot": copy.deepcopy(prior.suitability_snapshot),
            "communication_draft": prior.communication_draft,
            "advisor_decision": prior.advisor_decision,
            "compliance_decision": prior.compliance_decision,
            "customer_confirmation": copy.deepcopy(prior.customer_confirmation),
            "submitted_for_compliance": prior.submitted_for_compliance,
            "requires_human_review": prior.requires_human_review,
            "input_version": prior.input_version,
            "rule_version": prior.rule_version,
            "model_version": prior.model_version,
            "prompt_version": prior.prompt_version,
            "knowledge_version": prior.knowledge_version,
            "product_catalog_version": prior.product_catalog_version,
        }
        before_hash = prior.after_hash
    values.update(overrides or {})
    recommendation_snapshot = values["recommendation_snapshot"]
    if isinstance(recommendation_snapshot, dict):
        evidence = recommendation_snapshot.get("decision_evidence")
        prior_had_evidence = bool(
            prior is not None
            and isinstance(prior.recommendation_snapshot, dict)
            and prior.recommendation_snapshot.get("decision_evidence")
        )
        if prior_had_evidence and isinstance(evidence, dict):
            suitability_snapshot = values["suitability_snapshot"]
            customer_confirmation = values["customer_confirmation"]
            refreshed = refresh_workflow_decision_evidence(
                evidence,
                selected_candidate=values["selected_candidate"],
                recommendation_snapshot=recommendation_snapshot,
                suitability_snapshot=(
                    suitability_snapshot if isinstance(suitability_snapshot, dict) else {}
                ),
                communication_draft=str(values["communication_draft"]),
                advisor_decision=values["advisor_decision"],
                compliance_decision=values["compliance_decision"],
                customer_confirmation=(
                    customer_confirmation if isinstance(customer_confirmation, dict) else {}
                ),
                generated_at=utc_now(),
            )
            recommendation_snapshot = copy.deepcopy(recommendation_snapshot)
            recommendation_snapshot["decision_evidence"] = refreshed.model_dump(mode="json")
            values["recommendation_snapshot"] = recommendation_snapshot

    material = {
        "workflow_id": workflow_id,
        "household_id": household_id,
        "sequence": sequence,
        "cycle": cycle,
        "prior_version_id": prior.id if prior is not None else None,
        "state": state.value,
        "action": action.value,
        "reason": reason,
        "actor_id": actor.actor_id,
        "actor_role": actor.role,
        **values,
        "before_hash": before_hash,
        "request_id": request_id,
    }
    after_hash = _json_hash(_hash_material(material))
    if prior is not None:
        prior.is_current = False
    version = PlanWorkflowVersion(
        household_id=household_id,
        workflow_id=workflow_id,
        sequence=sequence,
        cycle=cycle,
        prior_version_id=prior.id if prior is not None else None,
        state=state,
        action=action.value,
        reason=reason,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        selected_candidate=values["selected_candidate"],
        recommendation_snapshot=values["recommendation_snapshot"],
        suitability_snapshot=values["suitability_snapshot"],
        communication_draft=values["communication_draft"],
        advisor_decision=values["advisor_decision"],
        compliance_decision=values["compliance_decision"],
        customer_confirmation=values["customer_confirmation"],
        submitted_for_compliance=values["submitted_for_compliance"],
        requires_human_review=values["requires_human_review"],
        is_current=True,
        input_version=values["input_version"],
        rule_version=values["rule_version"],
        model_version=values["model_version"],
        prompt_version=values["prompt_version"],
        knowledge_version=values["knowledge_version"],
        product_catalog_version=values["product_catalog_version"],
        before_hash=before_hash,
        after_hash=after_hash,
        request_id=request_id,
        valuation_date=date.today(),
        data_source=WORKFLOW_ENGINE_VERSION,
        is_user_confirmed=True,
        version=sequence,
    )
    session.add(version)
    session.flush()
    _audit_version(session, version, actor)
    return version


def _to_out(record: PlanWorkflowVersion) -> PlanWorkflowVersionOut:
    return PlanWorkflowVersionOut(
        id=record.id,
        workflow_id=record.workflow_id,
        household_id=record.household_id,
        version_number=record.sequence,
        cycle=record.cycle,
        prior_version_id=record.prior_version_id,
        state=record.state,
        action=PlanWorkflowAction(record.action),
        reason=record.reason,
        actor_id=record.actor_id,
        actor_role=record.actor_role,
        selected_candidate=(
            PortfolioCandidateType(record.selected_candidate)
            if record.selected_candidate is not None
            else None
        ),
        recommendation_snapshot=record.recommendation_snapshot,
        suitability_snapshot=record.suitability_snapshot,
        communication_draft=record.communication_draft,
        advisor_decision=record.advisor_decision,
        compliance_decision=record.compliance_decision,
        customer_confirmation=record.customer_confirmation,
        submitted_for_compliance=record.submitted_for_compliance,
        requires_human_review=record.requires_human_review,
        is_current=record.is_current,
        versions=WorkflowVersionLedger(
            input_version=record.input_version,
            rule_version=record.rule_version,
            model_version=record.model_version,
            prompt_version=record.prompt_version,
            knowledge_version=record.knowledge_version,
            product_catalog_version=record.product_catalog_version,
        ),
        before_hash=record.before_hash,
        after_hash=record.after_hash,
        request_id=record.request_id,
        created_at=record.created_at,
    )


def _next_actions(current: PlanWorkflowVersion, actor: ActorContext) -> list[PlanWorkflowAction]:
    actions: list[PlanWorkflowAction] = []
    for action in STATE_ACTIONS[current.state]:
        if actor.role not in ACTION_ROLES[action]:
            continue
        if (
            action
            in {
                PlanWorkflowAction.COMPLIANCE_APPROVE,
                PlanWorkflowAction.COMPLIANCE_RETURN,
                PlanWorkflowAction.REQUIRE_HUMAN_REVIEW,
            }
            and not current.submitted_for_compliance
        ):
            continue
        if action == PlanWorkflowAction.SUBMIT_COMPLIANCE and current.submitted_for_compliance:
            continue
        actions.append(action)
    return actions


def _response(
    session: Session,
    current: PlanWorkflowVersion,
    actor: ActorContext,
) -> PlanWorkflowResponse:
    versions = _workflow_versions(session, current.workflow_id)
    current_out = _to_out(current)
    version_outputs = [_to_out(item) for item in versions]
    if actor.role == "client":
        selected = (
            _candidate(current.recommendation_snapshot, current.selected_candidate)
            if current.selected_candidate is not None
            else {}
        )
        compliance_raw = current.suitability_snapshot.get("compliance_evidence", {})
        compliance = compliance_raw if isinstance(compliance_raw, dict) else {}
        current_out = current_out.model_copy(
            update={
                "reason": "合规通过后的客户可见方案版本",
                "actor_id": "redacted-for-client",
                "recommendation_snapshot": {
                    "selected_candidate": selected,
                    "counting_note": current.recommendation_snapshot.get("counting_note"),
                    "calculation_source": "deterministic_tools",
                },
                "suitability_snapshot": {
                    "overall_decision": compliance.get("overall_decision"),
                    "controls": compliance.get("controls", []),
                },
                "request_id": "redacted-for-client",
            }
        )
        version_outputs = [current_out]
    return PlanWorkflowResponse(
        workflow_id=current.workflow_id,
        household_id=current.household_id,
        current=current_out,
        versions=version_outputs,
        state_order=list(WORKFLOW_STATE_ORDER),
        next_actions=_next_actions(current, actor),
    )


def _assert_client_visibility(current: PlanWorkflowVersion, actor: ActorContext) -> None:
    if actor.role != "client":
        return
    visible = {
        PlanWorkflowState.COMPLIANCE_REVIEWED,
        PlanWorkflowState.CUSTOMER_CONFIRMED,
        PlanWorkflowState.ACTIVE,
        PlanWorkflowState.SUPERSEDED,
    }
    if current.state not in visible:
        raise AppError(
            "workflow_not_ready_for_client",
            "方案尚未通过合规复核，客户端无权查看内部草稿",
            status_code=403,
        )


def create_plan_workflow(
    session: Session,
    household_id: str,
    request: CreatePlanWorkflowRequest,
    actor: ActorContext,
    request_id: str,
) -> PlanWorkflowResponse:
    require_roles(actor, ADVISOR_ROLES)
    ensure_household(session, household_id)
    _require_planning_consent(session, household_id)
    existing = _latest_household_version(session, household_id)
    if existing is not None and existing.state != PlanWorkflowState.SUPERSEDED:
        raise AppError(
            "workflow_already_open",
            "该家庭已有未废止的方案审核流，请继续当前版本或先完成废止",
            status_code=409,
            details={
                "workflow_id": existing.workflow_id,
                "state": existing.state.value,
                "version": existing.sequence,
            },
        )
    workflow_id = new_id()
    version = _new_version(
        session,
        household_id=household_id,
        workflow_id=workflow_id,
        sequence=1,
        cycle=1,
        prior=None,
        state=PlanWorkflowState.DRAFT,
        action=PlanWorkflowAction.CREATE,
        reason=request.reason,
        actor=actor,
        request_id=request_id,
    )
    _commit(session)
    session.refresh(version)
    return _response(session, version, actor)


def get_plan_workflow(
    session: Session,
    workflow_id: str,
    actor: ActorContext,
) -> PlanWorkflowResponse:
    require_roles(actor, READ_ROLES)
    current = _current_version(session, workflow_id)
    require_household_access(actor, current.household_id)
    _assert_client_visibility(current, actor)
    return _response(session, current, actor)


def get_latest_household_workflow(
    session: Session,
    household_id: str,
    actor: ActorContext,
) -> PlanWorkflowResponse | None:
    require_roles(actor, READ_ROLES)
    require_household_access(actor, household_id)
    ensure_household(session, household_id)
    current = _latest_household_version(session, household_id)
    if current is None:
        return None
    _assert_client_visibility(current, actor)
    return _response(session, current, actor)


def _portfolio_snapshot(
    session: Session,
    household_id: str,
    workflow_id: str,
) -> dict[str, object]:
    settings = get_settings()
    portfolio = portfolio_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        date.today(),
        MarketScenario.NEUTRAL,
    )
    candidates = [item.model_dump(mode="json") for item in portfolio.candidates]
    numeric_ledger: dict[str, str] = {
        "eligible_long_term_amount": str(portfolio.context.eligible_long_term_amount),
        "annual_new_surplus": str(portfolio.context.annual_new_surplus),
    }
    for item in portfolio.candidates:
        prefix = item.candidate_type.value
        numeric_ledger[f"{prefix}.investment_amount"] = str(item.investment_amount)
        numeric_ledger[f"{prefix}.expected_nominal_return"] = str(item.expected_nominal_return)
        numeric_ledger[f"{prefix}.max_drawdown_estimate"] = str(item.max_drawdown_estimate)
        numeric_ledger[f"{prefix}.extreme_loss_amount"] = str(item.extreme_loss_amount)
        numeric_ledger[f"{prefix}.liquidity_score"] = str(item.liquidity_score)
        numeric_ledger[f"{prefix}.annual_fee_estimate"] = str(item.annual_fee_estimate)
    knowledge = load_knowledge_dataset(settings.knowledge_base_path)
    snapshot: dict[str, object] = {
        "meta": portfolio.meta.model_dump(mode="json"),
        "context": portfolio.context.model_dump(mode="json"),
        "candidates": candidates,
        "numeric_ledger": numeric_ledger,
        "counting_note": portfolio.counting_note,
        "calculation_source": "deterministic_tools",
        "knowledge_version": knowledge.dataset_version,
    }
    evidence, cfs_snapshot = build_workflow_decision_evidence(
        session,
        household_id=household_id,
        workflow_id=workflow_id,
        recommendation_snapshot=snapshot,
        settings=settings,
        generated_at=utc_now(),
    )
    snapshot.update(cfs_snapshot)
    snapshot["decision_evidence"] = evidence.model_dump(mode="json")
    return snapshot


def _candidate(snapshot: dict[str, object], candidate_type: str) -> dict[str, Any]:
    candidates = snapshot.get("candidates", [])
    if not isinstance(candidates, list):
        raise AppError("workflow_snapshot_invalid", "方案快照缺少候选方案", status_code=409)
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("candidate_type") == candidate_type:
            return candidate
    raise AppError("candidate_not_found", "所选候选方案不存在", status_code=422)


def _is_high_risk(candidate: dict[str, Any]) -> bool:
    mappings = candidate.get("product_mappings", [])
    return any(
        isinstance(item, dict)
        and item.get("risk_level") in {"r4", "r5"}
        and Decimal(str(item.get("allocation_ratio", "0"))) > 0
        for item in mappings
    )


def _advisor_template(household: Household, candidate: dict[str, Any]) -> str:
    amount = Decimal(str(candidate["investment_amount"]))
    drawdown = Decimal(str(candidate["max_drawdown_estimate"])) * Decimal("100")
    liquidity = Decimal(str(candidate["liquidity_score"])) * Decimal("100")
    execution_boundary = (
        "三道闸门当前只允许教育与安全层修复，不授权产品执行。"
        if candidate.get("decision") == SuitabilityDecision.EDUCATION_ONLY.value
        else "后续执行仍需通过合规审核与客户逐项确认。"
    )
    return (
        f"{household.name}您好。本次先核对家庭安全层和目标期限，再讨论长期资金。"
        f"当前候选方案只使用通过前置约束后的长期资金 {amount:.2f} 元；"
        f"压力口径下的最大回撤估计约 {drawdown:.2f}%，流动性评分 {liquidity:.2f}%。"
        "这些结果来自确定性工具和合成 Mock 数据，不是收益预测，也不承诺保本或收益。"
        f"{execution_boundary}若家庭收入、目标、授权或风险承受能力变化，需要重新计算并由人工复核。"
    )


def _selected_advice(
    session: Session,
    current: PlanWorkflowVersion,
    request: WorkflowActionRequest,
) -> dict[str, object]:
    assert request.selected_candidate is not None
    candidate = _candidate(current.recommendation_snapshot, request.selected_candidate.value)
    high_risk = _is_high_risk(candidate)
    if high_risk and not request.manual_high_risk_confirmed:
        raise AppError(
            "manual_high_risk_confirmation_required",
            "候选方案含较高风险产品类型，必须由客户经理人工确认后才能提交",
            status_code=409,
        )
    household = ensure_household(session, current.household_id)
    return {
        "selected_candidate": request.selected_candidate.value,
        "communication_draft": (
            request.communication_draft.strip()
            if request.communication_draft and request.communication_draft.strip()
            else _advisor_template(household, candidate)
        ),
        "advisor_decision": "manually_reviewed",
        "submitted_for_compliance": False,
        "requires_human_review": high_risk,
        "compliance_decision": None,
        "recommendation_snapshot": {
            **current.recommendation_snapshot,
            "advisor_modification": {
                "selected_candidate": request.selected_candidate.value,
                "advisor_note": request.advisor_note or request.reason,
                "manual_high_risk_confirmed": request.manual_high_risk_confirmed,
                "high_risk_product_type_present": high_risk,
                "execution_mode": str(candidate.get("decision")),
            },
        },
    }


def _all_numeric_representations(ledger: dict[str, object]) -> set[str]:
    allowed: set[str] = set()
    for raw in ledger.values():
        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            continue
        allowed.add(format(value, "f"))
        allowed.add(f"{value:.2f}")
        allowed.add(f"{value * Decimal('100'):.2f}")
        allowed.add(f"{value * Decimal('100'):.1f}")
    return allowed


def _prohibited_phrases(text: str) -> list[str]:
    sanitized = text
    for allowed in (
        "不承诺保本或收益",
        "不承诺保本",
        "不保证收益",
        "不构成收益保证",
        "并非稳赚",
        "不是零风险",
    ):
        sanitized = sanitized.replace(allowed, "")
    return [
        phrase
        for phrase in ("保本", "保证收益", "稳赚", "零风险", "绝对安全")
        if phrase in sanitized
    ]


def _control(
    code: str,
    category: str,
    status: str,
    title: str,
    explanation: str,
    rule: str,
    source_record_ids: list[str] | None = None,
) -> ComplianceControl:
    return ComplianceControl.model_validate(
        {
            "code": code,
            "category": category,
            "status": status,
            "title": title,
            "explanation": explanation,
            "rule": rule,
            "source_record_ids": source_record_ids or [],
        }
    )


def _hash_chain_verified(versions: list[PlanWorkflowVersion]) -> bool:
    for index, version in enumerate(versions):
        expected_before = EMPTY_HASH if index == 0 else versions[index - 1].after_hash
        if version.before_hash != expected_before:
            return False
        if version.after_hash != _json_hash(_hash_material(_record_values(version))):
            return False
        if index > 0 and version.prior_version_id != versions[index - 1].id:
            return False
    return True


def evaluate_compliance(
    session: Session,
    version: PlanWorkflowVersion,
) -> ComplianceEvidence:
    if version.selected_candidate is None:
        raise AppError("candidate_required", "方案尚未选择候选方案", status_code=409)
    candidate = _candidate(version.recommendation_snapshot, version.selected_candidate)
    decision = SuitabilityDecision(str(candidate.get("decision")))
    gates = candidate.get("gates", [])
    controls: list[ComplianceControl] = []
    gate_statuses: dict[str, SuitabilityStatus] = {}
    gate_categories = {
        "family_safety": "family_suitability",
        "customer": "customer_suitability",
        "product": "product_suitability",
    }
    gate_titles = {
        "family_safety": "家庭安全闸门",
        "customer": "客户适当性闸门",
        "product": "产品适当性闸门",
    }
    for gate_code in ("family_safety", "customer", "product"):
        gate = next(
            (item for item in gates if isinstance(item, dict) and item.get("gate") == gate_code),
            None,
        )
        status = SuitabilityStatus(str(gate.get("status"))) if gate else SuitabilityStatus.BLOCK
        gate_statuses[gate_code] = status
        education_only_gate = (
            status == SuitabilityStatus.BLOCK and decision == SuitabilityDecision.EDUCATION_ONLY
        )
        control_status = (
            "pass"
            if status == SuitabilityStatus.PASS
            else "warning"
            if status == SuitabilityStatus.RESTRICT or education_only_gate
            else "block"
        )
        controls.append(
            _control(
                f"gate_{gate_code}",
                gate_categories[gate_code],
                control_status,
                gate_titles[gate_code],
                (
                    "该闸门阻断产品执行；当前版本已降为教育与安全层修复计划。"
                    if education_only_gate
                    else str(gate.get("explanation"))
                    if gate
                    else "缺少闸门证据。"
                ),
                "三道闸门必须逐一存在；任一 block 不得通过。",
                [
                    str(record_id)
                    for check in (gate.get("checks", []) if gate else [])
                    if isinstance(check, dict)
                    for record_id in check.get("source_record_ids", [])
                ],
            )
        )

    prohibited = _prohibited_phrases(version.communication_draft)
    controls.append(
        _control(
            "prohibited_wording",
            "prohibited_wording",
            "block" if prohibited else "pass",
            "禁止性表述",
            (
                f"发现禁止性表述：{'、'.join(prohibited)}。"
                if prohibited
                else "未发现保本、保证收益、稳赚、零风险或绝对安全承诺。"
            ),
            "客户沟通不得作保本保收益或绝对安全承诺。",
        )
    )

    ledger_raw = version.recommendation_snapshot.get("numeric_ledger", {})
    ledger = ledger_raw if isinstance(ledger_raw, dict) else {}
    numeric_tokens = set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?", version.communication_draft))
    untraced = sorted(numeric_tokens - _all_numeric_representations(ledger))
    controls.append(
        _control(
            "numeric_consistency",
            "numeric_consistency",
            "block" if untraced else "pass",
            "数值一致性",
            (
                f"沟通稿存在未对齐工具账本的数字：{', '.join(untraced)}。"
                if untraced
                else "沟通稿数字均可回到确定性候选方案账本。"
            ),
            "关键金额、比率与配置只能来自确定性工具输出。",
        )
    )

    source_terms = [
        term
        for term in ("监管规定", "官方政策", "法律保证", "产品承诺")
        if term in version.communication_draft
    ]
    controls.append(
        _control(
            "source_integrity",
            "source_integrity",
            "block" if source_terms else "pass",
            "政策与产品事实来源",
            (
                f"发现未附受控引用的事实断言：{'、'.join(source_terms)}。"
                if source_terms
                else "沟通稿未使用无来源的政策或产品事实；产品属性来自版本化 Mock 目录。"
            ),
            "外部事实必须来自受控知识库，产品属性必须带目录版本。",
        )
    )

    security_events = list(
        session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.household_id == version.household_id,
                AuditEvent.event_type == AuditEventType.HALLUCINATION_BLOCKED,
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(10)
        ).all()
    )
    controls.append(
        _control(
            "model_governance",
            "model_governance",
            "information" if security_events else "pass",
            "模型幻觉与提示注入",
            (
                f"历史上有 {len(security_events)} 个已拦截事件；本方案使用可编辑 Mock 模板。"
                if security_events
                else "本方案未调用外部模型；沟通稿由可编辑 Mock 模板生成。"
            ),
            "语言模型只能理解与解释，不得生成关键数字；异常输入必须被隔离。",
        )
    )

    consent_ok = any(
        {"profile", "finance", "risk"}.issubset(set(item.scopes))
        for item in _active_consents(session, version.household_id)
    )
    controls.append(
        _control(
            "authorization",
            "authorization",
            "pass" if consent_ok else "block",
            "授权与敏感数据访问",
            "存在有效规划授权。" if consent_ok else "客户授权已撤回或不存在。",
            "无有效授权不得继续计算、审核或确认方案。",
        )
    )

    versions = _workflow_versions(session, version.workflow_id)
    chain_ok = _hash_chain_verified(versions)
    controls.append(
        _control(
            "version_integrity",
            "version_integrity",
            "pass" if chain_ok else "block",
            "版本与哈希链完整性",
            (
                f"已验证 {len(versions)} 个不可变版本。"
                if chain_ok
                else "版本哈希链不连续或内容哈希不匹配。"
            ),
            "每次修改必须产生新版本，before hash 必须等于上一版 after hash。",
            [item.id for item in versions],
        )
    )

    manual = version.recommendation_snapshot.get("advisor_modification", {})
    manual_confirmed = isinstance(manual, dict) and bool(manual.get("manual_high_risk_confirmed"))
    high_risk = _is_high_risk(candidate)
    education_declared = (
        isinstance(manual, dict)
        and manual.get("execution_mode") == SuitabilityDecision.EDUCATION_ONLY.value
    )
    anomalous = decision == SuitabilityDecision.REJECT or (
        decision == SuitabilityDecision.EDUCATION_ONLY and not education_declared
    )
    missing_manual = high_risk and not manual_confirmed
    controls.append(
        _control(
            "anomalous_recommendation",
            "anomalous_recommendation",
            "block"
            if anomalous or missing_manual
            else "warning"
            if decision in {SuitabilityDecision.DOWNGRADE, SuitabilityDecision.EDUCATION_ONLY}
            or high_risk
            else "pass",
            "异常推荐与人工复核",
            (
                "候选方案被拒绝、未声明教育模式，或较高风险产品类型缺少人工确认。"
                if anomalous or missing_manual
                else (
                    "候选方案经过降级或含较高风险产品类型，已保留人工确认。"
                    if decision
                    in {SuitabilityDecision.DOWNGRADE, SuitabilityDecision.EDUCATION_ONLY}
                    or high_risk
                    else "未发现拒绝态候选、未确认高风险产品类型或越权策略。"
                )
            ),
            "拒绝态候选不得通过；高风险建议必须由客户经理人工确认。",
        )
    )

    blocked = [item.code for item in controls if item.status == "block"]
    warnings = [item.code for item in controls if item.status == "warning"]
    overall = "block" if blocked else ("human_review" if warnings else "pass")
    return ComplianceEvidence(
        workflow_id=version.workflow_id,
        version_id=version.id,
        version_number=version.sequence,
        household_id=version.household_id,
        overall_decision=overall,
        controls=controls,
        three_gate_statuses=gate_statuses,
        blocked_codes=blocked,
        warning_codes=warnings,
        prohibited_phrases=prohibited,
        numeric_ledger={str(key): str(value) for key, value in ledger.items()},
        security_events=[
            {
                "event_id": item.id,
                "event_type": item.event_type.value,
                "occurred_at": item.occurred_at.isoformat(),
                "summary": item.summary,
            }
            for item in security_events
        ],
        versions=WorkflowVersionLedger(
            input_version=version.input_version,
            rule_version=version.rule_version,
            model_version=version.model_version,
            prompt_version=version.prompt_version,
            knowledge_version=version.knowledge_version,
            product_catalog_version=version.product_catalog_version,
        ),
        hash_chain_verified=chain_ok,
        explanation=(
            f"阻断 {len(blocked)} 项，预警 {len(warnings)} 项；"
            "结果由三道适当性闸门、文案、数字、来源、授权和版本证据共同决定。"
        ),
    )


def transition_plan_workflow(
    session: Session,
    workflow_id: str,
    request: WorkflowActionRequest,
    actor: ActorContext,
    request_id: str,
) -> PlanWorkflowResponse:
    if request.action == PlanWorkflowAction.CREATE:
        raise AppError("invalid_workflow_action", "创建方案必须使用创建接口", status_code=422)
    require_roles(actor, ACTION_ROLES[request.action])
    current = _current_version(session, workflow_id)
    require_household_access(actor, current.household_id)
    if current.sequence != request.expected_version:
        raise AppError(
            "workflow_version_conflict",
            "方案已产生新版本，请刷新后重试",
            status_code=409,
            details={"expected": request.expected_version, "current": current.sequence},
        )
    if request.action not in STATE_ACTIONS[current.state]:
        raise AppError(
            "workflow_transition_forbidden",
            "不能跳过必要审核环节或从当前状态执行该动作",
            status_code=409,
            details={
                "state": current.state.value,
                "action": request.action.value,
                "allowed_actions": [item.value for item in STATE_ACTIONS[current.state]],
            },
        )
    if request.action not in {
        PlanWorkflowAction.COMPLIANCE_RETURN,
        PlanWorkflowAction.SUPERSEDE,
    }:
        _require_planning_consent(session, current.household_id)

    next_state = current.state
    next_cycle = current.cycle
    overrides: dict[str, object] = {}
    if request.action == PlanWorkflowAction.CALCULATE:
        snapshot = _portfolio_snapshot(
            session,
            current.household_id,
            current.workflow_id,
        )
        meta = snapshot["meta"]
        assert isinstance(meta, dict)
        next_state = PlanWorkflowState.CALCULATED
        overrides = {
            "recommendation_snapshot": snapshot,
            "input_version": str(meta["input_version"]),
            "rule_version": str(meta["rule_version"]),
            "knowledge_version": str(snapshot["knowledge_version"]),
            "product_catalog_version": str(meta["catalog_version"]),
        }
    elif request.action == PlanWorkflowAction.SUITABILITY_CHECK:
        candidates = current.recommendation_snapshot.get("candidates", [])
        overrides = {
            "suitability_snapshot": {
                "candidate_gate_evidence": {
                    str(item.get("candidate_type")): item.get("gates", [])
                    for item in candidates
                    if isinstance(item, dict)
                },
                "calculation_source": "deterministic_suitability_engine",
            }
        }
        next_state = PlanWorkflowState.SUITABILITY_CHECKED
    elif request.action in {
        PlanWorkflowAction.ADVISOR_REVIEW,
        PlanWorkflowAction.REVISE_ADVICE,
    }:
        overrides = _selected_advice(session, current, request)
        next_state = PlanWorkflowState.ADVISOR_REVIEWED
    elif request.action == PlanWorkflowAction.EDIT_COMMUNICATION:
        if request.communication_draft is None or len(request.communication_draft.strip()) < 20:
            raise AppError(
                "communication_draft_invalid",
                "沟通稿至少需要 20 个字符并保留风险边界",
                status_code=422,
            )
        overrides = {
            "communication_draft": request.communication_draft.strip(),
            "submitted_for_compliance": False,
            "compliance_decision": None,
        }
    elif request.action == PlanWorkflowAction.SUBMIT_COMPLIANCE:
        if current.submitted_for_compliance:
            raise AppError("already_submitted", "当前版本已提交合规审核", status_code=409)
        overrides = {"submitted_for_compliance": True, "compliance_decision": "pending"}
    elif request.action in {
        PlanWorkflowAction.COMPLIANCE_APPROVE,
        PlanWorkflowAction.COMPLIANCE_RETURN,
        PlanWorkflowAction.REQUIRE_HUMAN_REVIEW,
    }:
        if not current.submitted_for_compliance:
            raise AppError(
                "compliance_submission_required",
                "客户经理尚未提交当前版本，合规不得提前审核",
                status_code=409,
            )
        evidence = evaluate_compliance(session, current)
        if request.action == PlanWorkflowAction.COMPLIANCE_APPROVE:
            if evidence.blocked_codes:
                raise AppError(
                    "compliance_blocked",
                    "当前方案命中阻断规则，不能审核通过",
                    status_code=409,
                    details={"blocked_codes": evidence.blocked_codes},
                )
            if (
                current.requires_human_review or evidence.warning_codes
            ) and not request.human_review_completed:
                raise AppError(
                    "human_review_required",
                    "当前方案存在人工复核要求，完成并记录后方可通过",
                    status_code=409,
                    details={"warning_codes": evidence.warning_codes},
                )
            next_state = PlanWorkflowState.COMPLIANCE_REVIEWED
            overrides = {
                "compliance_decision": "approved",
                "requires_human_review": False,
                "suitability_snapshot": {
                    **current.suitability_snapshot,
                    "compliance_evidence": evidence.model_dump(mode="json"),
                    "compliance_note": request.compliance_note or request.reason,
                },
            }
        elif request.action == PlanWorkflowAction.COMPLIANCE_RETURN:
            next_state = PlanWorkflowState.DRAFT
            next_cycle += 1
            overrides = {
                "selected_candidate": None,
                "recommendation_snapshot": {
                    "returned_from_version_id": current.id,
                    "return_reason": request.compliance_note or request.reason,
                },
                "suitability_snapshot": {"return_evidence": evidence.model_dump(mode="json")},
                "communication_draft": current.communication_draft,
                "advisor_decision": None,
                "compliance_decision": "returned",
                "customer_confirmation": {},
                "submitted_for_compliance": False,
                "requires_human_review": False,
                "input_version": "pending_recalculation",
                "rule_version": current.rule_version,
            }
        else:
            overrides = {
                "compliance_decision": "human_review_required",
                "requires_human_review": True,
                "suitability_snapshot": {
                    **current.suitability_snapshot,
                    "compliance_evidence": evidence.model_dump(mode="json"),
                    "human_review_reason": request.compliance_note or request.reason,
                },
            }
    elif request.action == PlanWorkflowAction.CUSTOMER_CONFIRM:
        now = utc_now()
        assert request.customer_name is not None
        confirmation = {
            "signature_status": "confirmed",
            "signature_mode": "demo_typed_signature",
            "signer_hash": hashlib.sha256(request.customer_name.encode("utf-8")).hexdigest(),
            "signer_hint": f"{request.customer_name[0]}***",
            "acknowledgements": sorted(request.acknowledgements),
            "confirmed_at": now.isoformat(),
            "legal_signature": False,
        }
        overrides = {"customer_confirmation": confirmation}
        next_state = PlanWorkflowState.CUSTOMER_CONFIRMED
    elif request.action == PlanWorkflowAction.ACTIVATE:
        if current.customer_confirmation.get("signature_status") != "confirmed":
            raise AppError(
                "customer_confirmation_required",
                "客户尚未完成逐项确认，方案不能激活",
                status_code=409,
            )
        next_state = PlanWorkflowState.ACTIVE
    elif request.action == PlanWorkflowAction.SUPERSEDE:
        next_state = PlanWorkflowState.SUPERSEDED
        overrides = {
            "recommendation_snapshot": {
                **current.recommendation_snapshot,
                "replacement_workflow_id": request.replacement_workflow_id,
            }
        }

    version = _new_version(
        session,
        household_id=current.household_id,
        workflow_id=current.workflow_id,
        sequence=current.sequence + 1,
        cycle=next_cycle,
        prior=current,
        state=next_state,
        action=request.action,
        reason=request.reason,
        actor=actor,
        request_id=request_id,
        overrides=overrides,
    )
    if request.action in {
        PlanWorkflowAction.ADVISOR_REVIEW,
        PlanWorkflowAction.REVISE_ADVICE,
    }:
        session.add(
            AdvisorReview(
                household_id=current.household_id,
                report_id=None,
                advisor_id=actor.actor_id,
                decision="manually_reviewed",
                comments=request.advisor_note or request.reason,
                reviewed_at=version.created_at,
                data_source=WORKFLOW_ENGINE_VERSION,
                is_user_confirmed=True,
            )
        )
    if request.action == PlanWorkflowAction.CUSTOMER_CONFIRM:
        session.add(
            CustomerConfirmation(
                household_id=current.household_id,
                report_id=None,
                member_id=None,
                confirmation_type="plan_workflow_demo_signature",
                confirmed_at=version.created_at,
                confirmation_version=version.after_hash,
                evidence={
                    **version.customer_confirmation,
                    "workflow_id": version.workflow_id,
                    "version_id": version.id,
                },
                data_source=WORKFLOW_ENGINE_VERSION,
                is_user_confirmed=True,
            )
        )
    _commit(session)
    session.refresh(version)
    return _response(session, version, actor)


def get_compliance_evidence(
    session: Session,
    workflow_id: str,
    actor: ActorContext,
) -> ComplianceEvidence:
    require_roles(actor, ("advisor", "compliance", "admin"))
    current = _current_version(session, workflow_id)
    require_household_access(actor, current.household_id)
    if current.state not in {
        PlanWorkflowState.ADVISOR_REVIEWED,
        PlanWorkflowState.COMPLIANCE_REVIEWED,
        PlanWorkflowState.CUSTOMER_CONFIRMED,
        PlanWorkflowState.ACTIVE,
        PlanWorkflowState.SUPERSEDED,
    }:
        raise AppError(
            "workflow_not_ready_for_compliance",
            "方案尚未完成客户经理审核，暂无可复核证据",
            status_code=409,
        )
    return evaluate_compliance(session, current)


def _summary(
    session: Session,
    household: Household,
    *,
    analysis_date: date,
) -> AdvisorHouseholdSummary:
    settings = get_settings()
    analysis = analyze_household(
        session,
        household.id,
        settings.financial_rules_path,
        analysis_date,
    )
    planning = plan_household(
        session,
        household.id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        analysis_date,
    )
    workflow = _latest_household_version(session, household.id)
    severities = [str(item.severity) for item in analysis.diagnostics.issues]
    rank = {"normal": 0, "attention": 1, "warning": 2, "critical": 3, "info": 0}
    highest = max(severities or ["normal"], key=lambda item: rank[str(item)])
    signature_status = "not_ready"
    if workflow is not None:
        if workflow.state == PlanWorkflowState.COMPLIANCE_REVIEWED:
            signature_status = "pending"
        elif workflow.state == PlanWorkflowState.CUSTOMER_CONFIRMED:
            signature_status = "confirmed"
        elif workflow.state in {PlanWorkflowState.ACTIVE, PlanWorkflowState.SUPERSEDED}:
            signature_status = "active"
    return AdvisorHouseholdSummary.model_validate(
        {
            "household_id": household.id,
            "household_code": household.code,
            "household_name": household.name,
            "lifecycle_stage": household.lifecycle_stage.value,
            "region": household.region,
            "data_as_of": analysis.meta.data_as_of,
            "net_worth": analysis.statements.balance_sheet.net_worth,
            "annual_surplus": analysis.statements.cash_flow.annual_surplus,
            "anomaly_count": analysis.diagnostics.issue_count,
            "goal_conflict_count": len(planning.conflicts),
            "highest_attention": "normal" if highest == "info" else highest,
            "workflow_id": workflow.workflow_id if workflow is not None else None,
            "workflow_state": workflow.state if workflow is not None else None,
            "workflow_version": workflow.sequence if workflow is not None else None,
            "signature_status": signature_status,
            "synthetic_data": household.is_synthetic,
        }
    )


def build_advisor_household_list(
    session: Session,
    actor: ActorContext,
) -> AdvisorHouseholdList:
    require_roles(actor, ADVISOR_ROLES)
    statement = select(Household).where(Household.is_deleted.is_(False))
    if actor.role != "admin" and "*" not in actor.household_ids:
        statement = statement.where(Household.id.in_(actor.household_ids))
    households = list(session.scalars(statement.order_by(Household.code)).all())
    today = date.today()
    return AdvisorHouseholdList(
        generated_at=utc_now(),
        items=[_summary(session, item, analysis_date=today) for item in households],
    )


def _product_reasons(candidate: dict[str, Any]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for mapping in candidate.get("product_mappings", []):
        if not isinstance(mapping, dict):
            continue
        product_type = str(mapping.get("product_type", "未匹配产品类型"))
        if product_type in seen:
            continue
        seen.add(product_type)
        reasons = mapping.get("reasons", [])
        results.append(f"{product_type}：{'；'.join(str(item) for item in reasons[:2])}")
    return results


def build_advisor_dossier(
    session: Session,
    household_id: str,
    actor: ActorContext,
) -> AdvisorDossier:
    require_roles(actor, ADVISOR_ROLES)
    require_household_access(actor, household_id)
    household = ensure_household(session, household_id)
    settings = get_settings()
    today = date.today()
    analysis = analyze_household(session, household_id, settings.financial_rules_path, today)
    planning = plan_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        today,
    )
    portfolio = portfolio_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        today,
        MarketScenario.NEUTRAL,
    )
    experience = build_client_experience(
        session,
        household_id,
        financial_rules_path=settings.financial_rules_path,
        planning_rules_path=settings.planning_rules_path,
        knowledge_path=settings.knowledge_base_path,
        analysis_date=today,
    )
    candidates: list[AdvisorCandidateSummary] = []
    for item in portfolio.candidates:
        raw = item.model_dump(mode="json")
        candidates.append(
            AdvisorCandidateSummary(
                candidate_type=item.candidate_type,
                name=item.name,
                decision=item.decision,
                investment_amount=item.investment_amount,
                expected_nominal_return=item.expected_nominal_return,
                max_drawdown_estimate=item.max_drawdown_estimate,
                extreme_loss_amount=item.extreme_loss_amount,
                liquidity_score=item.liquidity_score,
                annual_fee_estimate=item.annual_fee_estimate,
                product_type_reasons=_product_reasons(raw),
                primary_risks=item.primary_risks,
            )
        )
    balanced = next(
        item
        for item in portfolio.candidates
        if item.candidate_type == PortfolioCandidateType.BALANCED
    )
    monthly = next(group for group in experience.action_calendar if group.code == "next_12_months")
    questions = ["请客户确认授权范围、家庭成员责任与数据日是否仍然有效。"]
    questions.extend(item.action for item in analysis.diagnostics.issues[:3])
    questions.extend(
        f"目标冲突：{item.title}，是否接受调整期限、金额或月度投入?"
        for item in planning.conflicts[:2]
    )
    return AdvisorDossier(
        generated_at=utc_now(),
        household=_summary(session, household, analysis_date=today),
        members=[item.model_dump(mode="json") for item in analysis.profile.members],
        premeeting_questions=questions,
        financial_anomalies=[item.model_dump(mode="json") for item in analysis.diagnostics.issues],
        goal_conflicts=[item.model_dump(mode="json") for item in planning.conflicts],
        candidates=candidates,
        risk_and_liquidity_notes=[
            portfolio.family_safety_gate.explanation,
            portfolio.customer_suitability_gate.explanation,
            balanced.liquidity_description,
            balanced.rebalancing.explanation,
        ],
        suggested_communication_draft=_advisor_template(
            household,
            balanced.model_dump(mode="json"),
        ),
        monthly_review_reminders=[item.model_dump(mode="json") for item in monthly.items],
        mock_bank=build_mock_bank_snapshot(session, household_id, today),
        boundary_note=(
            "沟通稿仅为可编辑 Mock 模板，不能替代客户经理判断；高风险建议必须人工确认。"
        ),
    )


def build_compliance_queue(session: Session, actor: ActorContext) -> ComplianceQueue:
    require_roles(actor, COMPLIANCE_ROLES)
    statement = select(PlanWorkflowVersion).where(
        PlanWorkflowVersion.is_current.is_(True),
        PlanWorkflowVersion.is_deleted.is_(False),
        PlanWorkflowVersion.state.in_(
            [
                PlanWorkflowState.ADVISOR_REVIEWED,
                PlanWorkflowState.COMPLIANCE_REVIEWED,
                PlanWorkflowState.CUSTOMER_CONFIRMED,
                PlanWorkflowState.ACTIVE,
            ]
        ),
    )
    if actor.role != "admin" and "*" not in actor.household_ids:
        statement = statement.where(PlanWorkflowVersion.household_id.in_(actor.household_ids))
    current_versions = list(
        session.scalars(statement.order_by(PlanWorkflowVersion.created_at.desc())).all()
    )
    items: list[ComplianceQueueItem] = []
    for version in current_versions:
        household = ensure_household(session, version.household_id)
        evidence = evaluate_compliance(session, version)
        items.append(
            ComplianceQueueItem(
                workflow_id=version.workflow_id,
                household_id=version.household_id,
                household_code=household.code,
                household_name=household.name,
                version_id=version.id,
                version_number=version.sequence,
                state=version.state,
                submitted_for_compliance=version.submitted_for_compliance,
                requires_human_review=version.requires_human_review,
                selected_candidate=(
                    PortfolioCandidateType(version.selected_candidate)
                    if version.selected_candidate is not None
                    else None
                ),
                created_at=version.created_at,
                blocked_count=len(evidence.blocked_codes),
                warning_count=len(evidence.warning_codes),
                recommendation_reason=version.reason,
            )
        )
    return ComplianceQueue(generated_at=utc_now(), items=items)


def _audit_event_out(event: AuditEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "event_type": event.event_type.value,
        "actor_id": event.actor_id,
        "actor_role": event.actor_role,
        "time": event.occurred_at.isoformat(),
        "action": event.evidence.get("action", event.event_type.value),
        "object": event.evidence.get("object", event.entity_id),
        "before_hash": event.evidence.get("before_hash"),
        "after_hash": event.evidence.get("after_hash"),
        "reason": event.evidence.get("reason", event.summary),
        "rule_version": event.evidence.get("rule_version"),
        "model_version": event.evidence.get("model_version"),
        "request_id": event.evidence.get("request_id"),
        "summary": event.summary,
    }


def _workflow_audits(
    session: Session,
    household_id: str,
    versions: list[PlanWorkflowVersion],
) -> list[AuditEvent]:
    version_ids = {item.id for item in versions}
    workflow_id = versions[0].workflow_id
    events = list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.household_id == household_id)
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        ).all()
    )
    relevant_types = {
        AuditEventType.CONSENT_GRANTED,
        AuditEventType.CONSENT_WITHDRAWN,
        AuditEventType.HALLUCINATION_BLOCKED,
        AuditEventType.MOCK_BANK_DATA_ACCESSED,
    }
    relevant: list[AuditEvent] = []
    for event in events:
        object_evidence = event.evidence.get("object", {})
        evidence_workflow_id = (
            object_evidence.get("workflow_id") if isinstance(object_evidence, dict) else None
        )
        if (
            event.entity_id in version_ids
            or event.event_type in relevant_types
            or evidence_workflow_id == workflow_id
        ):
            relevant.append(event)
    return relevant


def build_audit_package(
    session: Session,
    workflow_id: str,
    actor: ActorContext,
    request_id: str,
    *,
    record_export: bool = True,
) -> WorkflowAuditPackage:
    require_roles(actor, COMPLIANCE_ROLES)
    versions = _workflow_versions(session, workflow_id)
    if not versions:
        raise AppError("workflow_not_found", "方案审核流不存在", status_code=404)
    require_household_access(actor, versions[0].household_id)
    events = _workflow_audits(session, versions[0].household_id, versions)
    version_payloads = [_to_out(item) for item in versions]
    audit_payloads = [_audit_event_out(item) for item in events]
    hash_chain_verified = _hash_chain_verified(versions)
    package_material = {
        "package_version": "workflow-audit-package-v1.0.0",
        "workflow_id": workflow_id,
        "household_id": versions[0].household_id,
        "version_hashes": [item.after_hash for item in versions],
        "audit_event_ids": [item.id for item in events],
        "hash_chain_verified": hash_chain_verified,
    }
    package_hash = _json_hash(package_material)
    package = WorkflowAuditPackage(
        package_version="workflow-audit-package-v1.0.0",
        generated_at=utc_now(),
        workflow_id=workflow_id,
        household_id=versions[0].household_id,
        versions=version_payloads,
        audit_events=audit_payloads,
        hash_chain_verified=hash_chain_verified,
        package_hash=package_hash,
        exported_by=actor.actor_id,
        exported_role=actor.role,
        request_id=request_id,
        boundary_note="审计包来自当前系统记录，不替代法定档案或生产银行日志。",
    )
    if record_export:
        session.add(
            AuditEvent(
                household_id=versions[0].household_id,
                event_type=AuditEventType.AUDIT_PACKAGE_EXPORTED,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type="PlanWorkflow",
                entity_id=None,
                event_version=versions[-1].sequence,
                summary="导出方案审核审计包",
                evidence={
                    "action": "export_audit_package",
                    "object": {"workflow_id": workflow_id},
                    "package_hash": package_hash,
                    "request_id": request_id,
                    "rule_version": versions[-1].rule_version,
                    "model_version": versions[-1].model_version,
                },
                occurred_at=package.generated_at,
                data_source=WORKFLOW_ENGINE_VERSION,
                is_user_confirmed=True,
            )
        )
        _commit(session)
    return package


def replay_complaint(
    session: Session,
    workflow_id: str,
    request: ComplaintReplayRequest,
    actor: ActorContext,
    request_id: str,
) -> ComplaintReplayResponse:
    require_roles(actor, COMPLIANCE_ROLES)
    versions = _workflow_versions(session, workflow_id)
    if not versions:
        raise AppError("workflow_not_found", "方案审核流不存在", status_code=404)
    require_household_access(actor, versions[0].household_id)
    target = next((item for item in versions if item.id == request.version_id), None)
    if target is None:
        raise AppError(
            "workflow_version_not_found",
            "投诉指定的方案版本不存在",
            status_code=404,
        )
    events = _workflow_audits(session, target.household_id, versions)
    timeline = [
        {
            "version_id": item.id,
            "version_number": item.sequence,
            "state": item.state.value,
            "action": item.action,
            "actor": item.actor_id,
            "role": item.actor_role,
            "time": item.created_at.isoformat(),
            "reason": item.reason,
            "before_hash": item.before_hash,
            "after_hash": item.after_hash,
            "request_id": item.request_id,
            "is_requested_version": item.id == target.id,
        }
        for item in versions
    ]
    event_payloads = [_audit_event_out(item) for item in events]
    package_hash = _json_hash(
        {
            "workflow_id": workflow_id,
            "requested_version_id": request.version_id,
            "timeline": timeline,
            "audit_event_ids": [item.id for item in events],
        }
    )
    replay_event = AuditEvent(
        household_id=target.household_id,
        event_type=AuditEventType.COMPLAINT_REPLAYED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="PlanWorkflow",
        entity_id=target.id,
        event_version=target.sequence,
        summary="回放投诉场景指定方案版本",
        evidence={
            "action": "replay_complaint",
            "object": {
                "workflow_id": workflow_id,
                "version_id": target.id,
            },
            "reason": request.reason,
            "package_hash": package_hash,
            "request_id": request_id,
            "timeline": timeline,
        },
        occurred_at=utc_now(),
        data_source=WORKFLOW_ENGINE_VERSION,
        is_user_confirmed=True,
    )
    session.add(replay_event)
    session.flush()
    response = ComplaintReplayResponse(
        replay_id=replay_event.id,
        workflow_id=workflow_id,
        requested_version_id=request.version_id,
        household_id=target.household_id,
        generated_at=replay_event.occurred_at,
        request_id=request_id,
        timeline=timeline,
        audit_events=event_payloads,
        package_hash=package_hash,
        boundary_note="投诉回放基于不可变版本与审计哈希，不修改任何历史方案。",
    )
    _commit(session)
    return response
