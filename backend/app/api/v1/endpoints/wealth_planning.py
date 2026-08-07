from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor, require_roles
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.wealth_planning import (
    PlanNarrativeRequest,
    PlanNarrativeResponse,
    PlanningIntakeRequest,
    PlanningIntakeResponse,
    RatioExplanationRequest,
    RatioExplanationResponse,
)
from app.services.financial.engine import analyze_household
from app.services.wealth_planning import (
    compose_plan_narrative,
    create_planning_case,
    explain_financial_ratios,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["wealth-planning-product"])


@router.post(
    "/wealth-planning/cases",
    response_model=PlanningIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case(
    payload: PlanningIntakeRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PlanningIntakeResponse:
    require_roles(actor, ("client", "advisor", "admin"))
    return create_planning_case(session, payload, actor, get_settings())


@router.post(
    "/households/{household_id}/ratio-explanations",
    response_model=RatioExplanationResponse,
)
async def explain_ratios(
    household_id: str,
    payload: RatioExplanationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RatioExplanationResponse:
    require_roles(actor, ("client", "advisor", "admin"))
    settings = get_settings()
    analysis = analyze_household(
        session,
        household_id,
        settings.financial_rules_path,
        date.today(),
    )
    return await explain_financial_ratios(analysis, payload, settings)


@router.post(
    "/households/{household_id}/plan-narrative",
    response_model=PlanNarrativeResponse,
)
async def build_plan_narrative(
    household_id: str,
    payload: PlanNarrativeRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PlanNarrativeResponse:
    require_roles(actor, ("client", "advisor", "admin"))
    return await compose_plan_narrative(
        session,
        household_id,
        payload,
        get_settings(),
    )
