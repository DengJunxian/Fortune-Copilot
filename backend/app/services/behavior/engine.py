from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AuditEventType,
    BehaviorInterventionStatus,
    BehaviorSessionStatus,
)
from app.models.assessment import BehaviorAssessment, RiskAssessment
from app.models.behavior import (
    BehaviorBiasFinding,
    BehaviorExperimentAssignment,
    BehaviorExperimentResponse,
    BehaviorExperimentSession,
    BehaviorIntervention,
)
from app.models.common import utc_now
from app.models.family import ConsentRecord, Household
from app.models.finance import FinancialGoal
from app.models.governance import AuditEvent
from app.schemas.behavior import (
    ABVariantMetricOut,
    ABVariantOut,
    BehaviorABFrameworkResponse,
    BehaviorCatalogResponse,
    BehaviorExperimentOut,
    BehaviorInterventionOut,
    BehaviorOverviewResponse,
    BehaviorProfileMeta,
    BehaviorProfileOut,
    BehaviorQuestionnaireInput,
    BehaviorResponseOut,
    BehaviorSessionOut,
    BiasDefinitionOut,
    ExitBehaviorSessionResponse,
    ExperimentOptionOut,
    InterventionActionRequest,
    InterventionDefinitionOut,
    QuestionnaireDimensionOut,
    RecordBehaviorResponseRequest,
    StartBehaviorSessionRequest,
)
from app.services.behavior.rules import (
    BehaviorRules,
    InterventionRule,
    ensure_behavior_rule_version,
    load_behavior_rules,
)
from app.services.behavior.scoring import (
    BehaviorEvaluation,
    RawResponse,
    evaluate_behavior,
    experiment_rule,
    option_rule,
    q6,
    questionnaire_score,
    response_consistency,
    score_to_level,
)
from app.services.crud import ensure_household


def behavior_catalog(session: Session, rules_path: str) -> BehaviorCatalogResponse:
    rules = load_behavior_rules(rules_path)
    ensure_behavior_rule_version(session, rules)
    session.commit()
    return BehaviorCatalogResponse(
        rule_version=rules.semantic_version,
        formula_version=rules.formula_version,
        experiment_version=rules.experiment_version,
        ab_framework_version=rules.ab_framework_version,
        source_summary=rules.source_summary,
        questionnaire_dimensions=[
            QuestionnaireDimensionOut.model_validate(item.model_dump())
            for item in rules.questionnaire_dimensions
        ],
        experiments=[
            BehaviorExperimentOut(
                code=item.code,
                name=item.name,
                scenario=item.scenario,
                options=[
                    ExperimentOptionOut(code=option.code, label=option.label)
                    for option in item.options
                ],
            )
            for item in rules.experiments
        ],
        bias_definitions=[
            BiasDefinitionOut.model_validate(item.model_dump()) for item in rules.bias_definitions
        ],
        intervention_definitions=[
            InterventionDefinitionOut(
                code=item.code,
                name=item.name,
                trigger_biases=item.trigger_biases,
                scenario_code=item.scenario_code,
                action_instruction=item.action_instruction,
            )
            for item in rules.interventions
        ],
        ab_variants=[ABVariantOut.model_validate(item.model_dump()) for item in rules.ab_variants],
        behavior_boundary=("问卷与实验只用于解释和审慎下调；最终风险上限不得高于客观承担能力。"),
    )


def _latest_risk_assessment(session: Session, household_id: str) -> RiskAssessment | None:
    return session.scalar(
        select(RiskAssessment)
        .where(
            RiskAssessment.household_id == household_id,
            RiskAssessment.is_deleted.is_(False),
        )
        .order_by(RiskAssessment.created_at.desc(), RiskAssessment.id.desc())
    )


def _latest_behavior_assessment(
    session: Session,
    household_id: str,
) -> BehaviorAssessment | None:
    return session.scalar(
        select(BehaviorAssessment)
        .where(
            BehaviorAssessment.household_id == household_id,
            BehaviorAssessment.is_deleted.is_(False),
        )
        .order_by(BehaviorAssessment.created_at.desc(), BehaviorAssessment.id.desc())
    )


def _authorization_basis(session: Session, household: Household) -> str | None:
    if household.is_synthetic:
        return "synthetic_data"
    consents = session.scalars(
        select(ConsentRecord).where(
            ConsentRecord.household_id == household.id,
            ConsentRecord.is_deleted.is_(False),
            ConsentRecord.withdrawn_at.is_(None),
        )
    ).all()
    if any("behavior" in item.scopes or "risk" in item.scopes for item in consents):
        return "authorized_behavior_or_risk_scope"
    return None


def _require_authorization(session: Session, household: Household) -> str:
    basis = _authorization_basis(session, household)
    if basis is None:
        raise AppError(
            "behavior_experiment_not_authorized",
            "行为实验只允许使用合成数据或已有行为／风险授权的数据",
            status_code=403,
        )
    return basis


def _input_version(
    household: Household,
    risk: RiskAssessment,
    questionnaire: BehaviorQuestionnaireInput,
    rules: BehaviorRules,
) -> str:
    payload = {
        "household_id": household.id,
        "household_version": household.version,
        "risk_assessment_id": risk.id,
        "risk_assessment_version": risk.version,
        "questionnaire": questionnaire.model_dump(mode="json"),
        "rule_version": rules.semantic_version,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _assignment(
    session: Session,
    household: Household,
    experiment_key: str,
    rules: BehaviorRules,
) -> tuple[str, str]:
    sequence = (
        session.scalar(
            select(func.count())
            .select_from(BehaviorExperimentAssignment)
            .where(
                BehaviorExperimentAssignment.household_id == household.id,
                BehaviorExperimentAssignment.experiment_key == experiment_key,
            )
        )
        or 0
    )
    digest = hashlib.sha256(
        f"{household.id}:{experiment_key}:{rules.ab_framework_version}:{sequence}".encode()
    ).hexdigest()
    variant = rules.ab_variants[int(digest[:16], 16) % len(rules.ab_variants)]
    return variant.code, digest


def _variant_name(rules: BehaviorRules, code: str) -> str:
    return next(item.name for item in rules.ab_variants if item.code == code)


def _utc_datetime(value: datetime) -> datetime:
    """Normalize SQLite's timezone-naive DateTime values before comparisons."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _audit(
    session: Session,
    *,
    household_id: str,
    actor: ActorContext,
    event_type: AuditEventType,
    entity_type: str,
    entity_id: str,
    event_version: int,
    summary: str,
    evidence: dict[str, object],
    valuation_date: date | None,
) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        event_type=event_type,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type=entity_type,
        entity_id=entity_id,
        event_version=event_version,
        summary=summary,
        evidence=evidence,
        occurred_at=utc_now(),
        valuation_date=valuation_date,
        data_source="deterministic_behavior_engine",
        is_user_confirmed=True,
    )
    session.add(event)
    return event


def start_behavior_session(
    session: Session,
    household_id: str,
    request: StartBehaviorSessionRequest,
    actor: ActorContext,
    rules_path: str,
) -> BehaviorSessionOut:
    household = ensure_household(session, household_id)
    authorization = _require_authorization(session, household)
    active = session.scalar(
        select(BehaviorExperimentSession).where(
            BehaviorExperimentSession.household_id == household_id,
            BehaviorExperimentSession.status == BehaviorSessionStatus.ACTIVE,
            BehaviorExperimentSession.is_deleted.is_(False),
        )
    )
    if active is not None:
        raise AppError(
            "behavior_session_already_active",
            "该家庭已有进行中的行为实验",
            status_code=409,
            details={"session_id": active.id},
        )
    risk = _latest_risk_assessment(session, household_id)
    if risk is None:
        raise AppError(
            "behavior_capacity_missing",
            "缺少客观风险能力记录，不能开始行为实验",
            status_code=422,
        )
    rules = load_behavior_rules(rules_path)
    rule_version = ensure_behavior_rule_version(session, rules)
    q_score = questionnaire_score(request.questionnaire, rules)
    objective_limit = score_to_level(risk.capacity_score, rules)
    questionnaire_limit = score_to_level(q_score, rules)
    variant_code, assignment_hash = _assignment(
        session,
        household,
        request.experiment_key,
        rules,
    )
    now = utc_now()
    analysis_date = request.analysis_date or date.today()
    record = BehaviorExperimentSession(
        household_id=household_id,
        status=BehaviorSessionStatus.ACTIVE,
        questionnaire=request.questionnaire.model_dump(mode="json"),
        questionnaire_score=q_score,
        objective_capacity_limit=objective_limit,
        questionnaire_claim_limit=questionnaire_limit,
        information_status="collecting",
        assigned_variant=variant_code,
        experiment_key=request.experiment_key,
        consent_basis=authorization,
        summary={},
        input_version=_input_version(household, risk, request.questionnaire, rules),
        formula_version=rules.formula_version,
        experiment_version=rules.experiment_version,
        rule_version_id=rule_version.id,
        calculation_source="deterministic_behavior_engine",
        started_at=now,
        valuation_date=analysis_date,
        data_source="behavior_experiment",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    assignment = BehaviorExperimentAssignment(
        household_id=household_id,
        session_id=record.id,
        experiment_key=request.experiment_key,
        framework_version=rules.ab_framework_version,
        variant_code=variant_code,
        assignment_method="deterministic_hash",
        assignment_hash=assignment_hash,
        data_scope=authorization,
        eligible_data=True,
        assigned_at=now,
        valuation_date=analysis_date,
        data_source="behavior_ab_framework",
        is_user_confirmed=True,
    )
    session.add(assignment)
    _audit(
        session,
        household_id=household_id,
        actor=actor,
        event_type=AuditEventType.BEHAVIOR_SESSION_STARTED,
        entity_type="BehaviorExperimentSession",
        entity_id=record.id,
        event_version=record.version,
        summary="开始六项行为实验",
        evidence={
            "experiment_version": rules.experiment_version,
            "rule_version": rules.semantic_version,
            "variant_code": variant_code,
            "authorization_basis": authorization,
            "input_version": record.input_version,
        },
        valuation_date=analysis_date,
    )
    session.commit()
    return _session_out(session, record, rules)


def _get_session(
    session: Session,
    household_id: str,
    session_id: str,
) -> BehaviorExperimentSession:
    record = session.scalar(
        select(BehaviorExperimentSession).where(
            BehaviorExperimentSession.id == session_id,
            BehaviorExperimentSession.household_id == household_id,
            BehaviorExperimentSession.is_deleted.is_(False),
        )
    )
    if record is None:
        raise AppError(
            "behavior_session_not_found",
            "找不到行为实验会话",
            status_code=404,
        )
    return record


def _raw_responses(
    session: Session,
    session_record: BehaviorExperimentSession,
) -> list[RawResponse]:
    records = session.scalars(
        select(BehaviorExperimentResponse)
        .where(
            BehaviorExperimentResponse.session_id == session_record.id,
            BehaviorExperimentResponse.is_deleted.is_(False),
        )
        .order_by(BehaviorExperimentResponse.created_at, BehaviorExperimentResponse.id)
    ).all()
    return [
        RawResponse(
            response_id=item.id,
            experiment_code=item.experiment_code,
            choice_code=item.choice_code,
            response_time_ms=item.response_time_ms,
            modification_count=item.modification_count,
            answered_at=item.answered_at,
        )
        for item in records
    ]


def record_behavior_response(
    session: Session,
    household_id: str,
    session_id: str,
    experiment_code: str,
    request: RecordBehaviorResponseRequest,
    actor: ActorContext,
    rules_path: str,
) -> BehaviorSessionOut:
    session_record = _get_session(session, household_id, session_id)
    if session_record.status != BehaviorSessionStatus.ACTIVE:
        raise AppError(
            "behavior_session_closed",
            "已完成或已退出的会话不能修改答卷",
            status_code=409,
        )
    rules = load_behavior_rules(rules_path)
    try:
        experiment = experiment_rule(rules, experiment_code)
        option = option_rule(rules, experiment_code, request.choice_code)
    except StopIteration as exc:
        raise AppError(
            "behavior_response_invalid",
            "实验代码或选择不存在",
            status_code=422,
        ) from exc
    questionnaire = BehaviorQuestionnaireInput.model_validate(session_record.questionnaire)
    consistency = response_consistency(questionnaire, experiment, option)
    now = utc_now()
    record = session.scalar(
        select(BehaviorExperimentResponse).where(
            BehaviorExperimentResponse.session_id == session_id,
            BehaviorExperimentResponse.experiment_code == experiment_code,
            BehaviorExperimentResponse.is_deleted.is_(False),
        )
    )
    if record is None:
        record = BehaviorExperimentResponse(
            household_id=household_id,
            session_id=session_id,
            experiment_code=experiment_code,
            choice_code=request.choice_code,
            response_time_ms=request.response_time_ms,
            modification_count=request.modification_count,
            consistency_score=consistency,
            response_payload={"choice_code": request.choice_code},
            evidence={"choice_label": option.label, "observation": option.evidence},
            answered_at=now,
            valuation_date=session_record.valuation_date,
            data_source="behavior_experiment",
            is_user_confirmed=True,
        )
        session.add(record)
        session.flush()
    else:
        record.choice_code = request.choice_code
        record.response_time_ms = request.response_time_ms
        record.modification_count = max(
            request.modification_count,
            record.modification_count + 1,
        )
        record.consistency_score = consistency
        record.response_payload = {"choice_code": request.choice_code}
        record.evidence = {"choice_label": option.label, "observation": option.evidence}
        record.answered_at = now
        record.version += 1
        record.updated_at = now
    session_record.version += 1
    session_record.updated_at = now
    _audit(
        session,
        household_id=household_id,
        actor=actor,
        event_type=AuditEventType.BEHAVIOR_RESPONSE_RECORDED,
        entity_type="BehaviorExperimentResponse",
        entity_id=record.id,
        event_version=record.version,
        summary=f"记录行为实验选择：{experiment.name}",
        evidence={
            "session_id": session_id,
            "experiment_code": experiment_code,
            "choice_code": request.choice_code,
            "response_time_ms": request.response_time_ms,
            "modification_count": record.modification_count,
            "consistency_score": str(consistency),
        },
        valuation_date=session_record.valuation_date,
    )
    session.commit()
    return _session_out(session, session_record, rules)


def _risk_for_evaluation(
    session: Session,
    household_id: str,
) -> RiskAssessment:
    risk = _latest_risk_assessment(session, household_id)
    if risk is None:
        raise AppError(
            "behavior_capacity_missing",
            "缺少客观风险能力记录，无法完成双画像",
            status_code=422,
        )
    return risk


def _goals(session: Session, household_id: str) -> list[FinancialGoal]:
    return list(
        session.scalars(
            select(FinancialGoal)
            .where(
                FinancialGoal.household_id == household_id,
                FinancialGoal.is_deleted.is_(False),
            )
            .order_by(FinancialGoal.priority, FinancialGoal.target_date, FinancialGoal.id)
        ).all()
    )


def _intervention_drafts(
    evaluation: BehaviorEvaluation,
    household: Household,
    goals: list[FinancialGoal],
    assigned_variant: str,
    rules: BehaviorRules,
    *,
    starts_at: datetime | None,
) -> list[BehaviorInterventionOut]:
    bias_by_code = {item.code: item for item in evaluation.biases}
    catalog_order = {item.code: index for index, item in enumerate(rules.interventions)}
    candidates: list[tuple[Decimal, int, InterventionRule, list[str]]] = []
    for intervention in rules.interventions:
        triggers = [
            code
            for code in intervention.trigger_biases
            if bias_by_code[code].score > rules.bias_thresholds.low_max
        ]
        if triggers:
            priority = max(bias_by_code[code].score for code in triggers)
            if intervention.code == "cooling_period" and priority < rules.cooling_period_threshold:
                continue
            candidates.append((priority, catalog_order[intervention.code], intervention, triggers))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[: rules.maximum_selected_interventions]
    primary_goal = goals[0] if goals else None
    results: list[BehaviorInterventionOut] = []
    for priority, _, raw_rule, triggers in selected:
        intervention = raw_rule
        cooling_hours = None
        if intervention.code == "cooling_period":
            cooling_hours = (
                rules.high_cooling_hours
                if priority >= rules.high_cooling_period_threshold
                else rules.default_cooling_hours
            )
        bias_names = "、".join(bias_by_code[code].name for code in triggers)
        goal_name = primary_goal.name if primary_goal is not None else "最优先家庭目标"
        message = intervention.message_template.format(
            household_name=household.name,
            bias_names=bias_names,
            cooling_hours=cooling_hours or rules.default_cooling_hours,
            goal_name=goal_name,
        )
        if not any(name in message for name in (household.name, bias_names, goal_name)):
            message = f"根据{bias_names}证据，并结合{goal_name}：{message}"
        eligible_at = (
            starts_at + timedelta(hours=cooling_hours)
            if starts_at is not None and cooling_hours is not None
            else None
        )
        results.append(
            BehaviorInterventionOut(
                intervention_id=None,
                code=intervention.code,
                name=intervention.name,
                status=BehaviorInterventionStatus.ACTIVE,
                trigger_biases=triggers,
                scenario_code=intervention.scenario_code,
                linked_goal_id=primary_goal.id if primary_goal is not None else None,
                linked_goal_name=primary_goal.name if primary_goal is not None else None,
                personalized_message=message,
                action_instruction=intervention.action_instruction,
                cooling_period_hours=cooling_hours,
                starts_at=starts_at,
                eligible_at=eligible_at,
                completed_at=None,
                dismissed_at=None,
                assigned_variant=assigned_variant,
                audit_note=(
                    "预览；完成实验后才写入可审计干预记录。"
                    if starts_at is None
                    else "状态、起止时间、触发偏差与操作都会进入审计链。"
                ),
            )
        )
    return results


def _persist_interventions(
    session: Session,
    session_record: BehaviorExperimentSession,
    drafts: list[BehaviorInterventionOut],
    actor: ActorContext,
) -> list[BehaviorIntervention]:
    records: list[BehaviorIntervention] = []
    for draft in drafts:
        if draft.starts_at is None:
            raise ValueError("持久化干预必须有开始时间")
        record = BehaviorIntervention(
            household_id=session_record.household_id,
            session_id=session_record.id,
            linked_goal_id=draft.linked_goal_id,
            intervention_code=draft.code,
            name=draft.name,
            status=draft.status,
            trigger_biases=draft.trigger_biases,
            scenario_code=draft.scenario_code,
            personalized_message=draft.personalized_message,
            action_instruction=draft.action_instruction,
            cooling_period_hours=draft.cooling_period_hours,
            starts_at=draft.starts_at,
            eligible_at=draft.eligible_at,
            assigned_variant=draft.assigned_variant,
            evidence={
                "trigger_biases": draft.trigger_biases,
                "linked_goal_name": draft.linked_goal_name,
                "input_version": session_record.input_version,
            },
            valuation_date=session_record.valuation_date,
            data_source="deterministic_behavior_engine",
            is_user_confirmed=True,
        )
        session.add(record)
        session.flush()
        _audit(
            session,
            household_id=session_record.household_id,
            actor=actor,
            event_type=AuditEventType.BEHAVIOR_INTERVENTION_UPDATED,
            entity_type="BehaviorIntervention",
            entity_id=record.id,
            event_version=record.version,
            summary=f"创建个性化行为干预：{record.name}",
            evidence={
                "session_id": session_record.id,
                "intervention_code": record.intervention_code,
                "status": record.status.value,
                "cooling_period_hours": record.cooling_period_hours,
                "eligible_at": record.eligible_at.isoformat() if record.eligible_at else None,
                "trigger_biases": record.trigger_biases,
            },
            valuation_date=session_record.valuation_date,
        )
        records.append(record)
    return records


def complete_behavior_session(
    session: Session,
    household_id: str,
    session_id: str,
    actor: ActorContext,
    rules_path: str,
) -> BehaviorSessionOut:
    session_record = _get_session(session, household_id, session_id)
    if session_record.status != BehaviorSessionStatus.ACTIVE:
        raise AppError(
            "behavior_session_closed",
            "只有进行中的会话可以完成",
            status_code=409,
        )
    rules = load_behavior_rules(rules_path)
    raw_responses = _raw_responses(session, session_record)
    expected = {item.code for item in rules.experiments}
    actual = {item.experiment_code for item in raw_responses}
    if actual != expected or len(raw_responses) != len(expected):
        raise AppError(
            "behavior_experiments_incomplete",
            "必须完成全部六项行为实验后才能生成双画像",
            status_code=422,
            details={"remaining_experiment_codes": sorted(expected - actual)},
        )
    household = ensure_household(session, household_id)
    risk = _risk_for_evaluation(session, household_id)
    questionnaire = BehaviorQuestionnaireInput.model_validate(session_record.questionnaire)
    evaluation = evaluate_behavior(
        questionnaire,
        raw_responses,
        risk.capacity_score,
        risk.id,
        rules,
    )
    now = utc_now()
    detected = [item.code for item in evaluation.biases if item.severity != "low"]
    assessment = BehaviorAssessment(
        household_id=household_id,
        questionnaire_score=evaluation.questionnaire_score,
        experiment_score=evaluation.experiment_score,
        final_behavior_limit=evaluation.dual_profile.behavioral_limit_before_capacity,
        detected_biases=detected,
        experiment_answers={
            item.experiment_code: {
                "choice_code": item.choice_code,
                "response_time_ms": item.response_time_ms,
                "modification_count": item.modification_count,
                "consistency_score": str(item.consistency_score),
            }
            for item in evaluation.responses
        },
        explanation=evaluation.dual_profile.explanation,
        valuation_date=session_record.valuation_date,
        data_source="deterministic_behavior_engine",
        is_user_confirmed=True,
    )
    session.add(assessment)
    session.flush()
    for bias in evaluation.biases:
        session.add(
            BehaviorBiasFinding(
                household_id=household_id,
                session_id=session_record.id,
                bias_code=bias.code,
                name=bias.name,
                score=bias.score,
                severity=bias.severity,
                explanation=bias.explanation,
                evidence=[item.model_dump(mode="json") for item in bias.evidence],
                source_experiment_codes=sorted(
                    {
                        item.source.removeprefix("experiment.")
                        for item in bias.evidence
                        if item.source.startswith("experiment.")
                        and item.source
                        not in {
                            "experiment.no_signal",
                            "experiment.modification_count",
                        }
                    }
                ),
                valuation_date=session_record.valuation_date,
                data_source="deterministic_behavior_engine",
                is_user_confirmed=True,
            )
        )

    drafts = _intervention_drafts(
        evaluation,
        household,
        _goals(session, household_id),
        session_record.assigned_variant,
        rules,
        starts_at=now,
    )
    interventions = _persist_interventions(session, session_record, drafts, actor)
    session_record.assessment_id = assessment.id
    session_record.status = BehaviorSessionStatus.COMPLETED
    session_record.information_status = "sufficient"
    session_record.experiment_score = evaluation.experiment_score
    session_record.experiment_limit = evaluation.dual_profile.experiment_limit
    session_record.effective_risk_limit = evaluation.dual_profile.effective_risk_limit
    session_record.summary = {
        "risk_downshifted": evaluation.dual_profile.risk_downshifted,
        "conflict_detected": evaluation.dual_profile.conflict_detected,
        "conflict_codes": evaluation.dual_profile.conflict_codes,
        "behavioral_limit_before_capacity": (
            evaluation.dual_profile.behavioral_limit_before_capacity.value
        ),
        "effective_risk_limit": evaluation.dual_profile.effective_risk_limit.value,
        "average_response_time_ms": evaluation.average_response_time_ms,
        "total_modification_count": evaluation.total_modification_count,
        "overall_consistency_score": str(evaluation.overall_consistency_score),
        "bias_codes": detected,
        "intervention_ids": [item.id for item in interventions],
    }
    session_record.completed_at = now
    session_record.version += 1
    session_record.updated_at = now
    completion_event = _audit(
        session,
        household_id=household_id,
        actor=actor,
        event_type=AuditEventType.BEHAVIOR_ASSESSMENT_COMPLETED,
        entity_type="BehaviorExperimentSession",
        entity_id=session_record.id,
        event_version=session_record.version,
        summary="完成行为金融双画像与个性化干预",
        evidence={
            "assessment_id": assessment.id,
            "objective_capacity_limit": evaluation.dual_profile.objective_capacity_limit.value,
            "questionnaire_limit": evaluation.dual_profile.questionnaire_claim_limit.value,
            "experiment_limit": evaluation.dual_profile.experiment_limit.value,
            "effective_risk_limit": evaluation.dual_profile.effective_risk_limit.value,
            "risk_downshifted": evaluation.dual_profile.risk_downshifted,
            "conflict_codes": evaluation.dual_profile.conflict_codes,
            "bias_codes": detected,
            "intervention_ids": [item.id for item in interventions],
            "calculation_source": "deterministic_behavior_engine",
        },
        valuation_date=session_record.valuation_date,
    )
    session.flush()
    session_record.summary = {
        **session_record.summary,
        "completion_audit_event_id": completion_event.id,
    }
    session.commit()
    return _session_out(session, session_record, rules)


def exit_behavior_session(
    session: Session,
    household_id: str,
    session_id: str,
    actor: ActorContext,
) -> ExitBehaviorSessionResponse:
    record = _get_session(session, household_id, session_id)
    if record.status != BehaviorSessionStatus.ACTIVE:
        raise AppError(
            "behavior_session_closed",
            "只有进行中的行为实验可以退出",
            status_code=409,
        )
    now = utc_now()
    record.status = BehaviorSessionStatus.EXITED
    record.information_status = "exited"
    record.exited_at = now
    record.version += 1
    record.updated_at = now
    event = _audit(
        session,
        household_id=household_id,
        actor=actor,
        event_type=AuditEventType.BEHAVIOR_EXPERIMENT_EXITED,
        entity_type="BehaviorExperimentSession",
        entity_id=record.id,
        event_version=record.version,
        summary="用户退出行为实验",
        evidence={
            "answered_count": len(_raw_responses(session, record)),
            "profile_generated": False,
            "interventions_generated": False,
        },
        valuation_date=record.valuation_date,
    )
    session.flush()
    session.commit()
    return ExitBehaviorSessionResponse(
        session_id=record.id,
        exited_at=now,
        audit_event_id=event.id,
        message="已退出实验；未生成画像或干预，不影响既有客观风险能力记录。",
    )


def _response_outputs(
    raw_responses: list[RawResponse],
    questionnaire: BehaviorQuestionnaireInput,
    rules: BehaviorRules,
) -> list[BehaviorResponseOut]:
    outputs: list[BehaviorResponseOut] = []
    order = {item.code: index for index, item in enumerate(rules.experiments)}
    for raw in sorted(raw_responses, key=lambda item: order[item.experiment_code]):
        experiment = experiment_rule(rules, raw.experiment_code)
        option = option_rule(rules, raw.experiment_code, raw.choice_code)
        outputs.append(
            BehaviorResponseOut(
                response_id=raw.response_id,
                experiment_code=raw.experiment_code,
                choice_code=raw.choice_code,
                choice_label=option.label,
                response_time_ms=raw.response_time_ms,
                modification_count=raw.modification_count,
                consistency_score=response_consistency(questionnaire, experiment, option),
                answered_at=raw.answered_at,
                evidence=option.evidence,
            )
        )
    return outputs


def _intervention_out(
    record: BehaviorIntervention,
    goal_names: dict[str, str],
) -> BehaviorInterventionOut:
    return BehaviorInterventionOut(
        intervention_id=record.id,
        code=record.intervention_code,
        name=record.name,
        status=record.status,
        trigger_biases=record.trigger_biases,
        scenario_code=record.scenario_code,
        linked_goal_id=record.linked_goal_id,
        linked_goal_name=goal_names.get(record.linked_goal_id or ""),
        personalized_message=record.personalized_message,
        action_instruction=record.action_instruction,
        cooling_period_hours=record.cooling_period_hours,
        starts_at=record.starts_at,
        eligible_at=record.eligible_at,
        completed_at=record.completed_at,
        dismissed_at=record.dismissed_at,
        assigned_variant=record.assigned_variant,
        audit_note="状态、触发证据与每次操作均已持久化并写入审计事件。",
    )


def _profile(
    session: Session,
    household: Household,
    questionnaire: BehaviorQuestionnaireInput,
    raw_responses: list[RawResponse],
    assigned_variant: str,
    input_version: str,
    analysis_date: date,
    data_as_of: date,
    source: str,
    rules: BehaviorRules,
    persisted_session_id: str | None = None,
) -> BehaviorProfileOut:
    risk = _risk_for_evaluation(session, household.id)
    evaluation = evaluate_behavior(
        questionnaire,
        raw_responses,
        risk.capacity_score,
        risk.id,
        rules,
    )
    goals = _goals(session, household.id)
    if persisted_session_id is None:
        interventions = _intervention_drafts(
            evaluation,
            household,
            goals,
            assigned_variant,
            rules,
            starts_at=None,
        )
    else:
        intervention_records = session.scalars(
            select(BehaviorIntervention)
            .where(
                BehaviorIntervention.session_id == persisted_session_id,
                BehaviorIntervention.is_deleted.is_(False),
            )
            .order_by(BehaviorIntervention.created_at, BehaviorIntervention.id)
        ).all()
        goal_names = {item.id: item.name for item in goals}
        interventions = [_intervention_out(item, goal_names) for item in intervention_records]
    return BehaviorProfileOut(
        meta=BehaviorProfileMeta(
            household_id=household.id,
            household_code=household.code,
            household_name=household.name,
            analysis_date=analysis_date,
            data_as_of=data_as_of,
            source=source,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
            experiment_version=rules.experiment_version,
            input_version=input_version,
        ),
        dual_profile=evaluation.dual_profile,
        biases=evaluation.biases,
        interventions=interventions,
        responses=evaluation.responses,
        assigned_variant=assigned_variant,
        assigned_variant_name=_variant_name(rules, assigned_variant),
        average_response_time_ms=evaluation.average_response_time_ms,
        total_modification_count=evaluation.total_modification_count,
        overall_consistency_score=evaluation.overall_consistency_score,
        limitations=[
            "行为分数来自内部演示问卷和六项选择实验，不是监管评级、医学诊断或收益预测。",
            "反应时间受设备、阅读和无障碍工具影响，只作为辅助证据，不单独决定风险上限。",
            "行为结果只能维持或下调客观风险能力，不能把客户提升到更高风险等级。",
            "干预用于减少冲动决策，不保证收益或避免损失，也不自动执行交易。",
        ],
    )


def _completed_profile(
    session: Session,
    session_record: BehaviorExperimentSession,
    rules: BehaviorRules,
) -> BehaviorProfileOut:
    household = ensure_household(session, session_record.household_id)
    questionnaire = BehaviorQuestionnaireInput.model_validate(session_record.questionnaire)
    return _profile(
        session,
        household,
        questionnaire,
        _raw_responses(session, session_record),
        session_record.assigned_variant,
        session_record.input_version,
        session_record.valuation_date or date.today(),
        session_record.valuation_date or date.today(),
        "completed_session",
        rules,
        persisted_session_id=session_record.id,
    )


def _session_out(
    session: Session,
    record: BehaviorExperimentSession,
    rules: BehaviorRules,
) -> BehaviorSessionOut:
    raw = _raw_responses(session, record)
    questionnaire = BehaviorQuestionnaireInput.model_validate(record.questionnaire)
    answered = {item.experiment_code for item in raw}
    responses = _response_outputs(raw, questionnaire, rules)
    profile = (
        _completed_profile(session, record, rules)
        if record.status == BehaviorSessionStatus.COMPLETED
        else None
    )
    return BehaviorSessionOut(
        session_id=record.id,
        household_id=record.household_id,
        status=record.status,
        information_status=record.information_status,
        answered_count=len(raw),
        remaining_experiment_codes=[
            item.code for item in rules.experiments if item.code not in answered
        ],
        assigned_variant=record.assigned_variant,
        assigned_variant_name=_variant_name(rules, record.assigned_variant),
        experiment_key=record.experiment_key,
        questionnaire_score=record.questionnaire_score,
        questionnaire_claim_limit=record.questionnaire_claim_limit,
        objective_capacity_limit=record.objective_capacity_limit,
        effective_risk_limit=record.effective_risk_limit,
        started_at=record.started_at,
        completed_at=record.completed_at,
        exited_at=record.exited_at,
        responses=responses,
        profile=profile,
    )


def get_behavior_session(
    session: Session,
    household_id: str,
    session_id: str,
    rules_path: str,
) -> BehaviorSessionOut:
    return _session_out(
        session,
        _get_session(session, household_id, session_id),
        load_behavior_rules(rules_path),
    )


def _legacy_profile(
    session: Session,
    household: Household,
    assessment: BehaviorAssessment,
    rules: BehaviorRules,
) -> BehaviorProfileOut | None:
    raw_payload = assessment.experiment_answers
    questionnaire_payload = raw_payload.get("questionnaire")
    responses_payload = raw_payload.get("responses")
    if not isinstance(questionnaire_payload, dict) or not isinstance(responses_payload, dict):
        return None
    try:
        questionnaire = BehaviorQuestionnaireInput.model_validate(questionnaire_payload)
        raw: list[RawResponse] = []
        for experiment in rules.experiments:
            payload = responses_payload[experiment.code]
            raw.append(
                RawResponse(
                    response_id=f"synthetic-{assessment.id[:8]}-{experiment.code}",
                    experiment_code=experiment.code,
                    choice_code=str(payload["choice_code"]),
                    response_time_ms=int(payload["response_time_ms"]),
                    modification_count=int(payload["modification_count"]),
                    answered_at=assessment.updated_at,
                )
            )
        input_payload = {
            "assessment_id": assessment.id,
            "assessment_version": assessment.version,
            "questionnaire": questionnaire.model_dump(mode="json"),
            "responses": responses_payload,
            "rule_version": rules.semantic_version,
        }
        input_version = hashlib.sha256(
            json.dumps(input_payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        variants = [item.code for item in rules.ab_variants]
        assigned_variant = variants[
            int(hashlib.sha256(household.code.encode()).hexdigest()[:16], 16) % len(variants)
        ]
        return _profile(
            session,
            household,
            questionnaire,
            raw,
            assigned_variant,
            input_version,
            assessment.valuation_date or date.today(),
            assessment.valuation_date or date.today(),
            "synthetic_behavior_input",
            rules,
        )
    except (KeyError, TypeError, ValueError):
        return None


def behavior_overview(
    session: Session,
    household_id: str,
    rules_path: str,
) -> BehaviorOverviewResponse:
    household = ensure_household(session, household_id)
    rules = load_behavior_rules(rules_path)
    authorization = _authorization_basis(session, household)
    latest_session = session.scalar(
        select(BehaviorExperimentSession)
        .where(
            BehaviorExperimentSession.household_id == household_id,
            BehaviorExperimentSession.data_source != "v5_monitoring_engine",
            BehaviorExperimentSession.is_deleted.is_(False),
        )
        .order_by(
            BehaviorExperimentSession.created_at.desc(),
            BehaviorExperimentSession.id.desc(),
        )
    )
    session_out = _session_out(session, latest_session, rules) if latest_session else None
    profile = session_out.profile if session_out else None
    if profile is None:
        legacy = _latest_behavior_assessment(session, household_id)
        if legacy is not None:
            profile = _legacy_profile(session, household, legacy, rules)
    sufficient = profile is not None
    active = latest_session is not None and latest_session.status == BehaviorSessionStatus.ACTIVE
    return BehaviorOverviewResponse(
        household_id=household_id,
        information_status="sufficient" if sufficient else "insufficient",
        information_message=(
            "已获得完整问卷与六项实验，可展示双画像、十一项偏差证据和个性化干预。"
            if sufficient
            else "行为信息不足：必须完成七维问卷与全部六项实验；系统不会据此提高风险等级。"
        ),
        profile=profile,
        latest_session=session_out,
        can_start_experiment=authorization is not None and not active,
        authorization_basis=authorization,
        limitations=[
            "仅处理合成或已授权测试数据。",
            "缺少行为数据时明确标记信息不足，不用家庭财务数据猜测人格或偏差。",
        ],
    )


def update_intervention(
    session: Session,
    household_id: str,
    intervention_id: str,
    request: InterventionActionRequest,
    actor: ActorContext,
) -> BehaviorInterventionOut:
    record = session.scalar(
        select(BehaviorIntervention).where(
            BehaviorIntervention.id == intervention_id,
            BehaviorIntervention.household_id == household_id,
            BehaviorIntervention.is_deleted.is_(False),
        )
    )
    if record is None:
        raise AppError(
            "behavior_intervention_not_found",
            "找不到行为干预记录",
            status_code=404,
        )
    if record.status != BehaviorInterventionStatus.ACTIVE:
        raise AppError(
            "behavior_intervention_closed",
            "该干预已经完成或忽略，不能重复操作",
            status_code=409,
        )
    now = utc_now()
    if request.action == "complete":
        if record.eligible_at is not None and now < _utc_datetime(record.eligible_at):
            raise AppError(
                "behavior_cooling_period_active",
                "冷静期尚未结束，当前不能标记完成",
                status_code=409,
                details={"eligible_at": record.eligible_at.isoformat()},
            )
        record.status = BehaviorInterventionStatus.COMPLETED
        record.completed_at = now
    else:
        record.status = BehaviorInterventionStatus.DISMISSED
        record.dismissed_at = now
    record.version += 1
    record.updated_at = now
    event = _audit(
        session,
        household_id=household_id,
        actor=actor,
        event_type=AuditEventType.BEHAVIOR_INTERVENTION_UPDATED,
        entity_type="BehaviorIntervention",
        entity_id=record.id,
        event_version=record.version,
        summary=f"行为干预状态更新为 {record.status.value}",
        evidence={
            "intervention_code": record.intervention_code,
            "status": record.status.value,
            "reason_code": request.reason_code,
            "cooling_period_hours": record.cooling_period_hours,
            "starts_at": record.starts_at.isoformat(),
            "eligible_at": record.eligible_at.isoformat() if record.eligible_at else None,
            "acted_at": now.isoformat(),
        },
        valuation_date=record.valuation_date,
    )
    session.flush()
    record.evidence = {**record.evidence, "latest_audit_event_id": event.id}
    session.commit()
    goal_names = {item.id: item.name for item in _goals(session, household_id)}
    return _intervention_out(record, goal_names)


def behavior_ab_framework(
    session: Session,
    experiment_key: str,
    rules_path: str,
) -> BehaviorABFrameworkResponse:
    rules = load_behavior_rules(rules_path)
    assignments = session.scalars(
        select(BehaviorExperimentAssignment).where(
            BehaviorExperimentAssignment.experiment_key == experiment_key,
            BehaviorExperimentAssignment.eligible_data.is_(True),
            BehaviorExperimentAssignment.is_deleted.is_(False),
        )
    ).all()
    session_ids = [item.session_id for item in assignments]
    sessions = (
        session.scalars(
            select(BehaviorExperimentSession).where(
                BehaviorExperimentSession.id.in_(session_ids),
                BehaviorExperimentSession.is_deleted.is_(False),
            )
        ).all()
        if session_ids
        else []
    )
    session_by_id = {item.id: item for item in sessions}
    responses = (
        session.scalars(
            select(BehaviorExperimentResponse).where(
                BehaviorExperimentResponse.session_id.in_(session_ids),
                BehaviorExperimentResponse.is_deleted.is_(False),
            )
        ).all()
        if session_ids
        else []
    )
    interventions = (
        session.scalars(
            select(BehaviorIntervention).where(
                BehaviorIntervention.session_id.in_(session_ids),
                BehaviorIntervention.is_deleted.is_(False),
            )
        ).all()
        if session_ids
        else []
    )
    metrics: list[ABVariantMetricOut] = []
    for variant in rules.ab_variants:
        variant_assignments = [item for item in assignments if item.variant_code == variant.code]
        variant_sessions = [
            session_by_id[item.session_id]
            for item in variant_assignments
            if item.session_id in session_by_id
        ]
        ids = {item.id for item in variant_sessions}
        variant_responses = [item for item in responses if item.session_id in ids]
        completed = sum(item.status == BehaviorSessionStatus.COMPLETED for item in variant_sessions)
        exited = sum(item.status == BehaviorSessionStatus.EXITED for item in variant_sessions)
        assigned = len(variant_assignments)
        completion_rate = q6(Decimal(completed) / Decimal(assigned)) if assigned else None
        average_time = (
            round(sum(item.response_time_ms for item in variant_responses) / len(variant_responses))
            if variant_responses
            else None
        )
        metrics.append(
            ABVariantMetricOut(
                variant_code=variant.code,
                variant_name=variant.name,
                assigned_count=assigned,
                completed_count=completed,
                exited_count=exited,
                completion_rate=completion_rate,
                average_response_time_ms=average_time,
                risk_downshift_count=sum(
                    bool(item.summary.get("risk_downshifted")) for item in variant_sessions
                ),
                intervention_completed_count=sum(
                    item.status == BehaviorInterventionStatus.COMPLETED
                    for item in interventions
                    if item.session_id in ids
                ),
            )
        )
    return BehaviorABFrameworkResponse(
        framework_version=rules.ab_framework_version,
        experiment_key=experiment_key,
        eligible_data_policy="仅统计 eligible_data=true 的合成或明确授权测试会话",
        variants=[ABVariantOut.model_validate(item.model_dump()) for item in rules.ab_variants],
        metrics=metrics,
        metric_definitions={
            "completion_rate": "完成会话数 ÷ 分配会话数",
            "average_response_time_ms": "该组已记录六项实验响应时间的算术平均值",
            "risk_downshift_count": "最终风险上限低于客观能力上限的完成会话数",
            "intervention_completed_count": "已过冷静期并由用户完成的干预记录数",
        },
        privacy_note="不统计未授权真实数据；指标为产品实验信号，不代表投资收益或干预因果效果。",
    )
