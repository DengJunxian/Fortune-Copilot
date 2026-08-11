from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.auth import (
    ActorContext,
    require_actor,
    require_roles,
    require_sensitive_confirmation,
)
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.schemas.cfs import (
    CFSComposeRequest,
    CFSSolutionResponse,
    ProfessionalReferralCreate,
    ProfessionalReferralOut,
)
from app.services.cfs_composer.engine import (
    compose_cfs_solution,
    create_professional_referral,
    get_cfs_solution,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="CFS 分析日")]

router = APIRouter(tags=["v5-cfs"])


def require_cfs_enabled() -> None:
    if not get_settings().enable_v5_cfs:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 综合财务方案",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_cfs_enabled)]


def _compose(
    session: Session,
    household_id: str,
    payload: CFSComposeRequest,
    actor: ActorContext,
    analysis_date: date,
) -> CFSSolutionResponse:
    settings = get_settings()
    return compose_cfs_solution(
        session,
        household_id,
        payload,
        actor,
        financial_rules_path=settings.financial_rules_path,
        planning_rules_path=settings.planning_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        client_profile_rules_path=settings.client_profile_rules_path,
        liability_rules_path=settings.liability_rules_path,
        family_enterprise_rules_path=settings.family_enterprise_rules_path,
        cfs_rules_path=settings.cfs_rules_path,
        analysis_date=analysis_date,
    )


@router.post(
    "/households/{household_id}/cfs-solutions",
    response_model=CFSSolutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_cfs_solution(
    request: Request,
    household_id: str,
    payload: CFSComposeRequest,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> CFSSolutionResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "create_cfs_solution")
    return _compose(session, household_id, payload, actor, analysis_date or date.today())


@router.get(
    "/households/{household_id}/cfs-solutions/{solution_id}",
    response_model=CFSSolutionResponse,
)
def read_cfs_solution(
    household_id: str,
    solution_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> CFSSolutionResponse:
    return get_cfs_solution(
        session,
        household_id,
        solution_id,
        get_settings().cfs_rules_path,
    )


@router.post(
    "/households/{household_id}/cfs-solutions/{solution_id}/recalculate",
    response_model=CFSSolutionResponse,
)
def recalculate_cfs_solution(
    request: Request,
    household_id: str,
    solution_id: str,
    payload: CFSComposeRequest,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> CFSSolutionResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "recalculate_cfs_solution")
    get_cfs_solution(session, household_id, solution_id, get_settings().cfs_rules_path)
    return _compose(session, household_id, payload, actor, analysis_date or date.today())


@router.post(
    "/households/{household_id}/professional-referrals",
    response_model=ProfessionalReferralOut,
    status_code=status.HTTP_201_CREATED,
)
def post_professional_referral(
    request: Request,
    household_id: str,
    payload: ProfessionalReferralCreate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> ProfessionalReferralOut:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "create_professional_referral")
    return create_professional_referral(session, household_id, payload, actor)
