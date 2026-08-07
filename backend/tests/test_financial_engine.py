import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.domain.enums import AssetCategory, LiquidityLevel, PropertyUse, RiskLevel
from app.main import app
from app.models.assessment import FinancialMetric, FinancialSnapshot
from app.models.family import Household
from app.models.finance import Asset, ExpenseItem, IncomeSource, Liability
from app.models.governance import AuditEvent, RuleVersion
from app.services.financial.engine import analyze_household
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
RULES_PATH = "../data/rules/financial_health_v1.json"
EXPECTED_PATH = Path("../data/expected/demo_b_financial_metrics_v1.json")
ANALYSIS_DATE = date(2026, 8, 4)


def seed_main_demo() -> Household:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=RULES_PATH,
            reset=True,
        )
        household = session.scalar(select(Household).where(Household.code == "DEMO_B"))
        assert household is not None
        session.expunge(household)
        return household


def analyze_main_demo() -> Any:
    household = seed_main_demo()
    with SessionLocal() as session:
        return analyze_household(session, household.id, RULES_PATH, ANALYSIS_DATE)


def metric_map(analysis: Any) -> dict[str, Any]:
    return {item.metric_id: item for item in analysis.metrics}


async def api_request(method: str, path: str) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path)


def call(method: str, path: str) -> Response:
    return asyncio.run(api_request(method, path))


def test_main_demo_matches_independent_standard_answer_for_all_metrics() -> None:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    analysis = analyze_main_demo()
    statements = analysis.statements
    totals = expected["statement_totals"]
    assert statements.balance_sheet.total_assets == Decimal(totals["total_assets"])
    assert statements.balance_sheet.total_liabilities == Decimal(totals["total_liabilities"])
    assert statements.balance_sheet.net_worth == Decimal(totals["net_worth"])
    assert statements.cash_flow.annual_income == Decimal(totals["annual_income"])
    assert statements.cash_flow.annual_expenses == Decimal(totals["annual_expenses"])
    assert statements.cash_flow.annual_surplus == Decimal(totals["annual_surplus"])

    actual = metric_map(analysis)
    assert len(actual) == len(expected["metrics"]) == 20
    for metric_id, baseline in expected["metrics"].items():
        metric = actual[metric_id]
        assert metric.result == Decimal(baseline["result"]), metric_id
        assert metric.status == baseline["status"], metric_id
        assert metric.unit == baseline["unit"], metric_id
        assert metric.formula
        assert metric.substitution
        assert metric.actions
        assert metric.data_as_of == ANALYSIS_DATE
        assert metric.reference.source_type in {
            "official_rule",
            "industry_reference",
            "internal_demo",
        }

    assert actual["liquidity_reserve_months"].result == Decimal("4.17")
    assert actual["debt_to_asset_ratio"].result == Decimal("0.423860")
    assert actual["debt_service_burden_ratio"].result == Decimal("0.200000")
    assert actual["savings_ratio"].result == Decimal("0.200000")
    assert actual["property_to_assets_ratio"].result == Decimal("0.842105")
    assert actual["housing_equity_to_net_worth"].result == Decimal("0.730816")
    assert analysis.meta.calculation_source == "deterministic_tools"
    assert analysis.meta.formula_version == expected["formula_version"]
    assert analysis.meta.rule_version == expected["rule_version"]


def test_statements_keep_asset_liability_insurance_and_goal_counting_separate() -> None:
    analysis = analyze_main_demo()
    statements = analysis.statements
    assert statements.balance_sheet.accounting_identity == ("2850000.00 - 1208000.00 = 1642000.00")
    assert statements.insurance.total_annual_premium == Decimal("12000.00")
    assert sum(line.coverage_amount for line in statements.insurance.policies) == Decimal(
        "1800000.00"
    )
    assert statements.balance_sheet.total_assets == Decimal("2850000.00")
    assert statements.goal_funding.total_target_amount == Decimal("2900000.00")
    assert statements.goal_funding.total_prepared_amount == Decimal("130000.00")
    assert statements.liquidity.emergency_liquid_assets == Decimal("50000.00")
    assert statements.liquidity.short_term_liquid_assets == Decimal("320000.00")


def test_analysis_api_exposes_required_views_export_and_persisted_audit_run() -> None:
    household = seed_main_demo()
    query = "?analysis_date=2026-08-04"
    for suffix in ("statements", "metrics", "diagnostics", "financial-analysis"):
        response = call(
            "GET",
            f"/api/v1/households/{household.id}/{suffix}{query}",
        )
        assert response.status_code == 200, (suffix, response.text)
        assert response.json()["meta"]["calculation_source"] == "deterministic_tools"

    metrics_response = call("GET", f"/api/v1/households/{household.id}/metrics{query}")
    by_id = {item["metric_id"]: item for item in metrics_response.json()["metrics"]}
    assert by_id["net_worth"]["result"] == "1642000.00"
    assert by_id["debt_to_asset_ratio"]["result"] == "0.423860"
    dimensions = metrics_response.json()["health_dimensions"]
    assert len(dimensions) == 7
    assert [item["code"] for item in dimensions] == [
        "liquidity",
        "debt",
        "savings",
        "protection",
        "diversification",
        "retirement",
        "goals",
    ]

    export = call(
        "GET",
        f"/api/v1/households/{household.id}/financial-analysis/export{query}",
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/json")
    assert "wealthtwin-demo_b-2026-08-04.json" in export.headers["content-disposition"]
    assert export.json()["statements"]["balance_sheet"]["net_worth"] == "1642000.00"

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(FinancialSnapshot)) == 0
    persisted = call(
        "POST",
        f"/api/v1/households/{household.id}/financial-analysis/runs{query}",
    )
    assert persisted.status_code == 201, persisted.text
    assert persisted.json()["metric_count"] == 20
    assert persisted.json()["calculation_source"] == "deterministic_tools"
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(FinancialSnapshot)) == 1
        assert session.scalar(select(func.count()).select_from(FinancialMetric)) == 20
        assert session.scalar(select(func.count()).select_from(RuleVersion)) == 1
        calculation_events = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_type == "calculation_executed")
        )
        assert calculation_events == 1


def test_zero_income_and_negative_net_worth_return_not_applicable_instead_of_fake_zero() -> None:
    household = seed_main_demo()
    with SessionLocal() as session:
        incomes = list(
            session.scalars(
                select(IncomeSource).where(IncomeSource.household_id == household.id)
            ).all()
        )
        for income in incomes:
            income.amount = Decimal("0.00")
        mortgage = session.scalar(
            select(Liability).where(
                Liability.household_id == household.id,
                Liability.category == "mortgage",
            )
        )
        assert mortgage is not None
        mortgage.outstanding_balance = Decimal("3000000.00")
        session.commit()
        analysis = analyze_household(session, household.id, RULES_PATH, ANALYSIS_DATE)

    metrics = metric_map(analysis)
    assert metrics["savings_ratio"].result is None
    assert metrics["savings_ratio"].status == "not_applicable"
    assert metrics["debt_service_burden_ratio"].result is None
    assert metrics["net_worth"].result == Decimal("-158000.00")
    assert metrics["net_worth"].status == "critical"
    assert metrics["investable_assets_to_net_worth"].result is None
    assert metrics["housing_equity_to_net_worth"].result is None
    assert any(issue.code == "expenses_without_income" for issue in analysis.diagnostics.issues)


def test_no_property_multiple_property_and_floating_income_boundaries() -> None:
    household = seed_main_demo()
    with SessionLocal() as session:
        mortgage = session.scalar(
            select(Liability).where(
                Liability.household_id == household.id,
                Liability.category == "mortgage",
            )
        )
        home = session.scalar(
            select(Asset).where(
                Asset.household_id == household.id,
                Asset.property_use == "primary_residence",
            )
        )
        assert mortgage is not None and home is not None
        session.delete(mortgage)
        session.delete(home)
        session.commit()
        no_property = analyze_household(session, household.id, RULES_PATH, ANALYSIS_DATE)
        no_property_metrics = metric_map(no_property)
        assert no_property_metrics["property_to_assets_ratio"].result == Decimal("0.000000")
        assert no_property_metrics["housing_equity_to_net_worth"].result is None

        for name, cost, value in (
            ("模拟投资性房产一", "400000.00", "500000.00"),
            ("模拟投资性房产二", "250000.00", "300000.00"),
        ):
            session.add(
                Asset(
                    household_id=household.id,
                    name=name,
                    category=AssetCategory.INVESTMENT_PROPERTY,
                    subcategory="边界测试",
                    acquisition_cost=Decimal(cost),
                    market_value=Decimal(value),
                    liquidity_days=240,
                    liquidity_level=LiquidityLevel.ILLIQUID,
                    risk_level=RiskLevel.MEDIUM_HIGH,
                    purpose="出租",
                    pledged=False,
                    ownership="家庭",
                    property_use=PropertyUse.INVESTMENT_PROPERTY,
                    valuation_date=ANALYSIS_DATE,
                    data_source="boundary-test",
                    is_user_confirmed=True,
                )
            )
        for income in session.scalars(
            select(IncomeSource).where(IncomeSource.household_id == household.id)
        ):
            income.stability = Decimal("0.50")
            income.volatility = Decimal("0.40")
        session.commit()
        multiple_property = analyze_household(session, household.id, RULES_PATH, ANALYSIS_DATE)

    metrics = metric_map(multiple_property)
    assert metrics["property_to_assets_ratio"].numerator == Decimal("800000.00")
    assert metrics["liquidity_reserve_months"].result == Decimal("4.17")
    assert metrics["liquidity_reserve_months"].status == "warning"
    assert "波动收入" in metrics["liquidity_reserve_months"].reference.reference_range


def test_missing_data_duplicate_stale_and_decimal_rounding_diagnostics() -> None:
    household = seed_main_demo()
    with SessionLocal() as session:
        expenses = list(
            session.scalars(
                select(ExpenseItem).where(ExpenseItem.household_id == household.id)
            ).all()
        )
        for expense in expenses:
            session.delete(expense)
        liquid = session.scalar(
            select(Asset).where(
                Asset.household_id == household.id,
                Asset.name == "流动资产",
            )
        )
        assert liquid is not None
        liquid.market_value = Decimal("50000.01")
        session.add(
            Asset(
                household_id=household.id,
                name=liquid.name,
                category=liquid.category,
                subcategory=liquid.subcategory,
                acquisition_cost=liquid.acquisition_cost,
                market_value=Decimal("50000.01"),
                liquidity_days=liquid.liquidity_days,
                liquidity_level=liquid.liquidity_level,
                risk_level=liquid.risk_level,
                purpose=liquid.purpose,
                pledged=False,
                ownership="边界测试",
                property_use=liquid.property_use,
                valuation_date=date(2024, 1, 1),
                data_source="boundary-test",
                is_user_confirmed=True,
            )
        )
        session.commit()
        analysis = analyze_household(session, household.id, RULES_PATH, ANALYSIS_DATE)

    issue_codes = {item.code for item in analysis.diagnostics.issues}
    assert "missing_core_data" in issue_codes
    assert "possible_duplicate_assets" in issue_codes
    assert "stale_valuation" in issue_codes
    assert analysis.statements.balance_sheet.total_assets == Decimal("2900000.02")
    assert metric_map(analysis)["liquidity_reserve_months"].result is None


def test_purchasing_power_keeps_minimum_wage_separate_from_cpi_and_return_guarantees() -> None:
    analysis = analyze_main_demo()
    purchasing = analysis.purchasing_power
    assert purchasing.official_cpi.rate == Decimal("0.020000")
    assert purchasing.family_weighted_inflation.rate == Decimal("0.017292")
    assert purchasing.minimum_wage_catch_up.rate == Decimal("0.030000")
    assert purchasing.minimum_wage_is_cpi is False
    assert purchasing.minimum_wage_is_return_guarantee is False
    assert "非实时" in purchasing.official_cpi.source_reference
    assert "不是 CPI 替代" in purchasing.minimum_wage_catch_up.note


def test_seed_file_contains_inputs_not_calculated_answers() -> None:
    payload = json.loads(Path(DATASET_PATH).read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden_key in (
        '"net_worth"',
        '"debt_to_asset_ratio"',
        '"savings_ratio"',
        '"property_to_assets_ratio"',
        '"housing_equity_to_net_worth"',
    ):
        assert forbidden_key not in serialized
