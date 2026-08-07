from __future__ import annotations

from decimal import Decimal

from app.domain.enums import (
    ComplexityLevel,
    ProductRiskLevel,
    RiskLevel,
    SuitabilityDecision,
    SuitabilityGateType,
    SuitabilityStatus,
)
from app.domain.financial import HouseholdFacts
from app.schemas.planning import PlanningResponse
from app.schemas.portfolio import (
    ProductOut,
    SuitabilityCheckItem,
    SuitabilityGateResult,
    SuitabilityProbeRequest,
)
from app.services.portfolio.rules import PortfolioRules

RISK_FROM_HOUSEHOLD = {
    RiskLevel.LOW: ProductRiskLevel.R1,
    RiskLevel.MEDIUM_LOW: ProductRiskLevel.R2,
    RiskLevel.MEDIUM: ProductRiskLevel.R3,
    RiskLevel.MEDIUM_HIGH: ProductRiskLevel.R4,
    RiskLevel.HIGH: ProductRiskLevel.R5,
}


def risk_rank(level: ProductRiskLevel, rules: PortfolioRules) -> int:
    return rules.suitability.risk_level_order.index(level)


def score_to_risk_level(score: Decimal, rules: PortfolioRules) -> ProductRiskLevel:
    for level in rules.suitability.risk_level_order:
        if score <= rules.suitability.score_thresholds[level]:
            return level
    return ProductRiskLevel.R5


def complexity_cap(knowledge_score: Decimal) -> ComplexityLevel:
    if knowledge_score < Decimal("0.40"):
        return ComplexityLevel.BASIC
    if knowledge_score < Decimal("0.70"):
        return ComplexityLevel.STANDARD
    if knowledge_score < Decimal("0.90"):
        return ComplexityLevel.COMPLEX
    return ComplexityLevel.PROFESSIONAL


def family_safety_gate(
    plan: PlanningResponse,
    rules: PortfolioRules,
) -> SuitabilityGateResult:
    labels = {
        "liquidity": "应急与流动性",
        "debt": "债务负担",
        "protection": "保障缺口",
        "horizon": "近期目标期限",
    }
    checks: list[SuitabilityCheckItem] = []
    for constraint_id, label in labels.items():
        constraint = next(item for item in plan.constraints if item.constraint_id == constraint_id)
        status = (
            SuitabilityStatus.PASS
            if constraint.status == "pass"
            else SuitabilityStatus.BLOCK
            if constraint.status == "block"
            else SuitabilityStatus.RESTRICT
        )
        checks.append(
            SuitabilityCheckItem(
                check_code=f"family_{constraint_id}",
                label=label,
                status=status,
                observed_value=constraint.observed_value,
                rule=constraint.required_condition,
                reason=constraint.effect,
                source_record_ids=constraint.source_record_ids,
            )
        )

    growth = next(item for item in plan.accounts if item.bucket.value == "long_term_growth")
    learning_mode = (
        plan.investment_learning.applicable and plan.investment_learning.eligible
    )
    amount_status = (
        SuitabilityStatus.PASS if growth.recommended_amount > 0 else SuitabilityStatus.BLOCK
    )
    checks.append(
        SuitabilityCheckItem(
            check_code="family_long_term_amount",
            label="小额学习仓" if learning_mode else "真实长期资金",
            status=amount_status,
            observed_value=(
                f"宽基指数学习仓 {growth.recommended_amount:.2f} 元"
                if learning_mode
                else f"可进入长期增长账户 {growth.recommended_amount:.2f} 元"
            ),
            rule=(
                "正式门槛以下仅使用不超过多余长期资金10%的学习仓"
                if learning_mode
                else "只有完成优先安全层后剩余的长期资金才可进入组合"
            ),
            reason=(
                (
                    "已有小额学习资金，仍须服从完整产品适当性闸门。"
                    if learning_mode
                    else "已有可配置的长期资金。"
                )
                if amount_status == SuitabilityStatus.PASS
                else "当前没有可执行的长期新增资金，只能展示教育候选并优先修复安全层。"
            ),
            source_record_ids=growth.source_record_ids,
        )
    )
    statuses = {item.status for item in checks}
    if SuitabilityStatus.BLOCK in statuses:
        status = SuitabilityStatus.BLOCK
        decision = SuitabilityDecision.EDUCATION_ONLY
        cap = rules.suitability.family_blocked_high_risk_cap
    elif SuitabilityStatus.RESTRICT in statuses:
        status = SuitabilityStatus.RESTRICT
        decision = SuitabilityDecision.DOWNGRADE
        cap = rules.suitability.family_restricted_high_risk_cap
    else:
        status = SuitabilityStatus.PASS
        decision = SuitabilityDecision.ALLOW
        cap = Decimal("1")
    failed = [item.check_code for item in checks if item.status != SuitabilityStatus.PASS]
    return SuitabilityGateResult(
        gate=SuitabilityGateType.FAMILY_SAFETY,
        name="家庭安全闸门",
        status=status,
        decision=decision,
        high_risk_cap=cap,
        checks=checks,
        failed_check_codes=failed,
        explanation=(
            "家庭安全条件全部通过，可以继续进行客户与产品匹配。"
            if status == SuitabilityStatus.PASS
            else "应急、债务、保障或近期目标仍有限制；市场情景不得覆盖这些前置条件。"
        ),
    )


def customer_suitability_gate(
    facts: HouseholdFacts,
    rules: PortfolioRules,
) -> SuitabilityGateResult:
    if not facts.risk_assessments:
        check = SuitabilityCheckItem(
            check_code="customer_risk_data",
            label="客户风险信息",
            status=SuitabilityStatus.BLOCK,
            observed_value="缺少有效风险测评",
            rule="能力、意愿、知识和行为四项都必须存在",
            reason="缺少数据时不得自动匹配产品。",
        )
        return SuitabilityGateResult(
            gate=SuitabilityGateType.CUSTOMER,
            name="客户适当性闸门",
            status=SuitabilityStatus.BLOCK,
            decision=SuitabilityDecision.EDUCATION_ONLY,
            effective_risk_limit=ProductRiskLevel.R1,
            high_risk_cap=Decimal("0"),
            checks=[check],
            failed_check_codes=[check.check_code],
            explanation="缺少风险测评，只能提供基础教育。",
        )

    assessment = facts.risk_assessments[-1]
    components: list[tuple[str, str, Decimal, str]] = [
        ("capacity", "风险承担能力", assessment.capacity_score, assessment.id),
        ("willingness", "风险承受意愿", assessment.willingness_score, assessment.id),
        ("knowledge", "产品知识", assessment.knowledge_score, assessment.id),
        ("behavior", "风险行为", assessment.behavior_score, assessment.id),
    ]
    derived = [
        (code, label, score_to_risk_level(score, rules), score, source_id)
        for code, label, score, source_id in components
    ]
    limits = [item[2] for item in derived]
    limits.append(RISK_FROM_HOUSEHOLD[assessment.final_risk_limit])
    behavior_source_ids: list[str] = []
    if facts.behavior_assessments:
        behavior = facts.behavior_assessments[-1]
        limits.append(RISK_FROM_HOUSEHOLD[behavior.final_behavior_limit])
        behavior_source_ids.append(behavior.id)
    effective = min(limits, key=lambda item: risk_rank(item, rules))
    checks = [
        SuitabilityCheckItem(
            check_code=f"customer_{code}",
            label=label,
            status=SuitabilityStatus.PASS,
            observed_value=f"{score:.2%} → {level.value.upper()}",
            rule="按版本化分数阈值映射风险等级，最终取四维及行为记录中的审慎下限",
            reason=f"该维度允许上限为 {level.value.upper()}。",
            source_record_ids=[source_id],
        )
        for code, label, level, score, source_id in derived
    ]
    checks.append(
        SuitabilityCheckItem(
            check_code="customer_prudent_limit",
            label="审慎风险上限",
            status=SuitabilityStatus.PASS,
            observed_value=effective.value.upper(),
            rule="能力、意愿、知识、行为、问卷结论与行为实验取最低等级",
            reason="任何候选或产品不得超过该等级。",
            source_record_ids=[assessment.id, *behavior_source_ids],
        )
    )
    high_risk_cap = rules.suitability.risk_level_high_risk_caps[effective]
    return SuitabilityGateResult(
        gate=SuitabilityGateType.CUSTOMER,
        name="客户适当性闸门",
        status=SuitabilityStatus.PASS,
        decision=SuitabilityDecision.ALLOW,
        effective_risk_limit=effective,
        high_risk_cap=high_risk_cap,
        checks=checks,
        failed_check_codes=[],
        explanation=(
            f"能力、意愿、知识与行为取审慎下限 {effective.value.upper()}；"
            f"高风险资产上限 {high_risk_cap:.0%}。"
        ),
    )


def candidate_customer_gate(
    base_gate: SuitabilityGateResult,
    required_level: ProductRiskLevel,
    rules: PortfolioRules,
) -> SuitabilityGateResult:
    effective = base_gate.effective_risk_limit or ProductRiskLevel.R1
    allowed = risk_rank(required_level, rules) <= risk_rank(effective, rules)
    candidate_check = SuitabilityCheckItem(
        check_code="customer_candidate_risk",
        label="候选风险等级",
        status=SuitabilityStatus.PASS if allowed else SuitabilityStatus.RESTRICT,
        observed_value=f"候选 {required_level.value.upper()} / 客户上限 {effective.value.upper()}",
        rule="候选策略风险等级不得高于客户审慎上限",
        reason=(
            "风险等级匹配。" if allowed else "候选必须按客户上限降级，不能按原始进取边界执行。"
        ),
        source_record_ids=[],
    )
    checks = [*base_gate.checks, candidate_check]
    failed = [item.check_code for item in checks if item.status != SuitabilityStatus.PASS]
    return base_gate.model_copy(
        update={
            "status": SuitabilityStatus.PASS if allowed else SuitabilityStatus.RESTRICT,
            "decision": SuitabilityDecision.ALLOW if allowed else SuitabilityDecision.DOWNGRADE,
            "checks": checks,
            "failed_check_codes": failed,
            "explanation": (
                base_gate.explanation
                if allowed
                else (
                    f"候选要求 {required_level.value.upper()}，超过客户上限 "
                    f"{effective.value.upper()}，已触发降级。"
                )
            ),
        }
    )


def product_check_items(
    products: list[ProductOut],
    request: SuitabilityProbeRequest,
    customer_gate: SuitabilityGateResult,
    facts: HouseholdFacts,
    rules: PortfolioRules,
) -> list[SuitabilityCheckItem]:
    effective = customer_gate.effective_risk_limit or ProductRiskLevel.R1
    knowledge = (
        facts.risk_assessments[-1].knowledge_score if facts.risk_assessments else Decimal("0")
    )
    allowed_complexity = complexity_cap(knowledge)
    complexity_order = rules.suitability.complexity_order
    checks: list[SuitabilityCheckItem] = []
    for product in products:
        reasons: list[tuple[str, str]] = []
        if not product.enabled or product.education_only:
            reasons.append(("disabled", "产品仅用于教育或默认关闭"))
        if product.professional_only:
            reasons.append(("professional_only", "普通家庭自动路径不满足专业投资者条件"))
        if risk_rank(product.risk_level, rules) > risk_rank(effective, rules):
            reasons.append(("risk", "产品风险等级高于客户审慎上限"))
        if product.minimum_holding_months > request.target_horizon_months:
            reasons.append(("horizon", "最低持有期限长于目标期限"))
        if request.investment_amount < product.minimum_investment:
            reasons.append(("minimum_amount", "投资金额低于最低金额"))
        if complexity_order.index(product.complexity_level) > complexity_order.index(
            allowed_complexity
        ):
            reasons.append(("complexity", "产品复杂度高于客户知识上限"))
        if (
            request.target_horizon_months <= rules.suitability.short_horizon_months
            and product.historical_volatility_max > rules.suitability.high_volatility_threshold
        ):
            reasons.append(("short_horizon_volatility", "短期刚性目标不得投入高波动产品"))
        status = SuitabilityStatus.BLOCK if reasons else SuitabilityStatus.PASS
        checks.append(
            SuitabilityCheckItem(
                check_code=f"product_{product.code}",
                label=product.name,
                status=status,
                observed_value=(
                    f"{product.risk_level.value.upper()} / {product.minimum_holding_months}月 / "
                    f"最低 {product.minimum_investment:.2f} 元"
                ),
                rule="风险、期限、流动性、复杂度、最低金额与启用状态必须全部匹配",
                reason="；".join(reason for _, reason in reasons)
                if reasons
                else "产品类型条件通过。",
                source_record_ids=[product.id],
            )
        )
    return checks


def product_gate_for_probe(
    products: list[ProductOut],
    request: SuitabilityProbeRequest,
    customer_gate: SuitabilityGateResult,
    facts: HouseholdFacts,
    rules: PortfolioRules,
) -> SuitabilityGateResult:
    checks = product_check_items(products, request, customer_gate, facts, rules)
    if request.leverage_ratio > 0:
        checks.append(
            SuitabilityCheckItem(
                check_code="product_leverage",
                label="杠杆限制",
                status=SuitabilityStatus.BLOCK,
                observed_value=f"申请杠杆 {request.leverage_ratio:.0%}",
                rule="普通家庭自动推荐不得使用杠杆或股指期货",
                reason="杠杆请求被拒绝；专业套保沙箱也必须另行人工复核。",
            )
        )
    if request.concentration_ratio > rules.suitability.maximum_single_product_ratio:
        checks.append(
            SuitabilityCheckItem(
                check_code="product_concentration",
                label="单产品集中度",
                status=SuitabilityStatus.BLOCK,
                observed_value=f"申请集中度 {request.concentration_ratio:.0%}",
                rule=f"单产品上限 {rules.suitability.maximum_single_product_ratio:.0%}",
                reason="集中度超过审慎上限。",
            )
        )
    failed = [item.check_code for item in checks if item.status != SuitabilityStatus.PASS]
    return SuitabilityGateResult(
        gate=SuitabilityGateType.PRODUCT,
        name="产品适当性闸门",
        status=SuitabilityStatus.BLOCK if failed else SuitabilityStatus.PASS,
        decision=SuitabilityDecision.REJECT if failed else SuitabilityDecision.ALLOW,
        effective_risk_limit=customer_gate.effective_risk_limit,
        high_risk_cap=customer_gate.high_risk_cap,
        checks=checks,
        failed_check_codes=failed,
        explanation=(
            "请求包含不匹配的风险、期限、流动性、复杂度、金额、集中度或杠杆条件。"
            if failed
            else "所选模拟产品通过当前客户与目标条件校验。"
        ),
    )
