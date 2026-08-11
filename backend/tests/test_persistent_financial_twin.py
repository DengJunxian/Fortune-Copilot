from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.family import Household
from app.models.finance import IncomeSource
from app.models.financial_twin import FinancialEvent, HouseholdSnapshot
from app.models.governance import AuditEvent, SimulationRun
from app.schemas.financial_twin import LifeEventCreate
from app.schemas.twin import TwinRunRequest
from app.services.financial_twin.engine import get_or_build_wealth_twin
from app.services.financial_twin.events import process_life_event
from app.services.financial_twin.snapshot import load_twin_model_input
from app.services.seed import seed_synthetic_data
from app.services.twin.engine import start_twin_run

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"
CLIENT_PROFILE_RULES_PATH = "../data/rules/client_profile_v1.json"
LIABILITY_RULES_PATH = "../data/rules/liability_engine_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"persistent-twin-{role}",
        role=role,  # type: ignore[arg-type]
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _seed() -> dict[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            twin_rules_path=TWIN_RULES_PATH,
            reset=True,
        )
        return {item.code: item.id for item in session.scalars(select(Household)).all()}


def _twin_kwargs() -> dict[str, Any]:
    return {
        "financial_rules_path": FINANCIAL_RULES_PATH,
        "methodology_rules_path": METHODOLOGY_RULES_PATH,
        "public_data_snapshot_path": PUBLIC_DATA_PATH,
        "client_profile_rules_path": CLIENT_PROFILE_RULES_PATH,
        "liability_rules_path": LIABILITY_RULES_PATH,
        "analysis_date": ANALYSIS_DATE,
    }


def _salary_event() -> LifeEventCreate:
    return LifeEventCreate(
        event_date=ANALYSIS_DATE,
        income_change_ratio=Decimal("-0.300000"),
        source_reference="acceptance-salary-minus-30",
        is_user_confirmed=True,
    )


def test_salary_event_creates_snapshot_recalculates_and_replay_is_idempotent() -> None:
    household_id = _seed()["DEMO_B"]
    actor = _actor()
    with SessionLocal() as session:
        baseline = get_or_build_wealth_twin(session, household_id, actor, **_twin_kwargs())
        repeated_baseline = get_or_build_wealth_twin(
            session,
            household_id,
            actor,
            **_twin_kwargs(),
        )
        assert repeated_baseline.current.id == baseline.current.id
        before_income = Decimal(baseline.current.state.facts.annual_income)
        before_model = load_twin_model_input(session, household_id, baseline.current.id)
        assert (
            Decimal(str(sum(item.monthly_amount for item in before_model.incomes) * 12)).quantize(
                Decimal("0.01")
            )
            == before_income
        )

        processed = process_life_event(
            session,
            household_id,
            _salary_event(),
            actor,
            **_twin_kwargs(),
        )
        after_income = Decimal(processed.snapshot.state.facts.annual_income)
        assert processed.idempotent_replay is False
        assert processed.snapshot.id != baseline.current.id
        assert processed.snapshot.parent_snapshot_id == baseline.current.id
        assert after_income == (before_income * Decimal("0.70")).quantize(Decimal("0.01"))
        assert any(item.code == "annual_income" for item in processed.comparison.changed_facts)
        assert processed.comparison.has_material_change is True
        assert processed.event.processed_snapshot_id == processed.snapshot.id

        amount_after_first = session.scalar(
            select(func.sum(IncomeSource.amount)).where(
                IncomeSource.household_id == household_id,
                IncomeSource.is_deleted.is_(False),
            )
        )
        replay = process_life_event(
            session,
            household_id,
            _salary_event(),
            actor,
            **_twin_kwargs(),
        )
        amount_after_replay = session.scalar(
            select(func.sum(IncomeSource.amount)).where(
                IncomeSource.household_id == household_id,
                IncomeSource.is_deleted.is_(False),
            )
        )
        assert replay.idempotent_replay is True
        assert replay.snapshot.id == processed.snapshot.id
        assert amount_after_replay == amount_after_first
        assert session.scalar(select(func.count()).select_from(FinancialEvent)) == 1
        assert session.scalar(select(func.count()).select_from(HouseholdSnapshot)) == 2
        assert session.scalar(select(func.count()).select_from(AuditEvent)) > 0


def test_persistent_snapshot_can_seed_existing_twin_simulator() -> None:
    household_id = _seed()["DEMO_A"]
    actor = _actor()
    with SessionLocal() as session:
        persistent = get_or_build_wealth_twin(session, household_id, actor, **_twin_kwargs())
        request = TwinRunRequest(
            household_snapshot_id=persistent.current.id,
            analysis_date=ANALYSIS_DATE,
            path_count=100,
            horizon_years=5,
            scenario_codes=["unemployment_equity_down_30"],
        )
        status = start_twin_run(
            session,
            household_id,
            request,
            actor,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            TWIN_RULES_PATH,
        )
        run = session.get(SimulationRun, status.run_id)
        assert run is not None
        assert status.household_snapshot_id == persistent.current.id
        assert run.household_snapshot_id == persistent.current.id
        assert run.inputs["household_snapshot_hash"] == persistent.current.snapshot_hash


async def _api_request(
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={
                "X-Actor-ID": f"persistent-twin-{role}",
                "X-Actor-Role": role,
                **(dict(headers) if headers else {}),
            },
        )


def _call(
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    return asyncio.run(_api_request(method, path, role=role, payload=payload, headers=headers))


def test_persistent_twin_api_is_flagged_confirmed_and_object_scoped(monkeypatch: Any) -> None:
    household_id = _seed()["DEMO_B"]
    twin_path = f"/api/v1/households/{household_id}/wealth-twin"
    event_path = f"/api/v1/households/{household_id}/life-events"

    monkeypatch.setenv("ENABLE_V5_PERSISTENT_TWIN", "false")
    get_settings.cache_clear()
    assert _call("GET", twin_path).status_code == 404

    for key, value in {
        "ENABLE_V5_PERSISTENT_TWIN": "true",
        "FINANCIAL_RULES_PATH": FINANCIAL_RULES_PATH,
        "METHODOLOGY_RULES_PATH": METHODOLOGY_RULES_PATH,
        "PUBLIC_DATA_SNAPSHOT_PATH": PUBLIC_DATA_PATH,
        "CLIENT_PROFILE_RULES_PATH": CLIENT_PROFILE_RULES_PATH,
        "LIABILITY_RULES_PATH": LIABILITY_RULES_PATH,
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    current = _call("GET", f"{twin_path}?analysis_date={ANALYSIS_DATE}")
    assert current.status_code == 200, current.text
    assert current.json()["meta"]["snapshot_count"] == 1

    payload = _salary_event().model_dump(mode="json")
    denied = _call("POST", event_path, role="compliance", payload=payload)
    assert denied.status_code == 403
    unconfirmed = _call("POST", event_path, role="client", payload=payload)
    assert unconfirmed.status_code == 409
    created = _call(
        "POST",
        f"{event_path}?analysis_date={ANALYSIS_DATE}",
        role="client",
        payload=payload,
        headers={"X-Confirm-Action": "create_life_event"},
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["idempotent_replay"] is False
    assert created_body["comparison"]["has_material_change"] is True

    timeline = _call("GET", f"/api/v1/households/{household_id}/event-timeline")
    assert timeline.status_code == 200
    assert timeline.json()["total"] == 1
    snapshot_id = created_body["snapshot"]["id"]
    snapshot = _call("GET", f"{twin_path}/snapshots/{snapshot_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["id"] == snapshot_id

    replay = _call(
        "POST",
        f"{event_path}?analysis_date={ANALYSIS_DATE}",
        role="client",
        payload=payload,
        headers={"X-Confirm-Action": "create_life_event"},
    )
    assert replay.status_code == 201
    assert replay.json()["idempotent_replay"] is True
    get_settings.cache_clear()
