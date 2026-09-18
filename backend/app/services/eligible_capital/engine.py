from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import AccountWrapper, AssetCategory, ExpenseCategory, GoalRigidity
from app.domain.financial import HouseholdFacts
from app.models.liability import LiabilityStream
from app.schemas.eligible_capital import (
    EligibilityGate,
    EligibleCapitalBridgeStep,
    EligibleCapitalCalculation,
    EligibleCapitalMeta,
    EligibleCapitalResponse,
    GrowthThresholdReference,
)
from app.schemas.methodology import MethodologyAssessment
from app.services.calibration.port import CalibrationPort, UnavailableCalibrationPort
from app.services.calibration.registry import build_database_calibration_port
from app.services.financial.engine import analyze_facts
from app.services.financial.facts import load_household_facts
from app.services.financial.rules import FinancialRules, load_financial_rules
from app.services.financial.utils import ZERO, annualize, money
from app.services.liability_engine.engine import materialize_liability_streams
from app.services.liability_engine.rules import LiabilityRules, load_liability_rules
from app.services.liability_engine.schedule import SchedulableStream, build_schedule
from app.services.methodology.engine import assess_methodology
from app.services.methodology.models import MethodologyRules
from app.services.methodology.purchasing_power_v2 import assess_purchasing_power_v2
from app.services.methodology.rules import load_methodology_rules
from app.services.public_data.models import AuthoritativePublicDataSnapshot
from app.services.public_data.rules import load_public_data_snapshot

_INSTITUTIONAL_WRAPPERS = {
    AccountWrapper.PERSONAL_PENSION,
    AccountWrapper.SOCIAL_SECURITY,
    AccountWrapper.ENTERPRISE_ANNUITY,
    AccountWrapper.OCCUPATIONAL_ANNUITY,
    AccountWrapper.PROVIDENT_FUND,
}


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _funding_amount(stream: SchedulableStream) -> Decimal:
    amount = ZERO
    for source in stream.funding_sources:
        source_type = str(source.get("source_type", ""))
        if source_type != "institutional_coverage":
            amount += Decimal(str(source.get("amount", "0")))
    return money(amount)


def _bridge_step(
    code: str,
    label: str,
    before: Decimal,
    requested: Decimal,
    source: str,
    reason: str,
) -> EligibleCapitalBridgeStep:
    requested_amount = money(max(ZERO, requested))
    deduction = money(min(before, requested_amount))
    return EligibleCapitalBridgeStep(
        code=code,
        label=label,
        before=money(before),
        requested_deduction=requested_amount,
        deduction=deduction,
        after=money(max(ZERO, before - deduction)),
        unfunded=money(max(ZERO, requested_amount - deduction)),
        source=source,
        reason=reason,
    )


def _input_hash(
    facts: HouseholdFacts,
    streams: Sequence[SchedulableStream],
    rules: LiabilityRules,
    analysis_date: date,
    calibration_version: str,
) -> str:
    stream_payload = [
        {
            "id": getattr(item, "id", None),
            "source_goal_id": getattr(item, "source_goal_id", None),
            "source_responsibility_id": getattr(item, "source_responsibility_id", None),
            "stream_version": item.stream_version,
        }
        for item in streams
    ]
    canonical = json.dumps(
        {
            "analysis_date": analysis_date,
            "facts": asdict(facts),
            "streams": stream_payload,
            "rule_version": rules.semantic_version,
            "formula_version": rules.formula_version,
            "calibration_version": calibration_version,
        },
        default=str,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _methodology(
    facts: HouseholdFacts,
    financial_rules: FinancialRules,
    methodology_rules: MethodologyRules,
    public_data: AuthoritativePublicDataSnapshot | None,
    analysis_date: date,
) -> MethodologyAssessment:
    financial = analyze_facts(facts, financial_rules, analysis_date)
    investable_categories = set(
        financial_rules.classification.investable_financial_asset_categories
    )
    investable_assets = money(
        sum(
            (
                item.market_value
                for item in facts.assets
                if item.category.value in investable_categories
            ),
            ZERO,
        )
    )
    pfnw = money(investable_assets - financial.statements.balance_sheet.total_liabilities)
    return assess_methodology(
        facts,
        financial,
        methodology_rules,
        analysis_date,
        pfnw,
        public_data,
    )


def calculate_eligible_capital(
    facts: HouseholdFacts,
    streams: Sequence[SchedulableStream],
    financial_rules: FinancialRules,
    methodology_rules: MethodologyRules,
    liability_rules: LiabilityRules,
    analysis_date: date,
    public_data: AuthoritativePublicDataSnapshot | None = None,
    calibration_port: CalibrationPort | None = None,
) -> EligibleCapitalResponse:
    resolved_calibration_port = calibration_port or UnavailableCalibrationPort()
    methodology = _methodology(
        facts,
        financial_rules,
        methodology_rules,
        public_data,
        analysis_date,
    )
    investable_categories = set(
        financial_rules.classification.investable_financial_asset_categories
    )
    dispatchable = money(
        sum(
            (
                item.market_value
                for item in facts.assets
                if item.category.value in investable_categories and not item.pledged
            ),
            ZERO,
        )
    )
    operating_annual = sum(
        (
            annualize(item.amount, item.frequency)
            for item in facts.expenses
            if item.necessity.value == "essential"
            and item.category
            not in {ExpenseCategory.DEBT_SERVICE, ExpenseCategory.INSURANCE_PREMIUM}
        ),
        ZERO,
    )
    monthly_operating = money(operating_annual / Decimal("12"))
    operating_liquidity = money(monthly_operating * liability_rules.operating_liquidity_months)
    emergency_reserve = money(monthly_operating * liability_rules.emergency_reserve_months)
    high_interest_debt = money(
        sum(
            (item.outstanding_balance for item in facts.liabilities if item.is_high_interest),
            ZERO,
        )
    )
    annual_premiums = sum(
        (
            item.annual_premium
            for item in facts.insurance_policies
            if item.start_date <= analysis_date
            and (item.end_date is None or item.end_date >= analysis_date)
        ),
        ZERO,
    )
    protection_funding = money(
        annual_premiums * Decimal(liability_rules.protection_funding_months) / Decimal("12")
    )
    horizon = _add_months(analysis_date, liability_rules.short_term_hard_liability_months)
    short_term_stream_gap = ZERO
    for stream in streams:
        hard = stream.rigidity == GoalRigidity.RIGID or not bool(
            getattr(stream, "deferrable", False)
        )
        if not hard:
            continue
        due_total = sum(
            (
                row.target_amount
                for row in build_schedule(stream, liability_rules.formula_version)
                if analysis_date <= row.due_date <= horizon
            ),
            ZERO,
        )
        short_term_stream_gap += max(ZERO, due_total - min(due_total, _funding_amount(stream)))
    scheduled_debt = ZERO
    for item in facts.liabilities:
        if item.is_high_interest:
            continue
        months = liability_rules.short_term_hard_liability_months
        if item.maturity_date is not None:
            if item.maturity_date < analysis_date:
                months = 0
            else:
                days = (min(item.maturity_date, horizon) - analysis_date).days
                months = min(months, max(1, (days + 29) // 30))
        scheduled_debt += min(
            item.outstanding_balance,
            item.monthly_payment * Decimal(months),
        )
    short_term_hard_liabilities = money(short_term_stream_gap + scheduled_debt)
    committed_goal_capital = money(sum((_funding_amount(item) for item in streams), ZERO))
    locked_institutional_assets = money(
        sum(
            (
                item.market_value
                for item in facts.assets
                if (
                    item.category == AssetCategory.PENSION_ACCOUNT
                    or item.account_wrapper in _INSTITUTIONAL_WRAPPERS
                )
                and (
                    item.lock_up
                    or item.withdrawable_date is None
                    or item.withdrawable_date > analysis_date
                )
            ),
            ZERO,
        )
    )
    deductions = (
        (
            "operating_liquidity",
            "经营性流动资金",
            operating_liquidity,
            "家庭必要支出",
            "保留日常周转，不将账单资金配置到长期风险资产。",
        ),
        (
            "emergency_reserve",
            "应急储备",
            emergency_reserve,
            "家庭必要支出",
            "覆盖收入中断与突发支出的安全垫。",
        ),
        (
            "high_interest_debt_repair",
            "高息债务修复",
            high_interest_debt,
            "未偿高息负债",
            "高息债务处理优先于长期投资。",
        ),
        (
            "protection_funding",
            "保障资金",
            protection_funding,
            "有效保险保费",
            "预留既有保障责任所需资金。",
        ),
        (
            "short_term_hard_liabilities",
            "短期刚性责任",
            short_term_hard_liabilities,
            "负债流日历与债务合同",
            f"覆盖未来 {liability_rules.short_term_hard_liability_months} 个月刚性现金流缺口。",
        ),
        (
            "committed_goal_capital",
            "已承诺目标资本",
            committed_goal_capital,
            "目标与责任准备金",
            "已指定用途的资本不能再次计入长期可配置资本。",
        ),
        (
            "locked_institutional_assets",
            "锁定制度资产",
            locked_institutional_assets,
            "养老金与制度账户",
            "分析日不可领取的制度资产不具备当前调度能力。",
        ),
    )
    bridge: list[EligibleCapitalBridgeStep] = []
    remaining = dispatchable
    for code, label, requested, source, reason in deductions:
        step = _bridge_step(code, label, remaining, requested, source, reason)
        bridge.append(step)
        remaining = step.after
    eligible_capital = money(remaining)
    latest_risk = facts.risk_assessments[-1] if facts.risk_assessments else None
    suitability_passed = bool(
        latest_risk is not None
        and latest_risk.capacity_score >= liability_rules.minimum_suitability_score
        and latest_risk.final_risk_limit in liability_rules.minimum_suitability_levels
    )
    sustainable_income = sum(
        (annualize(item.amount, item.frequency) for item in facts.incomes if item.is_sustainable),
        ZERO,
    )
    annual_expenses = sum((annualize(item.amount, item.frequency) for item in facts.expenses), ZERO)
    gates = [
        EligibilityGate(
            code="eltc_positive",
            label="长期可配置资本为正",
            passed=eligible_capital > ZERO,
            reason=(
                f"ELTC 为 {eligible_capital:.2f} 元。"
                if eligible_capital > ZERO
                else "前置责任已耗尽可调度金融资源。"
            ),
        ),
        EligibilityGate(
            code="suitability",
            label="适当性资料有效",
            passed=suitability_passed,
            reason="风险承担能力与风险上限满足政策。"
            if suitability_passed
            else "需完成或更新正式风险评估。",
        ),
        EligibilityGate(
            code="high_interest_debt",
            label="无待修复高息债务",
            passed=high_interest_debt == ZERO,
            reason="未发现高息债务。"
            if high_interest_debt == ZERO
            else "先实际偿还高息债务，再开放长期配置。",
        ),
        EligibilityGate(
            code="cashflow_safety",
            label="可持续收入覆盖年度支出",
            passed=sustainable_income >= annual_expenses,
            reason=(
                "可持续收入不低于年度支出。"
                if sustainable_income >= annual_expenses
                else "年度现金流存在缺口，应先修复收支。"
            ),
        ),
    ]
    formally_eligible = all(item.passed for item in gates)
    return EligibleCapitalResponse(
        meta=EligibleCapitalMeta(
            household_id=facts.id,
            analysis_date=analysis_date,
            data_as_of=analysis_date,
            input_hash=_input_hash(
                facts,
                streams,
                liability_rules,
                analysis_date,
                resolved_calibration_port.registry_version,
            ),
            rule_version=liability_rules.semantic_version,
            formula_version=liability_rules.formula_version,
            calibration_version=resolved_calibration_port.registry_version,
        ),
        calculation=EligibleCapitalCalculation(
            dispatchable_financial_resources=dispatchable,
            bridge=bridge,
            eligible_long_term_capital=eligible_capital,
            eligibility_gates=gates,
            formally_eligible=formally_eligible,
            decision="eligible" if formally_eligible else "repair_first",
            growth_entry_threshold=GrowthThresholdReference(
                amount=methodology.regional_threshold.effective_threshold,
                currency=facts.currency,
                source=methodology.regional_threshold.policy_version,
                communication_note="V5 中仅作为客户沟通与偏好参考，不决定投资资格。",
            ),
            purchasing_power=assess_purchasing_power_v2(
                facts,
                streams,
                financial_rules,
                methodology,
                liability_rules,
                analysis_date,
                resolved_calibration_port,
            ),
        ),
    )


def calculate_household_eligible_capital(
    session: Session,
    household_id: str,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    liability_rules_path: str,
    calibration_registry_path: str | None = None,
    calibration_enabled: bool = False,
    analysis_date: date,
) -> EligibleCapitalResponse:
    materialize_liability_streams(
        session,
        household_id,
        actor,
        liability_rules_path,
        analysis_date,
    )
    streams = tuple(
        session.scalars(
            select(LiabilityStream)
            .where(
                LiabilityStream.household_id == household_id,
                LiabilityStream.is_deleted.is_(False),
            )
            .order_by(LiabilityStream.start_date, LiabilityStream.id)
        ).all()
    )
    calibration_port: CalibrationPort = UnavailableCalibrationPort()
    if calibration_enabled and calibration_registry_path is not None:
        calibration_port = build_database_calibration_port(
            session,
            calibration_registry_path,
        )
    return calculate_eligible_capital(
        load_household_facts(session, household_id),
        streams,
        load_financial_rules(financial_rules_path),
        load_methodology_rules(methodology_rules_path),
        load_liability_rules(liability_rules_path),
        analysis_date,
        load_public_data_snapshot(public_data_snapshot_path),
        calibration_port,
    )
