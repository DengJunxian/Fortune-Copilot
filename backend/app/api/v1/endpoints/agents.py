from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor, require_roles
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.schemas.agents import (
    AgentToolRegistryResponse,
    BoundedAgentRunRequest,
    BoundedAgentRunResponse,
)
from app.services.agents.runtime import (
    agent_tool_catalog,
    get_bounded_agent_run,
    run_bounded_agent,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["v5-bounded-financial-agents"])


def require_bounded_agents_enabled() -> None:
    if not get_settings().enable_v5_agents:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 受限金融 Agent",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_bounded_agents_enabled)]


@router.get(
    "/trust/agents/tool-registry",
    response_model=AgentToolRegistryResponse,
)
def get_agent_tool_registry(
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> AgentToolRegistryResponse:
    return agent_tool_catalog()


@router.post(
    "/households/{household_id}/bounded-agent-runs",
    response_model=BoundedAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_bounded_agent_run(
    household_id: str,
    payload: BoundedAgentRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> BoundedAgentRunResponse:
    if payload.agent_code == "advisor_copilot":
        require_roles(actor, {"advisor", "compliance", "admin"})
    else:
        require_roles(actor, {"client", "advisor", "compliance", "admin"})
    return run_bounded_agent(session, household_id, payload, actor, get_settings())


@router.get(
    "/households/{household_id}/bounded-agent-runs/{run_id}",
    response_model=BoundedAgentRunResponse,
)
def read_bounded_agent_run(
    household_id: str,
    run_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> BoundedAgentRunResponse:
    return get_bounded_agent_run(session, household_id, run_id)
