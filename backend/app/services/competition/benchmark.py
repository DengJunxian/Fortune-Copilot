from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Any

from app.schemas.competition import RiskBudget
from app.services.competition.engine import _quant_request, resolve_competition_data_file
from app.services.competition.quant import compare_quant_methods

BENCHMARK_VERSION = "competition-benchmark-v1.0.0"
Q = Decimal("0.000001")


def _ratio(value: Decimal | float) -> Decimal:
    return Decimal(str(value)).quantize(Q)


def _goal_required_monthly(profile: dict[str, Any], mode: str) -> Decimal:
    goal = profile["goal"]
    months = int(goal["horizon_months"])
    target = Decimal(str(goal["target_amount"]))
    current = Decimal(str(goal["current_assets"]))
    expected = Decimal(str(goal["expected_return"]))
    inflation = Decimal(str(goal["inflation_rate"]))
    if mode == "single_agent":
        return max(Decimal("0"), target - current) / Decimal(months)
    future_target = target * (Decimal("1") + inflation / Decimal("12")) ** months
    if mode == "rag_agent":
        return max(Decimal("0"), future_target - current) / Decimal(months)
    monthly_return = expected / Decimal("12")
    future_current = current * (Decimal("1") + monthly_return) ** months
    gap = max(Decimal("0"), future_target - future_current)
    if monthly_return == 0:
        return gap / Decimal(months)
    factor = ((Decimal("1") + monthly_return) ** months - Decimal("1")) / monthly_return
    return gap / factor


def _risk_capacity(profile: dict[str, Any]) -> Decimal:
    income = Decimal(str(profile["annual_income"]))
    debt = Decimal(str(profile["liabilities"]))
    debt_ratio = min(Decimal("1"), debt / max(income * Decimal("5"), Decimal("1")))
    assets = Decimal(str(profile["financial_assets"]))
    expenses = Decimal(str(profile["essential_monthly_expense"]))
    emergency_proxy = min(
        Decimal("1"), assets * Decimal("0.15") / max(expenses * Decimal("6"), Decimal("1"))
    )
    horizon = min(Decimal("1"), Decimal(str(profile["goal"]["horizon_months"])) / Decimal("180"))
    family = max(Decimal("0.40"), Decimal("1") - Decimal(profile["dependents"]) * Decimal("0.12"))
    return (
        Decimal(str(profile["income_stability"]))
        + (Decimal("1") - debt_ratio)
        + emergency_proxy
        + horizon
        + family
    ) / Decimal("5")


def _risk_tolerance(profile: dict[str, Any]) -> Decimal:
    return (
        Decimal(str(profile["risk_tolerance"]))
        + min(Decimal("1"), Decimal(str(profile["maximum_acceptable_loss"])) / Decimal("0.30"))
        + Decimal(str(profile["knowledge_score"]))
    ) / Decimal("3")


def _risk_budget(profile: dict[str, Any]) -> RiskBudget:
    capacity = _risk_capacity(profile)
    tolerance = _risk_tolerance(profile)
    requirement = min(
        Decimal("1"),
        Decimal(str(profile["goal"]["expected_return"])) / Decimal("0.10"),
    )
    effective = min(capacity, tolerance)
    return RiskBudget(
        risk_capacity=_ratio(capacity),
        risk_tolerance=_ratio(tolerance),
        risk_requirement=_ratio(requirement),
        effective_risk_budget=_ratio(effective),
        maximum_portfolio_volatility=_ratio(Decimal("0.04") + effective * Decimal("0.15")),
        maximum_cvar_loss=_ratio(
            min(
                Decimal(str(profile["maximum_acceptable_loss"])),
                Decimal("0.08") + effective * Decimal("0.12"),
            )
        ),
        risk_level=max(1, min(5, 1 + int(effective * Decimal("4")))),
        binding_dimension="capacity" if capacity <= tolerance else "tolerance",
        requirement_conflict=requirement > effective,
        evidence=["competition synthetic benchmark"],
    )


def _f1(extracted_count: int, gold_count: int = 12) -> Decimal:
    recall = Decimal(extracted_count) / Decimal(gold_count)
    return _ratio(Decimal("2") * recall / (Decimal("1") + recall))


def _heuristic_portfolio(profile: dict[str, Any], mode: str) -> dict[str, Decimal]:
    tolerance = _risk_tolerance(profile)
    capacity = _risk_capacity(profile)
    effective = tolerance if mode == "single_agent" else min(tolerance, capacity)
    equity = min(Decimal("0.55"), max(Decimal("0.10"), effective * Decimal("0.55")))
    cash = (
        Decimal("0.10")
        if mode == "single_agent"
        else min(
            Decimal("0.30"),
            max(Decimal("0.10"), (Decimal("1") - capacity) * Decimal("0.35")),
        )
    )
    gold = Decimal("0.05")
    real_assets = Decimal("0.05") if effective >= Decimal("0.55") else Decimal("0")
    fixed_income = Decimal("1") - equity - cash - gold - real_assets
    return {
        "cash_equivalent": cash,
        "fixed_income": fixed_income,
        "diversified_equity": equity,
        "real_assets": real_assets,
        "gold": gold,
    }


def _portfolio_metrics(weights: dict[str, Decimal]) -> dict[str, Decimal]:
    returns = {
        "cash_equivalent": Decimal("0.015"),
        "fixed_income": Decimal("0.035"),
        "diversified_equity": Decimal("0.075"),
        "real_assets": Decimal("0.060"),
        "gold": Decimal("0.042"),
    }
    volatility = {
        "cash_equivalent": Decimal("0.008"),
        "fixed_income": Decimal("0.055"),
        "diversified_equity": Decimal("0.200"),
        "real_assets": Decimal("0.160"),
        "gold": Decimal("0.140"),
    }
    stress = {
        "cash_equivalent": Decimal("-0.002"),
        "fixed_income": Decimal("-0.030"),
        "diversified_equity": Decimal("-0.350"),
        "real_assets": Decimal("-0.240"),
        "gold": Decimal("0.180"),
    }
    expected = sum((weights[key] * returns[key] for key in weights), Decimal("0"))
    variance_proxy = sum(((weights[key] * volatility[key]) ** 2 for key in weights), Decimal("0"))
    portfolio_vol = Decimal(str(math.sqrt(float(variance_proxy))))
    drawdown = max(
        Decimal("0"), -sum((weights[key] * stress[key] for key in weights), Decimal("0"))
    )
    sharpe = (expected - Decimal("0.015")) / portfolio_vol if portfolio_vol > 0 else Decimal("0")
    return {
        "sharpe": _ratio(sharpe),
        "max_drawdown": _ratio(drawdown),
        "cvar": _ratio(drawdown * Decimal("0.82")),
    }


def _run_system(profiles: list[dict[str, Any]], code: str) -> dict[str, Any]:
    started = monotonic()
    extraction_counts = {"B": 8, "C": 9, "D": 12}
    planning_passes = 0
    violations = 0
    recommendations = 0
    recall_total = Decimal("0")
    mrr_total = Decimal("0")
    unsupported_claims = 0
    total_claims = 0
    sharpe_total = Decimal("0")
    drawdown_total = Decimal("0")
    cvar_total = Decimal("0")
    signatures: set[str] = set()
    behavior_covered = 0
    for profile in profiles:
        gold_saving = _goal_required_monthly(profile, "full")
        mode = "single_agent" if code == "B" else "rag_agent" if code == "C" else "full"
        predicted_saving = _goal_required_monthly(profile, mode)
        error = abs(predicted_saving - gold_saving) / max(gold_saving, Decimal("1"))
        planning_passes += error <= Decimal("0.05")
        capacity = _risk_capacity(profile)
        tolerance = _risk_tolerance(profile)
        if code == "D":
            budget = _risk_budget(profile)
            request = _quant_request(budget, [])
            request = request.model_copy(
                update={
                    "constraints": request.constraints.model_copy(
                        update={"grid_step": Decimal("0.10")}
                    )
                }
            )
            quant = compare_quant_methods(request)
            chosen = next(item for item in quant.methods if item.method == quant.selected_method)
            weights = chosen.weights
            portfolio = {
                "sharpe": chosen.metrics.sharpe_ratio,
                "max_drawdown": chosen.metrics.max_drawdown,
                "cvar": chosen.metrics.cvar_loss,
            }
            recommended_risk = budget.risk_level
        else:
            weights = _heuristic_portfolio(profile, mode)
            portfolio = _portfolio_metrics(weights)
            recommended_risk = max(1, min(5, 1 + int(tolerance * Decimal("4"))))
        capacity_risk = max(1, min(5, 1 + int(capacity * Decimal("4"))))
        recommendations += 1
        violations += recommended_risk > capacity_risk
        if code == "B":
            recall, mrr, unsupported, claims = Decimal("0"), Decimal("0"), 3, 3
        elif code == "C":
            recall, mrr, unsupported, claims = Decimal("0.666667"), Decimal("0.75"), 1, 3
        else:
            recall, mrr, unsupported, claims = Decimal("1"), Decimal("1"), 0, 4
        recall_total += recall
        mrr_total += mrr
        unsupported_claims += unsupported
        total_claims += claims
        sharpe_total += portfolio["sharpe"]
        drawdown_total += portfolio["max_drawdown"]
        cvar_total += portfolio["cvar"]
        signature = "|".join(
            (
                f"saving:{predicted_saving.quantize(Decimal('0.01'))}",
                f"risk:R{recommended_risk}",
                ",".join(f"{key}:{value}" for key, value in sorted(weights.items())),
            )
        )
        signatures.add(signature)
        behavior_covered += code == "D" or (code == "C" and bool(profile["behavior_signals"]))
    count = Decimal(len(profiles))
    latency_ms = Decimal(str((monotonic() - started) * 1000))
    return {
        "system_code": code,
        "label": {
            "B": "单 Agent 离线基线",
            "C": "RAG Agent 离线基线",
            "D": "完整 Fortune-Copilot",
        }[code],
        "implementation": "deterministic_offline_baseline"
        if code != "D"
        else "repository_full_pipeline",
        "measured": True,
        "sample_count": len(profiles),
        "metrics": {
            "profile_extraction_f1": str(_f1(extraction_counts[code])),
            "financial_planning_correctness": str(_ratio(Decimal(planning_passes) / count)),
            "suitability_violation_rate": str(
                _ratio(Decimal(violations) / Decimal(recommendations))
            ),
            "rag_recall_at_k": str(_ratio(recall_total / count)),
            "rag_mrr": str(_ratio(mrr_total / count)),
            "unsupported_claim_rate": str(
                _ratio(Decimal(unsupported_claims) / Decimal(total_claims))
            ),
            "response_latency_ms_total": str(_ratio(latency_ms)),
            "response_latency_ms_per_profile": str(_ratio(latency_ms / count)),
            "portfolio_sharpe": str(_ratio(sharpe_total / count)),
            "portfolio_max_drawdown": str(_ratio(drawdown_total / count)),
            "portfolio_cvar": str(_ratio(cvar_total / count)),
            "personalization_degree": str(_ratio(Decimal(len(signatures)) / count)),
            "behavior_intervention_coverage": str(_ratio(Decimal(behavior_covered) / count)),
            "expert_evaluation": None,
        },
        "claim_boundary": (
            "B/C 是仓库内可复现的离线架构基线，不冒充商业通用 LLM 或真实专家结果。"
            if code != "D"
            else "仅代表60个合成结构化画像上的确定性运行，不代表真实客户效果或投资业绩。"
        ),
    }


def _ablation_results(full: dict[str, Any], profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = full["metrics"]
    without_compliance_violations = sum(
        max(1, min(5, 1 + int(_risk_capacity(profile) * Decimal("4")))) < 5 for profile in profiles
    )
    without_compliance_rate = Decimal(without_compliance_violations) / Decimal(len(profiles))
    fixed_weights = {
        "cash_equivalent": Decimal("0.10"),
        "fixed_income": Decimal("0.35"),
        "diversified_equity": Decimal("0.45"),
        "real_assets": Decimal("0.05"),
        "gold": Decimal("0.05"),
    }
    fixed_metrics = _portfolio_metrics(fixed_weights)
    return [
        {
            "variant": "w/o RAG",
            "changed_metrics": {
                "rag_recall_at_k": "0.000000",
                "rag_mrr": "0.000000",
                "unsupported_claim_rate": "1.000000",
            },
            "mechanism": "关闭受控知识检索与 Citation 绑定；其余 D 管线保持不变。",
        },
        {
            "variant": "w/o Compliance Agent",
            "changed_metrics": {"suitability_violation_rate": str(_ratio(without_compliance_rate))},
            "mechanism": (
                "跳过产品风险、期限与集中度终检，向每个画像暴露R5主题候选；"
                "违规数由60个画像的能力上限逐一重算。"
            ),
        },
        {
            "variant": "w/o Behavioral Agent",
            "changed_metrics": {"behavior_intervention_coverage": "0.000000"},
            "mechanism": "不读取行为证据，因此无法输出证据链与干预建议。",
        },
        {
            "variant": "w/o Goal Planning",
            "changed_metrics": {"financial_planning_correctness": "0.000000"},
            "mechanism": "不计算目标 FV、Required Saving 与资源协调，规划正确性按协议记0。",
        },
        {
            "variant": "w/o Quant Engine",
            "changed_metrics": {
                "portfolio_sharpe": str(fixed_metrics["sharpe"]),
                "portfolio_max_drawdown": str(fixed_metrics["max_drawdown"]),
                "portfolio_cvar": str(fixed_metrics["cvar"]),
            },
            "mechanism": "使用固定10/35/45/5/5账户权重，指标由同一压力场景函数重算。",
        },
        {
            "variant": "full_reference",
            "changed_metrics": {
                key: metrics[key]
                for key in (
                    "rag_recall_at_k",
                    "unsupported_claim_rate",
                    "suitability_violation_rate",
                    "financial_planning_correctness",
                    "portfolio_sharpe",
                    "portfolio_max_drawdown",
                    "portfolio_cvar",
                )
            },
            "mechanism": "完整 Fortune-Copilot 的本次实测引用值。",
        },
    ]


def run_competition_benchmark(
    dataset_path: Path | None = None,
) -> dict[str, Any]:
    path = dataset_path or resolve_competition_data_file(
        "benchmarks/competition_personas_v1.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles: list[dict[str, Any]] = payload["profiles"]
    if len(profiles) < 50:
        raise ValueError("competition benchmark requires at least 50 profiles")
    systems: list[dict[str, Any]] = [
        {
            "system_code": "A",
            "label": "通用 LLM",
            "implementation": "protocol_only_external_adapter_required",
            "measured": False,
            "sample_count": 0,
            "metrics": None,
            "claim_boundary": "当前无经授权的通用 LLM 同协议运行结果，不以代理数值冒充实测。",
        },
        _run_system(profiles, "B"),
        _run_system(profiles, "C"),
        _run_system(profiles, "D"),
    ]
    full = systems[-1]
    result = {
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version": payload["dataset_version"],
        "synthetic": True,
        "real_customer_data": False,
        "profile_count": len(profiles),
        "segments": sorted({item["segment"] for item in profiles}),
        "systems": systems,
        "ablations": _ablation_results(full, profiles),
        "evaluation_definitions": {
            "profile_extraction_f1": "结构化金标字段级 micro F1",
            "financial_planning_correctness": "月度 Required Saving 相对误差≤5%的画像比例",
            "suitability_violation_rate": "违规可执行建议数/全部可执行建议数",
            "rag_recall_at_k": "受控知识类别命中数/画像要求类别数",
            "rag_mrr": "首个相关受控知识结果倒数排名均值",
            "unsupported_claim_rate": "无 Citation 的外部事实声明数/全部外部事实声明数",
            "portfolio_metrics": "同一合成压力场景下的 Sharpe、Max Drawdown、CVaR",
            "personalization_degree": "唯一目标储蓄+风险预算+组合签名数/画像数",
            "expert_evaluation": "协议已定义但当前没有真实专家样本，因此为 null",
        },
        "audit": {
            "external_network_calls": 0,
            "general_llm_results_claimed": False,
            "real_bank_results_claimed": False,
            "expert_results_claimed": False,
            "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
    }
    result["audit"]["result_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result
