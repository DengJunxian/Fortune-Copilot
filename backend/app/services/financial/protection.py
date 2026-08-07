from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.enums import GoalType, InsuranceType
from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import (
    FinancialStatements,
    ProtectionAssessment,
    ProtectionRisk,
)
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import ZERO, money, safe_ratio


def _active_coverage(
    facts: HouseholdFacts,
    analysis_date: date,
    policy_types: set[InsuranceType],
) -> Decimal:
    return money(
        sum(
            (
                policy.coverage_amount
                for policy in facts.insurance_policies
                if policy.policy_type in policy_types
                and policy.start_date <= analysis_date
                and (policy.end_date is None or policy.end_date >= analysis_date)
            ),
            ZERO,
        )
    )


def _risk(
    code: str,
    name: str,
    required: Decimal,
    coverage: Decimal,
    priority: int,
    basis: str,
) -> ProtectionRisk:
    return ProtectionRisk(
        risk_code=code,
        name=name,
        required_amount=money(required),
        existing_coverage=money(coverage),
        coverage_ratio=safe_ratio(coverage, required),
        gap=money(max(ZERO, required - coverage)),
        priority=priority,
        basis=basis,
    )


def assess_protection(
    facts: HouseholdFacts,
    statements: FinancialStatements,
    rules: FinancialRules,
    analysis_date: date,
) -> ProtectionAssessment:
    cash_flow = statements.cash_flow
    balance = statements.balance_sheet
    protection_rules = rules.protection
    life_coverage = _active_coverage(
        facts,
        analysis_date,
        {InsuranceType.TERM_LIFE, InsuranceType.WHOLE_LIFE},
    )
    medical_coverage = _active_coverage(
        facts,
        analysis_date,
        {InsuranceType.MEDICAL, InsuranceType.CRITICAL_ILLNESS},
    )
    accident_coverage = _active_coverage(
        facts,
        analysis_date,
        {InsuranceType.ACCIDENT},
    )
    active_deductibles = sum(
        (
            policy.deductible
            for policy in facts.insurance_policies
            if policy.start_date <= analysis_date
            and (policy.end_date is None or policy.end_date >= analysis_date)
            and policy.policy_type in {InsuranceType.MEDICAL, InsuranceType.CRITICAL_ILLNESS}
        ),
        ZERO,
    )
    goal_responsibility = sum(
        (
            max(ZERO, goal.minimum_acceptable_amount - goal.prepared_amount)
            for goal in facts.goals
            if goal.goal_type != GoalType.TRAVEL
        ),
        ZERO,
    )

    risks = [
        _risk(
            "death_responsibility",
            "身故责任",
            balance.total_liabilities
            + cash_flow.annual_basic_living_expenses
            * Decimal(protection_rules.death_support_years),
            life_coverage,
            1,
            "未偿负债 + 基本生活支出 × 责任年数",
        ),
        _risk(
            "medical_self_pay",
            "医疗自付",
            Decimal(protection_rules.medical_self_pay_reserve) + active_deductibles,
            medical_coverage,
            2,
            "内部医疗自付储备参数 + 有效保单免赔额",
        ),
        _risk(
            "accident_income_loss",
            "意外收入中断",
            cash_flow.annual_income * Decimal(protection_rules.accident_income_years),
            accident_coverage,
            3,
            "年度税后收入 × 意外收入补偿年数",
        ),
        _risk(
            "family_responsibility",
            "家庭责任",
            goal_responsibility
            + cash_flow.annual_basic_living_expenses
            * Decimal(protection_rules.family_support_years),
            life_coverage,
            4,
            "非旅行目标最低资金缺口 + 基本生活支出 × 家庭责任年数",
        ),
    ]
    significant = max(risks, key=lambda item: (item.gap, -item.priority))
    premium_ratio = safe_ratio(
        statements.insurance.total_annual_premium,
        cash_flow.annual_income,
    )
    if premium_ratio is None:
        payment_pressure = "收入缺失，无法评价保费支付压力"
    elif premium_ratio > Decimal("0.15"):
        payment_pressure = "保费支付压力较高，需在保障缺口与持续缴费能力之间复核"
    elif premium_ratio > Decimal("0.10"):
        payment_pressure = "保费支付压力需要关注，但不能仅凭比例削减必要保障"
    else:
        payment_pressure = "当前保费压力相对可控，仍应以保障缺口为主要判断依据"
    return ProtectionAssessment(
        risks=risks,
        most_significant_risk=significant.risk_code,
        coverage_ratio=significant.coverage_ratio,
        protection_gap=significant.gap,
        annual_premium=statements.insurance.total_annual_premium,
        premium_to_income_ratio=premium_ratio,
        payment_pressure=payment_pressure,
        counting_note=(
            "四类风险按独立情景评估，保额不跨情景相加；总缺口取最大单一不可承受风险，"
            "不直接映射或推荐具体保险产品。"
        ),
    )
