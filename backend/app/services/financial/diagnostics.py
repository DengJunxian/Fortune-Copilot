from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.domain.enums import PropertyUse
from app.domain.financial import HouseholdFacts
from app.schemas.financial_analysis import (
    DataDiagnostics,
    DiagnosticIssue,
    DiagnosticSeverity,
    FinancialStatements,
)
from app.services.financial.rules import FinancialRules
from app.services.financial.utils import ZERO, display_number


def _issue(
    code: str,
    severity: DiagnosticSeverity,
    title: str,
    detail: str,
    action: str,
    record_ids: list[str] | None = None,
) -> DiagnosticIssue:
    return DiagnosticIssue(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        related_record_ids=record_ids or [],
        action=action,
    )


def diagnose_data(
    facts: HouseholdFacts,
    statements: FinancialStatements,
    rules: FinancialRules,
    analysis_date: date,
) -> DataDiagnostics:
    issues: list[DiagnosticIssue] = []
    required_sections = {
        "members": facts.members,
        "assets": facts.assets,
        "incomes": facts.incomes,
        "expenses": facts.expenses,
    }
    missing = [name for name, records in required_sections.items() if not records]
    if missing:
        issues.append(
            _issue(
                "missing_core_data",
                "critical",
                "核心家庭数据缺失",
                "缺少：" + "、".join(missing),
                "补齐缺失资料并由家庭确认后重新计算。",
            )
        )

    duplicate_groups: defaultdict[tuple[str, str, Decimal], list[str]] = defaultdict(list)
    for asset in facts.assets:
        key = (asset.name.strip().casefold(), asset.category.value, asset.market_value)
        duplicate_groups[key].append(asset.id)
    duplicates = [ids for ids in duplicate_groups.values() if len(ids) > 1]
    if duplicates:
        related = [record_id for group in duplicates for record_id in group]
        issues.append(
            _issue(
                "possible_duplicate_assets",
                "warning",
                "可能存在重复资产",
                "发现名称、类别和市值完全相同的资产记录。",
                "逐项核对账户或权属，确认后合并重复记录。",
                related,
            )
        )

    linked_asset_ids = {
        liability.linked_asset_id
        for liability in facts.liabilities
        if liability.linked_asset_id is not None
    }
    unlinked_pledged = [
        asset.id for asset in facts.assets if asset.pledged and asset.id not in linked_asset_ids
    ]
    if unlinked_pledged:
        issues.append(
            _issue(
                "pledged_asset_without_liability",
                "warning",
                "质押资产可能漏记负债",
                "存在已质押资产，但没有关联的未偿负债记录。",
                "核对房贷、抵押贷或其他担保债务余额。",
                unlinked_pledged,
            )
        )

    cash_flow = statements.cash_flow
    if cash_flow.annual_income == ZERO and cash_flow.annual_expenses > ZERO:
        issues.append(
            _issue(
                "expenses_without_income",
                "critical",
                "有支出但无收入",
                "当前记录无法解释支出资金来源。",
                "补录收入、资产变现或家庭转移支付来源。",
            )
        )
    elif cash_flow.annual_expenses > cash_flow.annual_income:
        issues.append(
            _issue(
                "negative_annual_surplus",
                "warning",
                "年度现金流为负",
                "年度支出高于年度税后收入。",
                "核对一次性支出，并制定支出压缩或收入修复方案。",
            )
        )

    abnormal_multiple = Decimal(rules.classification.abnormal_return_multiple)
    abnormal_assets: list[str] = []
    for asset in facts.assets:
        if asset.acquisition_cost <= ZERO:
            continue
        change_multiple = abs(asset.market_value - asset.acquisition_cost) / asset.acquisition_cost
        if change_multiple > abnormal_multiple:
            abnormal_assets.append(asset.id)
    if abnormal_assets:
        issues.append(
            _issue(
                "abnormal_asset_change",
                "warning",
                "资产市值变化异常",
                "部分资产相对成本的变化超过受控异常倍数。",
                "核验估值单位、数量、币种和是否重复录入。",
                abnormal_assets,
            )
        )

    stale_ids: list[str] = []
    missing_dates: list[str] = []
    for asset in facts.assets:
        if asset.valuation_date is None:
            missing_dates.append(asset.id)
            continue
        limit = (
            rules.classification.stale_property_days
            if asset.property_use != PropertyUse.NOT_PROPERTY
            else rules.classification.stale_financial_days
        )
        if (analysis_date - asset.valuation_date).days > limit:
            stale_ids.append(asset.id)
    for collection in (
        facts.incomes,
        facts.expenses,
        facts.liabilities,
        facts.insurance_policies,
        facts.social_security_accounts,
        facts.goals,
    ):
        for record in collection:
            if record.valuation_date is None:
                missing_dates.append(record.id)
            elif (
                analysis_date - record.valuation_date
            ).days > rules.classification.stale_financial_days:
                stale_ids.append(record.id)
    if stale_ids:
        issues.append(
            _issue(
                "stale_valuation",
                "attention",
                "存在过期估值或观察值",
                "部分数据超过规则允许的更新间隔。",
                "更新相关资产、负债、收入或支出的数据日期。",
                stale_ids,
            )
        )
    if missing_dates:
        issues.append(
            _issue(
                "missing_valuation_date",
                "attention",
                "部分记录缺少估值日期",
                "无法完整判断数据新鲜度。",
                "补录观察日期；估算值必须继续标记为未确认。",
                missing_dates,
            )
        )

    scheduled_debt = sum(
        (item.scheduled_twelve_month_payment for item in statements.balance_sheet.liabilities),
        ZERO,
    )
    recorded_debt = cash_flow.annual_debt_service
    if abs(scheduled_debt - recorded_debt) > Decimal("1.00"):
        issues.append(
            _issue(
                "debt_service_reconciliation",
                "attention",
                "债务还款口径需要核对",
                (
                    f"现金流记录为 {recorded_debt:.2f}，按负债合同推算未来十二个月为 "
                    f"{scheduled_debt:.2f}。"
                ),
                "确认信用卡即期清偿与贷款月供是否均已进入年度支出。",
                [item.id for item in facts.liabilities],
            )
        )

    active_premium = statements.insurance.total_annual_premium
    if abs(active_premium - cash_flow.annual_insurance_premiums) > Decimal("1.00"):
        issues.append(
            _issue(
                "premium_reconciliation",
                "attention",
                "保费记录不一致",
                (
                    f"保单表有效保费为 {active_premium:.2f}，现金流保费支出为 "
                    f"{cash_flow.annual_insurance_premiums:.2f}。"
                ),
                "核对已失效保单、月缴保费和非商业保险支出。",
                [item.id for item in facts.insurance_policies],
            )
        )

    high_interest = [item.id for item in facts.liabilities if item.is_high_interest]
    if high_interest:
        issues.append(
            _issue(
                "high_interest_debt",
                "warning",
                "存在高息债务",
                "高息债务会优先占用后续可投资结余。",
                "核对实际计息规则并优先制定清偿行动。",
                high_interest,
            )
        )

    weights = {"critical": 25, "warning": 12, "attention": 5, "info": 1}
    penalty = sum(weights[item.severity] for item in issues)
    completeness = display_number(max(ZERO, Decimal(100 - penalty)))
    total_checks = 10
    passed_checks = max(0, total_checks - len({item.code for item in issues}))
    return DataDiagnostics(
        completeness_score=completeness,
        passed_checks=passed_checks,
        issue_count=len(issues),
        issues=issues,
    )
