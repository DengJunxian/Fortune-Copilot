from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.assessment import BehaviorAssessmentCreate, RiskAssessmentCreate
from app.schemas.family import ConsentRecordCreate, HouseholdCreate, HouseholdMemberCreate
from app.schemas.finance import (
    AssetCreate,
    ExpenseItemCreate,
    FinancialGoalCreate,
    IncomeSourceCreate,
    InsurancePolicyCreate,
    LiabilityCreate,
    SocialSecurityAccountCreate,
)


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
    dataset_version: str
    as_of_date: date
    households: list[SyntheticHouseholdBundle] = Field(min_length=3, max_length=3)
