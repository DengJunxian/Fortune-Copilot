from __future__ import annotations

import asyncio
from decimal import Decimal

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.competition.benchmark import run_competition_benchmark
from app.services.competition.engine import build_competition_demo


def test_shanghai_38_demo_runs_the_complete_cfs_chain() -> None:
    result = build_competition_demo()

    assert result.demo_status == "synthetic_demo"
    assert result.bank_connection is False
    assert result.client.personal_profile.age == 38
    assert result.client.personal_profile.city == "上海"
    assert result.client.family_profile.has_minor_child is True
    assert result.client.income_profile.household_annual_income == Decimal("650000.00")
    assert result.balance_sheet.financial_assets == Decimal("1800000.00")
    assert result.balance_sheet.total_liabilities == Decimal("2100000.00")
    assert result.balance_sheet.net_worth == Decimal("4700000.00")
    assert result.balance_sheet.emergency_fund_months == Decimal("4.000000")
    assert result.balance_sheet.accounting_identity == "6800000.00 - 2100000.00 = 4700000.00"

    assert sum(item.target_amount for item in result.wealth_accounts) == Decimal("1800000.00")
    assert sum(item.share_of_financial_assets for item in result.wealth_accounts) == Decimal(
        "1.000000"
    )
    assert [item.share_of_financial_assets for item in result.wealth_accounts] != [
        Decimal("0.10"),
        Decimal("0.20"),
        Decimal("0.30"),
        Decimal("0.40"),
    ]

    assert sum(item.allocated_monthly_saving for item in result.goals) <= Decimal("4833.34")
    assert result.goals[0].allocated_monthly_saving > 0
    assert result.goals[-1].coordination_status == "resource_constrained"
    assert result.risk_budget.effective_risk_budget == min(
        result.risk_budget.risk_capacity,
        result.risk_budget.risk_tolerance,
    )

    assert {item.method for item in result.quant.methods} == {
        "mean_variance",
        "risk_parity",
        "cvar",
        "black_litterman",
    }
    assert all(sum(item.weights.values()) == Decimal("1.000000") for item in result.quant.methods)
    assert all(item.status == "optimal" for item in result.quant.methods)
    assert result.audit["llm_modified_quant_output"] is False

    assert result.product_pipeline.suitability_violation_rate == Decimal("0.000000")
    assert result.product_pipeline.recommendations
    assert all(item.compliance.passed for item in result.product_pipeline.recommendations)
    assert any(
        "product_risk_above_customer_limit" in item.violations
        for item in result.product_pipeline.rejected_products
    )
    assert len(result.behavior_findings) == 6
    assert all(item.evidence and item.intervention for item in result.behavior_findings)
    assert len(result.citations) >= 5
    assert result.human_escalation.required is True


def test_competition_benchmark_uses_60_profiles_without_faking_llm_or_expert_results() -> None:
    result = run_competition_benchmark()
    assert result["profile_count"] == 60
    assert len(result["segments"]) == 6
    systems = {item["system_code"]: item for item in result["systems"]}
    assert systems["A"]["measured"] is False
    assert systems["A"]["metrics"] is None
    assert all(systems[code]["measured"] for code in "BCD")
    assert systems["D"]["metrics"]["suitability_violation_rate"] == "0.000000"
    assert systems["D"]["metrics"]["financial_planning_correctness"] == "1.000000"
    assert systems["D"]["metrics"]["expert_evaluation"] is None
    assert {item["variant"] for item in result["ablations"]} >= {
        "w/o RAG",
        "w/o Compliance Agent",
        "w/o Behavioral Agent",
        "w/o Goal Planning",
        "w/o Quant Engine",
    }
    assert result["audit"]["general_llm_results_claimed"] is False
    assert result["audit"]["real_bank_results_claimed"] is False
    assert result["audit"]["expert_results_claimed"] is False


async def _request(path: str, role: str = "client") -> tuple[int, dict[str, object]]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            path,
            headers={"X-Actor-ID": "competition-test", "X-Actor-Role": role},
        )
        return response.status_code, response.json()


def test_competition_demo_api_exposes_auditable_demo_boundary() -> None:
    status, payload = asyncio.run(_request("/api/v1/competition/demo"))
    assert status == 200
    assert payload["demo_status"] == "synthetic_demo"
    assert payload["bank_connection"] is False
    assert payload["audit"]["external_network_calls"] == 0
