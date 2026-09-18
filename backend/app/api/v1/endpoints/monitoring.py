from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
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
from app.schemas.monitoring import (
    AdvisorActionCenterResponse,
    BehaviorInterventionsResponse,
    MonitoringAlertsResponse,
    MonitoringEvaluateRequest,
    MonitoringEvaluateResponse,
    NextBestActionsResponse,
)
from app.services.monitoring.engine import (
    advisor_action_center,
    evaluate_monitoring,
    list_behavior_interventions,
    list_monitoring_alerts,
)
from app.services.next_best_action.engine import get_next_best_actions

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="监控分析日")]

router = APIRouter(tags=["v5-monitoring"])


def require_monitoring_enabled() -> None:
    if not get_settings().enable_v5_monitoring:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 持续监控与客户行动",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_monitoring_enabled)]


@router.get(
    "/households/{household_id}/monitoring/alerts",
    response_model=MonitoringAlertsResponse,
)
def read_monitoring_alerts(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> MonitoringAlertsResponse:
    return list_monitoring_alerts(
        session,
        household_id,
        get_settings().monitoring_rules_path,
    )


@router.post(
    "/households/{household_id}/monitoring/evaluate",
    response_model=MonitoringEvaluateResponse,
)
def post_monitoring_evaluation(
    request: Request,
    household_id: str,
    payload: MonitoringEvaluateRequest,
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
) -> MonitoringEvaluateResponse:
    require_roles(actor, {"advisor", "admin"})
    require_sensitive_confirmation(request, "evaluate_monitoring")
    settings = get_settings()
    return evaluate_monitoring(
        session,
        household_id,
        actor,
        payload,
        settings.monitoring_rules_path,
        settings.family_enterprise_rules_path,
        settings.specialized_cfs_rules_path,
    )


@router.get(
    "/households/{household_id}/behavior-interventions",
    response_model=BehaviorInterventionsResponse,
)
def read_behavior_interventions(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> BehaviorInterventionsResponse:
    return list_behavior_interventions(session, household_id)


@router.get(
    "/households/{household_id}/next-best-actions",
    response_model=NextBestActionsResponse,
)
def read_next_best_actions(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> NextBestActionsResponse:
    return get_next_best_actions(session, household_id, analysis_date or date.today())


@router.get(
    "/advisor/action-center",
    response_model=AdvisorActionCenterResponse,
)
def read_advisor_action_center(
    session: SessionDependency,
    actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> AdvisorActionCenterResponse:
    require_roles(actor, {"advisor", "compliance", "admin"})
    return advisor_action_center(session, actor, analysis_date or date.today())
