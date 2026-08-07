from __future__ import annotations

import json
import math
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.governance import RuleVersion, ScenarioDefinition


class ReturnAssumption(BaseModel):
    expected_annual_return: Decimal = Field(gt=Decimal("-1"), lt=Decimal("1"))
    annual_volatility: Decimal = Field(ge=0, le=Decimal("2"))


class ScenarioParameters(BaseModel):
    income_interruption_months: int = Field(default=0, ge=0, le=120)
    income_reduction_ratio: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    income_reduction_months: int = Field(default=0, ge=0, le=720)
    income_reduction_target: Literal["primary", "secondary", "all"] = "primary"
    medical_shock_amount: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("100000000"))
    family_support_monthly_increase: Decimal = Field(
        default=Decimal("0"), ge=0, le=Decimal("1000000")
    )
    family_support_duration_months: int = Field(default=0, ge=0, le=720)
    education_overrun_amount: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("100000000"))
    retirement_age_reduction_years: int = Field(default=0, ge=0, le=20)
    longevity_extension_years: int = Field(default=0, ge=0, le=30)
    mortgage_rate_increase: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.20"))
    investment_property_vacancy_months: int = Field(default=0, ge=0, le=120)
    property_value_shock: Decimal = Field(
        default=Decimal("0"), ge=Decimal("-0.80"), le=Decimal("0.50")
    )
    asset_return_shocks: dict[str, Decimal] = Field(default_factory=dict)
    asset_volatility_multipliers: dict[str, Decimal] = Field(default_factory=dict)
    long_term_return_reduction: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.20"))
    inflation_increase: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.20"))
    goal_advance_months: int = Field(default=0, ge=0, le=240)


class ScenarioRule(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=800)
    parameters: ScenarioParameters
    explanation: str = Field(min_length=1, max_length=800)
    is_composable: bool = True


class TwinRules(BaseModel):
    code: str
    semantic_version: str
    engine_version: str
    formula_version: str
    result_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    default_seed: int = Field(ge=0)
    default_path_count: int = Field(ge=100, le=5000)
    minimum_path_count: int = Field(ge=50, le=5000)
    maximum_path_count: int = Field(ge=100, le=10000)
    default_horizon_years: int = Field(ge=5, le=60)
    minimum_horizon_years: int = Field(ge=1, le=60)
    maximum_horizon_years: int = Field(ge=5, le=80)
    time_step_months: Literal[1]
    default_output_interval_months: int = Field(ge=1, le=12)
    quantiles: list[Decimal] = Field(min_length=5, max_length=9)
    goal_success_threshold: Decimal = Field(ge=0, le=1)
    maximum_balance: Decimal = Field(gt=0)
    base_inflation_rate: Decimal = Field(ge=0, le=Decimal("0.20"))
    base_income_growth_rate: Decimal = Field(ge=Decimal("-0.20"), le=Decimal("0.20"))
    asset_classes: list[str] = Field(min_length=5, max_length=8)
    asset_assumptions: dict[str, ReturnAssumption]
    correlation_matrix: list[list[Decimal]]
    property_assumption: ReturnAssumption
    pension_assumption: ReturnAssumption
    other_asset_annual_depreciation: Decimal = Field(ge=0, le=1)
    scenario_version: str
    scenarios: list[ScenarioRule] = Field(min_length=17)

    @model_validator(mode="after")
    def validate_twin_rules(self) -> TwinRules:
        if not self.minimum_path_count <= self.default_path_count <= self.maximum_path_count:
            raise ValueError("默认路径数必须位于最小值和最大值之间")
        if (
            not self.minimum_horizon_years
            <= self.default_horizon_years
            <= self.maximum_horizon_years
        ):
            raise ValueError("默认模拟期限必须位于允许范围内")
        if set(self.asset_assumptions) != set(self.asset_classes):
            raise ValueError("资产收益假设必须完整覆盖资产类别")
        if self.quantiles != sorted(self.quantiles) or Decimal("0.50") not in self.quantiles:
            raise ValueError("分位数必须升序并包含中位数")
        size = len(self.asset_classes)
        if len(self.correlation_matrix) != size or any(
            len(row) != size for row in self.correlation_matrix
        ):
            raise ValueError("相关矩阵维度必须与资产类别一致")
        matrix = [[float(value) for value in row] for row in self.correlation_matrix]
        for row_index, row in enumerate(matrix):
            for column_index, value in enumerate(row):
                if not -1 <= value <= 1:
                    raise ValueError("相关系数必须位于 -1 到 1")
                if row_index == column_index and not math.isclose(value, 1.0, abs_tol=1e-9):
                    raise ValueError("相关矩阵对角线必须为 1")
                if not math.isclose(
                    value,
                    matrix[column_index][row_index],
                    abs_tol=1e-9,
                ):
                    raise ValueError("相关矩阵必须对称")
        _cholesky(matrix)
        codes = [item.code for item in self.scenarios]
        if len(codes) != len(set(codes)):
            raise ValueError("压力场景代码必须唯一")
        allowed = set(self.asset_classes)
        for scenario in self.scenarios:
            if not set(scenario.parameters.asset_return_shocks) <= allowed:
                raise ValueError(f"场景 {scenario.code} 引用了未知资产类别")
            if not set(scenario.parameters.asset_volatility_multipliers) <= allowed:
                raise ValueError(f"场景 {scenario.code} 引用了未知波动类别")
        return self


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    result = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            subtotal = sum(result[row][k] * result[column][k] for k in range(column))
            if row == column:
                value = matrix[row][row] - subtotal
                if value <= 1e-12:
                    raise ValueError("相关矩阵必须正定")
                result[row][column] = math.sqrt(value)
            else:
                result[row][column] = (matrix[row][column] - subtotal) / result[column][column]
    return result


def resolve_twin_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/twin_simulation_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "twin_rules_missing",
        "找不到家庭财富数字孪生规则文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_twin_rules(configured_path: str) -> TwinRules:
    path = resolve_twin_rules_path(configured_path)
    try:
        return TwinRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise AppError(
            "twin_rules_invalid",
            "家庭财富数字孪生规则未通过结构校验",
            status_code=500,
        ) from exc


def ensure_twin_rule_version(session: Session, rules: TwinRules) -> RuleVersion:
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


def ensure_scenario_definitions(session: Session, rules: TwinRules) -> list[ScenarioDefinition]:
    records: list[ScenarioDefinition] = []
    for scenario in rules.scenarios:
        existing = session.scalar(
            select(ScenarioDefinition).where(
                ScenarioDefinition.code == scenario.code,
                ScenarioDefinition.is_deleted.is_(False),
            )
        )
        values = {
            "name": scenario.name,
            "category": scenario.category,
            "parameters": scenario.parameters.model_dump(mode="json"),
            "explanation": scenario.explanation,
            "scenario_version": rules.scenario_version,
            "is_composable": scenario.is_composable,
            "source_type": rules.source_type,
            "enabled": True,
            "valuation_date": rules.effective_from,
            "data_source": "wealthtwin-controlled-scenario",
            "is_user_confirmed": True,
        }
        if existing is None:
            existing = ScenarioDefinition(code=scenario.code, **values)
            session.add(existing)
            session.flush()
        elif existing.scenario_version != rules.scenario_version:
            for key, value in values.items():
                setattr(existing, key, value)
            existing.version += 1
            session.flush()
        records.append(existing)
    return records


def cholesky_for_rules(rules: TwinRules) -> list[list[float]]:
    return _cholesky([[float(value) for value in row] for row in rules.correlation_matrix])


def cholesky_matrix(matrix: list[list[Decimal]]) -> list[list[float]]:
    return _cholesky([[float(value) for value in row] for row in matrix])
