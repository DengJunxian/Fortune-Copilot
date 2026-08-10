from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.domain.enums import AuditEventType, SimulationStatus
from app.main import app
from app.models.family import Household
from app.models.governance import AuditEvent, ScenarioDefinition, SimulationRun
from app.schemas.twin import PlanAdjustments, TwinRunRequest
from app.services.financial.facts import load_household_facts
from app.services.seed import seed_synthetic_data
from app.services.twin.rules import load_twin_rules
from app.services.twin.simulator import simulate_distribution
from app.services.twin.state import build_twin_model_input

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
EXPECTED_PATH = Path("../data/expected/demo_b_twin_v1.json")


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
        result = seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            portfolio_rules_path=PORTFOLIO_RULES_PATH,
            product_catalog_path=PRODUCT_CATALOG_PATH,
            twin_rules_path=TWIN_RULES_PATH,
        )
        assert result.scenario_count == 22
        return {
            item.code: item.id
            for item in session.scalars(select(Household).where(Household.is_deleted.is_(False)))
        }


def run_to_completion(household_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    started = call("POST", f"/api/v1/households/{household_id}/twin/runs", payload=payload)
    assert started.status_code == 202, started.text
    status = started.json()
    for _ in range(12):
        if status["status"] == "completed":
            break
        advanced = call(
            "POST",
            f"/api/v1/households/{household_id}/twin/runs/{status['run_id']}/advance",
        )
        assert advanced.status_code == 200, advanced.text
        status = advanced.json()
    assert status["status"] == "completed", status
    assert status["progress_percent"] == 100
    return cast(dict[str, Any], status)


def main_demo_request() -> dict[str, Any]:
    return {
        "analysis_date": "2026-08-04",
        "seed": 20260804,
        "path_count": 100,
        "horizon_years": 30,
        "output_interval_months": 12,
        "scenario_codes": ["unemployment_equity_down_30"],
        "plan_adjustments": {
            "primary_retirement_age": 62,
            "additional_monthly_savings": "2000.00",
            "equity_ratio": "0.300000",
            "liquidity_reallocation_amount": "120000.00",
        },
    }


def test_scenario_catalog_covers_all_required_composable_stresses() -> None:
    seed_households()
    response = call("GET", "/api/v1/twin/scenarios")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["scenario_count"] == 22
    assert payload["scenario_version"] == "1.0.0"
    assert payload["source_type"] == "internal_demo"
    assert all(item["enabled"] and item["is_composable"] for item in payload["scenarios"])
    codes = {item["code"] for item in payload["scenarios"]}
    assert {
        "primary_income_interruption_6m",
        "one_income_reduction_30",
        "medical_out_of_pocket",
        "dependent_support_increase",
        "education_overrun",
        "early_retirement",
        "longevity",
        "mortgage_rate_up",
        "investment_property_vacancy_discount",
        "equity_down_20",
        "equity_down_30",
        "equity_down_40",
        "bond_rate_shock",
        "gold_reit_volatility",
        "multi_asset_drawdown",
        "prolonged_low_return",
        "cost_inflation_up",
        "goal_advanced",
        "unemployment_equity_down_30",
        "elder_care_10y",
        "housing_value_down_20",
        "regional_living_cost_hurdle_up",
    } == codes
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(ScenarioDefinition)) == 22


def test_fixed_seed_produces_byte_stable_distribution() -> None:
    household_id = seed_households()["DEMO_B"]
    rules = load_twin_rules(TWIN_RULES_PATH)
    request = TwinRunRequest.model_validate(main_demo_request())
    with SessionLocal() as session:
        facts = load_household_facts(session, household_id)
    model = build_twin_model_input(facts, date(2026, 8, 4))
    first, _ = simulate_distribution(
        model,
        rules,
        request,
        request.scenario_codes,
        PlanAdjustments(),
        "原方案／组合压力",
    )
    second, _ = simulate_distribution(
        model,
        rules,
        request,
        request.scenario_codes,
        PlanAdjustments(),
        "原方案／组合压力",
    )
    assert first.model_dump_json() == second.model_dump_json()
    assert first.validation.primary_income_paid_during_interruption_max == Decimal("0.00")
    assert first.validation.goal_spending_events_applied == 300
    assert first.validation.all_values_finite is True


def test_extreme_parameters_remain_finite_without_nan_or_overflow() -> None:
    household_id = seed_households()["DEMO_B"]
    rules = load_twin_rules(TWIN_RULES_PATH)
    request = TwinRunRequest.model_validate(
        {
            "analysis_date": "2026-08-04",
            "seed": 2147483647,
            "path_count": 100,
            "horizon_years": 60,
            "scenario_codes": ["multi_asset_drawdown", "longevity", "cost_inflation_up"],
            "scenario_overrides": {
                "unemployment_months": 36,
                "income_reduction_ratio": "1.000000",
                "medical_shock_amount": "100000000.00",
                "education_overrun_amount": "100000000.00",
                "property_value_change_ratio": "-0.800000",
                "mortgage_rate_change": "0.200000",
            },
            "assumption_overrides": {
                "inflation_rate": "0.200000",
                "income_growth_rate": "-0.200000",
                "asset_assumptions": {
                    "diversified_equity": {
                        "expected_annual_return": "0.900000",
                        "annual_volatility": "2.000000",
                    }
                },
            },
            "family_events": [
                {
                    "code": "extreme-care",
                    "name": "极端家庭责任",
                    "start_month": 1,
                    "duration_months": 720,
                    "one_time_cost": "100000000.00",
                    "monthly_income_loss": "1000000.00",
                    "monthly_expense_increase": "1000000.00",
                }
            ],
        }
    )
    with SessionLocal() as session:
        facts = load_household_facts(session, household_id)
    model = build_twin_model_input(facts, date(2026, 8, 4))
    result, _ = simulate_distribution(
        model,
        rules,
        request,
        request.scenario_codes,
        PlanAdjustments(),
        "极端参数",
    )
    assert result.validation.all_values_finite is True
    assert result.ending_net_worth_median.is_finite()
    assert result.ending_net_worth_p10.is_finite()
    assert all(point.p10.is_finite() and point.p90.is_finite() for point in result.fan)


def test_main_demo_completes_stress_comparison_export_and_audit() -> None:
    household_id = seed_households()["DEMO_B"]
    status = run_to_completion(household_id, main_demo_request())
    result = status["result"]
    assert result["meta"]["calculation_source"] == "deterministic_simulation_engine"
    assert result["assumptions"]["seed"] == 20260804
    assert result["assumptions"]["scenario_codes"] == ["unemployment_equity_down_30"]
    assert len(result["original_stress"]["fan"]) == 31
    assert (
        result["original_stress"]["validation"]["primary_income_paid_during_interruption_max"]
        == "0.00"
    )
    assert result["comparison"]["stress_not_better_than_baseline"] is True
    assert Decimal(result["original_stress"]["goal_success_probability"]) <= Decimal(
        result["baseline"]["goal_success_probability"]
    )
    assert status["audit_event_id"]
    export = call(
        "GET",
        f"/api/v1/households/{household_id}/twin/runs/{status['run_id']}/export",
    )
    assert export.status_code == 200, export.text
    assert "wealthtwin-demo_b-twin" in export.headers["content-disposition"]
    with SessionLocal() as session:
        run = session.get(SimulationRun, status["run_id"])
        assert run is not None
        assert run.status == SimulationStatus.COMPLETED
        assert run.path_count == 100
        assert run.outputs["result"]["meta"]["run_id"] == run.id
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == run.id,
                AuditEvent.event_type == AuditEventType.SIMULATION_EXECUTED,
            )
        )
        assert audit is not None
        assert audit.evidence["seed"] == 20260804


def test_run_can_be_cancelled_before_next_deterministic_phase() -> None:
    household_id = seed_households()["DEMO_B"]
    started = call(
        "POST",
        f"/api/v1/households/{household_id}/twin/runs",
        payload=main_demo_request(),
    )
    assert started.status_code == 202, started.text
    run_id = started.json()["run_id"]
    cancelled = call(
        "POST",
        f"/api/v1/households/{household_id}/twin/runs/{run_id}/cancel",
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["audit_event_id"]
    export = call("GET", f"/api/v1/households/{household_id}/twin/runs/{run_id}/export")
    assert export.status_code == 409


def test_demo_b_matches_independent_twin_standard_answer() -> None:
    assert EXPECTED_PATH.exists(), "家庭 B 数字孪生标准答案不可缺失"
    household_id = seed_households()["DEMO_B"]
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    status = run_to_completion(household_id, main_demo_request())
    result = status["result"]
    assert result["meta"]["formula_version"] == expected["formula_version"]
    assert result["meta"]["engine_version"] == expected["engine_version"]
    assert result["meta"]["rule_version"] == expected["rule_version"]
    assert result["meta"]["result_version"] == expected["result_version"]
    assert result["meta"]["scenario_version"] == expected["scenario_version"]
    assert result["assumptions"]["seed"] == expected["seed"]
    assert result["assumptions"]["path_count"] == expected["path_count"]
    for field, value in expected["initial_state"].items():
        assert str(result["initial_state"][field]) == str(value)
    for section in ("baseline", "original_stress", "optimized_stress"):
        for field, value in expected[section].items():
            assert str(result[section][field]) == str(value)
    for field, value in expected["comparison"].items():
        assert str(result["comparison"][field]) == str(value)
    assert Decimal(result["optimized_stress"]["forced_sale_probability"]) < Decimal(
        result["original_stress"]["forced_sale_probability"]
    )
