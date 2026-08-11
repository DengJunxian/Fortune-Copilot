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
from app.domain.enums import AssetCategory, FinancialEntityType
from app.main import app
from app.models.family import Household
from app.models.family_enterprise import EnterpriseProfile
from app.models.finance import Asset
from app.models.financial_twin import FinancialEvent, HouseholdSnapshot
from app.models.governance import AuditEvent
from app.schemas.family_enterprise import (
    EnterpriseCreate,
    EnterpriseExposureCreate,
)
from app.services.family_enterprise.events import process_enterprise_exposures
from app.services.family_enterprise.repository import create_enterprise
from app.services.financial_graph.engine import build_financial_graph
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"
CLIENT_PROFILE_RULES_PATH = "../data/rules/client_profile_v1.json"
LIABILITY_RULES_PATH = "../data/rules/liability_engine_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
FAMILY_ENTERPRISE_RULES_PATH = "../data/rules/family_enterprise_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"family-enterprise-{role}",
        role=role,  # type: ignore[arg-type]
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _seed_hero() -> tuple[str, str]:
    actor = _actor()
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
        household = session.scalar(select(Household).where(Household.code == "DEMO_B"))
        assert household is not None
        assets = list(
            session.scalars(
                select(Asset).where(
                    Asset.household_id == household.id,
                    Asset.is_deleted.is_(False),
                )
            ).all()
        )
        financial_set = False
        property_set = False
        for asset in assets:
            if asset.category == AssetCategory.PRIMARY_RESIDENCE and not property_set:
                asset.market_value = Decimal("5000000.00")
                property_set = True
            elif not financial_set and asset.category == AssetCategory.DEMAND_DEPOSIT:
                asset.market_value = Decimal("3000000.00")
                financial_set = True
            else:
                asset.market_value = Decimal("0.00")
            asset.version += 1
        session.commit()
        graph = build_financial_graph(session, household.id, actor)
        owner = next(
            item for item in graph.entities if item.entity_type == FinancialEntityType.PERSON
        )
        return household.id, owner.id


def _enterprise_payload() -> EnterpriseCreate:
    return EnterpriseCreate(
        name="景行智造科技",
        industry="高端制造",
        stage="mature",
        jurisdiction="CN",
        currency="CNY",
        listed_status="unlisted",
        enterprise_type="operating_company",
        valuation_date=ANALYSIS_DATE,
        data_source="hero-acceptance",
        is_user_confirmed=True,
    )


def _exposure_payload(enterprise_id: str, owner_entity_id: str) -> EnterpriseExposureCreate:
    return EnterpriseExposureCreate.model_validate(
        {
            "enterprise_id": enterprise_id,
            "ownerships": [
                {
                    "owner_entity_id": owner_entity_id,
                    "ownership_ratio": "1.000000",
                    "voting_ratio": "1.000000",
                    "instrument_type": "common_equity",
                }
            ],
            "valuations": [
                {
                    "valuation_date": ANALYSIS_DATE.isoformat(),
                    "equity_value": "17000000.00",
                    "valuation_method": "user_estimate",
                    "confidence": "medium",
                    "source_kind": "client_financial_statement",
                    "evidence": {"document": "hero-case-enterprise-statement"},
                    "currency": "CNY",
                }
            ],
            "cashflows": [
                {
                    "cashflow_type": "salary",
                    "amount": "360000.00",
                    "frequency": "annual",
                    "stability": "medium",
                },
                {
                    "cashflow_type": "dividend",
                    "amount": "240000.00",
                    "frequency": "annual",
                    "stability": "low",
                },
            ],
            "guarantees": [
                {
                    "guarantee_type": "personal",
                    "guaranteed_amount": "5000000.00",
                    "outstanding_exposure": "5000000.00",
                    "expiry_date": "2029-12-31",
                }
            ],
            "liquidity_events": [
                {
                    "event_type": "ipo",
                    "expected_date": "2028-06-30",
                    "estimated_value": "17000000.00",
                    "probability": "0.350000",
                    "lockup": True,
                    "status": "planned",
                }
            ],
            "source_reference": "hero-family-enterprise-exposure",
            "is_user_confirmed": True,
        }
    )


def _engine_kwargs() -> dict[str, Any]:
    return {
        "financial_rules_path": FINANCIAL_RULES_PATH,
        "methodology_rules_path": METHODOLOGY_RULES_PATH,
        "public_data_snapshot_path": PUBLIC_DATA_PATH,
        "client_profile_rules_path": CLIENT_PROFILE_RULES_PATH,
        "liability_rules_path": LIABILITY_RULES_PATH,
        "family_enterprise_rules_path": FAMILY_ENTERPRISE_RULES_PATH,
        "analysis_date": ANALYSIS_DATE,
    }


def test_hero_family_enterprise_dependency_blocks_mechanical_equity_increase() -> None:
    household_id, owner_entity_id = _seed_hero()
    actor = _actor()
    with SessionLocal() as session:
        enterprise, _entity = create_enterprise(
            session,
            household_id,
            _enterprise_payload(),
            actor,
        )
        payload = _exposure_payload(enterprise.id, owner_entity_id)
        result = process_enterprise_exposures(
            session,
            household_id,
            payload,
            actor,
            **_engine_kwargs(),
        )
        assert result.idempotent_replay is False
        assert result.view.wealth.financial_assets == Decimal("3000000.00")
        assert result.view.wealth.property_assets == Decimal("5000000.00")
        assert result.view.wealth.enterprise_wealth == Decimal("17000000.00")
        assert result.view.wealth.economic_household_wealth == Decimal("25000000.00")
        assert result.view.income.enterprise_annual_income == Decimal("600000.00")
        assert result.view.dependency.level.value == "high"
        assert result.view.dependency.score >= Decimal("0.600000")
        assert result.view.dependency.regulatory_rating is False
        assert (
            result.view.economic_capital.unlisted_company_equity
            == Decimal("17000000.00")
        )
        assert result.view.economic_capital.liquid_securities_equity == Decimal("0.00")
        assert result.view.economic_capital.additional_equity_risk_allowed is False
        assert result.view.economic_capital.remaining_incremental_equity_capacity == 0
        assert any("机械增加权益风险" in item for item in result.view.cfs_implication.constraints)
        assert len(result.financial_event_ids) == 4

        snapshot = session.get(HouseholdSnapshot, result.snapshot_id)
        assert snapshot is not None
        assert snapshot.state_json["risk_budget"]["enterprise_dependency_level"] == "high"
        assert snapshot.state_json["risk_budget"]["additional_equity_risk_allowed"] is False
        replay = process_enterprise_exposures(
            session,
            household_id,
            payload,
            actor,
            **_engine_kwargs(),
        )
        assert replay.idempotent_replay is True
        assert replay.snapshot_id == result.snapshot_id
        assert session.scalar(select(func.count()).select_from(EnterpriseProfile)) == 1
        assert session.scalar(select(func.count()).select_from(FinancialEvent)) == 4
        assert session.scalar(select(func.count()).select_from(HouseholdSnapshot)) == 2
        assert session.scalar(select(func.count()).select_from(AuditEvent)) > 0


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
                "X-Actor-ID": f"family-enterprise-{role}",
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


def test_family_enterprise_api_is_flagged_confirmed_and_event_sourced(monkeypatch: Any) -> None:
    household_id, owner_entity_id = _seed_hero()
    base = f"/api/v1/households/{household_id}"
    monkeypatch.setenv("ENABLE_V5_FAMILY_ENTERPRISE", "false")
    get_settings.cache_clear()
    assert _call("GET", f"{base}/family-enterprise-view").status_code == 404

    for key, value in {
        "ENABLE_V5_FAMILY_ENTERPRISE": "true",
        "ENABLE_V5_PERSISTENT_TWIN": "true",
        "FINANCIAL_RULES_PATH": FINANCIAL_RULES_PATH,
        "METHODOLOGY_RULES_PATH": METHODOLOGY_RULES_PATH,
        "PUBLIC_DATA_SNAPSHOT_PATH": PUBLIC_DATA_PATH,
        "CLIENT_PROFILE_RULES_PATH": CLIENT_PROFILE_RULES_PATH,
        "LIABILITY_RULES_PATH": LIABILITY_RULES_PATH,
        "FAMILY_ENTERPRISE_RULES_PATH": FAMILY_ENTERPRISE_RULES_PATH,
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    enterprise_payload = _enterprise_payload().model_dump(mode="json")
    denied = _call("POST", f"{base}/enterprises", role="compliance", payload=enterprise_payload)
    assert denied.status_code == 403
    unconfirmed = _call("POST", f"{base}/enterprises", payload=enterprise_payload)
    assert unconfirmed.status_code == 409
    created = _call(
        "POST",
        f"{base}/enterprises",
        role="advisor",
        payload=enterprise_payload,
        headers={"X-Confirm-Action": "create_enterprise"},
    )
    assert created.status_code == 201, created.text
    enterprise_id = created.json()["enterprise"]["id"]
    exposure_payload = _exposure_payload(enterprise_id, owner_entity_id).model_dump(mode="json")
    exposure = _call(
        "POST",
        f"{base}/enterprise-exposures?analysis_date={ANALYSIS_DATE}",
        role="client",
        payload=exposure_payload,
        headers={"X-Confirm-Action": "create_enterprise_exposure"},
    )
    assert exposure.status_code == 201, exposure.text
    assert exposure.json()["view"]["dependency"]["level"] == "high"
    assert exposure.json()["view"]["economic_capital"]["additional_equity_risk_allowed"] is False
    view = _call("GET", f"{base}/family-enterprise-view?analysis_date={ANALYSIS_DATE}")
    assert view.status_code == 200
    assert view.json()["wealth"]["enterprise_wealth"] == "17000000.00"
    timeline = _call("GET", f"{base}/event-timeline")
    assert timeline.status_code == 200
    assert {item["event_domain"] for item in timeline.json()["events"]} == {"enterprise"}
    assert all(item["life_event"] is None for item in timeline.json()["events"])
    get_settings.cache_clear()
