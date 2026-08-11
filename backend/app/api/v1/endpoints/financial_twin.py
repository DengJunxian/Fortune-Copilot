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
from app.schemas.financial_twin import (
    EventTimelineResponse,
    HouseholdSnapshotOut,
    LifeEventCreate,
    LifeEventProcessResponse,
    WealthTwinResponse,
)
from app.services.financial_twin.engine import (
    get_or_build_wealth_twin,
    get_snapshot_response,
)
from app.services.financial_twin.events import event_timeline, process_life_event

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="持久财富孪生分析日")]

router = APIRouter(tags=["v5-persistent-financial-twin"])


def require_persistent_twin_enabled() -> None:
    if not get_settings().enable_v5_persistent_twin:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 持久家庭财富孪生",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_persistent_twin_enabled)]


@router.get(
    "/households/{household_id}/wealth-twin",
    response_model=WealthTwinResponse,
)
def read_wealth_twin(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> WealthTwinResponse:
    settings = get_settings()
    return get_or_build_wealth_twin(
        session,
        household_id,
        actor,
        financial_rules_path=settings.financial_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        client_profile_rules_path=settings.client_profile_rules_path,
        liability_rules_path=settings.liability_rules_path,
        family_enterprise_rules_path=settings.family_enterprise_rules_path,
        analysis_date=analysis_date or date.today(),
    )


@router.post(
    "/households/{household_id}/life-events",
    response_model=LifeEventProcessResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_life_event(
    request: Request,
    household_id: str,
    payload: LifeEventCreate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> LifeEventProcessResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "create_life_event")
    settings = get_settings()
    return process_life_event(
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
    "/households/{household_id}/event-timeline",
    response_model=EventTimelineResponse,
)
def read_event_timeline(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> EventTimelineResponse:
    return event_timeline(session, household_id)


@router.get(
    "/households/{household_id}/wealth-twin/snapshots/{snapshot_id}",
    response_model=HouseholdSnapshotOut,
)
def read_wealth_twin_snapshot(
    household_id: str,
    snapshot_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> HouseholdSnapshotOut:
    return get_snapshot_response(session, household_id, snapshot_id)
