from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AccountBucket,
    AuditEventType,
    MarketScenario,
    PortfolioCandidateType,
    RecommendationStatus,
    SuitabilityDecision,
    SuitabilityStatus,
)
from app.models.assessment import PortfolioPlan, SuitabilityCheck
from app.models.common import utc_now
from app.models.governance import AuditEvent, Recommendation
from app.schemas.planning import PlanningResponse
from app.schemas.portfolio import (
    EducationCard,
    HedgeLabBoundary,
    PersistedPortfolioRun,
    PortfolioCandidate,
    PortfolioContext,
    PortfolioMeta,
    PortfolioResponse,
    ProductCatalogResponse,
    ProductOut,
    SuitabilityCheckItem,
    SuitabilityGateResult,
    SuitabilityProbeRequest,
    SuitabilityProbeResponse,
)
from app.services.financial.engine import analyze_facts
from app.services.financial.facts import load_household_facts
from app.services.financial.rules import load_financial_rules
from app.services.financial.utils import ZERO, money
from app.services.planning.engine import empty_counterfactual, plan_facts
from app.services.planning.rules import load_planning_rules
from app.services.portfolio.catalog import build_catalog_response
from app.services.portfolio.mapping import map_products, product_gate_from_mappings
from app.services.portfolio.optimizer import current_growth_weights, optimize_candidate
from app.services.portfolio.rules import (
    PortfolioRules,
    ensure_portfolio_rule_version,
    load_portfolio_rules,
)
from app.services.portfolio.suitability import (
    candidate_customer_gate,
    customer_suitability_gate,
    family_safety_gate,
    product_gate_for_probe,
)


def _portfolio_input_version(
    planning_input_version: str,
    rules: PortfolioRules,
    catalog: ProductCatalogResponse,
    market_scenario: MarketScenario,
) -> str:
    canonical = json.dumps(
        {
            "planning_input_version": planning_input_version,
            "portfolio_rule_version": rules.semantic_version,
            "catalog_version": catalog.catalog_version,
            "market_scenario": market_scenario.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _portfolio_context(
    planning: PlanningResponse,
    stable_goal_months: int,
) -> PortfolioContext:
    growth = next(
        item for item in planning.accounts if item.bucket == AccountBucket.LONG_TERM_GROWTH
    )
    long_term_goals = [
        item for item in planning.goals if item.months_remaining > stable_goal_months
    ]
    long_term_gap = money(sum((item.funding_gap for item in long_term_goals), ZERO))
    weighted_months_numerator = sum(
        (Decimal(item.months_remaining) * item.funding_gap for item in long_term_goals),
        ZERO,
    )
    horizon = max(60, int(weighted_months_numerator / long_term_gap)) if long_term_gap > 0 else 120
    return PortfolioContext(
        current_growth_assets=growth.current_amount,
        eligible_long_term_amount=growth.recommended_amount,
        amount_to_restore_safety_layers=money(
            max(ZERO, growth.current_amount - growth.recommended_amount)
        ),
        long_term_goal_present_value_gap=long_term_gap,
        simulation_horizon_months=horizon,
        annual_new_surplus=planning.denominators.annual_new_surplus,
        counting_note=(
            "组合金额只取动态四账户中通过前置顺序后的正式长期建议额或小额学习仓；"
            "当前增长资产与应补回安全层的金额分开显示，不重复增加可投资本金。"
        ),
    )


def _education_cards() -> list[EducationCard]:
    return [
        EducationCard(
            code="deposit_vs_wealth",
            title="存款与银行理财不是同一种承诺",
            summary="存款合同属性与净值型资管产品风险必须分开阅读。",
            points=[
                "模拟存款条目只说明合同本金属性，不承诺购买力。",
                "银行理财不是存款，不承诺保本保收益，业绩比较基准不是收益承诺。",
            ],
        ),
        EducationCard(
            code="bond_vs_bond_fund",
            title="债券与债券基金的持有逻辑不同",
            summary="债券基金没有统一到期日，净值会随利率、信用和流动性变化。",
            points=[
                "短期刚性目标不能因为名称含“债”就忽略净值波动。",
                "期限、赎回到账和信用暴露都要与目标日期匹配。",
            ],
        ),
        EducationCard(
            code="insurance_split",
            title="保险先分保障与储蓄功能",
            summary="保费、保额、现金价值、保证利益和非保证利益不可互相替代。",
            points=[
                "分红与演示利益不是保证收益。",
                "长期锁定、退保损失和持续缴费能力必须单独检查。",
            ],
        ),
        EducationCard(
            code="diversified_index",
            title="普通家庭默认从宽基分散开始",
            summary="长期权益方向优先低成本、宽基和多资产分散，不默认推荐个股或热点主题。",
            points=[
                "指数化不等于保本，仍会经历显著回撤。",
                "只有长期资金且三道闸门通过后才可执行。",
            ],
        ),
    ]


def _hedge_lab() -> HedgeLabBoundary:
    return HedgeLabBoundary(
        title="专业对冲实验室默认关闭",
        reason="普通家庭自动推荐不提供股指期货、杠杆或交易入口。",
        prerequisites=[
            "专业投资者资格与知识测试",
            "真实、明确且可核验的套期保值头寸",
            "交易经验、最大损失和保证金压力测试",
            "人工复核和独立风险确认",
        ],
    )


def _candidate_decision(
    family_gate: SuitabilityGateResult,
    customer_gate: SuitabilityGateResult,
    product_gate: SuitabilityGateResult,
    solver_method: str,
) -> SuitabilityDecision:
    if family_gate.status != SuitabilityStatus.PASS:
        return SuitabilityDecision.EDUCATION_ONLY
    if product_gate.status == SuitabilityStatus.BLOCK:
        return SuitabilityDecision.REJECT
    if customer_gate.status != SuitabilityStatus.PASS or solver_method == "rule_based_fallback":
        return SuitabilityDecision.DOWNGRADE
    return SuitabilityDecision.ALLOW


def _candidate_copy(
    candidate_type: PortfolioCandidateType,
    decision: SuitabilityDecision,
) -> tuple[list[str], list[str], str]:
    shared = [
        "仅使用动态四账户确认的长期资金",
        "家庭安全、客户和产品三道闸门均优先于市场情景",
        "所有产品条目均为 Mock 类型映射，不是工行在售产品",
    ]
    if candidate_type == PortfolioCandidateType.CONSERVATIVE:
        return (
            [*shared, "更重视回撤、流动性与较低换手"],
            ["可能较难覆盖长期购买力或较高目标缺口", "利率变化仍会影响债券基金净值"],
            "若可承受能力和长期目标更高，基准方案可能提供更强购买力；当前方案优先降低尾部损失。",
        )
    if candidate_type == PortfolioCandidateType.BALANCED:
        return (
            [*shared, "在回撤、目标概率与分散度之间取中间解"],
            ["权益和黄金仍会波动", "多资产相关性在压力期可能上升"],
            "稳健方案牺牲更多增长空间；进取方案需要更高风险上限和更强行为承受力。",
        )
    return (
        [*shared, "只适用于风险上限、期限和行为均支持的长期目标"],
        ["极端损失与最大回撤更高", "不得以短期目标、借款或应急资金承担波动"],
        (
            "若任一闸门受限，本方案会降级或仅作教育展示；不能因为预期增长更高而覆盖家庭安全。"
            if decision != SuitabilityDecision.ALLOW
            else "相比基准方案承担更高回撤，以争取长期目标和购买力空间。"
        ),
    )


def portfolio_household(
    session: Session,
    household_id: str,
    financial_rules_path: str,
    planning_rules_path: str,
    portfolio_rules_path: str,
    product_catalog_path: str,
    analysis_date: date,
    market_scenario: MarketScenario = MarketScenario.NEUTRAL,
) -> PortfolioResponse:
    facts = load_household_facts(session, household_id)
    financial_rules = load_financial_rules(financial_rules_path)
    planning_rules = load_planning_rules(planning_rules_path)
    portfolio_rules = load_portfolio_rules(portfolio_rules_path)
    financial = analyze_facts(facts, financial_rules, analysis_date)
    planning = plan_facts(
        facts,
        financial_rules_path,
        planning_rules,
        analysis_date,
        empty_counterfactual(),
    )
    catalog = build_catalog_response(session, product_catalog_path)
    context = _portfolio_context(planning, planning_rules.goals.stable_goal_months)
    family_gate = family_safety_gate(planning, portfolio_rules)
    customer_gate = customer_suitability_gate(facts, portfolio_rules)
    current_weights = current_growth_weights(facts, portfolio_rules)
    inflation_rate = financial.purchasing_power.family_weighted_inflation.rate
    products = catalog.products
    candidates: list[PortfolioCandidate] = []
    for candidate_type in PortfolioCandidateType:
        policy = portfolio_rules.candidate_policies[candidate_type.value]
        candidate_customer = candidate_customer_gate(
            customer_gate,
            policy.required_risk_level,
            portfolio_rules,
        )
        high_risk_cap = min(
            family_gate.high_risk_cap or ZERO,
            candidate_customer.high_risk_cap or ZERO,
        )
        optimized = optimize_candidate(
            candidate_type,
            context.eligible_long_term_amount,
            context.long_term_goal_present_value_gap,
            context.simulation_horizon_months,
            current_weights,
            inflation_rate,
            high_risk_cap,
            analysis_date,
            market_scenario,
            family_gate,
            candidate_customer,
            portfolio_rules,
        )
        mappings = map_products(
            optimized.allocations,
            products,
            context.eligible_long_term_amount,
            context.simulation_horizon_months,
            family_gate,
            candidate_customer,
            facts,
            portfolio_rules,
        )
        product_gate = product_gate_from_mappings(
            mappings,
            family_gate,
            candidate_customer,
        )
        decision = _candidate_decision(
            family_gate,
            candidate_customer,
            product_gate,
            optimized.diagnostics.method,
        )
        conditions, risks, why = _candidate_copy(candidate_type, decision)
        candidates.append(
            PortfolioCandidate(
                candidate_type=candidate_type,
                name=policy.name,
                decision=decision,
                investment_amount=context.eligible_long_term_amount,
                strategic_allocations=optimized.allocations,
                tactical_allocations=optimized.tactical_allocations,
                expected_nominal_return=optimized.metrics.expected_return,
                expected_real_return=optimized.metrics.expected_real_return,
                goal_success_probability=optimized.metrics.success_probability,
                simulation_method="deterministic_weighted_scenarios_not_monte_carlo",
                simulation_horizon_months=context.simulation_horizon_months,
                simulated_range_low=optimized.metrics.range_low,
                simulated_range_base=optimized.metrics.range_base,
                simulated_range_high=optimized.metrics.range_high,
                extreme_loss_ratio=optimized.metrics.cvar_loss,
                extreme_loss_amount=money(
                    context.eligible_long_term_amount * optimized.metrics.cvar_loss
                ),
                max_drawdown_estimate=optimized.metrics.max_drawdown,
                liquidity_score=optimized.metrics.liquidity_score,
                liquidity_description=(
                    "较高流动性"
                    if optimized.metrics.liquidity_score >= Decimal("0.80")
                    else "中等流动性"
                    if optimized.metrics.liquidity_score >= Decimal("0.65")
                    else "流动性受限"
                ),
                annual_fee_rate=optimized.metrics.annual_fee_rate,
                annual_fee_estimate=money(
                    context.eligible_long_term_amount * optimized.metrics.annual_fee_rate
                ),
                applicable_conditions=conditions,
                primary_risks=risks,
                why_not_other_candidates=why,
                gates=[family_gate, candidate_customer, product_gate],
                product_mappings=mappings,
                optimization=optimized.diagnostics,
                rebalancing=optimized.rebalancing,
            )
        )
    input_version = _portfolio_input_version(
        planning.meta.input_version,
        portfolio_rules,
        catalog,
        market_scenario,
    )
    return PortfolioResponse(
        meta=PortfolioMeta(
            household_id=facts.id,
            household_code=facts.code,
            analysis_date=analysis_date,
            data_as_of=financial.meta.data_as_of,
            input_version=input_version,
            formula_version=portfolio_rules.formula_version,
            rule_code=portfolio_rules.code,
            rule_version=portfolio_rules.semantic_version,
            optimizer_version=portfolio_rules.optimizer_version,
            catalog_version=catalog.catalog_version,
            currency=facts.currency,
            synthetic_data=facts.is_synthetic,
            market_scenario=market_scenario,
        ),
        context=context,
        family_safety_gate=family_gate,
        customer_suitability_gate=customer_gate,
        candidates=candidates,
        catalog=catalog,
        education_cards=_education_cards(),
        professional_hedge_lab=_hedge_lab(),
        counting_note=(
            "三套比例来自确定性多目标网格优化或有版本的规则降级；情景区间是离线加权情景，"
            "不是历史回测、Monte Carlo 或收益承诺。"
        ),
    )


def _probe_family_gate(
    gate: SuitabilityGateResult,
    request: SuitabilityProbeRequest,
) -> SuitabilityGateResult:
    cap = gate.high_risk_cap or ZERO
    expansion_blocked = request.requested_high_risk_ratio > cap
    check = SuitabilityCheckItem(
        check_code="family_requested_high_risk",
        label="申请高风险比例",
        status=SuitabilityStatus.BLOCK if expansion_blocked else SuitabilityStatus.PASS,
        observed_value=f"申请 {request.requested_high_risk_ratio:.0%} / 家庭上限 {cap:.0%}",
        rule="应急、债务、保障或近期目标受限时不得扩大高风险配置",
        reason="申请超过家庭安全上限。" if expansion_blocked else "申请未超过家庭安全上限。",
    )
    checks = [*gate.checks, check]
    failed = [item.check_code for item in checks if item.status != SuitabilityStatus.PASS]
    return gate.model_copy(
        update={
            "status": SuitabilityStatus.BLOCK if failed else SuitabilityStatus.PASS,
            "decision": SuitabilityDecision.REJECT if failed else SuitabilityDecision.ALLOW,
            "checks": checks,
            "failed_check_codes": failed,
        }
    )


def _probe_customer_gate(
    gate: SuitabilityGateResult,
    request: SuitabilityProbeRequest,
) -> SuitabilityGateResult:
    cap = gate.high_risk_cap or ZERO
    blocked = request.requested_high_risk_ratio > cap
    check = SuitabilityCheckItem(
        check_code="customer_requested_high_risk",
        label="客户申请与审慎上限",
        status=SuitabilityStatus.BLOCK if blocked else SuitabilityStatus.PASS,
        observed_value=f"申请 {request.requested_high_risk_ratio:.0%} / 客户上限 {cap:.0%}",
        rule="客户能力、意愿、知识和行为取审慎下限",
        reason="申请超过客户审慎上限。" if blocked else "申请未超过客户审慎上限。",
    )
    checks = [*gate.checks, check]
    failed = [item.check_code for item in checks if item.status != SuitabilityStatus.PASS]
    return gate.model_copy(
        update={
            "status": SuitabilityStatus.BLOCK if failed else SuitabilityStatus.PASS,
            "decision": SuitabilityDecision.REJECT if failed else SuitabilityDecision.ALLOW,
            "checks": checks,
            "failed_check_codes": failed,
        }
    )


def evaluate_suitability_probe(
    session: Session,
    household_id: str,
    request: SuitabilityProbeRequest,
    actor: ActorContext,
    financial_rules_path: str,
    planning_rules_path: str,
    portfolio_rules_path: str,
    product_catalog_path: str,
) -> SuitabilityProbeResponse:
    analysis_date = request.analysis_date or date.today()
    portfolio = portfolio_household(
        session,
        household_id,
        financial_rules_path,
        planning_rules_path,
        portfolio_rules_path,
        product_catalog_path,
        analysis_date,
    )
    facts = load_household_facts(session, household_id)
    rules = load_portfolio_rules(portfolio_rules_path)
    by_code: dict[str, ProductOut] = {item.code: item for item in portfolio.catalog.products}
    unknown = sorted(set(request.requested_product_codes) - set(by_code))
    if unknown:
        raise AppError(
            "portfolio_product_not_found",
            "适当性检查引用了不存在的模拟产品",
            status_code=422,
            details={"product_codes": unknown},
        )
    selected = [by_code[code] for code in request.requested_product_codes]
    family_gate = _probe_family_gate(portfolio.family_safety_gate, request)
    customer_gate = _probe_customer_gate(portfolio.customer_suitability_gate, request)
    product_gate = product_gate_for_probe(selected, request, customer_gate, facts, rules)
    gates = [family_gate, customer_gate, product_gate]
    failed = [code for gate in gates for code in gate.failed_check_codes]
    decision = SuitabilityDecision.REJECT if failed else SuitabilityDecision.ALLOW
    event = AuditEvent(
        household_id=household_id,
        event_type=AuditEventType.SUITABILITY_EVALUATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="SuitabilityProbe",
        entity_id=None,
        event_version=1,
        summary=(f"模拟产品适当性检查：{decision.value}；失败检查 {len(failed)} 项"),
        evidence={
            "decision": decision.value,
            "failed_check_codes": failed,
            "requested_product_codes": request.requested_product_codes,
            "target_horizon_months": request.target_horizon_months,
            "requested_high_risk_ratio": str(request.requested_high_risk_ratio),
            "leverage_ratio": str(request.leverage_ratio),
            "concentration_ratio": str(request.concentration_ratio),
            "rule_version": rules.semantic_version,
        },
        occurred_at=utc_now(),
        valuation_date=portfolio.meta.analysis_date,
        data_source="deterministic_suitability_engine",
        is_user_confirmed=True,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return SuitabilityProbeResponse(
        household_id=household_id,
        decision=decision,
        gates=gates,
        failed_check_codes=failed,
        audit_event_id=event.id,
        rule_version=rules.semantic_version,
        explanation=(
            "不匹配请求已拒绝并写入审计事件；不会因客户主动要求而绕过三道闸门。"
            if decision == SuitabilityDecision.REJECT
            else "请求通过当前三道闸门；仍需在真实业务中完成身份、授权与人工复核。"
        ),
    )


def persist_portfolio(
    session: Session,
    portfolio: PortfolioResponse,
    rules: PortfolioRules,
    actor: ActorContext,
) -> PersistedPortfolioRun:
    rule_version = ensure_portfolio_rule_version(session, rules)
    recommendation = Recommendation(
        household_id=portfolio.meta.household_id,
        recommendation_type="portfolio_candidates",
        status=RecommendationStatus.DRAFT,
        summary=(
            f"三候选组合；家庭闸门 {portfolio.family_safety_gate.status.value}；"
            f"客户上限 {portfolio.customer_suitability_gate.effective_risk_limit or 'unknown'}。"
        ),
        structured_advice=portfolio.model_dump(mode="json"),
        suitability_evidence={
            "family_gate": portfolio.family_safety_gate.model_dump(mode="json"),
            "customer_gate": portfolio.customer_suitability_gate.model_dump(mode="json"),
            "candidate_decisions": {
                item.candidate_type.value: item.decision.value for item in portfolio.candidates
            },
        },
        rule_version_id=rule_version.id,
        currency=portfolio.meta.currency,
        valuation_date=portfolio.meta.analysis_date,
        data_source="deterministic_portfolio_engine",
        is_user_confirmed=False,
    )
    session.add(recommendation)
    session.flush()
    plan_ids: list[str] = []
    check_ids: list[str] = []
    for candidate in portfolio.candidates:
        plan = PortfolioPlan(
            household_id=portfolio.meta.household_id,
            recommendation_id=recommendation.id,
            plan_name=candidate.name,
            candidate_type=candidate.candidate_type,
            denominator_name="动态四账户确认的长期可投资资金",
            allocations={
                item.asset_class: str(item.ratio) for item in candidate.strategic_allocations
            },
            tactical_allocations={
                item.asset_class: str(item.ratio) for item in candidate.tactical_allocations
            },
            product_mappings=[item.model_dump(mode="json") for item in candidate.product_mappings],
            rebalancing=candidate.rebalancing.model_dump(mode="json"),
            suitability_evidence={
                "decision": candidate.decision.value,
                "gates": [item.model_dump(mode="json") for item in candidate.gates],
            },
            investment_amount=candidate.investment_amount,
            objective_score=candidate.optimization.objective_score,
            goal_success_probability=candidate.goal_success_probability,
            simulated_range_low=candidate.simulated_range_low,
            simulated_range_high=candidate.simulated_range_high,
            extreme_loss_amount=candidate.extreme_loss_amount,
            max_drawdown_ratio=candidate.max_drawdown_estimate,
            annual_fee_estimate=candidate.annual_fee_estimate,
            liquidity_score=candidate.liquidity_score,
            suitability_decision=candidate.decision,
            solver_method=candidate.optimization.method,
            solver_status=candidate.optimization.status,
            random_seed=candidate.optimization.random_seed,
            solver_parameters=candidate.optimization.parameters,
            input_version=portfolio.meta.input_version,
            rule_version_id=rule_version.id,
            optimizer_version=portfolio.meta.optimizer_version,
            currency=portfolio.meta.currency,
            valuation_date=portfolio.meta.analysis_date,
            data_source="deterministic_portfolio_engine",
            is_user_confirmed=False,
        )
        session.add(plan)
        session.flush()
        plan_ids.append(plan.id)
        for gate in candidate.gates:
            check = SuitabilityCheck(
                household_id=portfolio.meta.household_id,
                portfolio_plan_id=plan.id,
                recommendation_id=recommendation.id,
                gate=gate.gate,
                status=gate.status,
                decision=gate.decision,
                check_version=portfolio.meta.formula_version,
                input_version=portfolio.meta.input_version,
                reasons=[
                    item.reason for item in gate.checks if item.status != SuitabilityStatus.PASS
                ],
                evidence=gate.model_dump(mode="json"),
                rule_version_id=rule_version.id,
                currency=portfolio.meta.currency,
                valuation_date=portfolio.meta.analysis_date,
                data_source="deterministic_suitability_engine",
                is_user_confirmed=False,
            )
            session.add(check)
            session.flush()
            check_ids.append(check.id)
    event = AuditEvent(
        household_id=portfolio.meta.household_id,
        event_type=AuditEventType.RECOMMENDATION_GENERATED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="Recommendation",
        entity_id=recommendation.id,
        event_version=recommendation.version,
        summary=(
            f"生成三候选组合草稿，优化器 {portfolio.meta.optimizer_version}，"
            f"规则 {portfolio.meta.rule_version}"
        ),
        evidence={
            "candidate_count": len(portfolio.candidates),
            "suitability_check_count": len(check_ids),
            "input_version": portfolio.meta.input_version,
            "catalog_version": portfolio.meta.catalog_version,
        },
        occurred_at=recommendation.created_at,
        valuation_date=portfolio.meta.analysis_date,
        data_source="deterministic_portfolio_engine",
        is_user_confirmed=True,
    )
    session.add(event)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "portfolio_persistence_failed",
            "组合候选与适当性链无法保存",
            status_code=409,
        ) from exc
    session.refresh(recommendation)
    return PersistedPortfolioRun(
        recommendation_id=recommendation.id,
        portfolio_plan_ids=plan_ids,
        suitability_check_ids=check_ids,
        household_id=portfolio.meta.household_id,
        input_version=portfolio.meta.input_version,
        rule_version_id=rule_version.id,
        rule_version=rules.semantic_version,
        candidate_count=len(plan_ids),
        suitability_check_count=len(check_ids),
        created_at=recommendation.created_at,
    )
