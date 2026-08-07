from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.domain.enums import MarketScenario
from app.schemas.portfolio import (
    PersistedPortfolioRun,
    PortfolioResponse,
    ProductCatalogResponse,
    SuitabilityProbeRequest,
    SuitabilityProbeResponse,
)
from app.services.portfolio.catalog import build_catalog_response
from app.services.portfolio.engine import (
    evaluate_suitability_probe,
    persist_portfolio,
    portfolio_household,
)
from app.services.portfolio.rules import load_portfolio_rules

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDate = Annotated[date | None, Query(description="可复现组合日期，默认服务端当天")]
MarketScenarioQuery = Annotated[
    MarketScenario,
    Query(description="有限战术情景；不能覆盖家庭、客户或产品闸门"),
]

router = APIRouter(tags=["portfolio-and-suitability"])


def _portfolio(
    session: Session,
    household_id: str,
    analysis_date: date | None,
    market_scenario: MarketScenario,
) -> PortfolioResponse:
    settings = get_settings()
    return portfolio_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        analysis_date or date.today(),
        market_scenario,
    )


@router.get("/portfolio/products", response_model=ProductCatalogResponse)
def get_mock_product_catalog(
    session: SessionDependency,
    _actor: ActorDependency,
) -> ProductCatalogResponse:
    return build_catalog_response(session, get_settings().product_catalog_path)


@router.get(
    "/households/{household_id}/portfolio",
    response_model=PortfolioResponse,
)
def get_portfolio(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    market_scenario: MarketScenarioQuery = MarketScenario.NEUTRAL,
) -> PortfolioResponse:
    return _portfolio(session, household_id, analysis_date, market_scenario)


@router.post(
    "/households/{household_id}/portfolio/suitability-check",
    response_model=SuitabilityProbeResponse,
)
def post_suitability_check(
    household_id: str,
    request: SuitabilityProbeRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> SuitabilityProbeResponse:
    settings = get_settings()
    return evaluate_suitability_probe(
        session,
        household_id,
        request,
        actor,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
    )


@router.post(
    "/households/{household_id}/portfolio/runs",
    response_model=PersistedPortfolioRun,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio_run(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    market_scenario: MarketScenarioQuery = MarketScenario.NEUTRAL,
) -> PersistedPortfolioRun:
    settings = get_settings()
    portfolio = _portfolio(session, household_id, analysis_date, market_scenario)
    rules = load_portfolio_rules(settings.portfolio_rules_path)
    return persist_portfolio(session, portfolio, rules, actor)


@router.get("/households/{household_id}/portfolio/export")
def export_portfolio_json(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    market_scenario: MarketScenarioQuery = MarketScenario.NEUTRAL,
) -> Response:
    portfolio = _portfolio(session, household_id, analysis_date, market_scenario)
    return Response(
        content=portfolio.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="wealthtwin-{portfolio.meta.household_code.lower()}-'
                f'portfolio-{portfolio.meta.analysis_date.isoformat()}.json"'
            )
        },
    )
