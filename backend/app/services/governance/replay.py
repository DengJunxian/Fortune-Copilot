from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, ActorRole, require_household_access, require_roles
from app.core.errors import AppError
from app.domain.enums import AuditEventType
from app.models.common import utc_now
from app.models.governance import AuditEvent, PlanReport, PlanWorkflowVersion, Recommendation
from app.schemas.decision_evidence_v2 import DecisionEvidenceV2, DecisionReplayResponse
from app.services.governance.evidence import (
    calculate_decision_hash,
    minimal_v2_from_legacy,
)

GOVERNANCE_READ_ROLES: tuple[ActorRole, ...] = ("advisor", "compliance", "admin")


def _workflow_evidence(record: PlanWorkflowVersion) -> DecisionEvidenceV2:
    raw = record.recommendation_snapshot.get("decision_evidence")
    if not isinstance(raw, dict):
        raise AppError(
            "decision_evidence_not_ready",
            "该方案版本尚未运行确定性计算，没有 Decision Evidence V2",
            status_code=409,
        )
    try:
        return DecisionEvidenceV2.model_validate(raw)
    except ValueError as exc:
        raise AppError(
            "decision_evidence_invalid",
            "冻结的决策证据未通过 V2 Schema 校验",
            status_code=409,
        ) from exc


def _recommendation_evidence(record: Recommendation) -> DecisionEvidenceV2:
    raw = record.decision_evidence
    if raw.get("evidence_version") == "decision-evidence-v2.0.0":
        return DecisionEvidenceV2.model_validate(raw)
    return minimal_v2_from_legacy(
        decision_id=record.id,
        decision_type="recommendation",
        household_id=record.household_id,
        legacy=raw,
        suitability=record.suitability_evidence,
        generated_at=record.created_at,
    )


def _report_evidence(record: PlanReport) -> DecisionEvidenceV2:
    raw = record.decision_evidence
    if raw.get("evidence_version") == "decision-evidence-v2.0.0":
        return DecisionEvidenceV2.model_validate(raw)
    legacy = {
        **raw,
        "household_input_version": record.input_version,
        "planning_rule_version": record.planning_rule_version,
        "methodology_version": record.methodology_version,
        "product_snapshot_version": record.product_catalog_version,
    }
    return minimal_v2_from_legacy(
        decision_id=record.id,
        decision_type="plan_report",
        household_id=record.household_id,
        legacy=legacy,
        generated_at=record.generated_at,
    )


def _resolve(
    session: Session,
    decision_id: str,
) -> tuple[DecisionEvidenceV2, str, str]:
    workflow = session.scalar(
        select(PlanWorkflowVersion)
        .where(
            or_(
                PlanWorkflowVersion.id == decision_id,
                (
                    (PlanWorkflowVersion.workflow_id == decision_id)
                    & PlanWorkflowVersion.is_current.is_(True)
                ),
            ),
            PlanWorkflowVersion.is_deleted.is_(False),
        )
        .order_by(PlanWorkflowVersion.sequence.desc())
    )
    if workflow is not None:
        return _workflow_evidence(workflow), workflow.id, workflow.household_id

    recommendation = session.scalar(
        select(Recommendation).where(
            Recommendation.id == decision_id,
            Recommendation.is_deleted.is_(False),
        )
    )
    if recommendation is not None:
        return (
            _recommendation_evidence(recommendation),
            recommendation.id,
            recommendation.household_id,
        )

    report = session.scalar(
        select(PlanReport).where(
            PlanReport.id == decision_id,
            PlanReport.is_deleted.is_(False),
        )
    )
    if report is not None:
        return _report_evidence(report), report.id, report.household_id
    raise AppError("decision_not_found", "找不到该决策或历史版本", status_code=404)


def get_decision_evidence(
    session: Session,
    decision_id: str,
    actor: ActorContext,
) -> DecisionEvidenceV2:
    require_roles(actor, GOVERNANCE_READ_ROLES)
    evidence, _source_id, household_id = _resolve(session, decision_id)
    require_household_access(actor, household_id)
    return evidence


def replay_decision(
    session: Session,
    decision_id: str,
    actor: ActorContext,
    request_id: str,
) -> DecisionReplayResponse:
    require_roles(actor, GOVERNANCE_READ_ROLES)
    evidence, source_id, household_id = _resolve(session, decision_id)
    require_household_access(actor, household_id)
    replay_hash = calculate_decision_hash(evidence)
    identical = replay_hash == evidence.decision_hash
    replayed_at = utc_now()
    response = DecisionReplayResponse(
        decision_id=evidence.decision_id,
        decision_type=evidence.decision_type,
        household_id=evidence.household_id,
        stored_decision_hash=evidence.decision_hash,
        replay_decision_hash=replay_hash,
        hash_identical=identical,
        used_snapshot_versions={
            name: getattr(evidence, name).version
            for name in (
                "household_input",
                "financial_graph",
                "client_profile",
                "wealth_needs",
                "liability",
                "ELTC",
                "risk_budget",
                "enterprise",
                "CFS",
                "product_snapshot",
                "suitability",
                "calibration",
                "advisor",
                "client_confirmation",
            )
        },
        replayed_at=replayed_at,
        evidence=evidence,
    )
    session.add(
        AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.CALCULATION_EXECUTED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="DecisionEvidenceV2Replay",
            entity_id=source_id,
            event_version=1,
            summary="使用冻结快照回放 Decision Evidence V2",
            evidence={
                "decision_id": evidence.decision_id,
                "source_record_id": source_id,
                "stored_decision_hash": evidence.decision_hash,
                "replay_decision_hash": replay_hash,
                "hash_identical": identical,
                "latest_product_data_used": False,
                "request_id": request_id,
            },
            occurred_at=replayed_at,
            data_source="decision-evidence-replay-v2",
            is_user_confirmed=True,
        )
    )
    session.commit()
    return response
