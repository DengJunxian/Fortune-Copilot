from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import (
    AuditEventType,
    CFSComponentType,
    ProfessionalSpecialistType,
    SpecializedComplexity,
    WealthNeedType,
)
from app.models.client_profile import WealthNeed
from app.models.specialized_cfs import PhilanthropyGoal
from app.schemas.specialized_cfs import (
    PhilanthropyGoalOut,
    PhilanthropyGoalsResponse,
    SpecializedResponseMeta,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.professional_routing.engine import resolve_professional_route
from app.services.specialized_cfs.common import ZERO, canonical_hash, money
from app.services.specialized_cfs.rules import load_specialized_cfs_rules

BOUNDARY = "公益目标作为家庭需要进入规划，不与产品销售绑定，也不替代公益、税务或法律专业意见。"


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _sync_goals(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> list[PhilanthropyGoal]:
    household = ensure_household(session, household_id)
    rules = load_specialized_cfs_rules(rules_path)
    needs = list(
        session.scalars(
            select(WealthNeed).where(
                WealthNeed.household_id == household_id,
                WealthNeed.need_type == WealthNeedType.PHILANTHROPY,
                WealthNeed.is_deleted.is_(False),
            )
        ).all()
    )
    preferences = household.planning_preferences
    preferred_budget = _decimal(preferences.get("philanthropy_annual_budget"))
    cause = str(preferences.get("philanthropy_target_cause") or "公益方向待确认")
    funding_asset = preferences.get("philanthropy_funding_asset")
    family_participation = str(
        preferences.get("philanthropy_family_participation") or "由家庭共同确认参与方式"
    )
    governance_preference = str(
        preferences.get("philanthropy_governance_preference") or "先明确预算、用途与年度复核"
    )
    drafts: list[dict[str, Any]] = []
    if needs or (preferred_budget is not None and preferred_budget > 0):
        need_budget = money(sum((item.target_amount for item in needs), ZERO))
        annual_budget = money(preferred_budget or need_budget)
        if annual_budget > 0:
            drafts.append(
                {
                    "annual_budget": annual_budget,
                    "target_cause": cause,
                    "funding_asset": str(funding_asset) if funding_asset else None,
                    "time_horizon": rules.philanthropy.default_time_horizon,
                    "family_participation": family_participation,
                    "governance_preference": governance_preference,
                    "professional_review_required": annual_budget
                    >= rules.philanthropy.professional_review_annual_budget,
                }
            )
    existing = list(
        session.scalars(
            select(PhilanthropyGoal).where(PhilanthropyGoal.household_id == household_id)
        ).all()
    )
    by_key = {(item.target_cause, item.time_horizon): item for item in existing}
    active_ids: set[str] = set()
    for values in drafts:
        key = (values["target_cause"], values["time_horizon"])
        record = by_key.get(key)
        if record is None:
            record = PhilanthropyGoal(
                household_id=household_id,
                currency=household.currency,
                valuation_date=analysis_date,
                data_source="v5_philanthropy_engine",
                is_user_confirmed=bool(needs) or preferred_budget is not None,
                **values,
            )
            session.add(record)
            session.flush()
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_CREATED,
                "建立公益目标",
            )
        else:
            changed = any(getattr(record, name) != value for name, value in values.items())
            if changed or record.is_deleted:
                for name, value in values.items():
                    setattr(record, name, value)
                record.is_deleted = False
                record.deleted_at = None
                record.version += 1
                record.valuation_date = analysis_date
                add_audit_event(
                    session,
                    record,
                    actor,
                    AuditEventType.DATA_UPDATED,
                    "更新公益目标",
                )
        active_ids.add(record.id)
    for record in existing:
        if record.id not in active_ids and not record.is_deleted:
            record.is_deleted = True
            record.version += 1
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_UPDATED,
                "公益目标来源失效",
            )
    session.commit()
    return list(
        session.scalars(
            select(PhilanthropyGoal)
            .where(
                PhilanthropyGoal.household_id == household_id,
                PhilanthropyGoal.is_deleted.is_(False),
            )
            .order_by(PhilanthropyGoal.created_at, PhilanthropyGoal.id)
        ).all()
    )


def get_philanthropy_goals(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> PhilanthropyGoalsResponse:
    rules = load_specialized_cfs_rules(rules_path)
    records = _sync_goals(session, household_id, actor, rules_path, analysis_date)
    professional = any(item.professional_review_required for item in records)
    route = resolve_professional_route(
        session,
        household_id,
        need="philanthropy",
        complexity=(
            SpecializedComplexity.MEDIUM
            if professional
            else SpecializedComplexity.LOW
            if records
            else SpecializedComplexity.NONE
        ),
        specialist_type=(
            ProfessionalSpecialistType.PHILANTHROPY_SPECIALIST if professional else None
        ),
        component_types={CFSComponentType.PHILANTHROPY},
        reason="公益预算或治理安排达到专业复核门槛。",
    )
    input_hash = canonical_hash(
        {
            "records": [
                (item.id, item.version, str(item.annual_budget), item.target_cause)
                for item in records
            ],
            "rules": rules.formula_version,
            "analysis_date": analysis_date.isoformat(),
        }
    )
    return PhilanthropyGoalsResponse(
        meta=SpecializedResponseMeta(
            household_id=household_id,
            analysis_date=analysis_date,
            data_as_of=max(
                (item.valuation_date for item in records if item.valuation_date),
                default=None,
            ),
            input_hash=input_hash,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
        ),
        has_explicit_goal=bool(records),
        goals=[PhilanthropyGoalOut.model_validate(item) for item in records],
        route=route,
        boundary=BOUNDARY,
    )
