from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import RiskLevel
from app.schemas.behavior import (
    BehaviorQuestionnaireInput,
    BehaviorResponseOut,
    BiasEvidenceOut,
    BiasScoreOut,
    DualProfileOut,
)
from app.services.behavior.rules import (
    BehaviorExperimentRule,
    BehaviorRules,
    ExperimentOptionRule,
)

Q6 = Decimal("0.000001")
ZERO = Decimal("0")
ONE = Decimal("1")


def q6(value: Decimal) -> Decimal:
    return min(ONE, max(ZERO, value)).quantize(Q6, rounding=ROUND_HALF_UP)


def score_to_level(score: Decimal, rules: BehaviorRules) -> RiskLevel:
    for level in rules.risk_level_order:
        if score <= rules.score_thresholds[level]:
            return level
    return RiskLevel.HIGH


def prudent_min(*levels: RiskLevel, rules: BehaviorRules) -> RiskLevel:
    return min(levels, key=rules.risk_level_order.index)


def questionnaire_score(
    questionnaire: BehaviorQuestionnaireInput,
    rules: BehaviorRules,
) -> Decimal:
    values = questionnaire.model_dump(mode="python")
    result = sum(
        (Decimal(values[item.code]) * item.weight for item in rules.questionnaire_dimensions),
        ZERO,
    )
    return q6(result)


def experiment_rule(rules: BehaviorRules, code: str) -> BehaviorExperimentRule:
    return next(item for item in rules.experiments if item.code == code)


def option_rule(
    rules: BehaviorRules,
    experiment_code: str,
    choice_code: str,
) -> ExperimentOptionRule:
    experiment = experiment_rule(rules, experiment_code)
    return next(item for item in experiment.options if item.code == choice_code)


def response_consistency(
    questionnaire: BehaviorQuestionnaireInput,
    experiment: BehaviorExperimentRule,
    option: ExperimentOptionRule,
) -> Decimal:
    claimed = Decimal(getattr(questionnaire, experiment.consistency_dimension))
    return q6(ONE - abs(claimed - option.behavior_score))


@dataclass(frozen=True, slots=True)
class RawResponse:
    response_id: str
    experiment_code: str
    choice_code: str
    response_time_ms: int
    modification_count: int
    answered_at: datetime


@dataclass(frozen=True, slots=True)
class BehaviorEvaluation:
    responses: list[BehaviorResponseOut]
    questionnaire_score: Decimal
    experiment_score: Decimal
    overall_consistency_score: Decimal
    average_response_time_ms: int
    total_modification_count: int
    dual_profile: DualProfileOut
    biases: list[BiasScoreOut]


def _evidence(
    source: str,
    source_label: str,
    observation: str,
    contribution: Decimal,
) -> BiasEvidenceOut:
    return BiasEvidenceOut(
        source=source,
        source_label=source_label,
        observation=observation,
        contribution=q6(contribution),
    )


def _questionnaire_bias_evidence(
    questionnaire: BehaviorQuestionnaireInput,
) -> dict[str, list[BiasEvidenceOut]]:
    unwilling_loss = q6(ONE - questionnaire.loss_tolerance_claim)
    attention_pull = q6(ONE - questionnaire.attention)
    weak_goal_discipline = q6(ONE - questionnaire.goal_discipline)
    active_trading = q6(ONE - questionnaire.trading_frequency)
    confidence_gap = q6(
        max(
            ZERO,
            questionnaire.investment_experience - questionnaire.knowledge,
            questionnaire.risk_willingness - questionnaire.knowledge,
        )
    )
    return {
        "loss_aversion": [
            _evidence(
                "questionnaire.loss_tolerance_claim",
                "自述损失承受",
                "分数越低，短期损失带来的退出压力越强。",
                unwilling_loss,
            )
        ],
        "overconfidence": [
            _evidence(
                "questionnaire.confidence_knowledge_gap",
                "经验／意愿与知识差",
                "经验或风险意愿高于知识时记录审慎差值。",
                confidence_gap,
            )
        ],
        "herding": [
            _evidence(
                "questionnaire.attention",
                "注意力稳定",
                "注意力越容易被热榜牵动，从众风险越高。",
                attention_pull * Decimal("0.60"),
            )
        ],
        "recency_bias": [
            _evidence(
                "questionnaire.attention",
                "注意力稳定",
                "短期行情占用注意力会放大近期偏差。",
                attention_pull * Decimal("0.70"),
            )
        ],
        "mental_accounting": [
            _evidence(
                "questionnaire.goal_discipline",
                "目标纪律",
                "目标纪律不足时更容易割裂一次性收入与家庭目标。",
                weak_goal_discipline * Decimal("0.60"),
            )
        ],
        "present_bias": [
            _evidence(
                "questionnaire.goal_discipline",
                "目标纪律",
                "目标纪律不足时即时消费权重上升。",
                weak_goal_discipline,
            )
        ],
        "frequent_trading_tendency": [
            _evidence(
                "questionnaire.trading_frequency",
                "交易克制度",
                "分数越低，临时高频操作倾向越强。",
                active_trading,
            )
        ],
    }


def _bias_scores(
    questionnaire: BehaviorQuestionnaireInput,
    scored: list[tuple[RawResponse, BehaviorExperimentRule, ExperimentOptionRule]],
    rules: BehaviorRules,
) -> list[BiasScoreOut]:
    evidence_by_bias = _questionnaire_bias_evidence(questionnaire)
    total_modifications = sum(item[0].modification_count for item in scored)
    if total_modifications:
        evidence_by_bias.setdefault("frequent_trading_tendency", []).append(
            _evidence(
                "experiment.modification_count",
                "选择修改次数",
                f"六项实验合计修改 {total_modifications} 次。",
                min(ONE, Decimal(total_modifications) / Decimal("12")),
            )
        )
    for _raw, experiment, option in scored:
        for bias_code, contribution in option.bias_impacts.items():
            evidence_by_bias.setdefault(bias_code, []).append(
                _evidence(
                    f"experiment.{experiment.code}",
                    experiment.name,
                    f"选择“{option.label}”：{option.evidence}",
                    contribution,
                )
            )

    results: list[BiasScoreOut] = []
    for definition in rules.bias_definitions:
        evidence = evidence_by_bias.get(definition.code, [])
        if not evidence:
            evidence = [
                _evidence(
                    "experiment.no_signal",
                    "本次问卷与实验",
                    "未观察到可计分证据；这不等于确认不存在该偏差。",
                    ZERO,
                )
            ]
        score = max(item.contribution for item in evidence)
        if score <= rules.bias_thresholds.low_max:
            severity = "low"
        elif score <= rules.bias_thresholds.watch_max:
            severity = "watch"
        else:
            severity = "high"
        strongest = max(evidence, key=lambda item: item.contribution)
        results.append(
            BiasScoreOut(
                code=definition.code,
                name=definition.name,
                description=definition.description,
                score=score,
                severity=severity,
                evidence=evidence,
                explanation=(
                    f"最高计分证据来自“{strongest.source_label}”；"
                    "该分数只用于干预与审慎下调，不是临床诊断或监管评级。"
                ),
            )
        )
    return results


def evaluate_behavior(
    questionnaire: BehaviorQuestionnaireInput,
    raw_responses: list[RawResponse],
    objective_capacity_score: Decimal,
    capacity_source_record_id: str,
    rules: BehaviorRules,
) -> BehaviorEvaluation:
    expected = {item.code for item in rules.experiments}
    actual = {item.experiment_code for item in raw_responses}
    if actual != expected or len(raw_responses) != len(expected):
        raise ValueError("行为评估必须恰好包含六项实验的完整答卷")

    scored: list[tuple[RawResponse, BehaviorExperimentRule, ExperimentOptionRule]] = []
    response_outputs: list[BehaviorResponseOut] = []
    for experiment in rules.experiments:
        raw = next(item for item in raw_responses if item.experiment_code == experiment.code)
        option = option_rule(rules, experiment.code, raw.choice_code)
        consistency = response_consistency(questionnaire, experiment, option)
        scored.append((raw, experiment, option))
        response_outputs.append(
            BehaviorResponseOut(
                response_id=raw.response_id,
                experiment_code=experiment.code,
                choice_code=option.code,
                choice_label=option.label,
                response_time_ms=raw.response_time_ms,
                modification_count=raw.modification_count,
                consistency_score=consistency,
                answered_at=raw.answered_at,
                evidence=option.evidence,
            )
        )

    q_score = questionnaire_score(questionnaire, rules)
    mean_behavior = sum((item[2].behavior_score for item in scored), ZERO) / Decimal(len(scored))
    overall_consistency = q6(
        sum((item.consistency_score for item in response_outputs), ZERO)
        / Decimal(len(response_outputs))
    )
    experiment_score = q6(mean_behavior * Decimal("0.80") + overall_consistency * Decimal("0.20"))
    questionnaire_limit = score_to_level(q_score, rules)
    experiment_limit = score_to_level(experiment_score, rules)
    objective_capacity_limit = score_to_level(objective_capacity_score, rules)

    choices = {item.experiment_code: item.choice_code for item in raw_responses}
    conflicts: list[str] = []
    if (
        questionnaire.loss_tolerance_claim >= Decimal("0.70")
        and choices["market_down_10"] == "sell_all"
    ):
        conflicts.append("claimed_30_percent_but_sold_at_10_percent")
        experiment_limit = prudent_min(experiment_limit, RiskLevel.LOW, rules=rules)
    if choices["market_up_20"] == "chase_add" and choices["market_down_10"] in {
        "reduce_some",
        "sell_all",
    }:
        conflicts.append("buy_after_rise_sell_after_fall")
        experiment_limit = prudent_min(experiment_limit, RiskLevel.MEDIUM_LOW, rules=rules)
    if questionnaire.knowledge >= Decimal("0.70") and (
        choices["hot_product_choice"] == "chase_hot"
        or choices["winner_loser_disposal"] != "rebalance_by_target"
    ):
        conflicts.append("knowledge_action_gap")
        experiment_limit = prudent_min(experiment_limit, RiskLevel.MEDIUM_LOW, rules=rules)

    behavioral_limit = prudent_min(questionnaire_limit, experiment_limit, rules=rules)
    effective_limit = prudent_min(objective_capacity_limit, behavioral_limit, rules=rules)
    risk_downshifted = rules.risk_level_order.index(effective_limit) < rules.risk_level_order.index(
        objective_capacity_limit
    )
    conflict_text = (
        "问卷与真实选择存在冲突，实验行为触发更保守上限。"
        if conflicts
        else "问卷与实验未命中强制冲突规则，仍按各维度审慎下限处理。"
    )
    dual_profile = DualProfileOut(
        objective_capacity_score=q6(objective_capacity_score),
        objective_capacity_limit=objective_capacity_limit,
        questionnaire_score=q_score,
        questionnaire_claim_limit=questionnaire_limit,
        experiment_score=experiment_score,
        experiment_limit=experiment_limit,
        behavioral_limit_before_capacity=behavioral_limit,
        effective_risk_limit=effective_limit,
        risk_downshifted=risk_downshifted,
        conflict_detected=bool(conflicts),
        conflict_codes=conflicts,
        explanation=(
            f"{conflict_text} 最终上限取客观能力 {objective_capacity_limit.value}、"
            f"问卷 {questionnaire_limit.value} 与实验 {experiment_limit.value} 的最低等级"
            f" {effective_limit.value}；行为结果不能提高客观能力。"
        ),
        capacity_source_record_id=capacity_source_record_id,
    )
    biases = _bias_scores(questionnaire, scored, rules)
    average_response_time = round(
        sum(item.response_time_ms for item in raw_responses) / len(raw_responses)
    )
    return BehaviorEvaluation(
        responses=response_outputs,
        questionnaire_score=q_score,
        experiment_score=experiment_score,
        overall_consistency_score=overall_consistency,
        average_response_time_ms=average_response_time,
        total_modification_count=sum(item.modification_count for item in raw_responses),
        dual_profile=dual_profile,
        biases=biases,
    )
