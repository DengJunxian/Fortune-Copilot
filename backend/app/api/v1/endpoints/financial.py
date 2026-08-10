from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.financial_analysis import (
    DiagnosticsResponse,
    FinancialAnalysisResponse,
    MetricsResponse,
    PersistedAnalysisRun,
    StatementsResponse,
)
from app.services.financial.engine import analyze_household, persist_analysis
from app.services.financial.rules import load_financial_rules

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDate = Annotated[date | None, Query(description="可复现分析日期，默认服务端当天")]

router = APIRouter(tags=["financial-analysis"])


def _analysis(
    session: Session,
    household_id: str,
    analysis_date: date | None,
) -> FinancialAnalysisResponse:
    settings = get_settings()
    return analyze_household(
        session,
        household_id,
        settings.financial_rules_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/financial-analysis",
    response_model=FinancialAnalysisResponse,
)
def get_financial_analysis(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> FinancialAnalysisResponse:
    return _analysis(session, household_id, analysis_date)


@router.get(
    "/households/{household_id}/statements",
    response_model=StatementsResponse,
)
def get_statements(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> StatementsResponse:
    analysis = _analysis(session, household_id, analysis_date)
    return StatementsResponse(
        meta=analysis.meta,
        profile=analysis.profile,
        statements=analysis.statements,
    )


@router.get(
    "/households/{household_id}/metrics",
    response_model=MetricsResponse,
)
def get_metrics(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> MetricsResponse:
    analysis = _analysis(session, household_id, analysis_date)
    return MetricsResponse(
        meta=analysis.meta,
        metrics=analysis.metrics,
        health_dimensions=analysis.health_dimensions,
        health_assessment=analysis.health_assessment,
    )


@router.get(
    "/households/{household_id}/diagnostics",
    response_model=DiagnosticsResponse,
)
def get_diagnostics(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> DiagnosticsResponse:
    analysis = _analysis(session, household_id, analysis_date)
    return DiagnosticsResponse(
        meta=analysis.meta,
        diagnostics=analysis.diagnostics,
        protection=analysis.protection,
        purchasing_power=analysis.purchasing_power,
    )


@router.post(
    "/households/{household_id}/financial-analysis/runs",
    response_model=PersistedAnalysisRun,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_run(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> PersistedAnalysisRun:
    settings = get_settings()
    analysis = _analysis(session, household_id, analysis_date)
    rules = load_financial_rules(settings.financial_rules_path)
    return persist_analysis(session, analysis, rules, actor)


@router.get("/households/{household_id}/financial-analysis/export")
def export_analysis_json(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> Response:
    analysis = _analysis(session, household_id, analysis_date)
    return Response(
        content=analysis.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="wealthtwin-{analysis.meta.household_code.lower()}-'
                f'{analysis.meta.analysis_date.isoformat()}.json"'
            )
        },
    )
