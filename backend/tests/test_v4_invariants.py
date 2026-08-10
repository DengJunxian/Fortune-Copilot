from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    AssetPurposeDimension,
    ComplexityLevel,
    GoalRigidity,
    LiquidityLevel,
    RiskLevel,
)
from app.models.family import Household
from app.models.finance import Asset, IncomeSource, InsurancePolicy, Responsibility
from app.schemas.finance import AssetCreate
from app.schemas.portfolio import ProductCatalogItem
from app.services.financial.facts import load_household_facts
from app.services.methodology.rules import load_methodology_rules
from app.services.planning.engine import empty_counterfactual, plan_facts, plan_household
from app.services.planning.rules import load_planning_rules
from app.services.portfolio.catalog import build_catalog_response, load_product_catalog
from app.services.portfolio.optimizer import ASSET_CATEGORY_MAP, current_growth_weights
from app.services.portfolio.rules import load_portfolio_rules
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
ANALYSIS_DATE = date(2026, 8, 4)


def seed_households() -> dict[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            portfolio_rules_path=PORTFOLIO_RULES_PATH,
            product_catalog_path=PRODUCT_CATALOG_PATH,
            reset=True,
        )
        return {
            household.code: household.id
            for household in session.scalars(select(Household))
        }


def planning(household_id: str):  # type: ignore[no-untyped-def]
    with SessionLocal() as session:
        return plan_household(
            session,
            household_id,
            FINANCIAL_RULES_PATH,
            PLANNING_RULES_PATH,
            ANALYSIS_DATE,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
        )


def test_credit_limit_and_insurance_coverage_never_become_investable_assets() -> None:
    household_id = seed_households()["DEMO_B"]
    before = planning(household_id)
    assert before.denominators.investable_financial_assets == Decimal("320000.00")
    assert "未使用额度不计入资产" in before.accounts[0].product_education[0]

    with SessionLocal() as session:
        policies = session.scalars(
            select(InsurancePolicy).where(InsurancePolicy.household_id == household_id)
        )
        for policy in policies:
            policy.coverage_amount = Decimal("999999999.00")
        session.commit()

    after = planning(household_id)
    assert after.denominators.investable_financial_assets == (
        before.denominators.investable_financial_assets
    )


def test_locked_pension_is_not_emergency_liquidity_and_wrapper_does_not_lower_risk() -> None:
    household_id = seed_households()["DEMO_B"]
    plan = planning(household_id)
    stable = next(item for item in plan.accounts if item.bucket.value == "stable_goals")

    assert plan.asset_liquidity.locked_institutional_assets == Decimal("30000.00")
    assert plan.asset_liquidity.withdrawable_institutional_assets == Decimal("0.00")
    assert stable.current_amount == Decimal("150000.00")

    pension_fund = AssetCreate(
        name="个人养老金指数基金",
        category=AssetCategory.PENSION_ACCOUNT,
        acquisition_cost=Decimal("10000.00"),
        market_value=Decimal("10000.00"),
        liquidity_days=3650,
        liquidity_level=LiquidityLevel.ILLIQUID,
        risk_level=RiskLevel.HIGH,
        purpose="退休长期增长",
        ownership="本人",
        purpose_dimension=AssetPurposeDimension.GROWTH,
        account_wrapper=AccountWrapper.PERSONAL_PENSION,
        principal_loss_possible=True,
        legally_principal_guaranteed=False,
        product_complexity=ComplexityLevel.STANDARD,
        valuation_date=ANALYSIS_DATE,
        data_source="invariant-test",
        is_user_confirmed=True,
    )
    assert pension_fund.risk_level == RiskLevel.HIGH
    assert pension_fund.account_wrapper == AccountWrapper.PERSONAL_PENSION
    assert pension_fund.principal_loss_possible is True
    assert pension_fund.lock_up is True


def test_pfnw_three_denominators_and_growth_denominator_are_explicit() -> None:
    household_id = seed_households()["DEMO_B"]
    plan = planning(household_id)

    assert plan.denominators.plannable_financial_net_worth == Decimal("-888000.00")
    assert plan.denominators.plannable_financial_net_worth == (
        plan.denominators.investable_financial_assets - Decimal("1208000.00")
    )
    assert plan.growth_70.denominator_id == "residual_long_term_plannable_capital"
    assert plan.growth_70.denominator_id != "total_household_assets"
    for account in plan.accounts:
        canonical = {
            measure.denominator_id
            for measure in account.measures
            if not measure.deprecated
        }
        assert canonical == {
            "total_household_assets",
            "investable_financial_assets",
            "residual_long_term_plannable_capital",
        }


def test_threshold_floor_formal_growth_and_learning_sleeve_invariants() -> None:
    household_ids = seed_households()
    accumulator = planning(household_ids["DEMO_A"])
    recovery = planning(household_ids["DEMO_B"])

    threshold = accumulator.methodology.regional_threshold
    assert Decimal("300000.00") <= threshold.effective_threshold <= Decimal("1000000.00")
    assert threshold.effective_threshold >= threshold.policy_minimum
    assert threshold.effective_threshold >= threshold.customer_selected_threshold
    assert accumulator.growth_70.formal_growth_amount == Decimal("0.00")
    assert accumulator.investment_learning.recommended_amount <= (
        accumulator.investment_learning.denominator_value * Decimal("0.10")
    )
    assert accumulator.contribution_plan.annual_new_surplus > Decimal("0.00")
    assert recovery.investment_learning.recommended_amount == Decimal("0.00")
    assert "仍有待处理的高息债务" in recovery.investment_learning.failed_conditions


def test_learning_sleeve_requires_positive_surplus() -> None:
    household_id = seed_households()["DEMO_A"]
    with SessionLocal() as session:
        for income in session.scalars(
            select(IncomeSource).where(IncomeSource.household_id == household_id)
        ):
            income.amount = Decimal("0.00")
        session.commit()

    plan = planning(household_id)
    assert plan.contribution_plan.annual_new_surplus == Decimal("0.00")
    assert plan.investment_learning.recommended_amount == Decimal("0.00")
    assert "年度新增结余不为正" in plan.investment_learning.failed_conditions


def test_market_snapshot_and_llm_cannot_override_hard_safety_gates() -> None:
    household_id = seed_households()["DEMO_B"]
    with SessionLocal() as session:
        facts = load_household_facts(session, household_id)
    planning_rules = load_planning_rules(PLANNING_RULES_PATH)
    methodology_rules = load_methodology_rules(METHODOLOGY_RULES_PATH)
    favorable = methodology_rules.market_regime_snapshot.model_copy(
        update={"regime": "favorable", "snapshot_version": "invariant-favorable"}
    )
    plan = plan_facts(
        facts,
        FINANCIAL_RULES_PATH,
        planning_rules,
        ANALYSIS_DATE,
        empty_counterfactual(),
        methodology_rules.model_copy(update={"market_regime_snapshot": favorable}),
    )

    assert plan.growth_70.formal_growth_amount == Decimal("0.00")
    assert any(item.status == "block" and item.limits_growth for item in plan.constraints)
    assert plan.meta.calculation_source == "deterministic_tools"
    assert plan.decision_evidence.llm_model_version is None
    assert plan.decision_evidence.llm_prompt_version is None


@pytest.mark.parametrize(
    ("regime", "minimum", "anchor", "maximum"),
    [
        ("favorable", "0.05", "0.075", "0.10"),
        ("neutral", "0.10", "0.15", "0.20"),
        ("defensive", "0.20", "0.25", "0.30"),
    ],
)
def test_stability_tactical_reference_is_bounded_but_responsibilities_can_exceed_it(
    regime: str,
    minimum: str,
    anchor: str,
    maximum: str,
) -> None:
    rules = load_planning_rules(PLANNING_RULES_PATH)
    configured = rules.market_environment.profiles[regime]
    assert configured.stable_reference_min == Decimal(minimum)
    assert configured.stable_target_ratio == Decimal(anchor)
    assert configured.stable_reference_max == Decimal(maximum)
    assert (
        Decimal("0.05")
        <= configured.stable_reference_min
        <= configured.stable_reference_max
        <= Decimal("0.30")
    )

    plan = planning(seed_households()["DEMO_A"])
    stable = next(item for item in plan.accounts if item.bucket.value == "stable_goals")
    stable_ratio = stable.recommended_amount / plan.denominators.investable_financial_assets
    assert stable_ratio > Decimal("0.30")
    assert stable.reference_band is not None and stable.reference_band.binding is False


def test_single_stock_is_not_diversified_equity() -> None:
    household_id = seed_households()["DEMO_A"]
    with SessionLocal() as session:
        equity = session.scalar(
            select(Asset).where(
                Asset.household_id == household_id,
                Asset.category == AssetCategory.EQUITY_FUND,
            )
        )
        assert equity is not None
        equity.category = AssetCategory.STOCK
        session.commit()
        facts = load_household_facts(session, household_id)

    weights = current_growth_weights(facts, load_portfolio_rules(PORTFOLIO_RULES_PATH))
    assert ASSET_CATEGORY_MAP["stock"] == "single_equity"
    assert weights["diversified_equity"] == Decimal("0")


def test_pph_never_labels_minimum_wage_as_cpi() -> None:
    plan = planning(seed_households()["DEMO_A"])
    hurdle = plan.methodology.purchasing_power_hurdle
    minimum_wage = next(
        item for item in hurdle.components if item.code == "regional_minimum_wage_cagr"
    )
    assert minimum_wage.is_cpi is False
    assert hurdle.minimum_wage_is_cpi is False
    assert hurdle.rate == max(item.rate for item in hurdle.components)


def test_native_responsibility_ledger_records_are_loaded_without_goal_double_counting() -> None:
    household_id = seed_households()["DEMO_A"]
    with SessionLocal() as session:
        session.add(
            Responsibility(
                household_id=household_id,
                responsible_member_id=None,
                beneficiary="父母",
                responsibility_type="parent_support",
                target_amount=Decimal("120000.00"),
                minimum_acceptable_amount=Decimal("90000.00"),
                target_date=date(2030, 8, 4),
                rigidity=GoalRigidity.RIGID,
                deferrable=False,
                annual_growth_assumption=Decimal("0.030000"),
                prepared_amount=Decimal("20000.00"),
                institutional_coverage=Decimal("10000.00"),
                funding_source="current_and_future_contributions",
                source_goal_id=None,
                valuation_date=ANALYSIS_DATE,
                data_source="invariant-test",
                is_user_confirmed=True,
            )
        )
        session.commit()

    ledger = planning(household_id).methodology.responsibility_ledger
    entry = next(item for item in ledger.entries if item.responsibility_type == "parent_support")
    assert entry.beneficiary == "父母"
    assert entry.institutional_coverage == Decimal("10000.00")
    assert ledger.total_target_amount >= Decimal("120000.00")


def test_stale_product_snapshot_blocks_execution_but_keeps_education() -> None:
    seed_households()
    methodology = load_methodology_rules(METHODOLOGY_RULES_PATH)
    with SessionLocal() as session:
        catalog = build_catalog_response(
            session,
            PRODUCT_CATALOG_PATH,
            analysis_date=date(2027, 8, 4),
            maximum_age_days=methodology.product_snapshot_policy.maximum_age_days,
        )
    assert catalog.catalog_stale is True
    assert catalog.executable_recommendations_allowed is False
    assert catalog.stale_action == "block_executable_allow_education"


def test_non_guaranteed_product_cannot_be_relabelled_as_principal_guaranteed() -> None:
    catalog = load_product_catalog(PRODUCT_CATALOG_PATH)
    wmp = next(item for item in catalog.products if item.product_type == "bank_wealth_management")
    invalid = {
        **wmp.model_dump(mode="python"),
        "principal_guaranteed": True,
        "legally_principal_guaranteed": True,
        "principal_loss_possible": False,
    }
    with pytest.raises(ValidationError, match="不得统一标记为保本"):
        ProductCatalogItem.model_validate(invalid)


def test_current_stock_and_future_contributions_are_not_double_counted() -> None:
    plan = planning(seed_households()["DEMO_A"])
    assert plan.current_allocation_plan.current_investable_balance == (
        plan.denominators.investable_financial_assets
    )
    assert plan.denominators.available_planning_resources == (
        plan.current_allocation_plan.current_investable_balance
    )
    assert plan.contribution_plan.denominator_id == "annual_new_surplus"
    assert plan.contribution_plan.annual_new_surplus not in {
        plan.denominators.available_planning_resources,
        plan.current_allocation_plan.current_balance_available_after_debt,
    }


def test_every_decision_evidence_version_is_populated_and_hash_is_stable() -> None:
    household_id = seed_households()["DEMO_A"]
    first = planning(household_id).decision_evidence
    second = planning(household_id).decision_evidence
    required = [
        first.household_input_version,
        first.methodology_version,
        first.financial_rule_version,
        first.planning_rule_version,
        first.regional_parameter_version,
        first.market_regime_version,
        first.minimum_wage_snapshot_version,
        first.public_data_snapshot_version,
        first.pension_policy_version,
        first.portfolio_version,
        first.product_snapshot_version,
        first.risk_assessment_version,
        first.behavior_assessment_version,
    ]
    assert all(value and value != "unknown" for value in required)
    assert first.decision_hash == second.decision_hash
    assert len(first.decision_hash) == 64


def test_external_demo_snapshots_share_governance_metadata() -> None:
    methodology = load_methodology_rules(METHODOLOGY_RULES_PATH)
    catalog = load_product_catalog(PRODUCT_CATALOG_PATH)
    required = set(methodology.data_governance.required_fields)
    snapshots = [
        methodology.market_regime_snapshot.model_dump(),
        methodology.pension_policy_snapshot.model_dump(),
        methodology.property_policy_snapshot.model_dump(),
        catalog.model_dump(),
    ]

    for snapshot in snapshots:
        assert required <= snapshot.keys()
        assert snapshot["is_demo"] is True
        assert snapshot["is_live"] is False

    for snapshot in methodology.regional_minimum_wage_snapshots.values():
        payload = snapshot.model_dump()
        assert required <= payload.keys()
        assert payload["is_demo"] is False
        assert payload["is_live"] is False
        assert payload["data_quality"].startswith("verified_public_snapshot")
