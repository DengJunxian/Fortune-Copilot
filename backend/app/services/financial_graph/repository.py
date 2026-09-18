from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import AuditEventType, FinancialEntityType
from app.models.common import RecordMixin
from app.models.family_enterprise import EnterpriseProfile
from app.models.governance import Product
from app.models.wealth_graph import (
    FinancialAccount,
    FinancialEntity,
    OwnershipEdge,
    Position,
)
from app.schemas.financial_graph import FinancialAccountDraft, PositionCreate, PositionUpdate
from app.services.crud import (
    add_audit_event,
    commit_session,
    ensure_household,
    get_active,
    soft_delete_record,
    update_record,
)


@dataclass(frozen=True, slots=True)
class FinancialGraphRecords:
    entities: tuple[FinancialEntity, ...]
    accounts: tuple[FinancialAccount, ...]
    positions: tuple[Position, ...]
    ownership_edges: tuple[OwnershipEdge, ...]


def _active_records[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    household_id: str,
) -> tuple[ModelT, ...]:
    statement = (
        select(model)
        .where(
            cast(Any, model).household_id == household_id,
            model.is_deleted.is_(False),
        )
        .order_by(model.created_at, model.id)
    )
    return tuple(session.scalars(statement).all())


def load_financial_graph(session: Session, household_id: str) -> FinancialGraphRecords:
    ensure_household(session, household_id)
    return FinancialGraphRecords(
        entities=_active_records(session, FinancialEntity, household_id),
        accounts=_active_records(session, FinancialAccount, household_id),
        positions=_active_records(session, Position, household_id),
        ownership_edges=_active_records(session, OwnershipEdge, household_id),
    )


def household_entity(graph: FinancialGraphRecords) -> FinancialEntity:
    entity = next(
        (item for item in graph.entities if item.entity_type == FinancialEntityType.HOUSEHOLD),
        None,
    )
    if entity is None:
        raise AppError(
            "financial_graph_incomplete",
            "家庭金融图缺少家庭主体",
            status_code=409,
        )
    return entity


def _ensure_entity(
    graph: FinancialGraphRecords,
    entity_id: str,
) -> FinancialEntity:
    entity = next((item for item in graph.entities if item.id == entity_id), None)
    if entity is None:
        raise AppError("not_found", "所有权主体不存在", status_code=404)
    return entity


def _ensure_account(
    graph: FinancialGraphRecords,
    account_id: str,
) -> FinancialAccount:
    account = next((item for item in graph.accounts if item.id == account_id), None)
    if account is None:
        raise AppError("not_found", "金融账户不存在", status_code=404)
    return account


def _create_account(
    session: Session,
    household_id: str,
    owner: FinancialEntity,
    draft: FinancialAccountDraft,
    payload: PositionCreate,
    actor: ActorContext,
) -> FinancialAccount:
    account = FinancialAccount(
        household_id=household_id,
        owner_entity_id=owner.id,
        provider_name=draft.provider_name,
        account_type=draft.account_type,
        account_wrapper=draft.account_wrapper,
        jurisdiction=draft.jurisdiction,
        external_reference=draft.external_reference,
        restriction_json=draft.restriction_json,
        currency=payload.currency,
        valuation_date=payload.valuation_date,
        data_source=payload.data_source,
        is_user_confirmed=payload.is_user_confirmed,
    )
    session.add(account)
    session.flush()
    add_audit_event(
        session,
        account,
        actor,
        AuditEventType.DATA_CREATED,
        "创建精细资产账户",
    )
    return account


def create_position(
    session: Session,
    household_id: str,
    payload: PositionCreate,
    actor: ActorContext,
) -> Position:
    if payload.valuation_date is None:
        raise AppError(
            "valuation_date_required",
            "精细资产必须提供估值日期",
            status_code=422,
        )
    graph = load_financial_graph(session, household_id)
    default_owner = household_entity(graph)
    owner = (
        _ensure_entity(graph, payload.owner_entity_id)
        if payload.owner_entity_id is not None
        else default_owner
    )
    if payload.product_id is not None:
        product = get_active(session, Product, payload.product_id)
        if product.is_simulated and payload.data_source not in {"synthetic", "controlled_demo"}:
            raise AppError(
                "mock_product_boundary",
                "模拟产品不能写入非演示客户的正式资产事实",
                status_code=409,
            )
    if payload.enterprise_id is not None:
        get_active(
            session,
            EnterpriseProfile,
            payload.enterprise_id,
            household_id=household_id,
        )
    account: FinancialAccount | None
    if payload.account_id is not None:
        account = _ensure_account(graph, payload.account_id)
    elif payload.account is not None:
        account = _create_account(session, household_id, owner, payload.account, payload, actor)
    else:
        account = next(
            (item for item in graph.accounts if item.owner_entity_id == owner.id),
            None,
        ) or next(iter(graph.accounts), None)
        if account is None:
            account = _create_account(
                session,
                household_id,
                owner,
                FinancialAccountDraft(
                    provider_name="客户自报账户",
                    account_type="self_reported",
                ),
                payload,
                actor,
            )
    assert account is not None

    values = payload.model_dump(
        mode="python",
        exclude={"account", "account_id", "owner_entity_id"},
    )
    position = Position(
        household_id=household_id,
        account_id=account.id,
        owner_entity_id=owner.id,
        **values,
    )
    session.add(position)
    session.flush()
    add_audit_event(
        session,
        position,
        actor,
        AuditEventType.DATA_CREATED,
        "创建精细资产持仓",
    )
    commit_session(session)
    session.refresh(position)
    return position


def update_position(
    session: Session,
    household_id: str,
    position_id: str,
    payload: PositionUpdate,
    actor: ActorContext,
) -> Position:
    record = get_active(session, Position, position_id, household_id=household_id)
    if payload.evidence_json is not None:
        payload = payload.model_copy(
            update={
                "evidence_json": {
                    **(record.evidence_json or {}),
                    **payload.evidence_json,
                }
            }
        )
    graph = load_financial_graph(session, household_id)
    if payload.owner_entity_id is not None:
        _ensure_entity(graph, payload.owner_entity_id)
    if payload.product_id is not None:
        get_active(session, Product, payload.product_id)
    if payload.enterprise_id is not None:
        get_active(
            session,
            EnterpriseProfile,
            payload.enterprise_id,
            household_id=household_id,
        )
    principal_loss_possible = (
        record.principal_loss_possible
        if payload.principal_loss_possible is None
        else payload.principal_loss_possible
    )
    legally_guaranteed = (
        record.legally_principal_guaranteed
        if payload.legally_principal_guaranteed is None
        else payload.legally_principal_guaranteed
    )
    if principal_loss_possible and legally_guaranteed:
        raise AppError(
            "validation_error",
            "法律属性保证本金的资产不能同时标记本金可损失",
            status_code=422,
        )
    return update_record(session, record, payload, actor)


def delete_position(
    session: Session,
    household_id: str,
    position_id: str,
    *,
    expected_version: int,
    actor: ActorContext,
) -> None:
    record = get_active(session, Position, position_id, household_id=household_id)
    soft_delete_record(session, record, actor, expected_version=expected_version)
