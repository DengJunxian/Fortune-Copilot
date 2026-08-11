from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import (
    CFSComponentType,
    ProfessionalSpecialistType,
    RiskLevel,
    WealthNeedType,
)
from app.models.governance import RuleVersion


class CFSNeedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_type: CFSComponentType
    recommended_action: str = Field(min_length=1, max_length=800)
    deterministic_tool: Literal[
        "financial_health",
        "liability_calendar",
        "protection_planner",
        "pension_planner",
        "planning_waterfall",
        "portfolio_optimizer",
        "family_enterprise",
        "professional_routing",
        "no_action",
    ]
    product_mapping_allowed: bool
    specialist: ProfessionalSpecialistType | None


class CFSComposerRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    risk_ceiling_by_level: dict[RiskLevel, Decimal]
    short_horizon_days: int = Field(ge=30, le=3650)
    high_liability_rigidity_ratio: Decimal = Field(ge=0, le=1)
    referral_due_days: dict[str, int]
    need_policies: dict[WealthNeedType, CFSNeedPolicy]

    @model_validator(mode="after")
    def validate_rules(self) -> CFSComposerRules:
        if set(self.risk_ceiling_by_level) != set(RiskLevel):
            raise ValueError("风险层级上限必须覆盖全部 RiskLevel")
        if set(self.need_policies) != set(WealthNeedType):
            raise ValueError("CFS 需求策略必须覆盖全部 WealthNeedType")
        if set(self.referral_due_days) != {"low", "medium", "high", "urgent"}:
            raise ValueError("专业转介时限必须覆盖四个紧急层级")
        return self


def resolve_cfs_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(Path(__file__).resolve().parents[4] / "data/rules/cfs_composer_v1.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "cfs_rules_missing",
        "找不到 CFS 编排规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_cfs_rules(configured_path: str) -> CFSComposerRules:
    path = resolve_cfs_rules_path(configured_path)
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return CFSComposerRules.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "cfs_rules_invalid",
            "CFS 编排规则不可用",
            status_code=503,
        ) from exc


def ensure_cfs_rule_version(session: Session, rules: CFSComposerRules) -> RuleVersion:
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
        currency="CNY",
        valuation_date=rules.effective_from,
        data_source="fortune-copilot-controlled-rule",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    return record
