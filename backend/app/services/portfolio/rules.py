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
from app.domain.enums import ComplexityLevel, ProductRiskLevel
from app.models.governance import RuleVersion
from app.schemas.records import Ratio


class AssetAssumption(BaseModel):
    expected_nominal_return: Ratio
    volatility: Ratio
    cvar_loss: Ratio
    max_drawdown: Ratio
    liquidity_score: Ratio
    annual_fee_rate: Ratio
    source: str
    effective_date: date
    confidence: Ratio
    approved_by: str
    calibration_period: str


class DeterministicScenario(BaseModel):
    code: str
    probability: Ratio
    returns: dict[str, Decimal]
    source: str
    effective_date: date
    confidence: Ratio
    approved_by: str
    calibration_period: str


class ObjectiveWeights(BaseModel):
    cvar: Decimal = Field(ge=0)
    goal_shortfall: Decimal = Field(ge=0)
    drawdown: Decimal = Field(ge=0)
    liquidity_shortfall: Decimal = Field(ge=0)
    turnover: Decimal = Field(ge=0)
    success_probability: Decimal = Field(ge=0)
    purchasing_power: Decimal = Field(ge=0)
    diversification: Decimal = Field(ge=0)


class CandidatePolicy(BaseModel):
    name: str
    required_risk_level: ProductRiskLevel
    bounds: dict[str, tuple[Ratio, Ratio]]
    fallback: dict[str, Ratio]


class SuitabilityRules(BaseModel):
    risk_level_order: list[ProductRiskLevel]
    score_thresholds: dict[ProductRiskLevel, Ratio]
    risk_level_high_risk_caps: dict[ProductRiskLevel, Ratio]
    maximum_single_product_ratio: Ratio
    maximum_single_asset_class_ratio: Ratio
    short_horizon_months: int = Field(ge=1, le=60)
    high_volatility_threshold: Ratio
    family_restricted_high_risk_cap: Ratio
    family_blocked_high_risk_cap: Ratio
    complexity_order: list[ComplexityLevel]


class RebalancingRules(BaseModel):
    absolute_drift_threshold: Ratio
    relative_drift_threshold: Ratio
    scheduled_review_months: int = Field(ge=1, le=24)
    maximum_tactical_shift: Ratio


class PortfolioRules(BaseModel):
    code: str
    semantic_version: str
    optimizer_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    random_seed: int = Field(ge=0)
    asset_classes: list[str] = Field(min_length=5, max_length=8)
    asset_assumptions: dict[str, AssetAssumption]
    scenarios: list[DeterministicScenario] = Field(min_length=3)
    objective_weights: ObjectiveWeights
    grid_step: Ratio
    minimum_liquidity_score: Ratio
    default_purchasing_power_hurdle: Ratio
    default_inflation_rate: Ratio | None = None
    candidate_policies: dict[str, CandidatePolicy]
    suitability: SuitabilityRules
    rebalancing: RebalancingRules

    @model_validator(mode="after")
    def validate_rules(self) -> PortfolioRules:
        expected = set(self.asset_classes)
        if set(self.asset_assumptions) != expected:
            raise ValueError("资产假设必须覆盖并且只覆盖全部资产类别")
        if set(self.candidate_policies) != {"conservative", "balanced", "growth"}:
            raise ValueError("必须且只能提供稳健、基准、进取三套候选策略")
        if sum((item.probability for item in self.scenarios), Decimal("0")) != Decimal("1"):
            raise ValueError("确定性情景概率之和必须为 1")
        if self.grid_step <= 0 or Decimal("1") % self.grid_step != 0:
            raise ValueError("网格步长必须能整除 1")
        for scenario in self.scenarios:
            if set(scenario.returns) != expected:
                raise ValueError(f"情景 {scenario.code} 未覆盖全部资产类别")
        for code, policy in self.candidate_policies.items():
            if set(policy.bounds) != expected or set(policy.fallback) != expected:
                raise ValueError(f"候选 {code} 的边界或降级权重不完整")
            if sum(policy.fallback.values(), Decimal("0")) != Decimal("1"):
                raise ValueError(f"候选 {code} 的降级权重之和必须为 1")
            for lower, upper in policy.bounds.values():
                if lower > upper:
                    raise ValueError(f"候选 {code} 的资产边界上下限无效")
        return self


def resolve_portfolio_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/portfolio_policy_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "portfolio_rules_missing",
        "找不到组合优化与适当性规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_portfolio_rules(configured_path: str) -> PortfolioRules:
    path = resolve_portfolio_rules_path(configured_path)
    try:
        return PortfolioRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "portfolio_rules_invalid",
            "组合优化与适当性规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_portfolio_rule_version(session: Session, rules: PortfolioRules) -> RuleVersion:
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
