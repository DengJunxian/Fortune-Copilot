from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from app.domain.enums import GoalRigidity
from app.domain.financial import GoalFact, HouseholdFacts
from app.schemas.planning import (
    ConflictAdjustment,
    GoalConflict,
    GoalProjection,
    GoalStatus,
)
from app.services.financial.utils import ZERO, format_money, money
from app.services.planning.rules import PlanningRules


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def months_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day > start.day:
        months += 1
    return max(1, months)


def _compound(value: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    monthly_rate = annual_rate / Decimal("12")
    return money(value * ((Decimal("1") + monthly_rate) ** months))


def _present_value(value: Decimal, annual_discount: Decimal, months: int) -> Decimal:
    monthly_discount = annual_discount / Decimal("12")
    return money(value / ((Decimal("1") + monthly_discount) ** months))


def project_goal(
    goal: GoalFact,
    rules: PlanningRules,
    analysis_date: date,
    prepared_addition: Decimal,
    deferral_months: int,
) -> GoalProjection:
    adjusted_date = add_months(goal.target_date, deferral_months)
    months = months_between(analysis_date, adjusted_date)
    future = _compound(goal.target_amount, goal.annual_cost_growth_rate, months)
    minimum_future = _compound(
        goal.minimum_acceptable_amount,
        goal.annual_cost_growth_rate,
        months,
    )
    discount = Decimal(rules.goals.present_value_discount_rate)
    present = _present_value(future, discount, months)
    minimum_present = _present_value(minimum_future, discount, months)
    prepared = money(goal.prepared_amount + prepared_addition)
    gap = money(max(ZERO, present - prepared))
    minimum_gap = money(max(ZERO, minimum_present - prepared))
    monthly = money(gap / Decimal(max(1, months)))
    annual = money(monthly * Decimal("12"))
    status: GoalStatus = "funded" if gap == ZERO else "gap"
    return GoalProjection(
        goal_id=goal.id,
        name=goal.name,
        goal_type=goal.goal_type.value,
        target_date=goal.target_date,
        adjusted_target_date=adjusted_date,
        months_remaining=months,
        current_cost=goal.target_amount,
        future_amount=future,
        present_value=present,
        minimum_present_value=minimum_present,
        prepared_amount=prepared,
        funding_gap=gap,
        minimum_funding_gap=minimum_gap,
        monthly_required=monthly,
        annual_required=annual,
        priority=goal.priority,
        rigidity=goal.rigidity.value,
        can_defer=goal.can_defer,
        annual_cost_growth_rate=goal.annual_cost_growth_rate,
        status=status,
        formula=(
            "未来金额 = 今日目标 × (1 + 年成本增速/12)^剩余月数；"
            "现值 = 未来金额 ÷ (1 + Demo 折现率/12)^剩余月数；"
            "月投入 = max(0, 现值 − 已准备) ÷ 剩余月数"
        ),
        substitution=(
            f"未来 {format_money(future)}；现值 {format_money(present)}；"
            f"({format_money(present)} − {format_money(prepared)}) ÷ {max(1, months)}"
            f" = {format_money(monthly)}/月"
        ),
        source_record_ids=[goal.id],
    )


def build_goal_plan(
    facts: HouseholdFacts,
    rules: PlanningRules,
    analysis_date: date,
    annual_surplus: Decimal,
    prepared_additions: dict[str, Decimal],
    defer_goal_ids: set[str],
    defer_months: int,
    monthly_savings_increase: Decimal,
) -> tuple[list[GoalProjection], list[GoalConflict]]:
    projections = [
        project_goal(
            goal,
            rules,
            analysis_date,
            prepared_additions.get(goal.id, ZERO),
            defer_months if goal.id in defer_goal_ids else 0,
        )
        for goal in sorted(facts.goals, key=lambda item: (item.priority, item.target_date, item.id))
    ]
    available_monthly = money(max(ZERO, annual_surplus) / Decimal("12") + monthly_savings_increase)
    required_monthly = money(sum((goal.monthly_required for goal in projections), ZERO))
    shortfall = money(max(ZERO, required_monthly - available_monthly))
    if shortfall == ZERO:
        return [
            goal.model_copy(update={"status": "on_track"}) if goal.status == "gap" else goal
            for goal in projections
        ], []

    adjustments: list[ConflictAdjustment] = []
    for goal in projections:
        if (
            goal.rigidity == GoalRigidity.FLEXIBLE.value
            and goal.funding_gap > goal.minimum_funding_gap
        ):
            effect = money(
                (goal.funding_gap - goal.minimum_funding_gap)
                / Decimal(max(1, goal.months_remaining))
            )
            adjustments.append(
                ConflictAdjustment(
                    action_code="reduce_to_minimum",
                    title=f"先把“{goal.name}”调整到最低可接受金额",
                    detail=(
                        f"月投入最多可下降 {format_money(effect)}，不隐藏仍存在的最低目标缺口。"
                    ),
                    affected_goal_ids=[goal.goal_id],
                    monthly_effect=effect,
                    preserves_minimum=True,
                )
            )
        if goal.can_defer:
            extension = defer_months or rules.goals.default_deferral_months
            deferred_monthly = money(
                goal.funding_gap / Decimal(max(1, goal.months_remaining + extension))
            )
            effect = money(max(ZERO, goal.monthly_required - deferred_monthly))
            adjustments.append(
                ConflictAdjustment(
                    action_code="defer_goal",
                    title=f"评估将“{goal.name}”延期 {extension} 个月",
                    detail=f"若家庭接受延期，月投入约可下降 {format_money(effect)}。",
                    affected_goal_ids=[goal.goal_id],
                    monthly_effect=effect,
                    preserves_minimum=True,
                )
            )
    adjustments.append(
        ConflictAdjustment(
            action_code="increase_savings",
            title="提高每月可持续结余",
            detail=f"若不调整目标，至少还需增加 {format_money(shortfall)}/月。",
            affected_goal_ids=[goal.goal_id for goal in projections if goal.funding_gap > ZERO],
            monthly_effect=shortfall,
            preserves_minimum=True,
        )
    )
    conflict = GoalConflict(
        conflict_id="monthly_goal_capacity",
        severity="critical" if available_monthly == ZERO else "warning",
        title="目标月投入超过当前新增结余",
        detail=(
            f"全部目标需要 {format_money(required_monthly)}/月，当前可用新增结余为 "
            f"{format_money(available_monthly)}/月，缺口 {format_money(shortfall)}/月。"
        ),
        affected_goal_ids=[goal.goal_id for goal in projections if goal.funding_gap > ZERO],
        available_monthly_surplus=available_monthly,
        required_monthly_contribution=required_monthly,
        monthly_shortfall=shortfall,
        adjustments=adjustments,
    )
    return [
        goal.model_copy(update={"status": "conflict"}) if goal.funding_gap > ZERO else goal
        for goal in projections
    ], [conflict]
