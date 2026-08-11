from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    AssetPurposeDimension,
    ComplexityLevel,
    FinancialEntityType,
    OwnershipType,
    RiskLevel,
)
from app.schemas.records import (
    Money,
    Ratio,
    RecordInput,
    RecordOut,
    RecordUpdate,
    reject_binary_float,
)

Quantity = Annotated[
    Decimal,
    BeforeValidator(reject_binary_float),
    Field(ge=0, max_digits=28, decimal_places=8),
]


class FinancialAccountDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(min_length=1, max_length=160)
    account_type: str = Field(min_length=1, max_length=64)
    account_wrapper: AccountWrapper = AccountWrapper.ORDINARY
    jurisdiction: str = Field(default="CN", min_length=2, max_length=64)
    external_reference: str | None = Field(default=None, max_length=200)
    restriction_json: dict[str, Any] = Field(default_factory=dict)


class PositionCreate(RecordInput):
    account_id: str | None = None
    account: FinancialAccountDraft | None = None
    owner_entity_id: str | None = None
    product_id: str | None = None
    enterprise_id: str | None = None
    instrument_type: AssetCategory
    instrument_code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    quantity: Quantity | None = None
    acquisition_cost: Money
    market_value: Money
    purpose_dimension: AssetPurposeDimension
    risk_level: RiskLevel
    liquidity_days: int = Field(ge=0, le=36500)
    complexity_level: ComplexityLevel = ComplexityLevel.BASIC
    principal_loss_possible: bool
    legally_principal_guaranteed: bool
    lock_up: bool = False
    withdrawable_date: date | None = None
    source_kind: str = Field(default="user_self_report", min_length=1, max_length=40)
    evidence_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_position(self) -> PositionCreate:
        if self.account_id is not None and self.account is not None:
            raise ValueError("account_id 与 account 只能提供一个")
        if self.legally_principal_guaranteed and self.principal_loss_possible:
            raise ValueError("法律属性保证本金的资产不能同时标记本金可损失")
        if not self.is_user_confirmed:
            raise ValueError("精细资产写入前必须由客户或顾问确认")
        return self


class PositionUpdate(RecordUpdate):
    owner_entity_id: str | None = None
    product_id: str | None = None
    enterprise_id: str | None = None
    instrument_type: AssetCategory | None = None
    instrument_code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    quantity: Quantity | None = None
    acquisition_cost: Money | None = None
    market_value: Money | None = None
    purpose_dimension: AssetPurposeDimension | None = None
    risk_level: RiskLevel | None = None
    liquidity_days: int | None = Field(default=None, ge=0, le=36500)
    complexity_level: ComplexityLevel | None = None
    principal_loss_possible: bool | None = None
    legally_principal_guaranteed: bool | None = None
    lock_up: bool | None = None
    withdrawable_date: date | None = None
    source_kind: str | None = Field(default=None, min_length=1, max_length=40)
    evidence_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_position(self) -> PositionUpdate:
        if self.legally_principal_guaranteed is True and self.principal_loss_possible is True:
            raise ValueError("法律属性保证本金的资产不能同时标记本金可损失")
        if self.is_user_confirmed is False:
            raise ValueError("已确认的精细资产不能改为未确认状态")
        return self


class FinancialEntityOut(RecordOut):
    household_id: str
    entity_type: FinancialEntityType
    display_name: str
    jurisdiction: str
    external_reference: str | None
    metadata_json: dict[str, Any]


class FinancialAccountOut(RecordOut):
    household_id: str
    owner_entity_id: str
    provider_name: str
    account_type: str
    account_wrapper: AccountWrapper
    jurisdiction: str
    external_reference: str | None
    restriction_json: dict[str, Any]


class PositionOut(RecordOut):
    household_id: str
    account_id: str
    owner_entity_id: str
    product_id: str | None
    legacy_asset_id: str | None
    enterprise_id: str | None
    instrument_type: AssetCategory
    instrument_code: str | None
    name: str
    quantity: Quantity | None
    acquisition_cost: Money
    market_value: Money
    purpose_dimension: AssetPurposeDimension
    risk_level: RiskLevel
    liquidity_days: int
    complexity_level: ComplexityLevel
    principal_loss_possible: bool
    legally_principal_guaranteed: bool
    lock_up: bool
    withdrawable_date: date | None
    source_kind: str
    evidence_json: dict[str, Any]


class OwnershipEdgeOut(RecordOut):
    household_id: str
    owner_entity_id: str
    owned_entity_id: str
    ownership_type: OwnershipType
    ownership_ratio: Ratio | None
    effective_from: date | None
    effective_to: date | None
    evidence_json: dict[str, Any]


class FinancialGraphMeta(BaseModel):
    household_id: str
    analysis_date: date
    data_as_of: date | None
    input_version: int
    source_snapshot_id: None = None
    engine_version: Literal["financial-graph-v1"] = "financial-graph-v1"
    rule_version: Literal["v5-e01-graph-rules-v1"] = "v5-e01-graph-rules-v1"
    methodology_version: Literal["v5-foundation"] = "v5-foundation"
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    synthetic_data: bool


class FinancialGraphIntegrity(BaseModel):
    status: Literal["passed", "needs_review"]
    issues: list[str] = Field(default_factory=list)


class ProjectionDiagnostic(BaseModel):
    status: Literal["matched", "mismatch"]
    legacy_asset_total: Money
    projected_asset_total: Money
    difference: Money
    details: list[str] = Field(default_factory=list)


class FinancialGraphResponse(BaseModel):
    meta: FinancialGraphMeta
    entities: list[FinancialEntityOut]
    accounts: list[FinancialAccountOut]
    positions: list[PositionOut]
    ownership_edges: list[OwnershipEdgeOut]
    integrity: FinancialGraphIntegrity
    projection_diagnostic: ProjectionDiagnostic
