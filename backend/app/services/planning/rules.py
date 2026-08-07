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
from app.models.governance import RuleVersion


class LifecycleRules(BaseModel):
    base_safety_months: dict[str, str]
    retirement_preparation_years: int = Field(ge=1, le=20)
    retirement_default_age: int = Field(ge=45, le=75)


class SafetyMonthRules(BaseModel):
    minimum: str
    maximum: str
    single_income_adjustment: str
    dual_income_adjustment: str
    high_stability_adjustment: str
    medium_stability_adjustment: str
    low_stability_adjustment: str
    medium_volatility_adjustment: str
    high_volatility_adjustment: str
    mortgage_adjustment: str
    dependent_child_adjustment: str
    family_support_adjustment: str
    medium_health_adjustment: str
    high_health_adjustment: str
    daily_operating_months: str
    daily_operating_min_amount: str
    daily_operating_max_amount: str


class GoalRules(BaseModel):
    present_value_discount_rate: str
    short_term_months: int = Field(ge=1, le=24)
    stable_goal_months: int = Field(ge=12, le=120)
    default_deferral_months: int = Field(ge=1, le=60)
    conflict_warning_ratio: str


class MarketRegimeProfile(BaseModel):
    label: str
    stable_reference_min: Decimal = Field(ge=0, le=1)
    stable_target_ratio: Decimal = Field(ge=0, le=1)
    stable_reference_max: Decimal = Field(ge=0, le=1)
    explanation: str

    @model_validator(mode="after")
    def validate_band(self) -> MarketRegimeProfile:
        if not (
            self.stable_reference_min
            <= self.stable_target_ratio
            <= self.stable_reference_max
        ):
            raise ValueError("市场环境参考带必须满足 minimum <= target <= maximum")
        return self


class MarketEnvironmentRules(BaseModel):
    active_regime: Literal["favorable", "neutral", "defensive"]
    governance_note: str
    profiles: dict[
        Literal["favorable", "neutral", "defensive"],
        MarketRegimeProfile,
    ]

    @model_validator(mode="after")
    def validate_profiles(self) -> MarketEnvironmentRules:
        required = {"favorable", "neutral", "defensive"}
        if set(self.profiles) != required:
            raise ValueError("市场环境规则必须完整包含 favorable、neutral、defensive")
        return self


class WaterfallRules(BaseModel):
    debt_buffer_months: str
    protection_coverage_pass_ratio: str
    hard_constraint_growth_cap: str
    learning_growth_cap: str
    growth_70_threshold: str
    stable_reference_denominator: Literal["investable_financial_assets"]
    growth_entry_default: str
    growth_entry_minimum: str
    growth_entry_maximum: str
    behavior_growth_factors: dict[str, str]
    suitability_pass_levels: list[str]


class PlanningRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    lifecycle: LifecycleRules
    safety_months: SafetyMonthRules
    goals: GoalRules
    market_environment: MarketEnvironmentRules
    waterfall: WaterfallRules
    product_education: dict[str, list[str]]


def resolve_planning_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/planning_waterfall_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "planning_rules_missing",
        "找不到目标与四账户规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_planning_rules(configured_path: str) -> PlanningRules:
    path = resolve_planning_rules_path(configured_path)
    try:
        return PlanningRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "planning_rules_invalid",
            "目标与四账户规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_planning_rule_version(session: Session, rules: PlanningRules) -> RuleVersion:
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
