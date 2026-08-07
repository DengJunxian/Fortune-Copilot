from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.governance import RuleVersion

ThresholdSourceType = Literal["official_rule", "industry_reference", "internal_demo"]


class ClassificationRules(BaseModel):
    emergency_liquid_levels: list[str]
    short_term_liquid_max_days: int = Field(ge=0)
    twelve_month_liquid_max_days: int = Field(ge=0)
    financial_asset_categories: list[str]
    investable_financial_asset_categories: list[str]
    property_categories: list[str]
    passive_income_types: list[str]
    stale_financial_days: int = Field(ge=1)
    stale_property_days: int = Field(ge=1)
    abnormal_return_multiple: str


class ProtectionRules(BaseModel):
    death_support_years: str
    medical_self_pay_reserve: str
    accident_income_years: str
    family_support_years: str


class BenchmarkParameter(BaseModel):
    label: str
    rate: str
    source_type: ThresholdSourceType
    source_reference: str
    data_as_of: date
    is_live: bool | None = None
    is_cpi: bool | None = None
    is_return_guarantee: bool | None = None


class PurchasingPowerRules(BaseModel):
    official_cpi: BenchmarkParameter
    expense_category_rates: dict[str, str]
    minimum_wage_catch_up: BenchmarkParameter


class ThresholdRule(BaseModel):
    reference_range: str
    source_type: ThresholdSourceType
    source_reference: str
    parameters: dict[str, str]


class FinancialRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_summary: str
    classification: ClassificationRules
    protection: ProtectionRules
    purchasing_power: PurchasingPowerRules
    thresholds: dict[str, ThresholdRule]

    def threshold(self, code: str) -> ThresholdRule:
        return self.thresholds.get(code, self.thresholds["measurement_only"])


def resolve_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/financial_health_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "financial_rules_missing",
        "找不到确定性财务规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_financial_rules(configured_path: str) -> FinancialRules:
    path = resolve_rules_path(configured_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return FinancialRules.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "financial_rules_invalid",
            "确定性财务规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_rule_version(session: Session, rules: FinancialRules) -> RuleVersion:
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
