from __future__ import annotations

import asyncio
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal, build_engine
from app.main import app
from app.models import Base
from app.models.family import Household
from app.models.finance import Asset
from app.models.governance import AuditEvent
from app.models.wealth_graph import FinancialAccount, FinancialEntity, Position
from app.services.financial.facts import load_household_facts
from app.services.financial_graph.engine import build_financial_graph, validate_graph_integrity
from app.services.financial_graph.projection import (
    compare_legacy_projection,
    project_graph_to_household_facts,
)
from app.services.planning.engine import plan_household
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"
ANALYSIS_DATE = date(2026, 8, 4)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"financial-graph-{role}",
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
            reset=True,
        )
        return {
            item.code: item.id for item in session.scalars(select(Household)).all()
        }


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
                "X-Actor-ID": f"financial-graph-{role}",
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
    return asyncio.run(
        _api_request(method, path, role=role, payload=payload, headers=headers)
    )


def test_graph_projection_matches_v4_assets_for_all_three_demo_households() -> None:
    household_ids = _seed()
    with SessionLocal() as session:
        for code, household_id in household_ids.items():
            before = plan_household(
                session,
                household_id,
                FINANCIAL_RULES_PATH,
                PLANNING_RULES_PATH,
                ANALYSIS_DATE,
                methodology_rules_path=METHODOLOGY_RULES_PATH,
                public_data_snapshot_path=PUBLIC_DATA_PATH,
            )
            legacy = load_household_facts(session, household_id)
            graph = build_financial_graph(session, household_id, _actor())
            projected = project_graph_to_household_facts(session, household_id, graph)
            diagnostic = compare_legacy_projection(session, household_id, graph)
            after = plan_household(
                session,
                household_id,
                FINANCIAL_RULES_PATH,
                PLANNING_RULES_PATH,
                ANALYSIS_DATE,
                methodology_rules_path=METHODOLOGY_RULES_PATH,
                public_data_snapshot_path=PUBLIC_DATA_PATH,
            )

            assert diagnostic.status == "matched", (code, diagnostic.details)
            assert diagnostic.difference <= Decimal("0.01")
            assert {item.id: item.market_value for item in projected.assets} == {
                item.id: item.market_value for item in legacy.assets
            }
            assert before.denominators == after.denominators
            assert validate_graph_integrity(graph).status == "passed"


def test_first_graph_read_is_concurrency_safe(tmp_path: Path) -> None:
    target_engine = build_engine(f"sqlite:///{tmp_path / 'graph-race.sqlite'}")
    target_sessions = sessionmaker(
        bind=target_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(target_engine)
    with target_sessions() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            reset=True,
        )
        household_id = session.scalar(
            select(Household.id).where(Household.code == "DEMO_A")
        )
        assert household_id is not None

    ready = Barrier(6)

    def read_graph() -> tuple[int, int]:
        with target_sessions() as session:
            ready.wait()
            graph = build_financial_graph(session, household_id, _actor())
            return len(graph.entities), len(graph.positions)

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: read_graph(), range(6)))
    assert len(set(results)) == 1

    with target_sessions() as session:
        entity_count = session.scalar(
            select(func.count())
            .select_from(FinancialEntity)
            .where(
                FinancialEntity.household_id == household_id,
                FinancialEntity.external_reference
                == f"legacy:household:{household_id}",
            )
        )
        account_count = session.scalar(
            select(func.count())
            .select_from(FinancialAccount)
            .where(
                FinancialAccount.household_id == household_id,
                FinancialAccount.external_reference == f"legacy:assets:{household_id}",
            )
        )
        asset_count = session.scalar(
            select(func.count())
            .select_from(Asset)
            .where(Asset.household_id == household_id, Asset.is_deleted.is_(False))
        )
        position_count = session.scalar(
            select(func.count())
            .select_from(Position)
            .where(
                Position.household_id == household_id,
                Position.legacy_asset_id.is_not(None),
            )
        )
    assert entity_count == 1
    assert account_count == 1
    assert position_count == asset_count
    target_engine.dispose()


def test_financial_graph_api_is_flagged_rbac_audited_and_versioned(monkeypatch: Any) -> None:
    household_id = _seed()["DEMO_A"]
    graph_path = f"/api/v1/households/{household_id}/financial-graph"

    monkeypatch.setenv("ENABLE_V5_FINANCIAL_GRAPH", "false")
    get_settings.cache_clear()
    disabled = _call("GET", graph_path)
    assert disabled.status_code == 404
    assert disabled.json()["error"]["code"] == "feature_not_enabled"

    monkeypatch.setenv("ENABLE_V5_FINANCIAL_GRAPH", "true")
    get_settings.cache_clear()
    graph = _call("GET", graph_path)
    assert graph.status_code == 200, graph.text
    assert graph.json()["integrity"]["status"] == "passed"
    assert graph.json()["projection_diagnostic"]["status"] == "matched"

    payload = {
        "currency": "CNY",
        "valuation_date": "2026-08-10",
        "data_source": "client_intake",
        "is_user_confirmed": True,
        "account": {
            "provider_name": "工商银行（客户自报）",
            "account_type": "securities_custody",
            "account_wrapper": "ordinary",
            "jurisdiction": "CN",
        },
        "instrument_type": "public_fund",
        "instrument_code": "SELF-REPORTED-001",
        "name": "客户补充的宽基基金持仓",
        "quantity": "1200.00000000",
        "acquisition_cost": "11500.00",
        "market_value": "12345.67",
        "purpose_dimension": "growth",
        "risk_level": "medium_high",
        "liquidity_days": 1,
        "complexity_level": "standard",
        "principal_loss_possible": True,
        "legally_principal_guaranteed": False,
        "lock_up": False,
        "source_kind": "user_self_report",
        "evidence_json": {"ownership": "本人", "confirmation": "explicit"},
    }
    denied = _call(
        "POST",
        f"{graph_path}/positions",
        role="compliance",
        payload=payload,
    )
    assert denied.status_code == 403

    created = _call("POST", f"{graph_path}/positions", role="client", payload=payload)
    assert created.status_code == 201, created.text
    position = created.json()
    assert position["market_value"] == "12345.67"
    assert position["version"] == 1

    updated = _call(
        "PATCH",
        f"{graph_path}/positions/{position['id']}",
        role="advisor",
        payload={
            "expected_version": 1,
            "market_value": "12400.00",
            "valuation_date": "2026-08-10",
            "is_user_confirmed": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["market_value"] == "12400.00"

    unconfirmed_delete = _call(
        "DELETE",
        f"{graph_path}/positions/{position['id']}?expected_version=2",
        role="client",
    )
    assert unconfirmed_delete.status_code == 409
    deleted = _call(
        "DELETE",
        f"{graph_path}/positions/{position['id']}?expected_version=2",
        role="client",
        headers={"X-Confirm-Action": "delete_financial_graph_position"},
    )
    assert deleted.status_code == 204

    with SessionLocal() as session:
        audit_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.household_id == household_id)
        )
        assert audit_count is not None and audit_count >= 3

    monkeypatch.setenv("ENABLE_V5_FINANCIAL_GRAPH", "false")
    get_settings.cache_clear()
