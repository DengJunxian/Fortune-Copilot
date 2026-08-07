from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.twin import ScenarioCatalogResponse, TwinRunRequest, TwinRunStatusResponse
from app.services.twin.engine import (
    advance_twin_run,
    cancel_twin_run,
    export_twin_result,
    get_twin_run,
    scenario_catalog,
    start_twin_run,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["wealth-digital-twin"])


@router.get("/twin/scenarios", response_model=ScenarioCatalogResponse)
def get_twin_scenarios(
    session: SessionDependency,
    _actor: ActorDependency,
) -> ScenarioCatalogResponse:
    return scenario_catalog(session, get_settings().twin_rules_path)


@router.post(
    "/households/{household_id}/twin/runs",
    response_model=TwinRunStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_twin_run(
    household_id: str,
    request: TwinRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> TwinRunStatusResponse:
    settings = get_settings()
    return start_twin_run(
        session,
        household_id,
        request,
        actor,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.twin_rules_path,
    )


@router.post(
    "/households/{household_id}/twin/runs/{run_id}/advance",
    response_model=TwinRunStatusResponse,
)
def advance_twin_run_step(
    household_id: str,
    run_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> TwinRunStatusResponse:
    return advance_twin_run(
        session,
        household_id,
        run_id,
        actor,
        get_settings().twin_rules_path,
    )


@router.get(
    "/households/{household_id}/twin/runs/{run_id}",
    response_model=TwinRunStatusResponse,
)
def read_twin_run(
    household_id: str,
    run_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> TwinRunStatusResponse:
    return get_twin_run(session, household_id, run_id)


@router.post(
    "/households/{household_id}/twin/runs/{run_id}/cancel",
    response_model=TwinRunStatusResponse,
)
def cancel_twin_run_step(
    household_id: str,
    run_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> TwinRunStatusResponse:
    return cancel_twin_run(session, household_id, run_id, actor)


@router.get("/households/{household_id}/twin/runs/{run_id}/export")
def export_twin_json(
    household_id: str,
    run_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> Response:
    result = export_twin_result(session, household_id, run_id)
    return Response(
        content=result.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="wealthtwin-{result.meta.household_code.lower()}-'
                f'twin-{result.meta.analysis_date.isoformat()}.json"'
            )
        },
    )
