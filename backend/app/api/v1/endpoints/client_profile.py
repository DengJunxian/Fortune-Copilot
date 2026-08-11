from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor, require_roles
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.schemas.client_profile import ClientProfileResponse, WealthNeedsResponse
from app.services.client_profile.engine import (
    get_client_profile,
    recalculate_client_profile,
)
from app.services.wealth_needs.engine import (
    get_wealth_needs,
    recalculate_wealth_needs,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["v5-client-profile"])


def require_client_profile_enabled() -> None:
    if not get_settings().enable_v5_client_profile:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 动态客户财富画像",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_client_profile_enabled)]
AnalysisDateQuery = Annotated[date | None, Query(description="画像计算基准日")]


@router.get(
    "/households/{household_id}/client-profile",
    response_model=ClientProfileResponse,
)
def read_client_profile(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> ClientProfileResponse:
    return get_client_profile(session, household_id)


@router.post(
    "/households/{household_id}/client-profile/recalculate",
    response_model=ClientProfileResponse,
)
def post_client_profile_recalculation(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> ClientProfileResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    settings = get_settings()
    return recalculate_client_profile(
        session,
        household_id,
        actor,
        settings.client_profile_rules_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/wealth-needs",
    response_model=WealthNeedsResponse,
)
def read_wealth_needs(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> WealthNeedsResponse:
    return get_wealth_needs(session, household_id)


@router.post(
    "/households/{household_id}/wealth-needs/recalculate",
    response_model=WealthNeedsResponse,
)
def post_wealth_needs_recalculation(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> WealthNeedsResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    settings = get_settings()
    return recalculate_wealth_needs(
        session,
        household_id,
        actor,
        settings.client_profile_rules_path,
        analysis_date or date.today(),
    )
