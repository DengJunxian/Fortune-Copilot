from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from decimal import Decimal
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AuditEventType,
    FinancialEventDomain,
    FinancialEventStatus,
    IncomeType,
)
from app.models.common import utc_now
from app.models.family import HouseholdMember
from app.models.finance import IncomeSource
from app.models.financial_twin import FinancialEvent, LifeEvent
from app.schemas.financial_twin import (
    EventTimelineResponse,
    FinancialEventOut,
    LifeEventCreate,
    LifeEventOut,
    LifeEventProcessResponse,
)
from app.services.crud import (
    add_audit_event,
    ensure_household,
    ensure_household_reference,
)
from app.services.financial.utils import ZERO, annualize, money

from .engine import materialize_current_twin
from .snapshot import compare_snapshots, load_snapshot, snapshot_out

_EVENT_LOCKS = tuple(Lock() for _ in range(64))


def _event_hash(household_id: str, payload: LifeEventCreate) -> str:
    canonical = json.dumps(
        {
            "household_id": household_id,
            **payload.model_dump(mode="json"),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _life_event(session: Session, event_id: str) -> LifeEvent | None:
    return session.scalar(
        select(LifeEvent).where(
            LifeEvent.financial_event_id == event_id,
            LifeEvent.is_deleted.is_(False),
        )
    )


def event_out(session: Session, event: FinancialEvent) -> FinancialEventOut:
    life = _life_event(session, event.id)
    if event.event_domain == FinancialEventDomain.LIFE and life is None:
        raise AppError("life_event_invalid", "事件缺少生活事件明细", status_code=409)
    values = {column.name: getattr(event, column.name) for column in event.__table__.columns}
    values["life_event"] = LifeEventOut.model_validate(life) if life is not None else None
    return FinancialEventOut.model_validate(values)


def _targets(
    session: Session,
    household_id: str,
    payload: LifeEventCreate,
) -> tuple[IncomeSource, ...]:
    filters = [
        IncomeSource.household_id == household_id,
        IncomeSource.income_type == IncomeType.EMPLOYMENT,
        IncomeSource.is_deleted.is_(False),
    ]
    if payload.member_id is not None:
        filters.append(IncomeSource.member_id == payload.member_id)
    if payload.income_source_ids:
        filters.append(IncomeSource.id.in_(payload.income_source_ids))
    records = tuple(
        session.scalars(select(IncomeSource).where(*filters).order_by(IncomeSource.id)).all()
    )
    if payload.income_source_ids and len(records) != len(payload.income_source_ids):
        raise AppError(
            "life_event_income_source_invalid",
            "部分收入来源不存在、不属于该家庭或不是工资收入",
            status_code=422,
        )
    if not records:
        raise AppError(
            "life_event_income_source_missing",
            "当前家庭没有可应用该工资事件的就业收入",
            status_code=422,
        )
    return records


def _apply_salary_change(
    session: Session,
    event: FinancialEvent,
    life: LifeEvent,
    payload: LifeEventCreate,
    actor: ActorContext,
) -> None:
    changes: list[dict[str, str | None]] = []
    annual_impact = ZERO
    now = utc_now()
    for income in _targets(session, event.household_id, payload):
        before = money(income.amount)
        after = money(max(ZERO, before * (Decimal("1") + payload.income_change_ratio)))
        impact = annualize(after, income.frequency) - annualize(before, income.frequency)
        annual_impact += impact
        changes.append(
            {
                "income_source_id": income.id,
                "member_id": income.member_id,
                "name": income.name,
                "before_amount": str(before),
                "after_amount": str(after),
                "frequency": income.frequency.value,
                "annual_impact": str(money(abs(impact)))
                if impact >= 0
                else str(-money(abs(impact))),
            }
        )
        income.amount = after
        income.valuation_date = payload.event_date
        income.data_source = "v5_financial_twin_event"
        income.is_user_confirmed = True
        income.version += 1
        income.updated_at = now
        add_audit_event(
            session,
            income,
            actor,
            AuditEventType.DATA_UPDATED,
            f"应用工资变动 {payload.income_change_ratio:+.1%}",
        )

    life.expected_financial_impact = annual_impact.quantize(Decimal("0.01"))
    life.metadata_json = {**payload.metadata_json, "applied_income_sources": changes}
    event.payload = {
        **event.payload,
        "applied": True,
        "applied_income_sources": changes,
        "annual_impact": str(life.expected_financial_impact),
    }
    event.confirmation_status = FinancialEventStatus.APPLIED
    event.version += 1
    event.updated_at = now
    add_audit_event(
        session,
        event,
        actor,
        AuditEventType.CONFIRMATION_RECORDED,
        "客户确认并应用家庭生活事件",
    )
    session.commit()


def _complete_event(
    session: Session,
    event: FinancialEvent,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    client_profile_rules_path: str,
    liability_rules_path: str,
    analysis_date: date,
    idempotent_replay: bool,
    family_enterprise_rules_path: str | None = None,
) -> LifeEventProcessResponse:
    if event.processed_snapshot_id is not None:
        snapshot = load_snapshot(session, event.household_id, event.processed_snapshot_id)
        previous = (
            load_snapshot(session, event.household_id, snapshot.parent_snapshot_id)
            if snapshot.parent_snapshot_id is not None
            else None
        )
        return LifeEventProcessResponse(
            event=event_out(session, event),
            snapshot=snapshot_out(snapshot),
            comparison=compare_snapshots(previous, snapshot),
            idempotent_replay=True,
        )

    snapshot = materialize_current_twin(
        session,
        event.household_id,
        actor,
        financial_rules_path=financial_rules_path,
        methodology_rules_path=methodology_rules_path,
        public_data_snapshot_path=public_data_snapshot_path,
        client_profile_rules_path=client_profile_rules_path,
        liability_rules_path=liability_rules_path,
        analysis_date=analysis_date,
        force_new=True,
        family_enterprise_rules_path=family_enterprise_rules_path,
    )
    previous = (
        load_snapshot(session, event.household_id, snapshot.parent_snapshot_id)
        if snapshot.parent_snapshot_id is not None
        else None
    )
    event.processed_snapshot_id = snapshot.id
    event.confirmation_status = FinancialEventStatus.PROCESSED
    event.payload = {
        **event.payload,
        "processed": True,
        "snapshot_hash": snapshot.snapshot_hash,
        "monitoring_status": snapshot.state_json.get("monitoring", {}).get("status", "not_enabled"),
    }
    event.version += 1
    event.updated_at = utc_now()
    add_audit_event(
        session,
        event,
        actor,
        AuditEventType.CALCULATION_EXECUTED,
        "生活事件完成画像、需求、责任、ELTC 与监测重算",
    )
    session.commit()
    session.refresh(event)
    return LifeEventProcessResponse(
        event=event_out(session, event),
        snapshot=snapshot_out(snapshot),
        comparison=compare_snapshots(previous, snapshot),
        idempotent_replay=idempotent_replay,
    )


def process_life_event(
    session: Session,
    household_id: str,
    payload: LifeEventCreate,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    client_profile_rules_path: str,
    liability_rules_path: str,
    analysis_date: date,
    family_enterprise_rules_path: str | None = None,
) -> LifeEventProcessResponse:
    if payload.event_date > analysis_date:
        raise AppError(
            "future_life_event_not_effective",
            "未来事件可记录为计划，但当前版本不会提前修改家庭事实",
            status_code=422,
        )
    lock = _EVENT_LOCKS[hash(household_id) % len(_EVENT_LOCKS)]
    with lock:
        household = ensure_household(session, household_id)
        ensure_household_reference(session, HouseholdMember, payload.member_id, household_id)
        event_hash = _event_hash(household_id, payload)
        existing = session.scalar(
            select(FinancialEvent).where(
                FinancialEvent.household_id == household_id,
                FinancialEvent.event_hash == event_hash,
                FinancialEvent.is_deleted.is_(False),
            )
        )
        if existing is not None:
            return _complete_event(
                session,
                existing,
                actor,
                financial_rules_path=financial_rules_path,
                methodology_rules_path=methodology_rules_path,
                public_data_snapshot_path=public_data_snapshot_path,
                client_profile_rules_path=client_profile_rules_path,
                liability_rules_path=liability_rules_path,
                analysis_date=analysis_date,
                idempotent_replay=True,
                family_enterprise_rules_path=family_enterprise_rules_path,
            )

        materialize_current_twin(
            session,
            household_id,
            actor,
            financial_rules_path=financial_rules_path,
            methodology_rules_path=methodology_rules_path,
            public_data_snapshot_path=public_data_snapshot_path,
            client_profile_rules_path=client_profile_rules_path,
            liability_rules_path=liability_rules_path,
            analysis_date=analysis_date,
            family_enterprise_rules_path=family_enterprise_rules_path,
        )
        recorded_at = utc_now()
        event = FinancialEvent(
            household_id=household_id,
            event_domain=FinancialEventDomain.LIFE,
            event_type=payload.life_event_type.value,
            effective_at=datetime.combine(payload.event_date, time.min, tzinfo=UTC),
            recorded_at=recorded_at,
            source_kind="user_confirmed_life_event",
            source_reference=payload.source_reference,
            confirmation_status=FinancialEventStatus.CONFIRMED,
            payload=payload.model_dump(mode="json"),
            event_hash=event_hash,
            processed_snapshot_id=None,
            currency=household.currency,
            valuation_date=payload.event_date,
            data_source="v5_financial_twin_event",
            is_user_confirmed=True,
        )
        session.add(event)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            winner = session.scalar(
                select(FinancialEvent).where(
                    FinancialEvent.household_id == household_id,
                    FinancialEvent.event_hash == event_hash,
                    FinancialEvent.is_deleted.is_(False),
                )
            )
            if winner is None:
                raise
            return _complete_event(
                session,
                winner,
                actor,
                financial_rules_path=financial_rules_path,
                methodology_rules_path=methodology_rules_path,
                public_data_snapshot_path=public_data_snapshot_path,
                client_profile_rules_path=client_profile_rules_path,
                liability_rules_path=liability_rules_path,
                analysis_date=analysis_date,
                idempotent_replay=True,
                family_enterprise_rules_path=family_enterprise_rules_path,
            )
        life = LifeEvent(
            household_id=household_id,
            financial_event_id=event.id,
            member_id=payload.member_id,
            life_event_type=payload.life_event_type,
            event_date=payload.event_date,
            expected_financial_impact=Decimal("0.00"),
            metadata_json=payload.metadata_json,
            currency=household.currency,
            valuation_date=payload.event_date,
            data_source="v5_financial_twin_event",
            is_user_confirmed=True,
        )
        session.add(life)
        session.flush()
        add_audit_event(
            session,
            event,
            actor,
            AuditEventType.DATA_CREATED,
            "记录客户确认的家庭生活事件",
        )
        _apply_salary_change(session, event, life, payload, actor)
        return _complete_event(
            session,
            event,
            actor,
            financial_rules_path=financial_rules_path,
            methodology_rules_path=methodology_rules_path,
            public_data_snapshot_path=public_data_snapshot_path,
            client_profile_rules_path=client_profile_rules_path,
            liability_rules_path=liability_rules_path,
            analysis_date=analysis_date,
            idempotent_replay=False,
            family_enterprise_rules_path=family_enterprise_rules_path,
        )


def event_timeline(session: Session, household_id: str) -> EventTimelineResponse:
    ensure_household(session, household_id)
    events = tuple(
        session.scalars(
            select(FinancialEvent)
            .where(
                FinancialEvent.household_id == household_id,
                FinancialEvent.is_deleted.is_(False),
            )
            .order_by(FinancialEvent.effective_at.desc(), FinancialEvent.recorded_at.desc())
        ).all()
    )
    return EventTimelineResponse(
        household_id=household_id,
        events=[event_out(session, item) for item in events],
        total=len(events),
    )
