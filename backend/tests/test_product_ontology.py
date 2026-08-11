from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.enums import CFSComponentType, ProductEligibilityDecision, ProductFamily
from app.main import app
from app.models.cfs import CFSSolution, CFSSolutionComponent
from app.models.family import Household
from app.models.governance import ProductSnapshot
from app.schemas.cfs import CFSComposeRequest
from app.schemas.product_ontology import (
    ProductEligibilityContext,
    ProductRankRequest,
    ProductRiskBudgetInput,
)
from app.services.cfs_composer.engine import compose_cfs_solution
from app.services.product_ontology.adapter import ensure_verified_fund_ontology
from app.services.product_ontology.composition import compose_cfs_product_candidates
from app.services.product_ontology.ranking import rank_products
from app.services.seed import seed_synthetic_data

CATALOG_PATH = "../data/products/verified_real_funds_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor() -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id="product-ontology-admin",
        role="admin",
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _context(
    need: str = "long_term_growth",
    *,
    analysis_date: date = ANALYSIS_DATE,
) -> ProductEligibilityContext:
    return ProductEligibilityContext(
        need=need,
        risk_budget=ProductRiskBudgetInput(
            maximum_risk_level="r3",
            additional_risk_allowed=True,
            remaining_capacity="1000000.00",
        ),
        account_wrapper="ordinary",
        horizon_days=3650,
        maximum_lockup_days=1095,
        client_qualification="retail",
        channel="icbc",
        analysis_date=analysis_date,
    )


def test_verified_fund_adapter_reuses_products_and_persists_versioned_snapshots() -> None:
    with SessionLocal() as session:
        catalog, products, snapshots = ensure_verified_fund_ontology(session, CATALOG_PATH)
        assert len(products) == len(catalog.products) == 8
        assert len(snapshots) == 8
        assert session.scalar(select(func.count()).select_from(ProductSnapshot)) == 8
        assert all(not item.is_simulated for item in products)
        assert {item.product_family for item in products} == {
            ProductFamily.MONEY_MARKET_FUND,
            ProductFamily.BOND_FUND,
            ProductFamily.EQUITY_INDEX_FUND,
            ProductFamily.PERSONAL_PENSION_PRODUCT,
        }
        assert all(item.sale_status == "channel_verification_required" for item in snapshots)
        assert all(item.snapshot_hash for item in snapshots)

        replay_catalog, replay_products, replay_snapshots = ensure_verified_fund_ontology(
            session, CATALOG_PATH
        )
        assert replay_catalog.catalog_version == catalog.catalog_version
        assert [item.id for item in replay_products] == [item.id for item in products]
        assert [item.id for item in replay_snapshots] == [item.id for item in snapshots]
        assert session.scalar(select(func.count()).select_from(ProductSnapshot)) == 8


def test_buy_side_ranking_never_rewards_distribution_incentives_and_supports_no_product() -> None:
    with SessionLocal() as session:
        catalog, products, snapshots = ensure_verified_fund_ontology(session, CATALOG_PATH)
        by_product = {item.product_id: item for item in snapshots}
        request = ProductRankRequest(context=_context(), maximum_candidates=8)
        before = rank_products(products, by_product, request, catalog)
        assert before.result == "ranked"
        assert before.executable_recommendation_allowed is False
        before_scores = {item.product.id: item.score for item in before.candidates}

        candidate = before.candidates[0].product
        product = next(item for item in products if item.id == candidate.id)
        product.distribution_incentive_disclosure = "渠道激励提高至 1.00%。"
        after = rank_products(products, by_product, request, catalog)
        after_scores = {item.product.id: item.score for item in after.candidates}
        assert after_scores[product.id] == before_scores[product.id]
        assert next(item.rank for item in after.candidates if item.product.id == product.id) >= 1

        none = rank_products(
            products,
            by_product,
            ProductRankRequest(context=_context("unsupported_need"), maximum_candidates=3),
            catalog,
        )
        assert none.result == "no_product"
        assert none.candidates == []
        assert len(none.excluded) == len(products)
        assert "有效方案" in (none.no_product_reason or "")


def test_stale_catalog_is_education_only_and_never_executable() -> None:
    with SessionLocal() as session:
        catalog, products, snapshots = ensure_verified_fund_ontology(session, CATALOG_PATH)
        result = rank_products(
            products,
            {item.product_id: item for item in snapshots},
            ProductRankRequest(
                context=_context(analysis_date=date(2026, 10, 1)),
                maximum_candidates=3,
            ),
            catalog,
        )
        assert result.catalog_stale is True
        assert result.executable_recommendation_allowed is False
        assert result.candidates
        assert {
            item.eligibility.decision for item in result.candidates
        } == {ProductEligibilityDecision.EDUCATION_ONLY}


def _seed_cfs() -> tuple[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            "../data/synthetic/families.json",
            rules_path="../data/rules/financial_health_v1.json",
            planning_rules_path="../data/rules/planning_waterfall_v1.json",
            methodology_rules_path="../data/rules/wealth_methodology_v3.json",
            twin_rules_path="../data/rules/twin_simulation_v1.json",
            reset=True,
        )
        household = session.scalar(select(Household).where(Household.code == "DEMO_B"))
        assert household is not None
        result = compose_cfs_solution(
            session,
            household.id,
            CFSComposeRequest(is_user_confirmed=True),
            _actor(),
            financial_rules_path="../data/rules/financial_health_v1.json",
            planning_rules_path="../data/rules/planning_waterfall_v1.json",
            methodology_rules_path="../data/rules/wealth_methodology_v3.json",
            public_data_snapshot_path="../data/public/authoritative_public_snapshot_v1.json",
            client_profile_rules_path="../data/rules/client_profile_v1.json",
            liability_rules_path="../data/rules/liability_engine_v1.json",
            family_enterprise_rules_path="../data/rules/family_enterprise_v1.json",
            cfs_rules_path="../data/rules/cfs_composer_v1.json",
            analysis_date=ANALYSIS_DATE,
        )
        return household.id, result.solution.id


def test_cfs_component_maps_to_zero_or_many_candidates_without_equating_plan_and_product() -> None:
    household_id, solution_id = _seed_cfs()
    with SessionLocal() as session:
        no_products = compose_cfs_product_candidates(
            session,
            household_id,
            solution_id,
            CATALOG_PATH,
            analysis_date=ANALYSIS_DATE,
        )
        assert no_products.groups
        assert all(item.result == "no_product" for item in no_products.groups)

        solution = session.get(CFSSolution, solution_id)
        component = session.scalar(
            select(CFSSolutionComponent).where(
                CFSSolutionComponent.solution_id == solution_id,
                CFSSolutionComponent.component_type == CFSComponentType.NO_ACTION,
            )
        )
        assert solution is not None and component is not None
        summary = dict(solution.summary)
        budget = dict(summary["risk_budget"])
        budget.update(
            {
                "household_economic_risk_capacity": "medium",
                "additional_risk_allowed": True,
                "remaining_risk_capacity": "1000000.00",
            }
        )
        summary["risk_budget"] = budget
        solution.summary = summary
        component.component_type = CFSComponentType.INVESTMENT
        component.product_mapping_allowed = True
        component.evidence = {**component.evidence, "wealth_need_type": "long_term_growth"}
        session.flush()

        mapped = compose_cfs_product_candidates(
            session,
            household_id,
            solution_id,
            CATALOG_PATH,
            analysis_date=ANALYSIS_DATE,
        )
        investment = next(
            item for item in mapped.groups if item.component_id == component.id
        )
        assert investment.result == "ranked"
        assert 1 <= len(investment.candidates) <= 3
        assert all(item.product.id for item in investment.candidates)


async def _api_request(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={"X-Actor-ID": "product-client", "X-Actor-Role": "client"},
        )


def _call(method: str, path: str, *, payload: Mapping[str, Any] | None = None) -> Response:
    return asyncio.run(_api_request(method, path, payload=payload))


def test_product_search_eligibility_and_rank_apis_are_feature_flagged(monkeypatch: Any) -> None:
    monkeypatch.setenv("ENABLE_V5_PRODUCT_ONTOLOGY", "false")
    get_settings.cache_clear()
    assert _call("GET", "/api/v1/products/search").status_code == 404

    monkeypatch.setenv("ENABLE_V5_PRODUCT_ONTOLOGY", "true")
    monkeypatch.setenv("FUND_ADVISORY_CATALOG_PATH", CATALOG_PATH)
    get_settings.cache_clear()
    search = _call(
        "GET",
        "/api/v1/products/search?client_role=long_term_growth&analysis_date=2026-08-10",
    )
    assert search.status_code == 200, search.text
    search_body = search.json()
    assert search_body["product_count"] >= 1
    assert search_body["executable_recommendations_allowed"] is False
    product_id = search_body["products"][0]["id"]

    detail = _call("GET", f"/api/v1/products/{product_id}?analysis_date=2026-08-10")
    assert detail.status_code == 200
    assert detail.json()["snapshot"]["sale_status"] == "channel_verification_required"

    context = _context().model_dump(mode="json")
    eligibility = _call(
        "POST",
        "/api/v1/products/eligibility-check",
        payload={"product_id": product_id, "context": context},
    )
    assert eligibility.status_code == 200, eligibility.text
    assert eligibility.json()["decision"] in {"restricted", "professional_review"}
    assert eligibility.json()["executable"] is False

    ranked = _call(
        "POST",
        "/api/v1/products/rank",
        payload={"context": context, "maximum_candidates": 3},
    )
    assert ranked.status_code == 200, ranked.text
    assert ranked.json()["result"] == "ranked"
    get_settings.cache_clear()
