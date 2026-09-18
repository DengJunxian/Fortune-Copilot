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
from app.schemas.eligible_capital import EligibleCapitalResponse
from app.schemas.liability import (
    LiabilityCalendarResponse,
    LiabilityStreamCreate,
    LiabilityStreamCreateResponse,
)
from app.services.eligible_capital.engine import calculate_household_eligible_capital
from app.services.liability_engine.engine import (
    create_liability_stream,
    materialize_liability_streams,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="负债流与 ELTC 计算基准日")]

router = APIRouter(tags=["v5-liability-and-eligible-capital"])


def require_liability_engine_enabled() -> None:
    if not get_settings().enable_v5_liability_engine:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 负债流与长期可配置资本",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_liability_engine_enabled)]


@router.get(
    "/households/{household_id}/liability-calendar",
    response_model=LiabilityCalendarResponse,
)
def read_liability_calendar(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> LiabilityCalendarResponse:
    settings = get_settings()
    return materialize_liability_streams(
        session,
        household_id,
        actor,
        settings.liability_rules_path,
        analysis_date or date.today(),
    )


@router.post(
    "/households/{household_id}/liability-streams",
    response_model=LiabilityStreamCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_liability_stream(
    request: Request,
    household_id: str,
    payload: LiabilityStreamCreate,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> LiabilityStreamCreateResponse:
    require_roles(actor, {"client", "advisor", "admin"})
    require_sensitive_confirmation(request, "create_liability_stream")
    settings = get_settings()
    return create_liability_stream(
        session,
        household_id,
        payload,
        actor,
        settings.liability_rules_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/eligible-capital",
    response_model=EligibleCapitalResponse,
)
def read_eligible_capital(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> EligibleCapitalResponse:
    settings = get_settings()
    return calculate_household_eligible_capital(
        session,
        household_id,
        actor,
        financial_rules_path=settings.financial_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        liability_rules_path=settings.liability_rules_path,
        calibration_registry_path=settings.calibration_registry_path,
        calibration_enabled=settings.enable_v5_calibration,
        analysis_date=analysis_date or date.today(),
    )
