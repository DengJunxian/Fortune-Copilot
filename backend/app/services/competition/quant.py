from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, cast

from app.schemas.competition import (
    QuantComparison,
    QuantMethodResult,
    QuantMetrics,
    QuantRequest,
)

ENGINE_VERSION = "competition-quant-v1.0.0"
Q = Decimal("0.000001")
ZERO = Decimal("0")


def _ratio(value: Decimal | float) -> Decimal:
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


def _compositions(
    total: int, parts: int, prefix: tuple[int, ...] = ()
) -> Iterator[tuple[int, ...]]:
    if parts == 1:
        yield (*prefix, total)
        return
    for value in range(total + 1):
        yield from _compositions(total - value, parts - 1, (*prefix, value))


def _covariance(request: QuantRequest) -> list[list[Decimal]]:
    result: list[list[Decimal]] = []
    for row_index, row in enumerate(request.correlation_matrix):
        result.append(
            [
                row[column_index]
                * request.assets[row_index].volatility
                * request.assets[column_index].volatility
                for column_index in range(len(row))
            ]
        )
    return result


def _portfolio_variance(weights: list[Decimal], covariance: list[list[Decimal]]) -> Decimal:
    return sum(
        (
            weights[row] * covariance[row][column] * weights[column]
            for row in range(len(weights))
            for column in range(len(weights))
        ),
        ZERO,
    )


def _scenario_returns(request: QuantRequest, weights: list[Decimal]) -> list[Decimal]:
    count = min(len(item.scenarios) for item in request.assets)
    return [
        sum(
            (
                weights[index] * request.assets[index].scenarios[scenario]
                for index in range(len(weights))
            ),
            ZERO,
        )
        for scenario in range(count)
    ]


def _cvar_loss(returns: list[Decimal]) -> Decimal:
    losses = sorted((-item for item in returns), reverse=True)
    tail_count = max(1, math.ceil(len(losses) * 0.20))
    return max(ZERO, sum(losses[:tail_count], ZERO) / Decimal(tail_count))


def _risk_contributions(weights: list[Decimal], covariance: list[list[Decimal]]) -> list[Decimal]:
    variance = _portfolio_variance(weights, covariance)
    if variance <= 0:
        return [ZERO for _ in weights]
    marginal = [
        sum((covariance[row][column] * weights[column] for column in range(len(weights))), ZERO)
        for row in range(len(weights))
    ]
    return [weights[index] * marginal[index] / variance for index in range(len(weights))]


def _metrics(
    request: QuantRequest,
    weights: list[Decimal],
    covariance: list[list[Decimal]],
    expected_returns: list[Decimal] | None = None,
) -> QuantMetrics:
    returns = expected_returns or [item.expected_return for item in request.assets]
    expected = sum((weights[index] * returns[index] for index in range(len(weights))), ZERO)
    variance = max(ZERO, _portfolio_variance(weights, covariance))
    volatility = Decimal(str(math.sqrt(float(variance))))
    scenarios = _scenario_returns(request, weights)
    cvar = _cvar_loss(scenarios)
    max_drawdown = max(ZERO, -min(scenarios, default=ZERO))
    liquidity = sum(
        (weights[index] * request.assets[index].liquidity_score for index in range(len(weights))),
        ZERO,
    )
    sharpe = (expected - request.risk_free_rate) / volatility if volatility > 0 else ZERO
    return QuantMetrics(
        expected_return=_ratio(expected),
        volatility=_ratio(volatility),
        sharpe_ratio=_ratio(sharpe),
        cvar_loss=_ratio(cvar),
        max_drawdown=_ratio(max_drawdown),
        liquidity_score=_ratio(liquidity),
    )


def _constraint_failures(
    request: QuantRequest,
    weights: list[Decimal],
    metrics: QuantMetrics,
    covariance: list[list[Decimal]],
) -> list[str]:
    constraints = request.constraints
    failures: list[str] = []
    names = [item.asset_class for item in request.assets]
    for index, asset in enumerate(request.assets):
        weight = weights[index]
        maximum = min(asset.max_weight, constraints.maximum_asset_exposure)
        if asset.asset_class not in constraints.allowed_asset_classes and weight > 0:
            failures.append("product_suitability")
        if weight < asset.min_weight or weight > maximum:
            failures.append("asset_exposure")
        if weight > 0 and asset.lockup_days > constraints.goal_horizon_days:
            failures.append("goal_horizon")
    cash_index = names.index(constraints.cash_asset_class)
    if weights[cash_index] < constraints.minimum_cash:
        failures.append("minimum_cash")
    if metrics.liquidity_score < constraints.minimum_liquidity_score:
        failures.append("liquidity_requirement")
    if metrics.volatility > constraints.maximum_volatility:
        failures.append("risk_budget_volatility")
    if metrics.cvar_loss > constraints.maximum_cvar_loss:
        failures.append("risk_budget_cvar")
    contributions = _risk_contributions(weights, covariance)
    for index, asset in enumerate(request.assets):
        if asset.risk_budget_share is not None and contributions[index] > (
            asset.risk_budget_share + Decimal("0.20")
        ):
            failures.append("risk_budget_contribution")
            break
    return sorted(set(failures))


@dataclass(frozen=True, slots=True)
class _Candidate:
    weights: list[Decimal]
    metrics: QuantMetrics
    objective: Decimal


def _risk_parity_objective(
    weights: list[Decimal], covariance: list[list[Decimal]], request: QuantRequest
) -> Decimal:
    contributions = _risk_contributions(weights, covariance)
    specified = [item.risk_budget_share for item in request.assets]
    if all(item is not None for item in specified):
        total = sum((item or ZERO for item in specified), ZERO)
        targets = [(item or ZERO) / total for item in specified]
    else:
        targets = [Decimal("1") / Decimal(len(weights)) for _ in weights]
    return sum(
        ((contributions[index] - targets[index]) ** 2 for index in range(len(weights))),
        ZERO,
    )


def _posterior_returns(request: QuantRequest, covariance: list[list[Decimal]]) -> list[Decimal]:
    market = [item.market_weight for item in request.assets]
    total_market = sum(market, ZERO)
    if total_market <= 0:
        market = [Decimal("1") / Decimal(len(market)) for _ in market]
    else:
        market = [item / total_market for item in market]
    risk_aversion = Decimal("2.5")
    implied = [
        risk_aversion
        * sum((covariance[row][column] * market[column] for column in range(len(market))), ZERO)
        for row in range(len(market))
    ]
    posterior: list[Decimal] = []
    for index, asset in enumerate(request.assets):
        prior = (implied[index] + asset.expected_return) / Decimal("2")
        view = request.black_litterman_views.get(asset.asset_class)
        confidence = request.view_confidences.get(asset.asset_class, Decimal("0"))
        if view is None:
            posterior.append(prior)
        else:
            posterior.append(prior * (Decimal("1") - confidence) + view * confidence)
    return posterior


def _method_result(
    request: QuantRequest,
    covariance: list[list[Decimal]],
    method: str,
    expected_returns: list[Decimal] | None = None,
) -> QuantMethodResult:
    step_units = int(Decimal("1") / request.constraints.grid_step)
    best: _Candidate | None = None
    rejection_counts: dict[str, int] = {}
    evaluated = 0
    expected = expected_returns or [item.expected_return for item in request.assets]
    for composition in _compositions(step_units, len(request.assets)):
        weights = [Decimal(value) / Decimal(step_units) for value in composition]
        metrics = _metrics(request, weights, covariance, expected)
        failures = _constraint_failures(request, weights, metrics, covariance)
        if failures:
            for failure in failures:
                rejection_counts[failure] = rejection_counts.get(failure, 0) + 1
            continue
        evaluated += 1
        portfolio_return = metrics.expected_return
        variance = metrics.volatility**2
        if method in {"mean_variance", "black_litterman"}:
            objective = variance * Decimal("3") - portfolio_return
        elif method == "risk_parity":
            objective = _risk_parity_objective(weights, covariance, request)
        else:
            target_shortfall = max(ZERO, request.target_return - portfolio_return)
            objective = metrics.cvar_loss + target_shortfall * Decimal("3")
        candidate = _Candidate(weights, metrics, objective)
        if best is None or (candidate.objective, -candidate.metrics.sharpe_ratio) < (
            best.objective,
            -best.metrics.sharpe_ratio,
        ):
            best = candidate
    status: Literal["optimal", "fallback"] = "optimal"
    if best is None:
        status = "fallback"
        cash_index = next(
            index
            for index, item in enumerate(request.assets)
            if item.asset_class == request.constraints.cash_asset_class
        )
        weights = [ZERO for _ in request.assets]
        weights[cash_index] = Decimal("1")
        metrics = _metrics(request, weights, covariance, expected)
        best = _Candidate(weights, metrics, Decimal("999"))
    weight_map = {
        request.assets[index].asset_class: _ratio(best.weights[index])
        for index in range(len(best.weights))
    }
    bindings: list[str] = []
    cash_weight = weight_map[request.constraints.cash_asset_class]
    if cash_weight == request.constraints.minimum_cash:
        bindings.append("minimum_cash")
    for asset in request.assets:
        if weight_map[asset.asset_class] in {
            asset.min_weight,
            min(asset.max_weight, request.constraints.maximum_asset_exposure),
        }:
            bindings.append(f"asset_exposure:{asset.asset_class}")
    if best.metrics.volatility >= request.constraints.maximum_volatility * Decimal("0.95"):
        bindings.append("risk_budget_volatility")
    if best.metrics.cvar_loss >= request.constraints.maximum_cvar_loss * Decimal("0.95"):
        bindings.append("risk_budget_cvar")
    explanations = {
        "mean_variance": "在可行域内最小化 3×方差−预期收益。",
        "risk_parity": "最小化各资产风险贡献与目标风险预算的平方偏差。",
        "cvar": "最小化压力场景尾部平均损失，并惩罚目标收益缺口。",
        "black_litterman": "将市场隐含收益与置信度加权观点收缩后再执行均值方差优化。",
    }
    return QuantMethodResult(
        method=cast(Literal["mean_variance", "risk_parity", "cvar", "black_litterman"], method),
        status=status,
        weights=weight_map,
        metrics=best.metrics,
        objective_value=_ratio(best.objective),
        evaluated_candidates=evaluated,
        rejection_counts=rejection_counts,
        binding_constraints=sorted(set(bindings)),
        explanation=[
            explanations[method],
            "全部权重由独立量化模块计算；语言模型不能修改输出。",
            "约束同时覆盖总权重、只做多、现金、上限、风险、流动性、期限和适当性。",
        ],
    )


def compare_quant_methods(request: QuantRequest) -> QuantComparison:
    covariance = _covariance(request)
    posterior = _posterior_returns(request, covariance)
    methods = [
        _method_result(request, covariance, "mean_variance"),
        _method_result(request, covariance, "risk_parity"),
        _method_result(request, covariance, "cvar"),
        _method_result(request, covariance, "black_litterman", posterior),
    ]
    feasible = [item for item in methods if item.status == "optimal"]
    selected = max(
        feasible or methods,
        key=lambda item: (
            item.metrics.sharpe_ratio - item.metrics.cvar_loss,
            -item.metrics.max_drawdown,
            item.method == "cvar",
        ),
    )
    payload = request.model_dump(mode="json")
    input_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return QuantComparison(
        input_hash=input_hash,
        engine_version=ENGINE_VERSION,
        selected_method=selected.method,
        selection_reason=(
            "在全部硬约束通过的方法中，选择 Sharpe−CVaR 得分最高且最大回撤更低的方案；"
            "这是一条版本化演示选择规则，不是收益预测。"
        ),
        methods=methods,
        immutable_trace={
            "input": payload,
            "covariance_matrix": [[str(_ratio(item)) for item in row] for row in covariance],
            "black_litterman_posterior_returns": [str(_ratio(item)) for item in posterior],
            "constraints": request.constraints.model_dump(mode="json"),
            "selection_rule": "max(sharpe_ratio-cvar_loss), then min(max_drawdown)",
            "output_checksum": hashlib.sha256(
                json.dumps(
                    [item.model_dump(mode="json") for item in methods],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        },
    )
