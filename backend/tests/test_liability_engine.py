from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    CashFlowFrequency,
    ExpenseCategory,
    ExpenseNecessity,
    GoalRigidity,
    LiabilityCategory,
    LiabilityStreamType,
    RateType,
    RiskLevel,
)
from app.domain.financial import LiabilityFact
from app.main import app
from app.models.family import Household
from app.models.finance import FinancialGoal
from app.models.governance import AuditEvent
from app.models.liability import LiabilityStream, LiabilityStreamCashflow
from app.schemas.liability import LiabilityStreamDraft
from app.services.eligible_capital.engine import calculate_eligible_capital
from app.services.financial.facts import load_household_facts
from app.services.financial.rules import load_financial_rules
from app.services.liability_engine.adapters import adapt_goals_and_responsibilities
from app.services.liability_engine.engine import materialize_liability_streams
from app.services.liability_engine.rules import load_liability_rules
from app.services.liability_engine.schedule import build_schedule
from app.services.methodology.rules import load_methodology_rules
from app.services.planning.engine import empty_counterfactual, plan_facts
from app.services.planning.rules import load_planning_rules
from app.services.public_data.rules import load_public_data_snapshot
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"
LIABILITY_RULES_PATH = "../data/rules/liability_engine_v1.json"
ANALYSIS_DATE = date(2026, 8, 10)


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"liability-{role}",
        role=role,  # type: ignore[arg-type]
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _seed() -> dict[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            reset=True,
        )
        return {item.code: item.id for item in session.scalars(select(Household)).all()}


def _stream(
    *,
    name: str,
    stream_type: LiabilityStreamType,
    start_date: date,
    end_date: date | None,
    frequency: CashFlowFrequency,
    base_amount: Decimal,
    minimum_amount: Decimal | None = None,
    growth: Decimal = Decimal("0.000000"),
    rigidity: GoalRigidity = GoalRigidity.RIGID,
    deferrable: bool = False,
    funding_sources: list[dict[str, Any]] | None = None,
) -> LiabilityStreamDraft:
    return LiabilityStreamDraft(
        name=name,
        stream_type=stream_type,
        currency="CNY",
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        base_amount=base_amount,
        minimum_amount=minimum_amount or base_amount,
        inflation_index_code=f"GCI_{stream_type.value.upper()}",
        annual_growth_assumption=growth,
        rigidity=rigidity,
        deferrable=deferrable,
        funding_sources=funding_sources or [],
        fallback_action="人工复核",
        stream_version=f"test-{name}",
        data_source="test",
        is_user_confirmed=True,
    )


def test_education_schedule_is_four_annual_installments_not_terminal_lump_sum() -> None:
    stream = _stream(
        name="2035 至 2038 教育费用",
        stream_type=LiabilityStreamType.EDUCATION,
        start_date=date(2035, 9, 1),
        end_date=date(2038, 9, 1),
        frequency=CashFlowFrequency.ANNUAL,
        base_amount=Decimal("250000.00"),
        funding_sources=[
            {
                "source_type": "prepared_goal_capital",
                "amount": "0.00",
                "target_total": "1000000.00",
                "minimum_total": "1000000.00",
            }
        ],
    )
    cashflows = build_schedule(stream, "test-formula")

    assert [item.due_date.year for item in cashflows] == [2035, 2036, 2037, 2038]
    assert [item.target_amount for item in cashflows] == [Decimal("250000.00")] * 4
    assert sum((item.target_amount for item in cashflows), Decimal("0.00")) == Decimal("1000000.00")


def test_goal_adapter_materialization_is_idempotent_audited_and_recalculates() -> None:
    household_id = _seed()["DEMO_A"]
    rules = load_liability_rules(LIABILITY_RULES_PATH)
    with SessionLocal() as session:
        facts = load_household_facts(session, household_id)
        drafts = adapt_goals_and_responsibilities(facts, rules, ANALYSIS_DATE)
        education = next(
            item for item in drafts if item.stream_type == LiabilityStreamType.EDUCATION
        )
        assert education.frequency == CashFlowFrequency.ANNUAL
        assert education.start_date.year == education.end_date.year - 3  # type: ignore[union-attr]

        first = materialize_liability_streams(
            session,
            household_id,
            _actor(),
            LIABILITY_RULES_PATH,
            ANALYSIS_DATE,
        )
        first_entry = next(
            item for item in first.entries if item.stream.source_goal_id == education.source_goal_id
        )
        assert len(first_entry.cashflows) == 4
        assert first_entry.target_total == Decimal("150000.00")

        repeated = materialize_liability_streams(
            session,
            household_id,
            _actor(),
            LIABILITY_RULES_PATH,
            ANALYSIS_DATE,
        )
        repeated_entry = next(
            item
            for item in repeated.entries
            if item.stream.source_goal_id == education.source_goal_id
        )
        assert repeated_entry.stream.id == first_entry.stream.id
        assert [item.id for item in repeated_entry.cashflows] == [
            item.id for item in first_entry.cashflows
        ]

        goal = session.get(FinancialGoal, education.source_goal_id)
        assert goal is not None
        goal.target_amount = Decimal("200000.00")
        goal.version += 1
        session.commit()
        updated = materialize_liability_streams(
            session,
            household_id,
            _actor(),
            LIABILITY_RULES_PATH,
            ANALYSIS_DATE,
        )
        updated_entry = next(
            item
            for item in updated.entries
            if item.stream.source_goal_id == education.source_goal_id
        )
        assert updated_entry.stream.id == first_entry.stream.id
        assert updated_entry.stream.version > first_entry.stream.version
        assert updated_entry.target_total == Decimal("200000.00")
        assert session.scalar(select(func.count()).select_from(AuditEvent)) > 0
        assert session.scalar(select(func.count()).select_from(LiabilityStream)) == len(facts.goals)
        assert session.scalar(select(func.count()).select_from(LiabilityStreamCashflow)) >= len(
            facts.goals
        )


def _case_facts() -> Any:
    household_id = _seed()["DEMO_A"]
    with SessionLocal() as session:
        facts = load_household_facts(session, household_id)
    asset = replace(
        facts.assets[0],
        category=AssetCategory.CASH,
        account_wrapper=AccountWrapper.ORDINARY,
        market_value=Decimal("300000.00"),
        acquisition_cost=Decimal("300000.00"),
        pledged=False,
        lock_up=False,
        withdrawable_date=None,
    )
    income = replace(
        facts.incomes[0],
        amount=Decimal("50000.00"),
        frequency=CashFlowFrequency.MONTHLY,
        is_sustainable=True,
    )
    expense = replace(
        facts.expenses[0],
        amount=Decimal("1000.00"),
        frequency=CashFlowFrequency.MONTHLY,
        necessity=ExpenseNecessity.ESSENTIAL,
        category=ExpenseCategory.BASIC_LIVING,
    )
    risk = replace(
        facts.risk_assessments[-1],
        capacity_score=Decimal("0.800000"),
        final_risk_limit=RiskLevel.MEDIUM,
    )
    return replace(
        facts,
        assets=(asset,),
        incomes=(income,),
        expenses=(expense,),
        liabilities=(),
        insurance_policies=(),
        social_security_accounts=(),
        goals=(),
        responsibilities=(),
        risk_assessments=(risk,),
    )


def _calculate(facts: Any, streams: tuple[LiabilityStreamDraft, ...]) -> Any:
    return calculate_eligible_capital(
        facts,
        streams,
        load_financial_rules(FINANCIAL_RULES_PATH),
        load_methodology_rules(METHODOLOGY_RULES_PATH),
        load_liability_rules(LIABILITY_RULES_PATH),
        ANALYSIS_DATE,
        load_public_data_snapshot(PUBLIC_DATA_PATH),
    )


def test_eltc_acceptance_cases_and_threshold_deprecation() -> None:
    case_a = _case_facts()
    result_a = _calculate(case_a, ())
    calculation_a = result_a.calculation
    assert calculation_a.dispatchable_financial_resources == Decimal("300000.00")
    assert calculation_a.eligible_long_term_capital > Decimal("0.00")
    assert calculation_a.formally_eligible is True
    assert calculation_a.growth_entry_threshold.amount > Decimal("300000.00")
    assert calculation_a.growth_entry_threshold.deprecated_as_hard_gate is True
    assert calculation_a.growth_entry_threshold.determines_eligibility is False

    mortgage = LiabilityFact(
        id="mortgage-case-b",
        name="大额住房按揭",
        category=LiabilityCategory.MORTGAGE,
        outstanding_balance=Decimal("700000.00"),
        annual_interest_rate=Decimal("0.040000"),
        monthly_payment=Decimal("15000.00"),
        maturity_date=date(2031, 8, 10),
        rate_type=RateType.FIXED,
        prepayment_cost=Decimal("0.00"),
        linked_asset_id=None,
        is_high_interest=False,
        valuation_date=ANALYSIS_DATE,
        version=1,
    )
    case_b = replace(
        case_a,
        assets=(
            replace(
                case_a.assets[0],
                market_value=Decimal("1000000.00"),
                acquisition_cost=Decimal("1000000.00"),
            ),
        ),
        liabilities=(mortgage,),
    )
    streams_b = (
        _stream(
            name="子女教育",
            stream_type=LiabilityStreamType.EDUCATION,
            start_date=date(2027, 9, 1),
            end_date=date(2028, 9, 1),
            frequency=CashFlowFrequency.ANNUAL,
            base_amount=Decimal("300000.00"),
        ),
        _stream(
            name="老人医疗",
            stream_type=LiabilityStreamType.MEDICAL,
            start_date=date(2029, 3, 1),
            end_date=date(2029, 3, 1),
            frequency=CashFlowFrequency.ONE_TIME,
            base_amount=Decimal("300000.00"),
        ),
    )
    calculation_b = _calculate(case_b, streams_b).calculation
    assert calculation_b.dispatchable_financial_resources == Decimal("1000000.00")
    assert calculation_b.eligible_long_term_capital == Decimal("0.00")
    assert calculation_b.formally_eligible is False
    assert any(item.unfunded > 0 for item in calculation_b.bridge)

    planning = plan_facts(
        case_a,
        FINANCIAL_RULES_PATH,
        load_planning_rules(PLANNING_RULES_PATH),
        ANALYSIS_DATE,
        empty_counterfactual(),
        load_methodology_rules(METHODOLOGY_RULES_PATH),
        load_public_data_snapshot(PUBLIC_DATA_PATH),
        calculation_a,
    )
    capital_gate = next(
        item for item in planning.constraints if item.constraint_id == "capital_threshold"
    )
    assert capital_gate.status == "pass"
    assert capital_gate.limits_growth is False
    assert "仅作沟通参考" in capital_gate.observed_value
    assert planning.investment_learning.applicable is False
    assert "最低工资" not in planning.growth_benchmark.components
    assert (
        calculation_a.purchasing_power.income_adequacy.minimum_wage_scope == "income_adequacy_only"
    )
    assert calculation_a.purchasing_power.minimum_wage_used_as_return_hurdle is False


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
                "X-Actor-ID": f"liability-{role}",
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


def test_liability_api_is_flagged_rbac_confirmed_and_returns_v2(monkeypatch: Any) -> None:
    household_id = _seed()["DEMO_A"]
    calendar_path = f"/api/v1/households/{household_id}/liability-calendar"
    eligible_path = f"/api/v1/households/{household_id}/eligible-capital"

    monkeypatch.setenv("ENABLE_V5_LIABILITY_ENGINE", "false")
    get_settings.cache_clear()
    disabled = _call("GET", calendar_path)
    assert disabled.status_code == 404
    assert disabled.json()["error"]["code"] == "feature_not_enabled"

    monkeypatch.setenv("ENABLE_V5_LIABILITY_ENGINE", "true")
    monkeypatch.setenv("LIABILITY_RULES_PATH", LIABILITY_RULES_PATH)
    monkeypatch.setenv("FINANCIAL_RULES_PATH", FINANCIAL_RULES_PATH)
    monkeypatch.setenv("METHODOLOGY_RULES_PATH", METHODOLOGY_RULES_PATH)
    monkeypatch.setenv("PUBLIC_DATA_SNAPSHOT_PATH", PUBLIC_DATA_PATH)
    get_settings.cache_clear()
    calendar = _call("GET", f"{calendar_path}?analysis_date={ANALYSIS_DATE}")
    assert calendar.status_code == 200, calendar.text
    assert calendar.json()["summary"]["stream_count"] >= 2

    eligible = _call("GET", f"{eligible_path}?analysis_date={ANALYSIS_DATE}")
    assert eligible.status_code == 200, eligible.text
    payload = eligible.json()["calculation"]
    assert [item["code"] for item in payload["bridge"]] == [
        "operating_liquidity",
        "emergency_reserve",
        "high_interest_debt_repair",
        "protection_funding",
        "short_term_hard_liabilities",
        "committed_goal_capital",
        "locked_institutional_assets",
    ]
    assert payload["growth_entry_threshold"]["determines_eligibility"] is False
    assert payload["purchasing_power"]["minimum_wage_used_as_return_hurdle"] is False

    create_payload = {
        "currency": "CNY",
        "valuation_date": str(ANALYSIS_DATE),
        "data_source": "client_confirmed",
        "is_user_confirmed": True,
        "name": "客户确认的护理责任",
        "stream_type": "medical",
        "start_date": "2028-08-10",
        "end_date": "2028-08-10",
        "frequency": "one_time",
        "base_amount": "50000.00",
        "minimum_amount": "40000.00",
        "inflation_index_code": "GCI_MEDICAL",
        "annual_growth_assumption": "0.030000",
        "rigidity": "important",
        "deferrable": False,
        "funding_sources": [],
        "fallback_action": "由客户经理复核护理安排",
    }
    denied = _call(
        "POST",
        f"/api/v1/households/{household_id}/liability-streams",
        role="compliance",
        payload=create_payload,
    )
    assert denied.status_code == 403
    missing_confirmation = _call(
        "POST",
        f"/api/v1/households/{household_id}/liability-streams",
        role="client",
        payload=create_payload,
    )
    assert missing_confirmation.status_code == 409
    created = _call(
        "POST",
        f"/api/v1/households/{household_id}/liability-streams",
        role="client",
        payload=create_payload,
        headers={"X-Confirm-Action": "create_liability_stream"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["entry"]["stream"]["source_goal_id"] is None
    get_settings.cache_clear()
