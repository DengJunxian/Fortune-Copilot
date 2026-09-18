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
from app.domain.enums import LiabilityStreamType, RiskLevel
from app.models.governance import RuleVersion
from app.schemas.records import Ratio


class IncomeAdequacyThresholds(BaseModel):
    critical_below: Decimal = Field(ge=0)
    watch_below: Decimal = Field(ge=0)
    comfortable_at: Decimal = Field(ge=0)


class LiabilityRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    education_installment_years: int = Field(ge=2, le=10)
    short_term_hard_liability_months: int = Field(ge=12, le=120)
    operating_liquidity_months: Decimal = Field(ge=0, le=12)
    emergency_reserve_months: Decimal = Field(ge=0, le=24)
    protection_funding_months: int = Field(ge=0, le=24)
    minimum_suitability_score: Ratio
    minimum_suitability_levels: list[RiskLevel] = Field(min_length=1)
    inflation_indexes: dict[LiabilityStreamType, str]
    iai_thresholds: IncomeAdequacyThresholds

    @model_validator(mode="after")
    def validate_policy(self) -> LiabilityRules:
        if set(self.inflation_indexes) != set(LiabilityStreamType):
            raise ValueError("通胀指数映射必须覆盖全部负债流类型")
        thresholds = self.iai_thresholds
        if not (thresholds.critical_below < thresholds.watch_below < thresholds.comfortable_at):
            raise ValueError("收入充足度阈值必须严格递增")
        if len(self.minimum_suitability_levels) != len(set(self.minimum_suitability_levels)):
            raise ValueError("最低适当性等级不能重复")
        return self


def resolve_liability_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/liability_engine_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "liability_rules_missing",
        "找不到负债流与长期可配置资本规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_liability_rules(configured_path: str) -> LiabilityRules:
    path = resolve_liability_rules_path(configured_path)
    try:
        return LiabilityRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "liability_rules_invalid",
            "负债流与长期可配置资本规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_liability_rule_version(session: Session, rules: LiabilityRules) -> RuleVersion:
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
        data_source="fortune-copilot-controlled-rule",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    return record
