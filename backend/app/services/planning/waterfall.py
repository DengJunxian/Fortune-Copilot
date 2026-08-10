from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import AccountBucket, AssetCategory, GoalRigidity, RiskLevel
from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import FinancialAnalysisResponse
from app.schemas.methodology import (
    AssetLiquiditySummary,
    ContributionPlan,
    CurrentAllocationPlan,
    MethodologyAssessment,
)
from app.schemas.planning import (
    AccountAllocation,
    ActionDraft,
    AppliedCounterfactual,
    ConstraintResult,
    DenominatorId,
    DenominatorSummary,
    GoalConflict,
    GoalProjection,
    GrowthBenchmark,
    GrowthEligibility,
    InvestmentLearningPlan,
    LifecycleAssessment,
    RatioMeasure,
    ReferenceBand,
    WaterfallStatus,
    WaterfallStep,
)
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import ZERO, format_money, money, safe_ratio
from app.services.methodology.models import MethodologyRules
from app.services.planning.cashflow import DeterministicDailyLiquidityPolicy
from app.services.planning.rules import PlanningRules


def _step_status(required: Decimal, allocated: Decimal) -> WaterfallStatus:
    if required == ZERO:
        return "informational"
    if allocated >= required:
        return "covered"
    if allocated > ZERO:
        return "partial"
    return "unfunded"


def _allocate(required: Decimal, remaining: Decimal) -> tuple[Decimal, Decimal]:
    allocated = money(min(max(ZERO, required), max(ZERO, remaining)))
    return allocated, money(max(ZERO, remaining - allocated))


def _measures(
    amount: Decimal,
    total_assets: Decimal,
    investable_assets: Decimal,
    annual_surplus: Decimal,
    residual_long_term_capital: Decimal = ZERO,
) -> list[RatioMeasure]:
    definitions: tuple[tuple[DenominatorId, str, Decimal, bool], ...] = (
        ("total_household_assets", "家庭总资产", total_assets, False),
        ("investable_financial_assets", "可投资金融资产", investable_assets, False),
        (
            "residual_long_term_plannable_capital",
            "完成前置安排后的长期可规划资源",
            residual_long_term_capital,
            False,
        ),
        ("total_assets", "家庭总资产（兼容字段）", total_assets, True),
        ("annual_new_surplus", "年度新增结余（流量观察）", annual_surplus, True),
    )
    return [
        RatioMeasure(
            denominator_id=code,
            denominator_name=name,
            denominator_value=denominator,
            ratio=safe_ratio(amount, denominator),
            applicable=denominator > ZERO,
            reason=(
                f"{format_money(amount)} ÷ {format_money(denominator)}"
                if denominator > ZERO
                else f"{name}为 0，比例不适用"
            ),
            deprecated=deprecated,
        )
        for code, name, denominator, deprecated in definitions
    ]


def _current_account_amounts(
    facts: HouseholdFacts,
    financial_rules: FinancialRules,
    adjustments: AppliedCounterfactual,
    analysis_date: date,
) -> tuple[
    Decimal,
    Decimal,
    Decimal,
    list[str],
    list[str],
    list[str],
    AssetLiquiditySummary,
]:
    investable_categories = set(
        financial_rules.classification.investable_financial_asset_categories
    )
    investable = [asset for asset in facts.assets if asset.category.value in investable_categories]
    institutional_assets = [
        asset
        for asset in facts.assets
        if asset.category == AssetCategory.PENSION_ACCOUNT
        or asset.account_wrapper.value
        in {
            "personal_pension",
            "social_security",
            "enterprise_annuity",
            "occupational_annuity",
            "provident_fund",
        }
    ]
    institutional_ids = {asset.id for asset in institutional_assets}
    reallocatable = [
        asset for asset in investable if not asset.lock_up and asset.id not in institutional_ids
    ]
    daily_assets = [
        asset for asset in reallocatable if asset.liquidity_days == 0
    ]
    stable_assets = [
        asset
        for asset in reallocatable
        if asset not in daily_assets
        and asset.risk_level in {RiskLevel.LOW, RiskLevel.MEDIUM_LOW}
    ]
    growth_assets = [
        asset
        for asset in reallocatable
        if asset not in daily_assets and asset not in stable_assets
    ]
    locked_institutional = [
        asset
        for asset in institutional_assets
        if asset.lock_up
        or asset.withdrawable_date is None
        or asset.withdrawable_date > analysis_date
    ]
    withdrawable_institutional = [
        asset
        for asset in institutional_assets
        if asset not in locked_institutional
        and asset.liquidity_days <= financial_rules.classification.twelve_month_liquid_max_days
    ]
    daily = money(sum((asset.market_value for asset in daily_assets), ZERO))
    eligible_withdrawable_institutional = [
        asset
        for asset in withdrawable_institutional
        if asset.category.value in investable_categories
    ]
    stable = money(
        sum((asset.market_value for asset in stable_assets), ZERO)
        + sum((asset.market_value for asset in eligible_withdrawable_institutional), ZERO)
    )
    growth = money(sum((asset.market_value for asset in growth_assets), ZERO))

    # Counterfactual additions represent re-labelling existing investable money, not new wealth.
    emergency_shift = min(adjustments.emergency_fund_addition, stable + growth)
    from_growth = min(growth, emergency_shift)
    growth = money(growth - from_growth)
    from_stable = emergency_shift - from_growth
    stable = money(stable - from_stable)
    daily = money(daily + emergency_shift)

    goal_shift = min(sum(adjustments.goal_prepared_additions.values(), ZERO), growth)
    growth = money(growth - goal_shift)
    stable = money(stable + goal_shift)
    return (
        daily,
        stable,
        growth,
        [asset.id for asset in daily_assets],
        [asset.id for asset in stable_assets + eligible_withdrawable_institutional],
        [asset.id for asset in growth_assets],
        AssetLiquiditySummary(
            daily_liquid_assets=daily,
            liquid_stable_assets=money(
                sum((asset.market_value for asset in stable_assets), ZERO)
            ),
            withdrawable_institutional_assets=money(
                sum((asset.market_value for asset in withdrawable_institutional), ZERO)
            ),
            locked_institutional_assets=money(
                sum((asset.market_value for asset in locked_institutional), ZERO)
            ),
            growth_assets=growth,
            locked_asset_ids=[asset.id for asset in locked_institutional],
            withdrawable_asset_ids=[asset.id for asset in withdrawable_institutional],
            explanation=(
                "只有已合法可领取且实际赎回期满足短期责任的制度账户才进入流动稳定资产；"
                "锁定个人养老金不满足日用、应急或近期刚性目标。"
            ),
        ),
    )


def build_waterfall(
    facts: HouseholdFacts,
    financial: FinancialAnalysisResponse,
    financial_rules: FinancialRules,
    rules: PlanningRules,
    lifecycle: LifecycleAssessment,
    goals: list[GoalProjection],
    conflicts: list[GoalConflict],
    adjustments: AppliedCounterfactual,
    methodology: MethodologyAssessment,
    methodology_rules: MethodologyRules,
) -> tuple[
    DenominatorSummary,
    list[WaterfallStep],
    list[ConstraintResult],
    list[AccountAllocation],
    InvestmentLearningPlan,
    GrowthEligibility,
    GrowthBenchmark,
    list[ActionDraft],
    AssetLiquiditySummary,
    CurrentAllocationPlan,
    ContributionPlan,
]:
    statements = financial.statements
    annual_surplus = money(
        max(ZERO, statements.cash_flow.annual_surplus)
        + adjustments.monthly_savings_increase * Decimal("12")
    )
    total_assets = statements.balance_sheet.total_assets
    investable_categories = set(
        financial_rules.classification.investable_financial_asset_categories
    )
    investable_assets = money(
        sum(
            (
                asset.market_value
                for asset in facts.assets
                if asset.category.value in investable_categories
            ),
            ZERO,
        )
    )
    total_liabilities = statements.balance_sheet.total_liabilities
    net_financial_assets = money(investable_assets - total_liabilities)
    growth_entry_threshold = methodology.regional_threshold.effective_threshold
    high_interest_before = money(
        sum(
            (
                liability.outstanding_balance
                for liability in facts.liabilities
                if liability.is_high_interest
            ),
            ZERO,
        )
    )
    debt_reduction = min(adjustments.high_interest_debt_reduction, high_interest_before)
    high_interest_after = money(high_interest_before - debt_reduction)
    annual_premium = statements.insurance.total_annual_premium
    current_balance_available = money(max(ZERO, investable_assets - debt_reduction))

    monthly_essential = money(statements.cash_flow.annual_essential_expenses / Decimal("12"))
    daily_forecast = DeterministicDailyLiquidityPolicy(
        methodology_rules.daily_liquidity
    ).forecast(monthly_essential)
    daily_months = methodology_rules.daily_liquidity.operating_months
    daily_operations_required = daily_forecast.target_amount
    emergency_required = money(
        monthly_essential * max(ZERO, lifecycle.dynamic_safety_months - daily_months)
    )
    short_term_goals = [
        goal
        for goal in goals
        if goal.months_remaining <= rules.goals.short_term_months
        and (goal.rigidity != GoalRigidity.FLEXIBLE.value or not goal.can_defer)
    ]
    short_term_gap = money(sum((goal.funding_gap for goal in short_term_goals), ZERO))
    certain_cashflow = money(min(annual_surplus, short_term_gap))
    short_term_net = money(max(ZERO, short_term_gap - certain_cashflow))
    daily_target = daily_operations_required
    future_contribution_available = money(max(ZERO, annual_surplus - certain_cashflow))
    resources = current_balance_available
    denominators = DenominatorSummary(
        total_assets=total_assets,
        total_household_assets=total_assets,
        investable_financial_assets=investable_assets,
        net_financial_assets_after_debt=net_financial_assets,
        plannable_financial_net_worth=net_financial_assets,
        growth_entry_threshold=growth_entry_threshold,
        residual_long_term_plannable_capital=ZERO,
        annual_new_surplus=annual_surplus,
        available_planning_resources=resources,
        high_interest_debt_before_plan=high_interest_before,
        high_interest_debt_after_counterfactual=high_interest_after,
        same_period_cashflow_committed=certain_cashflow,
    )

    stable_goals = [
        goal
        for goal in goals
        if rules.goals.short_term_months < goal.months_remaining <= rules.goals.stable_goal_months
        and (goal.rigidity != GoalRigidity.FLEXIBLE.value or not goal.can_defer)
    ]
    scheduled_non_high_debt_monthly = sum(
        (
            liability.monthly_payment
            for liability in facts.liabilities
            if not liability.is_high_interest
        ),
        ZERO,
    )
    debt_buffer = money(
        scheduled_non_high_debt_monthly * Decimal(rules.waterfall.debt_buffer_months)
    )
    stable_target = money(sum((goal.funding_gap for goal in stable_goals), ZERO) + debt_buffer)
    stable_minimum = money(
        sum((goal.minimum_funding_gap for goal in stable_goals), ZERO) + debt_buffer
    )

    steps: list[WaterfallStep] = []
    remaining = resources
    debt_allocated, remaining = _allocate(high_interest_after, remaining)
    steps.append(
        WaterfallStep(
            sequence=1,
            step_code="high_interest_debt",
            name="高息债务处理",
            required_amount=high_interest_after,
            allocated_amount=debt_allocated,
            remaining_resources=remaining,
            status=_step_status(high_interest_after, debt_allocated),
            formula="高息债务未偿余额 − 已完成的反事实偿还",
            explanation="高息债务优先于任何新增长期增长安排。",
            source_record_ids=[item.id for item in facts.liabilities if item.is_high_interest],
        )
    )
    daily_allocated, remaining = _allocate(daily_operations_required, remaining)
    steps.append(
        WaterfallStep(
            sequence=2,
            step_code="daily_operations",
            name="日常资金",
            required_amount=daily_operations_required,
            allocated_amount=daily_allocated,
            remaining_resources=remaining,
            status=_step_status(daily_operations_required, daily_allocated),
            formula="月必要支出 × 日常周转月数",
            explanation="日常支付和确定性账单优先，不按总资产固定 10%。",
            source_record_ids=[
                item.id for item in facts.expenses if item.necessity.value == "essential"
            ],
        )
    )
    emergency_allocated, remaining = _allocate(emergency_required, remaining)
    steps.append(
        WaterfallStep(
            sequence=3,
            step_code="emergency_reserve",
            name="应急储备",
            required_amount=emergency_required,
            allocated_amount=emergency_allocated,
            remaining_resources=remaining,
            status=_step_status(emergency_required, emergency_allocated),
            formula="月必要支出 × (动态安全月数 − 日常周转月数)",
            explanation=f"动态安全月数为 {lifecycle.dynamic_safety_months} 月。",
            source_record_ids=[item.id for item in facts.incomes]
            + [item.id for item in facts.members],
        )
    )
    protection_allocated = annual_premium
    steps.append(
        WaterfallStep(
            sequence=4,
            step_code="necessary_protection_cost",
            name="必要保障成本",
            required_amount=annual_premium,
            allocated_amount=protection_allocated,
            remaining_resources=remaining,
            status="cashflow_covered",
            formula="当前有效保单年度保费；保障缺口单独展示，不用保额反推产品价格",
            explanation="年度结余已经扣除已记录保费，因此资源池先加回保费再按本步骤列示，避免遗漏或重复扣减。",
            source_record_ids=[item.id for item in facts.insurance_policies],
        )
    )
    short_term_allocated, remaining = _allocate(short_term_net, remaining)
    short_term_total_covered = money(certain_cashflow + short_term_allocated)
    steps.append(
        WaterfallStep(
            sequence=5,
            step_code="twelve_month_commitments",
            name="一年内确定支出",
            required_amount=short_term_gap,
            allocated_amount=short_term_total_covered,
            remaining_resources=remaining,
            status=(
                "cashflow_covered"
                if short_term_gap > ZERO and certain_cashflow >= short_term_gap
                else _step_status(short_term_gap, short_term_total_covered)
            ),
            formula=("一年内刚性目标现值缺口；先用同期确定现金流，余额进入保本目标层"),
            explanation=(
                f"同期新增结余最多抵扣 {format_money(certain_cashflow)}，不抵扣基础应急储备。"
            ),
            source_record_ids=[goal.goal_id for goal in short_term_goals],
        )
    )
    stable_allocated, remaining = _allocate(stable_target, remaining)
    steps.append(
        WaterfallStep(
            sequence=6,
            step_code="one_to_five_year_goals",
            name="一至五年刚性目标",
            required_amount=stable_target,
            allocated_amount=stable_allocated,
            remaining_resources=remaining,
            status=_step_status(stable_target, stable_allocated),
            formula="五年内目标现值 − 已准备资金 + 一个月债务缓冲",
            explanation="可延期的柔性目标不会被伪装成短期刚性资金。",
            source_record_ids=[goal.goal_id for goal in stable_goals]
            + [item.id for item in facts.liabilities if not item.is_high_interest],
        )
    )
    raw_growth = remaining
    stable_account_target = money(emergency_required + short_term_net + stable_target)
    active_market_regime = methodology.market_regime.regime
    market_profile = rules.market_environment.profiles[active_market_regime]
    market_stable_anchor = money(
        investable_assets * Decimal(market_profile.stable_target_ratio)
    )
    stable_core_allocated = money(
        emergency_allocated + short_term_allocated + stable_allocated
    )
    market_holdback = money(
        min(raw_growth, max(ZERO, market_stable_anchor - stable_core_allocated))
    )
    market_adjusted_growth = money(max(ZERO, raw_growth - market_holdback))
    denominators = denominators.model_copy(
        update={"residual_long_term_plannable_capital": raw_growth}
    )

    (
        current_daily,
        current_stable,
        current_growth,
        daily_ids,
        stable_ids,
        growth_ids,
        asset_liquidity,
    ) = (
        _current_account_amounts(
            facts,
            financial_rules,
            adjustments,
            financial.meta.analysis_date,
        )
    )
    effective_protection_gap = money(
        max(ZERO, financial.protection.protection_gap - adjustments.protection_gap_reduction)
    )
    significant_risk = next(
        (
            risk
            for risk in financial.protection.risks
            if risk.risk_code == financial.protection.most_significant_risk
        ),
        None,
    )
    protection_required = money(significant_risk.required_amount if significant_risk else ZERO)
    effective_coverage_ratio = (
        safe_ratio(
            max(ZERO, protection_required - effective_protection_gap),
            protection_required,
        )
        if protection_required > ZERO
        else Decimal("1")
    )
    capital_threshold_pass = net_financial_assets >= growth_entry_threshold
    liquidity_pass = current_daily >= daily_target and (
        current_daily + current_stable >= daily_target + emergency_required + short_term_net
    )
    debt_pass = high_interest_after == ZERO
    protection_pass = effective_protection_gap == ZERO or (
        effective_coverage_ratio is not None
        and effective_coverage_ratio >= Decimal(rules.waterfall.protection_coverage_pass_ratio)
    )
    horizon_pass = (
        current_daily + current_stable >= daily_target + stable_account_target
    )
    latest_risk = facts.risk_assessments[-1] if facts.risk_assessments else None
    suitability_pass = bool(
        latest_risk
        and latest_risk.final_risk_limit.value in rules.waterfall.suitability_pass_levels
        and latest_risk.capacity_score >= Decimal("0.40")
    )
    latest_behavior = facts.behavior_assessments[-1] if facts.behavior_assessments else None
    behavior_level = (
        latest_behavior.final_behavior_limit.value
        if latest_behavior
        else RiskLevel.MEDIUM_LOW.value
    )
    behavior_factor = Decimal(
        rules.waterfall.behavior_growth_factors.get(behavior_level, "0.750000")
    )

    constraints = [
        ConstraintResult(
            constraint_id="capital_threshold",
            constraint_type="hard",
            name="长期资金启动门槛",
            status="pass" if capital_threshold_pass else "block",
            observed_value=(
                f"可规划金融净值 {format_money(net_financial_assets)}"
            ),
            required_condition=(
                f"达到客户确认的地区与稳定性门槛 {format_money(growth_entry_threshold)}"
            ),
            effect=(
                "达到启动门槛，可继续核对其余安全条件。"
                if capital_threshold_pass
                else (
                    "正式配置暂不启动；年度结余、债务和适当性条件允许时，"
                    "可从完成前置安排后的多余长期资金中设置不超过10%的学习仓。"
                )
            ),
            limits_growth=not capital_threshold_pass,
            source_record_ids=[item.id for item in facts.assets]
            + [item.id for item in facts.liabilities],
        ),
        ConstraintResult(
            constraint_id="liquidity",
            constraint_type="hard",
            name="流动性约束",
            status="pass" if liquidity_pass else "block",
            observed_value=(
                f"当前日用资产 {format_money(current_daily)}；"
                f"当前日用与保本资金 {format_money(current_daily + current_stable)}"
            ),
            required_condition=(
                f"日常周转 {format_money(daily_target)}；"
                "含应急和一年内目标共 "
                f"{format_money(daily_target + emergency_required + short_term_net)}"
            ),
            effect=(
                "流动性已满足。" if liquidity_pass else "阻止把尚未补足的安全资金转入长期增长。"
            ),
            limits_growth=not liquidity_pass,
            source_record_ids=daily_ids,
        ),
        ConstraintResult(
            constraint_id="debt",
            constraint_type="hard",
            name="偿债约束",
            status="pass" if debt_pass else "block",
            observed_value=f"反事实后高息债务 {format_money(high_interest_after)}",
            required_condition="高息债务已实际清零",
            effect=("未发现待处理高息债务。" if debt_pass else "高息债务先于增长账户处理。"),
            limits_growth=not debt_pass,
            source_record_ids=[item.id for item in facts.liabilities if item.is_high_interest],
        ),
        ConstraintResult(
            constraint_id="protection",
            constraint_type="hard",
            name="保障约束",
            status="pass" if protection_pass else "block",
            observed_value=f"有效保障缺口 {format_money(effective_protection_gap)}",
            required_condition=(
                f"主要风险覆盖率达到 "
                f"{Decimal(rules.waterfall.protection_coverage_pass_ratio) * 100:.0f}%"
            ),
            effect=(
                "主要不可承受风险已达到当前规则的安全条件。"
                if protection_pass
                else "先核对保障需求与持续缴费能力，不反推具体产品。"
            ),
            limits_growth=not protection_pass,
            source_record_ids=[item.id for item in facts.insurance_policies],
        ),
        ConstraintResult(
            constraint_id="horizon",
            constraint_type="hard",
            name="期限约束",
            status="pass" if horizon_pass else "block",
            observed_value=(
                f"当前日用 {format_money(current_daily)}；"
                f"当前保本目标资金 {format_money(current_stable)}"
            ),
            required_condition=(
                f"日用目标 {format_money(daily_target)}；"
                f"应急、近期和五年内目标 {format_money(stable_account_target)}"
            ),
            effect=("近期目标资金期限匹配。" if horizon_pass else "近期目标缺口限制长期资产暴露。"),
            limits_growth=not horizon_pass,
            source_record_ids=[goal.goal_id for goal in short_term_goals + stable_goals],
        ),
        ConstraintResult(
            constraint_id="suitability",
            constraint_type="hard",
            name="适当性约束",
            status="pass" if suitability_pass else "block",
            observed_value=(
                f"风险能力 {latest_risk.capacity_score}，"
                f"审慎上限 {latest_risk.final_risk_limit.value}"
                if latest_risk
                else "缺少风险能力评估"
            ),
            required_condition="风险能力不低于 0.40 且审慎上限不低于 medium",
            effect=(
                "账户级适当性条件已通过，具体产品仍需逐项匹配。"
                if suitability_pass
                else "缺少或未通过风险能力条件，长期增长被限制。"
            ),
            limits_growth=not suitability_pass,
            source_record_ids=[latest_risk.id] if latest_risk else [],
        ),
        ConstraintResult(
            constraint_id="behavior",
            constraint_type="soft",
            name="行为承受力修正",
            status="pass" if behavior_factor == Decimal("1") else "limit",
            observed_value=f"行为上限 {behavior_level}，修正系数 {behavior_factor}",
            required_condition="行为承受力不会覆盖客观安全约束，只能下调增长建议",
            effect=(
                "不额外下调。"
                if behavior_factor == Decimal("1")
                else "对约束后的增长上限继续审慎下调。"
            ),
            limits_growth=behavior_factor < Decimal("1"),
            source_record_ids=[latest_behavior.id] if latest_behavior else [],
        ),
    ]
    failed_hard = [
        item for item in constraints if item.constraint_type == "hard" and item.status != "pass"
    ]
    learning_cap_ratio = Decimal(rules.waterfall.learning_growth_cap)
    learning_applicable = not capital_threshold_pass
    learning_conditions = [
        "可规划金融净值尚未达到客户确认的正式启动线",
        "年度新增结余为正",
        "日常、应急与近期刚性责任已有可用流动资金",
        "完成债务安排和家庭责任后仍有多余长期资金",
        "没有待处理的高息债务",
        "风险能力与审慎上限通过长期投资适当性条件",
    ]
    learning_failed_conditions: list[str] = []
    if annual_surplus <= ZERO:
        learning_failed_conditions.append("年度新增结余不为正")
    if market_adjusted_growth <= ZERO:
        learning_failed_conditions.append("完成前置安排后没有多余长期资金")
    if not liquidity_pass or not horizon_pass:
        learning_failed_conditions.append("日常、应急或近期刚性责任尚未完整备资")
    if not debt_pass:
        learning_failed_conditions.append("仍有待处理的高息债务")
    if not suitability_pass:
        learning_failed_conditions.append("长期投资适当性条件未通过")
    learning_eligible = bool(
        learning_applicable and not learning_failed_conditions
    )
    learning_cap_amount = money(raw_growth * learning_cap_ratio)

    if learning_applicable:
        hard_cap = learning_cap_amount if learning_eligible else ZERO
        constrained_growth = money(hard_cap * behavior_factor)
    else:
        hard_cap = ZERO if failed_hard else market_adjusted_growth
        constrained_growth = money(min(market_adjusted_growth, hard_cap) * behavior_factor)
    safety_holdback = money(max(ZERO, market_adjusted_growth - constrained_growth))
    stable_recommended = money(
        stable_core_allocated + market_holdback + safety_holdback
    )
    growth_allocated = constrained_growth
    learning_ratio = (
        safe_ratio(growth_allocated, raw_growth)
        if learning_applicable and raw_growth > ZERO
        else None
    )
    learning_percent = (learning_ratio or ZERO) * Decimal("100")
    investment_learning = InvestmentLearningPlan(
        applicable=learning_applicable,
        eligible=learning_eligible,
        cap_ratio=learning_cap_ratio,
        recommended_ratio=learning_ratio,
        recommended_amount=growth_allocated if learning_applicable else ZERO,
        denominator_name="完成前置安排与市场留存后的多余长期资金",
        denominator_value=raw_growth,
        conditions=learning_conditions,
        failed_conditions=learning_failed_conditions,
        explanation=(
            (
                f"正式启动线尚未达到，本次可用 {format_money(growth_allocated)} "
                "作为宽基指数基金学习仓，"
                f"占多余长期资金 {learning_percent:.1f}%，"
                f"不超过 {learning_cap_ratio * Decimal('100'):.0f}% 上限。"
                "这笔钱用于学习波动、费率和持有纪律，不以短期盈利为任务。"
            )
            if learning_eligible
            else (
                "正式启动线尚未达到，当前也不满足小额学习仓条件："
                f"{'、'.join(learning_failed_conditions)}。"
                if learning_applicable
                else "已达到正式启动线，本次按完整长期配置条件评估，不适用小额学习仓规则。"
            )
        ),
    )
    remaining_after_growth = money(
        max(
            ZERO,
            raw_growth - growth_allocated - market_holdback - safety_holdback,
        )
    )
    steps.append(
        WaterfallStep(
            sequence=7,
            step_code="remaining_long_term_resources",
            name="剩余长期资金",
            required_amount=raw_growth,
            allocated_amount=growth_allocated,
            remaining_resources=remaining_after_growth,
            status="covered" if growth_allocated == raw_growth else "partial",
            formula=(
                "max(0, 可规划资源 - 债务 - 日用层 - 保障成本 - 保本目标层)，"
                "先应用市场战术留存；正式启动线以下仅按学习仓上限与行为系数计算"
            ),
            explanation=(
                f"原始剩余 {format_money(raw_growth)}；"
                f"{market_profile.label}市场口径留存 {format_money(market_holdback)}；"
                + (
                    f"小额学习仓 {format_money(growth_allocated)}；"
                    if learning_applicable and learning_eligible
                    else f"约束后增长 {format_money(growth_allocated)}；"
                )
                + f"安全留存 {format_money(safety_holdback)} 回流保本账户。"
            ),
            source_record_ids=[item.id for item in facts.assets],
        )
    )

    daily_recommended = daily_allocated
    protection_recommended = protection_allocated
    growth_target_amount = (
        learning_cap_amount if learning_eligible else ZERO
    ) if learning_applicable else raw_growth
    growth_product_education = list(
        rules.product_education[AccountBucket.LONG_TERM_GROWTH.value]
    )
    if learning_eligible:
        growth_product_education.insert(
            0,
            "学习仓只承担认识宽基指数基金净值波动、费率与持有纪律的任务；不追涨，不借钱，不把10%上限当成必须用满的目标。",
        )
        growth_formula = (
            "完成前置安排与市场留存后的多余长期资金 × 10%学习仓上限 × 行为承受力系数"
        )
        growth_substitution = (
                f"长期可规划资源 {format_money(raw_growth)} × "
            f"{learning_cap_ratio * Decimal('100'):.0f}% × {behavior_factor} = "
            f"{format_money(growth_allocated)}"
        )
        growth_rationale = (
            "尚未达到正式配置启动线，本次只保留不超过多余长期资金10%的学习仓；"
            "可从与风险承受能力匹配的宽基指数基金开始认识波动，不以短期盈利为任务。"
        )
    elif learning_applicable:
        growth_formula = "正式启动线以下先核验年度结余、债务、多余长期资金和适当性条件"
        growth_substitution = f"学习仓条件未通过，建议 {format_money(growth_allocated)}"
        growth_rationale = (
            "尚未达到正式配置启动线，且当前不满足小额学习仓条件；"
            "先处理现金流、债务或适当性问题。"
        )
    else:
        growth_formula = (
            "max(0, 可投资资源 - 日用层 - 保本目标层 - 必要保障成本)，"
            "再受启动门槛与适当性约束"
        )
        growth_substitution = (
            f"原始 {format_money(raw_growth)}；"
            f"硬约束上限 {format_money(hard_cap)}；"
            f"行为系数 {behavior_factor}；建议 {format_money(growth_allocated)}"
        )
        growth_rationale = (
            "达到客户确认门槛后，长期资金仍须接受安全与适当性约束；"
            "普通家庭以宽基指数和分散化工具为主，不默认推荐个股、杠杆或期指。"
        )
    daily_min = money(
        max(
            methodology_rules.daily_liquidity.minimum_amount,
            daily_target * Decimal("0.75"),
        )
    )
    daily_max = money(
        min(
            methodology_rules.daily_liquidity.maximum_amount,
            daily_target * Decimal("1.25"),
        )
    )
    account_specs = [
        AccountAllocation(
            bucket=AccountBucket.DAILY_LIQUIDITY,
            name="要花的钱",
            methodology_domain="DAILY_LIQUIDITY",
            sequence=1,
            current_amount=current_daily,
            target_amount=daily_target,
            recommended_amount=daily_recommended,
            recommended_range_min=daily_min,
            recommended_range_max=daily_max,
            gap_amount=money(max(ZERO, daily_target - current_daily)),
            annual_cost_amount=ZERO,
            coverage_gap_amount=ZERO,
            primary_denominator_name="可投资金融资产",
            primary_denominator_id="investable_financial_assets",
            reference_band=None,
            current_measures=_measures(
                current_daily, total_assets, investable_assets, annual_surplus, raw_growth
            ),
            target_measures=_measures(
                daily_target, total_assets, investable_assets, annual_surplus, raw_growth
            ),
            measures=_measures(
                daily_recommended,
                total_assets,
                investable_assets,
                annual_surplus,
                raw_growth,
            ),
            formula="月必要支出 × 版本化日常周转月数，再应用规则上下界",
            substitution=(
                f"{format_money(monthly_essential)} × {daily_months}，"
                f"再应用 {format_money(methodology_rules.daily_liquidity.minimum_amount)} "
                f"至 {format_money(methodology_rules.daily_liquidity.maximum_amount)} 的边界"
            ),
            rationale=(
                "只承担近期消费和结算，不按家庭总资产固定 10%；"
                "应急储备和近期大额支出进入保本目标层。"
            ),
            constraint_ids=["liquidity", "horizon"],
            source_record_ids=daily_ids + [goal.goal_id for goal in short_term_goals],
            product_education=rules.product_education[AccountBucket.DAILY_LIQUIDITY.value],
        ),
        AccountAllocation(
            bucket=AccountBucket.RISK_PROTECTION,
            name="保命的钱",
            methodology_domain="RISK_PROTECTION",
            sequence=2,
            current_amount=annual_premium,
            target_amount=annual_premium,
            recommended_amount=protection_recommended,
            recommended_range_min=protection_recommended,
            recommended_range_max=protection_recommended,
            gap_amount=ZERO,
            annual_cost_amount=annual_premium,
            coverage_gap_amount=effective_protection_gap,
            primary_denominator_name="可投资金融资产（仅用于结构解释）",
            primary_denominator_id="investable_financial_assets",
            reference_band=None,
            current_measures=_measures(
                annual_premium, total_assets, investable_assets, annual_surplus, raw_growth
            ),
            target_measures=_measures(
                annual_premium, total_assets, investable_assets, annual_surplus, raw_growth
            ),
            measures=_measures(
                protection_recommended,
                total_assets,
                investable_assets,
                annual_surplus,
                raw_growth,
            ),
            formula="已核验必要保障成本按年度保费列示；保障覆盖缺口独立列示",
            substitution=(
                f"年保费 {format_money(annual_premium)}；"
                f"保障缺口 {format_money(effective_protection_gap)}"
            ),
            rationale="不按家庭总资产百分比反推保费，也不把保额当作可投资资金。",
            constraint_ids=["protection"],
            source_record_ids=[item.id for item in facts.insurance_policies],
            product_education=rules.product_education[AccountBucket.RISK_PROTECTION.value],
        ),
        AccountAllocation(
            bucket=AccountBucket.STABLE_GOALS,
            name="保本的钱",
            methodology_domain="STABILITY_AND_GOALS",
            sequence=3,
            current_amount=current_stable,
            target_amount=stable_account_target,
            recommended_amount=stable_recommended,
            recommended_range_min=money(emergency_required + short_term_net + stable_minimum),
            recommended_range_max=money(
                max(
                    stable_account_target,
                    stable_recommended,
                    investable_assets * Decimal(market_profile.stable_reference_max),
                )
            ),
            gap_amount=money(max(ZERO, stable_account_target - current_stable)),
            annual_cost_amount=ZERO,
            coverage_gap_amount=ZERO,
            primary_denominator_name="可投资金融资产",
            primary_denominator_id="investable_financial_assets",
            reference_band=ReferenceBand(
                denominator_id=rules.waterfall.stable_reference_denominator,
                denominator_name="可投资金融资产",
                minimum_ratio=Decimal(market_profile.stable_reference_min),
                maximum_ratio=Decimal(market_profile.stable_reference_max),
                target_ratio=Decimal(market_profile.stable_target_ratio),
                overall_minimum_ratio=Decimal("0.050000"),
                overall_maximum_ratio=Decimal("0.300000"),
                market_regime=active_market_regime,
                market_regime_label=market_profile.label,
                binding=False,
                conditions=[
                    rules.market_environment.governance_note,
                    "分母为可投资金融资产，不是家庭总资产",
                    "目标现值、债务缓冲、安全留存和适当性约束优先于市场战术锚",
                ],
                explanation=(
                    f"当前采用{market_profile.label}市场口径："
                    f"{market_profile.explanation} 全周期总观察带为5%-30%，"
                    "本档区间和锚点均不是家庭总资产固定比例或产品承诺。"
                ),
            ),
            current_measures=_measures(
                current_stable, total_assets, investable_assets, annual_surplus, raw_growth
            ),
            target_measures=_measures(
                stable_account_target,
                total_assets,
                investable_assets,
                annual_surplus,
                raw_growth,
            ),
            measures=_measures(
                stable_recommended,
                total_assets,
                investable_assets,
                annual_surplus,
                raw_growth,
            ),
            formula=(
                "应急储备 + 一年内确定支出 + 五年内刚性目标 + "
                "债务缓冲 + 市场战术留存 + 安全留存"
            ),
            substitution=(
                f"{format_money(emergency_required)} + {format_money(short_term_net)} + "
                f"{format_money(stable_target - debt_buffer)} + {format_money(debt_buffer)} + "
                f"{format_money(market_holdback)} + {format_money(safety_holdback)}"
            ),
            rationale=(
                f"当前{market_profile.label}市场口径以可投资金融资产的"
                f"{Decimal(market_profile.stable_target_ratio) * 100:.1f}%作为战术锚；"
                "家庭目标和安全约束可覆盖该锚。"
                "\"保本的钱\"是家庭资金用途名称，不代表账户内所有产品保证本金。"
            ),
            constraint_ids=["debt", "horizon", "suitability", "behavior"],
            source_record_ids=stable_ids + [goal.goal_id for goal in stable_goals],
            product_education=rules.product_education[AccountBucket.STABLE_GOALS.value],
        ),
        AccountAllocation(
            bucket=AccountBucket.LONG_TERM_GROWTH,
            name="生钱的钱",
            methodology_domain="LONG_TERM_GROWTH",
            sequence=4,
            current_amount=current_growth,
            target_amount=growth_target_amount,
            recommended_amount=growth_allocated,
            recommended_range_min=ZERO,
            recommended_range_max=growth_target_amount,
            gap_amount=money(max(ZERO, growth_target_amount - growth_allocated)),
            annual_cost_amount=ZERO,
            coverage_gap_amount=ZERO,
            primary_denominator_name="完成前置安排后的长期可规划资源",
            primary_denominator_id="residual_long_term_plannable_capital",
            reference_band=None,
            current_measures=_measures(
                current_growth, total_assets, investable_assets, annual_surplus, raw_growth
            ),
            target_measures=_measures(
                growth_target_amount,
                total_assets,
                investable_assets,
                annual_surplus,
                raw_growth,
            ),
            measures=_measures(
                growth_allocated,
                total_assets,
                investable_assets,
                annual_surplus,
                raw_growth,
            ),
            formula=growth_formula,
            substitution=growth_substitution,
            rationale=growth_rationale,
            constraint_ids=[item.constraint_id for item in constraints],
            source_record_ids=growth_ids,
            product_education=growth_product_education,
        ),
    ]

    formal_growth_amount = ZERO if learning_applicable else growth_allocated
    growth_ratio = safe_ratio(formal_growth_amount, raw_growth)
    threshold = Decimal(rules.waterfall.growth_70_threshold)
    eligibility_conditions = [
        "可规划金融净值达到客户确认的 30万-100万元启动门槛",
        "流动性、偿债、保障、期限、适当性五项安全约束全部通过",
        "行为承受力未下调增长上限",
        "年度新增结余为正",
        "扣除优先层后仍有真实长期可规划资源",
    ]
    failed_conditions = [item.name for item in failed_hard]
    if behavior_factor < Decimal("1"):
        failed_conditions.append("行为承受力需要软修正")
    if annual_surplus <= ZERO:
        failed_conditions.append("年度新增结余不为正")
    if raw_growth <= ZERO:
        failed_conditions.append("没有剩余长期资源")
    eligible = bool(
        not failed_conditions and growth_ratio is not None and growth_ratio >= threshold
    )
    growth_ratio_percent = (
        growth_ratio * Decimal("100") if growth_ratio is not None else ZERO
    )
    if learning_applicable and learning_eligible:
        growth_explanation = (
            "当前仅安排小额学习仓，占“完成前置安排后的长期可规划资源”"
            f"{growth_ratio_percent:.1f}%。正式配置尚未启动，70%边界不适用于学习仓，"
            "更不得套用于家庭总资产。"
        )
    else:
        growth_explanation = (
            "当前增长建议占“完成前置安排后的长期可规划资源”"
            f"{growth_ratio_percent:.1f}%。"
            + (
                "满足 70% 展示条件。"
                if eligible
                else "不满足 70% 展示条件，不得套用于家庭总资产。"
            )
        )
    growth_70 = GrowthEligibility(
        eligible=eligible,
        threshold=threshold,
        actual_ratio=growth_ratio,
        denominator_name="完成日用、保障、近期目标和优先债务安排后的长期可规划资源",
        denominator_id="residual_long_term_plannable_capital",
        denominator_value=raw_growth,
        formal_growth_amount=formal_growth_amount,
        conditions=eligibility_conditions,
        failed_conditions=failed_conditions,
        explanation=growth_explanation,
    )

    pph = methodology.purchasing_power_hurdle
    benchmark_components = {item.label: item.rate for item in pph.components}
    growth_benchmark = GrowthBenchmark(
        benchmark_rate=pph.rate,
        components=benchmark_components,
        formula=pph.formula,
        explanation=pph.explanation,
    )

    actions: list[ActionDraft] = []
    priority = 1

    def action(
        code: str,
        title: str,
        detail: str,
        amount: Decimal,
        bucket: AccountBucket | None,
        ids: list[str],
        days: int | None = None,
    ) -> None:
        nonlocal priority
        actions.append(
            ActionDraft(
                priority=priority,
                action_code=code,
                title=title,
                detail=detail,
                amount=money(amount),
                due_date=(financial.meta.analysis_date + timedelta(days=days)) if days else None,
                account_bucket=bucket,
                source_record_ids=ids,
            )
        )
        priority += 1

    if high_interest_after > ZERO:
        action(
            "clear_high_interest_debt",
            "先清理高息债务",
            "在新增长期投资前核对计息规则并完成清偿。",
            high_interest_after,
            None,
            [item.id for item in facts.liabilities if item.is_high_interest],
            30,
        )
    if not capital_threshold_pass:
        action(
            "build_net_financial_base",
            "先达到长期资金启动门槛",
            (
                f"当前可规划金融净值为 {format_money(net_financial_assets)}，"
                f"客户确认门槛为 {format_money(growth_entry_threshold)}；"
                "达到前不启动正式长期配置，符合条件的小额学习仓除外。"
            ),
            money(max(ZERO, growth_entry_threshold - net_financial_assets)),
            AccountBucket.STABLE_GOALS,
            [item.id for item in facts.assets] + [item.id for item in facts.liabilities],
        )
    daily_gap = money(max(ZERO, daily_target - current_daily))
    if daily_gap > ZERO:
        action(
            "fill_daily_liquidity",
            "补足日常周转资金",
            "以近期消费所需的小额现金、活期存款或货币基金补齐，不使用信用卡额度。",
            daily_gap,
            AccountBucket.DAILY_LIQUIDITY,
            daily_ids,
            90,
        )
    if effective_protection_gap > ZERO:
        action(
            "review_protection_gap",
            "复核主要保障缺口",
            "先核对家庭责任和已有合同，再评估可持续保费；本行动不指定产品。",
            effective_protection_gap,
            AccountBucket.RISK_PROTECTION,
            [item.id for item in facts.insurance_policies],
            60,
        )
    stable_gap = money(max(ZERO, stable_account_target - current_stable))
    if stable_gap > ZERO:
        action(
            "fund_near_term_goals",
            "补足应急和五年内目标资金",
            "按应急需要和目标日期匹配期限，逐类核对本金风险与流动性。",
            stable_gap,
            AccountBucket.STABLE_GOALS,
            [goal.goal_id for goal in stable_goals],
            90,
        )
    if conflicts:
        action(
            "resolve_goal_conflict",
            "确认目标调整组合",
            conflicts[0].adjustments[0].detail,
            conflicts[0].monthly_shortfall,
            AccountBucket.STABLE_GOALS,
            conflicts[0].affected_goal_ids,
            30,
        )
    if behavior_factor < Decimal("1"):
        action(
            "behavior_guardrail",
            "先建立波动应对规则",
            "在增加长期风险暴露前确认下跌情景中的持有与再平衡纪律。",
            ZERO,
            AccountBucket.LONG_TERM_GROWTH,
            [latest_behavior.id] if latest_behavior else [],
        )
    if investment_learning.eligible:
        action(
            "start_index_learning",
            "用小仓位熟悉宽基指数基金",
            (
                f"本次学习仓为 {format_money(investment_learning.recommended_amount)}，"
                f"占多余长期资金 {learning_percent:.1f}%。"
                "先弄清指数覆盖范围、净值波动、费率和持有期限，再考虑是否分批投入；不追涨，也不借钱投资。"
            ),
            investment_learning.recommended_amount,
            AccountBucket.LONG_TERM_GROWTH,
            growth_ids,
        )
    if not actions and growth_allocated > ZERO:
        action(
            "allocate_eligible_growth",
            "分批安排长期合格资金",
            "完成具体产品适当性匹配后，再比较宽基指数和分散化候选方案。",
            growth_allocated,
            AccountBucket.LONG_TERM_GROWTH,
            growth_ids,
        )
    current_allocation_plan = CurrentAllocationPlan(
        current_investable_balance=investable_assets,
        debt_settlement_from_current_balance=money(debt_reduction + debt_allocated),
        current_balance_available_after_debt=money(
            max(ZERO, investable_assets - debt_reduction - debt_allocated)
        ),
        explanation=(
            "这是今天已存在的可投资金融资产；未来工资和年度结余不会加入该余额。"
        ),
    )
    contribution_plan = ContributionPlan(
        annual_new_surplus=annual_surplus,
        recorded_premium_reclassification=annual_premium,
        same_period_commitments=certain_cashflow,
        future_contribution_available=future_contribution_available,
        explanation=(
            "这是未来现金流贡献计划，不是今天可立即配置的资产存量；"
            "已记录保费仅用于流量口径解释，不与存量重复计数。"
        ),
    )
    return (
        denominators,
        steps,
        constraints,
        account_specs,
        investment_learning,
        growth_70,
        growth_benchmark,
        actions,
        asset_liquidity,
        current_allocation_plan,
        contribution_plan,
    )
