from __future__ import annotations

from datetime import date
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, create_session_token, verify_session_token
from app.core.config import Settings
from app.core.errors import AppError
from app.core.privacy import stable_hash
from app.domain.enums import AuditEventType
from app.models import Base
from app.models.common import RecordMixin, utc_now
from app.models.family import Household, HouseholdMember
from app.models.governance import AuditEvent
from app.models.security import IdentityAccessGrant, PrivacyRequest
from app.schemas.security import (
    ConsentCatalogResponse,
    ConsentScenario,
    DemoSessionRequest,
    PrivacyDeletionRequest,
    PrivacyRequestOut,
    SessionResponse,
)

CONSENT_CATALOG_VERSION = "privacy-consent-catalog-v1.0.0"
CONSENT_SCENARIOS = (
    ConsentScenario(
        code="core_planning",
        label="基础诊断与目标规划",
        scopes=["profile", "finance", "risk"],
        sensitive=False,
        purpose="形成家庭底表、财务体检和目标规划",
        required_acknowledgement="我理解关键金额由确定性工具计算，授权可撤回。",
    ),
    ConsentScenario(
        code="protection_review",
        label="敏感保障与健康核对",
        scopes=["identity_sensitive", "health_sensitive", "insurance"],
        sensitive=True,
        purpose="核对家庭责任、健康风险和保障缺口",
        required_acknowledgement="我单独同意处理身份、健康与保障敏感字段。",
    ),
    ConsentScenario(
        code="simulation_and_report",
        label="压力模拟与八章报告",
        scopes=["simulation", "report"],
        sensitive=False,
        purpose="运行压力情景并生成带水印的八章规划书",
        required_acknowledgement="我理解模拟不是预测，报告需人工复核。",
    ),
    ConsentScenario(
        code="behavior_experiment",
        label="行为金融问卷与实验",
        scopes=["behavior"],
        sensitive=False,
        purpose="识别行为偏差信号并仅作审慎下调",
        required_acknowledgement="我可随时退出，结果不是临床诊断或监管评级。",
    ),
)


def consent_catalog() -> ConsentCatalogResponse:
    return ConsentCatalogResponse(
        version=CONSENT_CATALOG_VERSION,
        scenarios=list(CONSENT_SCENARIOS),
        minimum_necessary_rule="每个场景只请求完成该场景必需的字段，不以一次授权覆盖未来所有用途。",
        sensitive_data_rule="身份、健康与保障字段必须使用独立记录明示同意，不得由基础授权推定。",
    )


def issue_demo_session(
    session: Session,
    request: DemoSessionRequest,
    settings: Settings,
) -> SessionResponse:
    if not settings.allow_demo_actor_headers:
        raise AppError("demo_session_disabled", "生产环境不提供演示会话签发", status_code=404)
    subject_hash = stable_hash(request.actor_id)
    now = utc_now()
    grants = list(
        session.scalars(
            select(IdentityAccessGrant).where(
                IdentityAccessGrant.actor_subject_hash == subject_hash,
                IdentityAccessGrant.actor_role == request.role,
                IdentityAccessGrant.revoked_at.is_(None),
                or_(
                    IdentityAccessGrant.valid_until.is_(None),
                    IdentityAccessGrant.valid_until > now,
                ),
                IdentityAccessGrant.is_deleted.is_(False),
            )
        ).all()
    )
    if not grants:
        raise AppError("demo_grant_not_found", "演示账号没有家庭访问授权", status_code=403)
    household_ids = sorted({item.household_id for item in grants})
    token = create_session_token(request.actor_id, request.role, household_ids, settings=settings)
    actor = verify_session_token(token, settings=settings)
    return SessionResponse(
        access_token=token,
        actor_id=actor.actor_id,
        role=actor.role,
        household_ids=list(actor.household_ids),
        issued_at=actor.issued_at,
        expires_at=actor.expires_at,
    )


def _privacy_out(record: PrivacyRequest) -> PrivacyRequestOut:
    request_type = "export" if record.request_type == "export" else "erase"
    status = "completed" if record.status == "completed" else "rejected"
    return PrivacyRequestOut(
        request_id=record.id,
        household_id=record.household_id,
        request_type=request_type,
        status=status,
        scope=record.scope,
        confirmation_method=record.confirmation_method,
        completed_at=record.completed_at,
        result_summary=record.result_summary,
        boundary_note=(
            "隐私请求只保留不可逆摘要、范围、状态和必要审计证据；原因正文不进入日志或审计包。"
        ),
    )


def record_privacy_export(
    session: Session,
    household: Household,
    actor: ActorContext,
    *,
    reason: str,
    exported_sections: list[str],
) -> PrivacyRequestOut:
    now = utc_now()
    record = PrivacyRequest(
        household_id=household.id,
        household_ref_hash=stable_hash(household.id),
        request_type="export",
        status="completed",
        scope=exported_sections,
        reason_hash=stable_hash(reason),
        requested_by_hash=stable_hash(actor.actor_id),
        confirmation_method="session_plus_explicit_action_header",
        result_summary={"exported_section_count": len(exported_sections), "format": "json"},
        completed_at=now,
        currency="CNY",
        valuation_date=date.today(),
        data_source="privacy_service",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    session.add(
        AuditEvent(
            household_id=household.id,
            event_type=AuditEventType.PRIVACY_DATA_EXPORTED,
            actor_id=stable_hash(actor.actor_id)[:16],
            actor_role=actor.role,
            entity_type="PrivacyRequest",
            entity_id=record.id,
            event_version=record.version,
            summary="完成客户数据导出",
            evidence={
                "scope": exported_sections,
                "reason_hash": record.reason_hash,
                "payload_values_logged": False,
            },
            occurred_at=now,
            data_source="privacy_service",
            is_user_confirmed=True,
        )
    )
    session.commit()
    session.refresh(record)
    return _privacy_out(record)


def erase_household_data(
    session: Session,
    household: Household,
    request: PrivacyDeletionRequest,
    actor: ActorContext,
) -> PrivacyRequestOut:
    if household.version != request.expected_version:
        raise AppError(
            "version_conflict",
            "家庭记录已变化，请刷新后重新确认",
            status_code=409,
            details={"expected": request.expected_version, "current": household.version},
        )
    if request.household_code_confirmation != household.code:
        raise AppError("deletion_confirmation_mismatch", "家庭代码确认不一致", status_code=409)

    now = utc_now()
    privacy_record = PrivacyRequest(
        household_id=household.id,
        household_ref_hash=stable_hash(household.id),
        request_type="erase",
        status="completed",
        scope=["identity", "financial", "behavior", "model", "report"],
        reason_hash=stable_hash(request.reason),
        requested_by_hash=stable_hash(actor.actor_id),
        confirmation_method="session_plus_action_header_plus_household_code",
        result_summary={},
        completed_at=now,
        currency="CNY",
        valuation_date=date.today(),
        data_source="privacy_service",
        is_user_confirmed=True,
    )
    session.add(privacy_record)
    session.flush()

    affected = 0
    # Keep privacy/audit tombstones, but make all household-domain records
    # inaccessible and strip the direct identity fields from member records.
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if model in {Household, AuditEvent, PrivacyRequest}:
            continue
        if not hasattr(model, "household_id") or not hasattr(model, "is_deleted"):
            continue
        rows: list[Any] = list(
            session.scalars(
                select(model).where(
                    cast(Any, model).household_id == household.id,
                    cast(Any, model).is_deleted.is_(False),
                )
            ).all()
        )
        for row in rows:
            record = cast(RecordMixin, row)
            record.is_deleted = True
            record.deleted_at = now
            record.updated_at = now
            record.version += 1
            if isinstance(record, HouseholdMember):
                record.display_name = "[已删除]"
                record.occupation = None
                record.birth_date = date(1900, 1, 1)
            affected += 1

    # Existing audit rows remain as minimal integrity evidence, detached from
    # the household and with actor/payload details pseudonymized.
    audits = list(
        session.scalars(select(AuditEvent).where(AuditEvent.household_id == household.id)).all()
    )
    for audit in audits:
        audit.actor_id = stable_hash(audit.actor_id)[:16]
        audit.evidence = {
            "redacted_after_erasure": True,
            "original_event_type": audit.event_type.value,
        }
        audit.household_id = None

    household_ref = stable_hash(household.id)[:12]
    household.code = f"ERASED_{household_ref}"[:32]
    household.name = "[已删除家庭]"
    household.region = "[已删除]"
    household.demo_profile = None
    household.is_deleted = True
    household.deleted_at = now
    household.updated_at = now
    household.version += 1

    privacy_record.household_id = None
    privacy_record.result_summary = {
        "logical_records_erased": affected,
        "audit_rows_redacted": len(audits),
        "direct_identity_fields_anonymized": True,
        "physical_backup_expiry": "由部署方保留策略执行；竞赛版不声称即时擦除备份",
    }
    session.add(
        AuditEvent(
            household_id=None,
            event_type=AuditEventType.PRIVACY_DATA_ERASED,
            actor_id=stable_hash(actor.actor_id)[:16],
            actor_role=actor.role,
            entity_type="PrivacyRequest",
            entity_id=privacy_record.id,
            event_version=privacy_record.version,
            summary="完成家庭数据逻辑擦除与身份去标识",
            evidence={
                "household_ref_hash": privacy_record.household_ref_hash,
                "logical_records_erased": affected,
                "audit_rows_redacted": len(audits),
            },
            occurred_at=now,
            data_source="privacy_service",
            is_user_confirmed=True,
        )
    )
    session.commit()
    session.refresh(privacy_record)
    return _privacy_out(privacy_record)
