from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.enums import (
    ClientProfileStatus,
    IncomeType,
    LifecycleStage,
    WealthNeedType,
)
from app.main import app
from app.models.client_profile import (
    ClientProfileTag,
    ClientWealthProfile,
    WealthNeed,
    WealthNeedPriority,
)
from app.models.family import Household
from app.models.finance import IncomeSource
from app.models.governance import AuditEvent
from app.services.client_profile.engine import (
    derive_client_profile,
    recalculate_client_profile,
)
from app.services.client_profile.rules import load_client_profile_rules
from app.services.financial.facts import load_household_facts
from app.services.financial_graph.engine import build_financial_graph
from app.services.seed import seed_synthetic_data
from app.services.wealth_needs.engine import recalculate_wealth_needs

DATASET_PATH = "../data/synthetic/families.json"
PROFILE_RULES_PATH = "../data/rules/client_profile_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"client-profile-{role}",
        role=role,
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _seed() -> dict[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(session, DATASET_PATH, reset=True)
        return {item.code: item.id for item in session.scalars(select(Household)).all()}


async def _api_request(
    method: str,
    path: str,
    *,
    role: str = "admin",
    headers: Mapping[str, str] | None = None,
) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(
            method,
            path,
            headers={
                "X-Actor-ID": f"client-profile-{role}",
                "X-Actor-Role": role,
                **(dict(headers) if headers else {}),
            },
        )


def _call(
    method: str,
    path: str,
    *,
    role: str = "admin",
) -> Response:
    return asyncio.run(_api_request(method, path, role=role))


def test_profile_and_need_snapshots_are_deterministic_audited_and_ranked() -> None:
    household_ids = _seed()
    with SessionLocal() as session:
        for household_id in household_ids.values():
            first = recalculate_client_profile(
                session,
                household_id,
                _actor(),
                PROFILE_RULES_PATH,
                ANALYSIS_DATE,
            )
            second = recalculate_client_profile(
                session,
                household_id,
                _actor(),
                PROFILE_RULES_PATH,
                ANALYSIS_DATE,
            )
            assert second.profile.id == first.profile.id
            assert first.profile.profile_hash == second.profile.profile_hash
            assert first.profile.status in {
                ClientProfileStatus.ACTIVE,
                ClientProfileStatus.NEEDS_REVIEW,
            }
            assert len(first.tags) >= 3
            assert all(tag.source_record_ids for tag in first.tags)
            assert all("rule" in tag.evidence for tag in first.tags)

            needs = recalculate_wealth_needs(
                session,
                household_id,
                _actor(),
                PROFILE_RULES_PATH,
                ANALYSIS_DATE,
            )
            repeated = recalculate_wealth_needs(
                session,
                household_id,
                _actor(),
                PROFILE_RULES_PATH,
                ANALYSIS_DATE,
            )
            assert [item.id for item in repeated.needs] == [item.id for item in needs.needs]
            assert len(needs.needs) >= 4
            assert {item.need_type for item in needs.needs} <= set(WealthNeedType)
            assert [item.priority for item in needs.needs] == list(range(1, len(needs.needs) + 1))
            priority_by_need = {item.wealth_need_id: item for item in needs.priorities}
            assert set(priority_by_need) == {item.id for item in needs.needs}
            assert all(
                priority_by_need[item.id].priority_rank == item.priority for item in needs.needs
            )

        profile_count = session.scalar(select(func.count()).select_from(ClientWealthProfile))
        tag_count = session.scalar(select(func.count()).select_from(ClientProfileTag))
        need_count = session.scalar(select(func.count()).select_from(WealthNeed))
        priority_count = session.scalar(select(func.count()).select_from(WealthNeedPriority))
        audit_count = session.scalar(select(func.count()).select_from(AuditEvent))
        assert profile_count == 3
        assert tag_count is not None and tag_count >= 9
        assert need_count is not None and need_count > 12
        assert priority_count is not None and priority_count > 12
        assert audit_count is not None and audit_count > 0


def test_six_target_profiles_come_from_facts_and_allow_multiple_tags() -> None:
    household_ids = _seed()
    rules = load_client_profile_rules(PROFILE_RULES_PATH)
    with SessionLocal() as session:
        facts_a = load_household_facts(session, household_ids["DEMO_A"])
        facts_b = load_household_facts(session, household_ids["DEMO_B"])
        facts_c = load_household_facts(session, household_ids["DEMO_C"])
        graph_a = build_financial_graph(session, facts_a.id, _actor())
        graph_b = build_financial_graph(session, facts_b.id, _actor())
        graph_c = build_financial_graph(session, facts_c.id, _actor())

        high_income = replace(
            facts_a,
            members=(replace(facts_a.members[0], occupation="心内科医生"),),
            incomes=(replace(facts_a.incomes[0], amount=Decimal("800000.00")),),
        )
        founder = replace(
            facts_a,
            members=(replace(facts_a.members[0], occupation="科技企业创始人"),),
            incomes=(replace(facts_a.incomes[0], income_type=IncomeType.BUSINESS),),
        )
        scientist = replace(
            facts_a,
            members=(replace(facts_a.members[0], occupation="科研院研究员"),),
        )
        retiree = replace(
            facts_c,
            lifecycle_stage=LifecycleStage.RETIREMENT_AND_LEGACY,
        )
        scenarios = {
            "young_worker": (facts_a, graph_a),
            "middle_class_family": (facts_b, graph_b),
            "high_income_professional": (high_income, graph_a),
            "founder": (founder, graph_a),
            "scientist": (scientist, graph_a),
            "retiree": (retiree, graph_c),
        }
        calculations = {
            code: derive_client_profile(facts, graph, rules, ANALYSIS_DATE)
            for code, (facts, graph) in scenarios.items()
        }
        for code, calculation in calculations.items():
            tag_codes = {item.tag_code for item in calculation.tags}
            assert code in tag_codes, (code, tag_codes)
            assert len(tag_codes) >= 3
        assert (
            calculations["young_worker"].profile_hash
            != calculations["high_income_professional"].profile_hash
        )


def test_profile_api_is_flagged_rbac_versioned_and_reacts_to_fact_changes(
    monkeypatch: Any,
) -> None:
    household_id = _seed()["DEMO_A"]
    profile_path = f"/api/v1/households/{household_id}/client-profile"
    needs_path = f"/api/v1/households/{household_id}/wealth-needs"

    monkeypatch.setenv("ENABLE_V5_CLIENT_PROFILE", "false")
    get_settings.cache_clear()
    disabled = _call("GET", profile_path)
    assert disabled.status_code == 404
    assert disabled.json()["error"]["code"] == "feature_not_enabled"

    monkeypatch.setenv("ENABLE_V5_CLIENT_PROFILE", "true")
    monkeypatch.setenv("CLIENT_PROFILE_RULES_PATH", PROFILE_RULES_PATH)
    get_settings.cache_clear()
    missing = _call("GET", profile_path)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "client_profile_not_calculated"

    denied = _call("POST", f"{profile_path}/recalculate", role="compliance")
    assert denied.status_code == 403
    created = _call(
        "POST",
        f"{profile_path}/recalculate?analysis_date={ANALYSIS_DATE.isoformat()}",
        role="client",
    )
    assert created.status_code == 200, created.text
    first_profile = created.json()["profile"]
    fetched = _call("GET", profile_path, role="compliance")
    assert fetched.status_code == 200
    assert fetched.json()["profile"]["id"] == first_profile["id"]

    needs = _call(
        "POST",
        f"{needs_path}/recalculate?analysis_date={ANALYSIS_DATE.isoformat()}",
        role="client",
    )
    assert needs.status_code == 200, needs.text
    assert needs.json()["needs"]
    assert _call("GET", needs_path, role="compliance").status_code == 200

    with SessionLocal() as session:
        income = session.scalar(
            select(IncomeSource).where(IncomeSource.household_id == household_id)
        )
        assert income is not None
        income.amount += Decimal("1000.00")
        income.version += 1
        session.commit()

    updated = _call(
        "POST",
        f"{profile_path}/recalculate?analysis_date={ANALYSIS_DATE.isoformat()}",
        role="client",
    )
    assert updated.status_code == 200, updated.text
    second_profile = updated.json()["profile"]
    assert second_profile["profile_hash"] != first_profile["profile_hash"]
    assert second_profile["profile_version"] == first_profile["profile_version"] + 1

    with SessionLocal() as session:
        statuses = list(
            session.scalars(
                select(ClientWealthProfile.status)
                .where(ClientWealthProfile.household_id == household_id)
                .order_by(ClientWealthProfile.profile_version)
            ).all()
        )
        assert statuses[0] == ClientProfileStatus.SUPERSEDED
        assert statuses[1] in {
            ClientProfileStatus.ACTIVE,
            ClientProfileStatus.NEEDS_REVIEW,
        }
    get_settings.cache_clear()
