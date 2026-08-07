from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import GoalType, PropertyUse
from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import (
    FinancialStatements,
    HealthDimension,
    MetricApplicability,
    MetricInput,
    MetricResult,
    MetricStatus,
    ProtectionAssessment,
    ThresholdReference,
)
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import (
    ONE,
    ZERO,
    display_number,
    format_money,
    money,
    ratio,
    safe_ratio,
)


@dataclass(frozen=True, slots=True)
class MetricContext:
    facts: HouseholdFacts
    statements: FinancialStatements
    protection: ProtectionAssessment
    rules: FinancialRules
    data_as_of: date
    analysis_date: date


def _reference(context: MetricContext, code: str) -> ThresholdReference:
    rule = context.rules.threshold(code)
    return ThresholdReference(
        reference_range=rule.reference_range,
        source_type=rule.source_type,
        source_reference=rule.source_reference,
        parameters=rule.parameters,
    )


def _input(
    key: str,
    label: str,
    value: Decimal,
    unit: str,
    source_ids: list[str],
) -> MetricInput:
    return MetricInput(
        key=key,
        label=label,
        value=value,
        unit=unit,
        source_record_ids=source_ids,
    )


def _metric(
    context: MetricContext,
    *,
    metric_id: str,
    name: str,
    formula: str,
    substitution: str,
    inputs: list[MetricInput],
    result: Decimal | None,
    numerator: Decimal | None,
    denominator: Decimal | None,
    unit: str,
    status: MetricStatus,
    threshold_code: str,
    applicability_reason: str,
    explanation: str,
    actions: list[str],
) -> MetricResult:
    applicable = result is not None
    return MetricResult(
        metric_id=metric_id,
        name=name,
        formula=formula,
        substitution=substitution,
        inputs=inputs,
        result=result,
        numerator=numerator,
        denominator=denominator,
        unit=unit,
        threshold_version=(
            f"{context.rules.code}@{context.rules.semantic_version}:{threshold_code}"
        ),
        status=status if applicable else "not_applicable",
        explanation_key=f"metric.{metric_id}.{status if applicable else 'not_applicable'}",
        data_as_of=context.data_as_of,
        applicability=MetricApplicability(
            applicable=applicable,
            reason=applicability_reason,
        ),
        reference=_reference(context, threshold_code),
        explanation=explanation,
        actions=actions,
    )


def metric_total_assets(context: MetricContext) -> MetricResult:
    value = context.statements.balance_sheet.total_assets
    ids = [item.id for item in context.facts.assets]
    return _metric(
        context,
        metric_id="total_assets",
        name="家庭总资产",
        formula="所有已确认资产市值之和（不含信用卡额度）",
        substitution=" + ".join(format_money(item.market_value) for item in context.facts.assets)
        or "无资产记录",
        inputs=[_input("assets", "资产市值", value, "CNY", ids)],
        result=value,
        numerator=value,
        denominator=None,
        unit="CNY",
        status="review",
        threshold_code="measurement_only",
        applicability_reason="资产市值按当前有效记录汇总。",
        explanation="总资产是资产负债表的资产端合计，不代表可立即投资金额。",
        actions=["逐项确认估值日期、权属和是否存在重复资产。"],
    )


def metric_total_liabilities(context: MetricContext) -> MetricResult:
    value = context.statements.balance_sheet.total_liabilities
    ids = [item.id for item in context.facts.liabilities]
    return _metric(
        context,
        metric_id="total_liabilities",
        name="家庭总负债",
        formula="所有未偿负债余额之和",
        substitution=" + ".join(
            format_money(item.outstanding_balance) for item in context.facts.liabilities
        )
        or "0.00",
        inputs=[_input("liabilities", "未偿余额", value, "CNY", ids)],
        result=value,
        numerator=value,
        denominator=None,
        unit="CNY",
        status="review",
        threshold_code="measurement_only",
        applicability_reason="负债余额按当前有效记录汇总。",
        explanation="信用卡已发生未付金额计入负债；未使用授信额度不计入。",
        actions=["核对信用卡、消费贷和担保债务是否完整。"],
    )


def metric_net_worth(context: MetricContext) -> MetricResult:
    balance = context.statements.balance_sheet
    value = balance.net_worth
    status: MetricStatus = "healthy" if value >= ZERO else "critical"
    return _metric(
        context,
        metric_id="net_worth",
        name="家庭净资产",
        formula="家庭总资产 − 家庭总负债",
        substitution=(
            f"{format_money(balance.total_assets)} − {format_money(balance.total_liabilities)}"
        ),
        inputs=[
            _input("total_assets", "家庭总资产", balance.total_assets, "CNY", []),
            _input("total_liabilities", "家庭总负债", balance.total_liabilities, "CNY", []),
        ],
        result=value,
        numerator=balance.total_assets - balance.total_liabilities,
        denominator=None,
        unit="CNY",
        status=status,
        threshold_code="measurement_only",
        applicability_reason="资产和负债均可按当前记录汇总。",
        explanation=(
            "净资产为正，但仍需结合流动性和资产集中度判断。"
            if value >= ZERO
            else "净资产为负，新增投资前应优先修复资产负债表。"
        ),
        actions=["将净资产变化与新增结余、负债偿还和估值变化分别核对。"],
    )


def _income_is_volatile(context: MetricContext) -> bool:
    incomes = context.facts.incomes
    annual_income = context.statements.cash_flow.annual_income
    if not incomes or annual_income <= ZERO:
        return True
    weighted_stability = (
        sum(
            (
                line.annual_amount * fact.stability
                for line, fact in zip(
                    context.statements.cash_flow.income_lines,
                    incomes,
                    strict=True,
                )
            ),
            ZERO,
        )
        / annual_income
    )
    weighted_volatility = (
        sum(
            (
                line.annual_amount * fact.volatility
                for line, fact in zip(
                    context.statements.cash_flow.income_lines,
                    incomes,
                    strict=True,
                )
            ),
            ZERO,
        )
        / annual_income
    )
    return weighted_stability < Decimal("0.70") or weighted_volatility > Decimal("0.30")


def metric_liquidity_reserve_months(context: MetricContext) -> MetricResult:
    liquid = context.statements.liquidity.emergency_liquid_assets
    annual_basic = context.statements.cash_flow.annual_basic_living_expenses
    monthly_basic = money(annual_basic / Decimal("12")) if annual_basic > ZERO else ZERO
    value = display_number(liquid / monthly_basic) if monthly_basic > ZERO else None
    volatile = _income_is_volatile(context)
    parameters = context.rules.threshold("liquidity_reserve_months").parameters
    minimum = Decimal(parameters["volatile_min" if volatile else "stable_min"])
    maximum = Decimal(parameters["volatile_max" if volatile else "stable_max"])
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < minimum / Decimal("2"):
        status = "critical"
    elif value < minimum:
        status = "warning"
    elif value > maximum:
        status = "review"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="liquidity_reserve_months",
        name="流动储备月数／应急储备月数",
        formula="即时可用金融资产 ÷ 月基本生活支出",
        substitution=(
            f"{format_money(liquid)} ÷ {format_money(monthly_basic)}"
            if monthly_basic > ZERO
            else "月基本生活支出为 0，无法计算"
        ),
        inputs=[
            _input(
                "emergency_liquid_assets",
                "即时可用金融资产",
                liquid,
                "CNY",
                [
                    item.asset_id
                    for item in context.statements.liquidity.lines
                    if item.included_in_emergency_reserve
                ],
            ),
            _input(
                "monthly_basic_living_expenses",
                "月基本生活支出",
                monthly_basic,
                "CNY/month",
                [
                    item.id
                    for item in context.facts.expenses
                    if item.category.value == "basic_living"
                ],
            ),
        ],
        result=value,
        numerator=liquid if value is not None else None,
        denominator=monthly_basic if value is not None else None,
        unit="months",
        status=status,
        threshold_code="liquidity_reserve_months",
        applicability_reason=(
            "存在基本生活支出，可计算覆盖月数。" if value is not None else "缺少非零基本生活支出。"
        ),
        explanation=(
            f"本家庭按{'波动' if volatile else '稳定'}收入参考带评价；"
            "定期存款和高波动基金不计入即时应急资金。"
        ),
        actions=["将日常周转与应急储备分账，并优先补足参考下限。"],
    )


def _rigid_goal_due_within_year(context: MetricContext) -> tuple[Decimal, list[str]]:
    deadline = context.analysis_date + timedelta(days=365)
    matching = [
        goal
        for goal in context.facts.goals
        if goal.target_date <= deadline and goal.rigidity.value == "rigid"
    ]
    value = money(
        sum(
            (max(ZERO, goal.minimum_acceptable_amount - goal.prepared_amount) for goal in matching),
            ZERO,
        )
    )
    return value, [goal.id for goal in matching]


def metric_short_term_debt_coverage(context: MetricContext) -> MetricResult:
    liquid = context.statements.liquidity.short_term_liquid_assets
    scheduled = money(
        sum(
            (
                item.scheduled_twelve_month_payment
                for item in context.statements.balance_sheet.liabilities
            ),
            ZERO,
        )
    )
    rigid_goals, goal_ids = _rigid_goal_due_within_year(context)
    obligations = money(scheduled + rigid_goals)
    value = safe_ratio(liquid, obligations)
    parameters = context.rules.threshold("short_term_debt_coverage").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(parameters["warning_below"]):
        status = "warning"
    elif value <= Decimal(parameters["healthy_above"]):
        status = "attention"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="short_term_debt_coverage",
        name="短期偿债覆盖率",
        formula="30 日内可变现金融资产 ÷（未来 12 个月合同应付债务 + 刚性目标缺口）",
        substitution=(
            f"{format_money(liquid)} ÷ ({format_money(scheduled)} + {format_money(rigid_goals)})"
            if value is not None
            else "未来 12 个月无已记录债务或刚性目标"
        ),
        inputs=[
            _input("short_term_liquid_assets", "30 日内可变现金融资产", liquid, "CNY", []),
            _input(
                "scheduled_debt",
                "未来 12 个月合同应付债务",
                scheduled,
                "CNY",
                [item.id for item in context.facts.liabilities],
            ),
            _input("rigid_goals", "一年内刚性目标缺口", rigid_goals, "CNY", goal_ids),
        ],
        result=value,
        numerator=liquid if value is not None else None,
        denominator=obligations if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="short_term_debt_coverage",
        applicability_reason=(
            "存在未来十二个月债务或刚性支出。"
            if value is not None
            else "分母为零，该家庭当前无需该覆盖率判断。"
        ),
        explanation="该指标使用合同应付口径，不等同现金流表中的年度已预算还款。",
        actions=["预留未来十二个月应付额，避免依赖未使用信用额度。"],
    )


def metric_debt_to_asset_ratio(context: MetricContext) -> MetricResult:
    balance = context.statements.balance_sheet
    value = safe_ratio(balance.total_liabilities, balance.total_assets)
    params = context.rules.threshold("debt_to_asset_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(params["healthy_below"]):
        status = "healthy"
    elif value > Decimal(params["warning_above"]):
        status = "warning"
    else:
        status = "attention"
    return _metric(
        context,
        metric_id="debt_to_asset_ratio",
        name="负债比率／资产负债率",
        formula="家庭总负债 ÷ 家庭总资产",
        substitution=(
            f"{format_money(balance.total_liabilities)} ÷ {format_money(balance.total_assets)}"
            if value is not None
            else "家庭总资产为 0，无法计算"
        ),
        inputs=[
            _input("total_liabilities", "家庭总负债", balance.total_liabilities, "CNY", []),
            _input("total_assets", "家庭总资产", balance.total_assets, "CNY", []),
        ],
        result=value,
        numerator=balance.total_liabilities if value is not None else None,
        denominator=balance.total_assets if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="debt_to_asset_ratio",
        applicability_reason=("家庭总资产大于零。" if value is not None else "家庭总资产为零。"),
        explanation="比率反映资产端对负债的总体承载，不代替月度偿债压力判断。",
        actions=["优先核对高息负债和房贷余额，再评估新增负债。"],
    )


def metric_savings_ratio(context: MetricContext) -> MetricResult:
    cash = context.statements.cash_flow
    value = safe_ratio(cash.annual_surplus, cash.annual_income)
    params = context.rules.threshold("savings_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(params["warning_below"]):
        status = "warning"
    elif value < Decimal(params["healthy_at"]):
        status = "attention"
    elif value >= Decimal(params["strong_at"]):
        status = "strong"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="savings_ratio",
        name="结余比率",
        formula="年度税后结余 ÷ 年度税后总收入",
        substitution=(
            f"({format_money(cash.annual_income)} − {format_money(cash.annual_expenses)}) "
            f"÷ {format_money(cash.annual_income)}"
            if value is not None
            else "年度税后收入为 0，无法计算"
        ),
        inputs=[
            _input("annual_surplus", "年度税后结余", cash.annual_surplus, "CNY/year", []),
            _input("annual_income", "年度税后总收入", cash.annual_income, "CNY/year", []),
        ],
        result=value,
        numerator=cash.annual_surplus if value is not None else None,
        denominator=cash.annual_income if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="savings_ratio",
        applicability_reason=(
            "存在非零年度税后收入。" if value is not None else "年度税后收入为零。"
        ),
        explanation="结余比率反映家庭每年可持续积累资金的能力，需结合收入稳定性和未来目标期限观察。",
        actions=["区分刚性支出与可压缩支出，为目标建立稳定年度投入。"],
    )


def metric_debt_service_burden_ratio(context: MetricContext) -> MetricResult:
    cash = context.statements.cash_flow
    value = safe_ratio(cash.annual_debt_service, cash.annual_income)
    params = context.rules.threshold("debt_service_burden_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(params["healthy_below"]):
        status = "healthy"
    elif value > Decimal(params["warning_above"]):
        status = "warning"
    else:
        status = "attention"
    return _metric(
        context,
        metric_id="debt_service_burden_ratio",
        name="财务负担率／偿债负担率",
        formula="年度债务本息支出 ÷ 年度税后总收入",
        substitution=(
            f"{format_money(cash.annual_debt_service)} ÷ {format_money(cash.annual_income)}"
            if value is not None
            else "年度税后收入为 0，无法计算"
        ),
        inputs=[
            _input(
                "annual_debt_service",
                "年度债务本息支出",
                cash.annual_debt_service,
                "CNY/year",
                [
                    item.id
                    for item in context.facts.expenses
                    if item.category.value == "debt_service"
                ],
            ),
            _input("annual_income", "年度税后总收入", cash.annual_income, "CNY/year", []),
        ],
        result=value,
        numerator=cash.annual_debt_service if value is not None else None,
        denominator=cash.annual_income if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="debt_service_burden_ratio",
        applicability_reason=(
            "存在非零年度税后收入。" if value is not None else "年度税后收入为零。"
        ),
        explanation="该值使用现金流中实际预算的年度本息支出，合同应付额另见短期覆盖率。",
        actions=["先清偿高息短债，再评估提前还贷与目标投入的取舍。"],
    )


def _investable_assets(context: MetricContext) -> tuple[Decimal, list[str]]:
    categories = set(context.rules.classification.investable_financial_asset_categories)
    assets = [item for item in context.facts.assets if item.category.value in categories]
    return money(sum((item.market_value for item in assets), ZERO)), [item.id for item in assets]


def metric_investable_assets_to_net_worth(context: MetricContext) -> MetricResult:
    investable, ids = _investable_assets(context)
    net_worth = context.statements.balance_sheet.net_worth
    value = safe_ratio(investable, net_worth) if net_worth > ZERO else None
    return _metric(
        context,
        metric_id="investable_assets_to_net_worth",
        name="投资与净资产比率",
        formula="可投资金融资产 ÷ 家庭净资产",
        substitution=(
            f"{format_money(investable)} ÷ {format_money(net_worth)}"
            if value is not None
            else "家庭净资产非正，比例不适用"
        ),
        inputs=[
            _input("investable_assets", "可投资金融资产", investable, "CNY", ids),
            _input("net_worth", "家庭净资产", net_worth, "CNY", []),
        ],
        result=value,
        numerator=investable if value is not None else None,
        denominator=net_worth if value is not None else None,
        unit="ratio",
        status="review",
        threshold_code="investable_assets_to_net_worth",
        applicability_reason=(
            "家庭净资产为正。" if value is not None else "家庭净资产非正，不能解释为越高越好。"
        ),
        explanation="20%—50% 可作为常用观察区间，但不能脱离年龄、责任、期限和安全约束机械判断。",
        actions=["先确认应急、债务、保障和近期目标，再解释可投资比例。"],
    )


def _property_assets(context: MetricContext) -> tuple[Decimal, list[str]]:
    assets = [
        item for item in context.facts.assets if item.property_use != PropertyUse.NOT_PROPERTY
    ]
    return money(sum((item.market_value for item in assets), ZERO)), [item.id for item in assets]


def metric_property_to_assets_ratio(context: MetricContext) -> MetricResult:
    property_value, ids = _property_assets(context)
    total_assets = context.statements.balance_sheet.total_assets
    value = safe_ratio(property_value, total_assets)
    params = context.rules.threshold("property_to_assets_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value > Decimal(params["warning_above"]):
        status = "warning"
    elif value > Decimal(params["attention_above"]):
        status = "attention"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="property_to_assets_ratio",
        name="房产与资产比率／房产集中度",
        formula="房产总价值 ÷ 家庭总资产",
        substitution=(
            f"{format_money(property_value)} ÷ {format_money(total_assets)}"
            if value is not None
            else "家庭总资产为 0，无法计算"
        ),
        inputs=[
            _input("property_value", "房产总价值", property_value, "CNY", ids),
            _input("total_assets", "家庭总资产", total_assets, "CNY", []),
        ],
        result=value,
        numerator=property_value if value is not None else None,
        denominator=total_assets if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="property_to_assets_ratio",
        applicability_reason=(
            "家庭总资产大于零；无房家庭结果为 0。" if value is not None else "家庭总资产为零。"
        ),
        explanation="集中度必须结合是否自住、城市、房贷和生命周期解释。",
        actions=["提高新增结余中的流动金融资产占比，避免被迫出售自住房。"],
    )


def metric_housing_equity_to_net_worth(context: MetricContext) -> MetricResult:
    property_value, property_ids = _property_assets(context)
    linked_debt = money(
        sum(
            (
                item.outstanding_balance
                for item in context.facts.liabilities
                if item.linked_asset_id in set(property_ids)
            ),
            ZERO,
        )
    )
    housing_equity = money(property_value - linked_debt)
    net_worth = context.statements.balance_sheet.net_worth
    value = (
        safe_ratio(housing_equity, net_worth)
        if property_value > ZERO and net_worth > ZERO
        else None
    )
    return _metric(
        context,
        metric_id="housing_equity_to_net_worth",
        name="住房净权益占净资产比例",
        formula="（房产价值 − 相关房贷余额）÷ 家庭净资产",
        substitution=(
            f"({format_money(property_value)} − {format_money(linked_debt)}) ÷ "
            f"{format_money(net_worth)}"
            if value is not None
            else "无房产或净资产非正，不适用"
        ),
        inputs=[
            _input("property_value", "房产价值", property_value, "CNY", property_ids),
            _input("linked_mortgage", "相关房贷余额", linked_debt, "CNY", []),
            _input("net_worth", "家庭净资产", net_worth, "CNY", []),
        ],
        result=value,
        numerator=housing_equity if value is not None else None,
        denominator=net_worth if value is not None else None,
        unit="ratio",
        status="review",
        threshold_code="measurement_only",
        applicability_reason=(
            "存在房产且家庭净资产为正。" if value is not None else "需要房产和正净资产才能解释。"
        ),
        explanation="该比例揭示家庭净资产对住房净权益的依赖程度。",
        actions=["同时查看房产集中度和应急流动性，不把住房净值当日常现金。"],
    )


def metric_twelve_month_liquidity_coverage(context: MetricContext) -> MetricResult:
    liquid = context.statements.liquidity.twelve_month_liquid_assets
    rigid_goals, goal_ids = _rigid_goal_due_within_year(context)
    essential = context.statements.cash_flow.annual_essential_expenses
    required = money(essential + rigid_goals)
    value = safe_ratio(liquid, required)
    params = context.rules.threshold("twelve_month_liquidity_coverage").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value >= Decimal(params["healthy_at"]):
        status = "healthy"
    elif value >= Decimal("0.75"):
        status = "attention"
    else:
        status = "warning"
    return _metric(
        context,
        metric_id="twelve_month_liquidity_coverage",
        name="12 个月流动覆盖率",
        formula="一年内可变现金融资产 ÷（年度必要支出 + 一年内刚性目标缺口）",
        substitution=(
            f"{format_money(liquid)} ÷ ({format_money(essential)} + {format_money(rigid_goals)})"
            if value is not None
            else "未来十二个月必要支出为 0，不适用"
        ),
        inputs=[
            _input("twelve_month_liquid_assets", "一年内可变现金融资产", liquid, "CNY", []),
            _input(
                "essential_expenses",
                "年度必要支出",
                essential,
                "CNY/year",
                [],
            ),
            _input("rigid_goals", "一年内刚性目标缺口", rigid_goals, "CNY", goal_ids),
        ],
        result=value,
        numerator=liquid if value is not None else None,
        denominator=required if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="twelve_month_liquidity_coverage",
        applicability_reason=("存在未来十二个月必要支出。" if value is not None else "分母为零。"),
        explanation="只计一年内可变现的金融资产，不计车辆、自住房和信用额度。",
        actions=["为一年内必要支出保留与期限匹配的金融资产。"],
    )


def metric_fixed_expense_ratio(context: MetricContext) -> MetricResult:
    cash = context.statements.cash_flow
    value = safe_ratio(cash.annual_fixed_expenses, cash.annual_income)
    params = context.rules.threshold("fixed_expense_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value > Decimal(params["warning_above"]):
        status = "warning"
    elif value > Decimal(params["attention_above"]):
        status = "attention"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="fixed_expense_ratio",
        name="固定支出率",
        formula="年度必要／刚性支出 ÷ 年度税后总收入",
        substitution=(
            f"{format_money(cash.annual_fixed_expenses)} ÷ {format_money(cash.annual_income)}"
            if value is not None
            else "年度税后收入为 0，无法计算"
        ),
        inputs=[
            _input(
                "fixed_expenses", "年度必要／刚性支出", cash.annual_fixed_expenses, "CNY/year", []
            ),
            _input("annual_income", "年度税后总收入", cash.annual_income, "CNY/year", []),
        ],
        result=value,
        numerator=cash.annual_fixed_expenses if value is not None else None,
        denominator=cash.annual_income if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="fixed_expense_ratio",
        applicability_reason=(
            "存在非零年度税后收入。" if value is not None else "年度税后收入为零。"
        ),
        explanation="固定支出越高，收入中断时可调整空间越小。",
        actions=["优先识别可重谈债务、保费缴费方式和可压缩支出。"],
    )


def metric_protection_coverage_ratio(context: MetricContext) -> MetricResult:
    value = context.protection.coverage_ratio
    params = context.rules.threshold("protection_coverage_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(params["warning_below"]):
        status = "warning"
    elif value < Decimal(params["healthy_at"]):
        status = "attention"
    else:
        status = "healthy"
    risk = next(
        item
        for item in context.protection.risks
        if item.risk_code == context.protection.most_significant_risk
    )
    return _metric(
        context,
        metric_id="protection_coverage_ratio",
        name="保障覆盖率",
        formula="最大不可承受风险的现有保障 ÷ 所需保障",
        substitution=(
            f"{format_money(risk.existing_coverage)} ÷ {format_money(risk.required_amount)}"
            if value is not None
            else "所需保障为 0，不适用"
        ),
        inputs=[
            _input("existing_coverage", "现有保障", risk.existing_coverage, "CNY", []),
            _input("required_coverage", "所需保障", risk.required_amount, "CNY", []),
        ],
        result=value,
        numerator=risk.existing_coverage if value is not None else None,
        denominator=risk.required_amount if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="protection_coverage_ratio",
        applicability_reason=(
            "存在可量化的最大风险责任。" if value is not None else "所需保障为零。"
        ),
        explanation=context.protection.counting_note,
        actions=["先核对最大保障缺口及责任期限，不直接按固定保费比例购买产品。"],
    )


def metric_protection_gap(context: MetricContext) -> MetricResult:
    value = context.protection.protection_gap
    return _metric(
        context,
        metric_id="protection_gap",
        name="保障缺口",
        formula="最大单一不可承受风险所需保障 − 对应现有保障",
        substitution=f"最大情景缺口 = {format_money(value)}",
        inputs=[_input("protection_gap", "最大情景保障缺口", value, "CNY", [])],
        result=value,
        numerator=value,
        denominator=None,
        unit="CNY",
        status="healthy" if value == ZERO else "warning",
        threshold_code="protection_coverage_ratio",
        applicability_reason="保障责任模型已完成四类风险情景计算。",
        explanation="缺口是风险责任金额，不是保费预算，也不对应具体产品。",
        actions=["按身故、医疗、意外和家庭责任优先级逐项复核保障。"],
    )


def metric_retirement_funding_adequacy(context: MetricContext) -> MetricResult:
    retirement_goals = [
        item for item in context.facts.goals if item.goal_type == GoalType.RETIREMENT
    ]
    target = money(sum((item.target_amount for item in retirement_goals), ZERO))
    goal_prepared = money(sum((item.prepared_amount for item in retirement_goals), ZERO))
    pension_assets = money(
        sum(
            (
                item.market_value
                for item in context.facts.assets
                if item.category.value == "pension_account"
            ),
            ZERO,
        )
    )
    social_balance = money(
        sum((item.balance for item in context.facts.social_security_accounts), ZERO)
    )
    prepared = money(max(goal_prepared, pension_assets) + social_balance)
    value = safe_ratio(prepared, target)
    params = context.rules.threshold("funding_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(params["warning_below"]):
        status = "warning"
    elif value < Decimal(params["healthy_at"]):
        status = "attention"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="retirement_funding_adequacy",
        name="养老资金充足率",
        formula="（max(养老目标已准备资金, 养老金资产) + 社保账户余额）÷ 养老目标金额",
        substitution=(
            f"(max({format_money(goal_prepared)}, {format_money(pension_assets)}) + "
            f"{format_money(social_balance)}) ÷ {format_money(target)}"
            if value is not None
            else "未录入养老目标，无法计算"
        ),
        inputs=[
            _input("retirement_prepared", "养老已准备资金", prepared, "CNY", []),
            _input(
                "retirement_target",
                "养老目标金额",
                target,
                "CNY",
                [item.id for item in retirement_goals],
            ),
        ],
        result=value,
        numerator=prepared if value is not None else None,
        denominator=target if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="funding_ratio",
        applicability_reason=("存在养老目标。" if value is not None else "未录入非零养老目标。"),
        explanation="使用 max 避免把同一养老金资产与目标已准备金额重复计算。",
        actions=["核对社保口径与养老金账户是否重复，并在提示词 4 计算持续投入。"],
    )


def metric_goal_funding_ratio(context: MetricContext) -> MetricResult:
    goals = context.statements.goal_funding
    value = safe_ratio(goals.total_prepared_amount, goals.total_target_amount)
    params = context.rules.threshold("funding_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value < Decimal(params["warning_below"]):
        status = "warning"
    elif value < Decimal(params["healthy_at"]):
        status = "attention"
    else:
        status = "healthy"
    return _metric(
        context,
        metric_id="goal_funding_ratio",
        name="目标准备率",
        formula="全部目标已准备资金 ÷ 全部目标金额",
        substitution=(
            f"{format_money(goals.total_prepared_amount)} ÷ "
            f"{format_money(goals.total_target_amount)}"
            if value is not None
            else "未录入目标金额，无法计算"
        ),
        inputs=[
            _input("prepared", "已准备资金", goals.total_prepared_amount, "CNY", []),
            _input(
                "target",
                "目标金额",
                goals.total_target_amount,
                "CNY",
                [item.id for item in context.facts.goals],
            ),
        ],
        result=value,
        numerator=goals.total_prepared_amount if value is not None else None,
        denominator=goals.total_target_amount if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="funding_ratio",
        applicability_reason=("存在非零目标金额。" if value is not None else "未录入非零目标。"),
        explanation="汇总值用于体检；实际优先级必须按期限和刚性逐项目标解释。",
        actions=["先补足高优先级刚性目标，不用低优先目标掩盖主要缺口。"],
    )


def _hhi(values: list[Decimal]) -> Decimal | None:
    total = sum(values, ZERO)
    if total <= ZERO:
        return None
    return ratio(sum(((value / total) ** 2 for value in values), ZERO))


def _hhi_status(context: MetricContext, value: Decimal | None) -> MetricStatus:
    if value is None:
        return "not_applicable"
    params = context.rules.threshold("concentration_hhi").parameters
    if value < Decimal(params["healthy_below"]):
        return "healthy"
    if value > Decimal(params["warning_above"]):
        return "warning"
    return "attention"


def metric_income_concentration_hhi(context: MetricContext) -> MetricResult:
    values = [item.annual_amount for item in context.statements.cash_flow.income_lines]
    value = _hhi(values)
    total = sum(values, ZERO)
    return _metric(
        context,
        metric_id="income_concentration_hhi",
        name="收入集中度 HHI",
        formula="Σ（单一收入来源 ÷ 年度总收入）²",
        substitution=(
            " + ".join(f"({format_money(item)} ÷ {format_money(total)})²" for item in values)
            if value is not None
            else "无正年度收入，无法计算"
        ),
        inputs=[
            _input(
                "annual_income",
                "年度收入来源",
                total,
                "CNY/year",
                [item.id for item in context.facts.incomes],
            )
        ],
        result=value,
        numerator=None,
        denominator=total if value is not None else None,
        unit="hhi",
        status=_hhi_status(context, value),
        threshold_code="concentration_hhi",
        applicability_reason=("存在正年度收入。" if value is not None else "没有正年度收入来源。"),
        explanation="HHI 越高表示收入更依赖少数来源；它不是收入金额高低评价。",
        actions=["为主要收入中断准备更长应急期，并逐步增加独立收入来源。"],
    )


def metric_product_hhi(context: MetricContext) -> MetricResult:
    categories = set(context.rules.classification.investable_financial_asset_categories)
    assets = [item for item in context.facts.assets if item.category.value in categories]
    values = [item.market_value for item in assets]
    value = _hhi(values)
    total = sum(values, ZERO)
    return _metric(
        context,
        metric_id="product_hhi",
        name="产品集中度 HHI",
        formula="Σ（单项可投资金融资产市值 ÷ 可投资金融资产总额）²",
        substitution=(
            " + ".join(f"({format_money(item)} ÷ {format_money(total)})²" for item in values)
            if value is not None
            else "无可投资金融资产，无法计算"
        ),
        inputs=[
            _input(
                "investable_positions",
                "可投资金融资产持仓",
                total,
                "CNY",
                [item.id for item in assets],
            )
        ],
        result=value,
        numerator=None,
        denominator=total if value is not None else None,
        unit="hhi",
        status=_hhi_status(context, value),
        threshold_code="concentration_hhi",
        applicability_reason=(
            "存在可投资金融资产。" if value is not None else "无可投资金融资产。"
        ),
        explanation="阶段 3 以单项资产作为产品代理；正式产品映射在提示词 5 接入。",
        actions=["核对单项持仓和底层资产重叠，避免用产品数量假装分散。"],
    )


def metric_financial_independence_ratio(context: MetricContext) -> MetricResult:
    passive_types = set(context.rules.classification.passive_income_types)
    passive_lines = [
        line
        for line, fact in zip(
            context.statements.cash_flow.income_lines,
            context.facts.incomes,
            strict=True,
        )
        if fact.income_type.value in passive_types and fact.is_sustainable
    ]
    passive_income = money(sum((line.annual_amount for line in passive_lines), ZERO))
    expenses = context.statements.cash_flow.annual_expenses
    value = safe_ratio(passive_income, expenses)
    params = context.rules.threshold("financial_independence_ratio").parameters
    if value is None:
        status: MetricStatus = "not_applicable"
    elif value >= Decimal(params["healthy_at"]):
        status = "healthy"
    elif value >= Decimal(params["attention_at"]):
        status = "attention"
    else:
        status = "warning"
    return _metric(
        context,
        metric_id="financial_independence_ratio",
        name="财务自由度",
        formula="可持续非劳动性年度收入 ÷ 年度总支出",
        substitution=(
            f"{format_money(passive_income)} ÷ {format_money(expenses)}"
            if value is not None
            else "年度支出为 0，无法计算"
        ),
        inputs=[
            _input(
                "passive_income",
                "可持续非劳动性收入",
                passive_income,
                "CNY/year",
                [line.id for line in passive_lines],
            ),
            _input(
                "annual_expenses",
                "年度总支出",
                expenses,
                "CNY/year",
                [item.id for item in context.facts.expenses],
            ),
        ],
        result=value,
        numerator=passive_income if value is not None else None,
        denominator=expenses if value is not None else None,
        unit="ratio",
        status=status,
        threshold_code="financial_independence_ratio",
        applicability_reason=("存在非零年度支出。" if value is not None else "年度支出为零。"),
        explanation="工资和经营劳动收入不计入分子；该指标不等同提前退休建议。",
        actions=["先提升安全结余和分散化长期资产，不追逐承诺收益的所谓被动收入。"],
    )


METRIC_FUNCTIONS: tuple[Callable[[MetricContext], MetricResult], ...] = (
    metric_total_assets,
    metric_total_liabilities,
    metric_net_worth,
    metric_liquidity_reserve_months,
    metric_short_term_debt_coverage,
    metric_debt_to_asset_ratio,
    metric_savings_ratio,
    metric_debt_service_burden_ratio,
    metric_investable_assets_to_net_worth,
    metric_property_to_assets_ratio,
    metric_housing_equity_to_net_worth,
    metric_twelve_month_liquidity_coverage,
    metric_fixed_expense_ratio,
    metric_protection_coverage_ratio,
    metric_protection_gap,
    metric_retirement_funding_adequacy,
    metric_goal_funding_ratio,
    metric_income_concentration_hhi,
    metric_product_hhi,
    metric_financial_independence_ratio,
)


def build_metrics(context: MetricContext) -> list[MetricResult]:
    return [metric_function(context) for metric_function in METRIC_FUNCTIONS]


def _metric_value(metrics: dict[str, MetricResult], metric_id: str) -> Decimal | None:
    metric = metrics.get(metric_id)
    return metric.result if metric is not None else None


def _score_from_ratio(value: Decimal | None, target: Decimal) -> Decimal:
    if value is None or target <= ZERO:
        return ZERO
    return display_number(max(ZERO, min(Decimal("100"), value / target * Decimal("100"))))


def build_health_dimensions(metrics: list[MetricResult]) -> list[HealthDimension]:
    by_id = {item.metric_id: item for item in metrics}
    liquidity = _score_from_ratio(_metric_value(by_id, "liquidity_reserve_months"), Decimal("6"))
    debt_ratio = _metric_value(by_id, "debt_to_asset_ratio")
    debt = (
        display_number(
            max(
                ZERO,
                min(Decimal("100"), (ONE - debt_ratio / Decimal("0.60")) * Decimal("100")),
            )
        )
        if debt_ratio is not None
        else ZERO
    )
    savings = _score_from_ratio(_metric_value(by_id, "savings_ratio"), Decimal("0.30"))
    protection = _score_from_ratio(_metric_value(by_id, "protection_coverage_ratio"), ONE)
    goals = _score_from_ratio(_metric_value(by_id, "goal_funding_ratio"), Decimal("0.80"))
    retirement = _score_from_ratio(
        _metric_value(by_id, "retirement_funding_adequacy"), Decimal("0.80")
    )
    hhi = _metric_value(by_id, "product_hhi")
    diversification = (
        display_number(
            max(
                ZERO,
                min(Decimal("100"), (ONE - hhi / Decimal("0.50")) * Decimal("100")),
            )
        )
        if hhi is not None
        else ZERO
    )
    return [
        HealthDimension(
            code="liquidity",
            name="流动性",
            score=liquidity,
            metric_ids=["liquidity_reserve_months", "twelve_month_liquidity_coverage"],
            explanation="按应急储备月数相对 6 个月归一化，上限 100。",
        ),
        HealthDimension(
            code="debt",
            name="债务韧性",
            score=debt,
            metric_ids=["debt_to_asset_ratio", "debt_service_burden_ratio"],
            explanation="按资产负债率相对 60% 的剩余空间归一化。",
        ),
        HealthDimension(
            code="savings",
            name="储蓄",
            score=savings,
            metric_ids=["savings_ratio", "fixed_expense_ratio"],
            explanation="按结余率相对 30% 归一化，上限 100。",
        ),
        HealthDimension(
            code="protection",
            name="保障",
            score=protection,
            metric_ids=["protection_coverage_ratio", "protection_gap"],
            explanation="按最大不可承受风险的保障覆盖率归一化。",
        ),
        HealthDimension(
            code="diversification",
            name="分散度",
            score=diversification,
            metric_ids=["product_hhi", "property_to_assets_ratio"],
            explanation="按可投资持仓 HHI 相对 0.50 的剩余空间归一化。",
        ),
        HealthDimension(
            code="retirement",
            name="养老",
            score=retirement,
            metric_ids=["retirement_funding_adequacy"],
            explanation="按养老资金充足率相对 80% 归一化；未录入养老目标时为 0。",
        ),
        HealthDimension(
            code="goals",
            name="目标准备",
            score=goals,
            metric_ids=["goal_funding_ratio"],
            explanation="按全体目标准备率相对 80% 归一化，不替代逐目标期限分析。",
        ),
    ]
