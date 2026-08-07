from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_household_access
from app.core.config import Settings
from app.core.errors import AppError
from app.core.privacy import scan_prohibited_language, stable_hash
from app.domain.enums import AuditEventType, SuitabilityDecision, SuitabilityStatus
from app.models.common import utc_now
from app.models.family import ConsentRecord
from app.models.governance import AuditEvent, PlanReport
from app.models.security import QualityGateRun
from app.schemas.formal_report import FormalReportDocument
from app.schemas.security import (
    PublishReportRequest,
    PublishReportResponse,
    QualityGateItem,
    QualityGateResponse,
)
from app.services.portfolio.engine import portfolio_household

QUALITY_GATE_VERSION = "pre-publication-quality-gate-v1.0.0"
QualityGateCode = Literal[
    "data_integrity",
    "calculation",
    "goals",
    "family_safety",
    "customer_suitability",
    "product_suitability",
    "fact_citations",
    "numeric_consistency",
    "prohibited_language",
    "human_review",
]


def _canonical_report_hash(document: FormalReportDocument) -> str:
    payload = document.model_dump(mode="json")
    payload["report_hash"] = "pending"
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _strings(nested)


def _gate(
    code: QualityGateCode,
    label: str,
    passed: bool,
    explanation: str,
    evidence: list[str] | None = None,
) -> QualityGateItem:
    return QualityGateItem(
        code=code,
        label=label,
        status="pass" if passed else "block",
        explanation=explanation,
        evidence=evidence or [],
    )


def _report_record(session: Session, report_id: str) -> PlanReport:
    record = session.scalar(
        select(PlanReport).where(PlanReport.id == report_id, PlanReport.is_deleted.is_(False))
    )
    if record is None:
        raise AppError("report_not_found", "正式规划书不存在", status_code=404)
    return record


def evaluate_quality_gate(
    session: Session,
    report_id: str,
    actor: ActorContext,
    settings: Settings,
    *,
    human_review_completed: bool,
    reason: str,
) -> tuple[QualityGateRun, QualityGateResponse]:
    record = _report_record(session, report_id)
    require_household_access(actor, record.household_id)
    document = FormalReportDocument.model_validate(record.structured_report)
    now = utc_now()
    active_consents = list(
        session.scalars(
            select(ConsentRecord).where(
                ConsentRecord.household_id == record.household_id,
                ConsentRecord.withdrawn_at.is_(None),
                ConsentRecord.is_deleted.is_(False),
            )
        ).all()
    )
    core_consent = any(
        {"profile", "finance", "risk"}.issubset(set(item.scopes)) for item in active_consents
    )
    report_consent = any("report" in item.scopes for item in active_consents)
    hash_ok = _canonical_report_hash(document) == record.report_hash == document.report_hash
    structure_ok = document.chapter_count == 8 and len(document.chapters) == 8 and hash_ok

    deterministic_sources = {
        "deterministic_tools",
        "deterministic_simulation_engine",
        "deterministic_review_schedule",
    }
    numeric_sources_ok = bool(document.numeric_ledger) and all(
        item.calculation_source in deterministic_sources for item in document.numeric_ledger
    )
    calculation_checks_ok = all(
        item.status == "passed"
        for item in document.consistency_checks
        if item.code in {"deterministic_numeric_ledger", "twin_validation"}
    )

    goal_chapter = document.chapters[1]
    goals_ok = goal_chapter.title == "理财目标" and bool(goal_chapter.sections)

    portfolio = portfolio_household(
        session,
        record.household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        document.analysis_date,
    )
    unsafe_decisions = [
        candidate.candidate_type.value
        for candidate in portfolio.candidates
        if candidate.decision == SuitabilityDecision.ALLOW
        and any(gate.status != SuitabilityStatus.PASS for gate in candidate.gates)
    ]
    family_safe = not unsafe_decisions and (
        portfolio.family_safety_gate.status == SuitabilityStatus.PASS
        or all(item.decision != SuitabilityDecision.ALLOW for item in portfolio.candidates)
    )
    customer_safe = not unsafe_decisions and (
        portfolio.customer_suitability_gate.status == SuitabilityStatus.PASS
        or all(item.decision != SuitabilityDecision.ALLOW for item in portfolio.candidates)
    )
    product_safe = not unsafe_decisions and all(
        candidate.decision != SuitabilityDecision.ALLOW
        or all(gate.status == SuitabilityStatus.PASS for gate in candidate.gates)
        for candidate in portfolio.candidates
    )

    citation_ids = {item.citation_id for item in document.citations}
    claimed_citations = {
        citation_id for claim in document.sourced_claims for citation_id in claim.citation_ids
    }
    citations_ok = bool(document.sourced_claims) and claimed_citations <= citation_ids
    report_text = "\n".join(_strings(document.model_dump(mode="json")))
    prohibited = scan_prohibited_language(report_text)
    human_review_ok = human_review_completed and actor.role in {"compliance", "admin"}

    gates = [
        _gate(
            "data_integrity",
            "数据完整性",
            structure_ok and core_consent and report_consent,
            "报告结构、哈希链及场景授权均完整。"
            if structure_ok and core_consent and report_consent
            else "八章结构、哈希或基础/报告授权不完整。",
            [
                f"hash_ok={hash_ok}",
                f"core_consent={core_consent}",
                f"report_consent={report_consent}",
            ],
        ),
        _gate(
            "calculation",
            "计算",
            numeric_sources_ok and calculation_checks_ok,
            "关键数字均来自确定性工具且计算校验通过。"
            if numeric_sources_ok and calculation_checks_ok
            else "数字来源或计算校验未通过。",
            [f"numeric_claims={len(document.numeric_ledger)}"],
        ),
        _gate(
            "goals",
            "目标",
            goals_ok,
            "理财目标章节与目标行动证据存在。" if goals_ok else "目标章节缺失或为空。",
        ),
        _gate(
            "family_safety",
            "家庭安全",
            family_safe,
            "家庭安全闸门的限制已反映到候选决策。"
            if family_safe
            else "存在绕过家庭安全闸门的允许态候选。",
            unsafe_decisions,
        ),
        _gate(
            "customer_suitability",
            "客户适当性",
            customer_safe,
            "客户风险能力限制已反映到候选决策。"
            if customer_safe
            else "存在绕过客户适当性闸门的允许态候选。",
            unsafe_decisions,
        ),
        _gate(
            "product_suitability",
            "产品适当性",
            product_safe,
            "产品期限、流动性、风险和复杂度检查与决策一致。"
            if product_safe
            else "产品检查与允许态决策不一致。",
            unsafe_decisions,
        ),
        _gate(
            "fact_citations",
            "事实引用",
            citations_ok,
            "外部事实均关联受控引用。" if citations_ok else "外部事实引用覆盖不足。",
            sorted(claimed_citations),
        ),
        _gate(
            "numeric_consistency",
            "数值一致性",
            hash_ok and document.consistency_status == "passed",
            "报告哈希与一致性状态通过。"
            if hash_ok and document.consistency_status == "passed"
            else "报告哈希或一致性状态未通过。",
        ),
        _gate(
            "prohibited_language",
            "禁止性表述",
            not prohibited,
            "未发现收益承诺、最低工资/CPI 混同或普通家庭高风险默认推荐。"
            if not prohibited
            else "发现禁止性表述。",
            prohibited,
        ),
        _gate(
            "human_review",
            "人工复核条件",
            human_review_ok,
            (
                "合规角色已记录本次人工复核。"
                if human_review_ok
                else "尚未由合规角色明确记录人工复核。"
            ),
        ),
    ]
    passed = all(item.status == "pass" for item in gates)
    gate_record = QualityGateRun(
        household_id=record.household_id,
        report_id=record.id,
        gate_version=QUALITY_GATE_VERSION,
        environment=settings.app_env,
        passed=passed,
        gate_results=[item.model_dump(mode="json") for item in gates],
        metrics={
            "passed": sum(item.status == "pass" for item in gates),
            "total": len(gates),
            "blocked": sum(item.status == "block" for item in gates),
        },
        evaluated_by_hash=stable_hash(actor.actor_id),
        evaluated_at=now,
        currency="CNY",
        valuation_date=date.today(),
        data_source="deterministic_release_gate",
        is_user_confirmed=True,
    )
    session.add(gate_record)
    session.flush()
    session.add(
        AuditEvent(
            household_id=record.household_id,
            event_type=AuditEventType.QUALITY_GATE_EVALUATED,
            actor_id=stable_hash(actor.actor_id)[:16],
            actor_role=actor.role,
            entity_type="QualityGateRun",
            entity_id=gate_record.id,
            event_version=gate_record.version,
            summary=f"发布质量门禁：{'通过' if passed else '阻断'}",
            evidence={
                "report_id": record.id,
                "passed": passed,
                "blocked_codes": [item.code for item in gates if item.status == "block"],
                "gate_version": QUALITY_GATE_VERSION,
                "reason_hash": stable_hash(reason),
            },
            occurred_at=now,
            data_source="deterministic_release_gate",
            is_user_confirmed=True,
        )
    )
    response = QualityGateResponse(
        gate_run_id=gate_record.id,
        report_id=record.id,
        household_id=record.household_id,
        gate_version=QUALITY_GATE_VERSION,
        environment=settings.app_env,
        passed=passed,
        gates=gates,
        evaluated_at=now,
        boundary_note="门禁是发布前必要条件，不替代持牌人员、银行流程或法律合规复核。",
    )
    return gate_record, response


def publish_report(
    session: Session,
    report_id: str,
    request: PublishReportRequest,
    actor: ActorContext,
    settings: Settings,
) -> PublishReportResponse:
    record = _report_record(session, report_id)
    if record.sequence != request.expected_report_sequence:
        raise AppError(
            "report_version_conflict",
            "报告版本已变化，请刷新后重试",
            status_code=409,
            details={"expected": request.expected_report_sequence, "current": record.sequence},
        )
    gate_record, gate = evaluate_quality_gate(
        session,
        report_id,
        actor,
        settings,
        human_review_completed=request.human_review_completed,
        reason=request.reason,
    )
    if not gate.passed:
        session.commit()
        raise AppError(
            "quality_gate_blocked",
            "报告未通过全部发布质量门禁",
            status_code=409,
            details={
                "gate_run_id": gate.gate_run_id,
                "blocked_codes": [item.code for item in gate.gates if item.status == "block"],
            },
        )
    now = utc_now()
    record.publication_status = "published"
    record.published_at = now
    record.quality_gate_run_id = gate_record.id
    record.version += 1
    session.add(
        AuditEvent(
            household_id=record.household_id,
            event_type=AuditEventType.REPORT_PUBLISHED,
            actor_id=stable_hash(actor.actor_id)[:16],
            actor_role=actor.role,
            entity_type="PlanReport",
            entity_id=record.id,
            event_version=record.version,
            summary="报告通过十项门禁并发布",
            evidence={
                "gate_run_id": gate_record.id,
                "gate_version": QUALITY_GATE_VERSION,
                "reason_hash": stable_hash(request.reason),
                "human_review_completed": request.human_review_completed,
            },
            occurred_at=now,
            data_source="deterministic_release_gate",
            is_user_confirmed=True,
        )
    )
    session.commit()
    return PublishReportResponse(
        report_id=record.id,
        publication_status="published",
        published_at=now,
        gate=gate,
        watermark=str(record.watermark),
        boundary_note="发布仅代表测试环境门禁通过；重大决策仍需真实业务机构人工复核。",
    )
