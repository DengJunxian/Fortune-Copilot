from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from app.domain.enums import GoalRigidity, RiskLevel
from app.schemas.cfs import HouseholdRiskBudget, RiskBudgetFactor
from app.schemas.client_profile import ClientProfileResponse
from app.schemas.eligible_capital import EligibleCapitalResponse
from app.schemas.family_enterprise import FamilyEnterpriseView
from app.schemas.liability import LiabilityCalendarResponse
from app.services.cfs_composer.rules import CFSComposerRules
from app.services.financial.utils import ONE, ZERO, money, ratio

_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM_LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.MEDIUM_HIGH: 3,
    RiskLevel.HIGH: 4,
}
_RISK_BY_ORDER = {value: key for key, value in _RISK_ORDER.items()}


def _min_level(*levels: RiskLevel) -> RiskLevel:
    return min(levels, key=lambda item: _RISK_ORDER[item])


def _cap_level(level: RiskLevel, ceiling: RiskLevel) -> RiskLevel:
    return _RISK_BY_ORDER[min(_RISK_ORDER[level], _RISK_ORDER[ceiling])]


def _step_down(level: RiskLevel) -> RiskLevel:
    return _RISK_BY_ORDER[max(0, _RISK_ORDER[level] - 1)]


def _bounded_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= ZERO:
        return ZERO
    return ratio(min(ONE, max(ZERO, numerator / denominator)))


def build_household_risk_budget(
    profile: ClientProfileResponse,
    liability: LiabilityCalendarResponse,
    eligible: EligibleCapitalResponse,
    family_enterprise: FamilyEnterpriseView,
    rules: CFSComposerRules,
    analysis_date: date,
) -> HouseholdRiskBudget:
    economic_wealth = family_enterprise.wealth.economic_household_wealth
    exposure = family_enterprise.economic_capital.total_economic_equity_exposure
    exposure_ratio = _bounded_ratio(exposure, economic_wealth)
    bridge_by_code = {item.code: item for item in eligible.calculation.bridge}
    liquidity_steps = [
        bridge_by_code[code]
        for code in ("operating_liquidity", "emergency_reserve")
        if code in bridge_by_code
    ]
    liquidity_required = money(
        sum((item.requested_deduction for item in liquidity_steps), ZERO)
    )
    liquidity_gap = money(sum((item.unfunded for item in liquidity_steps), ZERO))

    rigid_entries = [
        item for item in liability.entries if item.stream.rigidity == GoalRigidity.RIGID
    ]
    rigid_target = money(sum((item.target_total for item in rigid_entries), ZERO))
    rigid_gap = money(sum((item.funding_gap for item in rigid_entries), ZERO))
    rigid_ratio = (
        ratio(rigid_gap / economic_wealth) if economic_wealth > ZERO else ZERO
    )
    future_dates = [
        row.due_date
        for entry in liability.entries
        for row in entry.cashflows
        if row.due_date >= analysis_date
    ]
    shortest_days = min(((item - analysis_date).days for item in future_dates), default=None)

    capacity = profile.profile.risk_capacity
    willingness = profile.profile.risk_willingness
    behavior = profile.profile.behavior_limit
    economic_capacity = _min_level(capacity, willingness, behavior)
    constraints: list[str] = []
    if liquidity_gap > ZERO:
        economic_capacity = RiskLevel.LOW
        constraints.append("经营周转与应急储备尚有缺口，风险预算先降至较低水平。")
    if rigid_ratio >= rules.high_liability_rigidity_ratio:
        economic_capacity = _step_down(economic_capacity)
        constraints.append("刚性责任缺口占经济财富较高，风险预算向下收紧一级。")
    if shortest_days is not None and shortest_days <= rules.short_horizon_days:
        economic_capacity = _cap_level(economic_capacity, RiskLevel.MEDIUM_LOW)
        constraints.append("三年内存在责任现金流，不用近期资金承担较高波动。")

    failed_gates = [item for item in eligible.calculation.eligibility_gates if not item.passed]
    constraints.extend(item.reason for item in failed_gates)
    constraints.extend(family_enterprise.cfs_implication.constraints)
    constraints = list(dict.fromkeys(constraints))

    ceiling_ratio = rules.risk_ceiling_by_level[economic_capacity]
    ceiling_amount = money(economic_wealth * ceiling_ratio)
    remaining = money(max(ZERO, ceiling_amount - exposure))
    if not eligible.calculation.formally_eligible or liquidity_gap > ZERO:
        decision = "repair_first"
    elif not family_enterprise.economic_capital.additional_equity_risk_allowed:
        decision = "professional_only"
    else:
        decision = "open"
    additional_allowed = decision == "open" and remaining > ZERO
    if not additional_allowed:
        remaining = ZERO

    canonical = {
        "analysis_date": analysis_date.isoformat(),
        "profile_id": profile.profile.id,
        "profile_version": profile.profile.profile_version,
        "need_liability_version": liability.meta.formula_version,
        "eligible_input_hash": eligible.meta.input_hash,
        "family_input_hash": family_enterprise.meta.input_hash,
        "rules": [rules.semantic_version, rules.formula_version],
        "capacity": capacity.value,
        "willingness": willingness.value,
        "behavior": behavior.value,
        "economic_capacity": economic_capacity.value,
        "exposure": str(exposure),
        "liquidity_gap": str(liquidity_gap),
        "rigid_gap": str(rigid_gap),
        "shortest_days": shortest_days,
    }
    input_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    factors = [
        RiskBudgetFactor(
            code="capacity",
            label="风险承担能力",
            level=capacity,
            explanation="由收入、资产负债和责任期限决定家庭承受损失的能力。",
        ),
        RiskBudgetFactor(
            code="willingness",
            label="风险承担意愿",
            level=willingness,
            explanation="使用有效风险评估，不把意愿自动等同于可承担能力。",
        ),
        RiskBudgetFactor(
            code="behavior",
            label="行为承受上限",
            level=behavior,
            explanation="以真实行为边界限制问卷中可能偏高的风险意愿。",
        ),
        RiskBudgetFactor(
            code="existing_economic_exposure",
            label="现有经济权益暴露",
            amount=exposure,
            ratio=exposure_ratio,
            explanation="同时纳入证券权益、企业股权、雇主股和股权激励。",
        ),
        RiskBudgetFactor(
            code="liquidity",
            label="流动性安全垫",
            amount=liquidity_gap,
            ratio=_bounded_ratio(liquidity_gap, liquidity_required),
            explanation="显示经营周转和应急储备的未覆盖比例。",
        ),
        RiskBudgetFactor(
            code="liability_rigidity",
            label="刚性责任",
            amount=rigid_gap,
            ratio=rigid_ratio,
            explanation="刚性责任缺口越高，可用于承担波动的经济资本越少。",
        ),
        RiskBudgetFactor(
            code="time_horizon",
            label="最短责任期限",
            amount=Decimal(shortest_days or 0),
            ratio=(
                ratio(Decimal(shortest_days) / Decimal(rules.short_horizon_days))
                if shortest_days is not None
                else ZERO
            ),
            explanation="以最近一笔未来责任约束可承受风险，不代表建议持有期。",
        ),
    ]
    return HouseholdRiskBudget(
        factors=factors,
        capacity=capacity,
        willingness=willingness,
        behavior=behavior,
        household_economic_risk_capacity=economic_capacity,
        existing_economic_exposure=exposure,
        economic_exposure_ratio=exposure_ratio,
        liquidity_reserve_required=liquidity_required,
        liquidity_gap=liquidity_gap,
        rigid_liability_target=rigid_target,
        rigid_liability_gap=rigid_gap,
        shortest_time_horizon_days=shortest_days,
        risk_ceiling_ratio=ceiling_ratio,
        risk_ceiling_amount=ceiling_amount,
        remaining_risk_capacity=remaining,
        additional_risk_allowed=additional_allowed,
        decision=decision,
        constraints=constraints,
        input_hash=input_hash,
        version=f"{rules.formula_version}:{input_hash[:12]}",
        explanation=(
            "Risk Budget 表示 household economic risk capacity；"
            "它由能力、意愿、行为、现有经济暴露、流动性、刚性责任和期限共同约束，"
            "不是单一 R1-R5 标签。"
        ),
    )
