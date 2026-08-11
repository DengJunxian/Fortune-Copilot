from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import RiskLevel
from app.models.governance import RuleVersion
from app.schemas.records import Ratio

DependencyCode = Literal[
    "wealth_dependency",
    "income_dependency",
    "guarantee_dependency",
    "pledge_dependency",
    "currency_dependency",
]


class DependencyThresholds(BaseModel):
    low_below: Ratio
    medium_below: Ratio
    high_at: Ratio


class FamilyEnterpriseRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    dependency_weights: dict[DependencyCode, Ratio]
    dependency_thresholds: DependencyThresholds
    risk_budget_ceiling_by_capacity: dict[RiskLevel, Ratio]
    high_dependency_blocks_additional_equity: bool

    @model_validator(mode="after")
    def validate_policy(self) -> FamilyEnterpriseRules:
        required_components = {
            "wealth_dependency",
            "income_dependency",
            "guarantee_dependency",
            "pledge_dependency",
            "currency_dependency",
        }
        if set(self.dependency_weights) != required_components:
            raise ValueError("依赖度权重必须覆盖全部五个维度")
        if sum(self.dependency_weights.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("依赖度权重之和必须为 1")
        thresholds = self.dependency_thresholds
        if not (
            thresholds.low_below < thresholds.medium_below < thresholds.high_at <= 1
        ):
            raise ValueError("依赖度分层阈值必须严格递增")
        if set(self.risk_budget_ceiling_by_capacity) != set(RiskLevel):
            raise ValueError("风险预算上限必须覆盖全部风险能力等级")
        return self


def resolve_family_enterprise_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/family_enterprise_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "family_enterprise_rules_missing",
        "找不到家企财富依赖规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_family_enterprise_rules(configured_path: str) -> FamilyEnterpriseRules:
    path = resolve_family_enterprise_rules_path(configured_path)
    try:
        return FamilyEnterpriseRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "family_enterprise_rules_invalid",
            "家企财富依赖规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_family_enterprise_rule_version(
    session: Session,
    rules: FamilyEnterpriseRules,
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
        data_source="fortune-copilot-controlled-rule",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    return record
