from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ProductRiskLevel, RiskLevel, SuitabilityStatus
from app.schemas.records import Money, Ratio

FundCategory = Literal[
    "money_market",
    "short_bond",
    "pure_bond",
    "domestic_broad_index",
    "pension_bond_fof",
    "pension_broad_index",
]
AdvisorySleeveCode = Literal[
    "daily_liquidity",
    "stable_capital",
    "personal_pension",
    "long_term_growth",
]
EvidenceSupport = Literal[
    "product_identity",
    "fund_terms",
    "icbc_public_listing",
    "pension_eligibility",
    "regulatory_rule",
]


class FundEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^[a-z0-9_\-]+$")
    title: str = Field(min_length=2, max_length=240)
    issuer: str = Field(min_length=2, max_length=120)
    url: str = Field(pattern=r"^https://", max_length=1200)
    published_or_as_of: date | None = None
    verified_on: date
    supports: list[EvidenceSupport] = Field(min_length=1)
    note: str = Field(min_length=2, max_length=600)


class VerifiedFundProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(min_length=4, max_length=180)
    short_name: str = Field(min_length=2, max_length=80)
    manager: str = Field(min_length=4, max_length=120)
    share_class: str = Field(min_length=1, max_length=24)
    category: FundCategory
    trade_venue: Literal["off_exchange", "exchange"]
    tracked_index: str | None = Field(default=None, max_length=120)
    broad_index: bool
    sector_or_thematic: Literal[False] = False
    leveraged: Literal[False] = False
    inverse: Literal[False] = False
    qdii: bool = False
    internal_risk_level: ProductRiskLevel
    minimum_holding_days: int = Field(ge=0, le=3650)
    normal_redemption_note: str = Field(min_length=2, max_length=500)
    eligible_sleeves: list[AdvisorySleeveCode] = Field(min_length=1)
    personal_pension_eligible: bool
    icbc_publicly_listed: bool
    icbc_channel_status: Literal[
        "official_public_listing_app_confirmation_required",
        "not_verified",
    ]
    icbc_channel_note: str = Field(min_length=2, max_length=600)
    principal_guaranteed: Literal[False] = False
    selection_priority: int = Field(ge=1, le=100)
    evidence: list[FundEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_real_product_boundaries(self) -> VerifiedFundProduct:
        supports = {support for item in self.evidence for support in item.supports}
        if "product_identity" not in supports or "fund_terms" not in supports:
            raise ValueError("真实基金必须同时具备产品身份与基金条款证据")
        if self.icbc_publicly_listed and "icbc_public_listing" not in supports:
            raise ValueError("标记工行公开列示必须具备工行官方证据")
        if self.personal_pension_eligible and "pension_eligibility" not in supports:
            raise ValueError("个人养老金产品必须具备证监会名录证据")
        if self.category in {"domestic_broad_index", "pension_broad_index"}:
            if not self.broad_index or not self.tracked_index:
                raise ValueError("权益指数产品必须是可核验的宽基指数产品")
        elif self.broad_index or self.tracked_index:
            raise ValueError("非指数基金不得标记跟踪指数")
        if self.category.startswith("pension_") != self.personal_pension_eligible:
            raise ValueError("养老产品分类与个人养老金资格必须一致")
        return self


class VerifiedFundCatalogFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_code: str
    catalog_version: str
    data_date: date
    verified_on: date
    verification_expiry_days: int = Field(ge=1, le=366)
    source_type: Literal["verified_real_public_funds"] = "verified_real_public_funds"
    scope: str
    mandatory_channel_notice: str
    personal_pension_catalog_observation: str
    products: list[VerifiedFundProduct] = Field(min_length=7)

    @model_validator(mode="after")
    def validate_catalog(self) -> VerifiedFundCatalogFile:
        codes = [item.code for item in self.products]
        if len(codes) != len(set(codes)):
            raise ValueError("真实基金代码必须唯一")
        if not any(item.personal_pension_eligible for item in self.products):
            raise ValueError("目录必须包含经核验个人养老金基金")
        return self


class VerifiedFundCatalogResponse(BaseModel):
    catalog_code: str
    catalog_version: str
    data_date: date
    verified_on: date
    source_type: Literal["verified_real_public_funds"]
    catalog_stale: bool
    scope: str
    mandatory_channel_notice: str
    personal_pension_catalog_observation: str
    product_count: int
    products: list[VerifiedFundProduct]


class AdvisoryCandidate(BaseModel):
    product_code: str = Field(pattern=r"^\d{6}$")
    product_name: str
    role: str
    status: Literal["eligible", "channel_verification_required"]
    reason: str


class AdvisoryAllocation(BaseModel):
    allocation_type: Literal["bank_cash_reserve", "fund", "unallocated_guardrail"]
    ratio: Ratio
    amount: Money
    product_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    product_name: str | None = None
    product_risk_level: ProductRiskLevel | None = None
    icbc_publicly_listed: bool | None = None
    purchase_route: str
    reasons: list[str] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_allocation_identity(self) -> AdvisoryAllocation:
        if self.allocation_type == "fund" and not self.product_code:
            raise ValueError("基金分配必须有真实的六位基金代码")
        if self.allocation_type != "fund" and self.product_code is not None:
            raise ValueError("现金或守门分配不得伪装成基金")
        return self


class AdvisorySleeve(BaseModel):
    sleeve_code: AdvisorySleeveCode
    name: str
    source_amount: Money
    status: Literal[
        "recommended",
        "education_only",
        "not_applicable",
        "channel_verification_required",
    ]
    objective: str
    allocations: list[AdvisoryAllocation]
    candidate_products: list[AdvisoryCandidate] = Field(default_factory=list)
    guardrails: list[str] = Field(min_length=1)
    explanation: str

    @model_validator(mode="after")
    def validate_allocation_totals(self) -> AdvisorySleeve:
        if self.source_amount == 0:
            if self.allocations:
                raise ValueError("零金额用途不得生成分配")
            return self
        if not self.allocations:
            raise ValueError("非零金额用途必须明确分配或守门保留")
        if sum((item.ratio for item in self.allocations), Decimal("0")) != Decimal("1"):
            raise ValueError("用途分配比例必须精确合计为 100%")
        if sum((item.amount for item in self.allocations), Decimal("0")) != self.source_amount:
            raise ValueError("用途分配金额必须精确等于来源金额")
        return self


class FundAdvisoryMeta(BaseModel):
    household_id: str
    household_code: str
    analysis_date: date
    data_as_of: date
    input_version: str
    engine_version: str
    catalog_version: str
    catalog_data_date: date
    catalog_stale: bool
    icbc_only: bool
    calculation_source: Literal["deterministic_tools"] = "deterministic_tools"
    currency: str = "CNY"
    synthetic_data: bool


class FundAdvisoryResponse(BaseModel):
    meta: FundAdvisoryMeta
    effective_customer_risk: RiskLevel
    family_safety_status: SuitabilityStatus
    sleeves: list[AdvisorySleeve] = Field(min_length=4, max_length=4)
    catalog: VerifiedFundCatalogResponse
    hard_boundaries: list[str] = Field(min_length=1)
    execution_checklist: list[str] = Field(min_length=1)
    disclaimer: str
