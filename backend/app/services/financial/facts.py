from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.financial import (
    AssetFact,
    BehaviorAssessmentFact,
    ExpenseFact,
    GoalFact,
    HouseholdFacts,
    IncomeFact,
    InsuranceFact,
    LiabilityFact,
    MemberFact,
    ResponsibilityFact,
    RiskAssessmentFact,
    SocialSecurityFact,
)
from app.models.assessment import BehaviorAssessment, RiskAssessment
from app.models.common import RecordMixin
from app.models.family import HouseholdMember
from app.models.finance import (
    Asset,
    ExpenseItem,
    FinancialGoal,
    IncomeSource,
    InsurancePolicy,
    Liability,
    Responsibility,
    SocialSecurityAccount,
)
from app.services.crud import ensure_household


def _active_records[ModelT: RecordMixin](
    session: Session,
    model: type[ModelT],
    household_id: str,
) -> tuple[ModelT, ...]:
    statement = (
        select(model)
        .where(
            cast(Any, model).household_id == household_id,
            model.is_deleted.is_(False),
        )
        .order_by(model.created_at, model.id)
    )
    return tuple(session.scalars(statement).all())


def load_household_facts(session: Session, household_id: str) -> HouseholdFacts:
    household = ensure_household(session, household_id)
    members = _active_records(session, HouseholdMember, household_id)
    incomes = _active_records(session, IncomeSource, household_id)
    expenses = _active_records(session, ExpenseItem, household_id)
    assets = _active_records(session, Asset, household_id)
    liabilities = _active_records(session, Liability, household_id)
    policies = _active_records(session, InsurancePolicy, household_id)
    social_accounts = _active_records(session, SocialSecurityAccount, household_id)
    goals = _active_records(session, FinancialGoal, household_id)
    responsibilities = _active_records(session, Responsibility, household_id)
    risk_assessments = _active_records(session, RiskAssessment, household_id)
    behavior_assessments = _active_records(session, BehaviorAssessment, household_id)

    return HouseholdFacts(
        id=household.id,
        code=household.code,
        name=household.name,
        lifecycle_stage=household.lifecycle_stage,
        region=household.region,
        currency=household.currency,
        data_source=household.data_source,
        is_user_confirmed=household.is_user_confirmed,
        is_synthetic=household.is_synthetic,
        version=household.version,
        planning_preferences=dict(household.planning_preferences or {}),
        members=tuple(
            MemberFact(
                id=item.id,
                display_name=item.display_name,
                relationship=item.relationship,
                birth_date=item.birth_date,
                occupation=item.occupation,
                employment_stability=item.employment_stability,
                expected_retirement_age=item.expected_retirement_age,
                health_risk_level=item.health_risk_level,
                version=item.version,
            )
            for item in members
        ),
        incomes=tuple(
            IncomeFact(
                id=item.id,
                member_id=item.member_id,
                name=item.name,
                income_type=item.income_type,
                amount=item.amount,
                frequency=item.frequency,
                stability=item.stability,
                volatility=item.volatility,
                interruption_probability=item.interruption_probability,
                cycle_correlation=item.cycle_correlation,
                source_concentration=item.source_concentration,
                is_sustainable=item.is_sustainable,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in incomes
        ),
        expenses=tuple(
            ExpenseFact(
                id=item.id,
                member_id=item.member_id,
                name=item.name,
                amount=item.amount,
                frequency=item.frequency,
                necessity=item.necessity,
                compressible_ratio=item.compressible_ratio,
                category=item.category,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in expenses
        ),
        assets=tuple(
            AssetFact(
                id=item.id,
                owner_member_id=item.owner_member_id,
                name=item.name,
                category=item.category,
                subcategory=item.subcategory,
                acquisition_cost=item.acquisition_cost,
                market_value=item.market_value,
                liquidity_days=item.liquidity_days,
                liquidity_level=item.liquidity_level,
                risk_level=item.risk_level,
                purpose=item.purpose,
                pledged=item.pledged,
                property_use=item.property_use,
                purpose_dimension=item.purpose_dimension,
                account_wrapper=item.account_wrapper,
                principal_loss_possible=item.principal_loss_possible,
                legally_principal_guaranteed=item.legally_principal_guaranteed,
                lock_up=item.lock_up,
                withdrawable_date=item.withdrawable_date,
                volatility=item.volatility,
                product_complexity=item.product_complexity,
                institution_type=item.institution_type,
                source_kind=item.source_kind,
                household_role=item.household_role,
                region_code=item.region_code,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in assets
        ),
        liabilities=tuple(
            LiabilityFact(
                id=item.id,
                name=item.name,
                category=item.category,
                outstanding_balance=item.outstanding_balance,
                annual_interest_rate=item.annual_interest_rate,
                monthly_payment=item.monthly_payment,
                maturity_date=item.maturity_date,
                rate_type=item.rate_type,
                prepayment_cost=item.prepayment_cost,
                linked_asset_id=item.linked_asset_id,
                is_high_interest=item.is_high_interest,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in liabilities
        ),
        insurance_policies=tuple(
            InsuranceFact(
                id=item.id,
                insured_member_id=item.insured_member_id,
                name=item.name,
                policy_type=item.policy_type,
                coverage_amount=item.coverage_amount,
                annual_premium=item.annual_premium,
                start_date=item.start_date,
                end_date=item.end_date,
                deductible=item.deductible,
                waiting_period_days=item.waiting_period_days,
                guaranteed_benefit=item.guaranteed_benefit,
                non_guaranteed_benefit=item.non_guaranteed_benefit,
                cash_value=item.cash_value,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in policies
        ),
        social_security_accounts=tuple(
            SocialSecurityFact(
                id=item.id,
                member_id=item.member_id,
                account_type=item.account_type,
                balance=item.balance,
                annual_personal_contribution=item.annual_personal_contribution,
                annual_employer_contribution=item.annual_employer_contribution,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in social_accounts
        ),
        goals=tuple(
            GoalFact(
                id=item.id,
                name=item.name,
                goal_type=item.goal_type,
                target_amount=item.target_amount,
                target_date=item.target_date,
                rigidity=item.rigidity,
                priority=item.priority,
                can_defer=item.can_defer,
                minimum_acceptable_amount=item.minimum_acceptable_amount,
                prepared_amount=item.prepared_amount,
                annual_cost_growth_rate=item.annual_cost_growth_rate,
                valuation_date=item.valuation_date,
                version=item.version,
            )
            for item in goals
        ),
        responsibilities=tuple(
            ResponsibilityFact(
                id=item.id,
                responsible_member_id=item.responsible_member_id,
                beneficiary=item.beneficiary,
                responsibility_type=item.responsibility_type,
                target_amount=item.target_amount,
                minimum_acceptable_amount=item.minimum_acceptable_amount,
                target_date=item.target_date,
                rigidity=item.rigidity,
                deferrable=item.deferrable,
                annual_growth_assumption=item.annual_growth_assumption,
                prepared_amount=item.prepared_amount,
                institutional_coverage=item.institutional_coverage,
                funding_source=item.funding_source,
                source_goal_id=item.source_goal_id,
                version=item.version,
            )
            for item in responsibilities
        ),
        risk_assessments=tuple(
            RiskAssessmentFact(
                id=item.id,
                capacity_score=item.capacity_score,
                willingness_score=item.willingness_score,
                knowledge_score=item.knowledge_score,
                behavior_score=item.behavior_score,
                final_risk_limit=item.final_risk_limit,
                version=item.version,
            )
            for item in risk_assessments
        ),
        behavior_assessments=tuple(
            BehaviorAssessmentFact(
                id=item.id,
                questionnaire_score=item.questionnaire_score,
                experiment_score=item.experiment_score,
                final_behavior_limit=item.final_behavior_limit,
                detected_biases=tuple(item.detected_biases),
                version=item.version,
            )
            for item in behavior_assessments
        ),
    )
