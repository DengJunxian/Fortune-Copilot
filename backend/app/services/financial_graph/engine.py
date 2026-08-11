from __future__ import annotations

import logging
from datetime import date
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import (
    AccountWrapper,
    AuditEventType,
    FinancialEntityType,
    OwnershipType,
)
from app.models.family import HouseholdMember
from app.models.finance import Asset
from app.models.wealth_graph import (
    FinancialAccount,
    FinancialEntity,
    OwnershipEdge,
    Position,
)
from app.schemas.financial_graph import (
    FinancialAccountOut,
    FinancialEntityOut,
    FinancialGraphIntegrity,
    FinancialGraphMeta,
    FinancialGraphResponse,
    OwnershipEdgeOut,
    PositionOut,
)
from app.services.crud import add_audit_event, commit_session, ensure_household

from .projection import compare_legacy_projection
from .repository import FinancialGraphRecords, load_financial_graph

logger = logging.getLogger(__name__)
_GRAPH_BUILD_LOCKS = tuple(Lock() for _ in range(64))


def _entity_reference(kind: str, record_id: str) -> str:
    return f"legacy:{kind}:{record_id}"


def _asset_evidence(asset: Asset) -> dict[str, object]:
    return {
        "legacy_asset_id": asset.id,
        "legacy_created_at": asset.created_at.isoformat(),
        "owner_member_id": asset.owner_member_id,
        "subcategory": asset.subcategory,
        "liquidity_level": asset.liquidity_level.value,
        "purpose": asset.purpose,
        "pledged": asset.pledged,
        "ownership": asset.ownership,
        "property_use": asset.property_use.value,
        "account_wrapper": asset.account_wrapper.value,
        "volatility": str(asset.volatility),
        "product_complexity": asset.product_complexity.value,
        "institution_type": asset.institution_type,
        "household_role": asset.household_role,
        "region_code": asset.region_code,
        "version": asset.version,
    }


def _build_financial_graph_once(
    session: Session,
    household_id: str,
    actor: ActorContext,
) -> FinancialGraphRecords:
    household = ensure_household(session, household_id)
    graph = load_financial_graph(session, household_id)
    entities_by_reference = {
        item.external_reference: item
        for item in graph.entities
        if item.external_reference is not None
    }
    household_reference = _entity_reference("household", household.id)
    household_entity = entities_by_reference.get(household_reference)
    changed = False
    if household_entity is None:
        household_entity = FinancialEntity(
            household_id=household.id,
            entity_type=FinancialEntityType.HOUSEHOLD,
            display_name=household.name,
            jurisdiction="CN",
            external_reference=household_reference,
            metadata_json={"region": household.region, "legacy_version": household.version},
            currency=household.currency,
            valuation_date=household.valuation_date,
            data_source="v5_graph_projection",
            is_user_confirmed=household.is_user_confirmed,
        )
        session.add(household_entity)
        session.flush()
        add_audit_event(
            session,
            household_entity,
            actor,
            AuditEventType.DATA_CREATED,
            "建立 V5 家庭金融主体",
        )
        entities_by_reference[household_reference] = household_entity
        changed = True

    accounts = list(graph.accounts)
    default_account = next(
        (
            item
            for item in accounts
            if item.external_reference == _entity_reference("assets", household.id)
        ),
        None,
    )
    if default_account is None:
        default_account = FinancialAccount(
            household_id=household.id,
            owner_entity_id=household_entity.id,
            provider_name="Legacy household register",
            account_type="legacy_aggregate",
            account_wrapper=AccountWrapper.ORDINARY,
            jurisdiction="CN",
            external_reference=_entity_reference("assets", household.id),
            restriction_json={"compatibility_projection": True},
            currency=household.currency,
            valuation_date=household.valuation_date,
            data_source="v5_graph_projection",
            is_user_confirmed=household.is_user_confirmed,
        )
        session.add(default_account)
        session.flush()
        add_audit_event(
            session,
            default_account,
            actor,
            AuditEventType.DATA_CREATED,
            "建立 V4 兼容资产账户",
        )
        accounts.append(default_account)
        changed = True

    existing_edge_keys = {
        (item.owner_entity_id, item.owned_entity_id, item.ownership_type)
        for item in graph.ownership_edges
    }
    members = session.scalars(
        select(HouseholdMember)
        .where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.is_deleted.is_(False),
        )
        .order_by(HouseholdMember.created_at, HouseholdMember.id)
    )
    member_entities: dict[str, FinancialEntity] = {}
    for member in members:
        reference = _entity_reference("member", member.id)
        entity = entities_by_reference.get(reference)
        if entity is None:
            entity = FinancialEntity(
                household_id=household.id,
                entity_type=FinancialEntityType.PERSON,
                display_name=member.display_name,
                jurisdiction="CN",
                external_reference=reference,
                metadata_json={
                    "relationship": member.relationship,
                    "legacy_version": member.version,
                },
                currency=member.currency,
                valuation_date=member.valuation_date,
                data_source="v5_graph_projection",
                is_user_confirmed=member.is_user_confirmed,
            )
            session.add(entity)
            session.flush()
            add_audit_event(
                session,
                entity,
                actor,
                AuditEventType.DATA_CREATED,
                "建立 V5 家庭成员主体",
            )
            entities_by_reference[reference] = entity
            changed = True
        member_entities[member.id] = entity
        edge_key = (household_entity.id, entity.id, OwnershipType.HOUSEHOLD_MEMBER)
        if edge_key not in existing_edge_keys:
            edge = OwnershipEdge(
                household_id=household.id,
                owner_entity_id=household_entity.id,
                owned_entity_id=entity.id,
                ownership_type=OwnershipType.HOUSEHOLD_MEMBER,
                ownership_ratio=None,
                effective_from=None,
                effective_to=None,
                evidence_json={"legacy_member_id": member.id},
                currency=household.currency,
                valuation_date=member.valuation_date,
                data_source="v5_graph_projection",
                is_user_confirmed=member.is_user_confirmed,
            )
            session.add(edge)
            session.flush()
            add_audit_event(
                session,
                edge,
                actor,
                AuditEventType.DATA_CREATED,
                "建立家庭成员关系",
            )
            existing_edge_keys.add(edge_key)
            changed = True

    existing_legacy_assets = {
        item.legacy_asset_id for item in graph.positions if item.legacy_asset_id is not None
    }
    assets = session.scalars(
        select(Asset)
        .where(Asset.household_id == household_id, Asset.is_deleted.is_(False))
        .order_by(Asset.created_at, Asset.id)
    )
    for asset in assets:
        if asset.id in existing_legacy_assets:
            continue
        position = Position(
            household_id=household.id,
            account_id=default_account.id,
            owner_entity_id=(
                member_entities[asset.owner_member_id].id
                if asset.owner_member_id in member_entities
                else household_entity.id
            ),
            product_id=None,
            legacy_asset_id=asset.id,
            instrument_type=asset.category,
            instrument_code=None,
            name=asset.name,
            quantity=None,
            acquisition_cost=asset.acquisition_cost,
            market_value=asset.market_value,
            purpose_dimension=asset.purpose_dimension,
            risk_level=asset.risk_level,
            liquidity_days=asset.liquidity_days,
            complexity_level=asset.product_complexity,
            principal_loss_possible=asset.principal_loss_possible,
            legally_principal_guaranteed=asset.legally_principal_guaranteed,
            lock_up=asset.lock_up,
            withdrawable_date=asset.withdrawable_date,
            source_kind=asset.source_kind,
            evidence_json=_asset_evidence(asset),
            currency=asset.currency,
            valuation_date=asset.valuation_date,
            data_source="v5_graph_projection",
            is_user_confirmed=asset.is_user_confirmed,
        )
        session.add(position)
        session.flush()
        add_audit_event(
            session,
            position,
            actor,
            AuditEventType.DATA_CREATED,
            "将 V4 资产投影到 V5 持仓",
        )
        changed = True

    if changed:
        commit_session(session)
    return load_financial_graph(session, household_id)


def build_financial_graph(
    session: Session,
    household_id: str,
    actor: ActorContext,
) -> FinancialGraphRecords:
    """Idempotently materialize missing V4 records into the V5 graph.

    A browser can legitimately issue two first-read requests at the same time. The
    database uniqueness constraints elect one materializer; a losing transaction
    rolls back and reuses the graph committed by the winner.
    """

    build_lock = _GRAPH_BUILD_LOCKS[hash(household_id) % len(_GRAPH_BUILD_LOCKS)]
    with build_lock:
        try:
            return _build_financial_graph_once(session, household_id, actor)
        except IntegrityError:
            # The lock covers this process. Database uniqueness remains the final
            # arbiter when separate application workers race each other.
            session.rollback()
            graph = load_financial_graph(session, household_id)
            entity_reference = _entity_reference("household", household_id)
            account_reference = _entity_reference("assets", household_id)
            has_household_entity = any(
                item.external_reference == entity_reference for item in graph.entities
            )
            has_default_account = any(
                item.external_reference == account_reference for item in graph.accounts
            )
            if has_household_entity and has_default_account:
                logger.info(
                    "financial_graph_materialization_race_reused household_id=%s",
                    household_id,
                )
                return graph
            raise


def validate_graph_integrity(graph: FinancialGraphRecords) -> FinancialGraphIntegrity:
    issues: list[str] = []
    entity_ids = {item.id for item in graph.entities}
    account_ids = {item.id for item in graph.accounts}
    household_entities = [
        item for item in graph.entities if item.entity_type == FinancialEntityType.HOUSEHOLD
    ]
    if len(household_entities) != 1:
        issues.append("家庭金融图必须且只能有一个家庭主体")
    for account in graph.accounts:
        if account.owner_entity_id not in entity_ids:
            issues.append(f"账户 {account.id} 的所有者不存在")
    for position in graph.positions:
        if position.account_id not in account_ids:
            issues.append(f"持仓 {position.id} 的账户不存在")
        if position.owner_entity_id not in entity_ids:
            issues.append(f"持仓 {position.id} 的所有者不存在")
        if position.market_value < 0 or position.acquisition_cost < 0:
            issues.append(f"持仓 {position.id} 出现负金额")
        if position.legally_principal_guaranteed and position.principal_loss_possible:
            issues.append(f"持仓 {position.id} 的本金法律属性冲突")
    for edge in graph.ownership_edges:
        if edge.owner_entity_id not in entity_ids or edge.owned_entity_id not in entity_ids:
            issues.append(f"所有权关系 {edge.id} 引用了不存在的主体")
        if edge.effective_from and edge.effective_to and edge.effective_to < edge.effective_from:
            issues.append(f"所有权关系 {edge.id} 的有效期倒置")
    return FinancialGraphIntegrity(
        status="passed" if not issues else "needs_review",
        issues=issues,
    )


def financial_graph_response(
    session: Session,
    household_id: str,
    actor: ActorContext,
) -> FinancialGraphResponse:
    household = ensure_household(session, household_id)
    graph = build_financial_graph(session, household_id, actor)
    diagnostic = compare_legacy_projection(session, household_id, graph)
    if diagnostic.status == "mismatch":
        logger.warning(
            "financial_graph_projection_mismatch household_id=%s details=%s",
            household_id,
            diagnostic.details,
        )
    data_dates = [item.valuation_date for item in graph.positions if item.valuation_date]
    return FinancialGraphResponse(
        meta=FinancialGraphMeta(
            household_id=household.id,
            analysis_date=date.today(),
            data_as_of=max(data_dates) if data_dates else household.valuation_date,
            input_version=household.version,
            synthetic_data=household.is_synthetic,
        ),
        entities=[FinancialEntityOut.model_validate(item) for item in graph.entities],
        accounts=[FinancialAccountOut.model_validate(item) for item in graph.accounts],
        positions=[PositionOut.model_validate(item) for item in graph.positions],
        ownership_edges=[OwnershipEdgeOut.model_validate(item) for item in graph.ownership_edges],
        integrity=validate_graph_integrity(graph),
        projection_diagnostic=diagnostic,
    )
