import asyncio
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.domain.enums import GoalRigidity, GoalType, RiskLevel
from app.main import app
from app.models.assessment import AccountBucketPlan, BehaviorAssessment
from app.models.family import Household
from app.models.finance import FinancialGoal
from app.models.governance import ActionItem, AuditEvent, Recommendation, RuleVersion
from app.schemas.planning import CounterfactualRequest
from app.services.financial.facts import load_household_facts
from app.services.planning.engine import (
    compare_counterfactual,
    empty_counterfactual,
    plan_facts,
    plan_household,
)
from app.services.planning.rules import load_planning_rules
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
EXPECTED_PATH = Path("../data/expected/demo_b_planning_v1.json")
ANALYSIS_DATE = date(2026, 8, 4)


def seed_households() -> dict[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            reset=True,
        )
        households = session.scalars(select(Household)).all()
        return {item.code: item.id for item in households}


def planning(household_id: str) -> Any:
    with SessionLocal() as session:
        return plan_household(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            ANALYSIS_DATE,
        )


async def api_request(method: str, path: str, json_body: dict[str, Any] | None = None) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=json_body)


def call(method: str, path: str, json_body: dict[str, Any] | None = None) -> Response:
    return asyncio.run(api_request(method, path, json_body))


def test_demo_b_matches_versioned_goal_and_account_standard_answer() -> None:
    household_id = seed_households()["DEMO_B"]
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    plan = planning(household_id)

    assert plan.meta.formula_version == expected["formula_version"]
    assert plan.meta.rule_version == expected["rule_version"]
    assert plan.lifecycle.detected_stage.value == expected["lifecycle"]["detected_stage"]
    assert plan.lifecycle.effective_stage.value == expected["lifecycle"]["effective_stage"]
    assert plan.lifecycle.dynamic_safety_months == Decimal(
        expected["lifecycle"]["dynamic_safety_months"]
    )
    for field, value in expected["denominators"].items():
        actual_field = (
            "high_interest_debt_after_counterfactual" if field == "high_interest_debt" else field
        )
        assert getattr(plan.denominators, actual_field) == Decimal(value)

    accounts = {item.bucket.value: item for item in plan.accounts}
    for bucket, values in expected["accounts"].items():
        for field, value in values.items():
            assert getattr(accounts[bucket], field) == Decimal(value), (bucket, field)
        assert {item.denominator_id for item in accounts[bucket].measures} == {
            "total_assets",
            "investable_financial_assets",
            "annual_new_surplus",
        }
    goals = {item.name: item for item in plan.goals}
    for goal_name, values in expected["goals"].items():
        for field, value in values.items():
            assert getattr(goals[goal_name], field) == Decimal(value), (goal_name, field)

    assert len(plan.waterfall_steps) == 7
    assert [item.sequence for item in plan.waterfall_steps] == list(range(1, 8))
    assert len(plan.constraints) == 7
    stable = accounts["stable_goals"]
    assert stable.reference_band is not None
    assert stable.reference_band.denominator_id == "investable_financial_assets"
    assert stable.reference_band.minimum_ratio == Decimal("0.100000")
    assert stable.reference_band.target_ratio == Decimal("0.150000")
    assert stable.reference_band.maximum_ratio == Decimal("0.200000")
    assert stable.reference_band.overall_minimum_ratio == Decimal("0.050000")
    assert stable.reference_band.overall_maximum_ratio == Decimal("0.300000")
    assert stable.reference_band.market_regime == "neutral"
    assert stable.reference_band.binding is False
    assert plan.conflicts
    assert plan.growth_70.eligible is False
    assert "不得套用于家庭总资产" in plan.growth_70.explanation


def test_three_demo_households_produce_distinct_dynamic_results() -> None:
    household_ids = seed_households()
    signatures = {
        code: tuple(account.recommended_amount for account in planning(household_id).accounts)
        for code, household_id in household_ids.items()
    }
    assert set(signatures) == {"DEMO_A", "DEMO_B", "DEMO_C"}
    assert len(set(signatures.values())) == 3


def test_below_formal_threshold_can_use_at_most_ten_percent_learning_allocation() -> None:
    household_id = seed_households()["DEMO_A"]
    plan = planning(household_id)
    learning = plan.investment_learning
    growth = next(
        item for item in plan.accounts if item.bucket.value == "long_term_growth"
    )

    assert learning.applicable is True
    assert learning.eligible is True
    assert learning.cap_ratio == Decimal("0.100000")
    assert learning.denominator_value == Decimal("114250.00")
    assert learning.recommended_ratio == Decimal("0.075000")
    assert learning.recommended_amount == Decimal("8568.75")
    assert learning.recommended_amount <= learning.denominator_value * learning.cap_ratio
    assert growth.recommended_amount == learning.recommended_amount
    assert growth.recommended_range_max == Decimal("11425.00")
    assert plan.growth_70.eligible is False
    assert "学习仓" in plan.growth_70.explanation
    assert "不得套用于家庭总资产" in plan.growth_70.explanation


def test_market_regime_moves_only_eligible_long_term_resources() -> None:
    household_id = seed_households()["DEMO_C"]
    with SessionLocal() as session:
        facts = load_household_facts(session, household_id)
    facts = replace(
        facts,
        goals=(),
        behavior_assessments=tuple(
            replace(item, final_behavior_limit=RiskLevel.MEDIUM)
            for item in facts.behavior_assessments
        ),
    )
    rules = load_planning_rules(PLANNING_RULES_PATH)
    base = plan_facts(
        facts,
        FINANCIAL_RULES_PATH,
        rules,
        ANALYSIS_DATE,
        empty_counterfactual(),
    )
    adjustments = empty_counterfactual().model_copy(
        update={"protection_gap_reduction": base.accounts[1].coverage_gap_amount}
    )

    results: dict[str, tuple[Decimal, Decimal]] = {}
    for regime in ("favorable", "neutral", "defensive"):
        market_environment = rules.market_environment.model_copy(
            update={"active_regime": regime}
        )
        scenario = plan_facts(
            facts,
            FINANCIAL_RULES_PATH,
            rules.model_copy(update={"market_environment": market_environment}),
            ANALYSIS_DATE,
            adjustments,
        )
        accounts = {item.bucket.value: item for item in scenario.accounts}
        results[regime] = (
            accounts["stable_goals"].recommended_amount,
            accounts["long_term_growth"].recommended_amount,
        )

    assert results["favorable"][0] < results["neutral"][0] < results["defensive"][0]
    assert results["favorable"][1] > results["neutral"][1] > results["defensive"][1]


def test_two_year_home_goal_raises_stable_target_account() -> None:
    household_id = seed_households()["DEMO_A"]
    before = planning(household_id)
    with SessionLocal() as session:
        session.add(
            FinancialGoal(
                household_id=household_id,
                name="两年内购房首付",
                goal_type=GoalType.HOME,
                target_amount=Decimal("300000.00"),
                target_date=date(2028, 8, 4),
                rigidity=GoalRigidity.RIGID,
                priority=1,
                can_defer=False,
                minimum_acceptable_amount=Decimal("300000.00"),
                prepared_amount=Decimal("50000.00"),
                annual_cost_growth_rate=Decimal("0.030000"),
                currency="CNY",
                valuation_date=ANALYSIS_DATE,
                data_source="planning-boundary-test",
                is_user_confirmed=True,
            )
        )
        session.commit()
    after = planning(household_id)
    before_stable = next(item for item in before.accounts if item.bucket.value == "stable_goals")
    after_stable = next(item for item in after.accounts if item.bucket.value == "stable_goals")
    assert after_stable.target_amount > before_stable.target_amount
    assert after_stable.source_record_ids


def test_twelve_month_cashflow_is_committed_once_and_never_double_counted() -> None:
    household_id = seed_households()["DEMO_A"]
    with SessionLocal() as session:
        session.add(
            FinancialGoal(
                household_id=household_id,
                name="六个月内确定进修费",
                goal_type=GoalType.EDUCATION,
                target_amount=Decimal("50000.00"),
                target_date=date(2027, 2, 4),
                rigidity=GoalRigidity.RIGID,
                priority=1,
                can_defer=False,
                minimum_acceptable_amount=Decimal("50000.00"),
                prepared_amount=Decimal("0.00"),
                annual_cost_growth_rate=Decimal("0.000000"),
                currency="CNY",
                valuation_date=ANALYSIS_DATE,
                data_source="planning-boundary-test",
                is_user_confirmed=True,
            )
        )
        session.commit()
    plan = planning(household_id)
    commitment = plan.denominators.same_period_cashflow_committed
    short_step = next(
        item for item in plan.waterfall_steps if item.step_code == "twelve_month_commitments"
    )
    allocated_accounts = sum((item.recommended_amount for item in plan.accounts), Decimal("0"))

    assert commitment > Decimal("0.00")
    assert short_step.required_amount == short_step.allocated_amount
    assert short_step.status == "cashflow_covered"
    assert allocated_accounts + commitment == Decimal("151800.00")


def test_safety_gates_block_all_new_resources_from_growth_and_ignore_credit_limit() -> None:
    household_id = seed_households()["DEMO_B"]
    plan = planning(household_id)
    growth = next(item for item in plan.accounts if item.bucket.value == "long_term_growth")
    daily = next(item for item in plan.accounts if item.bucket.value == "daily_liquidity")

    assert daily.current_amount == Decimal("50000.00")
    assert plan.denominators.investable_financial_assets == Decimal("320000.00")
    assert plan.denominators.total_assets == Decimal("2850000.00")
    assert plan.denominators.high_interest_debt_before_plan == Decimal("8000.00")
    assert growth.recommended_amount == Decimal("0.00")
    assert any(
        item.constraint_id == "capital_threshold" and item.limits_growth
        for item in plan.constraints
    )
    assert plan.denominators.net_financial_assets_after_debt == Decimal("-888000.00")
    assert plan.denominators.growth_entry_threshold == Decimal("500000.00")
    assert "未使用额度不计入资产" in plan.accounts[0].product_education[0]


def test_growth_70_appears_only_after_every_prerequisite_passes() -> None:
    household_id = seed_households()["DEMO_C"]
    base = planning(household_id)
    assert base.growth_70.eligible is False

    with SessionLocal() as session:
        behavior = session.scalar(
            select(BehaviorAssessment).where(BehaviorAssessment.household_id == household_id)
        )
        assert behavior is not None
        behavior.final_behavior_limit = RiskLevel.MEDIUM
        session.commit()
        response = compare_counterfactual(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            CounterfactualRequest(
                analysis_date=ANALYSIS_DATE,
                protection_gap_reduction=base.accounts[1].coverage_gap_amount,
            ),
        )

    assert response.scenario.growth_70.eligible is True
    assert response.scenario.growth_70.actual_ratio is not None
    assert response.scenario.growth_70.actual_ratio >= Decimal("0.700000")
    assert "长期可规划资源" in response.scenario.growth_70.denominator_name
    assert all(
        item.status == "pass"
        for item in response.scenario.constraints
        if item.constraint_type == "hard"
    )


def test_client_goal_entry_planning_counterfactual_export_and_persistence_api() -> None:
    household_id = seed_households()["DEMO_B"]
    created_goal = call(
        "POST",
        f"/api/v1/households/{household_id}/goals",
        {
            "name": "家庭进修计划",
            "goal_type": "education",
            "target_amount": "60000.00",
            "target_date": "2028-08-04",
            "rigidity": "flexible",
            "priority": 4,
            "can_defer": True,
            "minimum_acceptable_amount": "40000.00",
            "prepared_amount": "5000.00",
            "annual_cost_growth_rate": "0.030000",
            "currency": "CNY",
            "valuation_date": "2026-08-04",
            "data_source": "client-input-test",
            "is_user_confirmed": True,
        },
    )
    assert created_goal.status_code == 201, created_goal.text

    query = "?analysis_date=2026-08-04"
    response = call("GET", f"/api/v1/households/{household_id}/planning{query}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["calculation_source"] == "deterministic_tools"
    assert any(item["name"] == "家庭进修计划" for item in payload["goals"])
    assert len(payload["accounts"]) == 4

    counterfactual = call(
        "POST",
        f"/api/v1/households/{household_id}/planning/counterfactual",
        {
            "analysis_date": "2026-08-04",
            "monthly_savings_increase": "2000.00",
            "defer_goal_ids": [created_goal.json()["id"]],
            "defer_months": 12,
        },
    )
    assert counterfactual.status_code == 200, counterfactual.text
    assert counterfactual.json()["scenario"]["meta"]["scenario_type"] == "counterfactual"
    assert len(counterfactual.json()["changes"]) == 5

    export = call("GET", f"/api/v1/households/{household_id}/planning/export{query}")
    assert export.status_code == 200
    assert "planning-2026-08-04.json" in export.headers["content-disposition"]

    persisted = call("POST", f"/api/v1/households/{household_id}/planning/runs{query}")
    assert persisted.status_code == 201, persisted.text
    assert persisted.json()["account_count"] == 4
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Recommendation)) == 1
        assert session.scalar(select(func.count()).select_from(AccountBucketPlan)) == 4
        assert session.scalar(select(func.count()).select_from(ActionItem)) >= 1
        assert session.scalar(select(func.count()).select_from(RuleVersion)) == 2
        event_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_type == "recommendation_generated")
        )
        assert event_count == 1
