from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.enums import (
    SuitabilityDecision,
    SuitabilityGateType,
    SuitabilityStatus,
)
from app.domain.financial import HouseholdFacts
from app.schemas.portfolio import (
    AllocationLine,
    ProductMapping,
    ProductOut,
    SuitabilityCheckItem,
    SuitabilityGateResult,
)
from app.services.financial.utils import ZERO, money
from app.services.portfolio.rules import PortfolioRules
from app.services.portfolio.suitability import complexity_cap, risk_rank


def _product_priority(product: ProductOut) -> int:
    value = product.terms.get("priority", 50)
    return value if isinstance(value, int) else 50


def _eligible_products(
    products: list[ProductOut],
    asset_class: str,
    allocation_amount: Decimal,
    horizon_months: int,
    customer_gate: SuitabilityGateResult,
    facts: HouseholdFacts,
    rules: PortfolioRules,
    analysis_date: date,
) -> list[ProductOut]:
    effective_risk = customer_gate.effective_risk_limit
    knowledge = facts.risk_assessments[-1].knowledge_score if facts.risk_assessments else ZERO
    allowed_complexity = complexity_cap(knowledge)
    complexity_order = rules.suitability.complexity_order
    result: list[ProductOut] = []
    for product in products:
        if product.asset_class != asset_class:
            continue
        if not product.enabled or product.education_only or product.professional_only:
            continue
        if product.sale_status != "available":
            continue
        if "long_term_growth" not in product.suitable_accounts:
            continue
        if effective_risk is None or risk_rank(product.risk_level, rules) > risk_rank(
            effective_risk,
            rules,
        ):
            continue
        if product.minimum_holding_months > horizon_months:
            continue
        if product.lock_up and (
            product.withdrawable_date is None or product.withdrawable_date > analysis_date
        ):
            continue
        if allocation_amount > 0 and product.minimum_investment > allocation_amount:
            continue
        if complexity_order.index(product.complexity_level) > complexity_order.index(
            allowed_complexity
        ):
            continue
        result.append(product)
    return sorted(
        result,
        key=lambda item: (
            _product_priority(item),
            item.annual_fee_rate,
            item.code,
        ),
    )


def map_products(
    allocations: list[AllocationLine],
    products: list[ProductOut],
    amount: Decimal,
    horizon_months: int,
    family_gate: SuitabilityGateResult,
    customer_gate: SuitabilityGateResult,
    facts: HouseholdFacts,
    rules: PortfolioRules,
    *,
    analysis_date: date,
    catalog_executable: bool,
) -> list[ProductMapping]:
    mappings: list[ProductMapping] = []
    maximum = (
        rules.suitability.maximum_single_product_ratio
        if amount > 0 and family_gate.status == SuitabilityStatus.PASS
        else Decimal("1")
    )
    for allocation in allocations:
        if allocation.ratio <= 0:
            continue
        eligible = _eligible_products(
            products,
            allocation.asset_class,
            allocation.amount,
            horizon_months,
            customer_gate,
            facts,
            rules,
            analysis_date,
        )
        if not eligible:
            mappings.append(
                ProductMapping(
                    asset_class=allocation.asset_class,
                    asset_class_name=allocation.asset_class_name,
                    allocation_ratio=allocation.ratio,
                    allocation_amount=allocation.amount,
                    product_id=None,
                    product_code=None,
                    product_name="无适配模拟产品类型",
                    product_type="unmatched",
                    risk_level=None,
                    liquidity_level=None,
                    decision=SuitabilityDecision.REJECT,
                    reasons=["风险、期限、复杂度、最低金额或账户用途没有同时匹配"],
                )
            )
            continue
        remaining = allocation.ratio
        index = 0
        while remaining > 0:
            if index >= len(eligible):
                mappings.append(
                    ProductMapping(
                        asset_class=allocation.asset_class,
                        asset_class_name=allocation.asset_class_name,
                        allocation_ratio=remaining,
                        allocation_amount=money(amount * remaining),
                        product_id=None,
                        product_code=None,
                        product_name="超过单产品集中度后的未匹配部分",
                        product_type="unmatched_concentration",
                        risk_level=None,
                        liquidity_level=None,
                        decision=SuitabilityDecision.REJECT,
                        reasons=[f"单产品最多 {maximum:.0%}，可用模拟类型不足以分散"],
                    )
                )
                break
            product = eligible[index]
            share = min(remaining, maximum)
            product_amount = money(amount * share)
            if amount > 0 and product_amount < product.minimum_investment:
                index += 1
                continue
            if not catalog_executable:
                decision = SuitabilityDecision.EDUCATION_ONLY
                reasons = ["产品快照已过期，禁止生成可执行购买建议"]
            elif family_gate.status != SuitabilityStatus.PASS or amount <= 0:
                decision = SuitabilityDecision.EDUCATION_ONLY
                reasons = ["家庭安全闸门未通过或没有可执行长期金额，只展示产品类型教育"]
            elif customer_gate.status != SuitabilityStatus.PASS:
                decision = SuitabilityDecision.DOWNGRADE
                reasons = ["候选风险高于客户上限，映射只用于降级后的复核"]
            else:
                decision = SuitabilityDecision.ALLOW
                reasons = ["风险、期限、流动性、复杂度、最低金额与账户用途匹配"]
            mappings.append(
                ProductMapping(
                    asset_class=allocation.asset_class,
                    asset_class_name=allocation.asset_class_name,
                    allocation_ratio=share,
                    allocation_amount=product_amount,
                    product_id=product.id,
                    product_code=product.code,
                    product_name=product.name,
                    product_type=product.product_type,
                    risk_level=product.risk_level,
                    liquidity_level=product.liquidity_level,
                    decision=decision,
                    reasons=reasons,
                )
            )
            remaining -= share
            index += 1
    return mappings


def product_gate_from_mappings(
    mappings: list[ProductMapping],
    family_gate: SuitabilityGateResult,
    customer_gate: SuitabilityGateResult,
) -> SuitabilityGateResult:
    checks = [
        SuitabilityCheckItem(
            check_code=f"mapping_{index + 1}_{item.asset_class}",
            label=item.product_name,
            status=(
                SuitabilityStatus.BLOCK
                if item.decision == SuitabilityDecision.REJECT
                else SuitabilityStatus.RESTRICT
                if item.decision
                in {SuitabilityDecision.DOWNGRADE, SuitabilityDecision.EDUCATION_ONLY}
                else SuitabilityStatus.PASS
            ),
            observed_value=(
                f"{item.asset_class_name} {item.allocation_ratio:.0%} / "
                f"{item.risk_level.value.upper() if item.risk_level else '未匹配'}"
            ),
            rule="产品风险、期限、流动性、复杂度、最低金额和单产品集中度必须同时匹配",
            reason="；".join(item.reasons),
            source_record_ids=[item.product_id] if item.product_id else [],
        )
        for index, item in enumerate(mappings)
    ]
    failures = [item.check_code for item in checks if item.status == SuitabilityStatus.BLOCK]
    restrictions = [item.check_code for item in checks if item.status == SuitabilityStatus.RESTRICT]
    if failures:
        status = SuitabilityStatus.BLOCK
        decision = SuitabilityDecision.REJECT
        explanation = "至少一项资产类别没有通过产品类型匹配，候选不可执行。"
    elif family_gate.status != SuitabilityStatus.PASS:
        status = SuitabilityStatus.RESTRICT
        decision = SuitabilityDecision.EDUCATION_ONLY
        explanation = "产品类型仅作教育展示；家庭安全闸门仍优先。"
    elif customer_gate.status != SuitabilityStatus.PASS or restrictions:
        status = SuitabilityStatus.RESTRICT
        decision = SuitabilityDecision.DOWNGRADE
        explanation = "产品类型需要按客户风险上限降级并重新复核。"
    else:
        status = SuitabilityStatus.PASS
        decision = SuitabilityDecision.ALLOW
        explanation = "所有已分配资产类别均找到通过适当性和集中度检查的模拟产品类型。"
    return SuitabilityGateResult(
        gate=SuitabilityGateType.PRODUCT,
        name="产品适当性闸门",
        status=status,
        decision=decision,
        effective_risk_limit=customer_gate.effective_risk_limit,
        high_risk_cap=customer_gate.high_risk_cap,
        checks=checks,
        failed_check_codes=[*failures, *restrictions],
        explanation=explanation,
    )
