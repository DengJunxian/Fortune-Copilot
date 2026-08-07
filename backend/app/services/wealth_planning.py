from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import cast
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import (
    AssetCategory,
    AuditEventType,
    CashFlowFrequency,
    ExpenseCategory,
    ExpenseNecessity,
    IncomeType,
    LiabilityCategory,
    LifecycleStage,
    LiquidityLevel,
    PropertyUse,
    RateType,
    RiskLevel,
)
from app.models.assessment import BehaviorAssessment, RiskAssessment
from app.models.common import utc_now
from app.models.family import Household, HouseholdMember
from app.models.finance import Asset, ExpenseItem, IncomeSource, Liability
from app.models.governance import AuditEvent
from app.schemas.financial_analysis import FinancialAnalysisResponse, MetricResult
from app.schemas.planning import PlanningResponse
from app.schemas.wealth_planning import (
    RATIO_METRIC_IDS,
    PlanNarrativeOutput,
    PlanNarrativeRequest,
    PlanNarrativeResponse,
    PlanningIntakeRequest,
    PlanningIntakeResponse,
    RatioExplanationItem,
    RatioExplanationOutput,
    RatioExplanationRequest,
    RatioExplanationResponse,
    RatioMetricId,
)
from app.services.financial.engine import analyze_household
from app.services.financial.utils import format_money
from app.services.llm import LLMRequest, generate_validated, get_llm_provider
from app.services.planning.engine import plan_household

ZERO = Decimal("0")
RATIO_QUANTUM = Decimal("0.000001")

FORTUNE_COPILOT_PHILOSOPHY = {
    "positioning": "构建立足中国家庭责任、住房、社保、养老金和人生目标的自主财富管理方法",
    "daily_liquidity": (
        "要花的钱只承担近期消费和支付，通常以数千元现金、活期存款或货币基金周转；"
        "信用卡只作为结算工具，额度不是资产"
    ),
    "risk_protection": (
        "保命的钱以消费型保障为主，保险保障归保险、投资归投资；按家庭责任与持续缴费能力核定"
    ),
    "stable_goals": (
        "保本的钱服务应急、个人养老金和五年内目标；5%-30%是以可投资金融资产为分母的总观察带，"
        "投研规则按偏积极、中性、偏防守发布当期区间与战术锚，家庭目标和安全约束优先；"
        "账户名称不代表银行理财、基金、保险等产品一律保证本金"
    ),
    "long_term_growth": (
        "生钱的钱正式配置仅在可规划金融净值达到客户确认的30万-100万元门槛并通过安全与适当性条件后启用；"
        "门槛以下如年度结余为正、没有待处理高息债务且通过适当性评估，可用不超过完成前置安排后多余长期资金10%的小仓位学习宽基指数基金；"
        "70%以上只针对正式配置且扣除前置用途后的长期可规划资源，不是家庭总资产，也不适用于学习仓"
    ),
    "investment_boundary": (
        "普通家庭以宽基指数和分散化工具为主，不默认推荐个股、杠杆、股指期货或投资性房产；"
        "专业衍生品必须另行完成专业投资者与产品适当性判断"
    ),
    "purchasing_power": (
        "最低工资增长只作为中国本土长期购买力压力辅助信号，不等同CPI，也不构成收益保证"
    ),
    "personal_pension": (
        "个人养老金按现行年度额度和税务事实评估，可选产品需逐项核对风险、期限与流动性"
    ),
}

LIFECYCLE_LABELS = {
    "early_career": "职业起步期",
    "family_formation": "家庭形成期",
    "parenting": "育儿成长期",
    "mature_family": "家庭成熟期",
    "retirement_preparation": "退休准备期",
    "retirement_and_legacy": "退休与传承期",
}


def _score(value: Decimal) -> Decimal:
    return min(Decimal("1"), max(ZERO, value)).quantize(RATIO_QUANTUM)


def _risk_level(score: Decimal) -> RiskLevel:
    if score < Decimal("0.30"):
        return RiskLevel.LOW
    if score < Decimal("0.45"):
        return RiskLevel.MEDIUM_LOW
    if score < Decimal("0.65"):
        return RiskLevel.MEDIUM
    if score < Decimal("0.80"):
        return RiskLevel.MEDIUM_HIGH
    return RiskLevel.HIGH


def _kyc_assessments(
    payload: PlanningIntakeRequest,
    household_id: str,
    common: dict[str, object],
) -> tuple[RiskAssessment, BehaviorAssessment]:
    kyc = payload.kyc
    financial_assets = sum(
        (
            item.amount
            for item in payload.assets
            if item.category
            in {
                "cash_and_equivalents",
                "time_deposit_and_bank_wealth",
                "non_bank_financial",
            }
        ),
        ZERO,
    )
    total_liabilities = sum((item.balance for item in payload.liabilities), ZERO)
    total_income = sum((item.annual_amount for item in payload.incomes), ZERO)
    total_expenses = sum((item.annual_amount for item in payload.expenses), ZERO)
    annual_surplus = total_income - total_expenses
    scheduled_debt_service = sum(
        (item.monthly_payment * Decimal("12") for item in payload.liabilities), ZERO
    )
    stated_debt_service = sum(
        (
            item.annual_amount
            for item in payload.expenses
            if item.category == "debt_service"
        ),
        ZERO,
    )
    debt_service = max(scheduled_debt_service, stated_debt_service)
    net_financial_assets = financial_assets - total_liabilities

    capacity = Decimal("0.15")
    if annual_surplus > ZERO:
        capacity += Decimal("0.20")
    if total_income > ZERO and debt_service / total_income < Decimal("0.30"):
        capacity += Decimal("0.15")
    if net_financial_assets >= kyc.growth_entry_threshold:
        capacity += Decimal("0.25")
    elif net_financial_assets > ZERO:
        capacity += Decimal("0.10")
    if kyc.investment_horizon_years >= 5:
        capacity += Decimal("0.15")
    if any(item.employment_stability.value == "high" for item in payload.members):
        capacity += Decimal("0.10")
    capacity = _score(capacity)

    willingness = _score(
        {
            "conservative": Decimal("0.35"),
            "balanced": Decimal("0.60"),
            "growth": Decimal("0.85"),
        }[kyc.risk_preference]
    )
    knowledge = _score(
        {
            "none": Decimal("0.25"),
            "basic": Decimal("0.55"),
            "experienced": Decimal("0.80"),
        }[kyc.investment_experience]
    )
    behavior = _score(
        {
            "low": Decimal("0.25"),
            "medium": Decimal("0.55"),
            "high": Decimal("0.80"),
        }[kyc.loss_tolerance]
    )
    final_risk_level = _risk_level(min(capacity, willingness, knowledge, behavior))
    behavior_level = _risk_level(behavior)
    explanation = (
        f"快速KYC确定性评估：风险能力{capacity}，意愿{willingness}，知识{knowledge}，"
        f"波动承受{behavior}；最终上限取四项最低等级。可规划金融净值为"
        f"{format_money(net_financial_assets)}，长期资金启动门槛为"
        f"{format_money(kyc.growth_entry_threshold)}。"
    )
    risk = RiskAssessment(
        **common,
        household_id=household_id,
        capacity_score=capacity,
        willingness_score=willingness,
        knowledge_score=knowledge,
        behavior_score=behavior,
        final_risk_limit=final_risk_level,
        explanation=explanation,
    )
    behavior_record = BehaviorAssessment(
        **common,
        household_id=household_id,
        questionnaire_score=behavior,
        experiment_score=behavior,
        final_behavior_limit=behavior_level,
        detected_biases=(
            ["loss_tolerance_requires_lower_risk"]
            if kyc.loss_tolerance == "low"
            else []
        ),
        experiment_answers={
            "source": "quick_kyc",
            "investment_experience": kyc.investment_experience,
            "risk_preference": kyc.risk_preference,
            "loss_tolerance": kyc.loss_tolerance,
            "investment_horizon_years": kyc.investment_horizon_years,
        },
        explanation="本记录来自客户确认的快速KYC，用于限制账户级增长建议，不替代具体产品风险测评。",
    )
    return risk, behavior_record


def _age_on(birth_date: date, on_date: date) -> int:
    return on_date.year - birth_date.year - (
        (on_date.month, on_date.day) < (birth_date.month, birth_date.day)
    )


def _lifecycle(payload: PlanningIntakeRequest, today: date) -> LifecycleStage:
    primary = next(item for item in payload.members if item.relationship == "本人")
    primary_age = _age_on(primary.birth_date, today)
    if primary_age >= 60:
        return LifecycleStage.RETIREMENT_AND_LEGACY
    if primary_age >= 50:
        return LifecycleStage.RETIREMENT_PREPARATION
    if any(
        item.relationship == "子女" and _age_on(item.birth_date, today) < 18
        for item in payload.members
    ):
        return LifecycleStage.PARENTING
    if payload.planning_scope == "family" and primary_age < 40:
        return LifecycleStage.FAMILY_FORMATION
    if primary_age < 35:
        return LifecycleStage.EARLY_CAREER
    return LifecycleStage.MATURE_FAMILY


def _ratio(value: Decimal, total: Decimal) -> Decimal:
    if total <= ZERO:
        return ZERO
    return (value / total).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


ASSET_MAPPING = {
    "cash_and_equivalents": (
        AssetCategory.DEMAND_DEPOSIT,
        LiquidityLevel.IMMEDIATE,
        0,
        RiskLevel.LOW,
        PropertyUse.NOT_PROPERTY,
        "日常支付与结算",
    ),
    "time_deposit_and_bank_wealth": (
        AssetCategory.BANK_WEALTH_MANAGEMENT,
        LiquidityLevel.WITHIN_1_YEAR,
        180,
        RiskLevel.MEDIUM_LOW,
        PropertyUse.NOT_PROPERTY,
        "定期存放与银行理财（不代表保本）",
    ),
    "non_bank_financial": (
        AssetCategory.PUBLIC_FUND,
        LiquidityLevel.WITHIN_30_DAYS,
        7,
        RiskLevel.MEDIUM,
        PropertyUse.NOT_PROPERTY,
        "非银行金融资产汇总",
    ),
    "primary_residence": (
        AssetCategory.PRIMARY_RESIDENCE,
        LiquidityLevel.ILLIQUID,
        36500,
        RiskLevel.MEDIUM,
        PropertyUse.PRIMARY_RESIDENCE,
        "家庭自住",
    ),
    "investment_property": (
        AssetCategory.INVESTMENT_PROPERTY,
        LiquidityLevel.ILLIQUID,
        36500,
        RiskLevel.MEDIUM_HIGH,
        PropertyUse.INVESTMENT_PROPERTY,
        "投资性持有",
    ),
    "vehicle_and_other": (
        AssetCategory.VEHICLE,
        LiquidityLevel.ILLIQUID,
        3650,
        RiskLevel.MEDIUM,
        PropertyUse.NOT_PROPERTY,
        "车辆及其他实物资产",
    ),
}

LIABILITY_MAPPING = {
    "mortgage": LiabilityCategory.MORTGAGE,
    "auto_loan": LiabilityCategory.AUTO_LOAN,
    "consumer_loan": LiabilityCategory.CONSUMER_LOAN,
    "credit_card_unpaid": LiabilityCategory.CREDIT_CARD_UNPAID,
    "non_bank_loan": LiabilityCategory.NON_BANK_LOAN,
    "other": LiabilityCategory.OTHER,
}

INCOME_MAPPING = {
    "self_employment": (IncomeType.EMPLOYMENT, Decimal("0.90"), Decimal("0.10")),
    "spouse_employment": (IncomeType.EMPLOYMENT, Decimal("0.90"), Decimal("0.10")),
    "asset_income": (IncomeType.INVESTMENT, Decimal("0.65"), Decimal("0.30")),
    "rental_income": (IncomeType.RENTAL, Decimal("0.75"), Decimal("0.20")),
    "other": (IncomeType.OTHER, Decimal("0.55"), Decimal("0.35")),
}

EXPENSE_MAPPING = {
    "living": (ExpenseCategory.BASIC_LIVING, ExpenseNecessity.ESSENTIAL, Decimal("0.05")),
    "parent_support": (
        ExpenseCategory.PARENT_SUPPORT,
        ExpenseNecessity.ESSENTIAL,
        Decimal("0.10"),
    ),
    "child_education": (
        ExpenseCategory.CHILD_EDUCATION,
        ExpenseNecessity.ESSENTIAL,
        Decimal("0.15"),
    ),
    "insurance_premium": (
        ExpenseCategory.INSURANCE_PREMIUM,
        ExpenseNecessity.ESSENTIAL,
        ZERO,
    ),
    "debt_service": (ExpenseCategory.DEBT_SERVICE, ExpenseNecessity.ESSENTIAL, ZERO),
    "other": (ExpenseCategory.OTHER, ExpenseNecessity.FLEXIBLE, Decimal("0.50")),
}


def create_planning_case(
    session: Session,
    payload: PlanningIntakeRequest,
    actor: ActorContext,
    settings: Settings,
    *,
    today: date | None = None,
) -> PlanningIntakeResponse:
    analysis_date = today or date.today()
    common = {
        "currency": "CNY",
        "valuation_date": analysis_date,
        "data_source": "client_intake",
        "is_user_confirmed": True,
    }
    household = Household(
        **common,
        code=f"PLAN_{uuid4().hex[:10].upper()}",
        name=payload.case_name,
        lifecycle_stage=_lifecycle(payload, analysis_date),
        region=payload.region,
        demo_profile=None,
        is_synthetic=False,
        planning_preferences=payload.kyc.model_dump(mode="json"),
    )
    session.add(household)
    try:
        session.flush()
        members: list[HouseholdMember] = []
        for member_input in payload.members:
            member = HouseholdMember(
                **common,
                household_id=household.id,
                display_name=member_input.display_name,
                relationship=member_input.relationship,
                birth_date=member_input.birth_date,
                occupation=member_input.occupation,
                employment_stability=member_input.employment_stability,
                expected_retirement_age=member_input.expected_retirement_age,
                health_risk_level=RiskLevel.LOW,
            )
            session.add(member)
            members.append(member)
        session.flush()

        primary_member = next(
            item for item in members if item.relationship == "本人"
        )
        spouse_member = next(
            (item for item in members if item.relationship == "配偶"), None
        )

        for asset_input in payload.assets:
            asset_category, liquidity, days, risk, property_use, purpose = ASSET_MAPPING[
                asset_input.category
            ]
            session.add(
                Asset(
                    **common,
                    household_id=household.id,
                    owner_member_id=primary_member.id,
                    name=asset_input.label,
                    category=asset_category,
                    subcategory=asset_input.category,
                    acquisition_cost=asset_input.amount,
                    market_value=asset_input.amount,
                    liquidity_days=days,
                    liquidity_level=liquidity,
                    risk_level=risk,
                    purpose=purpose,
                    pledged=False,
                    ownership="家庭共同" if payload.planning_scope == "family" else "本人",
                    property_use=property_use,
                )
            )

        for liability_input in payload.liabilities:
            session.add(
                Liability(
                    **common,
                    household_id=household.id,
                    borrower_member_id=primary_member.id,
                    linked_asset_id=None,
                    name=liability_input.label,
                    category=LIABILITY_MAPPING[liability_input.category],
                    outstanding_balance=liability_input.balance,
                    annual_interest_rate=liability_input.annual_interest_rate,
                    monthly_payment=liability_input.monthly_payment,
                    maturity_date=None,
                    rate_type=RateType.FLOATING,
                    prepayment_cost=ZERO,
                    is_high_interest=liability_input.annual_interest_rate
                    >= Decimal("0.10"),
                )
            )

        total_income = sum((item.annual_amount for item in payload.incomes), ZERO)
        for income_input in payload.incomes:
            income_type, stability, volatility = INCOME_MAPPING[income_input.category]
            linked_member = (
                spouse_member
                if income_input.category == "spouse_employment"
                and spouse_member is not None
                else primary_member
            )
            session.add(
                IncomeSource(
                    **common,
                    household_id=household.id,
                    member_id=linked_member.id,
                    name=income_input.label,
                    income_type=income_type,
                    amount=income_input.annual_amount,
                    frequency=CashFlowFrequency.ANNUAL,
                    stability=stability,
                    volatility=volatility,
                    interruption_probability=Decimal("0.10")
                    if income_type == IncomeType.EMPLOYMENT
                    else Decimal("0.20"),
                    cycle_correlation=Decimal("0.20"),
                    source_concentration=_ratio(income_input.annual_amount, total_income),
                    is_sustainable=True,
                )
            )

        for expense_input in payload.expenses:
            expense_category, necessity, compressible = EXPENSE_MAPPING[
                expense_input.category
            ]
            session.add(
                ExpenseItem(
                    **common,
                    household_id=household.id,
                    member_id=None,
                    name=expense_input.label,
                    amount=expense_input.annual_amount,
                    frequency=CashFlowFrequency.ANNUAL,
                    necessity=necessity,
                    compressible_ratio=compressible,
                    seasonality={},
                    category=expense_category,
                )
            )

        risk_assessment, behavior_assessment = _kyc_assessments(
            payload, household.id, common
        )
        session.add(risk_assessment)
        session.add(behavior_assessment)

        session.add(
            AuditEvent(
                household_id=household.id,
                event_type=AuditEventType.DATA_CREATED,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                entity_type="PlanningIntake",
                entity_id=household.id,
                event_version=1,
                summary="创建财富规划客户档案与家庭财务报表",
                occurred_at=utc_now(),
                data_source="system",
                is_user_confirmed=True,
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "planning_intake_conflict",
            "客户档案写入失败，请重新提交",
            status_code=409,
        ) from exc

    analysis = analyze_household(
        session,
        household.id,
        settings.financial_rules_path,
        analysis_date,
    )
    return PlanningIntakeResponse(household_id=household.id, analysis=analysis)


def _fallback_item(metric: MetricResult) -> RatioExplanationItem:
    action = metric.actions[0] if metric.actions else "结合家庭阶段与客户经理进一步核对。"
    return RatioExplanationItem(
        metric_id=cast(RatioMetricId, metric.metric_id),
        interpretation=metric.explanation,
        focus=(
            "当前结果不适用，需要先补齐分母相关资料。"
            if not metric.applicability.applicable
            else f"参考口径为：{metric.reference.reference_range}。"
        ),
        next_step=action,
    )


async def explain_financial_ratios(
    analysis: FinancialAnalysisResponse,
    request: RatioExplanationRequest,
    settings: Settings,
) -> RatioExplanationResponse:
    metric_map = {item.metric_id: item for item in analysis.metrics}
    metrics = [metric_map[item] for item in RATIO_METRIC_IDS]
    fallback = RatioExplanationOutput(items=[_fallback_item(item) for item in metrics])
    provider = get_llm_provider(settings)
    llm_request = LLMRequest(
        task="explain_verified_household_financial_ratios",
        user_text=request.question,
        context={
            "verified_statements": [
                {
                    "metric_id": item.metric_id,
                    "metric_title": item.name,
                    "formula": item.formula,
                    "result": str(item.result) if item.result is not None else None,
                    "unit": item.unit,
                    "status": item.status,
                    "reference_range": item.reference.reference_range,
                    "deterministic_explanation": item.explanation,
                }
                for item in metrics
            ],
            "risk_flags": [
                item.metric_id
                for item in metrics
                if item.status in {"attention", "warning", "critical"}
            ],
            "language": "zh-CN",
            "tone": "中国家庭理财规划师，清楚、具体、不推销产品",
            "fortune_copilot_philosophy": FORTUNE_COPILOT_PHILOSOPHY,
            "mandatory_boundaries": [
                "只解释确定性工具已经给出的金额、比率与状态，不得重新计算或编造数字",
                "结余比率是客户所称介于比率的规范名称",
                "结合中国家庭住房、养老、子女教育、赡养责任和收入稳定性解释",
                "不得把任何银行理财、基金、保险或信托统一描述为保证本金",
                "interpretation直接说明这个结果对本家庭意味着什么，六项不要重复使用表明、说明、健康水平等模板词",
                "focus只写一个值得客户核对的具体问题，不要再加需关注、值得注意等开头",
                "next_step只写一个本月可以完成的动作，不要再加建议、下一步等开头，不推销具体产品",
                "像理财规划师当面向投资者解释，句子简短、平实，避免报告腔和机械三段式复述",
            ],
        },
        schema_name="RatioExplanationOutput",
        response_json_schema=RatioExplanationOutput.model_json_schema(),
        fallback_output=fallback.model_dump(mode="json"),
    )
    response, output = await generate_validated(
        provider,
        llm_request,
        RatioExplanationOutput,
    )
    return RatioExplanationResponse(
        provider=response.provider,
        model=response.model,
        used_external_model=response.provider not in {"mock", "template_fallback"},
        degraded=response.degraded,
        items=output.items,
    )


def _fallback_plan_narrative(
    analysis: FinancialAnalysisResponse,
    planning: PlanningResponse,
    request: PlanNarrativeRequest,
) -> PlanNarrativeOutput:
    verified_plan = planning
    balance = analysis.statements.balance_sheet
    cashflow = analysis.statements.cash_flow
    account_map = {item.bucket.value: item for item in verified_plan.accounts}
    attention = [
        item.name
        for item in analysis.metrics
        if item.metric_id in RATIO_METRIC_IDS
        and item.status in {"attention", "warning", "critical"}
    ]
    goal_gap = sum(
        (max(ZERO, item.target_amount - item.prepared_amount) for item in request.goals),
        ZERO,
    )
    expense_gap = sum(
        (
            max(ZERO, item.target_amount - item.prepared_amount)
            for item in request.major_expenses
        ),
        ZERO,
    )
    daily = account_map["daily_liquidity"]
    protection = account_map["risk_protection"]
    stable = account_map["stable_goals"]
    growth = account_map["long_term_growth"]
    learning = verified_plan.investment_learning
    stable_reference = stable.reference_band
    market_context = (
        f"结合当前市场环境，本次为保本的钱设置的参考区间是"
        f"{stable_reference.minimum_ratio * Decimal('100'):.1f}%-"
        f"{stable_reference.maximum_ratio * Decimal('100'):.1f}%，"
        f"中间参考点为{stable_reference.target_ratio * Decimal('100'):.1f}%。"
        "家庭目标和资金使用日期仍然排在市场判断之前。"
        if stable_reference
        else ""
    )
    if learning.applicable and learning.eligible:
        growth_guidance = (
            f"您目前可用于长期规划的金融净值是"
            f"{format_money(verified_plan.denominators.net_financial_assets_after_debt)}，"
            f"还没有达到{format_money(verified_plan.denominators.growth_entry_threshold)}的正式起点。"
            "日常生活、保障和近期目标安排后，本次仍有"
            f"{format_money(learning.denominator_value)}可以长期不用。建议先拿出其中"
            f"{format_money(learning.recommended_amount)}作为小额学习资金，占这笔长期资金的"
            f"{(learning.recommended_ratio or ZERO) * Decimal('100'):.1f}%，不超过10%。"
            "可以先了解与您风险承受能力相匹配的宽基指数基金，重点看指数范围、净值波动、费率和计划持有多久，再决定是否分批投入。"
            "这笔小额资金主要用于认识真实波动，不承担短期收益目标。如果波动开始影响日常生活或近期目标，就先减仓或暂停。"
        )
    elif learning.applicable:
        growth_guidance = (
            f"您目前可用于长期规划的金融净值是"
            f"{format_money(verified_plan.denominators.net_financial_assets_after_debt)}，"
            f"还没有达到{format_money(verified_plan.denominators.growth_entry_threshold)}的正式起点。"
            f"本次先不新增投资，主要需要处理：{'；'.join(learning.failed_conditions)}。"
            "等这些事项稳定下来，手中仍有长期不用的资金时，可以再从不超过该笔资金10%的小仓位开始学习。"
        )
    else:
        growth_guidance = (
            f"您已具备评估长期配置的基础，本次可为生钱的钱安排{format_money(growth.recommended_amount)}。"
            "普通家庭可以先比较宽基、低成本和分散化工具，先看自己能否承受波动和持有期限，再看可能收益。"
            "页面中的70%以上只用于完成生活、保障、近期目标和优先债务后的长期资金，不是家庭总资产的配置比例。"
        )
    lifecycle_label = LIFECYCLE_LABELS.get(
        analysis.profile.lifecycle_stage,
        analysis.profile.lifecycle_stage,
    )
    return PlanNarrativeOutput(
        family_analysis=(
            f"本次规划覆盖{len(analysis.profile.members)}位家庭成员，当前处于"
            f"{lifecycle_label}。"
            "分析优先结合成员责任、就业稳定性、"
            "住房与地区生活成本，不套用统一家庭比例图。"
        ),
        goal_analysis=(
            f"本次登记{len(request.goals)}项目标，按已准备资金计算的名义缺口合计为"
            f"{format_money(goal_gap)}。目标资金应按完成日期和刚性排序，先保证近期必要目标。"
            if request.goals
            else "本次尚未登记独立理财目标，建议补充金额、日期、已准备资金和可否延期。"
        ),
        major_expense_analysis=(
            f"本次登记{len(request.major_expenses)}项大额支出，名义待准备金额合计为"
            f"{format_money(expense_gap)}。一年内计划进入保本目标层，避免与长期增长资金混用。"
            if request.major_expenses
            else "本次未登记大额支出。家庭出现购房、教育、医疗或车辆更新计划时应及时补充。"
        ),
        statement_analysis=(
            f"家庭总资产{format_money(balance.total_assets)}，总负债"
            f"{format_money(balance.total_liabilities)}，净资产{format_money(balance.net_worth)}；"
            f"年度收入{format_money(cashflow.annual_income)}，年度支出"
            f"{format_money(cashflow.annual_expenses)}，年度结余"
            f"{format_money(cashflow.annual_surplus)}。先改善现金流和负债结构，再讨论长期配置。"
        ),
        ratio_analysis_summary=(
            f"六项关键比率中需要优先关注：{'、'.join(attention)}。"
            if attention
            else "六项关键比率未出现优先预警，仍需结合家庭目标、地区与收入稳定性定期复核。"
        ),
        four_account_analysis=(
            "先把离生活最近的三笔钱安排好。"
            f"日常支付建议保留{format_money(daily.recommended_amount)}，"
            f"年度必要保障成本为{format_money(protection.recommended_amount)}，"
            f"应急、还款缓冲和五年内目标建议准备{format_money(stable.recommended_amount)}。"
            "“保本的钱”说的是资金用途，具体理财、基金或保险仍要分别查看本金风险和取用条件。"
            f"{market_context}"
            "\n\n"
            f"{growth_guidance}"
            "\n\n"
            "长期资金还要关注购买力。本次观察参考为"
            f"{verified_plan.growth_benchmark.benchmark_rate * Decimal('100'):.2f}%。"
            "这不是产品收益承诺。最低工资变化只作辅助观察，也不等同于居民消费价格指数（CPI）。"
        ),
        review_triggers=[
            "家庭成员、就业或收入稳定性发生明显变化",
            "新增贷款、提前还款或年度结余明显变化",
            "购房、教育、医疗、养老等目标金额或日期变化",
            "地区长期资金启动门槛或个人风险承受能力变化",
            "市场环境和长期资金参考条件发生明显变化",
        ],
    )


async def compose_plan_narrative(
    session: Session,
    household_id: str,
    request: PlanNarrativeRequest,
    settings: Settings,
) -> PlanNarrativeResponse:
    analysis_date = date.today()
    analysis = analyze_household(
        session,
        household_id,
        settings.financial_rules_path,
        analysis_date,
    )
    planning = plan_household(
        session,
        household_id,
        settings.financial_rules_path,
        settings.planning_rules_path,
        analysis_date,
    )
    fallback = _fallback_plan_narrative(analysis, planning, request)
    ratio_map = {item.metric_id: item for item in analysis.metrics}
    provider = get_llm_provider(settings)
    llm_request = LLMRequest(
        task="compose_fortune_copilot_household_plan_narrative",
        user_text="为本次家庭规划书生成简洁、清楚的中文分析。",
        context={
            "fortune_copilot_philosophy": FORTUNE_COPILOT_PHILOSOPHY,
            "verified_family": analysis.profile.model_dump(mode="json"),
            "verified_financial_summary": {
                "total_assets": str(analysis.statements.balance_sheet.total_assets),
                "total_liabilities": str(
                    analysis.statements.balance_sheet.total_liabilities
                ),
                "net_worth": str(analysis.statements.balance_sheet.net_worth),
                "annual_income": str(analysis.statements.cash_flow.annual_income),
                "annual_expenses": str(analysis.statements.cash_flow.annual_expenses),
                "annual_surplus": str(analysis.statements.cash_flow.annual_surplus),
            },
            "verified_ratios": [
                {
                    "metric_id": metric_id,
                    "name": ratio_map[metric_id].name,
                    "result": (
                        str(ratio_map[metric_id].result)
                        if ratio_map[metric_id].result is not None
                        else None
                    ),
                    "status": ratio_map[metric_id].status,
                    "reference_range": ratio_map[
                        metric_id
                    ].reference.reference_range,
                }
                for metric_id in RATIO_METRIC_IDS
            ],
            "client_goals": [item.model_dump(mode="json") for item in request.goals],
            "major_expenses": [
                item.model_dump(mode="json") for item in request.major_expenses
            ],
            "verified_four_accounts": [
                {
                    "name": item.name,
                    "current_amount": str(item.current_amount),
                    "target_amount": str(item.target_amount),
                    "recommended_amount": str(item.recommended_amount),
                    "rationale": item.rationale,
                    "product_education": item.product_education,
                }
                for item in planning.accounts
            ],
            "growth_entry": {
                "net_financial_assets_after_debt": str(
                    planning.denominators.net_financial_assets_after_debt
                ),
                "selected_threshold": str(
                    planning.denominators.growth_entry_threshold
                ),
                "investment_learning": planning.investment_learning.model_dump(
                    mode="json"
                ),
                "growth_70": planning.growth_70.model_dump(mode="json"),
                "purchasing_power_benchmark": planning.growth_benchmark.model_dump(
                    mode="json"
                ),
            },
            "writing_rules": [
                "family_analysis对应第一章；goal_analysis对应第二章；major_expense_analysis对应第三章",
                "statement_analysis对应第五章；ratio_analysis_summary对应第六章；four_account_analysis对应第七章",
                "只引用上下文已有事实，所有建议必须服从启动门槛和账户顺序",
                "保本账户是资金用途名称，不能扩展成所有金融产品保证本金",
                "最低工资增长信号不得写成CPI或保证收益率",
                "面向客户投资者说话，用投资者教育的语气解释为什么、怎么做和何时降低仓位，避免口号、训诫和机械罗列",
                "正式启动线以下只可解释确定性工具给出的宽基指数学习仓，不得突破10%上限或把上限写成必须配置比例",
                "用简短、通俗、中立的中文，先说客户现在可以做什么，再说明波动、费用、持有时间和退出条件",
                "不向客户展示系统、引擎、闸门、候选、工具调用或模型治理等内部术语",
            ],
        },
        schema_name="PlanNarrativeOutput",
        response_json_schema=PlanNarrativeOutput.model_json_schema(),
        fallback_output=fallback.model_dump(mode="json"),
    )
    response, output = await generate_validated(
        provider,
        llm_request,
        PlanNarrativeOutput,
    )
    output = output.model_copy(
        update={
            "four_account_analysis": fallback.four_account_analysis,
            "review_triggers": fallback.review_triggers,
        }
    )
    return PlanNarrativeResponse(
        provider=response.provider,
        model=response.model,
        used_external_model=response.provider not in {"mock", "template_fallback"},
        degraded=response.degraded,
        planning=planning,
        narrative=output,
    )
