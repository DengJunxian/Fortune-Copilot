from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.assessment import BehaviorAssessmentCreate, RiskAssessmentCreate
from app.schemas.family import ConsentRecordCreate, HouseholdCreate, HouseholdMemberCreate
from app.schemas.family_enterprise import (
    EnterpriseCashflowDraft,
    EnterpriseCreate,
    EnterpriseEventDraft,
    EnterpriseGuaranteeDraft,
    EnterpriseOwnershipDraft,
    EnterpriseValuationDraft,
)
from app.schemas.finance import (
    AssetCreate,
    ExpenseItemCreate,
    FinancialGoalCreate,
    IncomeSourceCreate,
    InsurancePolicyCreate,
    LiabilityCreate,
    SocialSecurityAccountCreate,
)


class SyntheticPersonaDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^DEMO_[A-H]$")
    title: str = Field(min_length=1, max_length=120)
    archetype: str = Field(min_length=1, max_length=80)
    validation_focus: list[str] = Field(min_length=1)


class SyntheticEnterpriseBundle(BaseModel):
    """Stable-name seed transport mapped into the canonical V5 enterprise model."""

    model_config = ConfigDict(extra="forbid")

    household_code: str = Field(pattern=r"^[A-Z0-9_-]+$")
    enterprise: EnterpriseCreate
    ownerships: list[EnterpriseOwnershipDraft] = Field(default_factory=list, max_length=50)
    valuations: list[EnterpriseValuationDraft] = Field(default_factory=list, max_length=20)
    cashflows: list[EnterpriseCashflowDraft] = Field(default_factory=list, max_length=50)
    guarantees: list[EnterpriseGuaranteeDraft] = Field(default_factory=list, max_length=50)
    liquidity_events: list[EnterpriseEventDraft] = Field(default_factory=list, max_length=50)
    source_reference: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def require_exposure(self) -> SyntheticEnterpriseBundle:
        if not any(
            (
                self.ownerships,
                self.valuations,
                self.cashflows,
                self.guarantees,
                self.liquidity_events,
            )
        ):
            raise ValueError("V5 合成企业至少需要一项暴露资料")
        return self


class SyntheticHouseholdBundle(BaseModel):
    household: HouseholdCreate
    members: list[HouseholdMemberCreate] = Field(min_length=1)
    consents: list[ConsentRecordCreate] = Field(min_length=1)
    incomes: list[IncomeSourceCreate] = Field(min_length=1)
    expenses: list[ExpenseItemCreate] = Field(min_length=1)
    assets: list[AssetCreate] = Field(min_length=1)
    liabilities: list[LiabilityCreate] = Field(default_factory=list)
    insurance_policies: list[InsurancePolicyCreate] = Field(min_length=1)
    social_security_accounts: list[SocialSecurityAccountCreate] = Field(default_factory=list)
    goals: list[FinancialGoalCreate] = Field(min_length=1)
    risk_assessments: list[RiskAssessmentCreate] = Field(min_length=1)
    behavior_assessments: list[BehaviorAssessmentCreate] = Field(min_length=1)


class SyntheticDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "canonical-v4-household-v1",
        "canonical-v5-persona-v2",
    ] = "canonical-v4-household-v1"
    dataset_version: str
    as_of_date: date
    personas: list[SyntheticPersonaDescriptor] = Field(default_factory=list, max_length=32)
    households: list[SyntheticHouseholdBundle] = Field(min_length=3, max_length=32)
    enterprise_extensions: list[SyntheticEnterpriseBundle] = Field(
        default_factory=list,
        max_length=32,
    )

    @model_validator(mode="after")
    def validate_dataset_grain_and_references(self) -> SyntheticDataset:
        bundles = {item.household.code: item for item in self.households}
        if len(bundles) != len(self.households):
            raise ValueError("合成家庭 code 必须在家庭粒度唯一")
        if not all(item.household.is_synthetic for item in self.households):
            raise ValueError("合成数据集不得包含非合成家庭")

        profile_codes = [item.household.demo_profile for item in self.households]
        if len(profile_codes) != len(set(profile_codes)):
            raise ValueError("合成家庭 demo_profile 必须唯一")

        if self.schema_version == "canonical-v5-persona-v2":
            required = {f"DEMO_{letter}" for letter in "ABCDEFGH"}
            if set(bundles) != required:
                raise ValueError("Persona V2 必须且只能包含 DEMO_A 至 DEMO_H")
            if {item.code for item in self.personas} != required:
                raise ValueError("Persona V2 描述符必须完整覆盖 DEMO_A 至 DEMO_H")

        for extension in self.enterprise_extensions:
            bundle = bundles.get(extension.household_code)
            if bundle is None:
                raise ValueError("企业扩展引用了不存在的合成家庭")
            members = {item.display_name for item in bundle.members}
            if len(members) != len(bundle.members):
                raise ValueError("同一合成家庭的成员显示名必须唯一")
            owner_references = {item.owner_entity_id for item in extension.ownerships}
            member_references = {
                item.member_id
                for item in extension.cashflows
                if item.member_id is not None
            } | {
                item.member_id
                for item in extension.guarantees
                if item.member_id is not None
            }
            invalid = (owner_references | member_references) - members - {"@household"}
            if invalid:
                raise ValueError(f"企业扩展成员引用不存在：{','.join(sorted(invalid))}")
        return self
