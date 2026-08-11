from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AdvisorTriggerStatus,
    BehaviorInterventionStatus,
    BehaviorObservationType,
    MonitoringAlertStatus,
    MonitoringCadence,
    MonitoringComparator,
    MonitoringPolicyType,
    MonitoringSeverity,
    RiskLimitEffect,
)


class BehaviorObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_type: BehaviorObservationType
    signal_strength: Decimal = Field(ge=0, le=1, max_digits=9, decimal_places=6)
    occurrence_count: int = Field(default=1, ge=1, le=10000)
    observed_at: datetime | None = None
    source_reference: str = Field(min_length=1, max_length=160)
    financial_event_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class MonitoringEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_date: date | None = None
    market_shock: bool = False
    hard_facts_changed: bool = False
    customer_confirmation_id: str | None = None
    observations: list[BehaviorObservationInput] = Field(default_factory=list, max_length=100)
    is_user_confirmed: Literal[True]


class MonitoringPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_type: MonitoringPolicyType
    metric: str
    comparator: MonitoringComparator
    threshold: Decimal
    cadence: MonitoringCadence
    severity: MonitoringSeverity
    active: bool
    effective_from: date
    effective_to: date | None
    rule_version: str


class MonitoringAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    monitoring_policy_id: str
    financial_event_id: str | None
    policy_type: MonitoringPolicyType
    trigger_reason: str
    client_impact: str
    severity: MonitoringSeverity
    recommended_action: str
    do_not_sell_flag: bool
    required_specialist: str | None
    evidence_snapshot: dict[str, Any]
    status: MonitoringAlertStatus
    detected_at: datetime
    resolved_at: datetime | None


class MonitoringAlertsResponse(BaseModel):
    household_id: str
    rule_version: str
    alerts: list[MonitoringAlertOut]


class BehaviorObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    observation_type: BehaviorObservationType
    observed_at: datetime
    signal_strength: Decimal
    occurrence_count: int
    risk_limit_effect: RiskLimitEffect
    hard_facts_changed: bool
    source_reference: str
    evidence_snapshot: dict[str, Any]


class MonitoringEvaluateResponse(BaseModel):
    household_id: str
    analysis_date: date
    rule_version: str
    evaluated_policy_count: int
    triggered_policy_count: int
    resolved_alert_count: int
    policies: list[MonitoringPolicyOut]
    alerts: list[MonitoringAlertOut]
    observations: list[BehaviorObservationOut]
    intervention_ids: list[str]


class BehaviorInterventionRecordOut(BaseModel):
    id: str
    status: BehaviorInterventionStatus
    intervention_code: str
    name: str
    trigger_biases: list[str]
    scenario_code: str
    personalized_message: str
    action_instruction: str
    cooling_period_hours: int | None
    starts_at: datetime
    eligible_at: datetime | None
    evidence: dict[str, Any]


class BehaviorInterventionsResponse(BaseModel):
    household_id: str
    interventions: list[BehaviorInterventionRecordOut]


class NextBestActionOut(BaseModel):
    action_code: str
    household_id: str
    priority: int = Field(ge=0)
    trigger_reason: str
    client_impact: str
    recommended_action: str
    do_not_sell_flag: bool
    required_specialist: str | None
    evidence: dict[str, Any]
    due_date: date | None


class NextBestActionsResponse(BaseModel):
    household_id: str
    outcome: Literal["ACTIONS_AVAILABLE", "NO_ACTION_REQUIRED"]
    actions: list[NextBestActionOut]
    boundary: str


class AdvisorActionCenterItem(BaseModel):
    trigger_id: str
    household_id: str
    household_code: str
    household_name: str
    trigger_type: str
    urgency: MonitoringSeverity
    reason: str
    required_role: str
    follow_up_due: date | None
    status: AdvisorTriggerStatus
    action_item_id: str | None
    action_code: str | None
    action_type: str | None
    title: str | None
    do_not_sell_flag: bool
    required_specialist: str | None
    evidence: dict[str, Any]


class AdvisorActionCenterResponse(BaseModel):
    items: list[AdvisorActionCenterItem]
    open_count: int
    overdue_count: int
    boundary: str
