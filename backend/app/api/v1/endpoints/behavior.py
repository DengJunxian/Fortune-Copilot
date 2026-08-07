from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.behavior import (
    BehaviorABFrameworkResponse,
    BehaviorCatalogResponse,
    BehaviorInterventionOut,
    BehaviorOverviewResponse,
    BehaviorSessionOut,
    ExitBehaviorSessionResponse,
    InterventionActionRequest,
    RecordBehaviorResponseRequest,
    StartBehaviorSessionRequest,
)
from app.services.behavior.engine import (
    behavior_ab_framework,
    behavior_catalog,
    behavior_overview,
    complete_behavior_session,
    exit_behavior_session,
    get_behavior_session,
    record_behavior_response,
    start_behavior_session,
    update_intervention,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["behavioral-finance"])


@router.get("/behavior/catalog", response_model=BehaviorCatalogResponse)
def get_behavior_catalog(
    session: SessionDependency,
    _actor: ActorDependency,
) -> BehaviorCatalogResponse:
    return behavior_catalog(session, get_settings().behavior_rules_path)


@router.get("/behavior/ab-framework", response_model=BehaviorABFrameworkResponse)
def get_behavior_ab_framework(
    session: SessionDependency,
    _actor: ActorDependency,
    experiment_key: Annotated[
        str,
        Query(min_length=1, max_length=64),
    ] = "behavior_nudge_main",
) -> BehaviorABFrameworkResponse:
    return behavior_ab_framework(
        session,
        experiment_key,
        get_settings().behavior_rules_path,
    )


@router.get(
    "/households/{household_id}/behavior",
    response_model=BehaviorOverviewResponse,
)
def get_household_behavior(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> BehaviorOverviewResponse:
    return behavior_overview(session, household_id, get_settings().behavior_rules_path)


@router.get("/households/{household_id}/behavior/export")
def export_household_behavior(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> Response:
    result = behavior_overview(session, household_id, get_settings().behavior_rules_path)
    return Response(
        content=result.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="wealthtwin-behavior-{household_id[:8]}.json"'
            )
        },
    )


@router.post(
    "/households/{household_id}/behavior/sessions",
    response_model=BehaviorSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_behavior_session(
    household_id: str,
    request: StartBehaviorSessionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> BehaviorSessionOut:
    return start_behavior_session(
        session,
        household_id,
        request,
        actor,
        get_settings().behavior_rules_path,
    )


@router.get(
    "/households/{household_id}/behavior/sessions/{session_id}",
    response_model=BehaviorSessionOut,
)
def read_behavior_session(
    household_id: str,
    session_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> BehaviorSessionOut:
    return get_behavior_session(
        session,
        household_id,
        session_id,
        get_settings().behavior_rules_path,
    )


@router.post(
    "/households/{household_id}/behavior/sessions/{session_id}/responses/{experiment_code}",
    response_model=BehaviorSessionOut,
)
def submit_behavior_response(
    household_id: str,
    session_id: str,
    experiment_code: str,
    request: RecordBehaviorResponseRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> BehaviorSessionOut:
    return record_behavior_response(
        session,
        household_id,
        session_id,
        experiment_code,
        request,
        actor,
        get_settings().behavior_rules_path,
    )


@router.post(
    "/households/{household_id}/behavior/sessions/{session_id}/complete",
    response_model=BehaviorSessionOut,
)
def complete_household_behavior_session(
    household_id: str,
    session_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> BehaviorSessionOut:
    return complete_behavior_session(
        session,
        household_id,
        session_id,
        actor,
        get_settings().behavior_rules_path,
    )


@router.post(
    "/households/{household_id}/behavior/sessions/{session_id}/exit",
    response_model=ExitBehaviorSessionResponse,
)
def exit_household_behavior_session(
    household_id: str,
    session_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> ExitBehaviorSessionResponse:
    return exit_behavior_session(session, household_id, session_id, actor)


@router.post(
    "/households/{household_id}/behavior/interventions/{intervention_id}/actions",
    response_model=BehaviorInterventionOut,
)
def update_household_behavior_intervention(
    household_id: str,
    intervention_id: str,
    request: InterventionActionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> BehaviorInterventionOut:
    return update_intervention(
        session,
        household_id,
        intervention_id,
        request,
        actor,
    )
