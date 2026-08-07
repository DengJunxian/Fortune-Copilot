from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import RiskLevel
from app.models.governance import RuleVersion
from app.schemas.records import Ratio

REQUIRED_BIASES = {
    "loss_aversion",
    "overconfidence",
    "herding",
    "recency_bias",
    "disposition_effect",
    "anchoring",
    "familiarity_bias",
    "mental_accounting",
    "present_bias",
    "performance_chasing",
    "frequent_trading_tendency",
}

REQUIRED_EXPERIMENTS = {
    "market_up_20",
    "market_down_10",
    "market_down_30",
    "hot_product_choice",
    "winner_loser_disposal",
    "consume_or_goal",
}

REQUIRED_VARIANTS = {
    "ordinary_prompt",
    "personalized_prompt",
    "twin_loss_simulation",
    "cooling_goal_reminder",
}


class QuestionnaireDimensionRule(BaseModel):
    code: str
    name: str
    prompt: str
    low_label: str
    high_label: str
    weight: Ratio


class ExperimentOptionRule(BaseModel):
    code: str
    label: str
    behavior_score: Ratio
    bias_impacts: dict[str, Ratio]
    evidence: str


class BehaviorExperimentRule(BaseModel):
    code: str
    name: str
    scenario: str
    consistency_dimension: str
    options: list[ExperimentOptionRule] = Field(min_length=2)


class BiasDefinitionRule(BaseModel):
    code: str
    name: str
    description: str


class BiasThresholdRules(BaseModel):
    low_max: Ratio
    watch_max: Ratio


class InterventionRule(BaseModel):
    code: str
    name: str
    trigger_biases: list[str] = Field(min_length=1)
    scenario_code: str
    message_template: str
    action_instruction: str


class ABVariantRule(BaseModel):
    code: str
    name: str
    description: str


class BehaviorRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    experiment_version: str
    ab_framework_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    risk_level_order: list[RiskLevel]
    score_thresholds: dict[RiskLevel, Ratio]
    questionnaire_dimensions: list[QuestionnaireDimensionRule] = Field(min_length=7)
    experiments: list[BehaviorExperimentRule] = Field(min_length=6)
    bias_definitions: list[BiasDefinitionRule] = Field(min_length=11)
    bias_thresholds: BiasThresholdRules
    interventions: list[InterventionRule] = Field(min_length=12)
    ab_variants: list[ABVariantRule] = Field(min_length=4)
    maximum_selected_interventions: int = Field(ge=1, le=12)
    cooling_period_threshold: Ratio
    high_cooling_period_threshold: Ratio
    default_cooling_hours: Literal[24]
    high_cooling_hours: Literal[48]

    @model_validator(mode="after")
    def validate_complete_policy(self) -> BehaviorRules:
        if self.risk_level_order != list(RiskLevel):
            raise ValueError("行为风险等级顺序必须覆盖 LOW 到 HIGH")
        if set(self.score_thresholds) != set(RiskLevel):
            raise ValueError("行为分数阈值必须覆盖五个风险等级")
        ordered_thresholds = [self.score_thresholds[item] for item in self.risk_level_order]
        if ordered_thresholds != sorted(ordered_thresholds) or ordered_thresholds[-1] != 1:
            raise ValueError("行为风险等级阈值必须递增并以 1 结束")
        dimension_codes = [item.code for item in self.questionnaire_dimensions]
        if len(dimension_codes) != len(set(dimension_codes)):
            raise ValueError("行为问卷维度代码不能重复")
        if sum((item.weight for item in self.questionnaire_dimensions), Decimal("0")) != 1:
            raise ValueError("行为问卷维度权重之和必须为 1")
        experiment_codes = [item.code for item in self.experiments]
        if set(experiment_codes) != REQUIRED_EXPERIMENTS:
            raise ValueError("行为实验必须且只能覆盖提示词要求的六项")
        if len(experiment_codes) != len(set(experiment_codes)):
            raise ValueError("行为实验代码不能重复")
        if {item.code for item in self.bias_definitions} != REQUIRED_BIASES:
            raise ValueError("偏差定义必须覆盖十一项要求")
        if {item.code for item in self.ab_variants} != REQUIRED_VARIANTS:
            raise ValueError("A/B 变体必须覆盖四类要求")
        if len({item.code for item in self.interventions}) != len(self.interventions):
            raise ValueError("行为干预代码不能重复")
        if self.bias_thresholds.low_max >= self.bias_thresholds.watch_max:
            raise ValueError("偏差严重度阈值顺序无效")
        if self.cooling_period_threshold >= self.high_cooling_period_threshold:
            raise ValueError("冷静期阈值顺序无效")
        dimensions = set(dimension_codes)
        for experiment in self.experiments:
            if experiment.consistency_dimension not in dimensions:
                raise ValueError(f"实验 {experiment.code} 的一致性维度不存在")
            option_codes = [item.code for item in experiment.options]
            if len(option_codes) != len(set(option_codes)):
                raise ValueError(f"实验 {experiment.code} 的选项代码重复")
            for option in experiment.options:
                unknown = set(option.bias_impacts) - REQUIRED_BIASES
                if unknown:
                    raise ValueError(f"实验 {experiment.code} 引用了未知偏差")
        for intervention in self.interventions:
            if set(intervention.trigger_biases) - REQUIRED_BIASES:
                raise ValueError(f"干预 {intervention.code} 引用了未知偏差")
        return self


def resolve_behavior_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/behavior_finance_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "behavior_rules_missing",
        "找不到行为金融规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_behavior_rules(configured_path: str) -> BehaviorRules:
    path = resolve_behavior_rules_path(configured_path)
    try:
        return BehaviorRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "behavior_rules_invalid",
            "行为金融规则未通过完整性校验",
            status_code=500,
        ) from exc


def ensure_behavior_rule_version(session: Session, rules: BehaviorRules) -> RuleVersion:
    existing = session.scalar(
        select(RuleVersion).where(
            RuleVersion.code == rules.code,
            RuleVersion.semantic_version == rules.semantic_version,
            RuleVersion.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    record = RuleVersion(
        code=rules.code,
        semantic_version=rules.semantic_version,
        effective_from=rules.effective_from,
        effective_to=rules.effective_to,
        rules=rules.model_dump(mode="json"),
        source_summary=rules.source_summary,
        valuation_date=rules.effective_from,
        data_source="wealthtwin-controlled-rule",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    return record
