from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import CFSTimeHorizon


class RetirementRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basic_expense_replacement_ratio: Decimal = Field(gt=0, le=1)
    medical_expense_ratio: Decimal = Field(ge=0, le=1)
    long_term_care_annual_per_adult: Decimal = Field(ge=0)
    longevity_age: int = Field(ge=70, le=120)
    liquidity_bridge_years: int = Field(ge=1, le=20)
    social_security_income_factor: Decimal = Field(gt=0, le=5)
    financial_withdrawal_rate: Decimal = Field(gt=0, le=1)
    near_retirement_years: int = Field(ge=1, le=30)


class CrossBorderRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_amount: Decimal = Field(ge=0)
    material_ratio: Decimal = Field(ge=0, le=1)
    short_term_days: int = Field(ge=1)
    medium_term_days: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_horizons(self) -> CrossBorderRules:
        if self.short_term_days >= self.medium_term_days:
            raise ValueError("跨境期限阈值必须递增")
        return self


class TrustSuccessionRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minor_age: int = Field(ge=1, le=25)
    ownership_complexity_count: int = Field(ge=2, le=20)
    high_value_asset_threshold: Decimal = Field(ge=0)


class PhilanthropyRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    professional_review_annual_budget: Decimal = Field(ge=0)
    default_time_horizon: CFSTimeHorizon


class SpecializedCFSRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["v5-specialized-cfs"]
    semantic_version: str
    formula_version: str
    effective_from: date
    source_type: Literal["internal_demo"]
    source_summary: str
    retirement: RetirementRules
    cross_border: CrossBorderRules
    trust_succession: TrustSuccessionRules
    philanthropy: PhilanthropyRules


@lru_cache(maxsize=4)
def load_specialized_cfs_rules(path: str) -> SpecializedCFSRules:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SpecializedCFSRules.model_validate(payload)
