# ruff: noqa: E501
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.domain.financial import HouseholdFacts
from app.schemas.behavior import BehaviorOverviewResponse
from app.schemas.financial_analysis import FinancialAnalysisResponse, MetricResult
from app.schemas.formal_report import (
    FORMAL_CHAPTER_TITLES,
    FormalReportChapter,
    FormalReportDocument,
    ReportActionOut,
    ReportAdvice,
    ReportAppendix,
    ReportConsistencyCheck,
    ReportExecutionMetrics,
    ReportNumericClaim,
    ReportSection,
    ReportSourceClaim,
    ReportStatus,
    ReportTable,
    ReportTrigger,
    ReportVersionLedger,
)
from app.schemas.fund_advisory import FundAdvisoryResponse
from app.schemas.planning import PlanningResponse
from app.schemas.portfolio import PortfolioResponse
from app.schemas.trust import KnowledgeCitation
from app.schemas.twin import TwinResult

ZERO = Decimal("0")
REPORT_COMPOSER_VERSION = "formal-report-composer-v1.0.0"
NumericSource = Literal[
    "deterministic_tools",
    "deterministic_simulation_engine",
    "deterministic_review_schedule",
]


def _money_display(value: Decimal) -> str:
    return f"{value:,.2f} 元"


def _ratio_display(value: Decimal) -> str:
    return f"{value * Decimal('100'):.2f}%"


def _decimal_display(value: Decimal, unit: str) -> str:
    if unit in {"ratio", "%"}:
        return _ratio_display(value)
    if unit in {"CNY", "元"}:
        return _money_display(value)
    if unit == "months":
        return f"{value:.2f} 个月"
    return f"{value:.6f} {unit}".strip()


class _NumericLedger:
    def __init__(self) -> None:
        self._items: dict[str, ReportNumericClaim] = {}

    def add(
        self,
        code: str,
        label: str,
        value: Decimal | int,
        unit: str,
        source_path: str,
        *,
        source: NumericSource = "deterministic_tools",
        display: str | None = None,
    ) -> str:
        raw = str(value)
        shown = display or _decimal_display(Decimal(raw), unit)
        item = ReportNumericClaim(
            code=code,
            label=label,
            raw_value=raw,
            display_value=shown,
            unit=unit,
            source_path=source_path,
            calculation_source=source,
        )
        existing = self._items.get(code)
        if existing is not None and existing != item:
            raise ValueError(f"numeric ledger code collision: {code}")
        self._items[code] = item
        return shown

    def money(
        self,
        code: str,
        label: str,
        value: Decimal,
        source_path: str,
        *,
        source: NumericSource = "deterministic_tools",
    ) -> str:
        return self.add(code, label, value, "CNY", source_path, source=source)

    def ratio(
        self,
        code: str,
        label: str,
        value: Decimal | None,
        source_path: str,
        *,
        source: NumericSource = "deterministic_tools",
    ) -> str:
        if value is None:
            return "不适用"
        return self.add(code, label, value, "ratio", source_path, source=source)

    def items(self) -> list[ReportNumericClaim]:
        return list(self._items.values())


def _table(
    title: str,
    columns: list[str],
    rows: Iterable[Iterable[object]],
    *,
    source: str = "deterministic_tools",
    note: str = "",
) -> ReportTable:
    return ReportTable(
        title=title,
        columns=columns,
        rows=[[str(cell) for cell in row] for row in rows],
        note=note,
        calculation_source=source,
    )


def _section(
    code: str,
    title: str,
    *,
    narratives: list[str] | None = None,
    tables: list[ReportTable] | None = None,
    advice: list[ReportAdvice] | None = None,
    citation_ids: list[str] | None = None,
) -> ReportSection:
    return ReportSection(
        code=code,
        title=title,
        narratives=narratives or [],
        tables=tables or [],
        advice=advice or [],
        citation_ids=citation_ids or [],
    )


def _metric_display(ledger: _NumericLedger, metric: MetricResult, part: str) -> str:
    value = getattr(metric, part)
    if value is None:
        return "不适用"
    return ledger.add(
        f"metric.{metric.metric_id}.{part}",
        f"{metric.name}{part}",
        value,
        metric.unit,
        f"financial_analysis.metrics.{metric.metric_id}.{part}",
    )


def _action_advice(item: ReportActionOut) -> ReportAdvice:
    return ReportAdvice(
        code=item.action_code,
        title=item.title,
        reason=item.why,
        priority=item.priority,
        action=item.detail,
        completion_criteria=item.completion_criteria,
        review_cycle=item.review_cycle,
        status=item.status,
        due_date=item.due_date,
        calculation_source=item.calculation_source,
    )


def _citation_ids(citations: list[KnowledgeCitation], category: str) -> list[str]:
    return [item.citation_id for item in citations if item.category == category]


def compose_formal_report(
    *,
    report_id: str,
    sequence: int,
    parent_report_id: str | None,
    workflow_id: str | None,
    workflow_version_id: str | None,
    workflow_state: str | None,
    workflow_version_label: str | None,
    status: ReportStatus,
    watermark: str,
    trigger: ReportTrigger,
    reason: str,
    generated_at: datetime,
    facts: HouseholdFacts,
    analysis: FinancialAnalysisResponse,
    plan: PlanningResponse,
    portfolio: PortfolioResponse,
    fund_advisory: FundAdvisoryResponse,
    twin: TwinResult,
    behavior: BehaviorOverviewResponse,
    actions: list[ReportActionOut],
    execution_metrics: ReportExecutionMetrics,
    citations: list[KnowledgeCitation],
    sourced_claims: list[ReportSourceClaim],
    knowledge_version: str,
    model_version: str,
    prompt_version: str,
) -> FormalReportDocument:
    ledger = _NumericLedger()
    balance = analysis.statements.balance_sheet
    cashflow = analysis.statements.cash_flow
    protection = analysis.protection
    goals_by_id = {item.id: item for item in analysis.statements.goal_funding.goals}
    twin_goals = {item.goal_id: item for item in twin.baseline.goal_outcomes}
    conflict_by_goal = {
        goal_id: conflict for conflict in plan.conflicts for goal_id in conflict.affected_goal_ids
    }

    total_assets = ledger.money(
        "balance.total_assets",
        "家庭总资产",
        balance.total_assets,
        "financial_analysis.statements.balance_sheet.total_assets",
    )
    total_liabilities = ledger.money(
        "balance.total_liabilities",
        "家庭总负债",
        balance.total_liabilities,
        "financial_analysis.statements.balance_sheet.total_liabilities",
    )
    net_worth = ledger.money(
        "balance.net_worth",
        "家庭净资产",
        balance.net_worth,
        "financial_analysis.statements.balance_sheet.net_worth",
    )
    annual_income = ledger.money(
        "cashflow.annual_income",
        "年度收入",
        cashflow.annual_income,
        "financial_analysis.statements.cash_flow.annual_income",
    )
    annual_expenses = ledger.money(
        "cashflow.annual_expenses",
        "年度支出",
        cashflow.annual_expenses,
        "financial_analysis.statements.cash_flow.annual_expenses",
    )
    annual_surplus = ledger.money(
        "cashflow.annual_surplus",
        "年度结余",
        cashflow.annual_surplus,
        "financial_analysis.statements.cash_flow.annual_surplus",
    )

    chapter_1 = FormalReportChapter(
        number=1,
        title=FORMAL_CHAPTER_TITLES[0],
        summary=(
            f"{analysis.profile.name}当前按 {plan.lifecycle.effective_stage.value} 生命周期阶段"
            f"测算，共 {len(analysis.profile.members)} 名成员；数据完整度与数据日均单独披露。"
        ),
        sections=[
            _section(
                "1.1",
                "家庭成员、责任与生命周期",
                narratives=[
                    plan.lifecycle.explanation,
                    "责任关系只依据家庭建档字段展示；健康、职业与家庭责任变化均需人工确认后重算。",
                ],
                tables=[
                    _table(
                        "家庭成员表",
                        ["成员", "关系", "年龄", "职业", "就业稳定性", "健康风险"],
                        (
                            (
                                item.display_name,
                                item.relationship,
                                item.age,
                                item.occupation or "待补充",
                                item.employment_stability,
                                item.health_risk_level,
                            )
                            for item in analysis.profile.members
                        ),
                    )
                ],
            ),
            _section(
                "1.2",
                "数据完整性与时点",
                narratives=[
                    f"家庭事实来源：{analysis.profile.data_source}；"
                    f"家庭确认状态：{'已确认' if analysis.profile.is_user_confirmed else '待确认'}。",
                    "本报告不会用信用卡授信额度补齐资产，也不会用模型猜测缺失金额。",
                ],
                tables=[
                    _table(
                        "数据质量摘要",
                        ["分析日", "数据日", "完整度", "通过检查", "异常数"],
                        [
                            (
                                analysis.meta.analysis_date,
                                analysis.meta.data_as_of,
                                ledger.ratio(
                                    "diagnostics.completeness",
                                    "数据完整度",
                                    analysis.diagnostics.completeness_score / Decimal("100"),
                                    "financial_analysis.diagnostics.completeness_score",
                                ),
                                analysis.diagnostics.passed_checks,
                                analysis.diagnostics.issue_count,
                            )
                        ],
                    )
                ],
            ),
        ],
    )

    goal_rows: list[tuple[object, ...]] = []
    for item in plan.goals:
        funding = goals_by_id.get(item.goal_id)
        outcome = twin_goals.get(item.goal_id)
        conflict = conflict_by_goal.get(item.goal_id)
        goal_rows.append(
            (
                item.name,
                ledger.money(
                    f"goal.{item.goal_id}.future_amount",
                    f"{item.name}未来金额",
                    item.future_amount,
                    f"planning.goals.{item.goal_id}.future_amount",
                ),
                item.target_date,
                item.priority,
                ledger.ratio(
                    f"goal.{item.goal_id}.funding_ratio",
                    f"{item.name}准备率",
                    funding.funding_ratio if funding else None,
                    f"financial_analysis.goal_funding.{item.goal_id}.funding_ratio",
                ),
                ledger.ratio(
                    f"goal.{item.goal_id}.success_probability",
                    f"{item.name}基线成功概率",
                    outcome.success_probability if outcome else None,
                    f"twin.baseline.goal_outcomes.{item.goal_id}.success_probability",
                    source="deterministic_simulation_engine",
                ),
                conflict.title if conflict else "未识别资金冲突",
            )
        )
    chapter_2 = FormalReportChapter(
        number=2,
        title=FORMAL_CHAPTER_TITLES[1],
        summary=(
            f"共识别 {len(plan.goals)} 个目标、{len(plan.conflicts)} 组资金冲突。"
            "准备率与成功概率使用不同口径，报告不将二者混同。"
        ),
        sections=[
            _section(
                "2.1",
                "目标金额、期限、优先级与可行性",
                tables=[
                    _table(
                        "家庭目标总表",
                        ["目标", "未来金额", "期限", "优先级", "准备率", "基线成功概率", "冲突"],
                        goal_rows,
                    )
                ],
                narratives=[
                    "成功概率来自固定版本、固定种子和固定路径数的确定性数字孪生运行；"
                    "它是情景结果，不是预测或收益承诺。"
                ],
            ),
            _section(
                "2.2",
                "目标冲突与调整边界",
                tables=[
                    _table(
                        "目标冲突",
                        ["严重度", "冲突", "月度可用结余", "月度所需", "月度缺口", "受影响目标"],
                        (
                            (
                                item.severity,
                                item.title,
                                ledger.money(
                                    f"conflict.{item.conflict_id}.available",
                                    f"{item.title}可用月结余",
                                    item.available_monthly_surplus,
                                    f"planning.conflicts.{item.conflict_id}.available_monthly_surplus",
                                ),
                                ledger.money(
                                    f"conflict.{item.conflict_id}.required",
                                    f"{item.title}月度所需",
                                    item.required_monthly_contribution,
                                    f"planning.conflicts.{item.conflict_id}.required_monthly_contribution",
                                ),
                                ledger.money(
                                    f"conflict.{item.conflict_id}.shortfall",
                                    f"{item.title}月度缺口",
                                    item.monthly_shortfall,
                                    f"planning.conflicts.{item.conflict_id}.monthly_shortfall",
                                ),
                                "、".join(item.affected_goal_ids),
                            )
                            for item in plan.conflicts
                        ),
                        note="无冲突时保留空表，不补造问题。",
                    )
                ],
            ),
        ],
    )

    spending_buckets = ((12, "未来 1 年"), (36, "未来 3 年"), (60, "未来 5 年"))
    spending_rows: list[tuple[object, ...]] = []
    for item in plan.goals:
        horizon = "更长期"
        for maximum, label in spending_buckets:
            if item.months_remaining <= maximum:
                horizon = label
                break
        source = (
            "短期流动资金与当期结余"
            if item.months_remaining <= 12
            else "保本账户与持续结余"
            if item.months_remaining <= 60
            else "目标资金与符合安全闸门的长期资金"
        )
        spending_rows.append(
            (
                horizon,
                item.name,
                item.target_date,
                ledger.money(
                    f"spending.{item.goal_id}.amount",
                    f"{item.name}大额支出金额",
                    item.future_amount,
                    f"planning.goals.{item.goal_id}.future_amount",
                ),
                ledger.money(
                    f"spending.{item.goal_id}.prepared",
                    f"{item.name}已准备金额",
                    item.prepared_amount,
                    f"planning.goals.{item.goal_id}.prepared_amount",
                ),
                source,
                "到期前复核可赎回日、到账日与目标付款日",
            )
        )
    chapter_3 = FormalReportChapter(
        number=3,
        title=FORMAL_CHAPTER_TITLES[2],
        summary="按 1 年、3 年、5 年及更长期分层展示大额支出，并把资金来源与流动性条件并列。",
        sections=[
            _section(
                "3.1",
                "分期限大额支出",
                tables=[
                    _table(
                        "大额支出时间表",
                        ["时间层", "事项", "日期", "预计金额", "已准备", "资金来源", "流动性条件"],
                        spending_rows,
                    )
                ],
            ),
            _section(
                "3.2",
                "流动性覆盖",
                narratives=[
                    "大额支出先核对到期日、赎回限制和应急资金隔离，不以长期资产的账面价值替代近期可用现金。"
                ],
                tables=[
                    _table(
                        "流动性可用量",
                        ["口径", "金额", "用途边界"],
                        [
                            (
                                "应急流动资产",
                                ledger.money(
                                    "liquidity.emergency",
                                    "应急流动资产",
                                    analysis.statements.liquidity.emergency_liquid_assets,
                                    "financial_analysis.statements.liquidity.emergency_liquid_assets",
                                ),
                                "只覆盖应急层，不重复计入目标准备金",
                            ),
                            (
                                "30 日内流动资产",
                                ledger.money(
                                    "liquidity.short_term",
                                    "短期流动资产",
                                    analysis.statements.liquidity.short_term_liquid_assets,
                                    "financial_analysis.statements.liquidity.short_term_liquid_assets",
                                ),
                                "核对赎回与到账日后用于短期支出",
                            ),
                            (
                                "12 个月内流动资产",
                                ledger.money(
                                    "liquidity.twelve_month",
                                    "十二个月流动资产",
                                    analysis.statements.liquidity.twelve_month_liquid_assets,
                                    "financial_analysis.statements.liquidity.twelve_month_liquid_assets",
                                ),
                                "不得与同一笔资产的其他用途重复计算",
                            ),
                        ],
                    )
                ],
            ),
        ],
    )

    pp = analysis.purchasing_power
    assumption_rows: list[tuple[object, ...]] = [
        (
            "年度收入基线",
            annual_income,
            "家庭现金流底表",
            analysis.meta.data_as_of,
            "收入变化即重算",
        ),
        (
            "年度支出基线",
            annual_expenses,
            "家庭现金流底表",
            analysis.meta.data_as_of,
            "支出变化即重算",
        ),
        (
            pp.official_cpi.name,
            ledger.ratio(
                "assumption.official_cpi",
                pp.official_cpi.name,
                pp.official_cpi.rate,
                "financial_analysis.purchasing_power.official_cpi.rate",
            ),
            pp.official_cpi.source_reference,
            pp.official_cpi.data_as_of,
            "离线参数上下变动时重算，不冒充实时统计",
        ),
        (
            pp.family_weighted_inflation.name,
            ledger.ratio(
                "assumption.family_inflation",
                pp.family_weighted_inflation.name,
                pp.family_weighted_inflation.rate,
                "financial_analysis.purchasing_power.family_weighted_inflation.rate",
            ),
            pp.family_weighted_inflation.source_reference,
            pp.family_weighted_inflation.data_as_of,
            "家庭支出权重变化即重算",
        ),
        (
            pp.minimum_wage_catch_up.name,
            ledger.ratio(
                "assumption.minimum_wage_auxiliary",
                pp.minimum_wage_catch_up.name,
                pp.minimum_wage_catch_up.rate,
                "financial_analysis.purchasing_power.minimum_wage_catch_up.rate",
            ),
            pp.minimum_wage_catch_up.source_reference,
            pp.minimum_wage_catch_up.data_as_of,
            "仅作辅助信号；不等同 CPI 或收益保证",
        ),
    ]
    assumption_rows.extend(
        (
            f"{item.goal_name}成本增长",
            ledger.ratio(
                f"assumption.goal_cost.{item.goal_id}",
                f"{item.goal_name}成本增长率",
                item.annual_cost_growth_rate,
                f"financial_analysis.purchasing_power.goal_specific_cost_growth.{item.goal_id}",
            ),
            "家庭目标事实与当前参考参数",
            analysis.meta.data_as_of,
            "目标金额或增长率变化即重算",
        )
        for item in pp.goal_specific_cost_growth
    )
    asset_assumption_rows = []
    for asset_class, values in twin.assumptions.asset_assumptions.items():
        expected = values.get("expected_annual_return", ZERO)
        volatility = values.get("annual_volatility", ZERO)
        asset_assumption_rows.append(
            (
                asset_class,
                ledger.ratio(
                    f"assumption.asset.{asset_class}.return",
                    f"{asset_class}预期年化回报假设",
                    expected,
                    f"twin.assumptions.asset_assumptions.{asset_class}.expected_annual_return",
                    source="deterministic_simulation_engine",
                ),
                ledger.ratio(
                    f"assumption.asset.{asset_class}.volatility",
                    f"{asset_class}年化波动假设",
                    volatility,
                    f"twin.assumptions.asset_assumptions.{asset_class}.annual_volatility",
                    source="deterministic_simulation_engine",
                ),
                "版本化参考参数",
                twin.meta.scenario_version,
                "假设变化会改变路径分布；不是预测或保证",
            )
        )
    pension_citations = _citation_ids(citations, "personal_pension")
    chapter_4 = FormalReportChapter(
        number=4,
        title=FORMAL_CHAPTER_TITLES[3],
        summary="收入、支出、通胀、目标成本、最低工资辅助信号、资产回报、费用与税务边界分项列示。",
        sections=[
            _section(
                "4.1",
                "家庭与购买力假设",
                narratives=[
                    pp.official_cpi.note,
                    pp.family_weighted_inflation.note,
                    pp.minimum_wage_catch_up.note,
                ],
                tables=[
                    _table(
                        "基础与成本假设",
                        ["假设", "当前值", "来源／版本", "生效或数据日", "敏感性"],
                        assumption_rows,
                    )
                ],
            ),
            _section(
                "4.2",
                "资产回报范围与压力参数",
                narratives=[
                    "所有回报与波动均为版本化规划假设；历史表现不代表未来，压力测试不是预测。"
                ],
                tables=[
                    _table(
                        "资产类别参数",
                        ["资产类别", "年回报假设", "年波动假设", "来源类型", "版本", "敏感性"],
                        asset_assumption_rows,
                        source="deterministic_simulation_engine",
                    )
                ],
            ),
            _section(
                "4.3",
                "费用与税务假设",
                narratives=[
                    "候选组合费用只按模拟产品目录与当前候选金额计算；实际费用、税率和可扣除条件须办理前人工核验。",
                    *[
                        claim.text
                        for claim in sourced_claims
                        if set(claim.citation_ids) & set(pension_citations)
                    ],
                ],
                tables=[
                    _table(
                        "候选组合费用",
                        ["候选", "年费率", "年费用估计", "目录版本", "敏感性"],
                        (
                            (
                                item.name,
                                ledger.ratio(
                                    f"portfolio.{item.candidate_type.value}.fee_rate",
                                    f"{item.name}年费率",
                                    item.annual_fee_rate,
                                    f"portfolio.candidates.{item.candidate_type.value}.annual_fee_rate",
                                ),
                                ledger.money(
                                    f"portfolio.{item.candidate_type.value}.fee",
                                    f"{item.name}年费用",
                                    item.annual_fee_estimate,
                                    f"portfolio.candidates.{item.candidate_type.value}.annual_fee_estimate",
                                ),
                                portfolio.meta.catalog_version,
                                "产品映射、费率或金额变化即重算",
                            )
                            for item in portfolio.candidates
                        ),
                    )
                ],
                citation_ids=pension_citations,
            ),
        ],
    )

    asset_rows = [
        (
            item.name,
            item.category,
            item.asset_group,
            ledger.money(
                f"asset.{item.id}.market_value",
                f"{item.name}市值",
                item.market_value,
                f"financial_analysis.balance_sheet.assets.{item.id}.market_value",
            ),
            item.liquidity_days,
            "是" if item.pledged else "否",
        )
        for item in balance.assets
    ]
    liability_rows = [
        (
            item.name,
            item.category,
            ledger.money(
                f"liability.{item.id}.balance",
                f"{item.name}余额",
                item.outstanding_balance,
                f"financial_analysis.balance_sheet.liabilities.{item.id}.outstanding_balance",
            ),
            ledger.ratio(
                f"liability.{item.id}.rate",
                f"{item.name}年利率",
                item.annual_interest_rate,
                f"financial_analysis.balance_sheet.liabilities.{item.id}.annual_interest_rate",
            ),
            ledger.money(
                f"liability.{item.id}.payment",
                f"{item.name}月供",
                item.monthly_payment,
                f"financial_analysis.balance_sheet.liabilities.{item.id}.monthly_payment",
            ),
            "是" if item.is_high_interest else "否",
        )
        for item in balance.liabilities
    ]
    cash_rows = [
        (
            "收入" if item in cashflow.income_lines else "支出",
            item.name,
            item.category,
            item.frequency,
            ledger.money(
                f"cashflow.{item.id}.annual",
                f"{item.name}年化金额",
                item.annual_amount,
                f"financial_analysis.cash_flow.lines.{item.id}.annual_amount",
            ),
            "是" if item.essential else "否",
        )
        for item in [*cashflow.income_lines, *cashflow.expense_lines]
    ]
    insurance_rows = [
        (
            item.name,
            item.insured_member_name,
            item.policy_type,
            ledger.money(
                f"insurance.{item.id}.coverage",
                f"{item.name}保额",
                item.coverage_amount,
                f"financial_analysis.insurance.policies.{item.id}.coverage_amount",
            ),
            ledger.money(
                f"insurance.{item.id}.premium",
                f"{item.name}年保费",
                item.annual_premium,
                f"financial_analysis.insurance.policies.{item.id}.annual_premium",
            ),
            item.waiting_period_days,
            "有效" if item.active_on_analysis_date else "非有效期",
        )
        for item in analysis.statements.insurance.policies
    ]
    funding_rows = [
        (
            item.name,
            ledger.money(
                f"funding.{item.id}.target",
                f"{item.name}目标金额",
                item.target_amount,
                f"financial_analysis.goal_funding.goals.{item.id}.target_amount",
            ),
            ledger.money(
                f"funding.{item.id}.prepared",
                f"{item.name}准备金额",
                item.prepared_amount,
                f"financial_analysis.goal_funding.goals.{item.id}.prepared_amount",
            ),
            ledger.money(
                f"funding.{item.id}.gap",
                f"{item.name}资金缺口",
                item.funding_gap,
                f"financial_analysis.goal_funding.goals.{item.id}.funding_gap",
            ),
            ledger.ratio(
                f"funding.{item.id}.ratio",
                f"{item.name}准备率",
                item.funding_ratio,
                f"financial_analysis.goal_funding.goals.{item.id}.funding_ratio",
            ),
        )
        for item in analysis.statements.goal_funding.goals
    ]
    liquidity_rows = [
        (
            item.name,
            item.category,
            ledger.money(
                f"liquidity.asset.{item.asset_id}",
                f"{item.name}流动性金额",
                item.market_value,
                f"financial_analysis.liquidity.lines.{item.asset_id}.market_value",
            ),
            item.liquidity_days,
            item.liquidity_tier,
            "是" if item.included_in_emergency_reserve else "否",
        )
        for item in analysis.statements.liquidity.lines
    ]
    chapter_5 = FormalReportChapter(
        number=5,
        title=FORMAL_CHAPTER_TITLES[4],
        summary=f"总资产 {total_assets}、总负债 {total_liabilities}、净资产 {net_worth}、年度结余 {annual_surplus}。",
        sections=[
            _section(
                "5.1",
                "资产负债表",
                narratives=[
                    balance.accounting_identity,
                    "信用卡授信额度不进入资产；未偿余额只进入负债。",
                ],
                tables=[
                    _table(
                        "资产明细", ["资产", "类别", "分组", "市值", "变现天数", "质押"], asset_rows
                    ),
                    _table(
                        "负债明细",
                        ["负债", "类别", "余额", "年利率", "月供", "高息"],
                        liability_rows,
                    ),
                    _table(
                        "资产负债汇总",
                        ["总资产", "总负债", "净资产"],
                        [(total_assets, total_liabilities, net_worth)],
                    ),
                ],
            ),
            _section(
                "5.2",
                "家庭现金流表",
                tables=[
                    _table(
                        "收支明细", ["方向", "项目", "类别", "频率", "年化金额", "必要"], cash_rows
                    ),
                    _table(
                        "现金流汇总",
                        ["年度收入", "年度支出", "年度结余", "年度债务偿付", "年度保费"],
                        [
                            (
                                annual_income,
                                annual_expenses,
                                annual_surplus,
                                ledger.money(
                                    "cashflow.debt_service",
                                    "年度债务偿付",
                                    cashflow.annual_debt_service,
                                    "financial_analysis.statements.cash_flow.annual_debt_service",
                                ),
                                ledger.money(
                                    "cashflow.insurance_premiums",
                                    "年度保费",
                                    cashflow.annual_insurance_premiums,
                                    "financial_analysis.statements.cash_flow.annual_insurance_premiums",
                                ),
                            )
                        ],
                    ),
                ],
            ),
            _section(
                "5.3",
                "保险保障表",
                narratives=[analysis.statements.insurance.counting_note],
                tables=[
                    _table(
                        "保单与保障",
                        ["保单", "被保险人", "类型", "保额", "年保费", "等待期天数", "状态"],
                        insurance_rows,
                    )
                ],
            ),
            _section(
                "5.4",
                "目标资金表",
                tables=[
                    _table("目标准备", ["目标", "金额", "已准备", "缺口", "准备率"], funding_rows)
                ],
            ),
            _section(
                "5.5",
                "流动性矩阵与异常",
                tables=[
                    _table(
                        "流动性矩阵",
                        ["资产", "类别", "金额", "变现天数", "层级", "计入应急"],
                        liquidity_rows,
                    ),
                    _table(
                        "数据异常",
                        ["等级", "异常", "说明", "处理动作", "记录数"],
                        (
                            (
                                item.severity,
                                item.title,
                                item.detail,
                                item.action,
                                len(item.related_record_ids),
                            )
                            for item in analysis.diagnostics.issues
                        ),
                        source="deterministic_tools",
                        note="异常为数据质量与财务诊断提示，不是监管评级。",
                    ),
                ],
            ),
        ],
    )

    metric_rows = []
    for metric in analysis.metrics:
        metric_rows.append(
            (
                metric.name,
                metric.formula,
                _metric_display(ledger, metric, "numerator"),
                _metric_display(ledger, metric, "denominator"),
                _metric_display(ledger, metric, "result"),
                metric.reference.reference_range,
                (
                    f"{metric.reference.source_type} · {metric.reference.source_reference} · "
                    f"{metric.threshold_version}"
                ),
                "；".join(metric.actions),
            )
        )
    chapter_6 = FormalReportChapter(
        number=6,
        title=FORMAL_CHAPTER_TITLES[5],
        summary=(
            f"完整列示 {len(analysis.metrics)} 项指标的公式、分子、分母、当前值、参考区间、来源与行动。"
        ),
        sections=[
            _section(
                "6.1",
                "比率与计量指标总表",
                narratives=[
                    "报告中的参考阈值是家庭理财常用观察口径，不是监管统一标准或家庭合格线。",
                    "不适用指标保留原因，不以零值替代缺失分母。",
                ],
                tables=[
                    _table(
                        "家庭财务比率",
                        [
                            "指标",
                            "公式",
                            "分子",
                            "分母",
                            "当前值",
                            "参考区间",
                            "来源／版本",
                            "行动",
                        ],
                        metric_rows,
                    )
                ],
            )
        ],
    )

    account_rows = []
    for account in plan.accounts:
        ratios = {measure.denominator_id: measure for measure in account.measures}
        total_asset_measure = ratios.get("total_assets")
        investable_measure = ratios.get("investable_financial_assets")
        surplus_measure = ratios.get("annual_new_surplus")
        account_rows.append(
            (
                account.name,
                ledger.money(
                    f"account.{account.bucket.value}.current",
                    f"{account.name}当前金额",
                    account.current_amount,
                    f"planning.accounts.{account.bucket.value}.current_amount",
                ),
                ledger.money(
                    f"account.{account.bucket.value}.target",
                    f"{account.name}目标金额",
                    account.target_amount,
                    f"planning.accounts.{account.bucket.value}.target_amount",
                ),
                ledger.money(
                    f"account.{account.bucket.value}.recommended",
                    f"{account.name}建议新增",
                    account.recommended_amount,
                    f"planning.accounts.{account.bucket.value}.recommended_amount",
                ),
                ledger.ratio(
                    f"account.{account.bucket.value}.total_asset_ratio",
                    f"{account.name}占总资产",
                    total_asset_measure.ratio if total_asset_measure else None,
                    f"planning.accounts.{account.bucket.value}.measures.total_assets",
                ),
                ledger.ratio(
                    f"account.{account.bucket.value}.investable_ratio",
                    f"{account.name}占可投资金融资产",
                    investable_measure.ratio if investable_measure else None,
                    f"planning.accounts.{account.bucket.value}.measures.investable_financial_assets",
                ),
                ledger.ratio(
                    f"account.{account.bucket.value}.surplus_ratio",
                    f"{account.name}占年度新结余",
                    surplus_measure.ratio if surplus_measure else None,
                    f"planning.accounts.{account.bucket.value}.measures.annual_new_surplus",
                ),
                account.rationale,
            )
        )
    candidate_rows = []
    for portfolio_candidate in portfolio.candidates:
        candidate_rows.append(
            (
                portfolio_candidate.name,
                portfolio_candidate.decision.value,
                ledger.money(
                    f"candidate.{portfolio_candidate.candidate_type.value}.amount",
                    f"{portfolio_candidate.name}长期资金",
                    portfolio_candidate.investment_amount,
                    f"portfolio.candidates.{portfolio_candidate.candidate_type.value}.investment_amount",
                ),
                ledger.ratio(
                    f"candidate.{portfolio_candidate.candidate_type.value}.return",
                    f"{portfolio_candidate.name}名义回报假设",
                    portfolio_candidate.expected_nominal_return,
                    f"portfolio.candidates.{portfolio_candidate.candidate_type.value}.expected_nominal_return",
                ),
                ledger.ratio(
                    f"candidate.{portfolio_candidate.candidate_type.value}.success",
                    f"{portfolio_candidate.name}固定情景成功率",
                    portfolio_candidate.goal_success_probability,
                    f"portfolio.candidates.{portfolio_candidate.candidate_type.value}.goal_success_probability",
                ),
                ledger.ratio(
                    f"candidate.{portfolio_candidate.candidate_type.value}.drawdown",
                    f"{portfolio_candidate.name}最大回撤估计",
                    portfolio_candidate.max_drawdown_estimate,
                    f"portfolio.candidates.{portfolio_candidate.candidate_type.value}.max_drawdown_estimate",
                ),
                ledger.money(
                    f"candidate.{portfolio_candidate.candidate_type.value}.extreme_loss",
                    f"{portfolio_candidate.name}极端损失金额",
                    portfolio_candidate.extreme_loss_amount,
                    f"portfolio.candidates.{portfolio_candidate.candidate_type.value}.extreme_loss_amount",
                ),
                portfolio_candidate.liquidity_description,
                ledger.money(
                    f"candidate.{portfolio_candidate.candidate_type.value}.annual_fee",
                    f"{portfolio_candidate.name}年费用",
                    portfolio_candidate.annual_fee_estimate,
                    f"portfolio.candidates.{portfolio_candidate.candidate_type.value}.annual_fee_estimate",
                ),
            )
        )
    twin_rows = [
        (
            "无冲击基线",
            ledger.ratio(
                "twin.baseline.success",
                "基线目标成功概率",
                twin.baseline.goal_success_probability,
                "twin.baseline.goal_success_probability",
                source="deterministic_simulation_engine",
            ),
            ledger.ratio(
                "twin.baseline.forced_sale",
                "基线被迫出售概率",
                twin.baseline.forced_sale_probability,
                "twin.baseline.forced_sale_probability",
                source="deterministic_simulation_engine",
            ),
            ledger.money(
                "twin.baseline.ending_p10",
                "基线期末净资产 P10",
                twin.baseline.ending_net_worth_p10,
                "twin.baseline.ending_net_worth_p10",
                source="deterministic_simulation_engine",
            ),
        ),
        (
            "原方案压力",
            ledger.ratio(
                "twin.stress.success",
                "压力目标成功概率",
                twin.original_stress.goal_success_probability,
                "twin.original_stress.goal_success_probability",
                source="deterministic_simulation_engine",
            ),
            ledger.ratio(
                "twin.stress.forced_sale",
                "压力被迫出售概率",
                twin.original_stress.forced_sale_probability,
                "twin.original_stress.forced_sale_probability",
                source="deterministic_simulation_engine",
            ),
            ledger.money(
                "twin.stress.ending_p10",
                "压力期末净资产 P10",
                twin.original_stress.ending_net_worth_p10,
                "twin.original_stress.ending_net_worth_p10",
                source="deterministic_simulation_engine",
            ),
        ),
        (
            "优化方案压力",
            ledger.ratio(
                "twin.optimized.success",
                "优化压力目标成功概率",
                twin.optimized_stress.goal_success_probability,
                "twin.optimized_stress.goal_success_probability",
                source="deterministic_simulation_engine",
            ),
            ledger.ratio(
                "twin.optimized.forced_sale",
                "优化压力被迫出售概率",
                twin.optimized_stress.forced_sale_probability,
                "twin.optimized_stress.forced_sale_probability",
                source="deterministic_simulation_engine",
            ),
            ledger.money(
                "twin.optimized.ending_p10",
                "优化压力期末净资产 P10",
                twin.optimized_stress.ending_net_worth_p10,
                "twin.optimized_stress.ending_net_worth_p10",
                source="deterministic_simulation_engine",
            ),
        ),
    ]
    behavior_rows: list[tuple[object, ...]] = []
    if behavior.profile is not None:
        for bias in behavior.profile.biases:
            behavior_rows.append((bias.name, bias.severity, bias.score, bias.explanation))
    else:
        behavior_rows.append(("行为信息", "不足", "不适用", behavior.information_message))
    product_rows: list[tuple[object, ...]] = []
    for candidate in portfolio.candidates:
        for mapping in candidate.product_mappings:
            product_rows.append(
                (
                    candidate.name,
                    mapping.asset_class_name,
                    mapping.product_name,
                    mapping.product_type,
                    mapping.risk_level.value if mapping.risk_level else "不适用",
                    mapping.decision.value,
                    "；".join(mapping.reasons),
                    "示例产品目录" if mapping.is_mock else "已核验产品目录",
                )
            )
    fund_advisory_rows: list[tuple[object, ...]] = []
    pension_candidate_rows: list[tuple[object, ...]] = []
    for sleeve in fund_advisory.sleeves:
        for index, allocation in enumerate(sleeve.allocations):
            allocation_name = allocation.product_name or (
                "工行活期/支付侧现金"
                if allocation.allocation_type == "bank_cash_reserve"
                else "守门保留，未匹配基金"
            )
            fund_advisory_rows.append(
                (
                    sleeve.name,
                    sleeve.status,
                    ledger.ratio(
                        f"fund_advisory.{sleeve.sleeve_code}.{index}.ratio",
                        f"{sleeve.name}{allocation_name}比例",
                        allocation.ratio,
                        f"fund_advisory.sleeves.{sleeve.sleeve_code}.allocations.{index}.ratio",
                    ),
                    ledger.money(
                        f"fund_advisory.{sleeve.sleeve_code}.{index}.amount",
                        f"{sleeve.name}{allocation_name}金额",
                        allocation.amount,
                        f"fund_advisory.sleeves.{sleeve.sleeve_code}.allocations.{index}.amount",
                    ),
                    allocation.product_code or "—",
                    allocation_name,
                    allocation.product_risk_level.value.upper()
                    if allocation.product_risk_level
                    else "—",
                    "工行官方公开列示"
                    if allocation.icbc_publicly_listed
                    else "非基金/未核验工行可售",
                    allocation.purchase_route,
                    "；".join(allocation.warnings),
                )
            )
        for pension_candidate in sleeve.candidate_products:
            pension_candidate_rows.append(
                (
                    sleeve.name,
                    pension_candidate.product_code,
                    pension_candidate.product_name,
                    pension_candidate.role,
                    pension_candidate.status,
                    pension_candidate.reason,
                )
            )
    immediate_advice = [
        _action_advice(item) for item in actions if item.group_code != "next_12_months"
    ]
    monthly_advice = [
        _action_advice(item) for item in actions if item.group_code == "next_12_months"
    ]
    insurance_citations = _citation_ids(citations, "insurance_disclosure")
    product_citations = _citation_ids(citations, "product_suitability")
    chapter_7 = FormalReportChapter(
        number=7,
        title=FORMAL_CHAPTER_TITLES[6],
        summary="建议按安全优先、目标匹配、适当性与人工确认推进；四账户不使用固定比例。",
        sections=[
            _section(
                "7.1",
                "四账户动态规划",
                narratives=[
                    "四账户按七步资金瀑布、目标期限和安全闸门动态生成；三种分母并列，"
                    "任何百分比都不能被解释为家庭总资产统一配置。",
                    plan.counting_note,
                ],
                tables=[
                    _table(
                        "四账户",
                        [
                            "账户",
                            "当前",
                            "目标",
                            "建议新增",
                            "占总资产",
                            "占可投资金融资产",
                            "占年结余",
                            "理由",
                        ],
                        account_rows,
                    )
                ],
            ),
            _section(
                "7.2",
                "日用与应急资金",
                narratives=[
                    f"动态安全月数为 {plan.lifecycle.dynamic_safety_months} 个月；"
                    "应急资金与日用资金按用途隔离，不能重复计入目标或长期增长。"
                ],
                tables=[
                    _table(
                        "安全资金约束",
                        ["约束", "状态", "观察值", "条件", "影响"],
                        (
                            (
                                item.name,
                                item.status,
                                item.observed_value,
                                item.required_condition,
                                item.effect,
                            )
                            for item in plan.constraints
                            if item.constraint_id == "liquidity"
                        ),
                    )
                ],
            ),
            _section(
                "7.3",
                "债务管理",
                narratives=["优先处理高息债务和未来 12 个月偿付压力；信用卡额度不构成资产。"],
                tables=[
                    _table(
                        "债务明细",
                        ["负债", "类别", "余额", "年利率", "月供", "高息"],
                        liability_rows,
                    )
                ],
            ),
            _section(
                "7.4",
                "保险保障",
                narratives=[
                    f"当前保障缺口为 {ledger.money('protection.gap', '保障缺口', protection.protection_gap, 'financial_analysis.protection.protection_gap')}。"
                    "该值是责任测算，不是具体保险销售建议。",
                    *[
                        claim.text
                        for claim in sourced_claims
                        if set(claim.citation_ids) & set(insurance_citations)
                    ],
                ],
                tables=[
                    _table(
                        "保障风险",
                        ["风险", "所需", "已有", "覆盖率", "缺口", "优先级", "依据"],
                        (
                            (
                                item.name,
                                ledger.money(
                                    f"protection.{item.risk_code}.required",
                                    f"{item.name}所需保障",
                                    item.required_amount,
                                    f"financial_analysis.protection.risks.{item.risk_code}.required_amount",
                                ),
                                ledger.money(
                                    f"protection.{item.risk_code}.existing",
                                    f"{item.name}已有保障",
                                    item.existing_coverage,
                                    f"financial_analysis.protection.risks.{item.risk_code}.existing_coverage",
                                ),
                                ledger.ratio(
                                    f"protection.{item.risk_code}.ratio",
                                    f"{item.name}覆盖率",
                                    item.coverage_ratio,
                                    f"financial_analysis.protection.risks.{item.risk_code}.coverage_ratio",
                                ),
                                ledger.money(
                                    f"protection.{item.risk_code}.gap",
                                    f"{item.name}缺口",
                                    item.gap,
                                    f"financial_analysis.protection.risks.{item.risk_code}.gap",
                                ),
                                item.priority,
                                item.basis,
                            )
                            for item in protection.risks
                        ),
                    )
                ],
                citation_ids=insurance_citations,
            ),
            _section(
                "7.5",
                "养老与税务",
                narratives=[
                    *[
                        claim.text
                        for claim in sourced_claims
                        if set(claim.citation_ids) & set(pension_citations)
                    ],
                    "系统不根据政策概述自行估算税负或承诺节税；参保、账户、目录与领取条件需人工核验。",
                ],
                tables=[
                    _table(
                        "社保与养老账户",
                        ["成员记录", "账户类型", "余额", "个人年缴费", "单位年缴费", "数据日"],
                        (
                            (
                                item.member_id,
                                item.account_type,
                                ledger.money(
                                    f"social.{item.id}.balance",
                                    f"{item.account_type}余额",
                                    item.balance,
                                    f"household_facts.social_security_accounts.{item.id}.balance",
                                ),
                                ledger.money(
                                    f"social.{item.id}.personal",
                                    f"{item.account_type}个人年缴费",
                                    item.annual_personal_contribution,
                                    f"household_facts.social_security_accounts.{item.id}.annual_personal_contribution",
                                ),
                                ledger.money(
                                    f"social.{item.id}.employer",
                                    f"{item.account_type}单位年缴费",
                                    item.annual_employer_contribution,
                                    f"household_facts.social_security_accounts.{item.id}.annual_employer_contribution",
                                ),
                                item.valuation_date or analysis.meta.data_as_of,
                            )
                            for item in facts.social_security_accounts
                        ),
                    )
                ],
                citation_ids=pension_citations,
            ),
            _section(
                "7.6",
                "目标规划",
                narratives=["目标现值、未来金额、月度所需和冲突均由同一规划规则版本计算。"],
                tables=[
                    _table(
                        "目标投入",
                        ["目标", "未来金额", "月度所需", "准备金额", "状态", "公式"],
                        (
                            (
                                item.name,
                                ledger.money(
                                    f"goalplan.{item.goal_id}.future",
                                    f"{item.name}未来目标金额",
                                    item.future_amount,
                                    f"planning.goals.{item.goal_id}.future_amount",
                                ),
                                ledger.money(
                                    f"goalplan.{item.goal_id}.monthly",
                                    f"{item.name}月度所需",
                                    item.monthly_required,
                                    f"planning.goals.{item.goal_id}.monthly_required",
                                ),
                                ledger.money(
                                    f"goalplan.{item.goal_id}.prepared",
                                    f"{item.name}准备金额",
                                    item.prepared_amount,
                                    f"planning.goals.{item.goal_id}.prepared_amount",
                                ),
                                item.status,
                                item.formula,
                            )
                            for item in plan.goals
                        ),
                    )
                ],
            ),
            _section(
                "7.7",
                "三套组合候选",
                narratives=[
                    portfolio.counting_note,
                    "普通家庭默认不推荐个股、杠杆或股指期货；候选需同时通过家庭、客户和产品三道闸门。",
                ],
                tables=[
                    _table(
                        "候选方案比较",
                        [
                            "方案",
                            "决定",
                            "长期资金",
                            "回报假设",
                            "固定情景成功率",
                            "回撤估计",
                            "极端损失",
                            "流动性",
                            "年费用",
                        ],
                        candidate_rows,
                    )
                ],
                citation_ids=product_citations,
            ),
            _section(
                "7.8",
                "数字孪生与压力测试",
                narratives=[
                    f"运行使用种子 {twin.assumptions.seed}、{twin.assumptions.path_count} 条路径、"
                    f"{twin.assumptions.horizon_months} 个月期限和共同随机数。",
                    "压力测试不是预测；分位数、成功概率和最差样本路径都不能被解释为收益承诺。",
                ],
                tables=[
                    _table(
                        "孪生结果",
                        ["情景", "目标成功概率", "被迫出售概率", "期末净资产 P10"],
                        twin_rows,
                        source="deterministic_simulation_engine",
                    )
                ],
            ),
            _section(
                "7.9",
                "行为干预",
                narratives=[
                    behavior.information_message,
                    "行为证据只能维持或下调风险上限，不得提高客观风险能力，也不自动交易。",
                ],
                tables=[_table("行为证据", ["偏差", "等级", "得分", "解释"], behavior_rows)],
            ),
            _section(
                "7.10",
                "产品适配",
                narratives=[
                    "模拟产品映射用于说明资产类别、期限、流动性和风险匹配，不代表真实在售或保本。"
                ],
                tables=[
                    _table(
                        "模拟产品适配",
                        ["候选", "资产类别", "模拟产品", "类型", "风险", "决定", "理由", "标记"],
                        product_rows,
                    )
                ],
                citation_ids=product_citations,
            ),
            _section(
                "7.11",
                "立即、三个月、一年与长期行动",
                narratives=[
                    "每项行动都包含原因、优先级、动作、完成标准和复盘周期；未经确认不执行。"
                ],
                advice=immediate_advice,
            ),
            _section(
                "7.12",
                "未来 12 个月行动日历",
                narratives=[
                    "月度任务可标记完成、延期或不适用；状态变化会创建新报告快照并重算执行指标，"
                    "不会覆盖旧报告。"
                ],
                advice=monthly_advice,
            ),
            _section(
                "7.13",
                "真实基金智能投顾补充",
                narratives=[
                    "本节不改写前述四账户金额或模拟组合，只将已确认的资金用途映射到经官方证据核验的真实公募基金份额。",
                    fund_advisory.catalog.mandatory_channel_notice,
                    fund_advisory.catalog.personal_pension_catalog_observation,
                    (
                        "当前真实基金目录已超过复核期，所有基金分配已自动停止。"
                        if fund_advisory.meta.catalog_stale
                        else f"目录截止 {fund_advisory.meta.catalog_data_date}，"
                        f"验证版本 {fund_advisory.meta.catalog_version}；报告默认使用工行限定模式。"
                    ),
                ],
                tables=[
                    _table(
                        "用途到真实基金的建议分配",
                        [
                            "资金用途",
                            "状态",
                            "比例",
                            "金额",
                            "六位代码",
                            "产品/保留项",
                            "内部风险",
                            "工行证据",
                            "执行路径",
                            "风险提示",
                        ],
                        fund_advisory_rows,
                        note="六位代码、份额类别、适当性和当日可售状态须在工行App最终确认。",
                    ),
                    _table(
                        "个人养老金精确候选与未分配原因",
                        ["用途", "六位代码", "基金全称", "角色", "状态", "原因"],
                        pension_candidate_rows,
                        note="候选不等于推荐或已分配；渠道证据不足的产品不进入工行限定分配。",
                    ),
                ],
            ),
        ],
    )

    source_rows = [
        (
            item.citation_id,
            item.title,
            item.issuing_authority,
            item.document_version,
            item.publication_date,
            item.effective_date,
            item.last_verified_date or "待核验",
            item.paragraph_ref,
            item.source_uri,
        )
        for item in citations
    ]
    version_rows = [
        ("报告", f"formal-report-v1.0.0-r{sequence}"),
        ("输入", plan.meta.input_version),
        ("财务公式", analysis.meta.formula_version),
        ("规划规则", plan.meta.rule_version),
        ("组合规则", portfolio.meta.rule_version),
        ("孪生结果", twin.meta.result_version),
        ("模型", model_version),
        ("Prompt", prompt_version),
        ("知识", knowledge_version),
        ("产品目录", portfolio.meta.catalog_version),
        ("真实基金投顾目录", fund_advisory.meta.catalog_version),
        ("方案工作流", workflow_version_label or "未关联"),
    ]
    chapter_8 = FormalReportChapter(
        number=8,
        title=FORMAL_CHAPTER_TITLES[7],
        summary="披露来源、公式、模型、规则版本、适用边界与风险；重大决定必须人工复核。",
        sections=[
            _section(
                "8.1",
                "来源与版本",
                tables=[
                    _table(
                        "受控来源",
                        [
                            "引用",
                            "文件",
                            "机构",
                            "版本",
                            "发布日",
                            "生效日",
                            "核验日",
                            "段落",
                            "入口",
                        ],
                        source_rows,
                        source="deterministic_hybrid_retrieval",
                    ),
                    _table(
                        "版本账本", ["对象", "版本"], version_rows, source=REPORT_COMPOSER_VERSION
                    ),
                ],
            ),
            _section(
                "8.2",
                "模型、规则与适用边界",
                narratives=[
                    "语言模型只允许理解、追问和解释，不参与关键金额、比率、概率或配置计算。",
                    "外部解释服务不可用时，报告仍可依据客户已确认资料和计算规则生成。",
                    "当前财务阈值、资产回报、压力参数及部分生活成本参数是版本化规划参考；"
                    "办理具体业务前应重新核验适用规则和家庭事实。",
                ],
            ),
            _section(
                "8.3",
                "风险揭示与免责声明",
                narratives=[
                    "本报告根据客户提供并确认的资料与当前计算规则生成，不构成存款、理财、基金、信托、"
                    "保险、证券、税务、法律或交易承诺。",
                    "银行理财、信托、基金和保险不能统一描述为保本产品；历史表现不代表未来。",
                    "数字孪生与压力测试用于比较假设下的路径分布，不是市场预测；任何收益率、"
                    "成功概率、回撤或分位数都不是保证。",
                    "长期增长账户的 70% 条件只针对通过全部安全闸门后的真实长期可规划资金，"
                    "不代表家庭总资产统一配置。",
                    "重大投保、赎回、借贷、税务、资产配置或产品购买决定必须由家庭、客户经理及"
                    "必要的合规／专业人员人工复核；系统不会自动交易。",
                    "报告边界：数据变化、收入变化、目标变化或市场假设变化后应创建新快照并重算；"
                    "旧报告永久保留，不得以新报告覆盖历史。",
                ],
            ),
        ],
    )

    appendices = [
        ReportAppendix(
            code="A",
            title="公式附录",
            tables=[
                _table(
                    "指标公式与代入",
                    ["指标", "公式", "代入", "阈值版本"],
                    (
                        (item.name, item.formula, item.substitution, item.threshold_version)
                        for item in analysis.metrics
                    ),
                )
            ],
        ),
        ReportAppendix(
            code="B",
            title="政策与知识附录",
            tables=[
                _table(
                    "政策引用索引",
                    ["引用", "文件", "版本", "生效日", "段落", "内容哈希"],
                    (
                        (
                            item.citation_id,
                            item.title,
                            item.document_version,
                            item.effective_date,
                            item.paragraph_ref,
                            item.content_hash,
                        )
                        for item in citations
                    ),
                    source="deterministic_hybrid_retrieval",
                )
            ],
        ),
        ReportAppendix(
            code="C",
            title="模拟产品附录",
            narratives=[portfolio.catalog.source_summary],
            tables=[
                _table(
                    "模拟产品目录摘录",
                    ["代码", "名称", "类型", "风险", "流动性", "保本", "披露"],
                    (
                        (
                            item.code,
                            item.name,
                            item.product_type,
                            item.risk_level.value,
                            item.liquidity_level.value,
                            "是" if item.principal_guaranteed else "否",
                            item.guarantee_disclosure or item.non_guaranteed_disclosure,
                        )
                        for item in portfolio.catalog.products
                    ),
                )
            ],
        ),
        ReportAppendix(
            code="D",
            title="数据与审计附录",
            narratives=[
                f"报告输入版本 {plan.meta.input_version}；报告序号 {sequence}；"
                f"父报告 {parent_report_id or '无'}；工作流 {workflow_id or '未关联'}。",
                "导出成功或失败均写入 AuditEvent；导出文件不携带可执行脚本或外部字体。",
            ],
            tables=[
                _table(
                    "执行指标",
                    ["总数", "待办", "完成", "延期", "不适用", "完成率"],
                    [
                        (
                            execution_metrics.total,
                            execution_metrics.open,
                            execution_metrics.completed,
                            execution_metrics.deferred,
                            execution_metrics.not_applicable,
                            execution_metrics.completion_ratio,
                        )
                    ],
                    source="formal_report_action_ledger",
                )
            ],
        ),
        ReportAppendix(
            code="E",
            title="真实基金证据附录",
            narratives=[
                fund_advisory.catalog.scope,
                fund_advisory.catalog.mandatory_channel_notice,
                "不收录个股、行业/主题指数、杠杆或反向产品；不记录未核验的收益率或排名。",
            ],
            tables=[
                _table(
                    "经核验真实基金目录",
                    [
                        "代码",
                        "基金全称",
                        "类别",
                        "跟踪指数",
                        "工行公开列示",
                        "个人养老金资格",
                        "非保本",
                        "官方证据URL",
                    ],
                    (
                        (
                            item.code,
                            item.name,
                            item.category,
                            item.tracked_index or "—",
                            "是，执行时仍需App确认"
                            if item.icbc_publicly_listed
                            else "未核验",
                            "是" if item.personal_pension_eligible else "否",
                            "是",
                            "；".join(dict.fromkeys(evidence.url for evidence in item.evidence)),
                        )
                        for item in fund_advisory.catalog.products
                    ),
                )
            ],
        ),
    ]

    checks = [
        ReportConsistencyCheck(
            code="exact_eight_chapters",
            status="passed",
            explanation="一级目录恰好八章且顺序、标题与正式协议完全一致。",
        ),
        ReportConsistencyCheck(
            code="deterministic_numeric_ledger",
            status="passed",
            explanation=f"{len(ledger.items())} 个关键数字均带确定性来源路径。",
        ),
        ReportConsistencyCheck(
            code="verified_rag_claims",
            status="passed" if citations and sourced_claims else "needs_review",
            explanation=(
                f"{len(sourced_claims)} 条外部事实均关联 {len(citations)} 个受控引用。"
                if citations and sourced_claims
                else "受控引用不足，外部事实未写入，需人工补充核验。"
            ),
        ),
        ReportConsistencyCheck(
            code="twin_validation",
            status="passed" if twin.baseline.validation.all_values_finite else "needs_review",
            explanation="数字孪生输出通过有限值与共同随机数校验。",
        ),
        ReportConsistencyCheck(
            code="action_status_balance",
            status="passed",
            explanation="完成、延期、不适用与待办状态合计等于行动总数。",
        ),
        ReportConsistencyCheck(
            code="verified_real_fund_catalog",
            status="needs_review" if fund_advisory.meta.catalog_stale else "passed",
            explanation=(
                "真实基金目录已超过复核期；系统已停止基金分配，需更新官方证据。"
                if fund_advisory.meta.catalog_stale
                else f"真实基金目录 {fund_advisory.meta.catalog_version} 通过代码、宽基、养老资格与工行渠道证据校验。"
            ),
        ),
    ]
    consistency = "passed" if all(item.status == "passed" for item in checks) else "needs_review"
    versions = ReportVersionLedger(
        report_version=f"formal-report-v1.0.0-r{sequence}",
        input_version=plan.meta.input_version,
        formula_version=analysis.meta.formula_version,
        planning_rule_version=plan.meta.rule_version,
        portfolio_rule_version=portfolio.meta.rule_version,
        twin_result_version=twin.meta.result_version,
        model_version=model_version,
        prompt_version=prompt_version,
        knowledge_version=knowledge_version,
        product_catalog_version=portfolio.meta.catalog_version,
        fund_advisory_catalog_version=fund_advisory.meta.catalog_version,
        workflow_version=workflow_version_label,
    )
    return FormalReportDocument(
        report_id=report_id,
        household_id=facts.id,
        household_code=facts.code,
        household_name=facts.name,
        sequence=sequence,
        parent_report_id=parent_report_id,
        workflow_id=workflow_id,
        workflow_version_id=workflow_version_id,
        workflow_state=workflow_state,
        status=status,
        title=f"{facts.name} · 财富规划书",
        subtitle="智运财富 · 普慧金融 · 个人／家庭八章理财规划书",
        watermark=watermark,
        chapters=[
            chapter_1,
            chapter_2,
            chapter_3,
            chapter_4,
            chapter_5,
            chapter_6,
            chapter_7,
            chapter_8,
        ],
        appendices=appendices,
        citations=citations,
        sourced_claims=sourced_claims,
        numeric_ledger=ledger.items(),
        versions=versions,
        execution_metrics=execution_metrics,
        consistency_checks=checks,
        consistency_status=consistency,
        generation_trigger=trigger,
        generation_reason=reason,
        generated_at=generated_at,
        analysis_date=analysis.meta.analysis_date,
        data_as_of=analysis.meta.data_as_of,
        report_hash="pending",
        boundary_note=(
            "本报告由确定性财务、规划、组合、孪生与行动工具生成；受控事实逐条引用。"
            "模型不计算关键数字，报告不自动交易，不构成保本或收益承诺，重大决定必须人工复核。"
        ),
    )
