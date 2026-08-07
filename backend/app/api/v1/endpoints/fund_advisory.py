from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.fund_advisory import FundAdvisoryResponse, VerifiedFundCatalogResponse
from app.services.fund_advisory.catalog import build_fund_catalog_response
from app.services.fund_advisory.engine import advise_household

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDate = Annotated[date | None, Query(description="可复现投顾日期，默认服务端当天")]

router = APIRouter(tags=["verified-fund-advisory"])


@router.get("/fund-advisory/products", response_model=VerifiedFundCatalogResponse)
def get_verified_fund_catalog(
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
) -> VerifiedFundCatalogResponse:
    settings = get_settings()
    return build_fund_catalog_response(
        settings.fund_advisory_catalog_path,
        analysis_date or date.today(),
    )


@router.get(
    "/households/{household_id}/fund-advisory",
    response_model=FundAdvisoryResponse,
)
def get_fund_advisory(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AnalysisDate = None,
    icbc_only: Annotated[
        bool,
        Query(description="实际分配是否只允许有工行官方公开列示证据的基金"),
    ] = True,
) -> FundAdvisoryResponse:
    settings = get_settings()
    return advise_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.portfolio_rules_path,
        settings.product_catalog_path,
        settings.fund_advisory_catalog_path,
        analysis_date or date.today(),
        icbc_only=icbc_only,
    )
