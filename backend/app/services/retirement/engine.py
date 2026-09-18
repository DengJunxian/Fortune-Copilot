from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import (
    AssetCategory,
    AuditEventType,
    CFSComponentType,
    ExpenseCategory,
    GoalType,
    IncomeType,
    InstitutionalEntitlementType,
    InsuranceType,
    ProfessionalSpecialistType,
    SpecializedComplexity,
)
from app.models.family import Household, HouseholdMember
from app.models.finance import (
    Asset,
    ExpenseItem,
    FinancialGoal,
    IncomeSource,
    InsurancePolicy,
    SocialSecurityAccount,
)
from app.models.specialized_cfs import InstitutionalEntitlement
from app.schemas.specialized_cfs import (
    InstitutionalEntitlementOut,
    RetirementGapOutput,
    RetirementLiabilityBreakdown,
    RetirementPlanResponse,
    SpecializedResponseMeta,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.professional_routing.engine import resolve_professional_route
from app.services.specialized_cfs.common import (
    ZERO,
    add_years,
    age_on,
    annualize,
    canonical_hash,
    money,
)
from app.services.specialized_cfs.rules import load_specialized_cfs_rules

BOUNDARY = "退休测算用于识别收入底线与缺口，不承诺养老金待遇、投资收益或长寿风险结果。"


def _entitlement_type(income: IncomeSource) -> InstitutionalEntitlementType:
    if income.income_type == IncomeType.RENTAL:
        return InstitutionalEntitlementType.RENTAL
    if "企业年金" in income.name:
        return InstitutionalEntitlementType.ENTERPRISE_PENSION
    if "个人养老金" in income.name:
        return InstitutionalEntitlementType.PERSONAL_PENSION
    return InstitutionalEntitlementType.OCCUPATIONAL_PENSION


def _sync_entitlements(
    session: Session,
    household: Household,
    members: list[HouseholdMember],
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> list[InstitutionalEntitlement]:
    rules = load_specialized_cfs_rules(rules_path)
    primary_member_id = members[0].id if members else None
    retirement_by_member = {
        item.id: item.expected_retirement_age or 60 for item in members
    }
    birth_by_member = {item.id: item.birth_date for item in members}
    drafts: dict[tuple[str | None, InstitutionalEntitlementType, str], dict[str, Any]] = {}

    social_by_member: dict[str, list[SocialSecurityAccount]] = defaultdict(list)
    for account in session.scalars(
        select(SocialSecurityAccount).where(
            SocialSecurityAccount.household_id == household.id,
            SocialSecurityAccount.is_deleted.is_(False),
        )
    ).all():
        social_by_member[account.member_id].append(account)
    for social_member_id, accounts in social_by_member.items():
        start_age = retirement_by_member.get(social_member_id, 60)
        birth_date = birth_by_member.get(social_member_id)
        drafts[
            (
                social_member_id,
                InstitutionalEntitlementType.SOCIAL_SECURITY,
                "social_security",
            )
        ] = {
            "member_id": social_member_id,
            "entitlement_type": InstitutionalEntitlementType.SOCIAL_SECURITY,
            "balance": money(sum((item.balance for item in accounts), ZERO)),
            "expected_income": money(
                sum(
                    (
                        item.annual_personal_contribution + item.annual_employer_contribution
                        for item in accounts
                    ),
                    ZERO,
                )
                * rules.retirement.social_security_income_factor
            ),
            "start_age": start_age,
            "start_date": add_years(birth_date, start_age) if birth_date else None,
            "end_date": None,
            "guaranteed": True,
            "indexed": True,
            "lock_up": True,
            "source_kind": "social_security",
            "confidence": Decimal("0.70"),
            "evidence": {
                "source_record_ids": [item.id for item in accounts],
                "benefit_regions": sorted({item.benefit_region for item in accounts}),
                "estimate_only": True,
            },
        }

    incomes = list(
        session.scalars(
            select(IncomeSource).where(
                IncomeSource.household_id == household.id,
                IncomeSource.income_type.in_([IncomeType.PENSION, IncomeType.RENTAL]),
                IncomeSource.is_deleted.is_(False),
            )
        ).all()
    )
    income_groups: dict[tuple[str | None, InstitutionalEntitlementType], list[IncomeSource]] = (
        defaultdict(list)
    )
    for income in incomes:
        income_groups[(income.member_id or primary_member_id, _entitlement_type(income))].append(
            income
        )
    for (income_member_id, entitlement_type), income_items in income_groups.items():
        start_age = retirement_by_member.get(income_member_id or "", 60)
        birth_date = birth_by_member.get(income_member_id or "")
        source_kind = f"income_{entitlement_type.value}"
        drafts[(income_member_id, entitlement_type, source_kind)] = {
            "member_id": income_member_id,
            "entitlement_type": entitlement_type,
            "balance": ZERO,
            "expected_income": money(
                sum((annualize(item.amount, item.frequency) for item in income_items), ZERO)
            ),
            "start_age": (
                start_age if entitlement_type != InstitutionalEntitlementType.RENTAL else None
            ),
            "start_date": (
                add_years(birth_date, start_age)
                if birth_date and entitlement_type != InstitutionalEntitlementType.RENTAL
                else analysis_date
            ),
            "end_date": None,
            "guaranteed": entitlement_type != InstitutionalEntitlementType.RENTAL,
            "indexed": False,
            "lock_up": False,
            "source_kind": source_kind,
            "confidence": Decimal("0.85"),
            "evidence": {"source_record_ids": [item.id for item in income_items]},
        }

    pension_assets = list(
        session.scalars(
            select(Asset).where(
                Asset.household_id == household.id,
                Asset.category == AssetCategory.PENSION_ACCOUNT,
                Asset.is_deleted.is_(False),
            )
        ).all()
    )
    assets_by_member: dict[str | None, list[Asset]] = defaultdict(list)
    for asset in pension_assets:
        assets_by_member[asset.owner_member_id or primary_member_id].append(asset)
    for asset_member_id, asset_items in assets_by_member.items():
        start_age = retirement_by_member.get(asset_member_id or "", 60)
        birth_date = birth_by_member.get(asset_member_id or "")
        balance = money(sum((item.market_value for item in asset_items), ZERO))
        drafts[
            (
                asset_member_id,
                InstitutionalEntitlementType.PERSONAL_PENSION,
                "pension_asset",
            )
        ] = {
            "member_id": asset_member_id,
            "entitlement_type": InstitutionalEntitlementType.PERSONAL_PENSION,
            "balance": balance,
            "expected_income": money(balance * rules.retirement.financial_withdrawal_rate),
            "start_age": start_age,
            "start_date": add_years(birth_date, start_age) if birth_date else None,
            "end_date": None,
            "guaranteed": False,
            "indexed": False,
            "lock_up": True,
            "source_kind": "pension_asset",
            "confidence": Decimal("0.90"),
            "evidence": {"source_record_ids": [item.id for item in asset_items]},
        }

    annuities = list(
        session.scalars(
            select(InsurancePolicy).where(
                InsurancePolicy.household_id == household.id,
                InsurancePolicy.policy_type == InsuranceType.ANNUITY,
                InsurancePolicy.is_deleted.is_(False),
            )
        ).all()
    )
    annuities_by_member: dict[str, list[InsurancePolicy]] = defaultdict(list)
    for policy in annuities:
        annuities_by_member[policy.insured_member_id].append(policy)
    for annuity_member_id, policies in annuities_by_member.items():
        drafts[(annuity_member_id, InstitutionalEntitlementType.ANNUITY, "annuity_policy")] = {
            "member_id": annuity_member_id,
            "entitlement_type": InstitutionalEntitlementType.ANNUITY,
            "balance": money(sum((item.cash_value for item in policies), ZERO)),
            "expected_income": money(
                sum((item.guaranteed_benefit for item in policies), ZERO)
            ),
            "start_age": retirement_by_member.get(annuity_member_id, 60),
            "start_date": min((item.start_date for item in policies), default=None),
            "end_date": max(
                (item.end_date for item in policies if item.end_date),
                default=None,
            ),
            "guaranteed": True,
            "indexed": False,
            "lock_up": True,
            "source_kind": "annuity_policy",
            "confidence": Decimal("0.90"),
            "evidence": {"source_record_ids": [item.id for item in policies]},
        }

    financial_assets = list(
        session.scalars(
            select(Asset).where(
                Asset.household_id == household.id,
                Asset.category.not_in(
                    [
                        AssetCategory.PRIMARY_RESIDENCE,
                        AssetCategory.INVESTMENT_PROPERTY,
                        AssetCategory.VEHICLE,
                        AssetCategory.PENSION_ACCOUNT,
                    ]
                ),
                Asset.is_deleted.is_(False),
            )
        ).all()
    )
    if financial_assets and primary_member_id is not None:
        balance = money(sum((item.market_value for item in financial_assets), ZERO))
        drafts[
            (
                primary_member_id,
                InstitutionalEntitlementType.FINANCIAL_WITHDRAWAL,
                "financial_assets",
            )
        ] = {
            "member_id": primary_member_id,
            "entitlement_type": InstitutionalEntitlementType.FINANCIAL_WITHDRAWAL,
            "balance": balance,
            "expected_income": money(balance * rules.retirement.financial_withdrawal_rate),
            "start_age": retirement_by_member.get(primary_member_id, 60),
            "start_date": None,
            "end_date": None,
            "guaranteed": False,
            "indexed": False,
            "lock_up": False,
            "source_kind": "financial_assets",
            "confidence": Decimal("0.75"),
            "evidence": {
                "source_record_ids": [item.id for item in financial_assets],
                "withdrawal_rate": str(rules.retirement.financial_withdrawal_rate),
            },
        }

    existing = list(
        session.scalars(
            select(InstitutionalEntitlement).where(
                InstitutionalEntitlement.household_id == household.id
            )
        ).all()
    )
    by_key = {
        (item.member_id, item.entitlement_type, item.source_kind): item for item in existing
    }
    active_ids: set[str] = set()
    for key, values in drafts.items():
        record = by_key.get(key)
        if record is None:
            record = InstitutionalEntitlement(
                household_id=household.id,
                currency=household.currency,
                valuation_date=analysis_date,
                data_source="v5_retirement_engine",
                is_user_confirmed=False,
                **values,
            )
            session.add(record)
            session.flush()
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_CREATED,
                "归一化退休制度权益",
            )
        else:
            changed = any(getattr(record, name) != value for name, value in values.items())
            if changed or record.is_deleted:
                for name, value in values.items():
                    setattr(record, name, value)
                record.is_deleted = False
                record.deleted_at = None
                record.version += 1
                record.valuation_date = analysis_date
                add_audit_event(
                    session,
                    record,
                    actor,
                    AuditEventType.DATA_UPDATED,
                    "更新退休制度权益",
                )
        active_ids.add(record.id)
    for record in existing:
        if record.id not in active_ids and not record.is_deleted:
            record.is_deleted = True
            record.version += 1
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_UPDATED,
                "退休制度权益来源失效",
            )
    session.commit()
    return list(
        session.scalars(
            select(InstitutionalEntitlement)
            .where(
                InstitutionalEntitlement.household_id == household.id,
                InstitutionalEntitlement.is_deleted.is_(False),
            )
            .order_by(InstitutionalEntitlement.entitlement_type, InstitutionalEntitlement.id)
        ).all()
    )


def get_retirement_plan(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> RetirementPlanResponse:
    household = ensure_household(session, household_id)
    rules = load_specialized_cfs_rules(rules_path)
    members = list(
        session.scalars(
            select(HouseholdMember)
            .where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.is_deleted.is_(False),
            )
            .order_by(HouseholdMember.birth_date)
        ).all()
    )
    entitlements = _sync_entitlements(
        session,
        household,
        members,
        actor,
        rules_path,
        analysis_date,
    )
    expenses = list(
        session.scalars(
            select(ExpenseItem).where(
                ExpenseItem.household_id == household_id,
                ExpenseItem.is_deleted.is_(False),
            )
        ).all()
    )
    goals = list(
        session.scalars(
            select(FinancialGoal).where(
                FinancialGoal.household_id == household_id,
                FinancialGoal.goal_type == GoalType.RETIREMENT,
                FinancialGoal.is_deleted.is_(False),
            )
        ).all()
    )
    essential = money(
        sum(
            (
                annualize(item.amount, item.frequency)
                for item in expenses
                if item.necessity.value == "essential"
            ),
            ZERO,
        )
    )
    actual_medical = money(
        sum(
            (
                annualize(item.amount, item.frequency)
                for item in expenses
                if item.category == ExpenseCategory.MEDICAL
            ),
            ZERO,
        )
    )
    basic = money(essential * rules.retirement.basic_expense_replacement_ratio)
    medical = max(actual_medical, money(basic * rules.retirement.medical_expense_ratio))
    adults = sum(1 for item in members if age_on(item.birth_date, analysis_date) >= 18)
    long_term_care = money(
        rules.retirement.long_term_care_annual_per_adult * max(adults, 1)
    )
    retirement_dates = [
        add_years(item.birth_date, item.expected_retirement_age or 60) for item in members
    ]
    retirement_start = min(retirement_dates, default=None)
    earliest_age = min(
        (item.expected_retirement_age or 60 for item in members),
        default=60,
    )
    retirement_years = max(rules.retirement.longevity_age - earliest_age, 0)
    retirement_floor = money(basic + medical + long_term_care)
    guaranteed_income = money(
        sum((item.expected_income for item in entitlements if item.guaranteed), ZERO)
    )
    income_gap = max(ZERO, money(retirement_floor - guaranteed_income))
    longevity_gap = money(income_gap * retirement_years)
    available_balance = money(sum((item.balance for item in entitlements), ZERO))
    liquidity_gap = max(
        ZERO,
        money(income_gap * rules.retirement.liquidity_bridge_years - available_balance),
    )
    explicit_goal = money(sum((item.target_amount for item in goals), ZERO))
    improved_goal = max(explicit_goal, longevity_gap)
    years_to_retirement = (
        max((retirement_start - analysis_date).days // 365, 0)
        if retirement_start is not None
        else 99
    )
    has_retirement_need = (
        bool(goals) or years_to_retirement <= rules.retirement.near_retirement_years
    )
    complexity = (
        SpecializedComplexity.HIGH
        if income_gap > 0 and years_to_retirement <= rules.retirement.near_retirement_years
        else SpecializedComplexity.MEDIUM
        if has_retirement_need and income_gap > 0
        else SpecializedComplexity.LOW
        if has_retirement_need
        else SpecializedComplexity.NONE
    )
    route = resolve_professional_route(
        session,
        household_id,
        need="retirement",
        complexity=complexity,
        specialist_type=ProfessionalSpecialistType.PENSION_SPECIALIST,
        component_types={CFSComponentType.RETIREMENT},
        reason="退休收入底线、制度权益和长寿缺口需要在同一方案中复核。",
    )
    input_hash = canonical_hash(
        {
            "members": [(item.id, item.version, item.expected_retirement_age) for item in members],
            "expenses": [(item.id, item.version, str(item.amount)) for item in expenses],
            "goals": [(item.id, item.version, str(item.target_amount)) for item in goals],
            "entitlements": [
                (item.id, item.version, item.entitlement_type.value, str(item.expected_income))
                for item in entitlements
            ],
            "rules": rules.formula_version,
            "analysis_date": analysis_date.isoformat(),
        }
    )
    return RetirementPlanResponse(
        meta=SpecializedResponseMeta(
            household_id=household_id,
            analysis_date=analysis_date,
            data_as_of=max(
                (item.valuation_date for item in entitlements if item.valuation_date),
                default=None,
            ),
            input_hash=input_hash,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
        ),
        has_retirement_need=has_retirement_need,
        liabilities=RetirementLiabilityBreakdown(
            basic_retirement_liability=basic,
            medical_liability=medical,
            long_term_care_liability=long_term_care,
            improved_retirement_goal=improved_goal,
            retirement_start_date=retirement_start,
            retirement_years=retirement_years,
        ),
        entitlements=[InstitutionalEntitlementOut.model_validate(item) for item in entitlements],
        output=RetirementGapOutput(
            retirement_floor=retirement_floor,
            guaranteed_income=guaranteed_income,
            income_gap=income_gap,
            longevity_gap=longevity_gap,
            liquidity_gap=liquidity_gap,
        ),
        route=route,
        assumptions=[
            "退休收入底线按必要支出、医疗和长期照护责任拆分。",
            "制度养老金仅按已录入缴费推算，最终待遇以经办机构核定为准。",
            "金融提取额使用受控提取率作压力测算，不是收益承诺。",
        ],
        boundary=BOUNDARY,
    )
