from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import AuditEventType, FinancialEventDomain, FinancialEventStatus
from app.models.common import utc_now
from app.models.financial_twin import FinancialEvent
from app.schemas.family_enterprise import (
    EnterpriseExposureCreate,
    EnterpriseExposureResponse,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.financial_twin.engine import materialize_current_twin
from app.services.financial_twin.snapshot import load_snapshot

from .engine import get_family_enterprise_view
from .repository import EnterpriseEventDescriptor, upsert_enterprise_exposures


def _event_hash(
    household_id: str,
    source_reference: str,
    descriptor: EnterpriseEventDescriptor,
) -> str:
    canonical = json.dumps(
        {
            "household_id": household_id,
            "source_reference": source_reference,
            "enterprise_id": descriptor.enterprise_id,
            "event_type": descriptor.event_type.value,
            "effective_date": descriptor.effective_date.isoformat(),
            "estimated_value": descriptor.estimated_value,
            "currency": descriptor.currency,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _create_events(
    session: Session,
    household_id: str,
    payload: EnterpriseExposureCreate,
    descriptors: tuple[EnterpriseEventDescriptor, ...],
    actor: ActorContext,
) -> list[FinancialEvent]:
    ensure_household(session, household_id)
    events: list[FinancialEvent] = []
    for descriptor in descriptors:
        event_hash = _event_hash(household_id, payload.source_reference, descriptor)
        existing = session.scalar(
            select(FinancialEvent).where(
                FinancialEvent.household_id == household_id,
                FinancialEvent.event_hash == event_hash,
                FinancialEvent.is_deleted.is_(False),
            )
        )
        if existing is not None:
            events.append(existing)
            continue
        event = FinancialEvent(
            household_id=household_id,
            event_domain=FinancialEventDomain.ENTERPRISE,
            event_type=descriptor.event_type.value,
            effective_at=datetime.combine(descriptor.effective_date, time.min, tzinfo=UTC),
            recorded_at=utc_now(),
            source_kind="user_confirmed_enterprise_event",
            source_reference=payload.source_reference,
            confirmation_status=FinancialEventStatus.CONFIRMED,
            payload={
                "enterprise_id": descriptor.enterprise_id,
                "estimated_value": descriptor.estimated_value,
                "currency": descriptor.currency,
                **descriptor.payload,
            },
            event_hash=event_hash,
            processed_snapshot_id=None,
            currency=descriptor.currency,
            valuation_date=descriptor.effective_date,
            data_source="v5_family_enterprise_event",
            is_user_confirmed=True,
        )
        session.add(event)
        session.flush()
        add_audit_event(
            session,
            event,
            actor,
            AuditEventType.DATA_CREATED,
            "记录已确认家企财务事件",
        )
        events.append(event)
    if events:
        session.commit()
        for event in events:
            session.refresh(event)
    return events


def _events_for_source(
    session: Session,
    household_id: str,
    source_reference: str,
) -> list[FinancialEvent]:
    return list(
        session.scalars(
            select(FinancialEvent).where(
                FinancialEvent.household_id == household_id,
                FinancialEvent.event_domain == FinancialEventDomain.ENTERPRISE,
                FinancialEvent.source_reference == source_reference,
                FinancialEvent.is_deleted.is_(False),
            )
        ).all()
    )


def process_enterprise_exposures(
    session: Session,
    household_id: str,
    payload: EnterpriseExposureCreate,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    client_profile_rules_path: str,
    liability_rules_path: str,
    family_enterprise_rules_path: str,
    analysis_date: date,
) -> EnterpriseExposureResponse:
    materialize_current_twin(
        session,
        household_id,
        actor,
        financial_rules_path=financial_rules_path,
        methodology_rules_path=methodology_rules_path,
        public_data_snapshot_path=public_data_snapshot_path,
        client_profile_rules_path=client_profile_rules_path,
        liability_rules_path=liability_rules_path,
        family_enterprise_rules_path=family_enterprise_rules_path,
        analysis_date=analysis_date,
    )
    write_result = upsert_enterprise_exposures(session, household_id, payload, actor)
    events = _create_events(
        session,
        household_id,
        payload,
        write_result.descriptors,
        actor,
    )
    if not events:
        events = _events_for_source(session, household_id, payload.source_reference)

    if write_result.changed:
        snapshot = materialize_current_twin(
            session,
            household_id,
            actor,
            financial_rules_path=financial_rules_path,
            methodology_rules_path=methodology_rules_path,
            public_data_snapshot_path=public_data_snapshot_path,
            client_profile_rules_path=client_profile_rules_path,
            liability_rules_path=liability_rules_path,
            family_enterprise_rules_path=family_enterprise_rules_path,
            analysis_date=analysis_date,
            force_new=True,
        )
        for event in events:
            event.processed_snapshot_id = snapshot.id
            event.confirmation_status = FinancialEventStatus.PROCESSED
            event.payload = {
                **event.payload,
                "processed": True,
                "snapshot_hash": snapshot.snapshot_hash,
            }
            event.version += 1
            event.updated_at = utc_now()
            add_audit_event(
                session,
                event,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                "家企事件完成经济风险预算与持久快照重算",
            )
        session.commit()
    else:
        processed_id = next(
            (event.processed_snapshot_id for event in events if event.processed_snapshot_id),
            None,
        )
        snapshot = load_snapshot(session, household_id, processed_id)

    view = get_family_enterprise_view(
        session,
        household_id,
        family_enterprise_rules_path,
        analysis_date,
    )
    return EnterpriseExposureResponse(
        view=view,
        financial_event_ids=[event.id for event in events],
        snapshot_id=snapshot.id,
        idempotent_replay=not write_result.changed,
    )
