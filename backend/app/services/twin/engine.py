from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import AuditEventType, SimulationStatus
from app.models.common import utc_now
from app.models.governance import AuditEvent, ScenarioDefinition, SimulationRun
from app.schemas.twin import (
    PlanAdjustments,
    ScenarioCatalogResponse,
    ScenarioDefinitionOut,
    ScenarioOverrides,
    SimulationDistribution,
    TwinResult,
    TwinResultMeta,
    TwinRunRequest,
    TwinRunStatusResponse,
)
from app.services.financial.facts import load_household_facts
from app.services.planning.engine import empty_counterfactual, plan_facts
from app.services.planning.rules import load_planning_rules
from app.services.twin.rules import (
    TwinRules,
    ensure_scenario_definitions,
    ensure_twin_rule_version,
    load_twin_rules,
)
from app.services.twin.simulator import (
    build_assumption_snapshot,
    build_comparison,
    build_scenario_impact,
    request_parameter_hash,
    resolve_simulation_config,
    simulate_distribution,
)
from app.services.twin.state import build_twin_model_input, initial_state_response


def _input_version(planning_input_version: str, parameter_hash: str, rules: TwinRules) -> str:
    payload = f"{planning_input_version}:{parameter_hash}:{rules.semantic_version}"
    return hashlib.sha256(payload.encode()).hexdigest()


def scenario_catalog(session: Session, twin_rules_path: str) -> ScenarioCatalogResponse:
    rules = load_twin_rules(twin_rules_path)
    ensure_twin_rule_version(session, rules)
    records = ensure_scenario_definitions(session, rules)
    session.commit()
    records_by_code = {item.code: item for item in records}
    return ScenarioCatalogResponse(
        scenario_version=rules.scenario_version,
        source_summary=rules.source_summary,
        scenario_count=len(rules.scenarios),
        scenarios=[
            ScenarioDefinitionOut(
                code=item.code,
                name=item.name,
                category=item.category,
                description=item.description,
                parameters=item.parameters.model_dump(mode="json"),
                explanation=item.explanation,
                scenario_version=rules.scenario_version,
                is_composable=item.is_composable,
                enabled=records_by_code[item.code].enabled,
            )
            for item in rules.scenarios
        ],
    )


def _ensure_requested_scenarios(
    session: Session,
    rules: TwinRules,
    codes: list[str],
) -> ScenarioDefinition:
    records = ensure_scenario_definitions(session, rules)
    by_code = {item.code: item for item in records}
    unknown = sorted(set(codes) - set(by_code))
    disabled = sorted(code for code in codes if code in by_code and not by_code[code].enabled)
    if unknown or disabled:
        raise AppError(
            "twin_scenario_unavailable",
            "压力场景不存在或当前不可用",
            status_code=422,
            details={"unknown": unknown, "disabled": disabled},
        )
    return by_code[codes[0]]


def start_twin_run(
    session: Session,
    household_id: str,
    request: TwinRunRequest,
    actor: ActorContext,
    financial_rules_path: str,
    planning_rules_path: str,
    twin_rules_path: str,
) -> TwinRunStatusResponse:
    facts = load_household_facts(session, household_id)
    rules = load_twin_rules(twin_rules_path)
    rule_version = ensure_twin_rule_version(session, rules)
    scenario = _ensure_requested_scenarios(session, rules, request.scenario_codes)
    try:
        resolved = resolve_simulation_config(
            rules,
            request,
            request.scenario_codes,
            request.plan_adjustments,
        )
    except ValueError as exc:
        raise AppError(
            "twin_parameters_invalid",
            "数字孪生参数未通过规则校验",
            status_code=422,
        ) from exc
    planning = plan_facts(
        facts,
        financial_rules_path,
        load_planning_rules(planning_rules_path),
        request.analysis_date or date.today(),
        empty_counterfactual(),
    )
    parameter_hash = request_parameter_hash(request, rules.semantic_version)
    input_version = _input_version(planning.meta.input_version, parameter_hash, rules)
    run = SimulationRun(
        household_id=household_id,
        scenario_id=scenario.id,
        snapshot_id=None,
        random_seed=request.seed,
        engine_version=rules.engine_version,
        inputs={
            "request": request.model_dump(mode="json"),
            "rule_version": rules.semantic_version,
            "planning_input_version": planning.meta.input_version,
            "data_as_of": planning.meta.data_as_of.isoformat(),
            "actor_id": actor.actor_id,
            "actor_role": actor.role,
        },
        outputs={"phase": "queued", "partial": {}},
        status=SimulationStatus.QUEUED,
        progress_percent=0,
        scenario_codes=request.scenario_codes,
        path_count=request.path_count,
        horizon_months=resolved.horizon_months,
        time_step_months=rules.time_step_months,
        input_version=input_version,
        formula_version=rules.formula_version,
        result_version=rules.result_version,
        parameter_hash=parameter_hash,
        rule_version_id=rule_version.id,
        calculation_source="deterministic_simulation_engine",
        cancel_requested=False,
        valuation_date=request.analysis_date or date.today(),
        data_source="deterministic_wealth_twin",
        is_user_confirmed=False,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run_status_response(run)


def _get_run(session: Session, household_id: str, run_id: str) -> SimulationRun:
    run = session.scalar(
        select(SimulationRun).where(
            SimulationRun.id == run_id,
            SimulationRun.household_id == household_id,
            SimulationRun.is_deleted.is_(False),
        )
    )
    if run is None:
        raise AppError("twin_run_not_found", "找不到数字孪生运行记录", status_code=404)
    return run


def get_twin_run(session: Session, household_id: str, run_id: str) -> TwinRunStatusResponse:
    return run_status_response(_get_run(session, household_id, run_id))


def _baseline_request(request: TwinRunRequest) -> TwinRunRequest:
    return request.model_copy(
        update={
            "scenario_overrides": ScenarioOverrides(),
            "plan_adjustments": PlanAdjustments(),
            "family_events": [],
        }
    )


def _cancelled_during_phase(session: Session, run: SimulationRun) -> bool:
    """Reload a run before persisting expensive phase output.

    A client can cancel through a second request while this worker is still
    computing.  Refreshing here prevents the late phase commit from replacing
    the already-audited cancelled state.
    """

    session.refresh(run)
    return run.cancel_requested or run.status == SimulationStatus.CANCELLED


def _complete_run(
    session: Session,
    run: SimulationRun,
    actor: ActorContext,
    rules: TwinRules,
    request: TwinRunRequest,
    facts_code: str,
    facts_synthetic: bool,
    facts_currency: str,
    data_as_of: date,
    model: object,
    partial: dict[str, object],
    optimized: SimulationDistribution,
    optimized_config: object,
) -> None:
    from app.services.twin.simulator import SimulationConfig
    from app.services.twin.state import TwinModelInput

    if not isinstance(model, TwinModelInput) or not isinstance(optimized_config, SimulationConfig):
        raise TypeError("数字孪生内部状态类型无效")
    baseline = SimulationDistribution.model_validate(partial["baseline"])
    original = SimulationDistribution.model_validate(partial["original_stress"])
    individual_raw = partial.get("individual", {})
    if not isinstance(individual_raw, dict):
        raise TypeError("单场景结果格式无效")
    impacts = []
    for code in run.scenario_codes:
        individual = SimulationDistribution.model_validate(individual_raw[code])
        individual_config = resolve_simulation_config(
            rules,
            request,
            [code],
            PlanAdjustments(),
        )
        impacts.append(build_scenario_impact(model, rules, baseline, individual, individual_config))
    assumptions = build_assumption_snapshot(
        rules,
        request,
        optimized_config,
        run.parameter_hash,
    )
    comparison = build_comparison(request, baseline, original, optimized)
    result = TwinResult(
        meta=TwinResultMeta(
            run_id=run.id,
            household_id=run.household_id,
            household_code=facts_code,
            analysis_date=run.valuation_date or date.today(),
            data_as_of=data_as_of,
            input_version=run.input_version,
            rule_code=rules.code,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
            engine_version=rules.engine_version,
            result_version=rules.result_version,
            scenario_version=rules.scenario_version,
            synthetic_data=facts_synthetic,
            currency=facts_currency,
        ),
        initial_state=initial_state_response(model),
        assumptions=assumptions,
        baseline=baseline,
        original_stress=original,
        optimized_stress=optimized,
        scenario_impacts=impacts,
        comparison=comparison,
        limitations=[
            "收益、波动、相关性、通胀、收入增长和压力参数均为 internal_demo，不是预测或收益承诺。",
            "Monte Carlo 展示给定模型和参数下的路径分布，不能穷尽政策、健康、市场和家庭结构风险。",
            "保险仅按有效保额与免赔额做简化抵扣，不替代合同责任、除外责任和理赔审核。",
            "自住房估值进入净资产，但不会自动当作目标流动资金；信用卡额度从未进入资产。",
            "原方案与优化方案使用相同 seed 和共同随机数；差异来自显式参数，不来自重新抽样。",
        ],
        counting_note=(
            "逐月先更新资产收益、收入与养老金，再扣除生活支出、债务和到期目标；"
            "现金与固定收益不足时才记录长期资产被迫出售。目标支出只在到期月扣减一次。"
        ),
    )
    event = AuditEvent(
        household_id=run.household_id,
        event_type=AuditEventType.SIMULATION_EXECUTED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="SimulationRun",
        entity_id=run.id,
        event_version=run.version,
        summary=(
            f"完成财富数字孪生：{run.path_count} 路径／{run.horizon_months} 月／"
            f"{len(run.scenario_codes)} 个压力场景"
        ),
        evidence={
            "seed": run.random_seed,
            "path_count": run.path_count,
            "horizon_months": run.horizon_months,
            "scenario_codes": run.scenario_codes,
            "input_version": run.input_version,
            "parameter_hash": run.parameter_hash,
            "rule_version": rules.semantic_version,
            "engine_version": rules.engine_version,
            "baseline_success": str(baseline.goal_success_probability),
            "stress_success": str(original.goal_success_probability),
            "optimized_success": str(optimized.goal_success_probability),
        },
        occurred_at=utc_now(),
        valuation_date=run.valuation_date,
        data_source="deterministic_wealth_twin",
        is_user_confirmed=True,
    )
    session.add(event)
    session.flush()
    run.outputs = {
        "phase": "completed",
        "result": result.model_dump(mode="json"),
        "audit_event_id": event.id,
    }
    run.status = SimulationStatus.COMPLETED
    run.progress_percent = 100
    run.completed_at = utc_now()
    run.error_code = None


def advance_twin_run(
    session: Session,
    household_id: str,
    run_id: str,
    actor: ActorContext,
    twin_rules_path: str,
) -> TwinRunStatusResponse:
    run = _get_run(session, household_id, run_id)
    if run.status in {SimulationStatus.COMPLETED, SimulationStatus.CANCELLED}:
        return run_status_response(run)
    if run.status == SimulationStatus.FAILED:
        raise AppError("twin_run_failed", "数字孪生运行已失败，不能继续", status_code=409)
    if run.cancel_requested:
        run.status = SimulationStatus.CANCELLED
        run.completed_at = utc_now()
        session.commit()
        return run_status_response(run)
    rules = load_twin_rules(twin_rules_path)
    request_raw = run.inputs.get("request")
    if not isinstance(request_raw, dict):
        raise AppError("twin_run_corrupt", "数字孪生运行输入损坏", status_code=500)
    request = TwinRunRequest.model_validate(request_raw)
    facts = load_household_facts(session, household_id)
    model = build_twin_model_input(facts, run.valuation_date or date.today())
    partial_raw = run.outputs.get("partial", {})
    partial: dict[str, object] = dict(partial_raw) if isinstance(partial_raw, dict) else {}
    run.status = SimulationStatus.RUNNING
    run.started_at = run.started_at or utc_now()
    try:
        if "baseline" not in partial:
            baseline, _ = simulate_distribution(
                model,
                rules,
                _baseline_request(request),
                [],
                PlanAdjustments(),
                "无冲击基线",
            )
            if _cancelled_during_phase(session, run):
                return run_status_response(run)
            partial["baseline"] = baseline.model_dump(mode="json")
            run.progress_percent = 20
            phase = "baseline_completed"
        else:
            individual_raw = partial.get("individual", {})
            individual: dict[str, object] = (
                dict(individual_raw) if isinstance(individual_raw, dict) else {}
            )
            remaining = [code for code in run.scenario_codes if code not in individual]
            if remaining:
                code = remaining[0]
                distribution, _ = simulate_distribution(
                    model,
                    rules,
                    request,
                    [code],
                    PlanAdjustments(),
                    f"单场景：{code}",
                )
                if _cancelled_during_phase(session, run):
                    return run_status_response(run)
                individual[code] = distribution.model_dump(mode="json")
                partial["individual"] = individual
                run.progress_percent = 20 + int(35 * len(individual) / len(run.scenario_codes))
                phase = f"scenario_{len(individual)}_of_{len(run.scenario_codes)}"
            elif "original_stress" not in partial:
                if len(run.scenario_codes) == 1:
                    partial["original_stress"] = individual[run.scenario_codes[0]]
                else:
                    original, _ = simulate_distribution(
                        model,
                        rules,
                        request,
                        run.scenario_codes,
                        PlanAdjustments(),
                        "原方案／组合压力",
                    )
                    if _cancelled_during_phase(session, run):
                        return run_status_response(run)
                    partial["original_stress"] = original.model_dump(mode="json")
                run.progress_percent = 70
                phase = "original_stress_completed"
            else:
                optimized, optimized_config = simulate_distribution(
                    model,
                    rules,
                    request,
                    run.scenario_codes,
                    request.plan_adjustments,
                    "优化方案／组合压力",
                )
                if _cancelled_during_phase(session, run):
                    return run_status_response(run)
                _complete_run(
                    session,
                    run,
                    actor,
                    rules,
                    request,
                    facts.code,
                    facts.is_synthetic,
                    facts.currency,
                    date.fromisoformat(str(run.inputs["data_as_of"])),
                    model,
                    partial,
                    optimized,
                    optimized_config,
                )
                session.commit()
                session.refresh(run)
                return run_status_response(run)
        run.outputs = {"phase": phase, "partial": partial}
        session.commit()
        session.refresh(run)
        return run_status_response(run)
    except Exception as exc:
        session.rollback()
        failed = _get_run(session, household_id, run_id)
        failed.status = SimulationStatus.FAILED
        failed.error_code = "simulation_computation_failed"
        failed.completed_at = utc_now()
        failed.outputs = {"phase": "failed", "partial": partial}
        session.commit()
        raise AppError(
            "twin_simulation_failed",
            "数字孪生计算失败；运行已保留错误状态，不返回部分结果",
            status_code=500,
        ) from exc


def cancel_twin_run(
    session: Session,
    household_id: str,
    run_id: str,
    actor: ActorContext,
) -> TwinRunStatusResponse:
    run = _get_run(session, household_id, run_id)
    if run.status == SimulationStatus.COMPLETED:
        raise AppError("twin_run_already_completed", "已完成运行不能取消", status_code=409)
    if run.status == SimulationStatus.FAILED:
        raise AppError("twin_run_already_failed", "已失败运行不能取消", status_code=409)
    if run.status != SimulationStatus.CANCELLED:
        run.cancel_requested = True
        run.status = SimulationStatus.CANCELLED
        run.completed_at = utc_now()
        event = AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.SIMULATION_CANCELLED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="SimulationRun",
            entity_id=run.id,
            event_version=run.version,
            summary=f"取消财富数字孪生运行，完成进度 {run.progress_percent}%",
            evidence={
                "progress_percent": run.progress_percent,
                "scenario_codes": run.scenario_codes,
                "input_version": run.input_version,
            },
            occurred_at=utc_now(),
            valuation_date=run.valuation_date,
            data_source="deterministic_wealth_twin",
            is_user_confirmed=True,
        )
        session.add(event)
        session.flush()
        run.outputs = {
            **run.outputs,
            "phase": "cancelled",
            "audit_event_id": event.id,
        }
        session.commit()
        session.refresh(run)
    return run_status_response(run)


def export_twin_result(session: Session, household_id: str, run_id: str) -> TwinResult:
    run = _get_run(session, household_id, run_id)
    if run.status != SimulationStatus.COMPLETED:
        raise AppError(
            "twin_result_not_ready",
            "数字孪生运行尚未完成，不能导出",
            status_code=409,
            details={"status": run.status.value, "progress_percent": run.progress_percent},
        )
    result = run.outputs.get("result")
    if not isinstance(result, dict):
        raise AppError("twin_result_missing", "数字孪生结果缺失", status_code=500)
    return TwinResult.model_validate(result)


def run_status_response(run: SimulationRun) -> TwinRunStatusResponse:
    result_raw = run.outputs.get("result") if isinstance(run.outputs, dict) else None
    result = TwinResult.model_validate(result_raw) if isinstance(result_raw, dict) else None
    phase_raw = (
        run.outputs.get("phase", run.status.value) if isinstance(run.outputs, dict) else None
    )
    audit_raw = run.outputs.get("audit_event_id") if isinstance(run.outputs, dict) else None
    rule_version = run.inputs.get("rule_version", "unknown")
    return TwinRunStatusResponse(
        run_id=run.id,
        household_id=run.household_id,
        status=run.status,
        progress_percent=run.progress_percent,
        phase=str(phase_raw or run.status.value),
        scenario_codes=list(run.scenario_codes),
        path_count=run.path_count,
        horizon_months=run.horizon_months,
        seed=run.random_seed,
        input_version=run.input_version,
        rule_version=str(rule_version),
        engine_version=run.engine_version,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        cancel_requested=run.cancel_requested,
        audit_event_id=str(audit_raw) if audit_raw else None,
        error_code=run.error_code,
        result=result,
    )
