from __future__ import annotations

from app.domain.enums import ProductEligibilityDecision, ProductRiskLevel
from app.models.governance import Product, ProductSnapshot
from app.schemas.product_ontology import (
    ProductEligibilityContext,
    ProductEligibilityResponse,
    SnapshotFreshness,
)

RISK_ORDER = {
    ProductRiskLevel.R1: 1,
    ProductRiskLevel.R2: 2,
    ProductRiskLevel.R3: 3,
    ProductRiskLevel.R4: 4,
    ProductRiskLevel.R5: 5,
}

UNAVAILABLE_STATUSES = {"unavailable", "subscription_suspended", "closed"}


def snapshot_freshness(
    snapshot: ProductSnapshot,
    context: ProductEligibilityContext,
) -> SnapshotFreshness:
    age_days = max(0, (context.analysis_date - snapshot.as_of_date).days)
    stale = age_days > context.maximum_snapshot_age_days
    executable = not stale and snapshot.sale_status == "available"
    return SnapshotFreshness(
        as_of_date=snapshot.as_of_date,
        age_days=age_days,
        maximum_age_days=context.maximum_snapshot_age_days,
        stale=stale,
        sale_status=snapshot.sale_status,
        executable=executable,
    )


def evaluate_product_eligibility(
    product: Product,
    snapshot: ProductSnapshot,
    context: ProductEligibilityContext,
) -> ProductEligibilityResponse:
    reasons: list[str] = []
    restrictions: list[str] = []
    blocked: list[str] = []
    freshness = snapshot_freshness(snapshot, context)

    if not context.product_mapping_allowed:
        blocked.append("该 CFS 组件没有通过产品映射闸门。")
    if product.is_deleted or not product.enabled:
        blocked.append("产品已停用，不能进入候选集。")
    if snapshot.sale_status in UNAVAILABLE_STATUSES:
        blocked.append("最新快照显示当前不可申购或已关闭。")
    if context.need not in product.client_role_in_cfs:
        blocked.append("产品用途与当前家庭需要不匹配。")
    if context.account_wrapper not in product.account_wrappers:
        blocked.append("产品不支持当前账户包装器。")
    if RISK_ORDER[snapshot.risk_level] > RISK_ORDER[context.risk_budget.maximum_risk_level]:
        blocked.append("产品风险等级超过家庭风险预算上限。")
    if context.need == "long_term_growth" and not context.risk_budget.additional_risk_allowed:
        blocked.append("家庭风险预算未开放新增投资。")

    minimum_holding_days = int(snapshot.liquidity_snapshot.get("minimum_holding_days", 0))
    if minimum_holding_days > context.horizon_days:
        blocked.append("最短持有期长于目标期限。")
    if minimum_holding_days > context.maximum_lockup_days:
        blocked.append("产品锁定期超过这笔资金可接受的上限。")

    if blocked:
        decision = ProductEligibilityDecision.BLOCKED
        restrictions.extend(blocked)
    elif freshness.stale:
        decision = ProductEligibilityDecision.EDUCATION_ONLY
        restrictions.append("产品快照已超过复核期限，只能用于教育与比较。")
    elif product.professional_only and context.client_qualification != "professional":
        decision = ProductEligibilityDecision.PROFESSIONAL_REVIEW
        restrictions.append("产品仅面向具备相应资格的客户，需专业人员复核。")
    elif product.professional_review_required:
        decision = ProductEligibilityDecision.PROFESSIONAL_REVIEW
        restrictions.append("该产品类别需要专业人员核对账户、期限和规则。")
    else:
        if context.channel == "icbc" and not bool(product.terms.get("icbc_publicly_listed")):
            restrictions.append("未取得工行当前公开列示证据。")
        if snapshot.sale_status == "channel_verification_required":
            restrictions.append("公开列示不等于当日可售，需在交易渠道再次核验。")
        if product.all_in_cost is None:
            restrictions.append("客户全口径费用尚未补齐。")
        decision = (
            ProductEligibilityDecision.RESTRICTED
            if restrictions
            else ProductEligibilityDecision.ELIGIBLE
        )

    if decision == ProductEligibilityDecision.ELIGIBLE:
        reasons.append("用途、风险、期限、流动性、资格和快照均通过硬性闸门。")
    elif decision == ProductEligibilityDecision.RESTRICTED:
        reasons.append("产品可进入候选比较，但限制项补齐前不能执行。")
    elif decision == ProductEligibilityDecision.EDUCATION_ONLY:
        reasons.append("目录证据仍可用于认识产品差异，但不能形成可执行建议。")
    elif decision == ProductEligibilityDecision.PROFESSIONAL_REVIEW:
        reasons.append("系统不替代专业资格与账户规则审查。")
    else:
        reasons.append("至少一个硬性适当性条件不满足，产品不进入排名。")

    executable = decision == ProductEligibilityDecision.ELIGIBLE and freshness.executable
    return ProductEligibilityResponse(
        product_id=product.id,
        product_code=product.code,
        snapshot_id=snapshot.id,
        decision=decision,
        eligible=decision == ProductEligibilityDecision.ELIGIBLE,
        executable=executable,
        reasons=reasons,
        restrictions=restrictions,
        freshness=freshness,
    )
