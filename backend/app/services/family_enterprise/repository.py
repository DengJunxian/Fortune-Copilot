from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AuditEventType,
    EnterpriseCashflowStability,
    EnterpriseCashflowType,
    EnterpriseEventType,
    FinancialEntityType,
    OwnershipType,
)
from app.models.common import RecordMixin, utc_now
from app.models.family import HouseholdMember
from app.models.family_enterprise import (
    EnterpriseCashflow,
    EnterpriseGuarantee,
    EnterpriseLiquidityEvent,
    EnterpriseOwnership,
    EnterpriseProfile,
    EnterpriseValuation,
)
from app.models.wealth_graph import FinancialEntity, OwnershipEdge
from app.schemas.family_enterprise import (
    EnterpriseCreate,
    EnterpriseExposureCreate,
)
from app.services.crud import (
    add_audit_event,
    commit_session,
    ensure_household,
    ensure_household_reference,
    get_active,
)
from app.services.financial_graph.engine import build_financial_graph


@dataclass(frozen=True, slots=True)
class FamilyEnterpriseRecords:
    profiles: tuple[EnterpriseProfile, ...]
    ownerships: tuple[EnterpriseOwnership, ...]
    valuations: tuple[EnterpriseValuation, ...]
    cashflows: tuple[EnterpriseCashflow, ...]
    guarantees: tuple[EnterpriseGuarantee, ...]
    liquidity_events: tuple[EnterpriseLiquidityEvent, ...]


@dataclass(frozen=True, slots=True)
class EnterpriseEventDescriptor:
    enterprise_id: str
    event_type: EnterpriseEventType
    effective_date: date
    estimated_value: str
    currency: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ExposureWriteResult:
    descriptors: tuple[EnterpriseEventDescriptor, ...]
    changed: bool


def _active_records[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    household_id: str,
) -> tuple[ModelT, ...]:
    return tuple(
        session.scalars(
            select(model)
            .where(
                cast(Any, model).household_id == household_id,
                model.is_deleted.is_(False),
            )
            .order_by(model.created_at, model.id)
        ).all()
    )


def load_family_enterprise_records(
    session: Session,
    household_id: str,
) -> FamilyEnterpriseRecords:
    ensure_household(session, household_id)
    return FamilyEnterpriseRecords(
        profiles=_active_records(session, EnterpriseProfile, household_id),
        ownerships=_active_records(session, EnterpriseOwnership, household_id),
        valuations=_active_records(session, EnterpriseValuation, household_id),
        cashflows=_active_records(session, EnterpriseCashflow, household_id),
        guarantees=_active_records(session, EnterpriseGuarantee, household_id),
        liquidity_events=_active_records(session, EnterpriseLiquidityEvent, household_id),
    )


def create_enterprise(
    session: Session,
    household_id: str,
    payload: EnterpriseCreate,
    actor: ActorContext,
) -> tuple[EnterpriseProfile, FinancialEntity]:
    ensure_household(session, household_id)
    build_financial_graph(session, household_id, actor)
    duplicate = session.scalar(
        select(EnterpriseProfile).where(
            EnterpriseProfile.household_id == household_id,
            EnterpriseProfile.name == payload.name,
            EnterpriseProfile.is_deleted.is_(False),
        )
    )
    if duplicate is not None:
        raise AppError(
            "enterprise_already_exists",
            "同一家庭下已存在同名企业",
            status_code=409,
        )
    profile = EnterpriseProfile(
        household_id=household_id,
        **payload.model_dump(mode="python"),
    )
    session.add(profile)
    session.flush()
    entity = FinancialEntity(
        household_id=household_id,
        entity_type=FinancialEntityType.ENTERPRISE,
        display_name=profile.name,
        jurisdiction=profile.jurisdiction,
        external_reference=f"enterprise:{profile.id}",
        metadata_json={
            "enterprise_profile_id": profile.id,
            "industry": profile.industry,
            "stage": profile.stage.value,
            "listed_status": profile.listed_status.value,
            "enterprise_type": profile.enterprise_type.value,
        },
        currency=profile.currency,
        valuation_date=profile.valuation_date,
        data_source=profile.data_source,
        is_user_confirmed=True,
    )
    session.add(entity)
    session.flush()
    add_audit_event(session, profile, actor, AuditEventType.DATA_CREATED, "创建家企财富企业档案")
    add_audit_event(session, entity, actor, AuditEventType.DATA_CREATED, "建立企业金融图主体")
    commit_session(session)
    session.refresh(profile)
    session.refresh(entity)
    return profile, entity


def _enterprise_entity(
    session: Session,
    household_id: str,
    enterprise_id: str,
) -> FinancialEntity:
    entity = session.scalar(
        select(FinancialEntity).where(
            FinancialEntity.household_id == household_id,
            FinancialEntity.external_reference == f"enterprise:{enterprise_id}",
            FinancialEntity.is_deleted.is_(False),
        )
    )
    if entity is None:
        raise AppError(
            "enterprise_graph_entity_missing",
            "企业档案缺少金融图主体",
            status_code=409,
        )
    return entity


def _update_if_changed(
    record: RecordMixin,
    values: dict[str, Any],
    session: Session,
    actor: ActorContext,
    summary: str,
) -> bool:
    changed = False
    for field, value in values.items():
        if getattr(record, field) != value:
            setattr(record, field, value)
            changed = True
    if changed:
        record.version += 1
        record.updated_at = utc_now()
        add_audit_event(session, record, actor, AuditEventType.DATA_UPDATED, summary)
    return changed


def upsert_enterprise_exposures(
    session: Session,
    household_id: str,
    payload: EnterpriseExposureCreate,
    actor: ActorContext,
) -> ExposureWriteResult:
    ensure_household(session, household_id)
    enterprise = get_active(
        session,
        EnterpriseProfile,
        payload.enterprise_id,
        household_id=household_id,
    )
    enterprise_entity = _enterprise_entity(session, household_id, enterprise.id)
    changed = False
    descriptors: list[EnterpriseEventDescriptor] = []

    for draft in payload.ownerships:
        owner = get_active(
            session,
            FinancialEntity,
            draft.owner_entity_id,
            household_id=household_id,
        )
        if owner.entity_type not in {FinancialEntityType.HOUSEHOLD, FinancialEntityType.PERSON}:
            raise AppError(
                "enterprise_owner_invalid",
                "企业权益所有者必须是本家庭或家庭成员主体",
                status_code=422,
            )
        record = session.scalar(
            select(EnterpriseOwnership).where(
                EnterpriseOwnership.enterprise_id == enterprise.id,
                EnterpriseOwnership.owner_entity_id == owner.id,
                EnterpriseOwnership.instrument_type == draft.instrument_type,
                EnterpriseOwnership.vesting_date == draft.vesting_date,
                EnterpriseOwnership.is_deleted.is_(False),
            )
        )
        values = {
            **draft.model_dump(mode="python"),
            "currency": enterprise.currency,
            "valuation_date": enterprise.valuation_date,
            "data_source": "v5_family_enterprise",
            "is_user_confirmed": True,
        }
        if record is None:
            record = EnterpriseOwnership(
                household_id=household_id,
                enterprise_id=enterprise.id,
                **values,
            )
            session.add(record)
            session.flush()
            add_audit_event(session, record, actor, AuditEventType.DATA_CREATED, "创建企业权益暴露")
            changed = True
        else:
            changed = _update_if_changed(
                record,
                values,
                session,
                actor,
                "更新企业权益暴露",
            ) or changed
        edge = session.scalar(
            select(OwnershipEdge).where(
                OwnershipEdge.household_id == household_id,
                OwnershipEdge.owner_entity_id == owner.id,
                OwnershipEdge.owned_entity_id == enterprise_entity.id,
                OwnershipEdge.ownership_type == OwnershipType.DIRECT,
                OwnershipEdge.effective_from == draft.vesting_date,
                OwnershipEdge.is_deleted.is_(False),
            )
        )
        edge_values = {
            "ownership_ratio": draft.ownership_ratio,
            "effective_to": None,
            "evidence_json": {
                "enterprise_profile_id": enterprise.id,
                "instrument_type": draft.instrument_type.value,
                "voting_ratio": str(draft.voting_ratio),
                "lockup_end_date": (
                    draft.lockup_end_date.isoformat() if draft.lockup_end_date else None
                ),
            },
            "currency": enterprise.currency,
            "valuation_date": enterprise.valuation_date,
            "data_source": "v5_family_enterprise",
            "is_user_confirmed": True,
        }
        if edge is None:
            edge = OwnershipEdge(
                household_id=household_id,
                owner_entity_id=owner.id,
                owned_entity_id=enterprise_entity.id,
                ownership_type=OwnershipType.DIRECT,
                effective_from=draft.vesting_date,
                **edge_values,
            )
            session.add(edge)
            session.flush()
            add_audit_event(
                session,
                edge,
                actor,
                AuditEventType.DATA_CREATED,
                "建立家庭到企业的权益关系",
            )
            changed = True
        else:
            changed = _update_if_changed(
                edge,
                edge_values,
                session,
                actor,
                "更新家庭到企业的权益关系",
            ) or changed

    for valuation_draft in payload.valuations:
        valuation_record = session.scalar(
            select(EnterpriseValuation).where(
                EnterpriseValuation.enterprise_id == enterprise.id,
                EnterpriseValuation.valuation_date == valuation_draft.valuation_date,
                EnterpriseValuation.valuation_method == valuation_draft.valuation_method,
                EnterpriseValuation.is_deleted.is_(False),
            )
        )
        valuation_values = {
            **valuation_draft.model_dump(mode="python"),
            "data_source": "v5_family_enterprise",
            "is_user_confirmed": True,
        }
        valuation_changed = False
        before_value = None
        if valuation_record is None:
            valuation_record = EnterpriseValuation(
                household_id=household_id,
                enterprise_id=enterprise.id,
                **valuation_values,
            )
            session.add(valuation_record)
            session.flush()
            add_audit_event(
                session,
                valuation_record,
                actor,
                AuditEventType.DATA_CREATED,
                "创建企业估值记录",
            )
            valuation_changed = True
        else:
            before_value = str(valuation_record.equity_value)
            valuation_changed = _update_if_changed(
                valuation_record,
                valuation_values,
                session,
                actor,
                "更新企业估值记录",
            )
        if valuation_changed:
            changed = True
            descriptors.append(
                EnterpriseEventDescriptor(
                    enterprise_id=enterprise.id,
                    event_type=EnterpriseEventType.VALUATION_CHANGE,
                    effective_date=valuation_draft.valuation_date,
                    estimated_value=str(valuation_draft.equity_value),
                    currency=valuation_draft.currency,
                    payload={
                        "enterprise_name": enterprise.name,
                        "before_value": before_value,
                        "after_value": str(valuation_draft.equity_value),
                        "valuation_method": valuation_draft.valuation_method.value,
                    },
                )
            )

    for cashflow_draft in payload.cashflows:
        ensure_household_reference(
            session,
            HouseholdMember,
            cashflow_draft.member_id,
            household_id,
        )
        cashflow_record = session.scalar(
            select(EnterpriseCashflow).where(
                EnterpriseCashflow.enterprise_id == enterprise.id,
                EnterpriseCashflow.member_id == cashflow_draft.member_id,
                EnterpriseCashflow.cashflow_type == cashflow_draft.cashflow_type,
                EnterpriseCashflow.frequency == cashflow_draft.frequency,
                EnterpriseCashflow.is_deleted.is_(False),
            )
        )
        cashflow_values = {
            **cashflow_draft.model_dump(mode="python"),
            "valuation_date": enterprise.valuation_date,
            "data_source": "v5_family_enterprise",
            "is_user_confirmed": True,
        }
        cashflow_changed = False
        before_amount = None
        before_stability = None
        if cashflow_record is None:
            cashflow_record = EnterpriseCashflow(
                household_id=household_id,
                enterprise_id=enterprise.id,
                **cashflow_values,
            )
            session.add(cashflow_record)
            session.flush()
            add_audit_event(
                session,
                cashflow_record,
                actor,
                AuditEventType.DATA_CREATED,
                "创建家企收入依赖记录",
            )
            cashflow_changed = True
        else:
            before_amount = str(cashflow_record.amount)
            before_stability = cashflow_record.stability.value
            cashflow_changed = _update_if_changed(
                cashflow_record,
                cashflow_values,
                session,
                actor,
                "更新家企收入依赖记录",
            )
        if cashflow_changed:
            changed = True
            event_type = (
                EnterpriseEventType.DIVIDEND_CHANGE
                if cashflow_draft.cashflow_type == EnterpriseCashflowType.DIVIDEND
                else EnterpriseEventType.CASHFLOW_DETERIORATION
            )
            if (
                cashflow_draft.cashflow_type == EnterpriseCashflowType.DIVIDEND
                or cashflow_draft.stability == EnterpriseCashflowStability.LOW
                or before_stability == EnterpriseCashflowStability.LOW.value
            ):
                descriptors.append(
                    EnterpriseEventDescriptor(
                        enterprise_id=enterprise.id,
                        event_type=event_type,
                        effective_date=enterprise.valuation_date or date.today(),
                        estimated_value=str(cashflow_draft.amount),
                        currency=cashflow_draft.currency,
                        payload={
                            "enterprise_name": enterprise.name,
                            "cashflow_type": cashflow_draft.cashflow_type.value,
                            "before_amount": before_amount,
                            "after_amount": str(cashflow_draft.amount),
                            "before_stability": before_stability,
                            "after_stability": cashflow_draft.stability.value,
                        },
                    )
                )

    for guarantee_draft in payload.guarantees:
        ensure_household_reference(
            session,
            HouseholdMember,
            guarantee_draft.member_id,
            household_id,
        )
        guarantee_record = session.scalar(
            select(EnterpriseGuarantee).where(
                EnterpriseGuarantee.enterprise_id == enterprise.id,
                EnterpriseGuarantee.member_id == guarantee_draft.member_id,
                EnterpriseGuarantee.guarantee_type == guarantee_draft.guarantee_type,
                EnterpriseGuarantee.expiry_date == guarantee_draft.expiry_date,
                EnterpriseGuarantee.is_deleted.is_(False),
            )
        )
        guarantee_values = {
            **guarantee_draft.model_dump(mode="python"),
            "valuation_date": enterprise.valuation_date,
            "data_source": "v5_family_enterprise",
            "is_user_confirmed": True,
        }
        guarantee_changed = False
        before_exposure = None
        if guarantee_record is None:
            guarantee_record = EnterpriseGuarantee(
                household_id=household_id,
                enterprise_id=enterprise.id,
                **guarantee_values,
            )
            session.add(guarantee_record)
            session.flush()
            add_audit_event(
                session,
                guarantee_record,
                actor,
                AuditEventType.DATA_CREATED,
                "创建家庭企业担保暴露",
            )
            guarantee_changed = True
        else:
            before_exposure = str(guarantee_record.outstanding_exposure)
            guarantee_changed = _update_if_changed(
                guarantee_record,
                guarantee_values,
                session,
                actor,
                "更新家庭企业担保暴露",
            )
        if guarantee_changed:
            changed = True
            descriptors.append(
                EnterpriseEventDescriptor(
                    enterprise_id=enterprise.id,
                    event_type=EnterpriseEventType.GUARANTEE_CHANGE,
                    effective_date=enterprise.valuation_date or date.today(),
                    estimated_value=str(guarantee_draft.outstanding_exposure),
                    currency=guarantee_draft.currency,
                    payload={
                        "enterprise_name": enterprise.name,
                        "guarantee_type": guarantee_draft.guarantee_type.value,
                        "before_exposure": before_exposure,
                        "after_exposure": str(guarantee_draft.outstanding_exposure),
                        "expiry_date": (
                            guarantee_draft.expiry_date.isoformat()
                            if guarantee_draft.expiry_date
                            else None
                        ),
                    },
                )
            )

    for event_draft in payload.liquidity_events:
        event_record = session.scalar(
            select(EnterpriseLiquidityEvent).where(
                EnterpriseLiquidityEvent.enterprise_id == enterprise.id,
                EnterpriseLiquidityEvent.event_type == event_draft.event_type,
                EnterpriseLiquidityEvent.expected_date == event_draft.expected_date,
                EnterpriseLiquidityEvent.is_deleted.is_(False),
            )
        )
        event_values = {
            **event_draft.model_dump(mode="python"),
            "valuation_date": event_draft.expected_date,
            "data_source": "v5_family_enterprise",
            "is_user_confirmed": True,
        }
        event_changed = False
        if event_record is None:
            event_record = EnterpriseLiquidityEvent(
                household_id=household_id,
                enterprise_id=enterprise.id,
                **event_values,
            )
            session.add(event_record)
            session.flush()
            add_audit_event(
                session,
                event_record,
                actor,
                AuditEventType.DATA_CREATED,
                "创建企业流动性事件",
            )
            event_changed = True
        else:
            event_changed = _update_if_changed(
                event_record,
                event_values,
                session,
                actor,
                "更新企业流动性事件",
            )
        if event_changed:
            changed = True
            descriptors.append(
                EnterpriseEventDescriptor(
                    enterprise_id=enterprise.id,
                    event_type=event_draft.event_type,
                    effective_date=event_draft.expected_date,
                    estimated_value=str(event_draft.estimated_value),
                    currency=event_draft.currency,
                    payload={
                        "enterprise_name": enterprise.name,
                        "probability": str(event_draft.probability),
                        "lockup": event_draft.lockup,
                        "status": event_draft.status.value,
                    },
                )
            )

    if changed:
        add_audit_event(
            session,
            enterprise,
            actor,
            AuditEventType.CONFIRMATION_RECORDED,
            "客户确认家企权益、收入、担保或流动性暴露",
        )
        commit_session(session)
    else:
        session.rollback()
    return ExposureWriteResult(descriptors=tuple(descriptors), changed=changed)
