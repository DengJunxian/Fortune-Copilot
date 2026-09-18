from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.auth import ActorContext, require_actor, require_roles
from app.schemas.competition import CompetitionDemoResponse
from app.services.competition.benchmark import run_competition_benchmark
from app.services.competition.engine import build_competition_demo

ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(prefix="/competition", tags=["competition-cfs"])


@router.get("/demo", response_model=CompetitionDemoResponse)
def get_competition_demo(actor: ActorDependency) -> CompetitionDemoResponse:
    require_roles(actor, ("client", "advisor", "compliance", "admin"))
    return build_competition_demo()


@router.post("/benchmark", response_model=dict[str, Any])
def post_competition_benchmark(actor: ActorDependency) -> dict[str, Any]:
    require_roles(actor, ("compliance", "admin"))
    return run_competition_benchmark()
