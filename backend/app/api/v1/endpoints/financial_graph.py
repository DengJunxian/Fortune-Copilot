from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
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
from app.schemas.financial_graph import (
    FinancialGraphResponse,
    PositionCreate,
    PositionOut,
    PositionUpdate,
)
from app.services.financial_graph.engine import build_financial_graph, financial_graph_response
from app.services.financial_graph.repository import (
    create_position,
    delete_position,
    update_position,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["v5-financial-graph"])


def require_financial_graph_enabled() -> None:
    if not get_settings().enable_v5_financial_graph:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 家庭金融图",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_financial_graph_enabled)]


@router.get(
    "/households/{household_id}/financial-graph",
    response_model=FinancialGraphResponse,
)
def get_financial_graph(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> FinancialGraphResponse:
    return financial_graph_response(session, household_id, actor)


@router.post(
    "/households/{household_id}/financial-graph/positions",
    response_model=PositionOut,
    status_code=status.HTTP_201_CREATED,
)
def post_financial_graph_position(
    household_id: str,
    payload: PositionCreate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> PositionOut:
    require_roles(actor, {"client", "advisor", "admin"})
    build_financial_graph(session, household_id, actor)
    return PositionOut.model_validate(
        create_position(session, household_id, payload, actor)
    )


@router.patch(
    "/households/{household_id}/financial-graph/positions/{position_id}",
    response_model=PositionOut,
)
def patch_financial_graph_position(
    household_id: str,
    position_id: str,
    payload: PositionUpdate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> PositionOut:
    require_roles(actor, {"client", "advisor", "admin"})
    return PositionOut.model_validate(
        update_position(session, household_id, position_id, payload, actor)
    )


@router.delete(
    "/households/{household_id}/financial-graph/positions/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_financial_graph_position(
    request: Request,
    household_id: str,
    position_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "delete_financial_graph_position")
    delete_position(
        session,
        household_id,
        position_id,
        expected_version=expected_version,
        actor=actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
