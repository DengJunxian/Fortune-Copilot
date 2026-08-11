from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast

from app.domain.enums import (
    AssetCategory,
    ExpenseCategory,
    ExpenseNecessity,
    IncomeType,
    InsuranceType,
    PropertyUse,
)
from app.domain.financial import HouseholdFacts
from app.schemas.twin import GoalState, InitialTwinState, MemberState
from app.services.financial.utils import ZERO, annualize, money


@dataclass(frozen=True, slots=True)
class IncomeStream:
    id: str
    member_id: str | None
    name: str
    income_type: IncomeType
    monthly_amount: float
    annual_volatility: float
    retirement_age: int | None
    primary_rank: int


@dataclass(frozen=True, slots=True)
class DebtSpec:
    id: str
    name: str
    category: str
    balance: float
    annual_rate: float
    monthly_payment: float
    floating_rate: bool


@dataclass(frozen=True, slots=True)
class GoalSpec:
    id: str
    name: str
    goal_type: str
    due_month: int
    target_amount: float
    prepared_amount: float
    annual_cost_growth_rate: float
    can_defer: bool


@dataclass(frozen=True, slots=True)
class MemberSpec:
    id: str
    name: str
    relationship: str
    age_at_start: float
    recorded_retirement_age: int | None


@dataclass(frozen=True, slots=True)
class TwinModelInput:
    household_id: str
    household_code: str
    currency: str
    synthetic_data: bool
    analysis_date: date
    members: tuple[MemberSpec, ...]
    incomes: tuple[IncomeStream, ...]
    debts: tuple[DebtSpec, ...]
    goals: tuple[GoalSpec, ...]
    asset_buckets: dict[str, float]
    monthly_expenses: float
    monthly_essential_expenses: float
    monthly_compressible_expenses: float
    medical_coverage: float
    medical_deductible: float
    pension_monthly_contributions: float
    source_record_ids: tuple[str, ...]


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(1, months)


def _age(start: date, birth_date: date) -> Decimal:
    return (Decimal((start - birth_date).days) / Decimal("365.25")).quantize(Decimal("0.01"))


def _asset_bucket(
    category: AssetCategory, property_use: PropertyUse, subcategory: str | None
) -> str:
    if property_use == PropertyUse.PRIMARY_RESIDENCE:
        return "primary_property"
    if property_use == PropertyUse.INVESTMENT_PROPERTY:
        return "investment_property"
    if category in {
        AssetCategory.CASH,
        AssetCategory.DEMAND_DEPOSIT,
        AssetCategory.MONEY_MARKET,
    }:
        return "cash_equivalent"
    if category in {
        AssetCategory.TIME_DEPOSIT,
        AssetCategory.BANK_WEALTH_MANAGEMENT,
        AssetCategory.BOND,
        AssetCategory.BOND_FUND,
    }:
        return "fixed_income"
    if category in {
        AssetCategory.PUBLIC_FUND,
        AssetCategory.EQUITY_FUND,
        AssetCategory.STOCK,
    }:
        return "diversified_equity"
    if category == AssetCategory.PENSION_ACCOUNT:
        return "pension"
    if category == AssetCategory.TRUST:
        return "real_assets"
    if subcategory and "黄金" in subcategory:
        return "gold"
    return "other_assets"


def build_twin_model_input(facts: HouseholdFacts, analysis_date: date) -> TwinModelInput:
    member_by_id = {item.id: item for item in facts.members}
    members = tuple(
        MemberSpec(
            id=item.id,
            name=item.display_name,
            relationship=item.relationship,
            age_at_start=float(_age(analysis_date, item.birth_date)),
            recorded_retirement_age=item.expected_retirement_age,
        )
        for item in facts.members
    )
    annual_incomes = [annualize(item.amount, item.frequency) for item in facts.incomes]
    employment_order = sorted(
        (
            (annual_incomes[index], item.id)
            for index, item in enumerate(facts.incomes)
            if item.income_type == IncomeType.EMPLOYMENT
        ),
        reverse=True,
    )
    ranks = {item_id: rank for rank, (_, item_id) in enumerate(employment_order, start=1)}
    incomes = tuple(
        IncomeStream(
            id=item.id,
            member_id=item.member_id,
            name=item.name,
            income_type=item.income_type,
            monthly_amount=float(annual_incomes[index] / Decimal("12")),
            annual_volatility=float(item.volatility),
            retirement_age=(
                member_by_id[item.member_id].expected_retirement_age
                if item.member_id in member_by_id
                else None
            ),
            primary_rank=ranks.get(item.id, 0),
        )
        for index, item in enumerate(facts.incomes)
    )
    expenses = [
        (item, annualize(item.amount, item.frequency))
        for item in facts.expenses
        if item.category != ExpenseCategory.DEBT_SERVICE
    ]
    annual_expenses = sum((amount for _, amount in expenses), ZERO)
    annual_essential = sum(
        (amount for item, amount in expenses if item.necessity == ExpenseNecessity.ESSENTIAL),
        ZERO,
    )
    annual_compressible = sum(
        (amount * item.compressible_ratio for item, amount in expenses),
        ZERO,
    )
    asset_buckets = {
        "cash_equivalent": 0.0,
        "fixed_income": 0.0,
        "diversified_equity": 0.0,
        "real_assets": 0.0,
        "gold": 0.0,
        "pension": 0.0,
        "primary_property": 0.0,
        "investment_property": 0.0,
        "other_assets": 0.0,
    }
    for asset in facts.assets:
        asset_buckets[_asset_bucket(asset.category, asset.property_use, asset.subcategory)] += (
            float(asset.market_value)
        )
    debts = tuple(
        DebtSpec(
            id=item.id,
            name=item.name,
            category=item.category.value,
            balance=float(item.outstanding_balance),
            annual_rate=float(item.annual_interest_rate),
            monthly_payment=float(item.monthly_payment),
            floating_rate=item.rate_type.value == "floating",
        )
        for item in facts.liabilities
    )
    goals = tuple(
        GoalSpec(
            id=item.id,
            name=item.name,
            goal_type=item.goal_type.value,
            due_month=_months_between(analysis_date, item.target_date),
            target_amount=float(item.target_amount),
            prepared_amount=float(item.prepared_amount),
            annual_cost_growth_rate=float(item.annual_cost_growth_rate),
            can_defer=item.can_defer,
        )
        for item in sorted(facts.goals, key=lambda goal: (goal.target_date, goal.priority))
    )
    active_medical = [
        item
        for item in facts.insurance_policies
        if item.policy_type in {InsuranceType.MEDICAL, InsuranceType.CRITICAL_ILLNESS}
        and item.start_date <= analysis_date
        and (item.end_date is None or item.end_date >= analysis_date)
    ]
    medical_coverage = sum((float(item.coverage_amount) for item in active_medical), 0.0)
    medical_deductible = sum((float(item.deductible) for item in active_medical), 0.0)
    pension_contributions = sum(
        (
            item.annual_personal_contribution + item.annual_employer_contribution
            for item in facts.social_security_accounts
        ),
        ZERO,
    )
    source_ids = tuple(
        [item.id for item in facts.members]
        + [item.id for item in facts.incomes]
        + [item.id for item in facts.expenses]
        + [item.id for item in facts.assets]
        + [item.id for item in facts.liabilities]
        + [item.id for item in facts.insurance_policies]
        + [item.id for item in facts.social_security_accounts]
        + [item.id for item in facts.goals]
    )
    return TwinModelInput(
        household_id=facts.id,
        household_code=facts.code,
        currency=facts.currency,
        synthetic_data=facts.is_synthetic,
        analysis_date=analysis_date,
        members=members,
        incomes=incomes,
        debts=debts,
        goals=goals,
        asset_buckets=asset_buckets,
        monthly_expenses=float(annual_expenses / Decimal("12")),
        monthly_essential_expenses=float(annual_essential / Decimal("12")),
        monthly_compressible_expenses=float(annual_compressible / Decimal("12")),
        medical_coverage=medical_coverage,
        medical_deductible=medical_deductible,
        pension_monthly_contributions=float(pension_contributions / Decimal("12")),
        source_record_ids=source_ids,
    )


def initial_state_response(model: TwinModelInput) -> InitialTwinState:
    annual_income = sum((item.monthly_amount * 12 for item in model.incomes), 0.0)
    total_assets = sum(model.asset_buckets.values())
    total_liabilities = sum((item.balance for item in model.debts), 0.0)
    return InitialTwinState(
        members=[
            MemberState(
                member_id=item.id,
                name=item.name,
                relationship=item.relationship,
                age_at_start=Decimal(str(item.age_at_start)),
                recorded_retirement_age=item.recorded_retirement_age,
            )
            for item in model.members
        ],
        annual_income=money(Decimal(str(annual_income))),
        annual_expenses_excluding_debt_service=money(Decimal(str(model.monthly_expenses * 12))),
        annual_essential_expenses_excluding_debt_service=money(
            Decimal(str(model.monthly_essential_expenses * 12))
        ),
        monthly_compressible_expenses=money(Decimal(str(model.monthly_compressible_expenses))),
        asset_buckets={
            key: money(Decimal(str(value))) for key, value in model.asset_buckets.items()
        },
        total_assets=money(Decimal(str(total_assets))),
        total_liabilities=money(Decimal(str(total_liabilities))),
        medical_coverage_available=money(Decimal(str(model.medical_coverage))),
        medical_deductible=money(Decimal(str(model.medical_deductible))),
        pension_annual_contributions=money(Decimal(str(model.pension_monthly_contributions * 12))),
        goals=[
            GoalState(
                goal_id=item.id,
                name=item.name,
                goal_type=item.goal_type,
                due_month=item.due_month,
                current_amount=money(Decimal(str(item.target_amount))),
                prepared_amount=money(Decimal(str(item.prepared_amount))),
                annual_cost_growth_rate=Decimal(str(item.annual_cost_growth_rate)),
            )
            for item in model.goals
        ],
        source_record_ids=list(model.source_record_ids),
        counting_note=(
            "初始总资产与财务底表一致；信用卡额度从未进入资产。社保名义余额不重复加入净资产，"
            "未来个人和单位缴费仅在劳动收入存续期进入养老金状态。债务还款从支出表剔除后按负债逐月摊还，避免重复扣减。"
        ),
    )


def serialize_twin_model_input(model: TwinModelInput) -> dict[str, object]:
    """Persist the exact simulator input without coupling snapshots to ORM rows."""

    return {
        "household_id": model.household_id,
        "household_code": model.household_code,
        "currency": model.currency,
        "synthetic_data": model.synthetic_data,
        "analysis_date": model.analysis_date.isoformat(),
        "members": [
            {
                "id": item.id,
                "name": item.name,
                "relationship": item.relationship,
                "age_at_start": item.age_at_start,
                "recorded_retirement_age": item.recorded_retirement_age,
            }
            for item in model.members
        ],
        "incomes": [
            {
                "id": item.id,
                "member_id": item.member_id,
                "name": item.name,
                "income_type": item.income_type.value,
                "monthly_amount": item.monthly_amount,
                "annual_volatility": item.annual_volatility,
                "retirement_age": item.retirement_age,
                "primary_rank": item.primary_rank,
            }
            for item in model.incomes
        ],
        "debts": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "balance": item.balance,
                "annual_rate": item.annual_rate,
                "monthly_payment": item.monthly_payment,
                "floating_rate": item.floating_rate,
            }
            for item in model.debts
        ],
        "goals": [
            {
                "id": item.id,
                "name": item.name,
                "goal_type": item.goal_type,
                "due_month": item.due_month,
                "target_amount": item.target_amount,
                "prepared_amount": item.prepared_amount,
                "annual_cost_growth_rate": item.annual_cost_growth_rate,
                "can_defer": item.can_defer,
            }
            for item in model.goals
        ],
        "asset_buckets": dict(model.asset_buckets),
        "monthly_expenses": model.monthly_expenses,
        "monthly_essential_expenses": model.monthly_essential_expenses,
        "monthly_compressible_expenses": model.monthly_compressible_expenses,
        "medical_coverage": model.medical_coverage,
        "medical_deductible": model.medical_deductible,
        "pension_monthly_contributions": model.pension_monthly_contributions,
        "source_record_ids": list(model.source_record_ids),
    }


def deserialize_twin_model_input(payload: dict[str, object]) -> TwinModelInput:
    """Restore a simulator input from a persistent snapshot."""

    members_raw = payload.get("members", [])
    incomes_raw = payload.get("incomes", [])
    debts_raw = payload.get("debts", [])
    goals_raw = payload.get("goals", [])
    buckets_raw = payload.get("asset_buckets", {})
    if not all(
        isinstance(value, list) for value in (members_raw, incomes_raw, debts_raw, goals_raw)
    ) or not isinstance(buckets_raw, dict):
        raise ValueError("持久快照中的模拟初始状态无效")

    members = cast(list[dict[str, Any]], members_raw)
    incomes = cast(list[dict[str, Any]], incomes_raw)
    debts = cast(list[dict[str, Any]], debts_raw)
    goals = cast(list[dict[str, Any]], goals_raw)
    buckets = cast(dict[str, Any], buckets_raw)
    source_ids_raw = payload.get("source_record_ids", [])
    if not isinstance(source_ids_raw, list):
        raise ValueError("持久快照中的来源记录无效")

    return TwinModelInput(
        household_id=str(payload["household_id"]),
        household_code=str(payload["household_code"]),
        currency=str(payload["currency"]),
        synthetic_data=bool(payload["synthetic_data"]),
        analysis_date=date.fromisoformat(str(payload["analysis_date"])),
        members=tuple(
            MemberSpec(
                id=str(item["id"]),
                name=str(item["name"]),
                relationship=str(item["relationship"]),
                age_at_start=float(item["age_at_start"]),
                recorded_retirement_age=(
                    int(item["recorded_retirement_age"])
                    if item.get("recorded_retirement_age") is not None
                    else None
                ),
            )
            for item in members
        ),
        incomes=tuple(
            IncomeStream(
                id=str(item["id"]),
                member_id=str(item["member_id"]) if item.get("member_id") is not None else None,
                name=str(item["name"]),
                income_type=IncomeType(str(item["income_type"])),
                monthly_amount=float(item["monthly_amount"]),
                annual_volatility=float(item["annual_volatility"]),
                retirement_age=(
                    int(item["retirement_age"]) if item.get("retirement_age") is not None else None
                ),
                primary_rank=int(item["primary_rank"]),
            )
            for item in incomes
        ),
        debts=tuple(
            DebtSpec(
                id=str(item["id"]),
                name=str(item["name"]),
                category=str(item["category"]),
                balance=float(item["balance"]),
                annual_rate=float(item["annual_rate"]),
                monthly_payment=float(item["monthly_payment"]),
                floating_rate=bool(item["floating_rate"]),
            )
            for item in debts
        ),
        goals=tuple(
            GoalSpec(
                id=str(item["id"]),
                name=str(item["name"]),
                goal_type=str(item["goal_type"]),
                due_month=int(item["due_month"]),
                target_amount=float(item["target_amount"]),
                prepared_amount=float(item["prepared_amount"]),
                annual_cost_growth_rate=float(item["annual_cost_growth_rate"]),
                can_defer=bool(item["can_defer"]),
            )
            for item in goals
        ),
        asset_buckets={str(key): float(value) for key, value in buckets.items()},
        monthly_expenses=float(str(payload["monthly_expenses"])),
        monthly_essential_expenses=float(str(payload["monthly_essential_expenses"])),
        monthly_compressible_expenses=float(str(payload["monthly_compressible_expenses"])),
        medical_coverage=float(str(payload["medical_coverage"])),
        medical_deductible=float(str(payload["medical_deductible"])),
        pension_monthly_contributions=float(str(payload["pension_monthly_contributions"])),
        source_record_ids=tuple(str(value) for value in source_ids_raw),
    )
