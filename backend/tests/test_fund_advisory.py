from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.family import Household
from app.services.fund_advisory.catalog import load_fund_advisory_catalog
from app.services.fund_advisory.engine import advise_household
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
FUND_CATALOG_PATH = "../data/products/verified_real_funds_v1.json"


async def api_request(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=payload)


def call(method: str, path: str) -> Response:
    return asyncio.run(api_request(method, path))


def seed_households() -> dict[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            portfolio_rules_path=PORTFOLIO_RULES_PATH,
            product_catalog_path=PRODUCT_CATALOG_PATH,
        )
        return {
            item.code: item.id
            for item in session.scalars(select(Household).where(Household.is_deleted.is_(False)))
        }


def test_verified_catalog_rejects_fabricated_and_thematic_boundaries() -> None:
    catalog = load_fund_advisory_catalog(FUND_CATALOG_PATH)
    assert catalog.catalog_version == "1.0.0"
    assert len(catalog.products) == 8
    assert {item.code for item in catalog.products} == {
        "482002",
        "006834",
        "000402",
        "005102",
        "164809",
        "020189",
        "022935",
        "022982",
    }
    for item in catalog.products:
        assert len(item.code) == 6 and item.code.isdigit()
        assert item.principal_guaranteed is False
        assert item.sector_or_thematic is False
        assert item.leveraged is False
        assert item.inverse is False
        supports = {support for evidence in item.evidence for support in evidence.supports}
        assert {"product_identity", "fund_terms"} <= supports
        if item.icbc_publicly_listed:
            assert "icbc_public_listing" in supports
        if item.personal_pension_eligible:
            assert "pension_eligibility" in supports
        if item.category in {"domestic_broad_index", "pension_broad_index"}:
            assert item.broad_index is True
            assert item.tracked_index in {"沪深300指数", "中证500指数", "中证A500指数"}


def test_catalog_api_discloses_channel_boundary_and_exact_codes() -> None:
    response = call(
        "GET",
        "/api/v1/fund-advisory/products?analysis_date=2026-08-07",
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_type"] == "verified_real_public_funds"
    assert payload["catalog_stale"] is False
    assert payload["product_count"] == 8
    assert "不等于" in payload["mandatory_channel_notice"]
    assert "020189" in payload["personal_pension_catalog_observation"]


def test_icbc_only_advice_uses_only_icbc_listed_real_funds() -> None:
    household_id = seed_households()["DEMO_B"]
    with SessionLocal() as session:
        result = advise_household(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            PORTFOLIO_RULES_PATH,
            PRODUCT_CATALOG_PATH,
            FUND_CATALOG_PATH,
            date(2026, 8, 7),
            icbc_only=True,
        )
    assert result.meta.icbc_only is True
    assert result.meta.catalog_stale is False
    by_sleeve = {item.sleeve_code: item for item in result.sleeves}
    assert by_sleeve["personal_pension"].source_amount == Decimal("30000.00")
    assert by_sleeve["personal_pension"].status == "channel_verification_required"
    assert by_sleeve["personal_pension"].allocations[0].allocation_type == "unallocated_guardrail"
    pension_candidates = {
        item.product_code: item for item in by_sleeve["personal_pension"].candidate_products
    }
    assert pension_candidates["020189"].status == "channel_verification_required"
    assert "022935" in pension_candidates and "022982" in pension_candidates
    for sleeve in result.sleeves:
        allocated = sum((item.amount for item in sleeve.allocations), Decimal("0"))
        assert allocated == sleeve.source_amount
        for allocation in sleeve.allocations:
            if allocation.allocation_type == "fund":
                assert allocation.product_code is not None
                assert allocation.icbc_publicly_listed is True


def test_non_icbc_mode_can_use_verified_pension_bond_without_claiming_icbc_sale() -> None:
    household_id = seed_households()["DEMO_B"]
    response = call(
        "GET",
        f"/api/v1/households/{household_id}/fund-advisory"
        "?analysis_date=2026-08-07&icbc_only=false",
    )
    assert response.status_code == 200, response.text
    pension = next(
        item for item in response.json()["sleeves"] if item["sleeve_code"] == "personal_pension"
    )
    bond = next(item for item in pension["allocations"] if item.get("product_code") == "020189")
    assert Decimal(bond["ratio"]) == Decimal("0.30")
    assert bond["icbc_publicly_listed"] is False
    assert "不视为工行可售" in bond["purchase_route"]


def test_mixed_pension_record_is_not_guessed_or_allocated() -> None:
    household_id = seed_households()["DEMO_C"]
    response = call(
        "GET",
        f"/api/v1/households/{household_id}/fund-advisory?analysis_date=2026-08-07",
    )
    assert response.status_code == 200, response.text
    pension = next(
        item for item in response.json()["sleeves"] if item["sleeve_code"] == "personal_pension"
    )
    assert pension["source_amount"] == "0.00"
    assert pension["allocations"] == []
    assert "未猜测可支配金额" in pension["explanation"]


def test_stale_catalog_blocks_all_fund_allocations() -> None:
    household_id = seed_households()["DEMO_B"]
    response = call(
        "GET",
        f"/api/v1/households/{household_id}/fund-advisory?analysis_date=2026-12-31",
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["catalog_stale"] is True
    assert all(
        allocation["allocation_type"] != "fund"
        for sleeve in payload["sleeves"]
        for allocation in sleeve["allocations"]
    )
