from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    BehaviorObservationType,
    MonitoringCadence,
    MonitoringComparator,
    MonitoringPolicyType,
    MonitoringSeverity,
    RiskLimitEffect,
)
from app.models.monitoring import MonitoringPolicy


class MonitoringPolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_type: MonitoringPolicyType
    metric: str = Field(min_length=1, max_length=80)
    comparator: MonitoringComparator
    threshold: Decimal
    cadence: MonitoringCadence
    severity: MonitoringSeverity
    client_impact: str = Field(min_length=1, max_length=800)
    recommended_action: str = Field(min_length=1, max_length=1000)
    action_type: str = Field(min_length=1, max_length=64)
    required_role: Literal["advisor", "compliance"] = "advisor"
    required_specialist: str | None = Field(default=None, max_length=40)
    do_not_sell_flag: Literal[True] = True
    due_days: int = Field(ge=0, le=365)


class MonitoringRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["v5-monitoring-and-triggers"]
    semantic_version: str
    formula_version: str
    effective_from: date
    source_type: Literal["internal_demo"]
    source_summary: str
    policies: list[MonitoringPolicyRule]
    behavior_risk_effects: dict[BehaviorObservationType, RiskLimitEffect]
    behavior_intervention_threshold: Decimal = Field(ge=0, le=1)
    behavior_lookback_days: int = Field(ge=1, le=365)
    cooling_period_hours: int = Field(ge=1, le=168)

    @model_validator(mode="after")
    def validate_complete_policy_catalog(self) -> MonitoringRules:
        policy_types = [item.policy_type for item in self.policies]
        if len(policy_types) != len(set(policy_types)):
            raise ValueError("monitoring policy_type must be unique")
        if set(policy_types) != set(MonitoringPolicyType):
            raise ValueError("monitoring rules must cover every policy type")
        if set(self.behavior_risk_effects) != set(BehaviorObservationType):
            raise ValueError("behavior risk effects must cover every observation type")
        if any(
            effect not in {RiskLimitEffect.MAINTAIN, RiskLimitEffect.REDUCE}
            for effect in self.behavior_risk_effects.values()
        ):
            raise ValueError("behavior observations may only maintain or reduce risk limits")
        return self

    def by_type(self) -> dict[MonitoringPolicyType, MonitoringPolicyRule]:
        return {item.policy_type: item for item in self.policies}


@lru_cache(maxsize=4)
def load_monitoring_rules(path: str) -> MonitoringRules:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return MonitoringRules.model_validate(payload)


def ensure_monitoring_policies(
    session: Session,
    household_id: str,
    rules: MonitoringRules,
    analysis_date: date,
) -> list[MonitoringPolicy]:
    existing = {
        item.policy_type: item
        for item in session.scalars(
            select(MonitoringPolicy).where(
                MonitoringPolicy.household_id == household_id,
                MonitoringPolicy.rule_version == rules.semantic_version,
            )
        ).all()
    }
    records: list[MonitoringPolicy] = []
    for policy_rule in rules.policies:
        record = existing.get(policy_rule.policy_type)
        values = {
            "metric": policy_rule.metric,
            "comparator": policy_rule.comparator,
            "threshold": policy_rule.threshold,
            "cadence": policy_rule.cadence,
            "severity": policy_rule.severity,
            "effective_from": rules.effective_from,
            "effective_to": None,
        }
        if record is None:
            record = MonitoringPolicy(
                household_id=household_id,
                policy_type=policy_rule.policy_type,
                rule_version=rules.semantic_version,
                active=True,
                **values,
                valuation_date=analysis_date,
                data_source="v5_monitoring_policy_catalog",
                is_user_confirmed=True,
            )
            session.add(record)
        else:
            changed = any(getattr(record, key) != value for key, value in values.items())
            if changed or record.is_deleted:
                for key, value in values.items():
                    setattr(record, key, value)
                record.is_deleted = False
                record.deleted_at = None
                record.version += 1
                record.valuation_date = analysis_date
        records.append(record)
    session.flush()
    return records
