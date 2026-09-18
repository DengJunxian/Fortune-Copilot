from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AssetCategory,
    AuditEventType,
    ClientProfileStatus,
    ComplexityBand,
    ExpenseNecessity,
    GoalRigidity,
    GoalType,
    InsuranceType,
    WealthNeedStatus,
    WealthNeedType,
)
from app.domain.financial import HouseholdFacts
from app.models.client_profile import (
    ClientWealthProfile,
    WealthNeed,
    WealthNeedPriority,
)
from app.schemas.client_profile import (
    WealthNeedDraft,
    WealthNeedOut,
    WealthNeedPriorityOut,
    WealthNeedsMeta,
    WealthNeedsResponse,
)
from app.services.client_profile.engine import recalculate_client_profile
from app.services.client_profile.rules import (
    ClientProfileRules,
    load_client_profile_rules,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.financial.facts import load_household_facts
from app.services.financial_graph.repository import (
    FinancialGraphRecords,
    household_entity,
    load_financial_graph,
)

_NEED_LOCKS = tuple(Lock() for _ in range(64))
_ANNUAL_MULTIPLIERS = {
    "monthly": Decimal("12"),
    "quarterly": Decimal("4"),
    "annual": Decimal("1"),
    "one_time": Decimal("1"),
    "irregular": Decimal("1"),
}


def _annual_amount(amount: Decimal, frequency: object) -> Decimal:
    raw = getattr(frequency, "value", str(frequency))
    return amount * _ANNUAL_MULTIPLIERS.get(str(raw), Decimal("1"))


def _status(
    target: Decimal,
    prepared: Decimal,
    *,
    review_required: bool = False,
) -> WealthNeedStatus:
    if review_required:
        return WealthNeedStatus.NEEDS_REVIEW
    if target <= 0 or prepared >= target:
        return WealthNeedStatus.PREPARED
    if prepared > 0:
        return WealthNeedStatus.PARTIALLY_PREPARED
    return WealthNeedStatus.IDENTIFIED


def _decimal_preference(value: object) -> Decimal | None:
    if isinstance(value, (str, int, Decimal)) and not isinstance(value, bool):
        try:
            parsed = Decimal(str(value))
            return parsed if parsed >= 0 else None
        except InvalidOperation:
            return None
    return None


def _need(
    rules: ClientProfileRules,
    need_type: WealthNeedType,
    *,
    target: Decimal,
    minimum: Decimal,
    prepared: Decimal,
    currency: str,
    analysis_date: date,
    end_date: date | None,
    rigidity: GoalRigidity,
    source_kind: str,
    source_record_ids: list[str],
    evidence: dict[str, object],
    beneficiary_entity_id: str | None,
    confidence: Decimal = Decimal("0.90"),
    review_required: bool | None = None,
) -> WealthNeedDraft:
    needs_rules = rules.needs
    professional_review = (
        need_type in needs_rules.professional_review_need_types
        if review_required is None
        else review_required
    )
    hard_constraint = need_type in needs_rules.hard_constraint_need_types or (
        rigidity == GoalRigidity.RIGID
    )
    score = needs_rules.priority_scores[need_type]
    reason = "家庭安全与刚性责任优先" if hard_constraint else "按目标期限、责任刚性与资料置信度排序"
    return WealthNeedDraft(
        need_type=need_type,
        beneficiary_entity_id=beneficiary_entity_id,
        target_amount=target.quantize(Decimal("0.01")),
        minimum_amount=min(minimum, target).quantize(Decimal("0.01")),
        currency=currency,
        start_date=analysis_date,
        end_date=end_date,
        rigidity=rigidity,
        priority=1,
        status=_status(target, prepared, review_required=professional_review),
        confidence=confidence,
        professional_review_required=professional_review,
        source_kind=source_kind,
        source_record_ids=source_record_ids,
        evidence={
            **evidence,
            "prepared_amount": str(prepared.quantize(Decimal("0.01"))),
            "calculation_rule": reason,
        },
        hard_constraint=hard_constraint,
        priority_score=score,
        priority_reason=reason,
    )


def derive_wealth_needs(
    facts: HouseholdFacts,
    graph: FinancialGraphRecords,
    profile: ClientWealthProfile,
    rules: ClientProfileRules,
    analysis_date: date,
) -> list[WealthNeedDraft]:
    currency = facts.currency
    household_beneficiary = household_entity(graph).id
    positions = tuple(graph.positions)
    essential_annual_expense = sum(
        (
            _annual_amount(item.amount, item.frequency)
            for item in facts.expenses
            if item.necessity == ExpenseNecessity.ESSENTIAL
        ),
        Decimal("0.00"),
    )
    essential_monthly = essential_annual_expense / Decimal("12")
    immediately_available = sum(
        (item.market_value for item in positions if item.liquidity_days <= 1),
        Decimal("0.00"),
    )
    emergency_available = sum(
        (item.market_value for item in positions if item.liquidity_days <= 30),
        Decimal("0.00"),
    )
    needs: list[WealthNeedDraft] = []
    liquidity_target = essential_monthly * Decimal(rules.needs.liquidity_months)
    needs.append(
        _need(
            rules,
            WealthNeedType.LIQUIDITY,
            target=liquidity_target,
            minimum=liquidity_target,
            prepared=immediately_available,
            currency=currency,
            analysis_date=analysis_date,
            end_date=analysis_date + timedelta(days=30),
            rigidity=GoalRigidity.RIGID,
            source_kind="expense_derived",
            source_record_ids=[item.id for item in facts.expenses],
            evidence={"essential_monthly_expense": str(essential_monthly)},
            beneficiary_entity_id=household_beneficiary,
            confidence=Decimal("0.95") if facts.expenses else Decimal("0.55"),
        )
    )

    emergency_goal = next(
        (item for item in facts.goals if item.goal_type == GoalType.EMERGENCY_FUND),
        None,
    )
    emergency_target = (
        emergency_goal.target_amount
        if emergency_goal
        else essential_monthly * Decimal(rules.needs.emergency_months)
    )
    emergency_minimum = (
        emergency_goal.minimum_acceptable_amount if emergency_goal else emergency_target
    )
    emergency_prepared = emergency_goal.prepared_amount if emergency_goal else emergency_available
    needs.append(
        _need(
            rules,
            WealthNeedType.EMERGENCY,
            target=emergency_target,
            minimum=emergency_minimum,
            prepared=emergency_prepared,
            currency=currency,
            analysis_date=analysis_date,
            end_date=emergency_goal.target_date
            if emergency_goal
            else analysis_date + timedelta(days=365),
            rigidity=emergency_goal.rigidity if emergency_goal else GoalRigidity.RIGID,
            source_kind="goal" if emergency_goal else "expense_derived",
            source_record_ids=[emergency_goal.id]
            if emergency_goal
            else [item.id for item in facts.expenses],
            evidence={"liquid_assets_within_30_days": str(emergency_available)},
            beneficiary_entity_id=household_beneficiary,
            confidence=Decimal("0.98") if emergency_goal else Decimal("0.80"),
        )
    )

    debt_balance = sum((item.outstanding_balance for item in facts.liabilities), Decimal("0.00"))
    if debt_balance > 0:
        high_interest = sum(
            (item.outstanding_balance for item in facts.liabilities if item.is_high_interest),
            Decimal("0.00"),
        )
        needs.append(
            _need(
                rules,
                WealthNeedType.DEBT_REPAYMENT,
                target=debt_balance,
                minimum=high_interest,
                prepared=Decimal("0.00"),
                currency=currency,
                analysis_date=analysis_date,
                end_date=min(
                    (item.maturity_date for item in facts.liabilities if item.maturity_date),
                    default=None,
                ),
                rigidity=GoalRigidity.RIGID,
                source_kind="liability",
                source_record_ids=[item.id for item in facts.liabilities],
                evidence={"high_interest_balance": str(high_interest)},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.98"),
            )
        )

    medical_goal = next(
        (item for item in facts.goals if item.goal_type == GoalType.MEDICAL),
        None,
    )
    medical_rule_target = rules.needs.medical_minimum_per_member * Decimal(
        max(1, len(facts.members))
    )
    medical_target = max(
        medical_rule_target,
        medical_goal.target_amount if medical_goal else Decimal("0.00"),
    )
    medical_coverage = sum(
        (
            item.coverage_amount
            for item in facts.insurance_policies
            if item.policy_type in {InsuranceType.MEDICAL, InsuranceType.CRITICAL_ILLNESS}
        ),
        Decimal("0.00"),
    )
    needs.append(
        _need(
            rules,
            WealthNeedType.MEDICAL_PROTECTION,
            target=medical_target,
            minimum=medical_rule_target,
            prepared=medical_coverage + (medical_goal.prepared_amount if medical_goal else 0),
            currency=currency,
            analysis_date=analysis_date,
            end_date=medical_goal.target_date if medical_goal else None,
            rigidity=GoalRigidity.RIGID,
            source_kind="protection_and_goal",
            source_record_ids=[
                *(item.id for item in facts.insurance_policies),
                *([medical_goal.id] if medical_goal else []),
            ],
            evidence={"medical_coverage": str(medical_coverage)},
            beneficiary_entity_id=household_beneficiary,
            confidence=Decimal("0.90"),
        )
    )

    annual_income = sum(
        (_annual_amount(item.amount, item.frequency) for item in facts.incomes),
        Decimal("0.00"),
    )
    dependents = [
        item for item in facts.members if item.relationship in {"子女", "父母", "child", "parent"}
    ]
    if annual_income > 0 and (dependents or facts.responsibilities):
        death_target = annual_income * Decimal(rules.needs.death_income_replacement_years)
        death_coverage = sum(
            (
                item.coverage_amount
                for item in facts.insurance_policies
                if item.policy_type in {InsuranceType.TERM_LIFE, InsuranceType.WHOLE_LIFE}
            ),
            Decimal("0.00"),
        )
        needs.append(
            _need(
                rules,
                WealthNeedType.DEATH_PROTECTION,
                target=death_target,
                minimum=death_target,
                prepared=death_coverage,
                currency=currency,
                analysis_date=analysis_date,
                end_date=None,
                rigidity=GoalRigidity.RIGID,
                source_kind="income_replacement",
                source_record_ids=[
                    *(item.id for item in facts.incomes),
                    *(item.id for item in facts.insurance_policies),
                    *(item.id for item in facts.responsibilities),
                ],
                evidence={
                    "death_coverage": str(death_coverage),
                    "dependent_count": len(dependents),
                },
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.90"),
            )
        )

    goal_need_types = {
        GoalType.EDUCATION: WealthNeedType.EDUCATION,
        GoalType.HOME: WealthNeedType.HOUSING,
        GoalType.RETIREMENT: WealthNeedType.RETIREMENT,
    }
    for goal in facts.goals:
        need_type = goal_need_types.get(goal.goal_type)
        if need_type is None:
            continue
        needs.append(
            _need(
                rules,
                need_type,
                target=goal.target_amount,
                minimum=goal.minimum_acceptable_amount,
                prepared=goal.prepared_amount,
                currency=currency,
                analysis_date=analysis_date,
                end_date=goal.target_date,
                rigidity=goal.rigidity,
                source_kind="goal",
                source_record_ids=[goal.id],
                evidence={"goal_name": goal.name, "goal_priority": goal.priority},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.98"),
            )
        )

    long_term_goals = [
        item for item in facts.goals if item.target_date > analysis_date + timedelta(days=365 * 5)
    ]
    growth_gap = sum(
        (
            max(Decimal("0.00"), item.target_amount - item.prepared_amount)
            for item in long_term_goals
        ),
        Decimal("0.00"),
    )
    growth_assets = sum(
        (item.market_value for item in positions if item.purpose_dimension.value == "growth"),
        Decimal("0.00"),
    )
    if long_term_goals or growth_assets > 0:
        growth_target = max(growth_gap, rules.needs.long_term_growth_minimum)
        needs.append(
            _need(
                rules,
                WealthNeedType.LONG_TERM_GROWTH,
                target=growth_target,
                minimum=Decimal("0.00"),
                prepared=growth_assets,
                currency=currency,
                analysis_date=analysis_date,
                end_date=max((item.target_date for item in long_term_goals), default=None),
                rigidity=GoalRigidity.FLEXIBLE,
                source_kind="long_term_goal_gap",
                source_record_ids=[
                    *(item.id for item in long_term_goals),
                    *(item.id for item in positions if item.purpose_dimension.value == "growth"),
                ],
                evidence={
                    "long_term_goal_gap": str(growth_gap),
                    "growth_assets": str(growth_assets),
                },
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.88"),
            )
        )

    total_assets = sum((item.market_value for item in positions), Decimal("0.00"))
    total_liabilities = sum(
        (item.outstanding_balance for item in facts.liabilities), Decimal("0.00")
    )
    net_worth = total_assets - total_liabilities
    enterprise_positions = [
        item
        for item in positions
        if bool((item.evidence_json or {}).get("enterprise_related"))
        or item.instrument_type == AssetCategory.STOCK
    ]
    enterprise_amount = sum((item.market_value for item in enterprise_positions), Decimal("0.00"))
    if profile.enterprise_dependency_level != ComplexityBand.NONE:
        needs.append(
            _need(
                rules,
                WealthNeedType.ENTERPRISE_CONCENTRATION,
                target=enterprise_amount,
                minimum=Decimal("0.00"),
                prepared=Decimal("0.00"),
                currency=currency,
                analysis_date=analysis_date,
                end_date=None,
                rigidity=GoalRigidity.IMPORTANT,
                source_kind="profile_tag",
                source_record_ids=[item.id for item in enterprise_positions],
                evidence={"enterprise_dependency": profile.enterprise_dependency_level.value},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.80"),
            )
        )

    foreign_positions = [
        item for item in positions if item.currency != currency and item.market_value > 0
    ]
    if profile.cross_border_complexity != ComplexityBand.NONE:
        foreign_amount = sum((item.market_value for item in foreign_positions), Decimal("0.00"))
        needs.append(
            _need(
                rules,
                WealthNeedType.CURRENCY_MATCHING,
                target=foreign_amount,
                minimum=Decimal("0.00"),
                prepared=Decimal("0.00"),
                currency=currency,
                analysis_date=analysis_date,
                end_date=None,
                rigidity=GoalRigidity.IMPORTANT,
                source_kind="currency_exposure",
                source_record_ids=[item.id for item in foreign_positions],
                evidence={"currencies": sorted({item.currency for item in positions})},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.85"),
            )
        )

    transfer_goals = [item for item in facts.goals if item.goal_type == GoalType.WEALTH_TRANSFER]
    if profile.succession_complexity != ComplexityBand.NONE or transfer_goals:
        succession_target = sum(
            (item.target_amount for item in transfer_goals),
            net_worth if not transfer_goals else Decimal("0.00"),
        )
        succession_minimum = sum(
            (item.minimum_acceptable_amount for item in transfer_goals), Decimal("0.00")
        )
        succession_prepared = sum(
            (item.prepared_amount for item in transfer_goals), Decimal("0.00")
        )
        needs.append(
            _need(
                rules,
                WealthNeedType.SUCCESSION,
                target=max(Decimal("0.00"), succession_target),
                minimum=succession_minimum,
                prepared=succession_prepared,
                currency=currency,
                analysis_date=analysis_date,
                end_date=max((item.target_date for item in transfer_goals), default=None),
                rigidity=GoalRigidity.IMPORTANT,
                source_kind="succession_profile",
                source_record_ids=[item.id for item in transfer_goals],
                evidence={"succession_complexity": profile.succession_complexity.value},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.78") if transfer_goals else Decimal("0.60"),
            )
        )

    if net_worth >= rules.needs.trust_review_net_worth or bool(
        facts.planning_preferences.get("trust_review_requested")
    ):
        needs.append(
            _need(
                rules,
                WealthNeedType.TRUST,
                target=max(Decimal("0.00"), net_worth),
                minimum=Decimal("0.00"),
                prepared=Decimal("0.00"),
                currency=currency,
                analysis_date=analysis_date,
                end_date=None,
                rigidity=GoalRigidity.FLEXIBLE,
                source_kind="review_trigger",
                source_record_ids=[facts.id],
                evidence={"review_trigger": "net_worth_or_explicit_request"},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.65"),
            )
        )

    philanthropy_target = _decimal_preference(
        facts.planning_preferences.get("philanthropy_target_amount")
    )
    if philanthropy_target is not None and philanthropy_target > 0:
        needs.append(
            _need(
                rules,
                WealthNeedType.PHILANTHROPY,
                target=philanthropy_target,
                minimum=Decimal("0.00"),
                prepared=Decimal("0.00"),
                currency=currency,
                analysis_date=analysis_date,
                end_date=None,
                rigidity=GoalRigidity.FLEXIBLE,
                source_kind="client_preference",
                source_record_ids=[facts.id],
                evidence={"explicit_preference": True},
                beneficiary_entity_id=household_beneficiary,
                confidence=Decimal("0.80"),
            )
        )

    ordered = sorted(
        needs,
        key=lambda item: (
            not item.hard_constraint,
            -item.priority_score,
            item.end_date or date.max,
            item.need_type.value,
        ),
    )
    return [item.model_copy(update={"priority": rank}) for rank, item in enumerate(ordered, 1)]


def _latest_profile(session: Session, household_id: str) -> ClientWealthProfile | None:
    return session.scalar(
        select(ClientWealthProfile)
        .where(
            ClientWealthProfile.household_id == household_id,
            ClientWealthProfile.status.in_(
                [ClientProfileStatus.ACTIVE, ClientProfileStatus.NEEDS_REVIEW]
            ),
            ClientWealthProfile.is_deleted.is_(False),
        )
        .order_by(ClientWealthProfile.profile_version.desc())
    )


def _records(
    session: Session,
    household_id: str,
    profile_id: str,
) -> tuple[tuple[WealthNeed, ...], tuple[WealthNeedPriority, ...]]:
    needs = tuple(
        session.scalars(
            select(WealthNeed)
            .where(
                WealthNeed.household_id == household_id,
                WealthNeed.profile_id == profile_id,
                WealthNeed.is_deleted.is_(False),
            )
            .order_by(WealthNeed.priority, WealthNeed.created_at, WealthNeed.id)
        ).all()
    )
    need_ids = [item.id for item in needs]
    priorities = (
        tuple(
            session.scalars(
                select(WealthNeedPriority)
                .where(
                    WealthNeedPriority.household_id == household_id,
                    WealthNeedPriority.wealth_need_id.in_(need_ids),
                    WealthNeedPriority.is_deleted.is_(False),
                )
                .order_by(WealthNeedPriority.priority_rank)
            ).all()
        )
        if need_ids
        else ()
    )
    return needs, priorities


def _response(
    profile: ClientWealthProfile,
    needs: tuple[WealthNeed, ...],
    priorities: tuple[WealthNeedPriority, ...],
) -> WealthNeedsResponse:
    return WealthNeedsResponse(
        meta=WealthNeedsMeta(
            household_id=profile.household_id,
            profile_id=profile.id,
            profile_hash=profile.profile_hash,
            analysis_date=profile.valuation_date or date.today(),
            data_as_of=profile.valuation_date,
            rule_version=profile.rule_version,
            formula_version=profile.formula_version,
            professional_review_count=sum(1 for item in needs if item.professional_review_required),
        ),
        needs=[WealthNeedOut.model_validate(item) for item in needs],
        priorities=[WealthNeedPriorityOut.model_validate(item) for item in priorities],
    )


def get_wealth_needs(session: Session, household_id: str) -> WealthNeedsResponse:
    profile = _latest_profile(session, household_id)
    if profile is None:
        ensure_household(session, household_id)
        raise AppError(
            "client_profile_not_calculated",
            "请先计算客户财富画像",
            status_code=404,
        )
    needs, priorities = _records(session, household_id, profile.id)
    if not needs:
        raise AppError(
            "wealth_needs_not_calculated",
            "财富需求尚未计算",
            status_code=404,
        )
    return _response(profile, needs, priorities)


def recalculate_wealth_needs(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> WealthNeedsResponse:
    recalculate_client_profile(
        session,
        household_id,
        actor,
        rules_path,
        analysis_date,
    )
    need_lock = _NEED_LOCKS[hash(household_id) % len(_NEED_LOCKS)]
    with need_lock:
        profile = _latest_profile(session, household_id)
        if profile is None:
            raise AppError(
                "client_profile_not_calculated",
                "客户财富画像尚未计算",
                status_code=404,
            )
        existing_needs, existing_priorities = _records(session, household_id, profile.id)
        if existing_needs:
            return _response(profile, existing_needs, existing_priorities)

        household = ensure_household(session, household_id)
        facts = load_household_facts(session, household_id)
        graph = load_financial_graph(session, household_id)
        rules = load_client_profile_rules(rules_path)
        drafts = derive_wealth_needs(facts, graph, profile, rules, analysis_date)
        for draft in drafts:
            values = draft.model_dump(
                mode="python",
                exclude={
                    "hard_constraint",
                    "priority_score",
                    "priority_reason",
                },
            )
            need = WealthNeed(
                household_id=household_id,
                profile_id=profile.id,
                **values,
                valuation_date=analysis_date,
                data_source="v5_wealth_need_engine",
                is_user_confirmed=household.is_user_confirmed,
            )
            session.add(need)
            session.flush()
            add_audit_event(
                session,
                need,
                actor,
                AuditEventType.CALCULATION_EXECUTED,
                f"识别财富需求 {need.need_type.value}",
            )
            priority = WealthNeedPriority(
                household_id=household_id,
                wealth_need_id=need.id,
                priority_rank=draft.priority,
                hard_constraint=draft.hard_constraint,
                priority_score=draft.priority_score,
                reason=draft.priority_reason,
                rule_version=rules.semantic_version,
                currency=facts.currency,
                valuation_date=analysis_date,
                data_source="v5_wealth_need_priority_engine",
                is_user_confirmed=household.is_user_confirmed,
            )
            session.add(priority)
            session.flush()
            add_audit_event(
                session,
                priority,
                actor,
                AuditEventType.RULE_APPLIED,
                f"排列财富需求优先级 {draft.priority}",
            )
        session.commit()
        return _response(profile, *_records(session, household_id, profile.id))
