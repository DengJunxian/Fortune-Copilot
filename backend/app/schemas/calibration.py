from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import CalibrationMode

CalibrationStatus = Literal["available", "degraded", "needs_review"]


class CalibrationParameterSeed(BaseModel):
    code: str = Field(min_length=3, max_length=160)
    value: Decimal
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    estimation_method: str = Field(min_length=3, max_length=240)
    segment: str = Field(default="all", min_length=1, max_length=100)
    region: str = Field(default="CN", min_length=1, max_length=40)
    effective_from: date
    effective_to: date | None = None
    version: str = Field(min_length=1, max_length=120)
    confidence: Decimal = Field(ge=0, le=1)
    limitations: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bounds_and_dates(self) -> CalibrationParameterSeed:
        if self.lower_bound is not None and self.value < self.lower_bound:
            raise ValueError("calibration value is below lower_bound")
        if self.upper_bound is not None and self.value > self.upper_bound:
            raise ValueError("calibration value is above upper_bound")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class CalibrationDatasetSeed(BaseModel):
    code: str = Field(min_length=3, max_length=100)
    mode: CalibrationMode
    source: str = Field(min_length=2, max_length=240)
    source_reference: str = Field(min_length=3, max_length=600)
    population: str = Field(min_length=2, max_length=240)
    sample_period: str = Field(min_length=2, max_length=160)
    effective_date: date
    version: str = Field(min_length=1, max_length=120)
    license_or_access_note: str = Field(min_length=2)
    limitations: list[str] = Field(min_length=1)
    data_quality: str = Field(min_length=2, max_length=100)
    parameters: list[CalibrationParameterSeed] = Field(min_length=1)


class CalibrationRegistrySeed(BaseModel):
    schema_version: Literal["calibration-registry-schema-v1.0.0"]
    registry_version: str = Field(min_length=3, max_length=120)
    datasets: list[CalibrationDatasetSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_scopes(self) -> CalibrationRegistrySeed:
        dataset_keys = [(item.code, item.version) for item in self.datasets]
        if len(dataset_keys) != len(set(dataset_keys)):
            raise ValueError("calibration dataset code/version must be unique")
        parameter_keys = [
            (
                dataset.code,
                item.code,
                item.segment,
                item.region,
                item.effective_from,
                item.version,
            )
            for dataset in self.datasets
            for item in dataset.parameters
        ]
        if len(parameter_keys) != len(set(parameter_keys)):
            raise ValueError("calibration parameter scope/version must be unique")
        return self


class CalibrationParameterResolution(BaseModel):
    parameter_id: str
    code: str
    value: Decimal | None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    segment: str
    region: str
    mode: CalibrationMode | None
    status: CalibrationStatus
    source: str
    source_reference: str
    version: str
    method: str
    confidence: Decimal = Field(ge=0, le=1)
    limitations: list[str]
    effective_from: date | None = None
    effective_to: date | None = None
    dataset_code: str | None = None
    reason: str


class CalibrationDatasetOut(BaseModel):
    id: str
    code: str
    mode: CalibrationMode
    source: str
    source_reference: str
    population: str
    sample_period: str
    effective_date: date
    version: str
    license_or_access_note: str
    limitations: list[str]
    data_quality: str
    parameter_count: int = Field(ge=0)


class CalibrationModeAvailability(BaseModel):
    mode: CalibrationMode
    available: bool
    dataset_count: int = Field(ge=0)
    parameter_count: int = Field(ge=0)
    note: str


class CalibrationCatalogResponse(BaseModel):
    registry_version: str
    datasets: list[CalibrationDatasetOut]
    modes: list[CalibrationModeAvailability]
    no_silent_guessing: Literal[True] = True
