from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.enums import CurrencyExposureType, TrustSuccessionNeedType
from app.main import app
from app.models.family import Household
from app.models.finance import Asset, FinancialGoal, IncomeSource, Liability
from app.models.specialized_cfs import (
    CurrencyExposure,
    InstitutionalEntitlement,
    PhilanthropyGoal,
    TrustSuccessionNeed,
)
from app.services.currency_exposure.engine import get_currency_exposures
from app.services.philanthropy.engine import get_philanthropy_goals
from app.services.retirement.engine import get_retirement_plan
from app.services.seed import seed_synthetic_data
from app.services.trust_succession.engine import get_trust_succession_needs

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
SPECIALIZED_RULES_PATH = "../data/rules/specialized_cfs_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"specialized-cfs-{role}",
        role=role,
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _seed(code: str) -> str:
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
        household = session.scalar(select(Household).where(Household.code == code))
        assert household is not None
        return household.id


def test_retirement_plan_normalizes_entitlements_and_is_idempotent() -> None:
    household_id = _seed("DEMO_C")
    with SessionLocal() as session:
        first = get_retirement_plan(
            session,
            household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert first.output.retirement_floor > 0
        assert first.output.guaranteed_income >= 0
        assert first.liabilities.improved_retirement_goal >= first.output.longevity_gap
        assert first.entitlements
        assert {item.entitlement_type.value for item in first.entitlements} >= {
            "social_security",
            "financial_withdrawal",
        }
        entitlement_count = session.scalar(
            select(func.count()).select_from(InstitutionalEntitlement)
        )

        replay = get_retirement_plan(
            session,
            household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert replay.meta.input_hash == first.meta.input_hash
        assert session.scalar(
            select(func.count()).select_from(InstitutionalEntitlement)
        ) == entitlement_count
        assert "投资收益" in replay.boundary


def test_currency_exposure_keeps_source_currency_and_detects_both_directions() -> None:
    household_id = _seed("DEMO_B")
    with SessionLocal() as session:
        asset = session.scalar(select(Asset).where(Asset.household_id == household_id))
        income = session.scalar(
            select(IncomeSource).where(IncomeSource.household_id == household_id)
        )
        liability = session.scalar(
            select(Liability).where(Liability.household_id == household_id)
        )
        goal = session.scalar(
            select(FinancialGoal).where(FinancialGoal.household_id == household_id)
        )
        assert asset is not None
        assert income is not None
        assert liability is not None
        assert goal is not None
        for record in (asset, income, liability, goal):
            record.currency = "USD"
            record.version += 1
        session.commit()

        result = get_currency_exposures(
            session,
            household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        detected_types = {item.exposure_type for item in result.exposures}
        assert CurrencyExposureType.ASSET_CURRENCY in detected_types
        assert CurrencyExposureType.INCOME_CURRENCY in detected_types
        assert CurrencyExposureType.LIABILITY_CURRENCY in detected_types
        assert CurrencyExposureType.FUTURE_OBLIGATION in detected_types
        assert result.base_currency == "CNY"
        assert result.material_exposure_detected is True
        assert result.summaries[0].currency == "USD"
        assert result.summaries[0].inflow > 0
        assert result.summaries[0].outflow > 0
        exposure_count = session.scalar(select(func.count()).select_from(CurrencyExposure))
        get_currency_exposures(
            session,
            household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert session.scalar(select(func.count()).select_from(CurrencyExposure)) == exposure_count
        assert "不提供法律、税务" in result.boundary


def test_trust_needs_are_evidence_triggered_and_not_defaulted_for_young_single() -> None:
    single_household_id = _seed("DEMO_A")
    with SessionLocal() as session:
        empty = get_trust_succession_needs(
            session,
            single_household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert empty.need_detected is False
        assert empty.outcome == "NO_NEED_DETECTED"
        assert session.scalar(select(func.count()).select_from(TrustSuccessionNeed)) == 0

    family_household_id = _seed("DEMO_B")
    with SessionLocal() as session:
        result = get_trust_succession_needs(
            session,
            family_household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert result.need_detected is True
        assert result.outcome == "EXPERT_REVIEW_REQUIRED"
        assert TrustSuccessionNeedType.MINOR_BENEFICIARY in {
            item.need_type for item in result.needs
        }
        assert all(item.professional_review_required for item in result.needs)
        assert all(item.complexity_gate_passed for item in result.routes)
        assert "不输出遗嘱" in result.boundary


def test_philanthropy_is_created_only_from_an_explicit_household_goal() -> None:
    household_id = _seed("DEMO_C")
    with SessionLocal() as session:
        household = session.get(Household, household_id)
        assert household is not None
        absent = get_philanthropy_goals(
            session,
            household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert absent.has_explicit_goal is False

        household.planning_preferences = {
            **household.planning_preferences,
            "philanthropy_annual_budget": "180000.00",
            "philanthropy_target_cause": "乡村青少年金融教育",
            "philanthropy_family_participation": "家庭成员共同参与年度复盘",
            "philanthropy_governance_preference": "预算与受益结果分开复核",
        }
        household.version += 1
        session.commit()
        result = get_philanthropy_goals(
            session,
            household_id,
            _actor(),
            SPECIALIZED_RULES_PATH,
            ANALYSIS_DATE,
        )
        assert result.has_explicit_goal is True
        assert result.goals[0].annual_budget == Decimal("180000.00")
        assert result.goals[0].professional_review_required is True
        assert result.route.specialist_type is not None
        assert session.scalar(select(func.count()).select_from(PhilanthropyGoal)) == 1
        assert "不与产品销售绑定" in result.boundary


async def _api_request(path: str, role: str = "client") -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(
            path,
            headers={
                "X-Actor-ID": f"specialized-api-{role}",
                "X-Actor-Role": role,
            },
        )


def _call(path: str, role: str = "client") -> Response:
    return asyncio.run(_api_request(path, role))


def test_specialized_cfs_read_apis_are_flagged_and_return_boundaries(
    monkeypatch: Any,
) -> None:
    household_id = _seed("DEMO_B")
    base = f"/api/v1/households/{household_id}"
    monkeypatch.setenv("ENABLE_V5_CFS", "false")
    get_settings.cache_clear()
    assert _call(f"{base}/retirement-plan").status_code == 404

    monkeypatch.setenv("ENABLE_V5_CFS", "true")
    monkeypatch.setenv("SPECIALIZED_CFS_RULES_PATH", SPECIALIZED_RULES_PATH)
    get_settings.cache_clear()
    for endpoint in (
        "retirement-plan",
        "currency-exposures",
        "trust-succession-needs",
        "philanthropy-goals",
    ):
        response = _call(
            f"{base}/{endpoint}?analysis_date={ANALYSIS_DATE}",
            role="compliance",
        )
        assert response.status_code == 200, response.text
        assert response.json()["meta"]["calculation_source"] == "deterministic_tools"
        assert response.json()["boundary"]
    get_settings.cache_clear()
