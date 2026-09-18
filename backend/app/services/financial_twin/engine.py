from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.models.financial_twin import HouseholdSnapshot
from app.schemas.financial_twin import (
    HouseholdSnapshotOut,
    SnapshotSummary,
    WealthTwinMeta,
    WealthTwinResponse,
)
from app.services.client_profile.engine import get_client_profile
from app.services.eligible_capital.engine import calculate_household_eligible_capital
from app.services.family_enterprise.engine import get_family_enterprise_view
from app.services.financial.facts import load_household_facts
from app.services.financial_graph.engine import financial_graph_response
from app.services.liability_engine.engine import materialize_liability_streams
from app.services.wealth_needs.engine import recalculate_wealth_needs

from .snapshot import (
    build_snapshot,
    compare_snapshots,
    event_count,
    load_snapshot,
    snapshot_count,
    snapshot_out,
)


def materialize_current_twin(
    session: Session,
    household_id: str,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    client_profile_rules_path: str,
    liability_rules_path: str,
    analysis_date: date,
    force_new: bool = False,
    family_enterprise_rules_path: str | None = None,
) -> HouseholdSnapshot:
    graph = financial_graph_response(session, household_id, actor)
    needs = recalculate_wealth_needs(
        session,
        household_id,
        actor,
        client_profile_rules_path,
        analysis_date,
    )
    profile = get_client_profile(session, household_id)
    liability = materialize_liability_streams(
        session,
        household_id,
        actor,
        liability_rules_path,
        analysis_date,
    )
    eligible = calculate_household_eligible_capital(
        session,
        household_id,
        actor,
        financial_rules_path=financial_rules_path,
        methodology_rules_path=methodology_rules_path,
        public_data_snapshot_path=public_data_snapshot_path,
        liability_rules_path=liability_rules_path,
        analysis_date=analysis_date,
    )
    facts = load_household_facts(session, household_id)
    family_enterprise = (
        get_family_enterprise_view(
            session,
            household_id,
            family_enterprise_rules_path,
            analysis_date,
        )
        if family_enterprise_rules_path is not None
        else None
    )
    return build_snapshot(
        session,
        household_id,
        actor,
        facts=facts,
        graph=graph,
        profile=profile,
        needs=needs,
        liability=liability,
        eligible=eligible,
        analysis_date=analysis_date,
        force_new=force_new,
        family_enterprise=family_enterprise,
    )


def wealth_twin_response(
    session: Session,
    household_id: str,
    snapshot: HouseholdSnapshot,
) -> WealthTwinResponse:
    previous = (
        load_snapshot(session, household_id, snapshot.parent_snapshot_id)
        if snapshot.parent_snapshot_id is not None
        else None
    )
    return WealthTwinResponse(
        meta=WealthTwinMeta(
            household_id=household_id,
            analysis_date=snapshot.snapshot_date,
            snapshot_count=snapshot_count(session, household_id),
            event_count=event_count(session, household_id),
        ),
        current=snapshot_out(snapshot),
        previous=(
            SnapshotSummary(
                id=previous.id,
                snapshot_date=previous.snapshot_date,
                event_cursor=previous.event_cursor,
                snapshot_hash=previous.snapshot_hash,
            )
            if previous is not None
            else None
        ),
        comparison=compare_snapshots(previous, snapshot),
    )


def get_or_build_wealth_twin(
    session: Session,
    household_id: str,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    client_profile_rules_path: str,
    liability_rules_path: str,
    analysis_date: date,
    family_enterprise_rules_path: str | None = None,
) -> WealthTwinResponse:
    snapshot = materialize_current_twin(
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
    return wealth_twin_response(session, household_id, snapshot)


def get_snapshot_response(
    session: Session,
    household_id: str,
    snapshot_id: str,
) -> HouseholdSnapshotOut:
    return snapshot_out(load_snapshot(session, household_id, snapshot_id))
