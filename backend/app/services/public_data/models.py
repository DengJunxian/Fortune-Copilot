from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictSnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernedPublicSource(StrictSnapshotModel):
    source_system: str
    source_reference: HttpUrl
    observed_at: date
    effective_at: date
    ingested_at: datetime
    version: str
    data_quality: str
    is_live: Literal[False]
    is_demo: Literal[False]
    lineage: str


class OfficialCpiObservation(GovernedPublicSource):
    rate: Decimal = Field(ge=Decimal("-0.20"), le=Decimal("1"))
    statistic_label: str
    period_start: date
    period_end: date
    is_cpi: Literal[True]


class LivingCostObservation(GovernedPublicSource):
    metric: str
    amount: Decimal = Field(ge=0)
    year_on_year_rate: Decimal
    unit: str
    period_start: date
    period_end: date
    interpretation: str
    can_be_used_as_cpi: Literal[False]


class RegionalLivingCostObservation(LivingCostObservation):
    region_code: str = Field(pattern=r"^\d{6}$")
    region_name: str


class MinimumWagePoint(StrictSnapshotModel):
    date: date
    monthly_amount: Decimal = Field(gt=0)
    source_reference: HttpUrl


class PublicMinimumWageSeries(GovernedPublicSource):
    region_code: str = Field(pattern=r"^\d{6}$")
    region_name: str
    values: list[MinimumWagePoint] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_series(self) -> PublicMinimumWageSeries:
        dates = [item.date for item in self.values]
        if dates != sorted(dates) or len(set(dates)) != len(dates):
            raise ValueError("最低工资序列必须按日期严格递增")
        return self


class PolicySource(StrictSnapshotModel):
    code: str
    title: str
    authority: str
    publication_date: date
    effective_from: date
    control_scope: list[str] = Field(min_length=1)
    source_reference: HttpUrl


class IntegrationAccessBoundary(StrictSnapshotModel):
    code: str
    authority: str
    access_model: str
    public_description: str
    source_reference: HttpUrl


class AuthoritativePublicDataSnapshot(StrictSnapshotModel):
    schema_version: str
    snapshot_version: str
    publication_cutoff: date
    ingested_at: datetime
    official_cpi: OfficialCpiObservation
    living_cost_observation: LivingCostObservation
    regional_living_cost_observations: dict[str, RegionalLivingCostObservation]
    regional_minimum_wages: dict[str, PublicMinimumWageSeries]
    policy_sources: list[PolicySource]
    integration_access_boundaries: list[IntegrationAccessBoundary]

    @model_validator(mode="after")
    def validate_snapshot(self) -> AuthoritativePublicDataSnapshot:
        if self.official_cpi.period_end > self.publication_cutoff:
            raise ValueError("CPI 观察期不能晚于快照截止日期")
        if self.living_cost_observation.can_be_used_as_cpi:
            raise ValueError("名义消费支出观察不得标记为 CPI")
        for key, observation in self.regional_living_cost_observations.items():
            if key != observation.region_code:
                raise ValueError("地区生活成本字典键必须等于 region_code")
            if observation.can_be_used_as_cpi:
                raise ValueError("地区名义消费支出观察不得标记为 CPI")
        for key, series in self.regional_minimum_wages.items():
            if key != series.region_code:
                raise ValueError("地区最低工资字典键必须等于 region_code")
            if any(point.date > self.publication_cutoff for point in series.values):
                raise ValueError("最低工资数据点不能晚于快照截止日期")
        return self


class PublicDataSnapshotResponse(StrictSnapshotModel):
    snapshot: AuthoritativePublicDataSnapshot
    integrity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    update_mode: Literal["controlled_snapshot_not_runtime_scraping"] = (
        "controlled_snapshot_not_runtime_scraping"
    )
    boundary_note: str
