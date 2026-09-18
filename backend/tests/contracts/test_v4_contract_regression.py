from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.family import Household
from app.schemas.formal_report import FORMAL_CHAPTER_TITLES
from app.services.financial.engine import analyze_household
from app.services.financial.facts import load_household_facts
from app.services.planning.engine import plan_household
from app.services.portfolio.engine import portfolio_household
from app.services.reporting.composer import REPORT_COMPOSER_VERSION
from app.services.reporting.service import REPORT_ENGINE_VERSION
from app.services.seed import seed_synthetic_data
from app.services.twin.state import build_twin_model_input

EXPECTED_PATH = Path(__file__).with_name("v4_demo_contracts_v1.json")
DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
BEHAVIOR_RULES_PATH = "../data/rules/behavior_finance_v1.json"
KNOWLEDGE_PATH = "../data/knowledge/controlled_knowledge_v1.json"


def _actual_contract(session: Any, household: Household, analysis_date: date) -> dict[str, Any]:
    analysis = analyze_household(session, household.id, FINANCIAL_RULES_PATH, analysis_date)
    planning = plan_household(
        session,
        household.id,
        FINANCIAL_RULES_PATH,
        PLANNING_RULES_PATH,
        analysis_date,
        methodology_rules_path=METHODOLOGY_RULES_PATH,
        public_data_snapshot_path=PUBLIC_DATA_PATH,
    )
    portfolio = portfolio_household(
        session,
        household.id,
        FINANCIAL_RULES_PATH,
        PLANNING_RULES_PATH,
        PORTFOLIO_RULES_PATH,
        PRODUCT_CATALOG_PATH,
        analysis_date,
        methodology_rules_path=METHODOLOGY_RULES_PATH,
    )
    twin = build_twin_model_input(load_household_facts(session, household.id), analysis_date)
    return {
        "financial_analysis": {
            "total_assets": str(analysis.statements.balance_sheet.total_assets),
            "total_liabilities": str(analysis.statements.balance_sheet.total_liabilities),
            "net_worth": str(analysis.statements.balance_sheet.net_worth),
            "annual_income": str(analysis.statements.cash_flow.annual_income),
            "annual_expenses": str(analysis.statements.cash_flow.annual_expenses),
            "annual_surplus": str(analysis.statements.cash_flow.annual_surplus),
            "health_score": str(analysis.health_assessment.overall_score),
            "health_status": analysis.health_assessment.status,
        },
        "planning": {
            "plannable_financial_net_worth": str(
                planning.denominators.plannable_financial_net_worth
            ),
            "investable_financial_assets": str(
                planning.denominators.investable_financial_assets
            ),
            "residual_long_term_plannable_capital": str(
                planning.denominators.residual_long_term_plannable_capital
            ),
            "accounts": {
                item.bucket.value: str(item.recommended_amount) for item in planning.accounts
            },
            "growth_eligible": planning.growth_70.eligible,
            "formal_growth_amount": str(planning.growth_70.formal_growth_amount),
            "learning_amount": str(planning.investment_learning.recommended_amount),
        },
        "portfolio": {
            "eligible_long_term_amount": str(portfolio.context.eligible_long_term_amount),
            "family_gate": portfolio.family_safety_gate.status.value,
            "effective_risk_limit": (
                portfolio.customer_suitability_gate.effective_risk_limit.value
            ),
            "candidate_decisions": {
                item.candidate_type.value: item.decision.value for item in portfolio.candidates
            },
        },
        "twin_configuration": {
            "asset_buckets": {key: str(value) for key, value in twin.asset_buckets.items()},
            "monthly_expenses": str(twin.monthly_expenses),
            "monthly_essential_expenses": str(twin.monthly_essential_expenses),
            "income_count": len(twin.incomes),
            "debt_count": len(twin.debts),
            "goal_count": len(twin.goals),
        },
    }


def test_v4_demo_contracts_remain_stable_with_all_v5_flags_off() -> None:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    analysis_date = date.fromisoformat(expected["analysis_date"])
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            portfolio_rules_path=PORTFOLIO_RULES_PATH,
            product_catalog_path=PRODUCT_CATALOG_PATH,
            twin_rules_path=TWIN_RULES_PATH,
            behavior_rules_path=BEHAVIOR_RULES_PATH,
            knowledge_base_path=KNOWLEDGE_PATH,
        )
        households = session.scalars(select(Household).order_by(Household.code)).all()
        actual = {
            household.code: _actual_contract(session, household, analysis_date)
            for household in households
        }

        versions = expected["shared_versions"]
        demo_a = households[0]
        financial = analyze_household(
            session, demo_a.id, FINANCIAL_RULES_PATH, analysis_date
        )
        planning = plan_household(
            session,
            demo_a.id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            analysis_date,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            public_data_snapshot_path=PUBLIC_DATA_PATH,
        )
        portfolio = portfolio_household(
            session,
            demo_a.id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            PORTFOLIO_RULES_PATH,
            PRODUCT_CATALOG_PATH,
            analysis_date,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
        )

    assert actual == expected["households"]
    assert financial.meta.formula_version == versions["financial_formula"]
    assert financial.meta.rule_version == versions["financial_rule"]
    assert planning.meta.formula_version == versions["planning_formula"]
    assert planning.meta.rule_version == versions["planning_rule"]
    assert planning.meta.methodology_version == versions["methodology"]
    assert portfolio.meta.formula_version == versions["portfolio_formula"]
    assert portfolio.meta.rule_version == versions["portfolio_rule"]
    assert portfolio.meta.optimizer_version == versions["optimizer"]
    assert portfolio.meta.catalog_version == versions["catalog"]

    report = expected["formal_report_metadata"]
    assert tuple(report["chapter_titles"]) == FORMAL_CHAPTER_TITLES
    assert report["chapter_count"] == len(FORMAL_CHAPTER_TITLES) == 8
    assert report["service_version"] == REPORT_ENGINE_VERSION
    assert report["composer_version"] == REPORT_COMPOSER_VERSION
