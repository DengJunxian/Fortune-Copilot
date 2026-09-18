from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import CFSTimeHorizon, ProductRiskLevel, RiskLevel
from app.models.cfs import CFSSolution, CFSSolutionComponent
from app.models.governance import ProductSnapshot
from app.schemas.product_ontology import (
    CFSProductCandidateGroup,
    CFSProductCompositionResponse,
    ProductEligibilityContext,
    ProductRankRequest,
    ProductRiskBudgetInput,
)
from app.services.fund_advisory.catalog import catalog_is_stale
from app.services.product_ontology.adapter import (
    EXECUTION_BOUNDARY,
    ensure_verified_fund_ontology,
)
from app.services.product_ontology.ranking import rank_products

RISK_TO_PRODUCT = {
    RiskLevel.LOW.value: ProductRiskLevel.R1,
    RiskLevel.MEDIUM_LOW.value: ProductRiskLevel.R2,
    RiskLevel.MEDIUM.value: ProductRiskLevel.R3,
    RiskLevel.MEDIUM_HIGH.value: ProductRiskLevel.R4,
    RiskLevel.HIGH.value: ProductRiskLevel.R5,
}

HORIZON_DAYS = {
    CFSTimeHorizon.IMMEDIATE: 30,
    CFSTimeHorizon.SHORT_TERM: 1095,
    CFSTimeHorizon.MEDIUM_TERM: 2555,
    CFSTimeHorizon.LONG_TERM: 3650,
    CFSTimeHorizon.ONGOING: 3650,
}

LOCKUP_DAYS = {
    CFSTimeHorizon.IMMEDIATE: 0,
    CFSTimeHorizon.SHORT_TERM: 30,
    CFSTimeHorizon.MEDIUM_TERM: 365,
    CFSTimeHorizon.LONG_TERM: 1095,
    CFSTimeHorizon.ONGOING: 1095,
}


def _records(
    session: Session,
    household_id: str,
    solution_id: str,
) -> tuple[CFSSolution, list[CFSSolutionComponent]]:
    solution = session.scalar(
        select(CFSSolution).where(
            CFSSolution.id == solution_id,
            CFSSolution.household_id == household_id,
            CFSSolution.is_deleted.is_(False),
        )
    )
    if solution is None:
        raise AppError("cfs_solution_not_found", "找不到家庭综合财务方案", status_code=404)
    components = list(
        session.scalars(
            select(CFSSolutionComponent)
            .where(
                CFSSolutionComponent.solution_id == solution.id,
                CFSSolutionComponent.is_deleted.is_(False),
            )
            .order_by(CFSSolutionComponent.priority, CFSSolutionComponent.id)
        ).all()
    )
    return solution, components


def compose_cfs_product_candidates(
    session: Session,
    household_id: str,
    solution_id: str,
    configured_catalog_path: str,
    *,
    analysis_date: date,
    maximum_snapshot_age_days: int = 45,
) -> CFSProductCompositionResponse:
    solution, components = _records(session, household_id, solution_id)
    catalog, products, snapshots = ensure_verified_fund_ontology(
        session, configured_catalog_path
    )
    snapshots_by_product: dict[str, ProductSnapshot] = {
        item.product_id: item for item in snapshots
    }
    risk_budget = solution.summary.get("risk_budget", {})
    risk_level = str(risk_budget.get("household_economic_risk_capacity", "low"))
    maximum_risk = RISK_TO_PRODUCT.get(risk_level, ProductRiskLevel.R1)
    additional_risk_allowed = bool(risk_budget.get("additional_risk_allowed", False))
    remaining_capacity = Decimal(str(risk_budget.get("remaining_risk_capacity", "0")))
    groups: list[CFSProductCandidateGroup] = []

    for component in components:
        purpose = component.recommended_action
        need = str(component.evidence.get("wealth_need_type", component.component_type.value))
        if not component.product_mapping_allowed:
            groups.append(
                CFSProductCandidateGroup(
                    component_id=component.id,
                    component_type=component.component_type,
                    purpose=purpose,
                    result="no_product",
                    candidates=[],
                    excluded=[],
                    funnel=None,
                    no_product_reason=(
                        "该行动不需要产品映射；现金保留、偿债、保障询价或专业服务"
                        "本身就是这一步的正确承接方式。"
                    ),
                )
            )
            continue

        context = ProductEligibilityContext(
            need=need,
            risk_budget=ProductRiskBudgetInput(
                maximum_risk_level=maximum_risk,
                additional_risk_allowed=additional_risk_allowed,
                remaining_capacity=max(Decimal("0"), remaining_capacity),
            ),
            account_wrapper="ordinary",
            horizon_days=HORIZON_DAYS[component.time_horizon],
            maximum_lockup_days=LOCKUP_DAYS[component.time_horizon],
            client_qualification="retail",
            channel="icbc",
            analysis_date=analysis_date,
            maximum_snapshot_age_days=maximum_snapshot_age_days,
            product_mapping_allowed=True,
        )
        ranking = rank_products(
            products,
            snapshots_by_product,
            ProductRankRequest(context=context, maximum_candidates=3),
            catalog,
        )
        groups.append(
            CFSProductCandidateGroup(
                component_id=component.id,
                component_type=component.component_type,
                purpose=purpose,
                result=ranking.result,
                candidates=ranking.candidates,
                excluded=ranking.excluded,
                funnel=ranking.funnel,
                no_product_reason=ranking.no_product_reason,
            )
        )

    stale = catalog_is_stale(catalog, analysis_date)
    return CFSProductCompositionResponse(
        household_id=household_id,
        solution_id=solution.id,
        analysis_date=analysis_date,
        catalog_as_of=catalog.verified_on,
        catalog_stale=stale,
        executable_recommendation_allowed=any(
            candidate.eligibility.executable
            for group in groups
            for candidate in group.candidates
        ),
        groups=groups,
        execution_boundary=EXECUTION_BOUNDARY,
    )
