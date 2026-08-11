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
from app.schemas.family_enterprise import (
    EnterpriseCreate,
    EnterpriseCreateResponse,
    EnterpriseExposureCreate,
    EnterpriseExposureResponse,
    EnterpriseProfileOut,
    FamilyEnterpriseView,
)
from app.services.family_enterprise.engine import get_family_enterprise_view
from app.services.family_enterprise.events import process_enterprise_exposures
from app.services.family_enterprise.repository import create_enterprise

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="家企财富暴露分析日")]

router = APIRouter(tags=["v5-family-enterprise"])


def require_family_enterprise_enabled() -> None:
    if not get_settings().enable_v5_family_enterprise:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 家企财富孪生",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_family_enterprise_enabled)]


@router.post(
    "/households/{household_id}/enterprises",
    response_model=EnterpriseCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_enterprise(
    request: Request,
    household_id: str,
    payload: EnterpriseCreate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> EnterpriseCreateResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "create_enterprise")
    enterprise, entity = create_enterprise(session, household_id, payload, actor)
    return EnterpriseCreateResponse(
        enterprise=EnterpriseProfileOut.model_validate(enterprise),
        financial_entity_id=entity.id,
    )


@router.post(
    "/households/{household_id}/enterprise-exposures",
    response_model=EnterpriseExposureResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_enterprise_exposures(
    request: Request,
    household_id: str,
    payload: EnterpriseExposureCreate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> EnterpriseExposureResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "create_enterprise_exposure")
    settings = get_settings()
    return process_enterprise_exposures(
        session,
        household_id,
        payload,
        actor,
        financial_rules_path=settings.financial_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        client_profile_rules_path=settings.client_profile_rules_path,
        liability_rules_path=settings.liability_rules_path,
        family_enterprise_rules_path=settings.family_enterprise_rules_path,
        analysis_date=analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/family-enterprise-view",
    response_model=FamilyEnterpriseView,
)
def read_family_enterprise_view(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> FamilyEnterpriseView:
    settings = get_settings()
    return get_family_enterprise_view(
        session,
        household_id,
        settings.family_enterprise_rules_path,
        analysis_date or date.today(),
    )
