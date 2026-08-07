from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.enums import (
    ExpenseCategory,
    GoalType,
    IncomeType,
    LifecycleStage,
    RiskLevel,
)
from app.domain.financial import HouseholdFacts, MemberFact
from app.schemas.planning import FactorEvidence, LifecycleAssessment
from app.services.financial.utils import ZERO, annualize, display_number
from app.services.planning.rules import PlanningRules


def _age(member: MemberFact, analysis_date: date) -> int:
    return max(
        0,
        analysis_date.year
        - member.birth_date.year
        - (
            (analysis_date.month, analysis_date.day)
            < (member.birth_date.month, member.birth_date.day)
        ),
    )


def detect_lifecycle(
    facts: HouseholdFacts,
    rules: PlanningRules,
    analysis_date: date,
) -> tuple[LifecycleStage, list[str]]:
    evidence: list[str] = []
    children = [member for member in facts.members if "子女" in member.relationship]
    adults = [member for member in facts.members if member not in children]
    if not adults:
        adults = list(facts.members)
    adult_ages = [_age(member, analysis_date) for member in adults]
    child_ages = [_age(member, analysis_date) for member in children]
    has_partner = any(
        any(label in member.relationship for label in ("配偶", "丈夫", "妻子")) for member in adults
    )
    employment_incomes = [
        income
        for income in facts.incomes
        if income.income_type in {IncomeType.EMPLOYMENT, IncomeType.BUSINESS}
        and income.is_sustainable
        and income.amount > ZERO
    ]
    retirement_state = any(
        income.income_type == IncomeType.PENSION and income.amount > ZERO
        for income in facts.incomes
    ) or any(member.occupation and "退休" in member.occupation for member in adults)
    retirement_years = [
        max(
            0,
            (member.expected_retirement_age or rules.lifecycle.retirement_default_age)
            - _age(member, analysis_date),
        )
        for member in adults
    ]

    if retirement_state or (adults and any(years == 0 for years in retirement_years)):
        evidence.append("家庭已存在养老金收入、退休职业状态或已达预计退休年龄。")
        return LifecycleStage.RETIREMENT_AND_LEGACY, evidence
    if retirement_years and min(retirement_years) <= rules.lifecycle.retirement_preparation_years:
        evidence.append(f"距离最早预计退休年龄约 {min(retirement_years)} 年，进入退休准备窗口。")
        return LifecycleStage.RETIREMENT_PREPARATION, evidence
    if any(age < 18 for age in child_ages):
        evidence.append("家庭存在未成年子女，育儿与教育责任仍在持续。")
        return LifecycleStage.PARENTING, evidence
    if (has_partner or len(adults) >= 2) and (not adult_ages or max(adult_ages) < 40):
        evidence.append("关系记录表明家庭存在配偶或两名主要成年人。")
        return LifecycleStage.FAMILY_FORMATION, evidence
    if len(adults) == 1 and adult_ages and adult_ages[0] < 35 and employment_incomes:
        evidence.append("家庭以单一年轻成年人和持续劳动或经营收入为主。")
        return LifecycleStage.EARLY_CAREER, evidence
    evidence.append("家庭已越过初始组建期，且尚未进入退休准备窗口。")
    return LifecycleStage.MATURE_FAMILY, evidence


def assess_lifecycle(
    facts: HouseholdFacts,
    rules: PlanningRules,
    analysis_date: date,
    override: LifecycleStage | None,
) -> LifecycleAssessment:
    detected, detection_evidence = detect_lifecycle(facts, rules, analysis_date)
    effective = override or facts.lifecycle_stage
    base = Decimal(rules.lifecycle.base_safety_months[effective.value])
    adjustments: list[FactorEvidence] = []

    def add(
        factor: str,
        label: str,
        observed: str,
        amount: str,
        record_ids: list[str] | None = None,
    ) -> None:
        adjustments.append(
            FactorEvidence(
                factor=factor,
                label=label,
                observed_value=observed,
                adjustment_months=Decimal(amount),
                source_record_ids=record_ids or [],
            )
        )

    employment_incomes = [
        income
        for income in facts.incomes
        if income.income_type in {IncomeType.EMPLOYMENT, IncomeType.BUSINESS}
        and income.is_sustainable
        and income.amount > ZERO
    ]
    if len(employment_incomes) >= 2:
        add(
            "dual_income",
            "双收入缓冲",
            f"{len(employment_incomes)} 个持续劳动收入来源",
            rules.safety_months.dual_income_adjustment,
            [item.id for item in employment_incomes],
        )
    else:
        add(
            "single_income",
            "单一劳动收入依赖",
            f"{len(employment_incomes)} 个持续劳动收入来源",
            rules.safety_months.single_income_adjustment,
            [item.id for item in employment_incomes],
        )

    annual_amounts = [annualize(item.amount, item.frequency) for item in facts.incomes]
    annual_income = sum(annual_amounts, ZERO)
    weighted_stability = (
        sum(
            (
                amount * income.stability
                for amount, income in zip(annual_amounts, facts.incomes, strict=True)
            ),
            ZERO,
        )
        / annual_income
        if annual_income > ZERO
        else ZERO
    )
    weighted_volatility = (
        sum(
            (
                amount * income.volatility
                for amount, income in zip(annual_amounts, facts.incomes, strict=True)
            ),
            ZERO,
        )
        / annual_income
        if annual_income > ZERO
        else Decimal("1")
    )
    if weighted_stability >= Decimal("0.85"):
        stability_adjustment = rules.safety_months.high_stability_adjustment
        stability_label = "较高"
    elif weighted_stability >= Decimal("0.70"):
        stability_adjustment = rules.safety_months.medium_stability_adjustment
        stability_label = "中等"
    else:
        stability_adjustment = rules.safety_months.low_stability_adjustment
        stability_label = "偏低"
    add(
        "income_stability",
        "收入稳定度",
        f"加权稳定度 {weighted_stability:.3f}（{stability_label}）",
        stability_adjustment,
        [item.id for item in facts.incomes],
    )
    if weighted_volatility >= Decimal("0.30"):
        add(
            "income_volatility",
            "收入波动",
            f"加权波动 {weighted_volatility:.3f}",
            rules.safety_months.high_volatility_adjustment,
            [item.id for item in facts.incomes],
        )
    elif weighted_volatility >= Decimal("0.15"):
        add(
            "income_volatility",
            "收入波动",
            f"加权波动 {weighted_volatility:.3f}",
            rules.safety_months.medium_volatility_adjustment,
            [item.id for item in facts.incomes],
        )

    mortgages = [item for item in facts.liabilities if item.category.value == "mortgage"]
    if mortgages:
        add(
            "mortgage",
            "按揭责任",
            f"{len(mortgages)} 笔按揭",
            rules.safety_months.mortgage_adjustment,
            [item.id for item in mortgages],
        )
    children = [
        member
        for member in facts.members
        if "子女" in member.relationship and _age(member, analysis_date) < 18
    ]
    if children:
        add(
            "dependent_child",
            "未成年子女责任",
            f"{len(children)} 名未成年子女",
            rules.safety_months.dependent_child_adjustment,
            [item.id for item in children],
        )
    support_records = [
        item.id for item in facts.goals if item.goal_type == GoalType.FAMILY_SUPPORT
    ] + [
        item.id
        for item in facts.expenses
        if item.category == ExpenseCategory.PARENT_SUPPORT or "赡养" in item.name
    ]
    if support_records:
        add(
            "family_support",
            "赡养责任",
            "存在赡养目标或支出",
            rules.safety_months.family_support_adjustment,
            support_records,
        )
    health_rank = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM_LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.MEDIUM_HIGH: 3,
        RiskLevel.HIGH: 4,
    }
    highest_health = max(
        (facts.members),
        key=lambda member: health_rank[member.health_risk_level],
        default=None,
    )
    if highest_health and health_rank[highest_health.health_risk_level] >= 3:
        add(
            "health_risk",
            "健康风险",
            highest_health.health_risk_level.value,
            rules.safety_months.high_health_adjustment,
            [highest_health.id],
        )
    elif highest_health and health_rank[highest_health.health_risk_level] == 2:
        add(
            "health_risk",
            "健康风险",
            highest_health.health_risk_level.value,
            rules.safety_months.medium_health_adjustment,
            [highest_health.id],
        )

    raw = base + sum((item.adjustment_months for item in adjustments), ZERO)
    safety_months = display_number(
        max(Decimal(rules.safety_months.minimum), min(Decimal(rules.safety_months.maximum), raw))
    )
    adjustment_text = " + ".join(str(item.adjustment_months) for item in adjustments) or "0"
    return LifecycleAssessment(
        detected_stage=detected,
        recorded_stage=facts.lifecycle_stage,
        effective_stage=effective,
        override_applied=override is not None,
        dynamic_safety_months=safety_months,
        base_safety_months=base,
        formula="生命周期基础月数 + 双收入/稳定度/房贷/子女赡养/健康/波动修正，并限制在 3—12 月",
        substitution=f"{base} + ({adjustment_text}) = {safety_months} 月",
        explanation=(
            "；".join(detection_evidence)
            + f" 当前采用{('人工修正' if override is not None else '家庭记录')}阶段；"
            "阶段只提供基础参数，实际家庭责任继续逐项修正。"
        ),
        evidence=adjustments,
    )
