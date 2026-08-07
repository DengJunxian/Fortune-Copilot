from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import AccountBucket, AuditEventType, RecommendationStatus
from app.domain.financial import HouseholdFacts
from app.models.assessment import AccountBucketPlan
from app.models.governance import ActionItem, AuditEvent, Recommendation
from app.schemas.planning import (
    AppliedCounterfactual,
    CounterfactualChange,
    CounterfactualRequest,
    CounterfactualResponse,
    PersistedPlanningRun,
    PlanningMeta,
    PlanningResponse,
    RatioMeasure,
)
from app.services.financial.engine import analyze_facts
from app.services.financial.facts import load_household_facts
from app.services.financial.rules import load_financial_rules
from app.services.financial.utils import ZERO, money
from app.services.planning.goals import build_goal_plan
from app.services.planning.lifecycle import assess_lifecycle
from app.services.planning.rules import (
    PlanningRules,
    ensure_planning_rule_version,
    load_planning_rules,
)
from app.services.planning.waterfall import build_waterfall


def empty_counterfactual() -> AppliedCounterfactual:
    return AppliedCounterfactual(
        emergency_fund_addition=ZERO,
        high_interest_debt_reduction=ZERO,
        protection_gap_reduction=ZERO,
        monthly_savings_increase=ZERO,
        goal_prepared_additions={},
        defer_goal_ids=[],
        defer_months=0,
        lifecycle_override=None,
    )


def _planning_input_version(
    facts: HouseholdFacts,
    analysis_date: date,
    adjustments: AppliedCounterfactual,
) -> str:
    canonical = json.dumps(
        {
            "analysis_date": analysis_date.isoformat(),
            "facts": asdict(facts),
            "counterfactual": adjustments.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_counterfactual(
    facts: HouseholdFacts,
    financial_protection_gap: Decimal,
    investable_categories: set[str],
    request: CounterfactualRequest,
) -> AppliedCounterfactual:
    goal_by_id = {goal.id: goal for goal in facts.goals}
    referenced_goal_ids = set(request.goal_prepared_additions) | set(request.defer_goal_ids)
    unknown_goal_ids = sorted(referenced_goal_ids - set(goal_by_id))
    if unknown_goal_ids:
        raise AppError(
            "planning_goal_not_found",
            "反事实方案引用了不存在的目标",
            status_code=422,
            details={"goal_ids": unknown_goal_ids},
        )
    non_deferable = sorted(
        goal_id for goal_id in request.defer_goal_ids if not goal_by_id[goal_id].can_defer
    )
    if non_deferable:
        raise AppError(
            "planning_goal_not_deferable",
            "所选目标不允许延期",
            status_code=422,
            details={"goal_ids": non_deferable},
        )
    high_interest_debt = money(
        sum(
            (
                liability.outstanding_balance
                for liability in facts.liabilities
                if liability.is_high_interest
            ),
            ZERO,
        )
    )
    if request.high_interest_debt_reduction > high_interest_debt:
        raise AppError(
            "planning_debt_reduction_too_large",
            "高息债务偿还额不能超过当前高息债务余额",
            status_code=422,
            details={"maximum": str(high_interest_debt)},
        )
    if request.protection_gap_reduction > financial_protection_gap:
        raise AppError(
            "planning_protection_reduction_too_large",
            "保障缺口改善额不能超过当前保障缺口",
            status_code=422,
            details={"maximum": str(financial_protection_gap)},
        )
    investable_assets = money(
        sum(
            (
                asset.market_value
                for asset in facts.assets
                if asset.category.value in investable_categories
            ),
            ZERO,
        )
    )
    reclassified_assets = money(
        request.emergency_fund_addition + sum(request.goal_prepared_additions.values(), ZERO)
    )
    if reclassified_assets > investable_assets:
        raise AppError(
            "planning_reclassification_too_large",
            "应急金与目标准备金调整合计不能超过当前可投资金融资产",
            status_code=422,
            details={"maximum": str(investable_assets)},
        )
    return AppliedCounterfactual(
        emergency_fund_addition=money(request.emergency_fund_addition),
        high_interest_debt_reduction=money(request.high_interest_debt_reduction),
        protection_gap_reduction=money(request.protection_gap_reduction),
        monthly_savings_increase=money(request.monthly_savings_increase),
        goal_prepared_additions={
            goal_id: money(amount) for goal_id, amount in request.goal_prepared_additions.items()
        },
        defer_goal_ids=sorted(set(request.defer_goal_ids)),
        defer_months=request.defer_months,
        lifecycle_override=request.lifecycle_override,
    )


def plan_facts(
    facts: HouseholdFacts,
    financial_rules_path: str,
    planning_rules: PlanningRules,
    analysis_date: date,
    adjustments: AppliedCounterfactual,
) -> PlanningResponse:
    financial_rules = load_financial_rules(financial_rules_path)
    financial = analyze_facts(facts, financial_rules, analysis_date)
    lifecycle = assess_lifecycle(
        facts,
        planning_rules,
        analysis_date,
        adjustments.lifecycle_override,
    )
    goals, conflicts = build_goal_plan(
        facts,
        planning_rules,
        analysis_date,
        financial.statements.cash_flow.annual_surplus,
        adjustments.goal_prepared_additions,
        set(adjustments.defer_goal_ids),
        adjustments.defer_months,
        adjustments.monthly_savings_increase,
    )
    (
        denominators,
        steps,
        constraints,
        accounts,
        investment_learning,
        growth_70,
        growth_benchmark,
        actions,
    ) = build_waterfall(
        facts,
        financial,
        financial_rules,
        planning_rules,
        lifecycle,
        goals,
        conflicts,
        adjustments,
    )
    return PlanningResponse(
        meta=PlanningMeta(
            household_id=facts.id,
            household_code=facts.code,
            analysis_date=analysis_date,
            data_as_of=financial.meta.data_as_of,
            input_version=_planning_input_version(facts, analysis_date, adjustments),
            formula_version=planning_rules.formula_version,
            rule_code=planning_rules.code,
            rule_version=planning_rules.semantic_version,
            currency=facts.currency,
            synthetic_data=facts.is_synthetic,
            scenario_type=("counterfactual" if adjustments != empty_counterfactual() else "base"),
        ),
        lifecycle=lifecycle,
        goals=goals,
        conflicts=conflicts,
        denominators=denominators,
        waterfall_steps=steps,
        constraints=constraints,
        accounts=accounts,
        investment_learning=investment_learning,
        growth_70=growth_70,
        growth_benchmark=growth_benchmark,
        actions=actions,
        applied_counterfactual=adjustments,
        counting_note=(
            "四账户采用顺序式资金瀑布；保额、信用卡额度、住房和养老金账户均不会被重复计入"
            "可规划金融资产。保命账户展示必要年保费与保障缺口，不将保额当作资产；"
            "保本账户名称表达用途目标，不代表其中所有产品保证本金。"
        ),
    )


def plan_household(
    session: Session,
    household_id: str,
    financial_rules_path: str,
    planning_rules_path: str,
    analysis_date: date,
    request: CounterfactualRequest | None = None,
) -> PlanningResponse:
    facts = load_household_facts(session, household_id)
    planning_rules = load_planning_rules(planning_rules_path)
    if request is None:
        adjustments = empty_counterfactual()
    else:
        financial_rules = load_financial_rules(financial_rules_path)
        financial = analyze_facts(facts, financial_rules, analysis_date)
        adjustments = _validate_counterfactual(
            facts,
            financial.protection.protection_gap,
            set(financial_rules.classification.investable_financial_asset_categories),
            request,
        )
    return plan_facts(
        facts,
        financial_rules_path,
        planning_rules,
        analysis_date,
        adjustments,
    )


def _account_amount(plan: PlanningResponse, bucket: AccountBucket) -> Decimal:
    return next(item.recommended_amount for item in plan.accounts if item.bucket == bucket)


def _changes(base: PlanningResponse, scenario: PlanningResponse) -> list[CounterfactualChange]:
    comparisons: tuple[tuple[str, str, Decimal, Decimal, str], ...] = (
        (
            "daily_recommended",
            "日用账户建议金额",
            _account_amount(base, AccountBucket.DAILY_LIQUIDITY),
            _account_amount(scenario, AccountBucket.DAILY_LIQUIDITY),
            "展示应急补足后，顺序式日用资金层是否发生变化。",
        ),
        (
            "stable_recommended",
            "稳健账户建议金额",
            _account_amount(base, AccountBucket.STABLE_GOALS),
            _account_amount(scenario, AccountBucket.STABLE_GOALS),
            "反映近期目标、债务缓冲和受约束资金的合计变化。",
        ),
        (
            "growth_recommended",
            "增长账户建议金额",
            _account_amount(base, AccountBucket.LONG_TERM_GROWTH),
            _account_amount(scenario, AccountBucket.LONG_TERM_GROWTH),
            "仅比较通过全部前置顺序与五硬一软约束后的长期资金。",
        ),
        (
            "high_interest_debt",
            "高息债务余额",
            base.denominators.high_interest_debt_after_counterfactual,
            scenario.denominators.high_interest_debt_after_counterfactual,
            "实际偿还高息债务会优先消耗可规划资源。",
        ),
        (
            "goal_monthly_required",
            "目标合计月投入",
            money(sum((goal.monthly_required for goal in base.goals), ZERO)),
            money(sum((goal.monthly_required for goal in scenario.goals), ZERO)),
            "目标准备金、延期和成本增长共同影响月投入要求。",
        ),
    )
    return [
        CounterfactualChange(
            code=code,
            label=label,
            before=before,
            after=after,
            delta=money(after - before),
            explanation=explanation,
        )
        for code, label, before, after, explanation in comparisons
    ]


def compare_counterfactual(
    session: Session,
    household_id: str,
    financial_rules_path: str,
    planning_rules_path: str,
    request: CounterfactualRequest,
) -> CounterfactualResponse:
    analysis_date = request.analysis_date or date.today()
    base = plan_household(
        session,
        household_id,
        financial_rules_path,
        planning_rules_path,
        analysis_date,
    )
    scenario = plan_household(
        session,
        household_id,
        financial_rules_path,
        planning_rules_path,
        analysis_date,
        request,
    )
    return CounterfactualResponse(
        base=base,
        scenario=scenario,
        changes=_changes(base, scenario),
        explanation=(
            "反事实只改变请求中列明的变量；所有目标现值、缺口、账户金额与比例均由同一"
            "确定性规则版本重新计算。"
        ),
    )


def _ratio(measures: list[RatioMeasure], denominator_id: str) -> Decimal | None:
    return next(
        (item.ratio for item in measures if item.denominator_id == denominator_id),
        None,
    )


def persist_planning(
    session: Session,
    plan: PlanningResponse,
    rules: PlanningRules,
    actor: ActorContext,
) -> PersistedPlanningRun:
    rule_version = ensure_planning_rule_version(session, rules)
    limiting = [item.name for item in plan.constraints if item.limits_growth]
    recommendation = Recommendation(
        household_id=plan.meta.household_id,
        recommendation_type="dynamic_four_account_plan",
        status=RecommendationStatus.DRAFT,
        summary=(
            f"生命周期 {plan.lifecycle.effective_stage.value}；"
            f"约束因素：{'、'.join(limiting) if limiting else '无'}。"
        ),
        structured_advice=plan.model_dump(mode="json"),
        suitability_evidence={
            "constraints": [item.model_dump(mode="json") for item in plan.constraints],
            "investment_learning": plan.investment_learning.model_dump(mode="json"),
            "growth_70": plan.growth_70.model_dump(mode="json"),
            "calculation_source": plan.meta.calculation_source,
        },
        rule_version_id=rule_version.id,
        currency=plan.meta.currency,
        valuation_date=plan.meta.data_as_of,
        data_source="deterministic_planning_engine",
        is_user_confirmed=False,
    )
    session.add(recommendation)
    session.flush()

    account_ids: list[str] = []
    for account in plan.accounts:
        investable_ratio = _ratio(account.measures, "investable_financial_assets")
        if account.bucket == AccountBucket.RISK_PROTECTION:
            primary_ratio = _ratio(account.measures, "annual_new_surplus")
        elif account.bucket == AccountBucket.LONG_TERM_GROWTH:
            primary_ratio = (
                plan.investment_learning.recommended_ratio
                if plan.investment_learning.applicable
                else plan.growth_70.actual_ratio
            )
        else:
            primary_ratio = investable_ratio
        account_plan = AccountBucketPlan(
            household_id=plan.meta.household_id,
            recommendation_id=recommendation.id,
            bucket=account.bucket,
            sequence=account.sequence,
            denominator_name=account.primary_denominator_name,
            allocated_amount=account.recommended_amount,
            allocation_ratio=primary_ratio or ZERO,
            current_amount=account.current_amount,
            target_amount=account.target_amount,
            gap_amount=account.gap_amount,
            recommended_range_min=account.recommended_range_min,
            recommended_range_max=account.recommended_range_max,
            annual_cost_amount=account.annual_cost_amount,
            coverage_gap_amount=account.coverage_gap_amount,
            total_asset_ratio=_ratio(account.measures, "total_assets"),
            investable_asset_ratio=investable_ratio,
            annual_surplus_ratio=_ratio(account.measures, "annual_new_surplus"),
            plan_version=plan.meta.formula_version,
            input_version=plan.meta.input_version,
            calculation_source=plan.meta.calculation_source,
            constraint_evidence={
                "formula": account.formula,
                "substitution": account.substitution,
                "constraint_ids": account.constraint_ids,
                "source_record_ids": account.source_record_ids,
                "current_measures": [
                    item.model_dump(mode="json") for item in account.current_measures
                ],
                "target_measures": [
                    item.model_dump(mode="json") for item in account.target_measures
                ],
                "reference_band": (
                    account.reference_band.model_dump(mode="json")
                    if account.reference_band
                    else None
                ),
                "measures": [item.model_dump(mode="json") for item in account.measures],
            },
            rule_version_id=rule_version.id,
            currency=plan.meta.currency,
            valuation_date=plan.meta.data_as_of,
            data_source="deterministic_planning_engine",
            is_user_confirmed=False,
        )
        session.add(account_plan)
        session.flush()
        account_ids.append(account_plan.id)

    action_ids: list[str] = []
    for draft in plan.actions:
        action_item = ActionItem(
            household_id=plan.meta.household_id,
            recommendation_id=recommendation.id,
            title=draft.title,
            due_date=draft.due_date,
            status="draft",
            owner_role="client",
            evidence=draft.model_dump(mode="json"),
            currency=plan.meta.currency,
            valuation_date=plan.meta.data_as_of,
            data_source="deterministic_planning_engine",
            is_user_confirmed=False,
        )
        session.add(action_item)
        session.flush()
        action_ids.append(action_item.id)

    session.add(
        AuditEvent(
            household_id=plan.meta.household_id,
            event_type=AuditEventType.RECOMMENDATION_GENERATED,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type="Recommendation",
            entity_id=recommendation.id,
            event_version=recommendation.version,
            summary=(
                f"生成确定性动态四账户草稿，公式 {plan.meta.formula_version}，"
                f"规则 {plan.meta.rule_version}"
            ),
            occurred_at=recommendation.created_at,
            valuation_date=plan.meta.data_as_of,
            data_source="deterministic_planning_engine",
            is_user_confirmed=True,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "planning_persistence_failed",
            "目标与四账户规划无法保存",
            status_code=409,
        ) from exc
    session.refresh(recommendation)
    return PersistedPlanningRun(
        recommendation_id=recommendation.id,
        account_plan_ids=account_ids,
        action_item_ids=action_ids,
        household_id=plan.meta.household_id,
        input_version=plan.meta.input_version,
        rule_version_id=rule_version.id,
        rule_version=rules.semantic_version,
        account_count=len(account_ids),
        action_count=len(action_ids),
        created_at=recommendation.created_at,
    )


def json_export_payload(plan: PlanningResponse) -> dict[str, Any]:
    return plan.model_dump(mode="json")
