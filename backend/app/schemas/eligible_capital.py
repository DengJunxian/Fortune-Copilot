from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import CalibrationMode, LiabilityStreamType
from app.schemas.calibration import CalibrationParameterResolution, CalibrationStatus
from app.schemas.records import Money, Ratio


class EligibleCapitalBridgeStep(BaseModel):
    code: str
    label: str
    before: Money
    requested_deduction: Money
    deduction: Money
    after: Money
    unfunded: Money
    source: str
    reason: str


class EligibilityGate(BaseModel):
    code: str
    label: str
    passed: bool
    reason: str


class GrowthThresholdReference(BaseModel):
    amount: Money
    currency: str
    source: str
    deprecated_as_hard_gate: Literal[True] = True
    determines_eligibility: Literal[False] = False
    communication_note: str


class InflationComponent(BaseModel):
    code: str
    label: str
    annual_rate: Ratio
    annual_cost: Money
    weight: Ratio


class HouseholdCostInflation(BaseModel):
    code: Literal["HCI"] = "HCI"
    annual_rate: Ratio
    components: list[InflationComponent]
    calibration_status: CalibrationStatus
    calibration_modes: list[CalibrationMode]
    parameter_references: list[CalibrationParameterResolution]
    interpretation: str


class GoalCostInflation(BaseModel):
    code: Literal["GCI"] = "GCI"
    stream_id: str
    stream_name: str
    stream_type: LiabilityStreamType
    inflation_index_code: str
    annual_rate: Ratio
    calibration_status: CalibrationStatus
    calibration_modes: list[CalibrationMode]
    parameter_references: list[CalibrationParameterResolution]
    interpretation: str


class IncomeAdequacyIndex(BaseModel):
    code: Literal["IAI"] = "IAI"
    sustainable_annual_income: Money
    essential_annual_cost: Money
    ratio: Decimal = Field(ge=0, max_digits=12, decimal_places=6)
    status: Literal["critical", "watch", "adequate", "comfortable"]
    minimum_wage_trend: Ratio
    minimum_wage_scope: Literal["income_adequacy_only"] = "income_adequacy_only"
    minimum_wage_used_as_portfolio_hurdle: Literal[False] = False
    calibration_status: CalibrationStatus
    calibration_modes: list[CalibrationMode]
    parameter_references: list[CalibrationParameterResolution]
    interpretation: str


class PurchasingPowerV2(BaseModel):
    formula_version: str
    calibration_registry_version: str
    calibration_status: CalibrationStatus
    calibration_modes: list[CalibrationMode]
    parameter_references: list[CalibrationParameterResolution]
    requires_human_review: bool
    household_cost_inflation: HouseholdCostInflation
    goal_cost_inflation: list[GoalCostInflation]
    income_adequacy: IncomeAdequacyIndex
    minimum_wage_used_as_cpi_proxy: Literal[False] = False
    minimum_wage_used_as_return_hurdle: Literal[False] = False


class EligibleCapitalCalculation(BaseModel):
    dispatchable_financial_resources: Money
    bridge: list[EligibleCapitalBridgeStep]
    eligible_long_term_capital: Money
    eligibility_gates: list[EligibilityGate]
    formally_eligible: bool
    decision: Literal["eligible", "repair_first"]
    growth_entry_threshold: GrowthThresholdReference
    purchasing_power: PurchasingPowerV2


class EligibleCapitalMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    input_hash: str
    rule_version: str
    formula_version: str
    calibration_version: str
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"


class EligibleCapitalResponse(BaseModel):
    meta: EligibleCapitalMeta
    calculation: EligibleCapitalCalculation
