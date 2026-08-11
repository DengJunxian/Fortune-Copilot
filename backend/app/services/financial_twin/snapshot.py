from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from threading import Lock
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import AuditEventType, HouseholdSnapshotStatus
from app.domain.financial import HouseholdFacts
from app.models.assessment import FinancialSnapshot
from app.models.financial_twin import FinancialEvent, HouseholdSnapshot
from app.schemas.client_profile import ClientProfileResponse, WealthNeedsResponse
from app.schemas.eligible_capital import EligibleCapitalResponse
from app.schemas.family_enterprise import FamilyEnterpriseView
from app.schemas.financial_graph import FinancialGraphResponse
from app.schemas.financial_twin import (
    CFSChange,
    FactChange,
    HouseholdSnapshotOut,
    HouseholdTwinState,
    NeedChange,
    ProfileChange,
    RiskBudgetChange,
    SnapshotComparison,
    TwinCFSState,
    TwinFactState,
    TwinIncomeState,
    TwinLiabilityState,
    TwinMonitoringState,
    TwinNeedState,
    TwinProfileState,
    TwinRiskBudgetState,
)
from app.schemas.liability import LiabilityCalendarResponse
from app.services.crud import add_audit_event, ensure_household
from app.services.financial.utils import ZERO, annualize, money
from app.services.twin.state import (
    TwinModelInput,
    build_twin_model_input,
    deserialize_twin_model_input,
    serialize_twin_model_input,
)

_SNAPSHOT_LOCKS = tuple(Lock() for _ in range(64))


def _canonical(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if hasattr(value, "value"):
        return str(value.value)
    return value


def _hash(value: object) -> str:
    payload = json.dumps(
        _canonical(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _latest_snapshot(session: Session, household_id: str) -> HouseholdSnapshot | None:
    return session.scalar(
        select(HouseholdSnapshot)
        .where(
            HouseholdSnapshot.household_id == household_id,
            HouseholdSnapshot.status == HouseholdSnapshotStatus.ACTIVE,
            HouseholdSnapshot.is_deleted.is_(False),
        )
        .order_by(HouseholdSnapshot.event_cursor.desc(), HouseholdSnapshot.created_at.desc())
    )


def _source_financial_snapshot_id(session: Session, household_id: str) -> str | None:
    return session.scalar(
        select(FinancialSnapshot.id)
        .where(
            FinancialSnapshot.household_id == household_id,
            FinancialSnapshot.is_deleted.is_(False),
        )
        .order_by(FinancialSnapshot.snapshot_date.desc(), FinancialSnapshot.created_at.desc())
    )


def _graph_version(graph: FinancialGraphResponse) -> str:
    return _hash(
        {
            "entities": [(item.id, item.version) for item in graph.entities],
            "accounts": [(item.id, item.version) for item in graph.accounts],
            "positions": [
                (item.id, item.version, item.market_value, item.enterprise_id)
                for item in graph.positions
            ],
            "edges": [(item.id, item.version) for item in graph.ownership_edges],
        }
    )


def _need_version(needs: WealthNeedsResponse) -> str:
    return _hash(
        [
            (item.id, item.version, item.need_type, item.status, item.target_amount, item.priority)
            for item in needs.needs
        ]
    )


def _liability_version(liability: LiabilityCalendarResponse) -> str:
    return _hash(
        [
            (
                item.stream.id,
                item.stream.version,
                item.stream.stream_version,
                [(row.id, row.version, row.calculation_version) for row in item.cashflows],
            )
            for item in liability.entries
        ]
    )


def build_state(
    facts: HouseholdFacts,
    profile: ClientProfileResponse,
    needs: WealthNeedsResponse,
    liability: LiabilityCalendarResponse,
    eligible: EligibleCapitalResponse,
    analysis_date: date,
    family_enterprise: FamilyEnterpriseView | None = None,
) -> dict[str, Any]:
    annual_income_by_source = [annualize(item.amount, item.frequency) for item in facts.incomes]
    annual_income = money(sum(annual_income_by_source, ZERO))
    annual_expenses = money(
        sum((annualize(item.amount, item.frequency) for item in facts.expenses), ZERO)
    )
    total_assets = money(sum((item.market_value for item in facts.assets), ZERO))
    total_liabilities = money(sum((item.outstanding_balance for item in facts.liabilities), ZERO))
    public_state = HouseholdTwinState(
        facts=TwinFactState(
            household_code=facts.code,
            household_name=facts.name,
            members=[
                {
                    "id": item.id,
                    "display_name": item.display_name,
                    "relationship": item.relationship,
                }
                for item in facts.members
            ],
            incomes=[
                TwinIncomeState(
                    id=item.id,
                    member_id=item.member_id,
                    name=item.name,
                    annual_amount=money(annual_income_by_source[index]),
                )
                for index, item in enumerate(facts.incomes)
            ],
            annual_income=annual_income,
            annual_expenses=annual_expenses,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_worth=money(total_assets - total_liabilities)
            if total_assets >= total_liabilities
            else -(total_liabilities - total_assets),
        ),
        profile=TwinProfileState(
            profile_version=profile.profile.profile_version,
            lifecycle_stage=profile.profile.lifecycle_stage.value,
            wealth_tier=profile.profile.wealth_tier.value,
            service_complexity=profile.profile.service_complexity.value,
            risk_capacity=profile.profile.risk_capacity,
            risk_willingness=profile.profile.risk_willingness,
            behavior_limit=profile.profile.behavior_limit,
            status=profile.profile.status.value,
        ),
        needs=[
            TwinNeedState(
                id=item.id,
                need_type=item.need_type,
                priority=item.priority,
                status=item.status,
                target_amount=item.target_amount,
                minimum_amount=item.minimum_amount,
            )
            for item in needs.needs
        ],
        liability=TwinLiabilityState(
            stream_count=liability.summary.stream_count,
            cashflow_count=liability.summary.cashflow_count,
            target_total=liability.summary.target_total,
            prepared_total=liability.summary.prepared_total,
            funding_gap=liability.summary.funding_gap,
            next_due_date=liability.summary.next_due_date,
        ),
        risk_budget=TwinRiskBudgetState(
            risk_capacity=profile.profile.risk_capacity,
            risk_willingness=profile.profile.risk_willingness,
            behavior_limit=profile.profile.behavior_limit,
            eligible_long_term_capital=eligible.calculation.eligible_long_term_capital,
            formally_eligible=eligible.calculation.formally_eligible,
            decision=eligible.calculation.decision,
            enterprise_dependency_score=(
                family_enterprise.dependency.score if family_enterprise is not None else None
            ),
            enterprise_dependency_level=(
                family_enterprise.dependency.level.value
                if family_enterprise is not None
                else None
            ),
            economic_equity_exposure=(
                family_enterprise.economic_capital.total_economic_equity_exposure
                if family_enterprise is not None
                else ZERO
            ),
            remaining_incremental_equity_capacity=(
                family_enterprise.economic_capital.remaining_incremental_equity_capacity
                if family_enterprise is not None
                else ZERO
            ),
            additional_equity_risk_allowed=(
                family_enterprise.economic_capital.additional_equity_risk_allowed
                if family_enterprise is not None
                else True
            ),
            enterprise_constraints=(
                family_enterprise.cfs_implication.constraints
                if family_enterprise is not None
                else []
            ),
        ),
        cfs=TwinCFSState(
            status="not_enabled",
            explanation=(
                "CFS 方案保存在独立方案账本；"
                "当前家庭快照尚未绑定具体 CFS 版本。"
            ),
        ),
        monitoring=TwinMonitoringState(
            status="not_enabled",
            alerts=[],
        ),
    )
    twin_model = build_twin_model_input(facts, analysis_date)
    return {
        **public_state.model_dump(mode="json"),
        "simulation_initial_state": serialize_twin_model_input(twin_model),
    }


def build_snapshot(
    session: Session,
    household_id: str,
    actor: ActorContext,
    *,
    facts: HouseholdFacts,
    graph: FinancialGraphResponse,
    profile: ClientProfileResponse,
    needs: WealthNeedsResponse,
    liability: LiabilityCalendarResponse,
    eligible: EligibleCapitalResponse,
    analysis_date: date,
    force_new: bool = False,
    family_enterprise: FamilyEnterpriseView | None = None,
) -> HouseholdSnapshot:
    lock = _SNAPSHOT_LOCKS[hash(household_id) % len(_SNAPSHOT_LOCKS)]
    with lock:
        household = ensure_household(session, household_id)
        state = build_state(
            facts,
            profile,
            needs,
            liability,
            eligible,
            analysis_date,
            family_enterprise,
        )
        input_hash = _hash(state)
        current = _latest_snapshot(session, household_id)
        if current is not None and current.input_hash == input_hash and not force_new:
            return current

        cursor = (current.event_cursor + 1) if current is not None else 0
        snapshot_hash = _hash(
            {
                "household_id": household_id,
                "parent_snapshot_hash": current.snapshot_hash if current is not None else None,
                "event_cursor": cursor,
                "snapshot_date": analysis_date,
                "input_hash": input_hash,
            }
        )
        if current is not None:
            current.status = HouseholdSnapshotStatus.SUPERSEDED
            current.version += 1
        snapshot = HouseholdSnapshot(
            household_id=household_id,
            parent_snapshot_id=current.id if current is not None else None,
            source_financial_snapshot_id=_source_financial_snapshot_id(session, household_id),
            snapshot_date=analysis_date,
            event_cursor=cursor,
            financial_graph_version=_graph_version(graph),
            profile_version=profile.profile.profile_version,
            need_version=_need_version(needs),
            liability_version=_liability_version(liability),
            state_json=state,
            input_hash=input_hash,
            snapshot_hash=snapshot_hash,
            status=HouseholdSnapshotStatus.ACTIVE,
            currency=facts.currency,
            valuation_date=analysis_date,
            data_source="v5_persistent_financial_twin",
            is_user_confirmed=household.is_user_confirmed,
        )
        session.add(snapshot)
        try:
            session.flush()
            add_audit_event(
                session,
                snapshot,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                f"生成家庭财富持久快照 #{cursor}",
            )
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            winner = _latest_snapshot(session, household_id)
            if winner is not None and winner.input_hash == input_hash:
                return winner
            raise AppError(
                "household_snapshot_conflict",
                "家庭财富快照与另一版本冲突，请重试",
                status_code=409,
            ) from exc
        session.refresh(snapshot)
        return snapshot


def load_snapshot(
    session: Session,
    household_id: str,
    snapshot_id: str | None = None,
) -> HouseholdSnapshot:
    ensure_household(session, household_id)
    if snapshot_id is None:
        snapshot = _latest_snapshot(session, household_id)
    else:
        snapshot = session.scalar(
            select(HouseholdSnapshot).where(
                HouseholdSnapshot.id == snapshot_id,
                HouseholdSnapshot.household_id == household_id,
                HouseholdSnapshot.is_deleted.is_(False),
            )
        )
    if snapshot is None:
        raise AppError("household_snapshot_not_found", "找不到家庭财富快照", status_code=404)
    return snapshot


def snapshot_out(snapshot: HouseholdSnapshot) -> HouseholdSnapshotOut:
    values = {column.name: getattr(snapshot, column.name) for column in snapshot.__table__.columns}
    values["state"] = HouseholdTwinState.model_validate(snapshot.state_json)
    return HouseholdSnapshotOut.model_validate(values)


def _direction(before: Decimal, after: Decimal) -> str:
    if after > before:
        return "increased"
    if after < before:
        return "decreased"
    return "changed"


def compare_snapshots(
    before: HouseholdSnapshot | None,
    after: HouseholdSnapshot,
) -> SnapshotComparison:
    after_state = HouseholdTwinState.model_validate(after.state_json)
    if before is None:
        return SnapshotComparison(
            from_snapshot_id=None,
            to_snapshot_id=after.id,
            changed_facts=[],
            changed_needs=[],
            changed_profile=ProfileChange(
                changed=False,
                before_version=None,
                after_version=after.profile_version,
            ),
            changed_risk_budget=RiskBudgetChange(
                changed=False,
                before=None,
                after=after_state.risk_budget,
            ),
            changed_cfs=CFSChange(changed=False, before=None, after=after_state.cfs),
            has_material_change=False,
        )

    before_state = HouseholdTwinState.model_validate(before.state_json)
    fact_fields = {
        "annual_income": "年度收入",
        "annual_expenses": "年度支出",
        "total_assets": "总资产",
        "total_liabilities": "总负债",
        "net_worth": "家庭净资产",
    }
    changes: list[FactChange] = []
    for code, label in fact_fields.items():
        before_value = Decimal(str(getattr(before_state.facts, code)))
        after_value = Decimal(str(getattr(after_state.facts, code)))
        if before_value != after_value:
            changes.append(
                FactChange(
                    code=code,
                    label=label,
                    before=str(before_value),
                    after=str(after_value),
                    direction=_direction(before_value, after_value),
                )
            )
    before_incomes = {item.id: item for item in before_state.facts.incomes}
    after_incomes = {item.id: item for item in after_state.facts.incomes}
    for income_id in sorted(before_incomes.keys() | after_incomes.keys()):
        prior = before_incomes.get(income_id)
        current = after_incomes.get(income_id)
        if prior is None and current is not None:
            changes.append(
                FactChange(
                    code=f"income:{income_id}",
                    label=current.name,
                    before=None,
                    after=str(current.annual_amount),
                    direction="added",
                )
            )
        elif current is None and prior is not None:
            changes.append(
                FactChange(
                    code=f"income:{income_id}",
                    label=prior.name,
                    before=str(prior.annual_amount),
                    after=None,
                    direction="removed",
                )
            )
        elif (
            prior is not None
            and current is not None
            and (prior.annual_amount != current.annual_amount)
        ):
            changes.append(
                FactChange(
                    code=f"income:{income_id}",
                    label=current.name,
                    before=str(prior.annual_amount),
                    after=str(current.annual_amount),
                    direction=_direction(prior.annual_amount, current.annual_amount),
                )
            )

    before_needs = {item.need_type: item for item in before_state.needs}
    after_needs = {item.need_type: item for item in after_state.needs}
    need_changes: list[NeedChange] = []
    for need_type in sorted(before_needs.keys() | after_needs.keys(), key=str):
        prior_need = before_needs.get(need_type)
        current_need = after_needs.get(need_type)
        if prior_need is None and current_need is not None:
            need_changes.append(
                NeedChange(
                    need_type=need_type,
                    change_type="added",
                    after_status=current_need.status,
                    after_target_amount=current_need.target_amount,
                )
            )
        elif current_need is None and prior_need is not None:
            need_changes.append(
                NeedChange(
                    need_type=need_type,
                    change_type="removed",
                    before_status=prior_need.status,
                    before_target_amount=prior_need.target_amount,
                )
            )
        elif (
            prior_need is not None
            and current_need is not None
            and (
                prior_need.status != current_need.status
                or prior_need.target_amount != current_need.target_amount
            )
        ):
            need_changes.append(
                NeedChange(
                    need_type=need_type,
                    change_type="changed",
                    before_status=prior_need.status,
                    after_status=current_need.status,
                    before_target_amount=prior_need.target_amount,
                    after_target_amount=current_need.target_amount,
                )
            )

    profile_fields = (
        "lifecycle_stage",
        "wealth_tier",
        "service_complexity",
        "risk_capacity",
        "risk_willingness",
        "behavior_limit",
        "status",
    )
    changed_profile_fields = [
        field
        for field in profile_fields
        if getattr(before_state.profile, field) != getattr(after_state.profile, field)
    ]
    risk_changed = before_state.risk_budget != after_state.risk_budget
    cfs_changed = before_state.cfs != after_state.cfs
    material = bool(
        changes or need_changes or changed_profile_fields or risk_changed or cfs_changed
    )
    return SnapshotComparison(
        from_snapshot_id=before.id,
        to_snapshot_id=after.id,
        changed_facts=changes,
        changed_needs=need_changes,
        changed_profile=ProfileChange(
            changed=bool(changed_profile_fields),
            before_version=before.profile_version,
            after_version=after.profile_version,
            changed_fields=changed_profile_fields,
        ),
        changed_risk_budget=RiskBudgetChange(
            changed=risk_changed,
            before=before_state.risk_budget,
            after=after_state.risk_budget,
        ),
        changed_cfs=CFSChange(
            changed=cfs_changed,
            before=before_state.cfs,
            after=after_state.cfs,
        ),
        has_material_change=material,
    )


def load_twin_model_input(
    session: Session,
    household_id: str,
    snapshot_id: str,
) -> TwinModelInput:
    snapshot = load_snapshot(session, household_id, snapshot_id)
    raw = snapshot.state_json.get("simulation_initial_state")
    if not isinstance(raw, dict):
        raise AppError(
            "household_snapshot_invalid",
            "家庭财富快照缺少模拟初始状态",
            status_code=409,
        )
    return deserialize_twin_model_input(raw)


def snapshot_count(session: Session, household_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(HouseholdSnapshot)
            .where(
                HouseholdSnapshot.household_id == household_id,
                HouseholdSnapshot.is_deleted.is_(False),
            )
        )
        or 0
    )


def event_count(session: Session, household_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(FinancialEvent)
            .where(
                FinancialEvent.household_id == household_id,
                FinancialEvent.is_deleted.is_(False),
            )
        )
        or 0
    )
