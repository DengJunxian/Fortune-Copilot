from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ConstitutionArticle(BaseModel):
    code: str
    title: str
    rule: str
    hard: bool


class DailyLiquidityRule(BaseModel):
    strategy: Literal["quarter_month_clamped"]
    operating_months: Decimal = Field(gt=0, le=1)
    minimum_amount: Decimal = Field(ge=0)
    maximum_amount: Decimal = Field(gt=0)
    forecast_port: Literal["CashFlowForecastPort"]
    future_forecast_horizons_days: list[int]
    future_quantile: Decimal = Field(gt=0, le=1)


class RegionProfile(BaseModel):
    region_code: str
    city_tier: str
    base: Decimal


class RegionalThresholdRule(BaseModel):
    policy_version: str
    minimum: Decimal
    default: Decimal
    maximum: Decimal
    recommended_band_width: Decimal
    region_profiles: dict[str, RegionProfile]
    city_tier_bases: dict[str, Decimal]
    employment_adjustments: dict[str, Decimal]
    volatility_adjustments: dict[str, Decimal]
    interruption_probability_breaks: dict[str, Decimal]
    interruption_adjustments: dict[str, Decimal]
    dependent_adjustment_each: Decimal
    single_income_adjustment: Decimal
    debt_burden_breaks: dict[str, Decimal]
    debt_adjustments: dict[str, Decimal]
    lifecycle_adjustments: dict[str, Decimal]

    @model_validator(mode="after")
    def validate_thresholds(self) -> RegionalThresholdRule:
        if not self.minimum <= self.default <= self.maximum:
            raise ValueError("地区启动线必须满足 minimum <= default <= maximum")
        return self


class MarketRegimeSnapshot(BaseModel):
    snapshot_version: str
    regime: Literal["favorable", "neutral", "defensive"]
    label: str
    valuation_date: date
    effective_from: date
    effective_to: date | None
    source: str
    methodology: str
    evidence: list[str]
    rule_version: str
    approved_by: str
    is_demo: bool
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    lineage: str


class MinimumWagePoint(BaseModel):
    date: date
    monthly_amount: Decimal = Field(gt=0)


class RegionalMinimumWageSnapshot(BaseModel):
    region_name: str
    values: list[MinimumWagePoint]
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    is_demo: bool
    lineage: str


class PensionPolicySnapshot(BaseModel):
    policy_version: str
    annual_contribution_limit: Decimal = Field(gt=0)
    withdrawal_tax_rate: Decimal = Field(ge=0, le=1)
    effective_from: date
    effective_to: date | None
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    is_demo: bool
    lineage: str


class PropertyInvestmentPolicySnapshot(BaseModel):
    policy_version: str
    status: Literal["restricted_by_default", "review_required", "available"]
    valuation_date: date
    source: str
    is_demo: bool
    source_system: str
    source_reference: str
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: bool
    lineage: str
    rules: list[str]


class ProductSnapshotPolicy(BaseModel):
    policy_version: str
    maximum_age_days: int = Field(ge=1, le=366)
    stale_action: Literal["block_executable_allow_education"]


class DataGovernanceRule(BaseModel):
    version: str
    required_fields: list[str]
    source_kinds: list[str]


class MethodologyRules(BaseModel):
    code: str
    semantic_version: str
    formula_version: str
    effective_from: date
    effective_to: date | None
    source_type: Literal["internal_demo"]
    source_summary: str
    constitution: list[ConstitutionArticle]
    denominators: dict[str, str]
    daily_liquidity: DailyLiquidityRule
    regional_growth_threshold: RegionalThresholdRule
    market_regime_snapshot: MarketRegimeSnapshot
    regional_minimum_wage_snapshots: dict[str, RegionalMinimumWageSnapshot]
    minimum_wage_fallback_rate: Decimal
    pension_policy_snapshot: PensionPolicySnapshot
    property_policy_snapshot: PropertyInvestmentPolicySnapshot
    product_snapshot_policy: ProductSnapshotPolicy
    data_governance: DataGovernanceRule

    @model_validator(mode="after")
    def validate_constitution(self) -> MethodologyRules:
        required_denominators = {
            "total_household_assets",
            "investable_financial_assets",
            "residual_long_term_plannable_capital",
        }
        if set(self.denominators) != required_denominators:
            raise ValueError("方法论必须且只能定义三个核心分母")
        if len(self.constitution) < 7 or not all(item.hard for item in self.constitution):
            raise ValueError("方法论宪法必须完整且不可覆盖")
        return self
