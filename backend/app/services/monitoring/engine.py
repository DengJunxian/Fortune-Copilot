from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AdvisorTriggerStatus,
    AuditEventType,
    BehaviorInterventionStatus,
    BehaviorSessionStatus,
    GoalType,
    MonitoringAlertStatus,
    MonitoringPolicyType,
    RiskLevel,
    RiskLimitEffect,
)
from app.models.assessment import RiskAssessment
from app.models.behavior import BehaviorExperimentSession, BehaviorIntervention
from app.models.cfs import CFSSolution, CFSSolutionComponent
from app.models.common import utc_now
from app.models.family import Household
from app.models.family_enterprise import EnterpriseProfile
from app.models.finance import Asset, FinancialGoal
from app.models.financial_twin import FinancialEvent, HouseholdSnapshot, LifeEvent
from app.models.governance import ActionItem, CustomerConfirmation, Product
from app.models.monitoring import (
    AdvisorTrigger,
    BehaviorObservation,
    MonitoringAlert,
    MonitoringPolicy,
)
from app.models.specialized_cfs import CurrencyExposure
from app.models.wealth_graph import Position
from app.schemas.monitoring import (
    AdvisorActionCenterItem,
    AdvisorActionCenterResponse,
    BehaviorInterventionRecordOut,
    BehaviorInterventionsResponse,
    BehaviorObservationOut,
    MonitoringAlertOut,
    MonitoringAlertsResponse,
    MonitoringEvaluateRequest,
    MonitoringEvaluateResponse,
    MonitoringPolicyOut,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.family_enterprise.engine import get_family_enterprise_view
from app.services.monitoring.policies import (
    MonitoringPolicyRule,
    MonitoringRules,
    ensure_monitoring_policies,
    load_monitoring_rules,
)
from app.services.retirement.engine import get_retirement_plan

ZERO = Decimal("0")
RISK_ORDER = list(RiskLevel)
OPEN_ALERT_STATUSES = {
    MonitoringAlertStatus.OPEN,
    MonitoringAlertStatus.ACKNOWLEDGED,
}


@dataclass(frozen=True, slots=True)
class Detection:
    policy_type: MonitoringPolicyType
    value: Decimal
    reason: str
    evidence: dict[str, Any]
    financial_event_id: str | None = None


def _decimal(value: object, default: Decimal = ZERO) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _goal_funding_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
) -> Detection | None:
    goals = list(
        session.scalars(
            select(FinancialGoal).where(
                FinancialGoal.household_id == household_id,
                FinancialGoal.target_amount > ZERO,
                FinancialGoal.is_deleted.is_(False),
            )
        ).all()
    )
    if not goals:
        return None
    ratios = [
        (item, _decimal(item.prepared_amount) / _decimal(item.target_amount))
        for item in goals
    ]
    goal, minimum_ratio = min(ratios, key=lambda item: item[1])
    if minimum_ratio >= policy.threshold:
        return None
    return Detection(
        policy_type=policy.policy_type,
        value=minimum_ratio,
        reason=f"目标“{goal.name}”资金准备度为 {minimum_ratio:.1%}，低于监控阈值。",
        evidence={
            "metric": policy.metric,
            "value": str(minimum_ratio.quantize(Decimal("0.000001"))),
            "threshold": str(policy.threshold),
            "goal_id": goal.id,
            "target_amount": str(goal.target_amount),
            "prepared_amount": str(goal.prepared_amount),
        },
    )


def _eltc_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
) -> Detection | None:
    solutions = list(
        session.scalars(
            select(CFSSolution)
            .where(
                CFSSolution.household_id == household_id,
                CFSSolution.is_deleted.is_(False),
            )
            .order_by(CFSSolution.solution_version.desc())
            .limit(2)
        ).all()
    )
    if len(solutions) < 2:
        return None
    totals: list[Decimal] = []
    component_ids: list[list[str]] = []
    for solution in solutions:
        components = list(
            session.scalars(
                select(CFSSolutionComponent).where(
                    CFSSolutionComponent.solution_id == solution.id,
                    CFSSolutionComponent.is_deleted.is_(False),
                )
            ).all()
        )
        eligible = [item for item in components if item.component_type.value == "investment"]
        totals.append(sum((_decimal(item.target_amount) for item in eligible), ZERO))
        component_ids.append([item.id for item in eligible])
    baseline = totals[1]
    if baseline <= ZERO:
        return None
    change_ratio = abs(totals[0] - baseline) / baseline
    if change_ratio < policy.threshold:
        return None
    return Detection(
        policy_type=policy.policy_type,
        value=change_ratio,
        reason=f"ELTC 对应长期投资目标金额较上一方案变化 {change_ratio:.1%}。",
        evidence={
            "metric": policy.metric,
            "value": str(change_ratio.quantize(Decimal("0.000001"))),
            "threshold": str(policy.threshold),
            "current_solution_id": solutions[0].id,
            "previous_solution_id": solutions[1].id,
            "current_amount": str(totals[0]),
            "previous_amount": str(totals[1]),
            "component_ids": component_ids,
        },
    )


def _risk_budget_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
) -> Detection | None:
    solution = session.scalar(
        select(CFSSolution)
        .where(
            CFSSolution.household_id == household_id,
            CFSSolution.is_deleted.is_(False),
        )
        .order_by(CFSSolution.solution_version.desc())
        .limit(1)
    )
    if solution is None:
        return None
    risk_budget = solution.summary.get("risk_budget", {})
    if bool(risk_budget.get("additional_risk_allowed", True)):
        return None
    remaining = _decimal(risk_budget.get("remaining_risk_capacity"))
    return Detection(
        policy_type=policy.policy_type,
        value=remaining,
        reason="最新 CFS 风险预算不允许增加风险暴露。",
        evidence={
            "metric": policy.metric,
            "value": "0",
            "threshold": str(policy.threshold),
            "solution_id": solution.id,
            "risk_budget_version": solution.risk_budget_version,
            "remaining_risk_capacity": str(remaining),
            "decision": risk_budget.get("decision"),
            "constraints": risk_budget.get("constraints", []),
        },
    )


def _asset_concentration_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
) -> Detection | None:
    assets = list(
        session.scalars(
            select(Asset).where(
                Asset.household_id == household_id,
                Asset.market_value > ZERO,
                Asset.is_deleted.is_(False),
            )
        ).all()
    )
    total = sum((_decimal(item.market_value) for item in assets), ZERO)
    if total <= ZERO:
        return None
    largest = max(assets, key=lambda item: item.market_value)
    ratio = _decimal(largest.market_value) / total
    if ratio < policy.threshold:
        return None
    return Detection(
        policy_type=policy.policy_type,
        value=ratio,
        reason=f"单一资产“{largest.name}”占家庭已确认资产 {ratio:.1%}。",
        evidence={
            "metric": policy.metric,
            "value": str(ratio.quantize(Decimal("0.000001"))),
            "threshold": str(policy.threshold),
            "asset_id": largest.id,
            "asset_value": str(largest.market_value),
            "total_asset_value": str(total),
        },
    )


def _enterprise_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
    family_enterprise_rules_path: str,
    analysis_date: date,
) -> Detection | None:
    enterprise_ids = list(
        session.scalars(
            select(EnterpriseProfile.id).where(
                EnterpriseProfile.household_id == household_id,
                EnterpriseProfile.is_deleted.is_(False),
            )
        ).all()
    )
    if not enterprise_ids:
        return None
    view = get_family_enterprise_view(
        session,
        household_id,
        family_enterprise_rules_path,
        analysis_date,
    )
    score = _decimal(view.dependency.score)
    if score < policy.threshold:
        return None
    return Detection(
        policy_type=policy.policy_type,
        value=score,
        reason=f"家企依赖评分为 {score:.1%}（{view.dependency.label}）。",
        evidence={
            "metric": policy.metric,
            "value": str(score),
            "threshold": str(policy.threshold),
            "enterprise_ids": enterprise_ids,
            "dependency_level": view.dependency.level.value,
            "dependency_components": [
                item.model_dump(mode="json") for item in view.dependency.components
            ],
            "guarantee_exposure": str(view.guarantees.outstanding_exposure),
            "additional_equity_risk_allowed": view.economic_capital.additional_equity_risk_allowed,
            "input_hash": view.meta.input_hash,
        },
    )


def _currency_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
) -> Detection | None:
    exposures = list(
        session.scalars(
            select(CurrencyExposure).where(
                CurrencyExposure.household_id == household_id,
                CurrencyExposure.is_deleted.is_(False),
            )
        ).all()
    )
    if not exposures:
        return None
    gross = sum((_decimal(item.amount) for item in exposures), ZERO)
    net_by_currency: dict[str, Decimal] = {}
    for item in exposures:
        direction = Decimal("1") if item.direction.value == "inflow" else Decimal("-1")
        net_by_currency[item.currency] = (
            net_by_currency.get(item.currency, ZERO) + direction * _decimal(item.amount)
        )
    mismatch = max((abs(value) for value in net_by_currency.values()), default=ZERO)
    if mismatch < policy.threshold:
        return None
    currencies = sorted({item.currency for item in exposures})
    return Detection(
        policy_type=policy.policy_type,
        value=mismatch,
        reason=(
            f"已确认外币资产、收入与责任的最大净错配为 {mismatch:.2f}，"
            f"涉及 {', '.join(currencies)}。"
        ),
        evidence={
            "metric": policy.metric,
            "value": str(mismatch),
            "threshold": str(policy.threshold),
            "gross_exposure": str(gross),
            "net_by_currency": {
                currency: str(value) for currency, value in sorted(net_by_currency.items())
            },
            "currencies": currencies,
            "exposure_ids": [item.id for item in exposures],
        },
    )


def _product_maturity_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
    analysis_date: date,
) -> Detection | None:
    rows = list(
        session.execute(
            select(Position, Product)
            .join(Product, Position.product_id == Product.id)
            .where(
                Position.household_id == household_id,
                Position.is_deleted.is_(False),
                Product.is_deleted.is_(False),
            )
        ).all()
    )
    candidates: list[tuple[int, Position, Product, date]] = []
    for position, product in rows:
        maturity = position.withdrawable_date or product.withdrawable_date
        if maturity is None:
            raw_maturity = product.terms.get("maturity_date")
            try:
                maturity = date.fromisoformat(str(raw_maturity)) if raw_maturity else None
            except ValueError:
                maturity = None
        if maturity is None:
            continue
        days = (maturity - analysis_date).days
        if 0 <= days <= int(policy.threshold):
            candidates.append((days, position, product, maturity))
    if not candidates:
        return None
    days, position, product, maturity = min(candidates, key=lambda item: item[0])
    return Detection(
        policy_type=policy.policy_type,
        value=Decimal(days),
        reason=f"持仓“{position.name}”将在 {days} 天后进入到期/可取用窗口。",
        evidence={
            "metric": policy.metric,
            "value": str(days),
            "threshold": str(policy.threshold),
            "position_id": position.id,
            "product_id": product.id,
            "product_code": product.code,
            "maturity_date": maturity.isoformat(),
            "replacement_product_generated": False,
        },
    )


def _snapshot_staleness_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
    analysis_date: date,
) -> Detection | None:
    snapshot = session.scalar(
        select(HouseholdSnapshot)
        .where(
            HouseholdSnapshot.household_id == household_id,
            HouseholdSnapshot.is_deleted.is_(False),
        )
        .order_by(HouseholdSnapshot.snapshot_date.desc(), HouseholdSnapshot.event_cursor.desc())
        .limit(1)
    )
    if snapshot is None:
        return None
    age_days = max(0, (analysis_date - snapshot.snapshot_date).days)
    if age_days <= policy.threshold:
        return None
    return Detection(
        policy_type=policy.policy_type,
        value=Decimal(age_days),
        reason=f"最新家庭快照距分析日已有 {age_days} 天。",
        evidence={
            "metric": policy.metric,
            "value": str(age_days),
            "threshold": str(policy.threshold),
            "snapshot_id": snapshot.id,
            "snapshot_hash": snapshot.snapshot_hash,
            "snapshot_date": snapshot.snapshot_date.isoformat(),
        },
    )


def _retirement_detection(
    session: Session,
    household_id: str,
    actor: ActorContext,
    policy: MonitoringPolicyRule,
    specialized_cfs_rules_path: str,
    analysis_date: date,
) -> Detection | None:
    goals = list(
        session.scalars(
            select(FinancialGoal.id).where(
                FinancialGoal.household_id == household_id,
                FinancialGoal.goal_type == GoalType.RETIREMENT,
                FinancialGoal.is_deleted.is_(False),
            )
        ).all()
    )
    if not goals:
        return None
    plan = get_retirement_plan(
        session,
        household_id,
        actor,
        specialized_cfs_rules_path,
        analysis_date,
    )
    gap = _decimal(plan.output.longevity_gap)
    if not plan.has_retirement_need or gap <= policy.threshold:
        return None
    return Detection(
        policy_type=policy.policy_type,
        value=gap,
        reason=f"退休长寿资金缺口为 {gap:.2f} 元。",
        evidence={
            "metric": policy.metric,
            "value": str(gap),
            "threshold": str(policy.threshold),
            "goal_ids": goals,
            "income_gap": str(plan.output.income_gap),
            "liquidity_gap": str(plan.output.liquidity_gap),
            "rule_version": plan.meta.rule_version,
        },
    )


def _life_event_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
    analysis_date: date,
) -> Detection | None:
    row = session.execute(
        select(LifeEvent, FinancialEvent)
        .join(FinancialEvent, LifeEvent.financial_event_id == FinancialEvent.id)
        .where(
            LifeEvent.household_id == household_id,
            LifeEvent.event_date <= analysis_date,
            LifeEvent.event_date >= analysis_date - timedelta(days=90),
            LifeEvent.is_deleted.is_(False),
            FinancialEvent.is_deleted.is_(False),
        )
        .order_by(LifeEvent.event_date.desc(), LifeEvent.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    life_event, financial_event = row
    return Detection(
        policy_type=policy.policy_type,
        value=Decimal("1"),
        reason=f"近 90 天发生生活事件：{life_event.life_event_type.value}。",
        evidence={
            "metric": policy.metric,
            "value": "1",
            "threshold": str(policy.threshold),
            "life_event_id": life_event.id,
            "life_event_type": life_event.life_event_type.value,
            "event_date": life_event.event_date.isoformat(),
            "expected_financial_impact": str(life_event.expected_financial_impact),
            "processed_snapshot_id": financial_event.processed_snapshot_id,
        },
        financial_event_id=financial_event.id,
    )


def _behavior_detection(
    session: Session,
    household_id: str,
    policy: MonitoringPolicyRule,
    rules: MonitoringRules,
    now: datetime,
) -> Detection | None:
    observations = list(
        session.scalars(
            select(BehaviorObservation)
            .where(
                BehaviorObservation.household_id == household_id,
                BehaviorObservation.observed_at
                >= now - timedelta(days=rules.behavior_lookback_days),
                BehaviorObservation.is_deleted.is_(False),
            )
            .order_by(BehaviorObservation.signal_strength.desc())
        ).all()
    )
    material = [item for item in observations if item.signal_strength >= policy.threshold]
    if not material:
        return None
    strongest = material[0]
    return Detection(
        policy_type=policy.policy_type,
        value=_decimal(strongest.signal_strength),
        reason=(
            f"近 {rules.behavior_lookback_days} 天识别到"
            f" {strongest.observation_type.value} 行为信号。"
        ),
        evidence={
            "metric": policy.metric,
            "value": str(strongest.signal_strength),
            "threshold": str(policy.threshold),
            "observation_ids": [item.id for item in material],
            "observation_types": sorted({item.observation_type.value for item in material}),
            "risk_limit_effects": sorted({item.risk_limit_effect.value for item in material}),
            "risk_limit_can_increase": False,
        },
        financial_event_id=strongest.financial_event_id,
    )


def _persist_observations(
    session: Session,
    household_id: str,
    request: MonitoringEvaluateRequest,
    rules: MonitoringRules,
    analysis_date: date,
    now: datetime,
    customer_confirmation_id: str | None,
) -> list[BehaviorObservation]:
    records: list[BehaviorObservation] = []
    for item in request.observations:
        if item.financial_event_id is not None:
            event_id = session.scalar(
                select(FinancialEvent.id).where(
                    FinancialEvent.id == item.financial_event_id,
                    FinancialEvent.household_id == household_id,
                    FinancialEvent.is_deleted.is_(False),
                )
            )
            if event_id is None:
                raise AppError(
                    "financial_event_not_found",
                    "财务事件不存在或不属于当前家庭",
                    status_code=404,
                )
        observed_at = item.observed_at or now
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        effect = rules.behavior_risk_effects[item.observation_type]
        record = session.scalar(
            select(BehaviorObservation).where(
                BehaviorObservation.household_id == household_id,
                BehaviorObservation.observation_type == item.observation_type,
                BehaviorObservation.observed_at == observed_at,
                BehaviorObservation.source_reference == item.source_reference,
            )
        )
        evidence = {
            **item.evidence,
            "risk_limit_can_increase": False,
            "monitoring_rule_version": rules.semantic_version,
            "customer_confirmation_id": customer_confirmation_id,
        }
        if record is None:
            record = BehaviorObservation(
                household_id=household_id,
                financial_event_id=item.financial_event_id,
                observation_type=item.observation_type,
                observed_at=observed_at,
                signal_strength=item.signal_strength,
                occurrence_count=item.occurrence_count,
                risk_limit_effect=effect,
                hard_facts_changed=request.hard_facts_changed,
                source_reference=item.source_reference,
                evidence_snapshot=evidence,
                valuation_date=analysis_date,
                data_source="v5_monitoring_engine",
                is_user_confirmed=True,
            )
            session.add(record)
        else:
            record.signal_strength = item.signal_strength
            record.occurrence_count = item.occurrence_count
            record.risk_limit_effect = effect
            record.hard_facts_changed = request.hard_facts_changed
            record.evidence_snapshot = evidence
            record.version += 1
        records.append(record)
    session.flush()
    return records


def _behavior_intervention(
    session: Session,
    household: Household,
    observations: list[BehaviorObservation],
    request: MonitoringEvaluateRequest,
    rules: MonitoringRules,
    actor: ActorContext,
    analysis_date: date,
    now: datetime,
    customer_confirmation_id: str | None,
) -> BehaviorIntervention | None:
    material = [
        item
        for item in observations
        if item.signal_strength >= rules.behavior_intervention_threshold
    ]
    if not request.market_shock or request.hard_facts_changed or not material:
        return None
    latest_risk = session.scalar(
        select(RiskAssessment)
        .where(
            RiskAssessment.household_id == household.id,
            RiskAssessment.is_deleted.is_(False),
        )
        .order_by(RiskAssessment.created_at.desc())
        .limit(1)
    )
    capacity = latest_risk.final_risk_limit if latest_risk is not None else RiskLevel.LOW
    should_reduce = any(item.risk_limit_effect == RiskLimitEffect.REDUCE for item in material)
    effective = (
        RISK_ORDER[max(0, RISK_ORDER.index(capacity) - 1)] if should_reduce else capacity
    )
    session_record = session.scalar(
        select(BehaviorExperimentSession)
        .where(
            BehaviorExperimentSession.household_id == household.id,
            BehaviorExperimentSession.status == BehaviorSessionStatus.COMPLETED,
            BehaviorExperimentSession.data_source != "v5_monitoring_engine",
            BehaviorExperimentSession.is_deleted.is_(False),
        )
        .order_by(BehaviorExperimentSession.created_at.desc())
        .limit(1)
    )
    if session_record is None:
        score = latest_risk.behavior_score if latest_risk is not None else Decimal("0")
        session_record = BehaviorExperimentSession(
            household_id=household.id,
            status=BehaviorSessionStatus.EXITED,
            questionnaire={
                "risk_willingness": str(score),
                "loss_tolerance_claim": str(score),
                "investment_experience": str(score),
                "knowledge": str(score),
                "trading_frequency": str(score),
                "attention": str(score),
                "goal_discipline": str(score),
            },
            questionnaire_score=score,
            objective_capacity_limit=capacity,
            questionnaire_claim_limit=capacity,
            effective_risk_limit=effective,
            information_status="exited",
            assigned_variant="monitoring_control",
            experiment_key="monitoring_behavior_intervention",
            consent_basis="confirmed_monitoring_observation",
            summary={"risk_limit_can_increase": False},
            input_version=_canonical_hash([item.id for item in material]),
            formula_version=rules.formula_version,
            experiment_version="monitoring-observation-v1",
            calculation_source="deterministic_monitoring_engine",
            started_at=now,
            exited_at=now,
            valuation_date=analysis_date,
            data_source="v5_monitoring_engine",
            is_user_confirmed=True,
        )
        session.add(session_record)
        session.flush()
    intervention = session.scalar(
        select(BehaviorIntervention).where(
            BehaviorIntervention.session_id == session_record.id,
            BehaviorIntervention.intervention_code == "monitoring_market_shock",
        )
    )
    biases = sorted({item.observation_type.value for item in material})
    evidence = {
        "observation_ids": [item.id for item in material],
        "market_shock": True,
        "hard_facts_changed": False,
        "risk_limit_before": capacity.value,
        "risk_limit_after": effective.value,
        "risk_limit_can_increase": False,
        "customer_confirmation_id": customer_confirmation_id,
        "rule_version": rules.semantic_version,
    }
    if intervention is None:
        intervention = BehaviorIntervention(
            household_id=household.id,
            session_id=session_record.id,
            intervention_code="monitoring_market_shock",
            name="市场冲击行为冷静与教育",
            status=BehaviorInterventionStatus.ACTIVE,
            trigger_biases=biases,
            scenario_code="market_shock_hard_facts_unchanged",
            personalized_message=(
                f"{household.name}的家庭硬事实未发生重大变化；先把市场波动与长期目标分开判断。"
            ),
            action_instruction=(
                "进入冷静期，查看原计划与压力情景对比；如仍担忧，请联系顾问。"
                "本干预不新增产品、不自动交易。"
            ),
            cooling_period_hours=rules.cooling_period_hours,
            starts_at=now,
            eligible_at=now + timedelta(hours=rules.cooling_period_hours),
            assigned_variant="monitoring_control",
            evidence=evidence,
            valuation_date=analysis_date,
            data_source="v5_monitoring_engine",
            is_user_confirmed=True,
        )
        session.add(intervention)
        session.flush()
        add_audit_event(
            session,
            intervention,
            actor,
            AuditEventType.BEHAVIOR_INTERVENTION_UPDATED,
            "市场冲击与行为偏差信号触发冷静和教育干预",
        )
    else:
        intervention.trigger_biases = biases
        intervention.evidence = evidence
        intervention.version += 1
    return intervention


def _detections(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules: MonitoringRules,
    analysis_date: date,
    now: datetime,
    family_enterprise_rules_path: str,
    specialized_cfs_rules_path: str,
) -> dict[MonitoringPolicyType, Detection]:
    policy = rules.by_type()
    candidates = [
        _goal_funding_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.GOAL_FUNDING_DRIFT],
        ),
        _eltc_detection(session, household_id, policy[MonitoringPolicyType.ELTC_CHANGE]),
        _risk_budget_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.RISK_BUDGET_BREACH],
        ),
        _asset_concentration_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.ASSET_CONCENTRATION],
        ),
        _enterprise_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.ENTERPRISE_DEPENDENCY],
            family_enterprise_rules_path,
            analysis_date,
        ),
        _currency_detection(session, household_id, policy[MonitoringPolicyType.CURRENCY_MISMATCH]),
        _product_maturity_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.PRODUCT_MATURITY],
            analysis_date,
        ),
        _snapshot_staleness_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.SNAPSHOT_STALENESS],
            analysis_date,
        ),
        _retirement_detection(
            session,
            household_id,
            actor,
            policy[MonitoringPolicyType.RETIREMENT_GAP],
            specialized_cfs_rules_path,
            analysis_date,
        ),
        _life_event_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.LIFE_EVENT],
            analysis_date,
        ),
        _behavior_detection(
            session,
            household_id,
            policy[MonitoringPolicyType.BEHAVIOR_DRIFT],
            rules,
            now,
        ),
    ]
    return {item.policy_type: item for item in candidates if item is not None}


def _alert_out(alert: MonitoringAlert, policy_type: MonitoringPolicyType) -> MonitoringAlertOut:
    return MonitoringAlertOut(
        id=alert.id,
        household_id=alert.household_id,
        monitoring_policy_id=alert.monitoring_policy_id,
        financial_event_id=alert.financial_event_id,
        policy_type=policy_type,
        trigger_reason=alert.trigger_reason,
        client_impact=alert.client_impact,
        severity=alert.severity,
        recommended_action=alert.recommended_action,
        do_not_sell_flag=alert.do_not_sell_flag,
        required_specialist=alert.required_specialist,
        evidence_snapshot=alert.evidence_snapshot,
        status=alert.status,
        detected_at=alert.detected_at,
        resolved_at=alert.resolved_at,
    )


def _ensure_advisor_work(
    session: Session,
    alert: MonitoringAlert,
    policy_rule: MonitoringPolicyRule,
    analysis_date: date,
) -> None:
    trigger = session.scalar(
        select(AdvisorTrigger).where(
            AdvisorTrigger.monitoring_alert_id == alert.id,
            AdvisorTrigger.trigger_type == policy_rule.action_type,
        )
    )
    due = analysis_date + timedelta(days=policy_rule.due_days)
    if trigger is None:
        trigger = AdvisorTrigger(
            household_id=alert.household_id,
            monitoring_alert_id=alert.id,
            trigger_type=policy_rule.action_type,
            urgency=alert.severity,
            reason=alert.trigger_reason,
            required_role=policy_rule.required_role,
            follow_up_due=due,
            status=AdvisorTriggerStatus.OPEN,
            valuation_date=analysis_date,
            data_source="v5_monitoring_engine",
            is_user_confirmed=True,
        )
        session.add(trigger)
        session.flush()
    action_code = f"MONITOR_{policy_rule.policy_type.value.upper()}"
    action = session.scalar(
        select(ActionItem).where(
            ActionItem.household_id == alert.household_id,
            ActionItem.action_code == action_code,
        )
    )
    evidence = {
        "monitoring_alert_id": alert.id,
        "monitoring_policy_id": alert.monitoring_policy_id,
        "trigger_reason": alert.trigger_reason,
        "client_impact": alert.client_impact,
        "recommended_action": alert.recommended_action,
        "do_not_sell_flag": True,
        "evidence_snapshot": alert.evidence_snapshot,
    }
    if action is None:
        action = ActionItem(
            household_id=alert.household_id,
            advisor_trigger_id=trigger.id,
            action_code=action_code,
            action_type=policy_rule.action_type,
            do_not_sell_flag=True,
            required_specialist=policy_rule.required_specialist,
            title=alert.recommended_action,
            due_date=due,
            status="open",
            owner_role=policy_rule.required_role,
            evidence=evidence,
            valuation_date=analysis_date,
            data_source="v5_monitoring_engine",
            is_user_confirmed=False,
        )
        session.add(action)
    else:
        action.advisor_trigger_id = trigger.id
        action.action_type = policy_rule.action_type
        action.do_not_sell_flag = True
        action.required_specialist = policy_rule.required_specialist
        action.title = alert.recommended_action
        action.due_date = due
        action.status = "open"
        action.completed_at = None
        action.status_reason = None
        action.owner_role = policy_rule.required_role
        action.evidence = evidence
        action.version += 1


def evaluate_monitoring(
    session: Session,
    household_id: str,
    actor: ActorContext,
    request: MonitoringEvaluateRequest,
    monitoring_rules_path: str,
    family_enterprise_rules_path: str,
    specialized_cfs_rules_path: str,
) -> MonitoringEvaluateResponse:
    household = ensure_household(session, household_id)
    rules = load_monitoring_rules(monitoring_rules_path)
    analysis_date = request.analysis_date or date.today()
    now = utc_now()
    confirmation_statement = select(CustomerConfirmation).where(
        CustomerConfirmation.household_id == household_id,
        CustomerConfirmation.is_deleted.is_(False),
    )
    if request.customer_confirmation_id is not None:
        confirmation_statement = confirmation_statement.where(
            CustomerConfirmation.id == request.customer_confirmation_id
        )
    customer_confirmation = session.scalar(
        confirmation_statement.order_by(CustomerConfirmation.confirmed_at.desc()).limit(1)
    )
    if request.customer_confirmation_id is not None and customer_confirmation is None:
        raise AppError(
            "customer_confirmation_not_found",
            "客户确认记录不存在或不属于当前家庭",
            status_code=404,
        )
    customer_confirmation_id = (
        customer_confirmation.id if customer_confirmation is not None else None
    )
    observations = _persist_observations(
        session,
        household_id,
        request,
        rules,
        analysis_date,
        now,
        customer_confirmation_id,
    )
    policies = ensure_monitoring_policies(
        session,
        household_id,
        rules,
        analysis_date,
    )
    detections = _detections(
        session,
        household_id,
        actor,
        rules,
        analysis_date,
        now,
        family_enterprise_rules_path,
        specialized_cfs_rules_path,
    )
    rule_by_type = rules.by_type()
    resolved_count = 0
    current_alerts: list[MonitoringAlert] = []
    evaluated_policy_count = 0
    for policy_record in policies:
        policy_rule = rule_by_type[policy_record.policy_type]
        open_alerts = list(
            session.scalars(
                select(MonitoringAlert).where(
                    MonitoringAlert.monitoring_policy_id == policy_record.id,
                    MonitoringAlert.status.in_(OPEN_ALERT_STATUSES),
                    MonitoringAlert.is_deleted.is_(False),
                )
            ).all()
        )
        policy_enabled = (
            policy_record.active
            and policy_record.effective_from <= analysis_date
            and (
                policy_record.effective_to is None
                or policy_record.effective_to >= analysis_date
            )
        )
        if policy_enabled:
            evaluated_policy_count += 1
        detection = detections.get(policy_record.policy_type) if policy_enabled else None
        if detection is None:
            for alert in open_alerts:
                alert.status = MonitoringAlertStatus.RESOLVED
                alert.resolved_at = now
                alert.version += 1
                resolved_count += 1
                for trigger in session.scalars(
                    select(AdvisorTrigger).where(
                        AdvisorTrigger.monitoring_alert_id == alert.id,
                        AdvisorTrigger.status.in_(
                            {AdvisorTriggerStatus.OPEN, AdvisorTriggerStatus.IN_PROGRESS}
                        ),
                    )
                ).all():
                    trigger.status = AdvisorTriggerStatus.COMPLETED
                    trigger.version += 1
                    for action in session.scalars(
                        select(ActionItem).where(
                            ActionItem.advisor_trigger_id == trigger.id,
                            ActionItem.status.in_({"open", "in_progress"}),
                            ActionItem.is_deleted.is_(False),
                        )
                    ).all():
                        action.status = "completed"
                        action.completed_at = now
                        action.status_reason = "monitoring_condition_cleared"
                        action.status_changed_at = now
                        action.version += 1
            continue
        evidence = {
            **detection.evidence,
            "evaluation_hash": _canonical_hash(detection.evidence),
            "analysis_date": analysis_date.isoformat(),
            "rule_version": rules.semantic_version,
            "formula_version": rules.formula_version,
            "customer_confirmation_id": customer_confirmation_id,
        }
        current_alert = open_alerts[0] if open_alerts else None
        for duplicate in open_alerts[1:]:
            duplicate.status = MonitoringAlertStatus.RESOLVED
            duplicate.resolved_at = now
            duplicate.version += 1
            resolved_count += 1
        if current_alert is None:
            current_alert = MonitoringAlert(
                household_id=household_id,
                monitoring_policy_id=policy_record.id,
                financial_event_id=detection.financial_event_id,
                trigger_reason=detection.reason,
                client_impact=policy_rule.client_impact,
                severity=policy_rule.severity,
                recommended_action=policy_rule.recommended_action,
                do_not_sell_flag=True,
                required_specialist=policy_rule.required_specialist,
                evidence_snapshot=evidence,
                status=MonitoringAlertStatus.OPEN,
                detected_at=now,
                valuation_date=analysis_date,
                data_source="v5_monitoring_engine",
                is_user_confirmed=True,
            )
            session.add(current_alert)
            session.flush()
            add_audit_event(
                session,
                current_alert,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                f"监控策略触发：{policy_record.policy_type.value}",
            )
        else:
            changed = (
                current_alert.trigger_reason != detection.reason
                or current_alert.evidence_snapshot != evidence
                or current_alert.financial_event_id != detection.financial_event_id
            )
            if changed:
                current_alert.trigger_reason = detection.reason
                current_alert.financial_event_id = detection.financial_event_id
                current_alert.evidence_snapshot = evidence
                current_alert.version += 1
        _ensure_advisor_work(session, current_alert, policy_rule, analysis_date)
        current_alerts.append(current_alert)
    intervention = _behavior_intervention(
        session,
        household,
        observations,
        request,
        rules,
        actor,
        analysis_date,
        now,
        customer_confirmation_id,
    )
    session.commit()
    policy_types = {item.id: item.policy_type for item in policies}
    return MonitoringEvaluateResponse(
        household_id=household_id,
        analysis_date=analysis_date,
        rule_version=rules.semantic_version,
        evaluated_policy_count=evaluated_policy_count,
        triggered_policy_count=len(current_alerts),
        resolved_alert_count=resolved_count,
        policies=[MonitoringPolicyOut.model_validate(item) for item in policies],
        alerts=[
            _alert_out(item, policy_types[item.monitoring_policy_id])
            for item in current_alerts
        ],
        observations=[BehaviorObservationOut.model_validate(item) for item in observations],
        intervention_ids=[intervention.id] if intervention is not None else [],
    )


def list_monitoring_alerts(
    session: Session,
    household_id: str,
    monitoring_rules_path: str,
) -> MonitoringAlertsResponse:
    ensure_household(session, household_id)
    rules = load_monitoring_rules(monitoring_rules_path)
    rows = list(
        session.execute(
            select(MonitoringAlert, MonitoringPolicy)
            .join(MonitoringPolicy, MonitoringAlert.monitoring_policy_id == MonitoringPolicy.id)
            .where(
                MonitoringAlert.household_id == household_id,
                MonitoringAlert.is_deleted.is_(False),
            )
            .order_by(MonitoringAlert.detected_at.desc(), MonitoringAlert.id)
        ).all()
    )
    return MonitoringAlertsResponse(
        household_id=household_id,
        rule_version=rules.semantic_version,
        alerts=[_alert_out(alert, policy.policy_type) for alert, policy in rows],
    )


def list_behavior_interventions(
    session: Session,
    household_id: str,
) -> BehaviorInterventionsResponse:
    ensure_household(session, household_id)
    records = list(
        session.scalars(
            select(BehaviorIntervention)
            .where(
                BehaviorIntervention.household_id == household_id,
                BehaviorIntervention.is_deleted.is_(False),
            )
            .order_by(BehaviorIntervention.starts_at.desc(), BehaviorIntervention.id)
        ).all()
    )
    return BehaviorInterventionsResponse(
        household_id=household_id,
        interventions=[
            BehaviorInterventionRecordOut(
                id=item.id,
                status=item.status,
                intervention_code=item.intervention_code,
                name=item.name,
                trigger_biases=item.trigger_biases,
                scenario_code=item.scenario_code,
                personalized_message=item.personalized_message,
                action_instruction=item.action_instruction,
                cooling_period_hours=item.cooling_period_hours,
                starts_at=item.starts_at,
                eligible_at=item.eligible_at,
                evidence=item.evidence,
            )
            for item in records
        ],
    )


def advisor_action_center(
    session: Session,
    actor: ActorContext,
    analysis_date: date,
) -> AdvisorActionCenterResponse:
    filters: list[Any] = [
        AdvisorTrigger.status.in_({AdvisorTriggerStatus.OPEN, AdvisorTriggerStatus.IN_PROGRESS}),
        AdvisorTrigger.is_deleted.is_(False),
        Household.is_deleted.is_(False),
    ]
    if actor.role != "admin" and "*" not in actor.household_ids:
        filters.append(AdvisorTrigger.household_id.in_(actor.household_ids))
    rows = list(
        session.execute(
            select(AdvisorTrigger, Household, ActionItem)
            .join(Household, AdvisorTrigger.household_id == Household.id)
            .outerjoin(ActionItem, ActionItem.advisor_trigger_id == AdvisorTrigger.id)
            .where(*filters)
            .order_by(
                AdvisorTrigger.follow_up_due,
                AdvisorTrigger.urgency.desc(),
                AdvisorTrigger.created_at,
            )
        ).all()
    )
    items = [
        AdvisorActionCenterItem(
            trigger_id=trigger.id,
            household_id=trigger.household_id,
            household_code=household.code,
            household_name=household.name,
            trigger_type=trigger.trigger_type,
            urgency=trigger.urgency,
            reason=trigger.reason,
            required_role=trigger.required_role,
            follow_up_due=trigger.follow_up_due,
            status=trigger.status,
            action_item_id=action.id if action else None,
            action_code=action.action_code if action else None,
            action_type=action.action_type if action else None,
            title=action.title if action else None,
            do_not_sell_flag=action.do_not_sell_flag if action else True,
            required_specialist=action.required_specialist if action else None,
            evidence=action.evidence if action else {},
        )
        for trigger, household, action in rows
    ]
    return AdvisorActionCenterResponse(
        items=items,
        open_count=len(items),
        overdue_count=sum(
            item.follow_up_due is not None and item.follow_up_due < analysis_date
            for item in items
        ),
        boundary="行动中心只呈现客户影响、复核和专业转介；不得转化为 Next Best Sale。",
    )
