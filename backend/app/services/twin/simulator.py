from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import IncomeType
from app.schemas.twin import (
    DistributionValidation,
    FailureTimeBucket,
    FanPoint,
    GoalSimulationOutcome,
    PlanAdjustments,
    ResolvedAssumptionSnapshot,
    ScenarioImpact,
    SimulationDistribution,
    TwinComparison,
    TwinRunRequest,
    WorstPath,
)
from app.services.twin.rules import ScenarioRule, TwinRules, cholesky_for_rules, cholesky_matrix
from app.services.twin.state import GoalSpec, TwinModelInput

MONEY_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.000001")
PAYMENT_TOLERANCE = 0.005


@dataclass(frozen=True, slots=True)
class ResolvedScenario:
    codes: tuple[str, ...]
    name: str
    income_interruption_months: int
    income_reduction_ratio: float
    income_reduction_months: int
    income_reduction_target: str
    medical_shock_amount: float
    family_support_monthly_increase: float
    family_support_duration_months: int
    education_overrun_amount: float
    retirement_age_reduction_years: int
    longevity_extension_years: int
    mortgage_rate_increase: float
    investment_property_vacancy_months: int
    investment_property_value_shock: float
    property_value_shock: float
    asset_return_shocks: dict[str, float]
    asset_volatility_multipliers: dict[str, float]
    long_term_return_reduction: float
    inflation_increase: float
    goal_advance_months: int


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    seed: int
    path_count: int
    horizon_months: int
    output_interval_months: int
    inflation_rate: float
    income_growth_rate: float
    asset_classes: tuple[str, ...]
    asset_assumptions: dict[str, tuple[float, float]]
    correlation_matrix: list[list[Decimal]]
    cholesky: list[list[float]]
    property_assumption: tuple[float, float]
    pension_assumption: tuple[float, float]
    other_asset_annual_depreciation: float
    maximum_balance: float
    scenario: ResolvedScenario
    plan_adjustments: PlanAdjustments


@dataclass(frozen=True, slots=True)
class PathSnapshot:
    net_worth: float
    liquid_assets: float
    long_term_assets: float
    liabilities: float


@dataclass(frozen=True, slots=True)
class PathResult:
    path_id: int
    snapshots: tuple[PathSnapshot, ...]
    ending_net_worth: float
    minimum_net_worth: float
    goal_success: dict[str, bool]
    goal_shortfalls: dict[str, float]
    goal_required: dict[str, float]
    first_failed_goal: str | None
    first_failure_month: int | None
    depletion_month: int | None
    forced_sale_amount: float
    total_goal_shortfall: float
    primary_income_during_interruption: float
    goal_spending_events: int


def _money(value: float, maximum: float = 1e15) -> Decimal:
    if not math.isfinite(value):
        raise ValueError("模拟结果出现非有限金额")
    bounded = min(max(value, -maximum), maximum)
    return Decimal(str(bounded)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _nonnegative_money(value: float, maximum: float = 1e15) -> Decimal:
    return _money(max(0.0, value), maximum)


def _ratio(value: float) -> Decimal:
    if not math.isfinite(value):
        raise ValueError("模拟结果出现非有限比例")
    return Decimal(str(min(1.0, max(0.0, value)))).quantize(
        RATIO_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _signed_ratio(value: float) -> Decimal:
    if not math.isfinite(value):
        raise ValueError("模拟结果出现非有限变化比例")
    return Decimal(str(min(1.0, max(-1.0, value)))).quantize(
        RATIO_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _add_months(value: date, months: int) -> date:
    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28]
    days.extend([31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    return date(year, month, min(value.day, days[month - 1]))


def _combine_shock(current: float, addition: float) -> float:
    return max(-0.95, min(0.50, (1 + current) * (1 + addition) - 1))


def resolve_scenario(
    rules: TwinRules,
    request: TwinRunRequest,
    scenario_codes: list[str],
) -> ResolvedScenario:
    by_code: dict[str, ScenarioRule] = {item.code: item for item in rules.scenarios}
    unknown = sorted(set(scenario_codes) - set(by_code))
    if unknown:
        raise ValueError(f"未知压力场景：{', '.join(unknown)}")
    interruption = 0
    reduction = 0.0
    reduction_months = 0
    reduction_target = "primary"
    medical = 0.0
    support = 0.0
    support_months = 0
    education = 0.0
    retirement_reduction = 0
    longevity = 0
    mortgage_rate = 0.0
    vacancy = 0
    investment_property_shock = 0.0
    property_shock = 0.0
    shocks = {asset_class: 0.0 for asset_class in rules.asset_classes}
    volatility = {asset_class: 1.0 for asset_class in rules.asset_classes}
    return_reduction = 0.0
    inflation_increase = 0.0
    goal_advance = 0
    targets: set[str] = set()
    for code in scenario_codes:
        scenario = by_code[code]
        parameters = scenario.parameters
        interruption = max(interruption, parameters.income_interruption_months)
        reduction = max(reduction, float(parameters.income_reduction_ratio))
        reduction_months = max(reduction_months, parameters.income_reduction_months)
        if parameters.income_reduction_ratio > 0:
            targets.add(parameters.income_reduction_target)
        medical += float(parameters.medical_shock_amount)
        support += float(parameters.family_support_monthly_increase)
        support_months = max(support_months, parameters.family_support_duration_months)
        education += float(parameters.education_overrun_amount)
        retirement_reduction = max(
            retirement_reduction,
            parameters.retirement_age_reduction_years,
        )
        longevity = max(longevity, parameters.longevity_extension_years)
        mortgage_rate += float(parameters.mortgage_rate_increase)
        vacancy = max(vacancy, parameters.investment_property_vacancy_months)
        if code == "investment_property_vacancy_discount":
            investment_property_shock = _combine_shock(
                investment_property_shock,
                float(parameters.property_value_shock),
            )
        else:
            property_shock = _combine_shock(
                property_shock,
                float(parameters.property_value_shock),
            )
        for asset_class, value in parameters.asset_return_shocks.items():
            shocks[asset_class] = _combine_shock(shocks[asset_class], float(value))
        for asset_class, value in parameters.asset_volatility_multipliers.items():
            volatility[asset_class] = max(volatility[asset_class], float(value))
        return_reduction = max(return_reduction, float(parameters.long_term_return_reduction))
        inflation_increase += float(parameters.inflation_increase)
        goal_advance = max(goal_advance, parameters.goal_advance_months)
    if "all" in targets or len(targets) > 1:
        reduction_target = "all"
    elif targets:
        reduction_target = next(iter(targets))
    overrides = request.scenario_overrides
    if overrides.unemployment_months is not None:
        interruption = overrides.unemployment_months
    if overrides.income_reduction_ratio is not None:
        reduction = float(overrides.income_reduction_ratio)
        reduction_months = max(reduction_months, request.horizon_years * 12)
    if overrides.medical_shock_amount is not None:
        medical = float(overrides.medical_shock_amount)
    if overrides.education_overrun_amount is not None:
        education = float(overrides.education_overrun_amount)
    if overrides.property_value_change_ratio is not None:
        property_shock = float(overrides.property_value_change_ratio)
    if overrides.mortgage_rate_change is not None:
        mortgage_rate = float(overrides.mortgage_rate_change)
    return ResolvedScenario(
        codes=tuple(scenario_codes),
        name=" + ".join(by_code[code].name for code in scenario_codes),
        income_interruption_months=interruption,
        income_reduction_ratio=reduction,
        income_reduction_months=reduction_months,
        income_reduction_target=reduction_target,
        medical_shock_amount=medical,
        family_support_monthly_increase=support,
        family_support_duration_months=support_months,
        education_overrun_amount=education,
        retirement_age_reduction_years=retirement_reduction,
        longevity_extension_years=longevity,
        mortgage_rate_increase=max(-0.20, min(0.20, mortgage_rate)),
        investment_property_vacancy_months=vacancy,
        investment_property_value_shock=investment_property_shock,
        property_value_shock=property_shock,
        asset_return_shocks=shocks,
        asset_volatility_multipliers=volatility,
        long_term_return_reduction=return_reduction,
        inflation_increase=min(0.20, inflation_increase),
        goal_advance_months=goal_advance,
    )


def resolve_simulation_config(
    rules: TwinRules,
    request: TwinRunRequest,
    scenario_codes: list[str],
    plan_adjustments: PlanAdjustments,
) -> SimulationConfig:
    if not rules.minimum_path_count <= request.path_count <= rules.maximum_path_count:
        raise ValueError("路径数超出当前规则版本允许范围")
    if not rules.minimum_horizon_years <= request.horizon_years <= rules.maximum_horizon_years:
        raise ValueError("模拟期限超出当前规则版本允许范围")
    scenario = resolve_scenario(rules, request, scenario_codes)
    assumptions = {
        key: (
            float(value.expected_annual_return),
            float(value.annual_volatility),
        )
        for key, value in rules.asset_assumptions.items()
    }
    unknown_assumptions = sorted(
        set(request.assumption_overrides.asset_assumptions) - set(rules.asset_classes)
    )
    if unknown_assumptions:
        raise ValueError(f"收益覆盖引用未知资产类别：{', '.join(unknown_assumptions)}")
    for key, override in request.assumption_overrides.asset_assumptions.items():
        expected, volatility = assumptions[key]
        assumptions[key] = (
            float(override.expected_annual_return)
            if override.expected_annual_return is not None
            else expected,
            float(override.annual_volatility)
            if override.annual_volatility is not None
            else volatility,
        )
    matrix = request.assumption_overrides.correlation_matrix or rules.correlation_matrix
    if len(matrix) != len(rules.asset_classes) or any(
        len(row) != len(rules.asset_classes) for row in matrix
    ):
        raise ValueError("相关矩阵维度与资产类别不一致")
    cholesky = (
        cholesky_matrix(matrix)
        if request.assumption_overrides.correlation_matrix is not None
        else cholesky_for_rules(rules)
    )
    return SimulationConfig(
        seed=request.seed,
        path_count=request.path_count,
        horizon_months=(request.horizon_years + scenario.longevity_extension_years) * 12,
        output_interval_months=request.output_interval_months,
        inflation_rate=float(
            request.assumption_overrides.inflation_rate
            if request.assumption_overrides.inflation_rate is not None
            else rules.base_inflation_rate
        )
        + scenario.inflation_increase,
        income_growth_rate=float(
            request.assumption_overrides.income_growth_rate
            if request.assumption_overrides.income_growth_rate is not None
            else rules.base_income_growth_rate
        ),
        asset_classes=tuple(rules.asset_classes),
        asset_assumptions=assumptions,
        correlation_matrix=matrix,
        cholesky=cholesky,
        property_assumption=(
            float(rules.property_assumption.expected_annual_return),
            float(rules.property_assumption.annual_volatility),
        ),
        pension_assumption=(
            float(rules.pension_assumption.expected_annual_return),
            float(rules.pension_assumption.annual_volatility),
        ),
        other_asset_annual_depreciation=float(rules.other_asset_annual_depreciation),
        maximum_balance=float(rules.maximum_balance),
        scenario=scenario,
        plan_adjustments=plan_adjustments,
    )


def _correlated_normals(rng: random.Random, cholesky: list[list[float]]) -> list[float]:
    independent = [rng.gauss(0.0, 1.0) for _ in cholesky]
    return [
        sum(cholesky[row][column] * independent[column] for column in range(row + 1))
        for row in range(len(cholesky))
    ]


def _monthly_return(mean: float, volatility: float, normal: float) -> float:
    adjusted_mean = max(-0.95, mean)
    log_mean = math.log1p(adjusted_mean)
    exponent = (log_mean - 0.5 * volatility * volatility) / 12 + (volatility / math.sqrt(12)) * max(
        -8.0, min(8.0, normal)
    )
    return max(-0.95, min(1.5, math.exp(exponent) - 1))


def _cap(value: float, maximum: float) -> float:
    if not math.isfinite(value):
        raise ValueError("状态转移产生非有限值")
    return min(maximum, max(0.0, value))


def _withdraw(
    buckets: dict[str, float],
    amount: float,
    *,
    allow_pension: bool,
) -> tuple[float, float]:
    remaining = max(0.0, amount)
    paid = 0.0
    forced_sale = 0.0
    order = ["cash_equivalent", "fixed_income", "gold", "real_assets", "diversified_equity"]
    if allow_pension:
        order.append("pension")
    for key in order:
        available = buckets.get(key, 0.0)
        used = min(available, remaining)
        buckets[key] = available - used
        remaining -= used
        paid += used
        if key in {"gold", "real_assets", "diversified_equity", "pension"}:
            forced_sale += used
        if remaining <= 1e-7:
            break
    return paid, forced_sale


def _apply_plan_adjustments(buckets: dict[str, float], plan: PlanAdjustments) -> None:
    reallocation = float(plan.liquidity_reallocation_amount)
    for key in ("diversified_equity", "real_assets", "gold", "fixed_income"):
        used = min(buckets.get(key, 0.0), reallocation)
        buckets[key] -= used
        buckets["cash_equivalent"] += used
        reallocation -= used
        if reallocation <= 1e-7:
            break
    if plan.equity_ratio is None:
        return
    movable = buckets["fixed_income"] + buckets["diversified_equity"]
    investable = sum(
        buckets[key]
        for key in ("cash_equivalent", "fixed_income", "diversified_equity", "real_assets", "gold")
    )
    desired_equity = min(movable, investable * float(plan.equity_ratio))
    buckets["diversified_equity"] = desired_equity
    buckets["fixed_income"] = movable - desired_equity


def _goal_schedule(
    goals: tuple[GoalSpec, ...],
    config: SimulationConfig,
) -> dict[int, list[tuple[GoalSpec, float]]]:
    schedule: dict[int, list[tuple[GoalSpec, float]]] = defaultdict(list)
    for goal in goals:
        due_month = max(1, goal.due_month - config.scenario.goal_advance_months)
        if due_month > config.horizon_months:
            continue
        cost_growth = max(-0.50, goal.annual_cost_growth_rate + config.scenario.inflation_increase)
        required = goal.target_amount * (1 + cost_growth) ** (due_month / 12)
        if goal.goal_type == "education":
            required += config.scenario.education_overrun_amount
        schedule[due_month].append((goal, required))
    return schedule


def _snapshot(
    buckets: dict[str, float],
    debt_balances: list[float],
    unmet_obligations: float,
) -> PathSnapshot:
    liabilities = sum(debt_balances) + unmet_obligations
    total_assets = sum(buckets.values())
    return PathSnapshot(
        net_worth=total_assets - liabilities,
        liquid_assets=buckets["cash_equivalent"] + buckets["fixed_income"],
        long_term_assets=(
            buckets["diversified_equity"]
            + buckets["real_assets"]
            + buckets["gold"]
            + buckets["pension"]
        ),
        liabilities=liabilities,
    )


def _simulate_path(
    model: TwinModelInput,
    config: SimulationConfig,
    request: TwinRunRequest,
    path_id: int,
) -> PathResult:
    rng = random.Random(config.seed ^ ((path_id + 1) * 2_654_435_761))
    buckets = dict(model.asset_buckets)
    _apply_plan_adjustments(buckets, config.plan_adjustments)
    debt_balances = [item.balance for item in model.debts]
    goal_schedule = _goal_schedule(model.goals, config)
    goal_success: dict[str, bool] = {
        goal.id: True for values in goal_schedule.values() for goal, _ in values
    }
    goal_shortfalls: dict[str, float] = {goal_id: 0.0 for goal_id in goal_success}
    goal_required: dict[str, float] = {
        goal.id: required for values in goal_schedule.values() for goal, required in values
    }
    snapshot_months = list(range(0, config.horizon_months + 1, config.output_interval_months))
    if snapshot_months[-1] != config.horizon_months:
        snapshot_months.append(config.horizon_months)
    snapshots = [_snapshot(buckets, debt_balances, 0.0)]
    first_failed_goal: str | None = None
    first_failure_month: int | None = None
    depletion_month: int | None = None
    forced_sale_amount = 0.0
    unmet_obligations = 0.0
    minimum_net_worth = snapshots[0].net_worth
    interruption_income = 0.0
    goal_spending_events = 0
    member_age = {item.id: item.age_at_start for item in model.members}
    all_employment_retired = False
    for month in range(1, config.horizon_months + 1):
        normals = _correlated_normals(rng, config.cholesky)
        normal_by_class = dict(zip(config.asset_classes, normals, strict=True))
        for asset_class in config.asset_classes:
            mean, volatility = config.asset_assumptions[asset_class]
            if asset_class != "cash_equivalent":
                mean -= config.scenario.long_term_return_reduction
            volatility *= config.scenario.asset_volatility_multipliers[asset_class]
            monthly = _monthly_return(mean, volatility, normal_by_class[asset_class])
            if month == 1:
                monthly = _combine_shock(monthly, config.scenario.asset_return_shocks[asset_class])
            buckets[asset_class] = _cap(
                buckets.get(asset_class, 0.0) * (1 + monthly),
                config.maximum_balance,
            )
        property_mean, property_volatility = config.property_assumption
        property_return = _monthly_return(
            property_mean,
            property_volatility,
            normal_by_class.get("real_assets", 0.0),
        )
        for key in ("primary_property", "investment_property"):
            applied_return = property_return
            if month == 1:
                applied_return = _combine_shock(
                    applied_return, config.scenario.property_value_shock
                )
                if key == "investment_property":
                    applied_return = _combine_shock(
                        applied_return,
                        config.scenario.investment_property_value_shock,
                    )
            buckets[key] = _cap(
                buckets.get(key, 0.0) * (1 + applied_return),
                config.maximum_balance,
            )
        pension_mean, pension_volatility = config.pension_assumption
        pension_normal = (
            normal_by_class.get("fixed_income", 0.0)
            + normal_by_class.get("diversified_equity", 0.0)
        ) / 2
        buckets["pension"] = _cap(
            buckets["pension"]
            * (1 + _monthly_return(pension_mean, pension_volatility, pension_normal)),
            config.maximum_balance,
        )
        buckets["other_assets"] = _cap(
            buckets["other_assets"] * (1 - config.other_asset_annual_depreciation) ** (1 / 12),
            config.maximum_balance,
        )

        total_income = 0.0
        active_employment = 0
        for stream in model.incomes:
            income_normal = rng.gauss(0.0, 1.0)
            member_current_age = (
                member_age.get(stream.member_id, 0.0) + month / 12
                if stream.member_id is not None
                else 0.0
            )
            retirement_age = stream.retirement_age
            if (
                stream.primary_rank == 1
                and config.plan_adjustments.primary_retirement_age is not None
            ):
                retirement_age = config.plan_adjustments.primary_retirement_age
            if retirement_age is not None:
                retirement_age -= config.scenario.retirement_age_reduction_years
            retired = (
                stream.income_type == IncomeType.EMPLOYMENT
                and retirement_age is not None
                and member_current_age >= retirement_age
            )
            noise = math.exp(
                -0.5 * stream.annual_volatility**2 / 12
                + stream.annual_volatility / math.sqrt(12) * max(-5.0, min(5.0, income_normal))
            )
            income = stream.monthly_amount * (1 + config.income_growth_rate) ** (month / 12) * noise
            if retired:
                income = 0.0
            elif stream.income_type == IncomeType.EMPLOYMENT:
                active_employment += 1
            if stream.primary_rank == 1 and month <= config.scenario.income_interruption_months:
                income = 0.0
                interruption_income += income
            reduction_applies = (
                config.scenario.income_reduction_ratio > 0
                and month <= config.scenario.income_reduction_months
                and (
                    config.scenario.income_reduction_target == "all"
                    or (
                        config.scenario.income_reduction_target == "primary"
                        and stream.primary_rank == 1
                    )
                    or (
                        config.scenario.income_reduction_target == "secondary"
                        and stream.primary_rank == 2
                    )
                )
            )
            if reduction_applies:
                income *= 1 - config.scenario.income_reduction_ratio
            if (
                stream.income_type == IncomeType.RENTAL
                and month <= config.scenario.investment_property_vacancy_months
            ):
                income = 0.0
            total_income += max(0.0, income)
        all_employment_retired = active_employment == 0
        buckets["cash_equivalent"] = _cap(
            buckets["cash_equivalent"]
            + total_income
            + float(config.plan_adjustments.additional_monthly_savings),
            config.maximum_balance,
        )
        if not all_employment_retired:
            buckets["pension"] = _cap(
                buckets["pension"] + model.pension_monthly_contributions,
                config.maximum_balance,
            )

        inflation_factor = (1 + config.inflation_rate) ** (month / 12)
        monthly_expenses = model.monthly_expenses * inflation_factor
        if month <= config.scenario.family_support_duration_months:
            monthly_expenses += config.scenario.family_support_monthly_increase
        for event in request.family_events:
            if event.start_month <= month < event.start_month + event.duration_months:
                monthly_expenses += float(event.monthly_expense_increase)
                # A custom income loss is represented as a deterministic cash-flow
                # shortfall.  It is deducted exactly once together with the month's
                # other outflows, so the withdrawal order and forced-sale evidence
                # remain consistent.
                monthly_expenses += float(event.monthly_income_loss)
            if month == event.start_month:
                monthly_expenses += float(event.one_time_cost)
        if month == 1 and config.scenario.medical_shock_amount > 0:
            covered = min(
                config.scenario.medical_shock_amount,
                max(0.0, model.medical_coverage - model.medical_deductible),
            )
            monthly_expenses += config.scenario.medical_shock_amount - covered
        paid_expenses, expense_forced = _withdraw(
            buckets,
            monthly_expenses,
            allow_pension=all_employment_retired,
        )
        # Drawing long-term assets after all employment income has retired is normal
        # decumulation, not an emergency forced sale.
        if not all_employment_retired:
            forced_sale_amount += expense_forced
        expense_shortfall = max(0.0, monthly_expenses - paid_expenses)
        if expense_shortfall >= PAYMENT_TOLERANCE:
            unmet_obligations += expense_shortfall
            if depletion_month is None:
                depletion_month = month

        for index, debt in enumerate(model.debts):
            balance = debt_balances[index]
            if balance <= 1e-7:
                continue
            rate = debt.annual_rate
            if debt.floating_rate:
                rate = max(0.0, rate + config.scenario.mortgage_rate_increase)
            interest = balance * rate / 12
            scheduled = min(balance + interest, debt.monthly_payment)
            paid, debt_forced = _withdraw(
                buckets,
                scheduled,
                allow_pension=all_employment_retired,
            )
            forced_sale_amount += debt_forced
            remaining_debt = max(0.0, balance + interest - paid)
            debt_balances[index] = min(
                config.maximum_balance,
                0.0 if remaining_debt < PAYMENT_TOLERANCE else remaining_debt,
            )

        for goal, required in goal_schedule.get(month, []):
            paid, goal_forced = _withdraw(
                buckets,
                required,
                allow_pension=goal.goal_type == "retirement" or all_employment_retired,
            )
            # A retirement goal deliberately consumes retirement assets.  Other
            # goals still count long-term liquidation as a forced sale.
            if goal.goal_type != "retirement":
                forced_sale_amount += goal_forced
            goal_spending_events += 1
            shortfall = max(0.0, required - paid)
            if shortfall < PAYMENT_TOLERANCE:
                shortfall = 0.0
            goal_shortfalls[goal.id] = shortfall
            if shortfall > 0:
                goal_success[goal.id] = False
                if first_failed_goal is None:
                    first_failed_goal = goal.name
                    first_failure_month = month

        current = _snapshot(buckets, debt_balances, unmet_obligations)
        minimum_net_worth = min(minimum_net_worth, current.net_worth)
        if month in snapshot_months[1:]:
            snapshots.append(current)
    ending = snapshots[-1].net_worth
    total_shortfall = sum(goal_shortfalls.values())
    return PathResult(
        path_id=path_id,
        snapshots=tuple(snapshots),
        ending_net_worth=ending,
        minimum_net_worth=minimum_net_worth,
        goal_success=goal_success,
        goal_shortfalls=goal_shortfalls,
        goal_required=goal_required,
        first_failed_goal=first_failed_goal,
        first_failure_month=first_failure_month,
        depletion_month=depletion_month,
        forced_sale_amount=forced_sale_amount,
        total_goal_shortfall=total_shortfall,
        primary_income_during_interruption=interruption_income,
        goal_spending_events=goal_spending_events,
    )


def simulate_distribution(
    model: TwinModelInput,
    rules: TwinRules,
    request: TwinRunRequest,
    scenario_codes: list[str],
    plan_adjustments: PlanAdjustments,
    label: str,
) -> tuple[SimulationDistribution, SimulationConfig]:
    config = resolve_simulation_config(rules, request, scenario_codes, plan_adjustments)
    paths = [
        _simulate_path(model, config, request, path_id) for path_id in range(config.path_count)
    ]
    snapshot_count = len(paths[0].snapshots)
    months = list(range(0, config.horizon_months + 1, config.output_interval_months))
    if months[-1] != config.horizon_months:
        months.append(config.horizon_months)
    primary_age = model.members[0].age_at_start if model.members else 0.0
    fan: list[FanPoint] = []
    for index in range(snapshot_count):
        net_worth = [path.snapshots[index].net_worth for path in paths]
        liquid = [path.snapshots[index].liquid_assets for path in paths]
        long_term = [path.snapshots[index].long_term_assets for path in paths]
        liabilities = [path.snapshots[index].liabilities for path in paths]
        month = months[index]
        fan.append(
            FanPoint(
                month=month,
                date=_add_months(model.analysis_date, month),
                primary_age=Decimal(str(primary_age + month / 12)).quantize(Decimal("0.01")),
                p10=_money(_quantile(net_worth, 0.10), config.maximum_balance),
                p25=_money(_quantile(net_worth, 0.25), config.maximum_balance),
                p50=_money(_quantile(net_worth, 0.50), config.maximum_balance),
                p75=_money(_quantile(net_worth, 0.75), config.maximum_balance),
                p90=_money(_quantile(net_worth, 0.90), config.maximum_balance),
                median_liquid_assets=_nonnegative_money(
                    _quantile(liquid, 0.50),
                    config.maximum_balance,
                ),
                median_long_term_assets=_nonnegative_money(
                    _quantile(long_term, 0.50),
                    config.maximum_balance,
                ),
                median_liabilities=_nonnegative_money(
                    _quantile(liabilities, 0.50),
                    config.maximum_balance,
                ),
            )
        )
    goal_ids = sorted({goal_id for path in paths for goal_id in path.goal_success})
    goals_by_id = {goal.id: goal for goal in model.goals}
    goal_outcomes: list[GoalSimulationOutcome] = []
    for goal_id in goal_ids:
        successes = sum(1 for path in paths if path.goal_success.get(goal_id, True))
        shortfalls = [path.goal_shortfalls.get(goal_id, 0.0) for path in paths]
        goal = goals_by_id[goal_id]
        required = paths[0].goal_required.get(goal_id, 0.0)
        goal_outcomes.append(
            GoalSimulationOutcome(
                goal_id=goal_id,
                name=goal.name,
                due_month=max(1, goal.due_month - config.scenario.goal_advance_months),
                required_amount=_nonnegative_money(required, config.maximum_balance),
                success_probability=_ratio(successes / config.path_count),
                failure_probability=_ratio(1 - successes / config.path_count),
                median_shortfall=_nonnegative_money(
                    _quantile(shortfalls, 0.50),
                    config.maximum_balance,
                ),
            )
        )
    all_goals_success = sum(1 for path in paths if all(path.goal_success.values()))
    depleted = sum(1 for path in paths if path.depletion_month is not None)
    forced = sum(1 for path in paths if path.forced_sale_amount > 0.01)
    failure_by_year: defaultdict[int, list[str]] = defaultdict(list)
    for path in paths:
        if path.first_failure_month is not None:
            failure_by_year[(path.first_failure_month + 11) // 12].append(
                path.first_failed_goal or "未知目标"
            )
    failure_distribution = [
        FailureTimeBucket(
            year=year,
            path_count=len(names),
            probability=_ratio(len(names) / config.path_count),
            most_common_goal=Counter(names).most_common(1)[0][0] if names else None,
        )
        for year, names in sorted(failure_by_year.items())
    ]
    worst = sorted(
        paths,
        key=lambda item: (
            item.ending_net_worth,
            -item.total_goal_shortfall,
            item.path_id,
        ),
    )[:5]
    worst_paths = [
        WorstPath(
            path_id=path.path_id,
            ending_net_worth=_money(path.ending_net_worth, config.maximum_balance),
            minimum_net_worth=_money(path.minimum_net_worth, config.maximum_balance),
            first_failed_goal=path.first_failed_goal,
            first_failure_month=path.first_failure_month,
            depletion_month=path.depletion_month,
            forced_sale_amount=_nonnegative_money(
                path.forced_sale_amount,
                config.maximum_balance,
            ),
            total_goal_shortfall=_nonnegative_money(
                path.total_goal_shortfall,
                config.maximum_balance,
            ),
            explanation=(
                "路径按期末净资产、目标缺口和路径编号排序；"
                "它是固定 seed 下的压力样本，不是最坏可能边界。"
            ),
        )
        for path in worst
    ]
    ending_values = [path.ending_net_worth for path in paths]
    shortfall_values = [path.total_goal_shortfall for path in paths]
    forced_values = [path.forced_sale_amount for path in paths]
    required_monthly = _quantile(shortfall_values, 0.50) / max(1, config.horizon_months)
    return (
        SimulationDistribution(
            label=label,
            path_count=config.path_count,
            horizon_months=config.horizon_months,
            goal_success_probability=_ratio(all_goals_success / config.path_count),
            depletion_probability=_ratio(depleted / config.path_count),
            forced_sale_probability=_ratio(forced / config.path_count),
            median_forced_sale_amount=_nonnegative_money(
                _quantile(forced_values, 0.50),
                config.maximum_balance,
            ),
            ending_net_worth_median=_money(
                _quantile(ending_values, 0.50),
                config.maximum_balance,
            ),
            ending_net_worth_p10=_money(
                _quantile(ending_values, 0.10),
                config.maximum_balance,
            ),
            total_goal_shortfall_median=_nonnegative_money(
                _quantile(shortfall_values, 0.50),
                config.maximum_balance,
            ),
            required_additional_monthly_savings=_nonnegative_money(
                required_monthly,
                config.maximum_balance,
            ),
            fan=fan,
            goal_outcomes=goal_outcomes,
            failure_time_distribution=failure_distribution,
            worst_paths=worst_paths,
            validation=DistributionValidation(
                all_values_finite=all(
                    math.isfinite(value)
                    for path in paths
                    for value in (
                        path.ending_net_worth,
                        path.minimum_net_worth,
                        path.forced_sale_amount,
                        path.total_goal_shortfall,
                    )
                ),
                primary_income_paid_during_interruption_max=_nonnegative_money(
                    max(path.primary_income_during_interruption for path in paths),
                    config.maximum_balance,
                ),
                goal_spending_events_applied=sum(path.goal_spending_events for path in paths),
                common_random_numbers=True,
            ),
        ),
        config,
    )


def build_assumption_snapshot(
    rules: TwinRules,
    request: TwinRunRequest,
    config: SimulationConfig,
    parameter_hash: str,
) -> ResolvedAssumptionSnapshot:
    scenario = config.scenario
    scenario_parameters: dict[str, object] = {
        "income_interruption_months": scenario.income_interruption_months,
        "income_reduction_ratio": str(scenario.income_reduction_ratio),
        "income_reduction_months": scenario.income_reduction_months,
        "income_reduction_target": scenario.income_reduction_target,
        "medical_shock_amount": str(scenario.medical_shock_amount),
        "family_support_monthly_increase": str(scenario.family_support_monthly_increase),
        "family_support_duration_months": scenario.family_support_duration_months,
        "education_overrun_amount": str(scenario.education_overrun_amount),
        "retirement_age_reduction_years": scenario.retirement_age_reduction_years,
        "longevity_extension_years": scenario.longevity_extension_years,
        "mortgage_rate_increase": str(scenario.mortgage_rate_increase),
        "investment_property_vacancy_months": scenario.investment_property_vacancy_months,
        "investment_property_value_shock": str(scenario.investment_property_value_shock),
        "property_value_shock": str(scenario.property_value_shock),
        "asset_return_shocks": {
            key: str(value) for key, value in scenario.asset_return_shocks.items()
        },
        "asset_volatility_multipliers": {
            key: str(value) for key, value in scenario.asset_volatility_multipliers.items()
        },
        "long_term_return_reduction": str(scenario.long_term_return_reduction),
        "inflation_increase": str(scenario.inflation_increase),
        "goal_advance_months": scenario.goal_advance_months,
    }
    return ResolvedAssumptionSnapshot(
        seed=config.seed,
        path_count=config.path_count,
        horizon_months=config.horizon_months,
        time_step_months=rules.time_step_months,
        output_interval_months=config.output_interval_months,
        inflation_rate=Decimal(str(config.inflation_rate)),
        income_growth_rate=Decimal(str(config.income_growth_rate)),
        asset_classes=list(config.asset_classes),
        asset_assumptions={
            key: {
                "expected_annual_return": Decimal(str(value[0])),
                "annual_volatility": Decimal(str(value[1])),
            }
            for key, value in config.asset_assumptions.items()
        },
        correlation_matrix=config.correlation_matrix,
        property_assumption={
            "expected_annual_return": Decimal(str(config.property_assumption[0])),
            "annual_volatility": Decimal(str(config.property_assumption[1])),
        },
        pension_assumption={
            "expected_annual_return": Decimal(str(config.pension_assumption[0])),
            "annual_volatility": Decimal(str(config.pension_assumption[1])),
        },
        scenario_codes=list(config.scenario.codes),
        scenario_parameters=scenario_parameters,
        plan_adjustments=config.plan_adjustments,
        family_events=request.family_events,
        parameter_hash=parameter_hash,
    )


def build_scenario_impact(
    model: TwinModelInput,
    rules: TwinRules,
    baseline: SimulationDistribution,
    scenario: SimulationDistribution,
    config: SimulationConfig,
) -> ScenarioImpact:
    monthly_debt = sum(item.monthly_payment for item in model.debts)
    stress_monthly_need = (
        model.monthly_essential_expenses
        + monthly_debt
        + config.scenario.family_support_monthly_increase
    )
    emergency_resources = (
        model.asset_buckets["cash_equivalent"] + model.asset_buckets["fixed_income"]
    )
    emergency_months = emergency_resources / stress_monthly_need if stress_monthly_need > 0 else 0.0
    medical_coverage = min(
        config.scenario.medical_shock_amount,
        max(0.0, model.medical_coverage - model.medical_deductible),
    )
    medical_gap = max(0.0, config.scenario.medical_shock_amount - medical_coverage)
    failed_goals = sorted(
        scenario.goal_outcomes,
        key=lambda item: (-float(item.failure_probability), item.due_month),
    )
    first_failed = (
        failed_goals[0].name if failed_goals and failed_goals[0].failure_probability > 0 else None
    )
    retirement = next(
        (item for item in scenario.goal_outcomes if "退休" in item.name),
        None,
    )
    retirement_shortfall = float(retirement.median_shortfall) if retirement is not None else 0.0
    primary_annual_income = max(
        (item.monthly_amount * 12 for item in model.incomes if item.primary_rank == 1),
        default=1.0,
    )
    delay_years = min(10, math.ceil(retirement_shortfall / max(1.0, primary_annual_income)))
    applicable = not (
        "investment_property_vacancy_discount" in config.scenario.codes
        and model.asset_buckets["investment_property"] <= 0
    )
    return ScenarioImpact(
        scenario_code="+".join(config.scenario.codes),
        name=config.scenario.name,
        emergency_support_months=Decimal(str(emergency_months)).quantize(Decimal("0.01")),
        first_failed_goal=first_failed,
        forced_sale_probability=scenario.forced_sale_probability,
        median_forced_sale_amount=scenario.median_forced_sale_amount,
        insurance_coverage_applied=_nonnegative_money(medical_coverage, config.maximum_balance),
        remaining_medical_gap=_nonnegative_money(medical_gap, config.maximum_balance),
        retirement_delay_needed=delay_years > 0,
        suggested_retirement_delay_years=delay_years,
        monthly_compressible_expenses=_nonnegative_money(
            model.monthly_compressible_expenses,
            config.maximum_balance,
        ),
        required_additional_monthly_savings=scenario.required_additional_monthly_savings,
        baseline_goal_success_probability=baseline.goal_success_probability,
        scenario_goal_success_probability=scenario.goal_success_probability,
        success_probability_change=_signed_ratio(
            float(scenario.goal_success_probability) - float(baseline.goal_success_probability)
        ),
        applicable=applicable,
        explanation=(
            "该家庭没有投资性房产，空置与折价参数不作用于自住房。"
            if not applicable
            else "应急月数、保障抵扣、目标失败、被迫出售和新增储蓄均由同一组状态路径计算。"
        ),
    )


def build_comparison(
    request: TwinRunRequest,
    baseline: SimulationDistribution,
    original: SimulationDistribution,
    optimized: SimulationDistribution,
) -> TwinComparison:
    stress_change = float(original.goal_success_probability) - float(
        baseline.goal_success_probability
    )
    optimization_change = float(optimized.goal_success_probability) - float(
        original.goal_success_probability
    )
    avoided_sale = float(original.forced_sale_probability) - float(
        optimized.forced_sale_probability
    )
    monotonic = original.goal_success_probability <= baseline.goal_success_probability
    positive_override = None
    if not monotonic:
        override = request.scenario_overrides.property_value_change_ratio
        if override is not None and override > 0:
            positive_override = "用户显式输入了正向房价变化，因此压力结果可能高于无冲击基线。"
        else:
            positive_override = (
                "结果改善来自用户显式覆盖的收益、收入或负向成本假设；请审计参数快照。"
            )
    liquidity_amount = request.plan_adjustments.liquidity_reallocation_amount
    return TwinComparison(
        baseline_success_probability=baseline.goal_success_probability,
        original_stress_success_probability=original.goal_success_probability,
        optimized_stress_success_probability=optimized.goal_success_probability,
        stress_change=_signed_ratio(stress_change),
        optimization_change=_signed_ratio(optimization_change),
        baseline_forced_sale_probability=baseline.forced_sale_probability,
        original_forced_sale_probability=original.forced_sale_probability,
        optimized_forced_sale_probability=optimized.forced_sale_probability,
        liquidity_reallocation_amount=liquidity_amount,
        avoided_forced_sale_probability=_signed_ratio(avoided_sale),
        stress_not_better_than_baseline=monotonic,
        positive_override_explanation=positive_override,
        liquidity_explanation=(
            f"优化方案把 {liquidity_amount:.2f} 元从长期资产重分类为流动性，净资产起点不变；"
            "只有被迫出售概率的实际差值才被报告为改善，未改善时也不会隐藏。"
        ),
    )


def request_parameter_hash(request: TwinRunRequest, rule_version: str) -> str:
    payload = {
        "request": request.model_dump(mode="json"),
        "rule_version": rule_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
