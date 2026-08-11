from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from math import ceil
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import AuditEventType
from app.models.common import RecordMixin, utc_now
from app.models.family import Household
from app.models.governance import AuditEvent


def get_active[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    record_id: str,
    *,
    household_id: str | None = None,
) -> ModelT:
    statement = select(model).where(model.id == record_id, model.is_deleted.is_(False))
    if household_id is not None and hasattr(model, "household_id"):
        statement = statement.where(cast(Any, model).household_id == household_id)
    record = session.scalar(statement)
    if record is None:
        raise AppError("not_found", "记录不存在或已删除", status_code=404)
    return record


def ensure_household(session: Session, household_id: str) -> Household:
    return get_active(session, Household, household_id)


def ensure_household_reference[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    record_id: str | None,
    household_id: str,
) -> None:
    if record_id is not None:
        get_active(session, model, record_id, household_id=household_id)


def list_active[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    *,
    page: int,
    page_size: int,
    household_id: str | None = None,
    allowed_household_ids: Sequence[str] | None = None,
) -> tuple[list[ModelT], int, int]:
    filters: list[Any] = [model.is_deleted.is_(False)]
    if household_id is not None and hasattr(model, "household_id"):
        filters.append(cast(Any, model).household_id == household_id)
    if allowed_household_ids is not None and "*" not in allowed_household_ids:
        if model is Household:
            filters.append(cast(Any, model).id.in_(allowed_household_ids))
        elif hasattr(model, "household_id"):
            filters.append(cast(Any, model).household_id.in_(allowed_household_ids))
    total = session.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    statement = (
        select(model)
        .where(*filters)
        .order_by(model.created_at, model.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(session.scalars(statement).all())
    pages = ceil(total / page_size) if total else 0
    return items, total, pages


def _household_id(record: RecordMixin) -> str | None:
    if isinstance(record, Household):
        return record.id
    value = getattr(record, "household_id", None)
    return str(value) if value is not None else None


def add_audit_event(
    session: Session,
    record: RecordMixin,
    actor: ActorContext,
    event_type: AuditEventType,
    summary: str,
) -> None:
    event = AuditEvent(
        household_id=_household_id(record),
        event_type=event_type,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type=record.__class__.__name__,
        entity_id=record.id,
        event_version=record.version,
        summary=summary,
        occurred_at=utc_now(),
        data_source="system",
        is_user_confirmed=True,
    )
    session.add(event)


def commit_session(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "data_conflict",
            "记录与现有数据冲突或引用无效",
            status_code=409,
        ) from exc


def create_record[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    payload: BaseModel,
    actor: ActorContext,
    *,
    household_id: str | None = None,
) -> ModelT:
    values = payload.model_dump(mode="python")
    if household_id is not None:
        values["household_id"] = household_id
    record = model(**values)
    session.add(record)
    try:
        session.flush()
        add_audit_event(
            session,
            record,
            actor,
            AuditEventType.DATA_CREATED,
            "创建记录",
        )
        commit_session(session)
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "data_conflict",
            "记录与现有数据冲突或引用无效",
            status_code=409,
        ) from exc
    session.refresh(record)
    return record


def update_record[ModelT: RecordMixin](
    session: Session,
    record: ModelT,
    payload: BaseModel,
    actor: ActorContext,
) -> ModelT:
    values = payload.model_dump(mode="python", exclude_unset=True)
    expected_version = int(values.pop("expected_version"))
    if record.version != expected_version:
        raise AppError(
            "version_conflict",
            "记录已被其他操作更新，请刷新后重试",
            status_code=409,
            details={"expected": expected_version, "current": record.version},
        )
    for field, value in values.items():
        setattr(record, field, value)
    record.version += 1
    record.updated_at = utc_now()
    add_audit_event(
        session,
        record,
        actor,
        AuditEventType.DATA_UPDATED,
        "更新记录",
    )
    commit_session(session)
    session.refresh(record)
    return record


def soft_delete_record(
    session: Session,
    record: RecordMixin,
    actor: ActorContext,
    *,
    expected_version: int,
) -> None:
    if record.version != expected_version:
        raise AppError(
            "version_conflict",
            "记录已被其他操作更新，请刷新后重试",
            status_code=409,
            details={"expected": expected_version, "current": record.version},
        )
    now: datetime = utc_now()
    record.is_deleted = True
    record.deleted_at = now
    record.updated_at = now
    record.version += 1
    add_audit_event(
        session,
        record,
        actor,
        AuditEventType.DATA_DELETED,
        "软删除记录",
    )
    commit_session(session)
