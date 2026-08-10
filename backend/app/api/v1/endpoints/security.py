from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import (
    ActorContext,
    require_actor,
    require_roles,
    require_sensitive_confirmation,
)
from app.core.config import get_settings
from app.core.database import get_session
from app.core.privacy import stable_hash
from app.schemas.security import (
    ConsentCatalogResponse,
    DemoSessionRequest,
    EvaluationResponse,
    FileInspectionResponse,
    ModelGovernanceEvaluationRequest,
    ModelGovernanceEvaluationResponse,
    ModelRunListResponse,
    PrivacyDeletionRequest,
    PrivacyExportRequest,
    PrivacyExportResponse,
    PrivacyRequestOut,
    PublishReportRequest,
    PublishReportResponse,
    QualityGateEvaluateRequest,
    QualityGateResponse,
    SecurityDashboardResponse,
    SessionResponse,
)
from app.services.client_experience import build_client_data_export
from app.services.crud import ensure_household
from app.services.security.evaluation import run_adversarial_evaluation, security_dashboard
from app.services.security.model_governance import evaluate_model_governance
from app.services.security.model_risk import list_model_runs
from app.services.security.privacy import (
    consent_catalog,
    erase_household_data,
    issue_demo_session,
    record_privacy_export,
)
from app.services.security.quality_gate import evaluate_quality_gate, publish_report
from app.services.security.uploads import inspect_uploaded_document

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["security-privacy-quality"])


@router.post("/security/demo-sessions", response_model=SessionResponse)
def post_demo_session(
    request: DemoSessionRequest,
    session: SessionDependency,
) -> SessionResponse:
    return issue_demo_session(session, request, get_settings())


@router.get("/security/privacy/consent-catalog", response_model=ConsentCatalogResponse)
def get_consent_catalog() -> ConsentCatalogResponse:
    return consent_catalog()


@router.post(
    "/households/{household_id}/privacy/exports",
    response_model=PrivacyExportResponse,
)
def post_privacy_export(
    request_context: Request,
    household_id: str,
    payload: PrivacyExportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PrivacyExportResponse:
    require_roles(actor, ("client", "admin"))
    require_sensitive_confirmation(request_context, "export_household_data")
    settings = get_settings()
    household = ensure_household(session, household_id)
    package = build_client_data_export(
        session,
        household_id,
        financial_rules_path=settings.financial_rules_path,
        planning_rules_path=settings.planning_rules_path,
        knowledge_path=settings.knowledge_base_path,
        analysis_date=date.today(),
    )
    exported_sections = ["financial_analysis", "planning", "client_experience"]
    privacy_request = record_privacy_export(
        session,
        household,
        actor,
        reason=payload.reason,
        exported_sections=exported_sections,
    )
    return PrivacyExportResponse(
        request=privacy_request,
        package_version=package.package_version,
        exported_at=package.exported_at,
        household_ref=stable_hash(household_id)[:16],
        data=package.model_dump(mode="json"),
        boundary_note=(
            "导出只包含当前授权家庭；身份与财务对象通过家庭引用关联，信用卡额度不会计入资产。"
        ),
    )


@router.post(
    "/households/{household_id}/privacy/deletion-requests",
    response_model=PrivacyRequestOut,
)
def post_privacy_deletion(
    request_context: Request,
    household_id: str,
    payload: PrivacyDeletionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PrivacyRequestOut:
    require_roles(actor, ("client", "admin"))
    require_sensitive_confirmation(request_context, "erase_household_data")
    household = ensure_household(session, household_id)
    return erase_household_data(session, household, payload, actor)


@router.post("/security/document-inspections", response_model=FileInspectionResponse)
async def post_document_inspection(
    upload: Annotated[UploadFile, File(description="UTF-8 TXT, Markdown or JSON; not persisted")],
    session: SessionDependency,
    actor: ActorDependency,
) -> FileInspectionResponse:
    require_roles(actor, ("client", "advisor", "compliance", "admin"))
    return await inspect_uploaded_document(
        session,
        upload,
        actor,
        max_bytes=get_settings().max_upload_bytes,
    )


@router.post("/security/evaluations/run", response_model=EvaluationResponse)
def post_security_evaluation(
    session: SessionDependency,
    actor: ActorDependency,
) -> EvaluationResponse:
    require_roles(actor, ("compliance", "admin"))
    return run_adversarial_evaluation(session, actor, get_settings())


@router.get("/security/dashboard", response_model=SecurityDashboardResponse)
def get_security_dashboard(
    session: SessionDependency,
    actor: ActorDependency,
) -> SecurityDashboardResponse:
    require_roles(actor, ("compliance", "admin"))
    return security_dashboard(session)


@router.get("/security/model-runs", response_model=ModelRunListResponse)
def get_model_runs(
    session: SessionDependency,
    actor: ActorDependency,
) -> ModelRunListResponse:
    require_roles(actor, ("compliance", "admin"))
    return list_model_runs(session)


@router.post(
    "/security/model-governance/evaluate",
    response_model=ModelGovernanceEvaluationResponse,
)
def post_model_governance_evaluation(
    payload: ModelGovernanceEvaluationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ModelGovernanceEvaluationResponse:
    require_roles(actor, ("compliance", "admin"))
    response = evaluate_model_governance(session, payload, actor)
    session.commit()
    return response


@router.post("/reports/{report_id}/quality-gate", response_model=QualityGateResponse)
def post_report_quality_gate(
    report_id: str,
    payload: QualityGateEvaluateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> QualityGateResponse:
    require_roles(actor, ("compliance", "admin"))
    _record, response = evaluate_quality_gate(
        session,
        report_id,
        actor,
        get_settings(),
        human_review_completed=payload.human_review_completed,
        reason=payload.reason,
    )
    session.commit()
    return response


@router.post("/reports/{report_id}/publish", response_model=PublishReportResponse)
def post_report_publish(
    request_context: Request,
    report_id: str,
    payload: PublishReportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PublishReportResponse:
    require_roles(actor, ("compliance", "admin"))
    require_sensitive_confirmation(request_context, "publish_report")
    return publish_report(session, report_id, payload, actor, get_settings())
