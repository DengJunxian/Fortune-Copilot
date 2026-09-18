from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.schemas.specialized_cfs import (
    CurrencyExposureResponse,
    PhilanthropyGoalsResponse,
    RetirementPlanResponse,
    TrustSuccessionResponse,
)
from app.services.currency_exposure.engine import get_currency_exposures
from app.services.philanthropy.engine import get_philanthropy_goals
from app.services.retirement.engine import get_retirement_plan
from app.services.trust_succession.engine import get_trust_succession_needs

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="专业 CFS 分析日")]

router = APIRouter(tags=["v5-specialized-cfs"])


def require_specialized_cfs_enabled() -> None:
    if not get_settings().enable_v5_cfs:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 专业财务方案",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_specialized_cfs_enabled)]


@router.get(
    "/households/{household_id}/retirement-plan",
    response_model=RetirementPlanResponse,
)
def read_retirement_plan(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> RetirementPlanResponse:
    return get_retirement_plan(
        session,
        household_id,
        actor,
        get_settings().specialized_cfs_rules_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/currency-exposures",
    response_model=CurrencyExposureResponse,
)
def read_currency_exposures(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> CurrencyExposureResponse:
    return get_currency_exposures(
        session,
        household_id,
        actor,
        get_settings().specialized_cfs_rules_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/trust-succession-needs",
    response_model=TrustSuccessionResponse,
)
def read_trust_succession_needs(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> TrustSuccessionResponse:
    return get_trust_succession_needs(
        session,
        household_id,
        actor,
        get_settings().specialized_cfs_rules_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/philanthropy-goals",
    response_model=PhilanthropyGoalsResponse,
)
def read_philanthropy_goals(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> PhilanthropyGoalsResponse:
    return get_philanthropy_goals(
        session,
        household_id,
        actor,
        get_settings().specialized_cfs_rules_path,
        analysis_date or date.today(),
    )
