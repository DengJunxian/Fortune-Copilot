from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, cast

from app.schemas.competition import (
    BehavioralFinding,
    CashFlow,
    Citation,
    CompetitionDemoResponse,
    ComplianceCheck,
    FamilyBalanceSheet,
    FinancialGoal,
    GoalPlan,
    HumanEscalation,
    ProductPipeline,
    ProductRecommendation,
    ProductSchema,
    QuantAsset,
    QuantConstraints,
    QuantRequest,
    RiskBudget,
    WealthAccount,
    WealthClientModel,
)
from app.services.competition.quant import compare_quant_methods

ANALYSIS_DATE = date(2026, 9, 1)
ENGINE_VERSION = "competition-cfs-v1.0.0"
Q = Decimal("0.000001")
MONEY_Q = Decimal("0.01")
ZERO = Decimal("0")
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def resolve_competition_data_file(relative_path: str) -> Path:
    configured_root = os.getenv("COMPETITION_DATA_ROOT", "").strip()
    candidates = [PROJECT_ROOT / "data" / relative_path, Path("/seed-data") / relative_path]
    if configured_root:
        candidates.insert(0, Path(configured_root).expanduser() / relative_path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"competition data file not found: {relative_path}")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _ratio(value: Decimal | float) -> Decimal:
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def load_competition_client() -> WealthClientModel:
    payload = _read_json(
        resolve_competition_data_file("synthetic/competition_demo_shanghai_38_v1.json")
    )
    return WealthClientModel.model_validate(payload)


def load_competition_products() -> list[ProductSchema]:
    payload = _read_json(
        resolve_competition_data_file("products/competition_demo_products_v1.json")
    )
    return [ProductSchema.model_validate(item) for item in payload["products"]]


def _annual_cash_flow(client: WealthClientModel) -> CashFlow:
    income = client.income_profile.household_annual_income
    expenses = client.expense_profile.annual_expense
    debt_service = sum((item.monthly_payment * Decimal("12") for item in client.liabilities), ZERO)
    return CashFlow(
        annual_income=_money(income),
        annual_expense=_money(expenses),
        annual_debt_service=_money(debt_service),
        annual_surplus=_money(income - expenses - debt_service),
    )


def build_family_balance_sheet(
    client: WealthClientModel, cash_flow: CashFlow
) -> FamilyBalanceSheet:
    total_assets = sum((item.market_value for item in client.assets), ZERO)
    financial_assets = sum(
        (item.market_value for item in client.assets if item.is_financial_asset), ZERO
    )
    liabilities = sum((item.outstanding_balance for item in client.liabilities), ZERO)
    liquid_assets = sum(
        (
            item.market_value
            for item in client.assets
            if item.is_financial_asset and item.liquidity_days <= 7 and not item.pledged
        ),
        ZERO,
    )
    emergency_eligible_assets = sum(
        (
            item.market_value
            for item in client.assets
            if item.category in {"cash", "deposit"}
            and item.liquidity_days <= 7
            and not item.pledged
        ),
        ZERO,
    )
    investment_assets = sum(
        (item.market_value for item in client.assets if item.is_investment_asset), ZERO
    )
    monthly_income = cash_flow.annual_income / Decimal("12")
    monthly_debt = cash_flow.annual_debt_service / Decimal("12")
    emergency_months = (
        emergency_eligible_assets / client.expense_profile.essential_monthly_expense
        if client.expense_profile.essential_monthly_expense > 0
        else ZERO
    )
    concentration = (
        max((item.market_value for item in client.assets), default=ZERO) / total_assets
        if total_assets > 0
        else ZERO
    )
    protection_coverage = sum(
        (
            item.coverage_amount
            for item in client.insurance
            if item.protection_type in {"life", "critical_illness"}
        ),
        ZERO,
    )
    required_protection = cash_flow.annual_income * Decimal("5") + liabilities
    protection_gap = max(ZERO, required_protection - protection_coverage)
    return FamilyBalanceSheet(
        total_assets=_money(total_assets),
        financial_assets=_money(financial_assets),
        total_liabilities=_money(liabilities),
        net_worth=_money(total_assets - liabilities),
        liquid_assets=_money(liquid_assets),
        investment_assets=_money(investment_assets),
        monthly_cash_flow=_money(cash_flow.annual_surplus / Decimal("12")),
        debt_to_income_ratio=_ratio(monthly_debt / monthly_income if monthly_income > 0 else ZERO),
        emergency_fund_months=_ratio(emergency_months),
        asset_concentration=_ratio(concentration),
        insurance_protection_gap=_money(protection_gap),
        accounting_identity=(
            f"{_money(total_assets)} - {_money(liabilities)} = {_money(total_assets - liabilities)}"
        ),
    )


def build_dynamic_wealth_accounts(
    client: WealthClientModel,
    balance: FamilyBalanceSheet,
    cash_flow: CashFlow,
) -> list[WealthAccount]:
    dependency_adjustment = Decimal(client.family_profile.dependent_count) * Decimal("0.75")
    stability_adjustment = (Decimal("1") - client.income_profile.stability_score) * Decimal("5")
    family_adjustment = Decimal("0.50") if client.family_profile.has_minor_child else ZERO
    debt_adjustment = Decimal("1") if balance.debt_to_income_ratio > Decimal("0.35") else ZERO
    employment_adjustment = (
        Decimal("1.50") if client.personal_profile.employment_type == "business_owner" else ZERO
    )
    safety_months = min(
        Decimal("12"),
        Decimal("3")
        + dependency_adjustment
        + stability_adjustment
        + family_adjustment
        + debt_adjustment
        + employment_adjustment,
    )
    liquidity_target = min(
        balance.financial_assets,
        client.expense_profile.essential_monthly_expense * safety_months,
    )
    premium = sum((item.annual_premium for item in client.insurance), ZERO)
    protection_reserve = min(
        max(ZERO, balance.financial_assets - liquidity_target),
        max(premium * Decimal("2"), cash_flow.annual_income * Decimal("0.03")),
    )
    near_term_gaps = sum(
        (
            max(ZERO, item.target_amount - item.current_assets)
            for item in client.financial_goals
            if (item.target_date - ANALYSIS_DATE).days <= 365 * 5
        ),
        ZERO,
    )
    high_interest_debt = sum(
        (
            item.outstanding_balance
            for item in client.liabilities
            if item.annual_interest_rate >= Decimal("0.08")
        ),
        ZERO,
    )
    remaining_after_safety = max(
        ZERO, balance.financial_assets - liquidity_target - protection_reserve
    )
    goal_matching = min(remaining_after_safety, near_term_gaps + high_interest_debt)
    growth = max(
        ZERO,
        balance.financial_assets - liquidity_target - protection_reserve - goal_matching,
    )
    amounts = [liquidity_target, protection_reserve, goal_matching, growth]
    codes = ["liquidity", "protection", "liability_goal_matching", "growth"]
    names = ["要花的钱", "保命的钱", "保本与目标匹配的钱", "生钱的钱"]
    drivers = [
        [
            f"收入稳定性 {client.income_profile.stability_score}",
            f"家庭抚养人数 {client.family_profile.dependent_count}",
            f"动态应急月数 {safety_months.quantize(Decimal('0.01'))}",
        ],
        [
            f"年保费 {_money(premium)} 元",
            f"保障缺口 {_money(balance.insurance_protection_gap)} 元",
            "保障额度与用于交保费的现金预算分开计算",
        ],
        [
            f"五年内目标缺口 {_money(near_term_gaps)} 元",
            f"高息债务 {_money(high_interest_debt)} 元",
            "低息住房按揭不机械要求提前清偿",
        ],
        [
            f"金融资产 {_money(balance.financial_assets)} 元",
            "只使用前置安全账户安排后的长期剩余资金",
            f"当前月结余 {_money(cash_flow.annual_surplus / Decimal('12'))} 元",
        ],
    ]
    explanations = [
        "覆盖日常支出与按家庭事实动态推导的应急月数。",
        "用于持续保障安排；保障缺口本身不是一笔应投资现金。",
        "优先匹配短期刚性目标和高息债务，不使用固定比例。",
        "由金融资产扣除前三类责任后得到，不由语言模型或固定40%生成。",
    ]
    return [
        WealthAccount(
            code=code,
            chinese_name=name,
            target_amount=_money(amount),
            share_of_financial_assets=_ratio(
                amount / balance.financial_assets if balance.financial_assets > 0 else ZERO
            ),
            drivers=drivers[index],
            explanation=explanations[index],
        )
        for index, (code, name, amount) in enumerate(zip(codes, names, amounts, strict=True))
    ]


def _months_between(start: date, end: date) -> int:
    return max(1, (end.year - start.year) * 12 + end.month - start.month)


def _future_value_of_contributions(monthly: Decimal, rate: Decimal, months: int) -> Decimal:
    monthly_rate = rate / Decimal("12")
    if monthly_rate == 0:
        return monthly * Decimal(months)
    return monthly * (((Decimal("1") + monthly_rate) ** months - Decimal("1")) / monthly_rate)


def _required_monthly_saving(goal: FinancialGoal, months: int) -> tuple[Decimal, Decimal, Decimal]:
    return_rate = goal.expected_return / Decimal("12")
    inflation_rate = goal.inflation_rate / Decimal("12")
    future_target = goal.target_amount * (Decimal("1") + inflation_rate) ** months
    future_current = goal.current_assets * (Decimal("1") + return_rate) ** months
    gap = max(ZERO, future_target - future_current)
    if return_rate == 0:
        required = gap / Decimal(months)
    else:
        factor = ((Decimal("1") + return_rate) ** months - Decimal("1")) / return_rate
        required = gap / factor
    return future_target, future_current, required


def build_goal_plans(client: WealthClientModel, cash_flow: CashFlow) -> list[GoalPlan]:
    monthly_resources = max(ZERO, cash_flow.annual_surplus / Decimal("12"))
    remaining = monthly_resources
    results: list[GoalPlan] = []
    for goal in sorted(client.financial_goals, key=lambda item: (item.priority, item.target_date)):
        months = _months_between(ANALYSIS_DATE, goal.target_date)
        future_target, future_current, required = _required_monthly_saving(goal, months)
        allocated = min(required, remaining)
        remaining -= allocated
        projected = future_current + _future_value_of_contributions(
            allocated, goal.expected_return, months
        )
        funding_gap = max(ZERO, future_target - projected)
        funding_ratio = min(Decimal("1"), projected / future_target)
        horizon_factor = min(Decimal("1"), Decimal(months) / Decimal("60"))
        probability = min(
            Decimal("0.99"),
            Decimal(str(float(funding_ratio) ** 0.70))
            * (Decimal("0.85") + horizon_factor * Decimal("0.15")),
        )
        if funding_gap == 0:
            status = "funded"
        elif allocated >= required * Decimal("0.95"):
            status = "on_track"
        else:
            status = "resource_constrained"
        results.append(
            GoalPlan(
                goal_id=goal.goal_id,
                name=goal.name,
                future_value=_money(future_target),
                projected_assets=_money(projected),
                required_monthly_saving=_money(required),
                allocated_monthly_saving=_money(allocated),
                funding_gap=_money(funding_gap),
                success_probability=_ratio(probability),
                coordination_status=status,
                formula_trace=[
                    "FV_target = target_amount × (1 + inflation/12)^months",
                    "FV_current = current_assets × (1 + expected_return/12)^months",
                    "RequiredSaving = (FV_target − FV_current) / annuity_factor",
                    (
                        f"按优先级 {goal.priority} 从月度可用结余 "
                        f"{_money(monthly_resources)} 元协调资金"
                    ),
                ],
            )
        )
    return results


def build_risk_budget(
    client: WealthClientModel,
    balance: FamilyBalanceSheet,
    goals: list[GoalPlan],
) -> RiskBudget:
    longest_horizon = max(
        (_months_between(ANALYSIS_DATE, item.target_date) for item in client.financial_goals),
        default=12,
    )
    horizon_score = min(Decimal("1"), Decimal(longest_horizon) / Decimal("240"))
    debt_score = max(ZERO, Decimal("1") - balance.debt_to_income_ratio * Decimal("1.8"))
    emergency_score = min(Decimal("1"), balance.emergency_fund_months / Decimal("6"))
    family_score = max(
        Decimal("0.40"),
        Decimal("1") - Decimal(client.family_profile.dependent_count) * Decimal("0.12"),
    )
    net_worth_score = min(
        Decimal("1"),
        max(ZERO, balance.net_worth / max(balance.total_assets, Decimal("1"))),
    )
    capacity = sum(
        (
            client.income_profile.stability_score,
            horizon_score,
            debt_score,
            emergency_score,
            family_score,
            net_worth_score,
        ),
        ZERO,
    ) / Decimal("6")
    reaction_scores = {
        "sell_all": Decimal("0.20"),
        "reduce": Decimal("0.45"),
        "hold": Decimal("0.70"),
        "buy_more": Decimal("0.75"),
    }
    tolerance = sum(
        (
            client.risk_profile.tolerance_score,
            min(Decimal("1"), client.risk_profile.maximum_acceptable_loss / Decimal("0.30")),
            client.risk_profile.investment_knowledge_score,
            reaction_scores[client.risk_profile.loss_reaction],
        ),
        ZERO,
    ) / Decimal("4")
    goal_by_id = {item.goal_id: item for item in client.financial_goals}
    total_future = sum((item.future_value for item in goals), ZERO)
    requirement_return = sum(
        (goal_by_id[item.goal_id].expected_return * item.future_value for item in goals),
        ZERO,
    ) / max(total_future, Decimal("1"))
    requirement = min(Decimal("1"), max(ZERO, requirement_return / Decimal("0.10")))
    effective = min(capacity, tolerance)
    level = max(1, min(5, 1 + int((effective * Decimal("4")).to_integral_value())))
    binding = "capacity" if capacity <= tolerance else "tolerance"
    return RiskBudget(
        risk_capacity=_ratio(capacity),
        risk_tolerance=_ratio(tolerance),
        risk_requirement=_ratio(requirement),
        effective_risk_budget=_ratio(effective),
        maximum_portfolio_volatility=_ratio(Decimal("0.04") + effective * Decimal("0.15")),
        maximum_cvar_loss=_ratio(
            min(
                client.risk_profile.maximum_acceptable_loss,
                Decimal("0.08") + effective * Decimal("0.12"),
            )
        ),
        risk_level=level,
        binding_dimension=binding,
        requirement_conflict=requirement > effective,
        evidence=[
            f"收入稳定性={client.income_profile.stability_score}",
            f"最长目标期限={longest_horizon}个月",
            f"债务收入比={balance.debt_to_income_ratio}",
            f"应急资金={balance.emergency_fund_months}个月",
            f"最大可接受亏损={client.risk_profile.maximum_acceptable_loss}",
            "Risk Requirement 只揭示目标要求与能力/意愿冲突，不能反向抬高风险上限。",
        ],
    )


def _quant_request(risk: RiskBudget, goals: list[GoalPlan]) -> QuantRequest:
    longest_goal_days = max(
        (
            (item.target_date - ANALYSIS_DATE).days
            for item in load_competition_client().financial_goals
        ),
        default=3650,
    )
    assets = [
        QuantAsset(
            asset_class="cash_equivalent",
            expected_return="0.015",
            volatility="0.008",
            liquidity_score="1.00",
            lockup_days=0,
            min_weight="0.00",
            max_weight="0.45",
            market_weight="0.12",
            scenarios=[
                "0.012",
                "0.013",
                "0.014",
                "0.015",
                "0.015",
                "0.016",
                "0.016",
                "0.017",
                "0.012",
                "0.014",
            ],
        ),
        QuantAsset(
            asset_class="fixed_income",
            expected_return="0.035",
            volatility="0.055",
            liquidity_score="0.85",
            lockup_days=30,
            min_weight="0.10",
            max_weight="0.55",
            market_weight="0.36",
            scenarios=[
                "0.025",
                "0.010",
                "0.030",
                "0.040",
                "-0.015",
                "0.045",
                "0.020",
                "0.035",
                "-0.030",
                "0.028",
            ],
        ),
        QuantAsset(
            asset_class="diversified_equity",
            expected_return="0.075",
            volatility="0.200",
            liquidity_score="0.80",
            lockup_days=7,
            min_weight="0.00",
            max_weight="0.45",
            market_weight="0.34",
            scenarios=[
                "0.120",
                "-0.180",
                "0.080",
                "0.160",
                "-0.280",
                "0.220",
                "0.040",
                "-0.060",
                "-0.350",
                "0.100",
            ],
        ),
        QuantAsset(
            asset_class="real_assets",
            expected_return="0.060",
            volatility="0.160",
            liquidity_score="0.60",
            lockup_days=180,
            min_weight="0.00",
            max_weight="0.20",
            market_weight="0.10",
            scenarios=[
                "0.080",
                "-0.100",
                "0.070",
                "0.120",
                "-0.180",
                "0.140",
                "0.030",
                "-0.040",
                "-0.240",
                "0.090",
            ],
        ),
        QuantAsset(
            asset_class="gold",
            expected_return="0.042",
            volatility="0.140",
            liquidity_score="0.90",
            lockup_days=3,
            min_weight="0.00",
            max_weight="0.20",
            market_weight="0.08",
            scenarios=[
                "0.020",
                "0.090",
                "-0.030",
                "0.040",
                "0.150",
                "-0.060",
                "0.070",
                "0.030",
                "0.180",
                "-0.040",
            ],
        ),
    ]
    return QuantRequest(
        assets=assets,
        correlation_matrix=[
            ["1.00", "0.05", "0.00", "0.00", "0.00"],
            ["0.05", "1.00", "0.20", "0.15", "0.05"],
            ["0.00", "0.20", "1.00", "0.55", "-0.05"],
            ["0.00", "0.15", "0.55", "1.00", "0.05"],
            ["0.00", "0.05", "-0.05", "0.05", "1.00"],
        ],
        target_return="0.045",
        constraints=QuantConstraints(
            minimum_cash="0.10",
            maximum_asset_exposure="0.55",
            minimum_liquidity_score="0.75",
            maximum_volatility=risk.maximum_portfolio_volatility,
            maximum_cvar_loss=risk.maximum_cvar_loss,
            goal_horizon_days=longest_goal_days,
            allowed_asset_classes=[item.asset_class for item in assets],
            grid_step="0.05",
        ),
        black_litterman_views={
            "diversified_equity": "0.065",
            "fixed_income": "0.038",
        },
        view_confidences={
            "diversified_equity": "0.35",
            "fixed_income": "0.55",
        },
    )


def _product_check(
    product: ProductSchema,
    target_weight: Decimal,
    target_amount: Decimal,
    risk: RiskBudget,
    horizon_months: int,
) -> ComplianceCheck:
    violations: list[str] = []
    if product.risk_level > risk.risk_level:
        violations.append("product_risk_above_customer_limit")
    if risk.risk_level not in product.suitable_customer:
        violations.append("customer_not_in_suitable_segment")
    if product.duration_months > horizon_months:
        violations.append("duration_exceeds_goal_horizon")
    if product.liquidity_days > 30:
        violations.append("liquidity_exceeds_growth_sleeve_limit")
    if target_weight > Decimal("0.55"):
        violations.append("concentration_limit_exceeded")
    if target_amount < product.minimum_investment:
        violations.append("below_minimum_investment")
    if "主题集中" in product.tags:
        violations.append("conflict_rule_theme_concentration")
    return ComplianceCheck(
        product_id=product.product_id,
        passed=not violations,
        violations=violations,
        checked_rules=[
            "customer_risk_level",
            "product_risk_level",
            "investment_horizon",
            "liquidity",
            "concentration",
            "minimum_investment",
            "conflict_rules",
        ],
    )


def build_product_pipeline(
    client: WealthClientModel,
    accounts: list[WealthAccount],
    risk: RiskBudget,
    quant: Any,
) -> ProductPipeline:
    products = load_competition_products()
    growth_amount = next(item.target_amount for item in accounts if item.code == "growth")
    selected_quant = next(item for item in quant.methods if item.method == quant.selected_method)
    horizon_months = max(
        (_months_between(ANALYSIS_DATE, item.target_date) for item in client.financial_goals),
        default=60,
    )
    recommendations: list[ProductRecommendation] = []
    rejected: list[ComplianceCheck] = []
    for asset_class, weight in selected_quant.weights.items():
        amount = _money(growth_amount * weight)
        candidates = [item for item in products if item.asset_class == asset_class]
        approved: list[tuple[ProductSchema, ComplianceCheck, Decimal]] = []
        for product in candidates:
            check = _product_check(product, weight, amount, risk, horizon_months)
            if not check.passed:
                rejected.append(check)
                continue
            score = (
                Decimal("1")
                - product.fees * Decimal("8")
                - product.volatility * Decimal("0.35")
                + Decimal("0.08") / Decimal(max(1, product.liquidity_days + 1))
            )
            approved.append((product, check, score))
        if not approved or amount <= 0:
            continue
        product, check, score = max(approved, key=lambda item: (item[2], -item[0].fees))
        recommendations.append(
            ProductRecommendation(
                product=product,
                target_weight=weight,
                target_amount=amount,
                rank_score=_ratio(score),
                compliance=check,
                why_selected=[
                    f"先由量化引擎确定 {asset_class} 权重，再在同资产类别中匹配产品。",
                    f"客户风险上限 R{risk.risk_level}，产品风险 R{product.risk_level}。",
                    f"费用率 {product.fees}，流动性 {product.liquidity_days} 天。",
                ],
            )
        )
    violation_count = sum(not item.compliance.passed for item in recommendations)
    violation_rate = Decimal(violation_count) / Decimal(max(1, len(recommendations)))
    return ProductPipeline(
        stages=[
            "Asset Allocation",
            "Product Filtering",
            "Suitability Check",
            "Product Ranking",
            "Portfolio Construction",
            "Compliance Agent Approval",
        ],
        recommendations=recommendations,
        rejected_products=rejected,
        suitability_violation_rate=_ratio(violation_rate),
        no_executable_product=not recommendations,
    )


def detect_behavioral_biases(client: WealthClientModel) -> list[BehavioralFinding]:
    mapping = {
        "panic_sale": (
            "loss_aversion",
            "短期亏损可能诱发过早减仓，破坏长期目标资金路径。",
            "设置48小时冷静期，并在操作前重看目标期限与压力测试结果。",
        ),
        "hold_loser": (
            "disposition_effect",
            "仅因账面亏损而继续持有会忽略机会成本和原投资逻辑失效。",
            "按投资逻辑和资产类别目标权重复核，不以买入成本作为唯一锚点。",
        ),
        "follow_crowd": (
            "herding",
            "群体讨论不能替代产品适当性、费用和集中度检查。",
            "要求写下一条独立购买理由，并通过合规闸门后再决定。",
        ),
        "excessive_trading": (
            "overconfidence",
            "高频调仓增加费用和行为误差，可能偏离长期策略。",
            "默认半年复核；只有阈值漂移或重大生活事件才触发再平衡。",
        ),
        "recent_return_anchor": (
            "recency_bias",
            "最近表现无法代表完整周期风险，容易低估回撤。",
            "同时查看至少一个完整市场周期、CVaR与最大回撤压力情景。",
        ),
        "chase_top_performer": (
            "performance_chasing",
            "追逐短期排名可能在估值和拥挤度较高时买入。",
            "将短期业绩从排名因子中移除，优先比较资产角色、费用和适当性。",
        ),
    }
    grouped: dict[str, list[str]] = {}
    for evidence in client.behavior_profile.evidence:
        grouped.setdefault(evidence.signal, []).append(
            f"{evidence.observed_on.isoformat()}：{evidence.observation}"
        )
    return [
        BehavioralFinding(
            bias=mapping[signal][0],
            evidence=evidence,
            risk=mapping[signal][1],
            intervention=mapping[signal][2],
        )
        for signal, evidence in grouped.items()
    ]


def _citations() -> list[Citation]:
    payload = _read_json(resolve_competition_data_file("knowledge/controlled_knowledge_v1.json"))
    wanted = {
        "wealth_product_suitability",
        "wealth_product_risk_disclosure",
        "consumer_protection_review",
        "insurance_information_scope",
        "shanghai_cost_method",
    }
    result: list[Citation] = []
    for document in payload["documents"]:
        for chunk in document["chunks"]:
            if chunk["code"] not in wanted:
                continue
            result.append(
                Citation(
                    citation_id=chunk["code"],
                    title=document["title"],
                    source_type=document["source_type"],
                    source_uri=document["source_uri"],
                    excerpt=chunk["content"],
                )
            )
    return result


def _human_escalation(
    balance: FamilyBalanceSheet,
    risk: RiskBudget,
    behavior: list[BehavioralFinding],
) -> HumanEscalation:
    triggers: list[str] = []
    if balance.total_assets >= Decimal("6000000"):
        triggers.append("高资产家庭：建议客户经理复核服务层级与复杂需求")
    if balance.asset_concentration >= Decimal("0.60"):
        triggers.append("自住房等单一资产集中度超过60%")
    if balance.insurance_protection_gap >= Decimal("2000000"):
        triggers.append("家庭支柱保障缺口较大，需要持牌人员复核")
    if risk.requirement_conflict:
        triggers.append("目标要求收益高于客户有效风险预算")
    if len(behavior) >= 4:
        triggers.append("多项行为偏差同时出现，建议人工沟通而非自动推送")
    return HumanEscalation(
        required=bool(triggers),
        triggers=triggers,
        service_level="priority" if triggers else "routine",
        next_best_action=(
            "客户经理在7日内完成保障、目标资源冲突与房产集中度三项会谈复核。"
            if triggers
            else "维持半年例行复核。"
        ),
    )


def build_competition_demo() -> CompetitionDemoResponse:
    client = load_competition_client()
    cash_flow = _annual_cash_flow(client)
    balance = build_family_balance_sheet(client, cash_flow)
    accounts = build_dynamic_wealth_accounts(client, balance, cash_flow)
    goals = build_goal_plans(client, cash_flow)
    risk = build_risk_budget(client, balance, goals)
    quant_request = _quant_request(risk, goals)
    quant = compare_quant_methods(quant_request)
    products = build_product_pipeline(client, accounts, risk, quant)
    behavior = detect_behavioral_biases(client)
    citations = _citations()
    escalation = _human_escalation(balance, risk, behavior)
    advisor_summary = [
        (
            f"家庭净资产 {_money(balance.net_worth)} 元，但自住房导致资产集中度 "
            f"{balance.asset_concentration}。"
        ),
        (
            f"月度可用结余 {_money(balance.monthly_cash_flow)} 元，"
            f"需按优先级协调 {len(goals)} 项目标。"
        ),
        (
            f"风险能力 {risk.risk_capacity}、风险意愿 {risk.risk_tolerance}、"
            f"目标风险要求 {risk.risk_requirement} 分开计算。"
        ),
        f"量化引擎比较4种方法后选择 {quant.selected_method}，Advisor 不得修改其权重。",
        (
            f"产品建议违规率 {products.suitability_violation_rate}；"
            "高波动主题产品被合规闸门拒绝。[wealth_product_suitability]"
        ),
        "下一步先补足应急与保障，再按目标期限执行分层资金安排并由客户经理复核。",
    ]
    rm_copilot: dict[str, object] = {
        "customer_360": {
            "lifecycle": "家庭成长期",
            "city": "上海",
            "financial_assets": str(balance.financial_assets),
            "net_worth": str(balance.net_worth),
            "risk_level": f"R{risk.risk_level}",
        },
        "current_wealth_issues": [
            "房产集中度偏高",
            "保障缺口仍需核验",
            "月度结余不足以同时覆盖全部目标要求",
        ],
        "priority_goals": [item.name for item in goals[:3]],
        "holding_risks": ["现有权益仓位需与教育、养老目标分账", "个人养老金流动性受限"],
        "service_opportunities": ["保障复核", "教育金分账", "养老现金流规划"],
        "next_best_action": escalation.next_best_action,
        "communication_guide": [
            "先解释家庭安全与目标冲突，不从单只产品切入。",
            "展示四种量化方法对比与合规拒绝记录。",
            "确认客户能接受的亏损金额，而非只问风险等级。",
        ],
        "human_review_items": escalation.triggers,
    }
    input_hash = hashlib.sha256(
        json.dumps(client.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output_hash = hashlib.sha256(
        json.dumps(
            {
                "balance": balance.model_dump(mode="json"),
                "goals": [item.model_dump(mode="json") for item in goals],
                "risk": risk.model_dump(mode="json"),
                "quant": quant.model_dump(mode="json"),
                "products": products.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return CompetitionDemoResponse(
        client=client,
        balance_sheet=balance,
        cash_flow=cash_flow,
        wealth_accounts=accounts,
        goals=goals,
        risk_budget=risk,
        quant=quant,
        product_pipeline=products,
        behavior_findings=behavior,
        citations=citations,
        advisor_summary=advisor_summary,
        rm_copilot=rm_copilot,
        human_escalation=escalation,
        audit={
            "engine_version": ENGINE_VERSION,
            "analysis_date": ANALYSIS_DATE.isoformat(),
            "input_hash": input_hash,
            "output_hash": output_hash,
            "calculation_source": "deterministic_tools",
            "llm_modified_quant_output": False,
            "external_network_calls": 0,
            "data_boundary": "synthetic_demo_not_icbc_production",
        },
    )
