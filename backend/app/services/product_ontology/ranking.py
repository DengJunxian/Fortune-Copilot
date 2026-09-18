from __future__ import annotations

from decimal import Decimal

from app.domain.enums import ComplexityLevel, ProductEligibilityDecision, ProductRiskLevel
from app.models.governance import Product, ProductSnapshot
from app.schemas.fund_advisory import VerifiedFundCatalogFile
from app.schemas.product_ontology import (
    ExcludedProductCandidate,
    ProductCandidateFunnel,
    ProductFunnelStage,
    ProductOntologyItem,
    ProductRankRequest,
    ProductRankResponse,
    ProductScoreBreakdown,
    ProductSnapshotOut,
    RankedProductCandidate,
)
from app.services.fund_advisory.catalog import catalog_is_stale
from app.services.product_eligibility.engine import evaluate_product_eligibility
from app.services.product_ontology.adapter import EXECUTION_BOUNDARY

RISK_ORDER = {
    ProductRiskLevel.R1: 1,
    ProductRiskLevel.R2: 2,
    ProductRiskLevel.R3: 3,
    ProductRiskLevel.R4: 4,
    ProductRiskLevel.R5: 5,
}

ELIGIBILITY_SCORE = {
    ProductEligibilityDecision.ELIGIBLE: Decimal("25"),
    ProductEligibilityDecision.RESTRICTED: Decimal("15"),
    ProductEligibilityDecision.EDUCATION_ONLY: Decimal("8"),
    ProductEligibilityDecision.PROFESSIONAL_REVIEW: Decimal("5"),
    ProductEligibilityDecision.BLOCKED: Decimal("0"),
}


def _score(
    product: Product,
    snapshot: ProductSnapshot,
    request: ProductRankRequest,
) -> ProductScoreBreakdown:
    context = request.context
    eligibility = evaluate_product_eligibility(product, snapshot, context)
    minimum_holding_days = int(snapshot.liquidity_snapshot.get("minimum_holding_days", 0))
    maximum_risk = RISK_ORDER[context.risk_budget.maximum_risk_level]
    product_risk = RISK_ORDER[snapshot.risk_level]
    issuer_ratio = context.existing_issuer_exposure.get(product.issuer, Decimal("0"))
    if product.all_in_cost is None:
        cost_score = Decimal("-3")
    else:
        cost_score = max(Decimal("-5"), Decimal("10") - product.all_in_cost * 1000)
    complexity_score = {
        ComplexityLevel.BASIC: Decimal("6"),
        ComplexityLevel.STANDARD: Decimal("4"),
        ComplexityLevel.COMPLEX: Decimal("1"),
        ComplexityLevel.PROFESSIONAL: Decimal("-3"),
    }[product.complexity_level]
    return ProductScoreBreakdown(
        need_fit=Decimal("24") if context.need in product.client_role_in_cfs else Decimal("-24"),
        hard_eligibility=ELIGIBILITY_SCORE[eligibility.decision],
        liquidity_fit=(
            Decimal("12")
            if minimum_holding_days <= context.maximum_lockup_days
            else Decimal("-20")
        ),
        risk_fit=Decimal("12") - Decimal(abs(maximum_risk - product_risk) * 2),
        goal_horizon_fit=(
            Decimal("10") if minimum_holding_days <= context.horizon_days else Decimal("-20")
        ),
        all_in_cost=cost_score,
        diversification=Decimal("7") if bool(product.terms.get("broad_index")) else Decimal("3"),
        issuer_concentration=-(issuer_ratio * Decimal("20")),
        operational_simplicity=complexity_score,
        conflict_penalty=Decimal("-20") if product.conflict_of_interest_flag else Decimal("0"),
    )


def _score_total(breakdown: ProductScoreBreakdown) -> Decimal:
    return sum(
        (Decimal(str(value)) for value in breakdown.model_dump().values()),
        Decimal("0"),
    )


def _candidate_funnel(
    pool: list[Product],
    snapshots: dict[str, ProductSnapshot],
    request: ProductRankRequest,
    *,
    qualified_count: int,
    final_count: int,
) -> ProductCandidateFunnel:
    context = request.context
    purpose_matched = [
        product for product in pool if context.need in product.client_role_in_cfs
    ]
    horizon_matched = [
        product
        for product in purpose_matched
        if (snapshot := snapshots.get(product.id)) is not None
        and int(snapshot.liquidity_snapshot.get("minimum_holding_days", 0))
        <= context.horizon_days
    ]
    risk_matched = [
        product
        for product in horizon_matched
        if (snapshot := snapshots.get(product.id)) is not None
        and RISK_ORDER[snapshot.risk_level]
        <= RISK_ORDER[context.risk_budget.maximum_risk_level]
        and not (
            context.need == "long_term_growth"
            and not context.risk_budget.additional_risk_allowed
        )
    ]
    liquidity_matched = [
        product
        for product in risk_matched
        if (snapshot := snapshots.get(product.id)) is not None
        and int(snapshot.liquidity_snapshot.get("minimum_holding_days", 0))
        <= context.maximum_lockup_days
    ]
    return ProductCandidateFunnel(
        stages=[
            ProductFunnelStage(code="sample_pool", label="产品样本池", count=len(pool)),
            ProductFunnelStage(code="need_fit", label="用途匹配", count=len(purpose_matched)),
            ProductFunnelStage(code="horizon_fit", label="期限匹配", count=len(horizon_matched)),
            ProductFunnelStage(
                code="risk_suitability", label="风险适当性", count=len(risk_matched)
            ),
            ProductFunnelStage(
                code="liquidity_fit", label="流动性要求", count=len(liquidity_matched)
            ),
            ProductFunnelStage(
                code="quality_filters",
                label="费用 / 资格 / 冲突过滤",
                count=qualified_count,
            ),
            ProductFunnelStage(code="final_candidates", label="最终候选", count=final_count),
        ],
        explanation=(
            "各阶段数量由同一产品资格与排序上下文逐层计算；"
            "最终候选不是工行实时货架，也不是自动交易清单。"
        ),
    )


def rank_products(
    products: list[Product],
    snapshots: dict[str, ProductSnapshot],
    request: ProductRankRequest,
    catalog: VerifiedFundCatalogFile,
) -> ProductRankResponse:
    allowed_ids = set(request.product_ids)
    pool = [item for item in products if not allowed_ids or item.id in allowed_ids]
    scored: list[tuple[Decimal, int, Product, ProductSnapshot, ProductScoreBreakdown]] = []
    excluded: list[ExcludedProductCandidate] = []
    for product in pool:
        snapshot = snapshots.get(product.id)
        if snapshot is None:
            excluded.append(
                ExcludedProductCandidate(
                    product_id=product.id,
                    product_code=product.code,
                    product_name=product.name,
                    decision=ProductEligibilityDecision.BLOCKED,
                    reasons=["产品缺少可核验快照。"],
                )
            )
            continue
        eligibility = evaluate_product_eligibility(product, snapshot, request.context)
        if eligibility.decision == ProductEligibilityDecision.BLOCKED:
            excluded.append(
                ExcludedProductCandidate(
                    product_id=product.id,
                    product_code=product.code,
                    product_name=product.name,
                    decision=eligibility.decision,
                    reasons=eligibility.restrictions,
                )
            )
            continue
        breakdown = _score(product, snapshot, request)
        scored.append(
            (
                _score_total(breakdown),
                int(product.terms.get("selection_priority", 100)),
                product,
                snapshot,
                breakdown,
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1], item[2].code))
    selected = scored[: request.maximum_candidates]
    candidates: list[RankedProductCandidate] = []
    for index, (score, _priority, product, snapshot, breakdown) in enumerate(
        selected, start=1
    ):
        eligibility = evaluate_product_eligibility(product, snapshot, request.context)
        why_selected = [
            "产品用途覆盖当前 CFS 需要。",
            "风险等级未超过家庭风险预算。",
            "最短持有期未超过目标期限与流动性上限。",
        ]
        if product.all_in_cost is None:
            why_selected.append("费用尚未补齐，因此成本项被扣分且执行被限制。")
        lower_count = max(0, len(scored) - index)
        why_not = [
            (
                f"另有 {lower_count} 个通过硬闸门的候选综合得分更低。"
                if lower_count
                else "没有其他通过硬闸门且综合得分更高的候选。"
            )
        ]
        if excluded:
            why_not.append(f"另有 {len(excluded)} 个产品未通过硬性资格闸门。")
        candidates.append(
            RankedProductCandidate(
                rank=index,
                product=ProductOntologyItem.model_validate(product),
                snapshot=ProductSnapshotOut.model_validate(snapshot),
                eligibility=eligibility,
                score=score,
                score_breakdown=breakdown,
                why_selected=why_selected,
                why_not_other_candidates=why_not,
            )
        )

    stale = catalog_is_stale(catalog, request.context.analysis_date)
    funnel = _candidate_funnel(
        pool,
        snapshots,
        request,
        qualified_count=len(scored),
        final_count=len(candidates),
    )
    if not candidates:
        return ProductRankResponse(
            result="no_product",
            need=request.context.need,
            candidate_count=0,
            candidates=[],
            excluded=excluded,
            funnel=funnel,
            catalog_as_of=catalog.verified_on,
            catalog_stale=stale,
            executable_recommendation_allowed=False,
            no_product_reason=(
                "没有产品同时通过用途、风险、期限、流动性、账户和资格闸门；"
                "保留资金或专业服务本身就是有效方案。"
            ),
            execution_boundary=EXECUTION_BOUNDARY,
        )
    return ProductRankResponse(
        result="ranked",
        need=request.context.need,
        candidate_count=len(candidates),
        candidates=candidates,
        excluded=excluded,
        funnel=funnel,
        catalog_as_of=catalog.verified_on,
        catalog_stale=stale,
        executable_recommendation_allowed=any(
            item.eligibility.executable for item in candidates
        ),
        execution_boundary=EXECUTION_BOUNDARY,
    )
