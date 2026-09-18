from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from threading import Lock
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import AuditEventType, ClientProfileStatus
from app.models.client_profile import ClientWealthProfile, WealthNeed
from app.models.common import utc_now
from app.models.liability import LiabilityStream, LiabilityStreamCashflow
from app.models.wealth_graph import FinancialEntity
from app.schemas.liability import (
    LiabilityCalendarEntry,
    LiabilityCalendarMeta,
    LiabilityCalendarResponse,
    LiabilityCalendarSummary,
    LiabilityStreamCashflowOut,
    LiabilityStreamCreate,
    LiabilityStreamCreateResponse,
    LiabilityStreamDraft,
    LiabilityStreamOut,
)
from app.services.crud import (
    add_audit_event,
    commit_session,
    ensure_household,
    ensure_household_reference,
)
from app.services.financial.facts import load_household_facts
from app.services.liability_engine.adapters import adapt_goals_and_responsibilities
from app.services.liability_engine.rules import (
    LiabilityRules,
    ensure_liability_rule_version,
    load_liability_rules,
)
from app.services.liability_engine.schedule import build_schedule

_STREAM_LOCKS = tuple(Lock() for _ in range(64))


def _need_links(session: Session, household_id: str) -> dict[str, tuple[str, str | None]]:
    profile = session.scalar(
        select(ClientWealthProfile)
        .where(
            ClientWealthProfile.household_id == household_id,
            ClientWealthProfile.status.in_(
                [ClientProfileStatus.ACTIVE, ClientProfileStatus.NEEDS_REVIEW]
            ),
            ClientWealthProfile.is_deleted.is_(False),
        )
        .order_by(ClientWealthProfile.profile_version.desc())
    )
    if profile is None:
        return {}
    needs = session.scalars(
        select(WealthNeed).where(
            WealthNeed.household_id == household_id,
            WealthNeed.profile_id == profile.id,
            WealthNeed.is_deleted.is_(False),
        )
    ).all()
    links: dict[str, tuple[str, str | None]] = {}
    for need in needs:
        for source_id in need.source_record_ids:
            links.setdefault(str(source_id), (need.id, need.beneficiary_entity_id))
    return links


def _stream_values(draft: LiabilityStreamDraft) -> dict[str, Any]:
    return draft.model_dump(mode="python")


def _derived_key(stream: LiabilityStream) -> tuple[str, str] | None:
    if stream.source_goal_id is not None:
        return ("goal", stream.source_goal_id)
    if stream.source_responsibility_id is not None:
        return ("responsibility", stream.source_responsibility_id)
    return None


def _draft_key(draft: LiabilityStreamDraft) -> tuple[str, str]:
    if draft.source_goal_id is not None:
        return ("goal", draft.source_goal_id)
    if draft.source_responsibility_id is not None:
        return ("responsibility", draft.source_responsibility_id)
    raise ValueError("derived stream draft requires a source record")


def _soft_delete_cashflows(
    session: Session,
    stream: LiabilityStream,
    actor: ActorContext,
) -> None:
    now = utc_now()
    rows = session.scalars(
        select(LiabilityStreamCashflow).where(
            LiabilityStreamCashflow.liability_stream_id == stream.id,
            LiabilityStreamCashflow.is_deleted.is_(False),
        )
    ).all()
    for row in rows:
        row.is_deleted = True
        row.deleted_at = now
        row.updated_at = now
        row.version += 1
        add_audit_event(
            session,
            row,
            actor,
            AuditEventType.DATA_DELETED,
            "负债流现金流随来源记录失效",
        )


def _sync_cashflows(
    session: Session,
    stream: LiabilityStream,
    rules: LiabilityRules,
    actor: ActorContext,
) -> None:
    drafts = build_schedule(stream, rules.formula_version)
    existing = {
        row.sequence: row
        for row in session.scalars(
            select(LiabilityStreamCashflow).where(
                LiabilityStreamCashflow.liability_stream_id == stream.id
            )
        ).all()
    }
    now = utc_now()
    active_sequences: set[int] = set()
    for draft in drafts:
        active_sequences.add(draft.sequence)
        row = existing.get(draft.sequence)
        values = draft.model_dump(mode="python")
        if row is None:
            row = LiabilityStreamCashflow(
                household_id=stream.household_id,
                liability_stream_id=stream.id,
                **values,
                currency=stream.currency,
                valuation_date=stream.valuation_date,
                data_source="v5_liability_schedule_engine",
                is_user_confirmed=stream.is_user_confirmed,
            )
            session.add(row)
            session.flush()
            add_audit_event(
                session,
                row,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                f"生成负债流第 {draft.sequence} 期现金流",
            )
            continue
        changed = row.is_deleted or any(getattr(row, key) != value for key, value in values.items())
        if changed:
            for key, value in values.items():
                setattr(row, key, value)
            row.is_deleted = False
            row.deleted_at = None
            row.currency = stream.currency
            row.valuation_date = stream.valuation_date
            row.updated_at = now
            row.version += 1
            add_audit_event(
                session,
                row,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                f"重算负债流第 {draft.sequence} 期现金流",
            )
    for sequence, row in existing.items():
        if sequence not in active_sequences and not row.is_deleted:
            row.is_deleted = True
            row.deleted_at = now
            row.updated_at = now
            row.version += 1
            add_audit_event(
                session,
                row,
                actor,
                AuditEventType.DATA_DELETED,
                "过期负债流现金流软删除",
            )


def _sync_derived_stream(
    session: Session,
    household_id: str,
    draft: LiabilityStreamDraft,
    existing: LiabilityStream | None,
    rules: LiabilityRules,
    actor: ActorContext,
    analysis_date: date,
) -> LiabilityStream:
    values = _stream_values(draft)
    if existing is None:
        stream = LiabilityStream(
            household_id=household_id,
            **values,
            valuation_date=analysis_date,
        )
        session.add(stream)
        session.flush()
        add_audit_event(
            session,
            stream,
            actor,
            AuditEventType.CALCULATION_EXECUTED,
            "从既有目标或责任生成负债流",
        )
    else:
        stream = existing
        changed = stream.is_deleted or any(
            getattr(stream, key) != value for key, value in values.items()
        )
        if changed:
            for key, value in values.items():
                setattr(stream, key, value)
            stream.is_deleted = False
            stream.deleted_at = None
            stream.valuation_date = analysis_date
            stream.updated_at = utc_now()
            stream.version += 1
            add_audit_event(
                session,
                stream,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                "来源事实变化后重算负债流",
            )
    _sync_cashflows(session, stream, rules, actor)
    return stream


def _active_records(
    session: Session,
    household_id: str,
) -> tuple[tuple[LiabilityStream, ...], tuple[LiabilityStreamCashflow, ...]]:
    streams = tuple(
        session.scalars(
            select(LiabilityStream)
            .where(
                LiabilityStream.household_id == household_id,
                LiabilityStream.is_deleted.is_(False),
            )
            .order_by(LiabilityStream.start_date, LiabilityStream.id)
        ).all()
    )
    stream_ids = [stream.id for stream in streams]
    cashflows = (
        tuple(
            session.scalars(
                select(LiabilityStreamCashflow)
                .where(
                    LiabilityStreamCashflow.liability_stream_id.in_(stream_ids),
                    LiabilityStreamCashflow.is_deleted.is_(False),
                )
                .order_by(
                    LiabilityStreamCashflow.due_date,
                    LiabilityStreamCashflow.sequence,
                )
            ).all()
        )
        if stream_ids
        else ()
    )
    return streams, cashflows


def _prepared_amount(stream: LiabilityStream) -> Decimal:
    return sum(
        (Decimal(str(item.get("amount", "0"))) for item in stream.funding_sources),
        Decimal("0.00"),
    )


def _response(
    session: Session,
    household_id: str,
    rules: LiabilityRules,
    analysis_date: date,
) -> LiabilityCalendarResponse:
    streams, cashflows = _active_records(session, household_id)
    grouped: dict[str, list[LiabilityStreamCashflow]] = {item.id: [] for item in streams}
    for cashflow in cashflows:
        grouped[cashflow.liability_stream_id].append(cashflow)
    entries: list[LiabilityCalendarEntry] = []
    for stream in streams:
        rows = grouped[stream.id]
        target_total = sum((row.target_amount for row in rows), Decimal("0.00"))
        minimum_total = sum((row.minimum_amount for row in rows), Decimal("0.00"))
        prepared_amount = min(target_total, _prepared_amount(stream))
        entries.append(
            LiabilityCalendarEntry(
                stream=LiabilityStreamOut.model_validate(stream),
                cashflows=[LiabilityStreamCashflowOut.model_validate(row) for row in rows],
                target_total=target_total,
                minimum_total=minimum_total,
                prepared_amount=prepared_amount,
                funding_gap=max(Decimal("0.00"), target_total - prepared_amount),
            )
        )
    target_total = sum((item.target_total for item in entries), Decimal("0.00"))
    minimum_total = sum((item.minimum_total for item in entries), Decimal("0.00"))
    prepared_total = sum((item.prepared_amount for item in entries), Decimal("0.00"))
    return LiabilityCalendarResponse(
        meta=LiabilityCalendarMeta(
            household_id=household_id,
            analysis_date=analysis_date,
            data_as_of=analysis_date,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
            adapter_sources=["financial_goals", "responsibilities"],
        ),
        summary=LiabilityCalendarSummary(
            stream_count=len(entries),
            cashflow_count=len(cashflows),
            target_total=target_total,
            minimum_total=minimum_total,
            prepared_total=prepared_total,
            funding_gap=max(Decimal("0.00"), target_total - prepared_total),
            next_due_date=min(
                (row.due_date for row in cashflows if row.due_date >= analysis_date),
                default=None,
            ),
        ),
        entries=entries,
    )


def materialize_liability_streams(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> LiabilityCalendarResponse:
    stream_lock = _STREAM_LOCKS[hash(household_id) % len(_STREAM_LOCKS)]
    with stream_lock:
        ensure_household(session, household_id)
        facts = load_household_facts(session, household_id)
        rules = load_liability_rules(rules_path)
        ensure_liability_rule_version(session, rules)
        drafts = adapt_goals_and_responsibilities(
            facts,
            rules,
            analysis_date,
            _need_links(session, household_id),
        )
        all_derived = [
            stream
            for stream in session.scalars(
                select(LiabilityStream).where(
                    LiabilityStream.household_id == household_id,
                    (LiabilityStream.source_goal_id.is_not(None))
                    | (LiabilityStream.source_responsibility_id.is_not(None)),
                )
            ).all()
        ]
        by_key = {
            key: stream for stream in all_derived if (key := _derived_key(stream)) is not None
        }
        active_keys: set[tuple[str, str]] = set()
        for draft in drafts:
            key = _draft_key(draft)
            active_keys.add(key)
            _sync_derived_stream(
                session,
                household_id,
                draft,
                by_key.get(key),
                rules,
                actor,
                analysis_date,
            )
        now = utc_now()
        for key, stream in by_key.items():
            if key not in active_keys and not stream.is_deleted:
                stream.is_deleted = True
                stream.deleted_at = now
                stream.updated_at = now
                stream.version += 1
                add_audit_event(
                    session,
                    stream,
                    actor,
                    AuditEventType.DATA_DELETED,
                    "来源目标或责任已失效，负债流同步软删除",
                )
                _soft_delete_cashflows(session, stream, actor)
        commit_session(session)
        return _response(session, household_id, rules, analysis_date)


def create_liability_stream(
    session: Session,
    household_id: str,
    payload: LiabilityStreamCreate,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> LiabilityStreamCreateResponse:
    ensure_household(session, household_id)
    ensure_household_reference(session, WealthNeed, payload.wealth_need_id, household_id)
    ensure_household_reference(
        session,
        FinancialEntity,
        payload.beneficiary_entity_id,
        household_id,
    )
    rules = load_liability_rules(rules_path)
    ensure_liability_rule_version(session, rules)
    values = payload.model_dump(mode="python")
    canonical = json.dumps(
        values,
        default=str,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    values["funding_sources"] = [item.model_dump(mode="json") for item in payload.funding_sources]
    values["valuation_date"] = payload.valuation_date or analysis_date
    stream = LiabilityStream(
        household_id=household_id,
        source_goal_id=None,
        source_responsibility_id=None,
        stream_version=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        **values,
    )
    session.add(stream)
    session.flush()
    add_audit_event(
        session,
        stream,
        actor,
        AuditEventType.DATA_CREATED,
        "客户确认新增自定义负债流",
    )
    _sync_cashflows(session, stream, rules, actor)
    commit_session(session)
    response = _response(session, household_id, rules, analysis_date)
    entry = next(item for item in response.entries if item.stream.id == stream.id)
    return LiabilityStreamCreateResponse(meta=response.meta, entry=entry)
