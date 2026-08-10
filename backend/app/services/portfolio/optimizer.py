from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import MarketScenario, PortfolioCandidateType, SuitabilityStatus
from app.domain.financial import HouseholdFacts
from app.schemas.portfolio import (
    AllocationLine,
    OptimizationDiagnostics,
    RebalanceLine,
    RebalancePlan,
    SuitabilityGateResult,
)
from app.services.financial.utils import ZERO, money
from app.services.portfolio.rules import CandidatePolicy, PortfolioRules

RATIO_QUANTUM = Decimal("0.000001")
ASSET_CLASS_NAMES = {
    "cash_equivalent": "现金与现金等价物",
    "fixed_income": "存款与分散固定收益",
    "diversified_equity": "宽基与分散权益",
    "real_assets": "公募 REITs 等实物资产工具",
    "gold": "黄金分散工具",
}
ASSET_CATEGORY_MAP = {
    "cash": "cash_equivalent",
    "demand_deposit": "cash_equivalent",
    "money_market": "cash_equivalent",
    "time_deposit": "fixed_income",
    "bank_wealth_management": "fixed_income",
    "bond": "fixed_income",
    "bond_fund": "fixed_income",
    "public_fund": "diversified_equity",
    "equity_fund": "diversified_equity",
    "stock": "single_equity",
}


def ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class PortfolioMetrics:
    objective: Decimal
    expected_return: Decimal
    expected_real_return: Decimal
    success_probability: Decimal
    range_low: Decimal
    range_base: Decimal
    range_high: Decimal
    cvar_loss: Decimal
    max_drawdown: Decimal
    liquidity_score: Decimal
    annual_fee_rate: Decimal
    responsibility_breach_probability: Decimal
    purchasing_power_success_probability: Decimal
    liability_coverage: Decimal
    liquidity_shortfall: Decimal
    concentration: Decimal
    real_return_after_fee: Decimal
    lexicographic_key: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class OptimizedCandidate:
    weights: dict[str, Decimal]
    tactical_weights: dict[str, Decimal]
    metrics: PortfolioMetrics
    allocations: list[AllocationLine]
    tactical_allocations: list[AllocationLine]
    diagnostics: OptimizationDiagnostics
    rebalancing: RebalancePlan


def current_growth_weights(
    facts: HouseholdFacts,
    rules: PortfolioRules,
) -> dict[str, Decimal]:
    amounts = {asset_class: ZERO for asset_class in rules.asset_classes}
    for asset in facts.assets:
        asset_class = ASSET_CATEGORY_MAP.get(asset.category.value)
        if asset_class is None or asset_class not in amounts:
            continue
        if asset.purpose not in {"长期增长", "养老", "财富传承", "长期投资"} and asset_class in {
            "cash_equivalent",
            "fixed_income",
        }:
            continue
        amounts[asset_class] += asset.market_value
    total = sum(amounts.values(), ZERO)
    if total <= 0:
        return {asset_class: ZERO for asset_class in rules.asset_classes}
    return {asset_class: ratio(amount / total) for asset_class, amount in amounts.items()}


def _compositions(
    total: int, parts: int, prefix: tuple[int, ...] = ()
) -> Iterator[tuple[int, ...]]:
    if parts == 1:
        yield (*prefix, total)
        return
    for value in range(total + 1):
        yield from _compositions(total - value, parts - 1, (*prefix, value))


def _weighted(weights: dict[str, Decimal], values: dict[str, Decimal]) -> Decimal:
    return sum((weights[key] * values[key] for key in weights), ZERO)


def _scenario_metrics(
    weights: dict[str, Decimal],
    amount: Decimal,
    goal_need: Decimal,
    horizon_months: int,
    current_weights: dict[str, Decimal],
    purchasing_power_hurdle: Decimal,
    rules: PortfolioRules,
) -> PortfolioMetrics:
    years = max(1, (horizon_months + 11) // 12)
    assumptions = rules.asset_assumptions
    expected_return = _weighted(
        weights,
        {key: value.expected_nominal_return for key, value in assumptions.items()},
    )
    cvar_loss = _weighted(weights, {key: value.cvar_loss for key, value in assumptions.items()})
    drawdown = _weighted(weights, {key: value.max_drawdown for key, value in assumptions.items()})
    liquidity = _weighted(
        weights,
        {key: value.liquidity_score for key, value in assumptions.items()},
    )
    fee_rate = _weighted(
        weights,
        {key: value.annual_fee_rate for key, value in assumptions.items()},
    )
    base_terminal = amount * (Decimal("1") + expected_return) ** years
    purchasing_power_target = amount * (Decimal("1") + purchasing_power_hurdle) ** years
    target = max(goal_need, purchasing_power_target)
    terminals: list[tuple[Decimal, Decimal]] = []
    success = ZERO
    purchasing_power_success = ZERO
    responsibility_breach = ZERO
    expected_shortfall = ZERO
    for scenario in rules.scenarios:
        scenario_return = _weighted(weights, scenario.returns)
        terminal = amount * (Decimal("1") + scenario_return) ** years
        terminals.append((scenario.probability, terminal))
        if amount > 0 and terminal >= target:
            success += scenario.probability
        if amount > 0 and terminal >= purchasing_power_target:
            purchasing_power_success += scenario.probability
        if goal_need > ZERO and terminal < goal_need:
            responsibility_breach += scenario.probability
        if target > 0 and terminal < target:
            expected_shortfall += scenario.probability * ((target - terminal) / target)
    turnover = sum(
        (abs(weights[key] - current_weights.get(key, ZERO)) for key in weights),
        ZERO,
    ) / Decimal("2")
    diversification = Decimal("1") - sum((value * value for value in weights.values()), ZERO)
    liquidity_shortfall = max(ZERO, rules.minimum_liquidity_score - liquidity)
    purchasing_shortfall = max(ZERO, purchasing_power_hurdle - expected_return)
    concentration = sum((value * value for value in weights.values()), ZERO)
    liability_coverage = (
        min(Decimal("1"), base_terminal / goal_need) if goal_need > ZERO else Decimal("1")
    )
    real_return_after_fee = expected_return - purchasing_power_hurdle - fee_rate
    objective_weights = rules.objective_weights
    objective = (
        objective_weights.cvar * cvar_loss
        + objective_weights.goal_shortfall * expected_shortfall
        + objective_weights.drawdown * drawdown
        + objective_weights.liquidity_shortfall * liquidity_shortfall
        + objective_weights.turnover * turnover
        + objective_weights.purchasing_power * purchasing_shortfall
        - objective_weights.success_probability * success
        - objective_weights.diversification * diversification
    )
    values = [terminal for _, terminal in terminals]
    return PortfolioMetrics(
        objective=ratio(objective),
        expected_return=ratio(expected_return),
        expected_real_return=ratio(expected_return - purchasing_power_hurdle),
        success_probability=ratio(success),
        range_low=money(min(values, default=ZERO)),
        range_base=money(base_terminal),
        range_high=money(max(values, default=ZERO)),
        cvar_loss=ratio(cvar_loss),
        max_drawdown=ratio(drawdown),
        liquidity_score=ratio(liquidity),
        annual_fee_rate=ratio(fee_rate),
        responsibility_breach_probability=ratio(responsibility_breach),
        purchasing_power_success_probability=ratio(purchasing_power_success),
        liability_coverage=ratio(liability_coverage),
        liquidity_shortfall=ratio(liquidity_shortfall),
        concentration=ratio(concentration),
        real_return_after_fee=ratio(real_return_after_fee),
        lexicographic_key=(
            ratio(responsibility_breach),
            ratio(liquidity_shortfall),
            ratio(cvar_loss + drawdown),
            ratio(-success),
            ratio(fee_rate + turnover),
            ratio(objective),
        ),
    )


def _within_policy(
    weights: dict[str, Decimal],
    policy: CandidatePolicy,
    high_risk_cap: Decimal,
    rules: PortfolioRules,
) -> bool:
    for asset_class, value in weights.items():
        lower, upper = policy.bounds[asset_class]
        if value < lower or value > upper:
            return False
        if value > rules.suitability.maximum_single_asset_class_ratio:
            return False
    high_risk = weights["diversified_equity"] + weights["real_assets"]
    if high_risk > high_risk_cap:
        return False
    liquidity = _weighted(
        weights,
        {key: value.liquidity_score for key, value in rules.asset_assumptions.items()},
    )
    return liquidity >= rules.minimum_liquidity_score


def _fallback_weights(
    policy: CandidatePolicy,
    high_risk_cap: Decimal,
    rules: PortfolioRules,
) -> dict[str, Decimal]:
    weights = dict(policy.fallback)
    risky = weights["diversified_equity"] + weights["real_assets"]
    if risky > high_risk_cap:
        removed = risky - high_risk_cap
        if risky > 0:
            factor = high_risk_cap / risky
            weights["diversified_equity"] *= factor
            weights["real_assets"] *= factor
        weights["fixed_income"] += removed
    maximum = rules.suitability.maximum_single_asset_class_ratio
    if weights["fixed_income"] > maximum:
        excess = weights["fixed_income"] - maximum
        weights["fixed_income"] = maximum
        gold_room = max(ZERO, policy.bounds["gold"][1] - weights["gold"])
        gold_addition = min(excess, gold_room)
        weights["gold"] += gold_addition
        weights["cash_equivalent"] += excess - gold_addition
    total = sum(weights.values(), ZERO)
    if total != Decimal("1"):
        weights["cash_equivalent"] += Decimal("1") - total
    return {key: ratio(value) for key, value in weights.items()}


def _tactical_weights(
    strategic: dict[str, Decimal],
    market_scenario: MarketScenario,
    high_risk_cap: Decimal,
    family_gate: SuitabilityGateResult,
    customer_gate: SuitabilityGateResult,
    rules: PortfolioRules,
) -> dict[str, Decimal]:
    tactical = dict(strategic)
    if (
        market_scenario == MarketScenario.NEUTRAL
        or family_gate.status != SuitabilityStatus.PASS
        or customer_gate.status != SuitabilityStatus.PASS
    ):
        return tactical
    shift = rules.rebalancing.maximum_tactical_shift
    if market_scenario == MarketScenario.RISK_OFF:
        actual = min(shift, tactical["diversified_equity"])
        tactical["diversified_equity"] -= actual
        tactical["fixed_income"] += actual
    elif market_scenario == MarketScenario.RISK_ON:
        risk_room = max(
            ZERO,
            high_risk_cap - tactical["diversified_equity"] - tactical["real_assets"],
        )
        actual = min(shift, risk_room, tactical["fixed_income"])
        tactical["fixed_income"] -= actual
        tactical["diversified_equity"] += actual
    return {key: ratio(value) for key, value in tactical.items()}


def _allocation_lines(
    weights: dict[str, Decimal],
    amount: Decimal,
    rules: PortfolioRules,
) -> list[AllocationLine]:
    return [
        AllocationLine(
            asset_class=asset_class,
            asset_class_name=ASSET_CLASS_NAMES[asset_class],
            ratio=value,
            amount=money(amount * value),
            expected_nominal_return=rules.asset_assumptions[asset_class].expected_nominal_return,
            cvar_loss=rules.asset_assumptions[asset_class].cvar_loss,
            max_drawdown=rules.asset_assumptions[asset_class].max_drawdown,
            liquidity_score=rules.asset_assumptions[asset_class].liquidity_score,
        )
        for asset_class, value in weights.items()
    ]


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    month_days = [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    return date(year, month, min(value.day, month_days[month - 1]))


def _rebalance_plan(
    current: dict[str, Decimal],
    strategic: dict[str, Decimal],
    tactical: dict[str, Decimal],
    analysis_date: date,
    market_scenario: MarketScenario,
    family_gate: SuitabilityGateResult,
    rules: PortfolioRules,
) -> RebalancePlan:
    lines: list[RebalanceLine] = []
    for asset_class in rules.asset_classes:
        current_ratio = current.get(asset_class, ZERO)
        strategic_ratio = strategic[asset_class]
        tactical_ratio = tactical[asset_class]
        absolute = ratio(abs(current_ratio - tactical_ratio))
        relative = ratio(absolute / tactical_ratio) if tactical_ratio > 0 else None
        trigger = absolute >= rules.rebalancing.absolute_drift_threshold or (
            relative is not None and relative >= rules.rebalancing.relative_drift_threshold
        )
        if current_ratio > tactical_ratio:
            action = "降低至战术区间"
        elif current_ratio < tactical_ratio:
            action = "补充至战术区间"
        else:
            action = "保持"
        lines.append(
            RebalanceLine(
                asset_class=asset_class,
                asset_class_name=ASSET_CLASS_NAMES[asset_class],
                current_ratio=current_ratio,
                strategic_ratio=strategic_ratio,
                tactical_ratio=tactical_ratio,
                absolute_drift=absolute,
                relative_drift=relative,
                trigger=trigger,
                action=action,
            )
        )
    if family_gate.status != SuitabilityStatus.PASS:
        status = "blocked_by_safety"
        explanation = "家庭安全闸门未通过；暂停按市场情景扩张，先把资金补回前置账户。"
    elif any(item.trigger for item in lines):
        status = "rebalance_due"
        explanation = "达到绝对 5 个百分点或相对 20% 偏离条件，建议复核后再平衡。"
    else:
        status = "within_band"
        explanation = "当前偏离未达到阈值；仍在六个月例行复核周期内。"
    return RebalancePlan(
        market_scenario=market_scenario,
        status=status,
        absolute_threshold=rules.rebalancing.absolute_drift_threshold,
        relative_threshold=rules.rebalancing.relative_drift_threshold,
        maximum_tactical_shift=rules.rebalancing.maximum_tactical_shift,
        next_scheduled_review=_add_months(
            analysis_date,
            rules.rebalancing.scheduled_review_months,
        ),
        lines=lines,
        explanation=explanation,
    )


def optimize_candidate(
    candidate_type: PortfolioCandidateType,
    amount: Decimal,
    goal_need: Decimal,
    horizon_months: int,
    current_weights: dict[str, Decimal],
    purchasing_power_hurdle: Decimal,
    high_risk_cap: Decimal,
    analysis_date: date,
    market_scenario: MarketScenario,
    family_gate: SuitabilityGateResult,
    customer_gate: SuitabilityGateResult,
    rules: PortfolioRules,
    *,
    force_solver_failure: bool = False,
) -> OptimizedCandidate:
    policy = rules.candidate_policies[candidate_type.value]
    parameter_payload = {
        "candidate": candidate_type.value,
        "amount": str(amount),
        "goal_need": str(goal_need),
        "horizon_months": horizon_months,
        "current_weights": {key: str(value) for key, value in current_weights.items()},
        "purchasing_power_hurdle": str(purchasing_power_hurdle),
        "inflation_rate_deprecated": str(purchasing_power_hurdle),
        "high_risk_cap": str(high_risk_cap),
        "market_scenario": market_scenario.value,
        "rule_version": rules.semantic_version,
    }
    parameter_hash = hashlib.sha256(
        json.dumps(parameter_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    step_units = int(Decimal("1") / rules.grid_step)
    best_weights: dict[str, Decimal] | None = None
    best_metrics: PortfolioMetrics | None = None
    evaluated = 0
    if not force_solver_failure:
        for composition in _compositions(step_units, len(rules.asset_classes)):
            weights = {
                asset_class: Decimal(units) / Decimal(step_units)
                for asset_class, units in zip(rules.asset_classes, composition, strict=True)
            }
            if not _within_policy(weights, policy, high_risk_cap, rules):
                continue
            evaluated += 1
            metrics = _scenario_metrics(
                weights,
                amount,
                goal_need,
                horizon_months,
                current_weights,
                purchasing_power_hurdle,
                rules,
            )
            if best_metrics is None or metrics.lexicographic_key < best_metrics.lexicographic_key:
                best_weights = weights
                best_metrics = metrics
    fallback_reason: str | None = None
    if best_weights is None or best_metrics is None:
        best_weights = _fallback_weights(policy, high_risk_cap, rules)
        best_metrics = _scenario_metrics(
            best_weights,
            amount,
            goal_need,
            horizon_months,
            current_weights,
            purchasing_power_hurdle,
            rules,
        )
        method = "rule_based_fallback"
        status = "fallback"
        fallback_reason = (
            "测试强制触发求解失败。"
            if force_solver_failure
            else "候选原始边界与家庭／客户风险上限无可行交集，已使用审慎规则型组合。"
        )
    else:
        method = "deterministic_grid_search"
        status = "optimal"
    strategic = {key: ratio(value) for key, value in best_weights.items()}
    tactical = _tactical_weights(
        strategic,
        market_scenario,
        high_risk_cap,
        family_gate,
        customer_gate,
        rules,
    )
    return OptimizedCandidate(
        weights=strategic,
        tactical_weights=tactical,
        metrics=best_metrics,
        allocations=_allocation_lines(strategic, amount, rules),
        tactical_allocations=_allocation_lines(tactical, amount, rules),
        diagnostics=OptimizationDiagnostics(
            method=method,
            status=status,
            optimizer_version=rules.optimizer_version,
            random_seed=rules.random_seed,
            grid_step=rules.grid_step,
            evaluated_candidates=evaluated,
            objective_score=best_metrics.objective,
            parameter_hash=parameter_hash,
            parameters=parameter_payload,
            fallback_reason=fallback_reason,
        ),
        rebalancing=_rebalance_plan(
            current_weights,
            strategic,
            tactical,
            analysis_date,
            market_scenario,
            family_gate,
            rules,
        ),
    )
