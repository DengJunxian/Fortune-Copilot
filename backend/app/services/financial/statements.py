from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import ExpenseCategory, ExpenseNecessity, PropertyUse
from app.domain.financial import AssetFact, HouseholdFacts, LiabilityFact
from app.schemas.financial_analysis import (
    AssetStatementLine,
    BalanceSheet,
    CashFlowLine,
    CashFlowStatement,
    FinancialStatements,
    GoalFundingLine,
    GoalFundingStatement,
    InsuranceStatement,
    InsuranceStatementLine,
    LiabilityStatementLine,
    LiquidityLine,
    LiquidityMatrix,
)
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import ZERO, annualize, money, safe_ratio, years_between


def _asset_group(asset: AssetFact, rules: FinancialRules) -> str:
    category = asset.category.value
    if asset.property_use == PropertyUse.PRIMARY_RESIDENCE:
        return "primary_residence"
    if asset.property_use == PropertyUse.INVESTMENT_PROPERTY:
        return "investment_property"
    if category in rules.classification.investable_financial_asset_categories:
        return "investable_financial"
    if category in rules.classification.financial_asset_categories:
        return "restricted_financial"
    if category == "vehicle":
        return "personal_use"
    return "other"


def _scheduled_twelve_month_payment(item: LiabilityFact, analysis_date: date) -> Decimal:
    next_year = analysis_date + timedelta(days=365)
    if item.maturity_date is not None and item.maturity_date <= next_year:
        return money(item.outstanding_balance)
    return money(min(item.outstanding_balance, item.monthly_payment * Decimal("12")))


def _build_balance_sheet(
    facts: HouseholdFacts,
    rules: FinancialRules,
    analysis_date: date,
) -> BalanceSheet:
    asset_totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    assets: list[AssetStatementLine] = []
    for asset in facts.assets:
        group = _asset_group(asset, rules)
        asset_totals[group] += asset.market_value
        assets.append(
            AssetStatementLine(
                id=asset.id,
                name=asset.name,
                category=asset.category.value,
                subcategory=asset.subcategory,
                asset_group=group,
                market_value=money(asset.market_value),
                acquisition_cost=money(asset.acquisition_cost),
                unrealized_change=money(asset.market_value - asset.acquisition_cost),
                liquidity_days=asset.liquidity_days,
                liquidity_level=asset.liquidity_level.value,
                property_use=asset.property_use.value,
                pledged=asset.pledged,
                valuation_date=asset.valuation_date,
            )
        )

    liability_totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    liabilities: list[LiabilityStatementLine] = []
    for liability in facts.liabilities:
        liability_totals[liability.category.value] += liability.outstanding_balance
        liabilities.append(
            LiabilityStatementLine(
                id=liability.id,
                name=liability.name,
                category=liability.category.value,
                outstanding_balance=money(liability.outstanding_balance),
                annual_interest_rate=liability.annual_interest_rate,
                monthly_payment=money(liability.monthly_payment),
                scheduled_twelve_month_payment=_scheduled_twelve_month_payment(
                    liability, analysis_date
                ),
                maturity_date=liability.maturity_date,
                rate_type=liability.rate_type.value,
                linked_asset_id=liability.linked_asset_id,
                is_high_interest=liability.is_high_interest,
            )
        )

    total_assets = money(sum((item.market_value for item in facts.assets), ZERO))
    total_liabilities = money(sum((item.outstanding_balance for item in facts.liabilities), ZERO))
    net_worth = money(total_assets - total_liabilities)
    return BalanceSheet(
        assets=assets,
        liabilities=liabilities,
        asset_totals_by_group={key: money(value) for key, value in asset_totals.items()},
        liability_totals_by_category={key: money(value) for key, value in liability_totals.items()},
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        accounting_identity=(f"{total_assets:.2f} - {total_liabilities:.2f} = {net_worth:.2f}"),
    )


def _build_cash_flow(facts: HouseholdFacts) -> CashFlowStatement:
    income_totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    expense_totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    income_lines: list[CashFlowLine] = []
    expense_lines: list[CashFlowLine] = []

    for income in facts.incomes:
        annual_amount = annualize(income.amount, income.frequency)
        income_totals[income.income_type.value] += annual_amount
        income_lines.append(
            CashFlowLine(
                id=income.id,
                name=income.name,
                category=income.income_type.value,
                frequency=income.frequency.value,
                original_amount=money(income.amount),
                annual_amount=annual_amount,
                essential=False,
                compressible_amount=ZERO,
            )
        )

    for expense in facts.expenses:
        annual_amount = annualize(expense.amount, expense.frequency)
        expense_totals[expense.category.value] += annual_amount
        expense_lines.append(
            CashFlowLine(
                id=expense.id,
                name=expense.name,
                category=expense.category.value,
                frequency=expense.frequency.value,
                original_amount=money(expense.amount),
                annual_amount=annual_amount,
                essential=expense.necessity == ExpenseNecessity.ESSENTIAL,
                compressible_amount=money(annual_amount * expense.compressible_ratio),
            )
        )

    annual_income = money(sum(income_totals.values(), ZERO))
    annual_expenses = money(sum(expense_totals.values(), ZERO))
    essential = money(
        sum(
            (line.annual_amount for line in expense_lines if line.essential),
            ZERO,
        )
    )
    basic_living = money(expense_totals.get(ExpenseCategory.BASIC_LIVING.value, ZERO))
    debt_service = money(expense_totals.get(ExpenseCategory.DEBT_SERVICE.value, ZERO))
    premiums = money(expense_totals.get(ExpenseCategory.INSURANCE_PREMIUM.value, ZERO))
    return CashFlowStatement(
        income_lines=income_lines,
        expense_lines=expense_lines,
        income_totals_by_type={key: money(value) for key, value in income_totals.items()},
        expense_totals_by_category={key: money(value) for key, value in expense_totals.items()},
        annual_income=annual_income,
        annual_expenses=annual_expenses,
        annual_surplus=money(annual_income - annual_expenses),
        annual_basic_living_expenses=basic_living,
        annual_essential_expenses=essential,
        annual_fixed_expenses=essential,
        annual_debt_service=debt_service,
        annual_insurance_premiums=premiums,
    )


def _build_insurance(facts: HouseholdFacts, analysis_date: date) -> InsuranceStatement:
    member_names = {item.id: item.display_name for item in facts.members}
    coverage: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    lines: list[InsuranceStatementLine] = []
    total_premium = ZERO
    total_cash_value = ZERO
    for item in facts.insurance_policies:
        active = item.start_date <= analysis_date and (
            item.end_date is None or item.end_date >= analysis_date
        )
        if active:
            coverage[item.policy_type.value] += item.coverage_amount
            total_premium += item.annual_premium
            total_cash_value += item.cash_value
        lines.append(
            InsuranceStatementLine(
                id=item.id,
                name=item.name,
                policy_type=item.policy_type.value,
                insured_member_id=item.insured_member_id,
                insured_member_name=member_names.get(item.insured_member_id, "未知成员"),
                coverage_amount=money(item.coverage_amount),
                annual_premium=money(item.annual_premium),
                deductible=money(item.deductible),
                waiting_period_days=item.waiting_period_days,
                start_date=item.start_date,
                end_date=item.end_date,
                guaranteed_benefit=money(item.guaranteed_benefit),
                non_guaranteed_benefit=money(item.non_guaranteed_benefit),
                cash_value=money(item.cash_value),
                active_on_analysis_date=active,
            )
        )
    return InsuranceStatement(
        policies=lines,
        coverage_by_policy_type={key: money(value) for key, value in coverage.items()},
        total_annual_premium=money(total_premium),
        total_cash_value=money(total_cash_value),
        counting_note=(
            "保额、保费和现金价值分列；保额不是资产，现金价值只有在资产表已有对应记录时才计入总资产。"
        ),
    )


def _build_goals(facts: HouseholdFacts, analysis_date: date) -> GoalFundingStatement:
    lines: list[GoalFundingLine] = []
    for item in facts.goals:
        funding_ratio = safe_ratio(item.prepared_amount, item.target_amount)
        lines.append(
            GoalFundingLine(
                id=item.id,
                name=item.name,
                goal_type=item.goal_type.value,
                target_amount=money(item.target_amount),
                target_date=item.target_date,
                years_remaining=years_between(analysis_date, item.target_date),
                rigidity=item.rigidity.value,
                priority=item.priority,
                can_defer=item.can_defer,
                minimum_acceptable_amount=money(item.minimum_acceptable_amount),
                prepared_amount=money(item.prepared_amount),
                funding_gap=money(max(ZERO, item.target_amount - item.prepared_amount)),
                funding_ratio=funding_ratio,
                annual_cost_growth_rate=item.annual_cost_growth_rate,
            )
        )
    return GoalFundingStatement(
        goals=lines,
        total_target_amount=money(sum((item.target_amount for item in facts.goals), ZERO)),
        total_prepared_amount=money(sum((item.prepared_amount for item in facts.goals), ZERO)),
        total_funding_gap=money(sum((item.funding_gap for item in lines), ZERO)),
    )


def _liquidity_tier(days: int) -> str:
    if days == 0:
        return "immediate"
    if days <= 7:
        return "within_7_days"
    if days <= 30:
        return "within_30_days"
    if days <= 365:
        return "within_1_year"
    return "illiquid"


def _build_liquidity(facts: HouseholdFacts, rules: FinancialRules) -> LiquidityMatrix:
    financial_categories = set(rules.classification.financial_asset_categories)
    totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    lines: list[LiquidityLine] = []
    emergency = ZERO
    short_term = ZERO
    twelve_month = ZERO
    for item in facts.assets:
        tier = _liquidity_tier(item.liquidity_days)
        totals[tier] += item.market_value
        is_financial = item.category.value in financial_categories
        in_emergency = is_financial and (
            item.liquidity_level.value in rules.classification.emergency_liquid_levels
        )
        in_short = is_financial and (
            item.liquidity_days <= rules.classification.short_term_liquid_max_days
        )
        in_twelve = is_financial and (
            item.liquidity_days <= rules.classification.twelve_month_liquid_max_days
        )
        if in_emergency:
            emergency += item.market_value
        if in_short:
            short_term += item.market_value
        if in_twelve:
            twelve_month += item.market_value
        lines.append(
            LiquidityLine(
                asset_id=item.id,
                name=item.name,
                category=item.category.value,
                market_value=money(item.market_value),
                liquidity_days=item.liquidity_days,
                liquidity_level=item.liquidity_level.value,
                liquidity_tier=tier,
                included_in_emergency_reserve=in_emergency,
                included_in_short_term_coverage=in_short,
            )
        )
    return LiquidityMatrix(
        lines=lines,
        totals_by_tier={key: money(value) for key, value in totals.items()},
        emergency_liquid_assets=money(emergency),
        short_term_liquid_assets=money(short_term),
        twelve_month_liquid_assets=money(twelve_month),
    )


def build_statements(
    facts: HouseholdFacts,
    rules: FinancialRules,
    analysis_date: date,
) -> FinancialStatements:
    return FinancialStatements(
        balance_sheet=_build_balance_sheet(facts, rules, analysis_date),
        cash_flow=_build_cash_flow(facts),
        insurance=_build_insurance(facts, analysis_date),
        goal_funding=_build_goals(facts, analysis_date),
        liquidity=_build_liquidity(facts, rules),
    )
