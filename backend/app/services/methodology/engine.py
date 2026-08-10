from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.enums import AssetCategory, CashFlowFrequency, GoalRigidity, GoalType
from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import FinancialAnalysisResponse
from app.schemas.methodology import (
    FinancialJourneyAssessment,
    GRBDecisionState,
    InstitutionalCoverageSummary,
    MarketRegimeSnapshotOut,
    MethodologyArticleOut,
    MethodologyAssessment,
    PensionPolicySnapshotOut,
    PensionRiskAllocation,
    PersonalPensionPlan,
    PropertyInvestmentPolicyOut,
    PurchasingPowerComponent,
    PurchasingPowerHurdle,
    RegionalGrowthThresholdAssessment,
    RegionalMinimumWagePoint,
    RegionalMinimumWageSnapshotOut,
    ResponsibilityEntry,
    ResponsibilityLedger,
    RetirementIncomeFloorCoverage,
    ThresholdFactorEvidence,
)
from app.services.financial.utils import ZERO, money, ratio
from app.services.methodology.models import MethodologyRules, RegionalMinimumWageSnapshot
from app.services.public_data.models import AuthoritativePublicDataSnapshot


def _annual_amount(amount: Decimal, frequency: CashFlowFrequency) -> Decimal:
    multiplier = {
        CashFlowFrequency.MONTHLY: Decimal("12"),
        CashFlowFrequency.QUARTERLY: Decimal("4"),
        CashFlowFrequency.ANNUAL: Decimal("1"),
        CashFlowFrequency.ONE_TIME: Decimal("0"),
        CashFlowFrequency.IRREGULAR: Decimal("1"),
    }[frequency]
    return money(amount * multiplier)


def _bucket(value: Decimal, medium: Decimal, high: Decimal) -> str:
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"


def _regional_threshold(
    facts: HouseholdFacts,
    financial: FinancialAnalysisResponse,
    rules: MethodologyRules,
) -> RegionalGrowthThresholdAssessment:
    policy = rules.regional_growth_threshold
    profile = policy.region_profiles.get(facts.region)
    configured_tier = str(facts.planning_preferences.get("city_tier", "other_city"))
    region_code = str(
        facts.planning_preferences.get(
            "region_code",
            profile.region_code if profile else "unmapped_demo_region",
        )
    )
    city_tier = profile.city_tier if profile else configured_tier
    base = profile.base if profile else policy.city_tier_bases.get(city_tier, policy.default)
    evidence = [
        ThresholdFactorEvidence(
            factor="region",
            observed_value=f"{facts.region} / {city_tier}",
            adjustment_amount=base - policy.default,
            explanation=f"地区基准启动线 {money(base):,.2f} 元。",
        )
    ]

    adult_members = [item for item in facts.members if item.relationship != "子女"]
    employment_order = {"low": 0, "medium": 1, "high": 2}
    employment = min(
        (item.employment_stability.value for item in adult_members),
        key=lambda value: employment_order[value],
        default="medium",
    )
    employment_adjustment = policy.employment_adjustments[employment]
    evidence.append(
        ThresholdFactorEvidence(
            factor="employment_stability",
            observed_value=employment,
            adjustment_amount=employment_adjustment,
            explanation="职业稳定性越低，收入中断安全边际越高。",
            source_record_ids=[item.id for item in adult_members],
        )
    )

    max_volatility = max((item.volatility for item in facts.incomes), default=ZERO)
    volatility_bucket = _bucket(max_volatility, Decimal("0.15"), Decimal("0.30"))
    volatility_adjustment = policy.volatility_adjustments[volatility_bucket]
    evidence.append(
        ThresholdFactorEvidence(
            factor="income_volatility",
            observed_value=str(max_volatility),
            adjustment_amount=volatility_adjustment,
            explanation="使用已确认收入中的最高波动参数。",
            source_record_ids=[item.id for item in facts.incomes],
        )
    )

    interruption = max((item.interruption_probability for item in facts.incomes), default=ZERO)
    interruption_bucket = _bucket(
        interruption,
        policy.interruption_probability_breaks["medium"],
        policy.interruption_probability_breaks["high"],
    )
    interruption_adjustment = policy.interruption_adjustments[interruption_bucket]
    evidence.append(
        ThresholdFactorEvidence(
            factor="income_interruption",
            observed_value=str(interruption),
            adjustment_amount=interruption_adjustment,
            explanation="收入中断概率只能提高安全线，不用于放宽门槛。",
            source_record_ids=[item.id for item in facts.incomes],
        )
    )

    dependents = sum(
        1 for item in facts.members if item.relationship in {"子女", "父母", "其他家庭成员"}
    )
    dependent_adjustment = policy.dependent_adjustment_each * dependents
    evidence.append(
        ThresholdFactorEvidence(
            factor="dependents",
            observed_value=f"{dependents} 人",
            adjustment_amount=dependent_adjustment,
            explanation="被抚养与赡养责任增加启动安全边际。",
            source_record_ids=[
                item.id
                for item in facts.members
                if item.relationship in {"子女", "父母", "其他家庭成员"}
            ],
        )
    )

    sustainable_income_count = sum(
        1
        for item in facts.incomes
        if item.is_sustainable and _annual_amount(item.amount, item.frequency) > 0
    )
    income_structure_adjustment = (
        policy.single_income_adjustment if sustainable_income_count <= 1 else ZERO
    )
    evidence.append(
        ThresholdFactorEvidence(
            factor="household_income_structure",
            observed_value=f"{sustainable_income_count} 个可持续收入来源",
            adjustment_amount=income_structure_adjustment,
            explanation="单一可持续收入家庭需要更高安全边际。",
            source_record_ids=[item.id for item in facts.incomes if item.is_sustainable],
        )
    )

    total_assets = financial.statements.balance_sheet.total_assets
    debt_burden = (
        ratio(financial.statements.balance_sheet.total_liabilities / total_assets)
        if total_assets > ZERO
        else Decimal("1")
    )
    debt_bucket = _bucket(
        debt_burden,
        policy.debt_burden_breaks["medium"],
        policy.debt_burden_breaks["high"],
    )
    debt_adjustment = policy.debt_adjustments[debt_bucket]
    evidence.append(
        ThresholdFactorEvidence(
            factor="debt_burden",
            observed_value=str(debt_burden),
            adjustment_amount=debt_adjustment,
            explanation="总负债与家庭总资产共同决定债务安全边际。",
            source_record_ids=[item.id for item in facts.liabilities],
        )
    )

    lifecycle_adjustment = policy.lifecycle_adjustments[facts.lifecycle_stage.value]
    evidence.append(
        ThresholdFactorEvidence(
            factor="lifecycle",
            observed_value=facts.lifecycle_stage.value,
            adjustment_amount=lifecycle_adjustment,
            explanation="家庭阶段只调整安全边际，不替代真实责任。",
        )
    )
    raw = base + sum((item.adjustment_amount for item in evidence[1:]), ZERO)
    recommended_minimum = money(min(policy.maximum, max(policy.minimum, raw)))
    recommended_maximum = money(
        min(policy.maximum, recommended_minimum + policy.recommended_band_width)
    )
    selected = money(
        Decimal(str(facts.planning_preferences.get("growth_entry_threshold", policy.default)))
    )
    selected = money(min(policy.maximum, max(policy.minimum, selected)))
    effective = money(max(policy.minimum, recommended_minimum, selected))
    return RegionalGrowthThresholdAssessment(
        policy_version=policy.policy_version,
        region_code=region_code,
        region_name=facts.region,
        city_tier=city_tier,
        policy_minimum=policy.minimum,
        recommended_minimum=recommended_minimum,
        recommended_maximum=recommended_maximum,
        customer_selected_threshold=selected,
        effective_threshold=effective,
        explanation=(
            f"系统建议 {recommended_minimum / Decimal('10000'):.0f}-"
            f"{recommended_maximum / Decimal('10000'):.0f} 万元；客户选择 "
            f"{selected / Decimal('10000'):.0f} 万元；最终有效值 "
            f"{effective / Decimal('10000'):.0f} 万元。客户选择不能低于系统安全底线。"
        ),
        evidence=evidence,
    )


def _minimum_wage_snapshot(
    region_code: str,
    region_name: str,
    rules: MethodologyRules,
    analysis_date: date,
    public_data: AuthoritativePublicDataSnapshot | None,
) -> RegionalMinimumWageSnapshotOut:
    public_series = (
        public_data.regional_minimum_wages.get(region_code)
        if public_data is not None
        else None
    )
    snapshot = (
        RegionalMinimumWageSnapshot(
            region_name=public_series.region_name,
            values=[
                {"date": item.date, "monthly_amount": item.monthly_amount}
                for item in public_series.values
            ],
            source_system=public_series.source_system,
            source_reference=str(public_series.source_reference),
            observed_at=public_series.observed_at,
            effective_at=public_series.effective_at,
            ingested_at=public_series.ingested_at,
            version=public_series.version,
            data_quality=public_series.data_quality,
            is_live=public_series.is_live,
            is_demo=public_series.is_demo,
            lineage=public_series.lineage,
        )
        if public_series is not None
        else rules.regional_minimum_wage_snapshots.get(region_code)
    )
    if snapshot is None or len(snapshot.values) < 2:
        fallback = RegionalMinimumWageSnapshot(
            region_name=region_name,
            values=[],
            source_system="controlled_demo_fallback",
            source_reference="该地区时间序列未入库，使用版本化演示参数",
            observed_at=analysis_date,
            effective_at=analysis_date,
            ingested_at=datetime.combine(analysis_date, datetime.min.time(), tzinfo=UTC),
            version="minimum-wage-demo-fallback-v1.0.0",
            data_quality="degraded",
            is_live=False,
            is_demo=True,
            lineage="missing regional series -> controlled fallback",
        )
        return RegionalMinimumWageSnapshotOut(
            region_code=region_code,
            region_name=region_name,
            values=[],
            cagr=rules.minimum_wage_fallback_rate,
            period_years=ZERO,
            status="fallback",
            **fallback.model_dump(exclude={"region_name", "values"}),
        )
    points = sorted(snapshot.values, key=lambda item: item.date)
    days = Decimal((points[-1].date - points[0].date).days)
    years = days / Decimal("365.25")
    cagr_float = float(points[-1].monthly_amount / points[0].monthly_amount) ** (
        1 / float(years)
    ) - 1
    return RegionalMinimumWageSnapshotOut(
        region_code=region_code,
        region_name=snapshot.region_name,
        values=[RegionalMinimumWagePoint(**item.model_dump()) for item in points],
        cagr=ratio(Decimal(str(cagr_float))),
        period_years=ratio(years),
        status="available",
        **snapshot.model_dump(exclude={"region_name", "values"}),
    )


def _purchasing_power(
    financial: FinancialAnalysisResponse,
    wage: RegionalMinimumWageSnapshotOut,
    rules: MethodologyRules,
    public_data: AuthoritativePublicDataSnapshot | None,
) -> PurchasingPowerHurdle:
    official = financial.purchasing_power.official_cpi
    family = financial.purchasing_power.family_weighted_inflation
    official_rate = public_data.official_cpi.rate if public_data is not None else official.rate
    official_date = (
        public_data.official_cpi.period_end if public_data is not None else official.data_as_of
    )
    official_source = (
        str(public_data.official_cpi.source_reference)
        if public_data is not None
        else official.source_reference
    )
    official_version = (
        public_data.official_cpi.version
        if public_data is not None
        else financial.meta.rule_version
    )
    components = [
        PurchasingPowerComponent(
            code="official_cpi_trend",
            label="官方 CPI 趋势观察信号",
            rate=official_rate,
            data_as_of=official_date,
            source=official_source,
            version=official_version,
            is_cpi=True,
        ),
        PurchasingPowerComponent(
            code="family_weighted_expense_inflation",
            label="家庭支出加权变化",
            rate=family.rate,
            data_as_of=family.data_as_of,
            source=family.source_reference,
            version=financial.meta.rule_version,
            is_cpi=False,
        ),
        PurchasingPowerComponent(
            code="regional_minimum_wage_cagr",
            label="地区最低工资 CAGR 辅助信号",
            rate=wage.cagr,
            data_as_of=wage.observed_at,
            source=wage.source_reference,
            version=wage.version,
            status=wage.status,
            is_cpi=False,
        ),
    ]
    return PurchasingPowerHurdle(
        version=f"pph@{rules.semantic_version}",
        rate=max(item.rate for item in components),
        formula=(
            "max(official_cpi_trend, family_weighted_expense_inflation, "
            "regional_minimum_wage_cagr)"
        ),
        components=components,
        explanation=(
            "PPH 是家庭层长期购买力目标，不是单一产品的收益承诺；"
            "最低工资信号与 CPI 统计含义分离。"
        ),
    )


def _responsibility_ledger(
    facts: HouseholdFacts,
    analysis_date: date,
) -> ResponsibilityLedger:
    entries: list[ResponsibilityEntry] = []
    primary_member_id = facts.members[0].id if facts.members else None
    for responsibility in facts.responsibilities:
        entries.append(
            ResponsibilityEntry(
                responsibility_id=responsibility.id,
                responsible_member_id=responsibility.responsible_member_id,
                beneficiary=responsibility.beneficiary,
                responsibility_type=responsibility.responsibility_type,
                target_amount=responsibility.target_amount,
                minimum_acceptable_amount=responsibility.minimum_acceptable_amount,
                target_date=responsibility.target_date,
                rigidity=responsibility.rigidity.value,
                deferrable=responsibility.deferrable,
                annual_growth_assumption=responsibility.annual_growth_assumption,
                prepared_amount=responsibility.prepared_amount,
                institutional_coverage=responsibility.institutional_coverage,
                funding_source=responsibility.funding_source,
                source_record_ids=[responsibility.id],
            )
        )
    linked_goal_ids = {
        item.source_goal_id for item in facts.responsibilities if item.source_goal_id is not None
    }
    for goal in facts.goals:
        if goal.id in linked_goal_ids:
            continue
        beneficiary = "家庭"
        if goal.goal_type == GoalType.EDUCATION:
            child = next((item for item in facts.members if item.relationship == "子女"), None)
            beneficiary = child.display_name if child else "子女"
        entries.append(
            ResponsibilityEntry(
                responsibility_id=f"goal:{goal.id}",
                responsible_member_id=primary_member_id,
                beneficiary=beneficiary,
                responsibility_type=goal.goal_type.value,
                target_amount=goal.target_amount,
                minimum_acceptable_amount=goal.minimum_acceptable_amount,
                target_date=goal.target_date,
                rigidity=goal.rigidity.value,
                deferrable=goal.can_defer,
                annual_growth_assumption=goal.annual_cost_growth_rate,
                prepared_amount=goal.prepared_amount,
                institutional_coverage=ZERO,
                funding_source="goal_prepared_assets_and_future_contributions",
                source_record_ids=[goal.id],
            )
        )
    for liability in facts.liabilities:
        target_date = liability.maturity_date or date(
            min(analysis_date.year + 1, 9999), analysis_date.month, analysis_date.day
        )
        entries.append(
            ResponsibilityEntry(
                responsibility_id=f"liability:{liability.id}",
                responsible_member_id=primary_member_id,
                beneficiary="债权人",
                responsibility_type=liability.category.value,
                target_amount=liability.outstanding_balance,
                minimum_acceptable_amount=liability.outstanding_balance,
                target_date=target_date,
                rigidity=GoalRigidity.RIGID.value,
                deferrable=False,
                annual_growth_assumption=liability.annual_interest_rate,
                prepared_amount=ZERO,
                institutional_coverage=ZERO,
                funding_source="current_balance_and_debt_service_cashflow",
                source_record_ids=[liability.id],
            )
        )
    return ResponsibilityLedger(
        version="responsibility-ledger-adapter-v1.0.0",
        entries=entries,
        total_target_amount=money(sum((item.target_amount for item in entries), ZERO)),
        total_minimum_amount=money(
            sum((item.minimum_acceptable_amount for item in entries), ZERO)
        ),
        total_prepared_amount=money(sum((item.prepared_amount for item in entries), ZERO)),
        total_institutional_coverage=money(
            sum((item.institutional_coverage for item in entries), ZERO)
        ),
        explanation=(
            "V4 通过适配器将现有目标和债务投影为责任账本；"
            "新的 Responsibility 实体可逐步承接赡养、医疗和退休底线等明细。"
        ),
    )


def _institutional_and_pension(
    facts: HouseholdFacts,
    rules: MethodologyRules,
) -> tuple[InstitutionalCoverageSummary, PersonalPensionPlan]:
    wrapper_amounts: dict[str, Decimal] = {}
    pension_allocations: list[PensionRiskAllocation] = []
    for asset in facts.assets:
        wrapper = str(getattr(asset, "account_wrapper", "ordinary"))
        if asset.category == AssetCategory.PENSION_ACCOUNT and wrapper == "ordinary":
            wrapper = "personal_pension"
        wrapper_amounts[wrapper] = wrapper_amounts.get(wrapper, ZERO) + asset.market_value
        if wrapper == "personal_pension":
            pension_allocations.append(
                PensionRiskAllocation(
                    asset_id=asset.id,
                    asset_name=asset.name,
                    market_value=asset.market_value,
                    risk_level=asset.risk_level.value,
                    principal_loss_possible=bool(
                        getattr(asset, "principal_loss_possible", asset.risk_level.value != "low")
                    ),
                    liquidity_days=asset.liquidity_days,
                    lock_up=bool(getattr(asset, "lock_up", True)),
                )
            )
    social_balance = money(sum((item.balance for item in facts.social_security_accounts), ZERO))
    personal_balance = money(wrapper_amounts.get("personal_pension", ZERO))
    locked_balance = money(
        sum(
            (
                asset.market_value
                for asset in facts.assets
                if bool(getattr(asset, "lock_up", asset.category == AssetCategory.PENSION_ACCOUNT))
            ),
            ZERO,
        )
    )
    withdrawable_balance = money(
        sum(
            (
                asset.market_value
                for asset in facts.assets
                if str(getattr(asset, "account_wrapper", "ordinary"))
                in {"personal_pension", "enterprise_annuity", "occupational_annuity"}
                and not bool(getattr(asset, "lock_up", True))
            ),
            ZERO,
        )
    )
    institutional = InstitutionalCoverageSummary(
        version="institutional-coverage-v1.0.0",
        social_security_balance=social_balance,
        provident_fund_balance=money(wrapper_amounts.get("provident_fund", ZERO)),
        enterprise_annuity_balance=money(wrapper_amounts.get("enterprise_annuity", ZERO)),
        occupational_annuity_balance=money(wrapper_amounts.get("occupational_annuity", ZERO)),
        personal_pension_balance=personal_balance,
        locked_balance=locked_balance,
        withdrawable_balance=withdrawable_balance,
        retirement_income_floor=RetirementIncomeFloorCoverage(
            required_annual_floor=None,
            covered_annual_income=None,
            coverage_ratio=None,
            status="needs_review",
            explanation="当前只有账户余额与缴费事实，缺少可核验的退休待遇预测，不虚构养老收入覆盖率。",
        ),
        explanation=(
            "制度账户外壳与底层产品风险分开记账；"
            "锁定账户不会因为属于个人养老金而自动变成低风险或短期流动资产。"
        ),
    )
    policy = rules.pension_policy_snapshot
    annual_contribution = money(
        Decimal(str(facts.planning_preferences.get("personal_pension_annual_contribution", "0")))
    )
    annual_contribution = min(annual_contribution, policy.annual_contribution_limit)
    marginal_tax_rate = ratio(
        Decimal(str(facts.planning_preferences.get("marginal_tax_rate", "0.10")))
    )
    personal = PersonalPensionPlan(
        policy=PensionPolicySnapshotOut(**policy.model_dump()),
        eligibility_status="needs_review",
        annual_contribution_amount=annual_contribution,
        contribution_limit=policy.annual_contribution_limit,
        contribution_progress_ratio=ratio(
            annual_contribution / policy.annual_contribution_limit
        ),
        remaining_contribution_capacity=money(
            policy.annual_contribution_limit - annual_contribution
        ),
        assumed_marginal_tax_rate=marginal_tax_rate,
        estimated_current_year_tax_benefit=money(annual_contribution * marginal_tax_rate),
        account_balance=personal_balance,
        product_risk_allocation=pension_allocations,
        reminder_state=(
            "not_needed"
            if annual_contribution >= policy.annual_contribution_limit
            else "review_eligibility"
            if annual_contribution == ZERO
            else "contribution_available"
        ),
        retirement_projection_status="needs_more_data",
        explanation=(
            "每年限额与税率来自版本化政策快照；个人养老金是制度外壳，"
            "账户内指数基金仍可能损失本金。缺少真实缴存或退休参数时保持待复核。"
        ),
    )
    return institutional, personal


def _journey(
    facts: HouseholdFacts,
    financial: FinancialAnalysisResponse,
    pfnw: Decimal,
    threshold: Decimal,
) -> FinancialJourneyAssessment:
    annual_surplus = financial.statements.cash_flow.annual_surplus
    has_high_interest = any(
        item.is_high_interest and item.outstanding_balance > ZERO for item in facts.liabilities
    )
    complex_structure = any(
        item.category in {AssetCategory.TRUST, AssetCategory.INVESTMENT_PROPERTY}
        for item in facts.assets
    ) or financial.statements.balance_sheet.net_worth >= Decimal("5000000")
    if pfnw <= ZERO or has_high_interest or annual_surplus <= ZERO:
        return FinancialJourneyAssessment(
            state="financial_recovery",
            label="财务修复",
            investment_mode="no_investment_sales",
            explanation="先修复负债、现金流和基础保障，不开放新增风险投资。",
        )
    if pfnw < threshold:
        return FinancialJourneyAssessment(
            state="wealth_accumulation",
            label="财富积累",
            investment_mode="safety_and_learning",
            explanation="补足安全垫与目标资金；只有全部学习仓条件通过时才允许小额学习。",
        )
    if complex_structure:
        return FinancialJourneyAssessment(
            state="complex_wealth_management",
            label="复杂财富管理",
            investment_mode="human_in_loop",
            explanation="家庭结构或资产复杂，需要客户经理、风控与持牌专业人员共同复核。",
        )
    return FinancialJourneyAssessment(
        state="wealth_growth",
        label="财富增长",
        investment_mode="full_portfolio",
        explanation="PFNW 达到有效启动线；仍需通过所有家庭安全与适当性闸门。",
    )


def _grb_decision_state(
    facts: HouseholdFacts,
    responsibility_ledger: ResponsibilityLedger,
) -> GRBDecisionState:
    dated_entries = [item for item in responsibility_ledger.entries if item.target_date]
    nearest_goal_date = min((item.target_date for item in dated_entries), default=None)
    rigid_goal_count = sum(item.rigidity == GoalRigidity.RIGID.value for item in dated_entries)
    goal_count = len(dated_entries)

    latest_risk = facts.risk_assessments[-1] if facts.risk_assessments else None
    latest_behavior = facts.behavior_assessments[-1] if facts.behavior_assessments else None
    revealed_score = (
        latest_behavior.experiment_score
        if latest_behavior is not None
        else latest_risk.behavior_score
        if latest_risk is not None
        else None
    )

    if latest_risk is not None:
        risk_status = "ready"
        risk_summary = (
            "已同时读取客观风险承担能力、主观风险意愿和现行风险上限；"
            "具体产品仍须通过正式适当性检查。"
        )
    else:
        risk_status = "needs_input"
        risk_summary = "尚未形成正式风险评估，不开放具体高波动产品建议。"

    if latest_behavior is not None:
        behavior_status = "ready"
        behavior_summary = (
            "已完成问卷与下跌情景实验；行为结果只允许维持或下调风险预算。"
        )
        detected_biases = list(latest_behavior.detected_biases)
    elif latest_risk is not None:
        behavior_status = "partial"
        behavior_summary = "暂用风险评估中的行为分量，完成选择实验后再更新。"
        detected_biases = []
    else:
        behavior_status = "needs_input"
        behavior_summary = "尚无行为观察，不以自述偏好推高长期风险预算。"
        detected_biases = []

    return GRBDecisionState(
        version="grb-dynamic-account-v1.0.0",
        formula="Allocation = π(Goal, Risk, Behavior, Household State)",
        goal_count=goal_count,
        rigid_goal_count=rigid_goal_count,
        nearest_goal_date=nearest_goal_date,
        goal_status="ready" if goal_count else "needs_input",
        goal_summary=(
            f"已识别 {goal_count} 项有期限责任，其中 {rigid_goal_count} 项为刚性责任。"
            if goal_count
            else "尚未录入有金额和期限的家庭目标。"
        ),
        risk_status=risk_status,
        capacity_score=latest_risk.capacity_score if latest_risk is not None else None,
        willingness_score=latest_risk.willingness_score if latest_risk is not None else None,
        effective_risk_limit=(
            latest_risk.final_risk_limit.value if latest_risk is not None else None
        ),
        risk_summary=risk_summary,
        behavior_status=behavior_status,
        revealed_behavior_score=revealed_score,
        detected_biases=detected_biases,
        behavior_summary=behavior_summary,
    )


def assess_methodology(
    facts: HouseholdFacts,
    financial: FinancialAnalysisResponse,
    rules: MethodologyRules,
    analysis_date: date,
    plannable_financial_net_worth: Decimal,
    public_data: AuthoritativePublicDataSnapshot | None = None,
) -> MethodologyAssessment:
    threshold = _regional_threshold(facts, financial, rules)
    wage = _minimum_wage_snapshot(
        threshold.region_code,
        threshold.region_name,
        rules,
        analysis_date,
        public_data,
    )
    purchasing_power = _purchasing_power(financial, wage, rules, public_data)
    institutional, pension = _institutional_and_pension(facts, rules)
    responsibility_ledger = _responsibility_ledger(facts, analysis_date)
    return MethodologyAssessment(
        optimization_objective=(
            "在四账户前置边界内，提高家庭现金流连续性、风险保障、目标实现概率、"
            "财务韧性与长期实际购买力。"
        ),
        methodology_code=rules.code,
        methodology_version=rules.semantic_version,
        formula_version=rules.formula_version,
        public_data_snapshot_version=(
            public_data.snapshot_version
            if public_data is not None
            else "methodology-embedded-demo-snapshot"
        ),
        constitution=[MethodologyArticleOut(**item.model_dump()) for item in rules.constitution],
        regional_threshold=threshold,
        market_regime=MarketRegimeSnapshotOut(**rules.market_regime_snapshot.model_dump()),
        minimum_wage_snapshot=wage,
        purchasing_power_hurdle=purchasing_power,
        responsibility_ledger=responsibility_ledger,
        institutional_coverage=institutional,
        personal_pension=pension,
        property_policy=PropertyInvestmentPolicyOut(
            **rules.property_policy_snapshot.model_dump()
        ),
        financial_journey=_journey(
            facts,
            financial,
            plannable_financial_net_worth,
            threshold.effective_threshold,
        ),
        grb=_grb_decision_state(facts, responsibility_ledger),
    )
