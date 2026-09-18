from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import RiskLevel, WealthNeedType
from app.models.governance import RuleVersion
from app.schemas.records import Money, Ratio


class WealthTierRules(BaseModel):
    emerging_affluent_minimum: Money
    affluent_minimum: Money
    high_net_worth_minimum: Money


class TagThresholdRules(BaseModel):
    young_worker_max_age: int = Field(ge=18, le=50)
    high_income_annual_amount: Money
    income_stability_watch_below: Ratio
    income_concentration_watch_above: Ratio
    property_concentration_watch_above: Ratio
    single_security_concentration_watch_above: Ratio
    family_complexity_member_count: int = Field(ge=2, le=20)
    cross_border_currency_count: int = Field(ge=2, le=10)
    succession_watch_net_worth: Money
    succession_high_net_worth: Money
    professional_occupation_keywords: list[str] = Field(min_length=1)
    founder_occupation_keywords: list[str] = Field(min_length=1)
    scientist_occupation_keywords: list[str] = Field(min_length=1)


class ServiceComplexityRules(BaseModel):
    enhanced_score: int = Field(ge=1)
    complex_score: int = Field(ge=2)
    specialist_score: int = Field(ge=3)


class WealthNeedRules(BaseModel):
    liquidity_months: str
    emergency_months: str
    medical_minimum_per_member: Money
    death_income_replacement_years: str
    long_term_growth_minimum: Money
    trust_review_net_worth: Money
    priority_scores: dict[WealthNeedType, Ratio]
    hard_constraint_need_types: list[WealthNeedType]
    professional_review_need_types: list[WealthNeedType]


class ClientProfileRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    wealth_tiers: WealthTierRules
    risk_score_thresholds: dict[RiskLevel, Ratio]
    tag_thresholds: TagThresholdRules
    service_complexity: ServiceComplexityRules
    needs: WealthNeedRules
    required_profile_domains: list[
        Literal["members", "income", "assets", "expenses", "risk", "behavior", "goals"]
    ]

    @model_validator(mode="after")
    def validate_policy(self) -> ClientProfileRules:
        tiers = self.wealth_tiers
        if not (
            tiers.emerging_affluent_minimum < tiers.affluent_minimum < tiers.high_net_worth_minimum
        ):
            raise ValueError("财富层级阈值必须严格递增")
        thresholds = [self.risk_score_thresholds[item] for item in RiskLevel]
        if thresholds != sorted(thresholds) or thresholds[-1] != 1:
            raise ValueError("风险分数阈值必须递增并以 1 结束")
        complexity = self.service_complexity
        if not (complexity.enhanced_score < complexity.complex_score < complexity.specialist_score):
            raise ValueError("服务复杂度阈值必须严格递增")
        if set(self.needs.priority_scores) != set(WealthNeedType):
            raise ValueError("财富需求优先级必须覆盖全部 NeedType")
        if len(self.required_profile_domains) != len(set(self.required_profile_domains)):
            raise ValueError("资料完整度域不能重复")
        return self


def resolve_client_profile_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(Path(__file__).resolve().parents[4] / "data/rules/client_profile_v1.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "client_profile_rules_missing",
        "找不到客户财富画像规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_client_profile_rules(configured_path: str) -> ClientProfileRules:
    path = resolve_client_profile_rules_path(configured_path)
    try:
        return ClientProfileRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "client_profile_rules_invalid",
            "客户财富画像规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_client_profile_rule_version(
    session: Session,
    rules: ClientProfileRules,
) -> RuleVersion:
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
