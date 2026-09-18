from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import Field, model_validator

from app.domain.enums import EmploymentStability, LifecycleStage, RiskLevel
from app.schemas.records import RecordInput, RecordOut, RecordUpdate

CONSENT_SCOPES = {
    "profile",
    "finance",
    "risk",
    "simulation",
    "report",
    "behavior",
    "identity_sensitive",
    "health_sensitive",
    "insurance",
}
SENSITIVE_CONSENT_SCOPES = {"identity_sensitive", "health_sensitive", "insurance"}


class HouseholdCreate(RecordInput):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    lifecycle_stage: LifecycleStage
    region: str = Field(min_length=1, max_length=120)
    demo_profile: str | None = Field(default=None, max_length=32)
    is_synthetic: bool = False
    planning_preferences: dict[str, Any] = Field(default_factory=dict)


class HouseholdUpdate(RecordUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    lifecycle_stage: LifecycleStage | None = None
    region: str | None = Field(default=None, min_length=1, max_length=120)
    demo_profile: str | None = Field(default=None, max_length=32)
    planning_preferences: dict[str, Any] | None = None


class HouseholdOut(RecordOut):
    code: str
    name: str
    lifecycle_stage: LifecycleStage
    region: str
    demo_profile: str | None
    is_synthetic: bool
    planning_preferences: dict[str, Any]


class HouseholdMemberCreate(RecordInput):
    display_name: str = Field(min_length=1, max_length=80)
    relationship: str = Field(min_length=1, max_length=40)
    birth_date: date
    occupation: str | None = Field(default=None, max_length=120)
    employment_stability: EmploymentStability
    expected_retirement_age: int | None = Field(default=None, ge=45, le=80)
    health_risk_level: RiskLevel = RiskLevel.LOW


class HouseholdMemberUpdate(RecordUpdate):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    relationship: str | None = Field(default=None, min_length=1, max_length=40)
    birth_date: date | None = None
    occupation: str | None = Field(default=None, max_length=120)
    employment_stability: EmploymentStability | None = None
    expected_retirement_age: int | None = Field(default=None, ge=45, le=80)
    health_risk_level: RiskLevel | None = None


class HouseholdMemberOut(RecordOut):
    household_id: str
    display_name: str
    relationship: str
    birth_date: date
    occupation: str | None
    employment_stability: EmploymentStability
    expected_retirement_age: int | None
    health_risk_level: RiskLevel


class ConsentRecordCreate(RecordInput):
    member_id: str | None = None
    scopes: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=1, max_length=300)
    granted_at: datetime
    withdrawn_at: datetime | None = None
    consent_version: str = Field(min_length=1, max_length=32)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_timeline(self) -> ConsentRecordCreate:
        if self.withdrawn_at is not None and self.withdrawn_at < self.granted_at:
            raise ValueError("授权撤回时间不得早于授权时间")
        unknown = sorted(set(self.scopes) - CONSENT_SCOPES)
        if unknown:
            raise ValueError(f"授权包含未知范围：{','.join(unknown)}")
        if len(self.scopes) != len(set(self.scopes)):
            raise ValueError("授权范围不得重复")
        if (
            set(self.scopes) & SENSITIVE_CONSENT_SCOPES
            and self.metadata_json.get("sensitive_data_acknowledged") is not True
        ):
            raise ValueError("身份、健康或保障敏感数据必须单独明示同意")
        if not str(self.metadata_json.get("scenario", "")).strip():
            raise ValueError("授权必须声明具体使用场景")
        if self.metadata_json.get("explicit") is not True:
            raise ValueError("授权必须记录为明示同意")
        return self


class ConsentRecordUpdate(RecordUpdate):
    member_id: str | None = None
    scopes: list[str] | None = Field(default=None, min_length=1)
    purpose: str | None = Field(default=None, min_length=1, max_length=300)
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    consent_version: str | None = Field(default=None, min_length=1, max_length=32)
    metadata_json: dict[str, Any] | None = None


class ConsentRecordOut(RecordOut):
    household_id: str
    member_id: str | None
    scopes: list[str]
    purpose: str
    granted_at: datetime
    withdrawn_at: datetime | None
    consent_version: str
    metadata_json: dict[str, Any]
