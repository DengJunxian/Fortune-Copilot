from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import (
    FinancialStatements,
    GoalCostFactor,
    PurchasingPowerAssessment,
    PurchasingPowerFactor,
)
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import ZERO, ratio


def assess_purchasing_power(
    facts: HouseholdFacts,
    statements: FinancialStatements,
    rules: FinancialRules,
    data_as_of: date,
) -> PurchasingPowerAssessment:
    purchasing_rules = rules.purchasing_power
    official = purchasing_rules.official_cpi
    minimum_wage = purchasing_rules.minimum_wage_catch_up
    weighted_numerator = sum(
        (
            line.annual_amount
            * Decimal(purchasing_rules.expense_category_rates.get(line.category, "0"))
            for line in statements.cash_flow.expense_lines
        ),
        ZERO,
    )
    annual_expenses = statements.cash_flow.annual_expenses
    family_rate = ratio(weighted_numerator / annual_expenses) if annual_expenses > ZERO else ZERO
    return PurchasingPowerAssessment(
        official_cpi=PurchasingPowerFactor(
            code="official_cpi_demo_baseline",
            name=official.label,
            rate=Decimal(official.rate),
            source_type=official.source_type,
            source_reference=official.source_reference,
            data_as_of=official.data_as_of,
            note="采用官方 CPI 的指标口径，但当前数值是离线比赛参数，不冒充实时统计发布。",
        ),
        family_weighted_inflation=PurchasingPowerFactor(
            code="family_weighted_inflation",
            name="家庭个性化消费通胀",
            rate=family_rate,
            source_type="internal_demo",
            source_reference="家庭年度支出权重 × 受控分类成本增长参数",
            data_as_of=data_as_of,
            note="按本家庭支出结构计算；债务本金与利息不按消费价格增长处理。",
        ),
        goal_specific_cost_growth=[
            GoalCostFactor(
                goal_id=goal.id,
                goal_name=goal.name,
                goal_type=goal.goal_type.value,
                annual_cost_growth_rate=goal.annual_cost_growth_rate,
                target_date=goal.target_date,
            )
            for goal in facts.goals
        ],
        minimum_wage_catch_up=PurchasingPowerFactor(
            code="minimum_wage_catch_up",
            name=minimum_wage.label,
            rate=Decimal(minimum_wage.rate),
            source_type=minimum_wage.source_type,
            source_reference=minimum_wage.source_reference,
            data_as_of=minimum_wage.data_as_of,
            note="只用于观察长期民生收入追赶，不是 CPI 替代，也不是收益保证线。",
        ),
        minimum_wage_is_cpi=False,
        minimum_wage_is_return_guarantee=False,
    )
