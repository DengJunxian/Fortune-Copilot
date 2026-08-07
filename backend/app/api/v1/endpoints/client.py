from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor, require_roles
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.schemas.client_experience import (
    ClientExperienceResponse,
    ConsentWithdrawRequest,
    HumanReviewRequest,
    HumanReviewResponse,
    PrivacyConsentItem,
)
from app.services.client_experience import (
    build_client_data_export,
    build_client_experience,
    request_human_review,
    withdraw_consent,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDate = Annotated[date | None, Query(description="可复现客户端体验日期")]

router = APIRouter(tags=["client-experience"])


@router.get(
    "/households/{household_id}/client-experience",
    response_model=ClientExperienceResponse,
)
def get_client_experience(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> ClientExperienceResponse:
    settings = get_settings()
    return build_client_experience(
        session,
        household_id,
        financial_rules_path=settings.financial_rules_path,
        planning_rules_path=settings.planning_rules_path,
        knowledge_path=settings.knowledge_base_path,
        analysis_date=analysis_date or date.today(),
    )


@router.get("/households/{household_id}/client-experience/export")
def export_client_experience(
    request_context: Request,
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> Response:
    settings = get_settings()
    if settings.is_production:
        raise AppError(
            "legacy_export_disabled",
            "生产环境请使用带二次确认和审计的隐私导出接口",
            status_code=410,
        )
    package = build_client_data_export(
        session,
        household_id,
        financial_rules_path=settings.financial_rules_path,
        planning_rules_path=settings.planning_rules_path,
        knowledge_path=settings.knowledge_base_path,
        analysis_date=analysis_date or date.today(),
    )
    return Response(
        content=package.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                'attachment; filename="wealthtwin-'
                f"{package.client_experience.household_code.lower()}-"
                f'client-data-{package.client_experience.analysis_date.isoformat()}.json"'
            )
        },
    )


@router.post(
    "/households/{household_id}/privacy/consents/{consent_id}/withdraw",
    response_model=PrivacyConsentItem,
)
def post_withdraw_consent(
    household_id: str,
    consent_id: str,
    request: ConsentWithdrawRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PrivacyConsentItem:
    require_roles(actor, ("client", "admin"))
    return withdraw_consent(session, household_id, consent_id, request, actor)


@router.post(
    "/households/{household_id}/privacy/human-review-requests",
    response_model=HumanReviewResponse,
)
def post_human_review_request(
    household_id: str,
    request: HumanReviewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> HumanReviewResponse:
    require_roles(actor, ("client", "admin"))
    return request_human_review(session, household_id, request, actor)
