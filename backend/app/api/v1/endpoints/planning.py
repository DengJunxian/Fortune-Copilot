from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.domain.enums import LifecycleStage
from app.schemas.planning import (
    CounterfactualRequest,
    CounterfactualResponse,
    PersistedPlanningRun,
    PlanningResponse,
)
from app.services.planning.engine import (
    compare_counterfactual,
    persist_planning,
    plan_household,
)
from app.services.planning.rules import load_planning_rules

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDate = Annotated[date | None, Query(description="可复现规划日期，默认服务端当天")]
LifecycleOverride = Annotated[
    LifecycleStage | None,
    Query(description="人工覆盖生命周期；只改变参数，不替代目标与约束"),
]

router = APIRouter(tags=["goal-and-account-planning"])


def _planning(
    session: Session,
    household_id: str,
    analysis_date: date | None,
    lifecycle_override: LifecycleStage | None,
) -> PlanningResponse:
    settings = get_settings()
    request = (
        CounterfactualRequest(lifecycle_override=lifecycle_override)
        if lifecycle_override is not None
        else None
    )
    return plan_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        analysis_date or date.today(),
        request,
    )


@router.get(
    "/households/{household_id}/planning",
    response_model=PlanningResponse,
)
def get_planning(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    lifecycle_override: LifecycleOverride = None,
) -> PlanningResponse:
    return _planning(session, household_id, analysis_date, lifecycle_override)


@router.post(
    "/households/{household_id}/planning/counterfactual",
    response_model=CounterfactualResponse,
)
def post_counterfactual(
    household_id: str,
    request: CounterfactualRequest,
    session: SessionDependency,
    _actor: ActorDependency,
) -> CounterfactualResponse:
    settings = get_settings()
    return compare_counterfactual(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        request,
    )


@router.post(
    "/households/{household_id}/planning/runs",
    response_model=PersistedPlanningRun,
    status_code=status.HTTP_201_CREATED,
)
def create_planning_run(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    lifecycle_override: LifecycleOverride = None,
) -> PersistedPlanningRun:
    settings = get_settings()
    plan = _planning(session, household_id, analysis_date, lifecycle_override)
    rules = load_planning_rules(settings.planning_rules_path)
    return persist_planning(session, plan, rules, actor)


@router.get("/households/{household_id}/planning/export")
def export_planning_json(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    lifecycle_override: LifecycleOverride = None,
) -> Response:
    plan = _planning(session, household_id, analysis_date, lifecycle_override)
    return Response(
        content=plan.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="wealthtwin-{plan.meta.household_code.lower()}-planning-'
                f'{plan.meta.analysis_date.isoformat()}.json"'
            )
        },
    )
