from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.core.privacy import stable_hash
from app.domain.enums import AuditEventType, FinancialEntityType
from app.models.assessment import BehaviorAssessment, RiskAssessment
from app.models.family import ConsentRecord, Household, HouseholdMember
from app.models.family_enterprise import EnterpriseProfile
from app.models.finance import (
    Asset,
    ExpenseItem,
    FinancialGoal,
    IncomeSource,
    InsurancePolicy,
    Liability,
    SocialSecurityAccount,
)
from app.models.governance import AuditEvent
from app.models.security import IdentityAccessGrant
from app.schemas.family_enterprise import EnterpriseExposureCreate
from app.schemas.seed import SyntheticDataset
from app.services.behavior.rules import ensure_behavior_rule_version, load_behavior_rules
from app.services.family_enterprise.repository import (
    create_enterprise,
    upsert_enterprise_exposures,
)
from app.services.financial.rules import ensure_rule_version, load_financial_rules
from app.services.financial_graph.engine import build_financial_graph
from app.services.methodology.rules import (
    ensure_methodology_rule_version,
    load_methodology_rules,
)
from app.services.planning.rules import ensure_planning_rule_version, load_planning_rules
from app.services.portfolio.catalog import ensure_mock_product_catalog, load_product_catalog
from app.services.portfolio.rules import ensure_portfolio_rule_version, load_portfolio_rules
from app.services.trust.knowledge import ensure_knowledge_base
from app.services.twin.rules import (
    ensure_scenario_definitions,
    ensure_twin_rule_version,
    load_twin_rules,
)


@dataclass(frozen=True)
class SeedResult:
    loaded: int
    skipped: int
    reset_removed: int
    household_codes: tuple[str, ...]
    dataset_version: str
    product_count: int = 0
    scenario_count: int = 0
    behavior_rule_version: str | None = None
    behavior_inputs_refreshed: int = 0
    knowledge_document_count: int = 0
    knowledge_chunk_count: int = 0
    knowledge_quarantined_chunk_count: int = 0
    knowledge_documents_changed: int = 0
    knowledge_chunks_changed: int = 0
    enterprise_profiles_loaded: int = 0
    enterprise_exposures_refreshed: int = 0


def resolve_dataset_path(configured_path: str) -> Path:
    configured = Path(configured_path).expanduser()
    candidates = [configured]
    if not configured.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        candidates.extend(
            [
                project_root / "backend" / configured,
                project_root / configured,
                project_root / "data/synthetic/families.json",
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "seed_data_missing",
        "找不到合成家庭数据文件",
        status_code=500,
        details={"configured_path": configured_path},
    )


def read_dataset(configured_path: str) -> SyntheticDataset:
    path = resolve_dataset_path(configured_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return SyntheticDataset.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "seed_data_invalid",
            "合成家庭数据未通过结构校验",
            status_code=500,
        ) from exc


def _values(payload: BaseModel, dataset: SyntheticDataset) -> dict[str, Any]:
    values = payload.model_dump(mode="python")
    values["valuation_date"] = dataset.as_of_date
    values["data_source"] = dataset.dataset_version
    values["is_user_confirmed"] = True
    return values


def _translate_reference(
    values: dict[str, Any],
    field: str,
    references: dict[str, str],
) -> None:
    reference = values.get(field)
    if reference is None:
        return
    resolved = references.get(str(reference))
    if resolved is None:
        raise AppError(
            "seed_reference_invalid",
            f"合成数据引用不存在: {field}",
            status_code=500,
        )
    values[field] = resolved


def reset_synthetic_data(session: Session) -> int:
    count = (
        session.scalar(
            select(func.count()).select_from(Household).where(Household.is_synthetic.is_(True))
        )
        or 0
    )
    session.execute(delete(Household).where(Household.is_synthetic.is_(True)))
    session.commit()
    return int(count)


def _sync_demo_identity_grants(session: Session) -> None:
    """Maintain pseudonymous demo grants in the isolated identity zone."""

    households = list(
        session.scalars(
            select(Household).where(
                Household.is_synthetic.is_(True),
                Household.is_deleted.is_(False),
            )
        ).all()
    )
    role_actions = {
        "client": ["read", "export", "withdraw_consent", "request_deletion"],
        "advisor": ["read", "calculate", "draft", "submit_review"],
        "compliance": ["read", "review", "publish", "audit_export"],
        "admin": ["read", "write", "review", "publish", "grant"],
    }
    for household in households:
        for role, actions in role_actions.items():
            subject_hash = stable_hash(f"demo-{role}")
            existing = session.scalar(
                select(IdentityAccessGrant.id).where(
                    IdentityAccessGrant.actor_subject_hash == subject_hash,
                    IdentityAccessGrant.household_id == household.id,
                    IdentityAccessGrant.actor_role == role,
                )
            )
            if existing is None:
                session.add(
                    IdentityAccessGrant(
                        actor_subject_hash=subject_hash,
                        actor_role=role,
                        household_id=household.id,
                        allowed_actions=actions,
                        purpose="仅用于合成家庭竞赛演示的身份区到财务区授权映射",
                        currency="CNY",
                        valuation_date=household.valuation_date,
                        data_source="synthetic_identity_zone",
                        is_user_confirmed=True,
                    )
                )


def _sync_synthetic_behavior_inputs(
    session: Session,
    dataset: SyntheticDataset,
) -> int:
    """Refresh only authoritative seed behavior facts on existing demo households."""

    refreshed = 0
    for bundle in dataset.households:
        household = session.scalar(
            select(Household).where(
                Household.code == bundle.household.code,
                Household.is_synthetic.is_(True),
                Household.is_deleted.is_(False),
            )
        )
        if household is None:
            continue
        existing = list(
            session.scalars(
                select(BehaviorAssessment)
                .where(
                    BehaviorAssessment.household_id == household.id,
                    BehaviorAssessment.data_source == dataset.dataset_version,
                    BehaviorAssessment.is_deleted.is_(False),
                )
                .order_by(BehaviorAssessment.created_at, BehaviorAssessment.id)
            ).all()
        )
        for index, payload in enumerate(bundle.behavior_assessments):
            values = _values(payload, dataset)
            if index >= len(existing):
                session.add(BehaviorAssessment(household_id=household.id, **values))
                refreshed += 1
                continue
            record = existing[index]
            changed = False
            for field, value in values.items():
                if getattr(record, field) != value:
                    setattr(record, field, value)
                    changed = True
            if changed:
                record.version += 1
                refreshed += 1
    return refreshed


def _seed_actor() -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id="synthetic-persona-seed",
        role="admin",
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _sync_synthetic_enterprise_extensions(
    session: Session,
    dataset: SyntheticDataset,
) -> tuple[int, int]:
    """Resolve stable seed references and write the canonical V5 enterprise records."""

    created_count = 0
    refreshed_count = 0
    actor = _seed_actor()
    for extension in dataset.enterprise_extensions:
        household = session.scalar(
            select(Household).where(
                Household.code == extension.household_code,
                Household.is_synthetic.is_(True),
                Household.is_deleted.is_(False),
            )
        )
        if household is None:
            raise AppError(
                "seed_reference_invalid",
                "V5 企业扩展引用的合成家庭不存在",
                status_code=500,
                details={"household_code": extension.household_code},
            )
        enterprise = session.scalar(
            select(EnterpriseProfile).where(
                EnterpriseProfile.household_id == household.id,
                EnterpriseProfile.name == extension.enterprise.name,
                EnterpriseProfile.is_deleted.is_(False),
            )
        )
        if enterprise is None:
            enterprise, _entity = create_enterprise(
                session,
                household.id,
                extension.enterprise,
                actor,
            )
            created_count += 1
        graph = build_financial_graph(session, household.id, actor)
        household_entity = next(
            item
            for item in graph.entities
            if item.entity_type == FinancialEntityType.HOUSEHOLD
        )
        household_entity_id = household_entity.id
        member_entities = {
            item.display_name: item.id
            for item in graph.entities
            if item.entity_type == FinancialEntityType.PERSON
        }

        def entity_reference(
            reference: str,
            household_entity_id: str = household_entity_id,
            member_entities: dict[str, str] = member_entities,
            household_code: str = extension.household_code,
        ) -> str:
            if reference == "@household":
                return household_entity_id
            resolved = member_entities.get(reference)
            if resolved is None:
                raise AppError(
                    "seed_reference_invalid",
                    "V5 企业权益所有者引用不存在",
                    status_code=500,
                    details={
                        "household_code": household_code,
                        "reference": reference,
                    },
                )
            return resolved

        members = {
            item.display_name: item.id
            for item in session.scalars(
                select(HouseholdMember).where(
                    HouseholdMember.household_id == household.id,
                    HouseholdMember.is_deleted.is_(False),
                )
            ).all()
        }

        def member_reference(
            reference: str | None,
            members: dict[str, str] = members,
            household_code: str = extension.household_code,
        ) -> str | None:
            if reference is None:
                return None
            resolved = members.get(reference)
            if resolved is None:
                raise AppError(
                    "seed_reference_invalid",
                    "V5 家企收入或担保成员引用不存在",
                    status_code=500,
                    details={
                        "household_code": household_code,
                        "reference": reference,
                    },
                )
            return resolved

        payload = EnterpriseExposureCreate(
            enterprise_id=enterprise.id,
            ownerships=[
                item.model_copy(
                    update={"owner_entity_id": entity_reference(item.owner_entity_id)}
                )
                for item in extension.ownerships
            ],
            valuations=extension.valuations,
            cashflows=[
                item.model_copy(update={"member_id": member_reference(item.member_id)})
                for item in extension.cashflows
            ],
            guarantees=[
                item.model_copy(update={"member_id": member_reference(item.member_id)})
                for item in extension.guarantees
            ],
            liquidity_events=extension.liquidity_events,
            source_reference=extension.source_reference,
            is_user_confirmed=True,
        )
        result = upsert_enterprise_exposures(
            session,
            household.id,
            payload,
            actor,
        )
        if result.changed:
            refreshed_count += 1
    return created_count, refreshed_count


def seed_synthetic_data(
    session: Session,
    dataset_path: str,
    *,
    rules_path: str | None = None,
    planning_rules_path: str | None = None,
    methodology_rules_path: str | None = None,
    portfolio_rules_path: str | None = None,
    product_catalog_path: str | None = None,
    twin_rules_path: str | None = None,
    behavior_rules_path: str | None = None,
    knowledge_base_path: str | None = None,
    reset: bool = False,
    if_empty: bool = False,
) -> SeedResult:
    dataset = read_dataset(dataset_path)
    removed = reset_synthetic_data(session) if reset else 0
    if rules_path is not None:
        ensure_rule_version(session, load_financial_rules(rules_path))
    if planning_rules_path is not None:
        ensure_planning_rule_version(session, load_planning_rules(planning_rules_path))
    if methodology_rules_path is not None:
        ensure_methodology_rule_version(
            session,
            load_methodology_rules(methodology_rules_path),
        )
    if portfolio_rules_path is not None:
        ensure_portfolio_rule_version(session, load_portfolio_rules(portfolio_rules_path))
    product_count = 0
    if product_catalog_path is not None:
        products = ensure_mock_product_catalog(session, load_product_catalog(product_catalog_path))
        product_count = len(products)
    scenario_count = 0
    if twin_rules_path is not None:
        twin_rules = load_twin_rules(twin_rules_path)
        ensure_twin_rule_version(session, twin_rules)
        scenarios = ensure_scenario_definitions(session, twin_rules)
        scenario_count = len(scenarios)
    behavior_rule_version = None
    if behavior_rules_path is not None:
        behavior_rules = load_behavior_rules(behavior_rules_path)
        ensure_behavior_rule_version(session, behavior_rules)
        behavior_rule_version = behavior_rules.semantic_version
    knowledge_document_count = 0
    knowledge_chunk_count = 0
    knowledge_quarantined_chunk_count = 0
    knowledge_documents_changed = 0
    knowledge_chunks_changed = 0
    if knowledge_base_path is not None:
        knowledge_result = ensure_knowledge_base(session, knowledge_base_path)
        knowledge_document_count = knowledge_result.document_count
        knowledge_chunk_count = knowledge_result.chunk_count
        knowledge_quarantined_chunk_count = knowledge_result.quarantined_chunk_count
        knowledge_documents_changed = knowledge_result.changed_document_count
        knowledge_chunks_changed = knowledge_result.changed_chunk_count
    behavior_inputs_refreshed = _sync_synthetic_behavior_inputs(session, dataset)
    active_count = (
        session.scalar(
            select(func.count()).select_from(Household).where(Household.is_deleted.is_(False))
        )
        or 0
    )
    if if_empty and active_count:
        _sync_demo_identity_grants(session)
        session.commit()
        return SeedResult(
            0,
            len(dataset.households),
            removed,
            (),
            dataset.dataset_version,
            product_count,
            scenario_count,
            behavior_rule_version,
            behavior_inputs_refreshed,
            knowledge_document_count,
            knowledge_chunk_count,
            knowledge_quarantined_chunk_count,
            knowledge_documents_changed,
            knowledge_chunks_changed,
        )

    loaded_codes: list[str] = []
    skipped = 0
    for bundle in dataset.households:
        existing = session.scalar(select(Household).where(Household.code == bundle.household.code))
        if existing is not None and not existing.is_deleted:
            skipped += 1
            continue
        if existing is not None:
            session.delete(existing)
            session.flush()

        household = Household(**_values(bundle.household, dataset))
        session.add(household)
        session.flush()

        member_ids: dict[str, str] = {}
        for member_payload in bundle.members:
            member = HouseholdMember(
                household_id=household.id,
                **_values(member_payload, dataset),
            )
            session.add(member)
            session.flush()
            member_ids[member.display_name] = member.id

        for consent_payload in bundle.consents:
            values = _values(consent_payload, dataset)
            _translate_reference(values, "member_id", member_ids)
            session.add(ConsentRecord(household_id=household.id, **values))

        for income_payload in bundle.incomes:
            values = _values(income_payload, dataset)
            _translate_reference(values, "member_id", member_ids)
            session.add(IncomeSource(household_id=household.id, **values))

        for expense_payload in bundle.expenses:
            values = _values(expense_payload, dataset)
            _translate_reference(values, "member_id", member_ids)
            session.add(ExpenseItem(household_id=household.id, **values))

        asset_ids: dict[str, str] = {}
        for asset_payload in bundle.assets:
            values = _values(asset_payload, dataset)
            _translate_reference(values, "owner_member_id", member_ids)
            asset = Asset(household_id=household.id, **values)
            session.add(asset)
            session.flush()
            asset_ids[asset.name] = asset.id

        for liability_payload in bundle.liabilities:
            values = _values(liability_payload, dataset)
            _translate_reference(values, "borrower_member_id", member_ids)
            _translate_reference(values, "linked_asset_id", asset_ids)
            session.add(Liability(household_id=household.id, **values))

        for policy_payload in bundle.insurance_policies:
            values = _values(policy_payload, dataset)
            _translate_reference(values, "insured_member_id", member_ids)
            session.add(InsurancePolicy(household_id=household.id, **values))

        for account_payload in bundle.social_security_accounts:
            values = _values(account_payload, dataset)
            _translate_reference(values, "member_id", member_ids)
            session.add(SocialSecurityAccount(household_id=household.id, **values))

        for goal_payload in bundle.goals:
            session.add(FinancialGoal(household_id=household.id, **_values(goal_payload, dataset)))

        for risk_payload in bundle.risk_assessments:
            session.add(RiskAssessment(household_id=household.id, **_values(risk_payload, dataset)))

        for behavior_payload in bundle.behavior_assessments:
            session.add(
                BehaviorAssessment(
                    household_id=household.id,
                    **_values(behavior_payload, dataset),
                )
            )

        session.add(
            AuditEvent(
                household_id=household.id,
                event_type=AuditEventType.DATA_CREATED,
                actor_id="synthetic-seed",
                actor_role="system",
                entity_type="Household",
                entity_id=household.id,
                event_version=1,
                summary=f"加载合成演示家庭 {bundle.household.demo_profile}",
                occurred_at=household.created_at,
                valuation_date=dataset.as_of_date,
                data_source=dataset.dataset_version,
                is_user_confirmed=True,
            )
        )
        loaded_codes.append(household.code)

    session.flush()
    enterprise_profiles_loaded, enterprise_exposures_refreshed = (
        _sync_synthetic_enterprise_extensions(session, dataset)
    )
    _sync_demo_identity_grants(session)
    session.commit()
    return SeedResult(
        loaded=len(loaded_codes),
        skipped=skipped,
        reset_removed=removed,
        household_codes=tuple(loaded_codes),
        dataset_version=dataset.dataset_version,
        product_count=product_count,
        scenario_count=scenario_count,
        behavior_rule_version=behavior_rule_version,
        behavior_inputs_refreshed=behavior_inputs_refreshed,
        knowledge_document_count=knowledge_document_count,
        knowledge_chunk_count=knowledge_chunk_count,
        knowledge_quarantined_chunk_count=knowledge_quarantined_chunk_count,
        knowledge_documents_changed=knowledge_documents_changed,
        knowledge_chunks_changed=knowledge_chunks_changed,
        enterprise_profiles_loaded=enterprise_profiles_loaded,
        enterprise_exposures_refreshed=enterprise_exposures_refreshed,
    )
