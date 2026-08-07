from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.domain.enums import InsuranceType, MarketScenario, PortfolioCandidateType, RiskLevel
from app.main import app
from app.models.assessment import (
    BehaviorAssessment,
    PortfolioPlan,
    RiskAssessment,
    SuitabilityCheck,
)
from app.models.family import Household
from app.models.finance import Asset, FinancialGoal, InsurancePolicy, Liability
from app.models.governance import AuditEvent, Product, Recommendation
from app.services.financial.facts import load_household_facts
from app.services.portfolio.engine import portfolio_household
from app.services.portfolio.optimizer import current_growth_weights, optimize_candidate
from app.services.portfolio.rules import load_portfolio_rules
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
EXPECTED_PATH = Path("../data/expected/demo_b_portfolio_v1.json")


async def api_request(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=payload)


def call(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, payload=payload))


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


def test_mock_catalog_covers_required_types_and_guarantee_boundaries() -> None:
    seed_households()
    response = call("GET", "/api/v1/portfolio/products")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_type"] == "mock"
    assert payload["product_count"] == 19
    assert payload["professional_hedge_lab_enabled"] is False
    assert all(item["is_simulated"] for item in payload["products"])
    required_types = {
        "cash",
        "time_deposit",
        "savings_treasury_bond",
        "money_market_fund",
        "short_bond_fund",
        "bond_fund",
        "bank_wealth_management",
        "broad_market_index_fund",
        "dividend_value_index_fund",
        "multi_asset_fund",
        "public_reit",
        "gold_fund",
        "retirement_savings",
        "personal_pension_target_date_fund",
        "commercial_annuity_insurance",
    }
    by_type = {item["product_type"]: item for item in payload["products"]}
    assert required_types <= set(by_type)
    for product_type in {
        "bank_wealth_management",
        "short_bond_fund",
        "bond_fund",
        "collective_fund_trust",
        "participating_life_insurance",
    }:
        assert by_type[product_type]["principal_guaranteed"] is False
    futures = by_type["index_futures_education_sandbox"]
    assert futures["enabled"] is False
    assert futures["education_only"] is True
    assert futures["professional_only"] is True


def test_demo_b_matches_independent_portfolio_standard_answer() -> None:
    household_id = seed_households()["DEMO_B"]
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        result = portfolio_household(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            PORTFOLIO_RULES_PATH,
            PRODUCT_CATALOG_PATH,
            analysis_date=date(2026, 8, 4),
        )
    assert result.meta.formula_version == expected["formula_version"]
    assert result.meta.rule_version == expected["rule_version"]
    assert result.meta.optimizer_version == expected["optimizer_version"]
    assert result.meta.catalog_version == expected["catalog_version"]
    for field, value in expected["context"].items():
        actual = getattr(result.context, field)
        assert str(actual) == str(value)
    assert result.family_safety_gate.status.value == expected["family_status"]
    assert result.customer_suitability_gate.effective_risk_limit.value == expected["customer_limit"]
    assert result.catalog.product_count == expected["product_count"]
    for candidate in result.candidates:
        standard = expected["candidates"][candidate.candidate_type.value]
        assert candidate.decision.value == standard["decision"]
        assert {
            item.asset_class: str(item.ratio) for item in candidate.strategic_allocations
        } == standard["weights"]
        for field in (
            "expected_nominal_return",
            "expected_real_return",
            "goal_success_probability",
            "extreme_loss_ratio",
            "max_drawdown_estimate",
            "liquidity_score",
            "annual_fee_rate",
        ):
            assert str(getattr(candidate, field)) == standard[field]
        assert candidate.optimization.method == standard["method"]
        assert candidate.gates[2].status.value == standard["product_gate"]


def test_three_households_receive_distinct_contexts_with_capital_gate() -> None:
    household_ids = seed_households()
    results = {}
    with SessionLocal() as session:
        for code, household_id in household_ids.items():
            result = portfolio_household(
                session,
                household_id,
                FINANCIAL_RULES_PATH,
                PLANNING_RULES_PATH,
                PORTFOLIO_RULES_PATH,
                PRODUCT_CATALOG_PATH,
                analysis_date=date(2026, 8, 4),
            )
            results[code] = result
            assert [item.candidate_type for item in result.candidates] == list(
                PortfolioCandidateType
            )
            for candidate in result.candidates:
                assert sum(
                    (item.ratio for item in candidate.strategic_allocations),
                    Decimal("0"),
                ) == Decimal("1.000000")
                assert candidate.optimization.method in {
                    "deterministic_grid_search",
                    "rule_based_fallback",
                }
                assert len(candidate.gates) == 3
                assert all(mapping.is_mock for mapping in candidate.product_mappings)
    assert results["DEMO_B"].context.eligible_long_term_amount == Decimal("0.00")
    assert all(item.decision.value == "education_only" for item in results["DEMO_B"].candidates)
    context_signatures = {
        code: (
            result.context.eligible_long_term_amount,
            result.context.long_term_goal_present_value_gap,
            result.context.simulation_horizon_months,
            result.context.annual_new_surplus,
        )
        for code, result in results.items()
    }
    assert len(set(context_signatures.values())) == 3
    assert results["DEMO_A"].context.eligible_long_term_amount == Decimal("8568.75")
    assert all(item.decision.value == "education_only" for item in results["DEMO_A"].candidates)
    assert results["DEMO_C"].context.eligible_long_term_amount > Decimal("0.00")


def test_solver_failure_uses_versioned_rule_fallback() -> None:
    household_id = seed_households()["DEMO_A"]
    with SessionLocal() as session:
        response = portfolio_household(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            PORTFOLIO_RULES_PATH,
            PRODUCT_CATALOG_PATH,
            analysis_date=date(2026, 8, 4),
        )
        rules = load_portfolio_rules(PORTFOLIO_RULES_PATH)
        facts = load_household_facts(session, household_id)
        fallback = optimize_candidate(
            PortfolioCandidateType.BALANCED,
            Decimal("100000.00"),
            Decimal("150000.00"),
            120,
            current_growth_weights(facts, rules),
            Decimal("0.025000"),
            Decimal("0.100000"),
            date(2026, 8, 4),
            MarketScenario.NEUTRAL,
            response.family_safety_gate,
            response.customer_suitability_gate,
            rules,
            force_solver_failure=True,
        )
    assert fallback.diagnostics.method == "rule_based_fallback"
    assert fallback.diagnostics.status == "fallback"
    assert fallback.diagnostics.fallback_reason == "测试强制触发求解失败。"
    assert sum(fallback.weights.values(), Decimal("0")) == Decimal("1.000000")
    assert fallback.weights["diversified_equity"] + fallback.weights["real_assets"] <= Decimal(
        "0.100000"
    )


def test_safe_household_can_pass_gates_without_bypassing_product_suitability() -> None:
    household_id = seed_households()["DEMO_B"]
    with SessionLocal() as session:
        cash_asset = session.scalar(
            select(Asset).where(
                Asset.household_id == household_id,
                Asset.name == "流动资产",
            )
        )
        assert cash_asset is not None
        cash_asset.market_value = Decimal("800000.00")
        for liability in session.scalars(
            select(Liability).where(Liability.household_id == household_id)
        ):
            liability.outstanding_balance = Decimal("0.00")
            liability.monthly_payment = Decimal("0.00")
            liability.is_high_interest = False
        policies = list(
            session.scalars(
                select(InsurancePolicy).where(InsurancePolicy.household_id == household_id)
            )
        )
        for policy in policies:
            policy.coverage_amount = Decimal("10000000.00")
        session.add(
            InsurancePolicy(
                household_id=household_id,
                insured_member_id=policies[0].insured_member_id,
                name="测试意外保障",
                policy_type=InsuranceType.ACCIDENT,
                coverage_amount=Decimal("10000000.00"),
                annual_premium=Decimal("0.00"),
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                deductible=Decimal("0.00"),
                waiting_period_days=0,
                guaranteed_benefit=Decimal("0.00"),
                non_guaranteed_benefit=Decimal("0.00"),
                cash_value=Decimal("0.00"),
                valuation_date=date(2026, 8, 4),
                data_source="test",
                is_user_confirmed=True,
            )
        )
        for goal in session.scalars(
            select(FinancialGoal).where(FinancialGoal.household_id == household_id)
        ):
            goal.prepared_amount = Decimal("10000000.00")
        session.commit()
        result = portfolio_household(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            PORTFOLIO_RULES_PATH,
            PRODUCT_CATALOG_PATH,
            analysis_date=date(2026, 8, 4),
            market_scenario=MarketScenario.RISK_ON,
        )
    assert result.family_safety_gate.status.value == "pass"
    assert result.context.eligible_long_term_amount > 0
    conservative, balanced, growth = result.candidates
    assert conservative.decision.value == "allow"
    assert balanced.decision.value == "allow"
    assert growth.decision.value == "downgrade"
    assert all(item.decision.value == "allow" for item in conservative.product_mappings)
    assert all(item.decision.value == "allow" for item in balanced.product_mappings)
    for candidate in (conservative, balanced):
        strategic = {item.asset_class: item.ratio for item in candidate.strategic_allocations}
        tactical = {item.asset_class: item.ratio for item in candidate.tactical_allocations}
        assert max(abs(tactical[key] - strategic[key]) for key in strategic) <= Decimal("0.050000")
    balanced_strategic = {item.asset_class: item.ratio for item in balanced.strategic_allocations}
    balanced_tactical = {item.asset_class: item.ratio for item in balanced.tactical_allocations}
    assert balanced_tactical["diversified_equity"] - balanced_strategic[
        "diversified_equity"
    ] == Decimal("0.050000")
    assert all(
        item.product_type not in {"stock", "index_futures_education_sandbox"}
        for candidate in result.candidates
        for item in candidate.product_mappings
    )


def test_portfolio_api_exports_and_persists_three_candidates_with_nine_gates() -> None:
    household_id = seed_households()["DEMO_A"]
    query = "?analysis_date=2026-08-04&market_scenario=risk_on"
    response = call("GET", f"/api/v1/households/{household_id}/portfolio{query}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["calculation_source"] == "deterministic_tools"
    assert payload["meta"]["market_scenario"] == "risk_on"
    assert len(payload["candidates"]) == 3
    assert all(
        item["simulation_method"] == "deterministic_weighted_scenarios_not_monte_carlo"
        for item in payload["candidates"]
    )
    for candidate in payload["candidates"]:
        assert [item["ratio"] for item in candidate["strategic_allocations"]] == [
            item["ratio"] for item in candidate["tactical_allocations"]
        ]

    export = call("GET", f"/api/v1/households/{household_id}/portfolio/export{query}")
    assert export.status_code == 200
    assert "portfolio-2026-08-04.json" in export.headers["content-disposition"]

    persisted = call("POST", f"/api/v1/households/{household_id}/portfolio/runs{query}")
    assert persisted.status_code == 201, persisted.text
    assert persisted.json()["candidate_count"] == 3
    assert persisted.json()["suitability_check_count"] == 9
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(PortfolioPlan)) == 3
        assert session.scalar(select(func.count()).select_from(SuitabilityCheck)) == 9
        assert session.scalar(select(func.count()).select_from(Recommendation)) == 1


def test_five_obvious_mismatches_are_rejected_and_audited() -> None:
    household_ids = seed_households()
    with SessionLocal() as session:
        a_risk = session.scalar(
            select(RiskAssessment).where(RiskAssessment.household_id == household_ids["DEMO_A"])
        )
        a_behavior = session.scalar(
            select(BehaviorAssessment).where(
                BehaviorAssessment.household_id == household_ids["DEMO_A"]
            )
        )
        assert a_risk is not None and a_behavior is not None
        a_risk.capacity_score = Decimal("0.10")
        a_risk.willingness_score = Decimal("0.10")
        a_risk.knowledge_score = Decimal("0.10")
        a_risk.behavior_score = Decimal("0.10")
        a_risk.final_risk_limit = RiskLevel.LOW
        a_behavior.final_behavior_limit = RiskLevel.LOW
        session.commit()

    cases = [
        (
            household_ids["DEMO_A"],
            {
                "investment_amount": "100000.00",
                "target_horizon_months": 120,
                "requested_high_risk_ratio": "0.800000",
                "leverage_ratio": "0.500000",
                "concentration_ratio": "0.500000",
                "requested_product_codes": ["MOCK-FUTURES-LAB-001"],
                "purpose": "professional_hedge",
            },
        ),
        (
            household_ids["DEMO_B"],
            {
                "investment_amount": "100000.00",
                "target_horizon_months": 6,
                "requested_high_risk_ratio": "1.000000",
                "concentration_ratio": "1.000000",
                "requested_product_codes": ["MOCK-INDEX-BROAD-001"],
                "purpose": "tuition",
            },
        ),
        (
            household_ids["DEMO_C"],
            {
                "investment_amount": "1000000.00",
                "target_horizon_months": 120,
                "requested_high_risk_ratio": "0.800000",
                "concentration_ratio": "1.000000",
                "requested_product_codes": ["MOCK-TRUST-001"],
                "purpose": "retirement",
            },
        ),
        (
            household_ids["DEMO_B"],
            {
                "investment_amount": "50000.00",
                "target_horizon_months": 120,
                "requested_high_risk_ratio": "0.500000",
                "concentration_ratio": "0.200000",
                "requested_product_codes": ["MOCK-INDEX-BROAD-001"],
                "purpose": "long_term_growth",
            },
        ),
        (
            household_ids["DEMO_B"],
            {
                "investment_amount": "50000.00",
                "target_horizon_months": 120,
                "requested_high_risk_ratio": "0.300000",
                "leverage_ratio": "0.300000",
                "concentration_ratio": "0.200000",
                "requested_product_codes": ["MOCK-FUND-MONEY-001"],
                "purpose": "long_term_growth",
            },
        ),
    ]
    results = [
        call(
            "POST",
            f"/api/v1/households/{household_id}/portfolio/suitability-check",
            payload=payload,
        )
        for household_id, payload in cases
    ]
    assert all(response.status_code == 200 for response in results)
    assert all(response.json()["decision"] == "reject" for response in results)
    assert all(response.json()["failed_check_codes"] for response in results)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 8
        assert session.scalar(select(func.count()).select_from(Product)) == 19
