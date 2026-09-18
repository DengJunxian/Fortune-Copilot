from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    AssetCategory,
    ClientProfileStatus,
    ComplexityBand,
    EnterpriseCashflowStability,
    EnterpriseCashflowType,
    EnterpriseInstrumentType,
    EnterpriseListedStatus,
    RiskLevel,
)
from app.models.client_profile import ClientWealthProfile
from app.models.family_enterprise import (
    EnterpriseCashflow,
    EnterpriseGuarantee,
    EnterpriseLiquidityEvent,
    EnterpriseOwnership,
    EnterpriseValuation,
)
from app.models.wealth_graph import Position
from app.schemas.family_enterprise import (
    CFSImplication,
    EconomicCapitalExposure,
    EnterpriseCashflowOut,
    EnterpriseDependencyAssessment,
    EnterpriseDependencyComponent,
    EnterpriseDetail,
    EnterpriseEventOut,
    EnterpriseGuaranteeOut,
    EnterpriseGuaranteeSummary,
    EnterpriseIncomeSummary,
    EnterpriseOwnershipOut,
    EnterpriseProfileOut,
    EnterpriseValuationOut,
    EnterpriseWealthSummary,
    FamilyEnterpriseMeta,
    FamilyEnterpriseView,
)
from app.services.financial.facts import load_household_facts
from app.services.financial.utils import ONE, ZERO, annualize, money, ratio
from app.services.financial_graph.repository import load_financial_graph

from .repository import FamilyEnterpriseRecords, load_family_enterprise_records
from .rules import (
    DependencyCode,
    FamilyEnterpriseRules,
    ensure_family_enterprise_rule_version,
    load_family_enterprise_rules,
)

_PROPERTY_CATEGORIES = {
    AssetCategory.PRIMARY_RESIDENCE,
    AssetCategory.INVESTMENT_PROPERTY,
}
_NON_ENTERPRISE_EQUITY_CATEGORIES = {
    AssetCategory.STOCK,
    AssetCategory.EQUITY_FUND,
}
_INCENTIVE_INSTRUMENTS = {
    EnterpriseInstrumentType.RESTRICTED_STOCK,
    EnterpriseInstrumentType.STOCK_OPTION,
}


def _bounded_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= ZERO:
        return ZERO
    return ratio(min(ONE, max(ZERO, numerator / denominator)))


def _record_payload(record: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: str(getattr(record, field)) for field in fields}


def _input_hash(
    records: FamilyEnterpriseRecords,
    positions: tuple[Any, ...],
    facts: Any,
    rules: FamilyEnterpriseRules,
    analysis_date: date,
) -> str:
    payload = {
        "analysis_date": analysis_date.isoformat(),
        "rules": [rules.semantic_version, rules.formula_version],
        "household": {
            "currency": facts.currency,
            "assets": [(item.id, item.version, str(item.market_value)) for item in facts.assets],
            "incomes": [(item.id, item.version, str(item.amount)) for item in facts.incomes],
        },
        "profiles": [
            _record_payload(item, ("id", "version", "currency", "listed_status", "stage"))
            for item in records.profiles
        ],
        "ownerships": [
            _record_payload(
                item,
                (
                    "id",
                    "version",
                    "enterprise_id",
                    "owner_entity_id",
                    "ownership_ratio",
                    "instrument_type",
                    "lockup_end_date",
                ),
            )
            for item in records.ownerships
        ],
        "valuations": [
            _record_payload(
                item,
                ("id", "version", "enterprise_id", "equity_value", "valuation_date"),
            )
            for item in records.valuations
        ],
        "cashflows": [
            _record_payload(
                item,
                ("id", "version", "enterprise_id", "amount", "frequency", "stability"),
            )
            for item in records.cashflows
        ],
        "guarantees": [
            _record_payload(
                item,
                ("id", "version", "enterprise_id", "outstanding_exposure", "expiry_date"),
            )
            for item in records.guarantees
        ],
        "events": [
            _record_payload(
                item,
                ("id", "version", "enterprise_id", "event_type", "expected_date", "status"),
            )
            for item in records.liquidity_events
        ],
        "positions": [
            (item.id, item.version, item.enterprise_id, str(item.market_value), item.evidence_json)
            for item in positions
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _latest_valuation(
    valuations: list[EnterpriseValuation],
    analysis_date: date,
) -> EnterpriseValuation | None:
    eligible = [
        item
        for item in valuations
        if item.valuation_date is not None and item.valuation_date <= analysis_date
    ]
    return (
        max(eligible, key=lambda item: (item.valuation_date, item.created_at))
        if eligible
        else None
    )


def _risk_capacity(session: Session, household_id: str) -> RiskLevel:
    record = session.scalar(
        select(ClientWealthProfile)
        .where(
            ClientWealthProfile.household_id == household_id,
            ClientWealthProfile.status == ClientProfileStatus.ACTIVE,
            ClientWealthProfile.is_deleted.is_(False),
        )
        .order_by(ClientWealthProfile.profile_version.desc())
    )
    return record.risk_capacity if record is not None else RiskLevel.MEDIUM


def _dependency_level(
    score: Decimal,
    has_enterprise: bool,
    rules: FamilyEnterpriseRules,
) -> ComplexityBand:
    if not has_enterprise:
        return ComplexityBand.NONE
    if score < rules.dependency_thresholds.medium_below:
        return ComplexityBand.LOW
    if score < rules.dependency_thresholds.high_at:
        return ComplexityBand.MEDIUM
    return ComplexityBand.HIGH


def _component(
    code: DependencyCode,
    label: str,
    numerator: Decimal,
    denominator: Decimal,
    weight: Decimal,
    explanation: str,
) -> EnterpriseDependencyComponent:
    component_ratio = _bounded_ratio(numerator, denominator)
    return EnterpriseDependencyComponent(
        code=code,
        label=label,
        ratio=component_ratio,
        weighted_score=ratio(component_ratio * weight),
        numerator=money(numerator),
        denominator=money(denominator),
        explanation=explanation,
    )


def get_family_enterprise_view(
    session: Session,
    household_id: str,
    rules_path: str,
    analysis_date: date,
) -> FamilyEnterpriseView:
    rules = load_family_enterprise_rules(rules_path)
    ensure_family_enterprise_rule_version(session, rules)
    session.commit()
    facts = load_household_facts(session, household_id)
    records = load_family_enterprise_records(session, household_id)
    graph = load_financial_graph(session, household_id)
    positions = tuple(graph.positions)

    ownerships_by_enterprise: dict[str, list[EnterpriseOwnership]] = defaultdict(list)
    valuations_by_enterprise: dict[str, list[EnterpriseValuation]] = defaultdict(list)
    cashflows_by_enterprise: dict[str, list[EnterpriseCashflow]] = defaultdict(list)
    guarantees_by_enterprise: dict[str, list[EnterpriseGuarantee]] = defaultdict(list)
    events_by_enterprise: dict[str, list[EnterpriseLiquidityEvent]] = defaultdict(list)
    positions_by_enterprise: dict[str, list[Position]] = defaultdict(list)
    for ownership_record in records.ownerships:
        ownerships_by_enterprise[ownership_record.enterprise_id].append(ownership_record)
    for valuation_record in records.valuations:
        valuations_by_enterprise[valuation_record.enterprise_id].append(valuation_record)
    for cashflow_record in records.cashflows:
        cashflows_by_enterprise[cashflow_record.enterprise_id].append(cashflow_record)
    for guarantee_record in records.guarantees:
        guarantees_by_enterprise[guarantee_record.enterprise_id].append(guarantee_record)
    for liquidity_record in records.liquidity_events:
        events_by_enterprise[liquidity_record.enterprise_id].append(liquidity_record)
    for position_record in positions:
        if position_record.enterprise_id is not None:
            positions_by_enterprise[position_record.enterprise_id].append(position_record)

    enterprise_details: list[EnterpriseDetail] = []
    enterprise_wealth = ZERO
    unlisted_equity = ZERO
    listed_employer_stock = ZERO
    equity_incentives = ZERO
    foreign_enterprise_wealth = ZERO
    linked_enterprise_positions = ZERO

    for profile in records.profiles:
        ownerships = ownerships_by_enterprise[profile.id]
        latest = _latest_valuation(valuations_by_enterprise[profile.id], analysis_date)
        owned_value = ZERO
        incentive_value = ZERO
        if latest is not None:
            total_ratio = min(
                ONE,
                sum((item.ownership_ratio for item in ownerships), ZERO),
            )
            owned_value = money(latest.equity_value * total_ratio)
            incentive_ratio = min(
                total_ratio,
                sum(
                    (
                        item.ownership_ratio
                        for item in ownerships
                        if item.instrument_type in _INCENTIVE_INSTRUMENTS
                    ),
                    ZERO,
                ),
            )
            incentive_value = money(latest.equity_value * incentive_ratio)
        linked_value = money(
            sum((item.market_value for item in positions_by_enterprise[profile.id]), ZERO)
        )
        linked_enterprise_positions += linked_value
        if profile.listed_status == EnterpriseListedStatus.UNLISTED:
            unlisted_equity += max(ZERO, owned_value - incentive_value)
        else:
            listed_employer_stock += linked_value or max(ZERO, owned_value - incentive_value)
        equity_incentives += incentive_value + money(
            sum(
                (
                    item.market_value
                    for item in positions_by_enterprise[profile.id]
                    if bool((item.evidence_json or {}).get("equity_incentive"))
                ),
                ZERO,
            )
        )
        enterprise_wealth += max(owned_value, linked_value)
        if profile.currency != facts.currency:
            foreign_enterprise_wealth += max(owned_value, linked_value)
        enterprise_details.append(
            EnterpriseDetail(
                profile=EnterpriseProfileOut.model_validate(profile),
                latest_valuation=(
                    EnterpriseValuationOut.model_validate(latest) if latest is not None else None
                ),
                ownerships=[EnterpriseOwnershipOut.model_validate(item) for item in ownerships],
                cashflows=[
                    EnterpriseCashflowOut.model_validate(item)
                    for item in cashflows_by_enterprise[profile.id]
                ],
                guarantees=[
                    EnterpriseGuaranteeOut.model_validate(item)
                    for item in guarantees_by_enterprise[profile.id]
                ],
                liquidity_events=[
                    EnterpriseEventOut.model_validate(item)
                    for item in events_by_enterprise[profile.id]
                ],
                household_owned_value=owned_value,
            )
        )

    household_wealth = money(sum((item.market_value for item in facts.assets), ZERO))
    property_assets = money(
        sum(
            (item.market_value for item in facts.assets if item.category in _PROPERTY_CATEGORIES),
            ZERO,
        )
    )
    financial_assets = money(
        sum(
            (
                item.market_value
                for item in facts.assets
                if item.category not in _PROPERTY_CATEGORIES
                and item.category not in {AssetCategory.VEHICLE, AssetCategory.OTHER}
            ),
            ZERO,
        )
    )
    enterprise_wealth = money(enterprise_wealth)
    economic_household_wealth = money(
        household_wealth + max(ZERO, enterprise_wealth - linked_enterprise_positions)
    )
    enterprise_wealth_ratio = _bounded_ratio(enterprise_wealth, economic_household_wealth)

    annual_enterprise_income = money(
        sum((annualize(item.amount, item.frequency) for item in records.cashflows), ZERO)
    )
    annual_household_income = money(
        sum((annualize(item.amount, item.frequency) for item in facts.incomes), ZERO)
    )
    income_denominator = max(annual_household_income, annual_enterprise_income)
    income_dependency_ratio = _bounded_ratio(annual_enterprise_income, income_denominator)
    low_stability_income = money(
        sum(
            (
                annualize(item.amount, item.frequency)
                for item in records.cashflows
                if item.stability == EnterpriseCashflowStability.LOW
            ),
            ZERO,
        )
    )

    active_guarantees = [
        item
        for item in records.guarantees
        if item.expiry_date is None or item.expiry_date >= analysis_date
    ]
    guaranteed_amount = money(sum((item.guaranteed_amount for item in active_guarantees), ZERO))
    guarantee_exposure = money(
        sum((item.outstanding_exposure for item in active_guarantees), ZERO)
    )
    pledged_positions = [
        item
        for item in positions
        if item.enterprise_id is not None and bool((item.evidence_json or {}).get("pledged"))
    ]
    pledge_exposure = money(sum((item.market_value for item in pledged_positions), ZERO))
    liquid_securities_equity = money(
        sum(
            (
                item.market_value
                for item in positions
                if item.enterprise_id is None
                and item.instrument_type in _NON_ENTERPRISE_EQUITY_CATEGORIES
            ),
            ZERO,
        )
    )

    components = [
        _component(
            "wealth_dependency",
            "财富依赖",
            enterprise_wealth,
            economic_household_wealth,
            rules.dependency_weights["wealth_dependency"],
            "企业权益占家庭经济财富的比例。",
        ),
        _component(
            "income_dependency",
            "收入依赖",
            annual_enterprise_income,
            income_denominator,
            rules.dependency_weights["income_dependency"],
            "工资、分红和经营分配对同一企业来源的依赖。",
        ),
        _component(
            "guarantee_dependency",
            "担保依赖",
            guarantee_exposure,
            economic_household_wealth,
            rules.dependency_weights["guarantee_dependency"],
            "家庭为企业承担的未偿担保暴露。",
        ),
        _component(
            "pledge_dependency",
            "质押依赖",
            pledge_exposure,
            max(financial_assets, pledge_exposure),
            rules.dependency_weights["pledge_dependency"],
            "与企业相关且已质押的持仓暴露。",
        ),
        _component(
            "currency_dependency",
            "币种依赖",
            foreign_enterprise_wealth,
            enterprise_wealth,
            rules.dependency_weights["currency_dependency"],
            "与家庭记账币种不一致的企业权益比例；当前不伪造实时汇率。",
        ),
    ]
    dependency_score = ratio(sum((item.weighted_score for item in components), ZERO))
    dependency_level = _dependency_level(dependency_score, bool(records.profiles), rules)
    labels = {
        ComplexityBand.NONE: "尚无家企暴露",
        ComplexityBand.LOW: "低企业依赖",
        ComplexityBand.MEDIUM: "中等企业依赖",
        ComplexityBand.HIGH: "高 Enterprise Dependency",
    }

    total_economic_equity = money(
        unlisted_equity + listed_employer_stock + equity_incentives + liquid_securities_equity
    )
    economic_equity_ratio = _bounded_ratio(total_economic_equity, economic_household_wealth)
    capacity = _risk_capacity(session, household_id)
    risk_ceiling_ratio = rules.risk_budget_ceiling_by_capacity[capacity]
    risk_ceiling_amount = money(economic_household_wealth * risk_ceiling_ratio)
    remaining_capacity = money(max(ZERO, risk_ceiling_amount - total_economic_equity))
    additional_allowed = remaining_capacity > ZERO and not (
        rules.high_dependency_blocks_additional_equity
        and dependency_level == ComplexityBand.HIGH
    )
    if not additional_allowed:
        remaining_capacity = ZERO

    constraints: list[str] = []
    if dependency_level == ComplexityBand.HIGH:
        constraints.append("企业依赖度高，不应因证券账户持股低而机械增加权益风险。")
    if guarantee_exposure > ZERO:
        constraints.append("先审查创始人担保的追偿边界、期限与风险隔离。")
    if pledge_exposure > ZERO:
        constraints.append("已质押企业权益不计为可自由增配的流动风险资本。")
    if any(item.lockup for item in records.liquidity_events):
        constraints.append("预期流动性事件仍受限售期约束，不将估值当作可用现金。")
    if not constraints and records.profiles:
        constraints.append("家企暴露已进入经济风险预算，后续 CFS 需继续遵守该上限。")

    all_events = sorted(
        (EnterpriseEventOut.model_validate(item) for item in records.liquidity_events),
        key=lambda item: (item.expected_date, item.id),
    )
    data_dates: list[date] = []
    data_dates.extend(
        item.valuation_date for item in records.profiles if item.valuation_date is not None
    )
    data_dates.extend(
        item.valuation_date for item in records.valuations if item.valuation_date is not None
    )
    data_dates.extend(
        item.valuation_date for item in records.cashflows if item.valuation_date is not None
    )
    data_dates.extend(
        item.valuation_date for item in records.guarantees if item.valuation_date is not None
    )
    data_dates.extend(
        item.valuation_date
        for item in records.liquidity_events
        if item.valuation_date is not None
    )
    fact_dates = [
        item.valuation_date for item in facts.assets if item.valuation_date is not None
    ] + [item.valuation_date for item in facts.incomes if item.valuation_date is not None]
    return FamilyEnterpriseView(
        meta=FamilyEnterpriseMeta(
            household_id=household_id,
            analysis_date=analysis_date,
            data_as_of=(
                max(data_dates)
                if data_dates
                else max(fact_dates, default=None)
            ),
            input_hash=_input_hash(records, positions, facts, rules, analysis_date),
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
        ),
        enterprises=enterprise_details,
        wealth=EnterpriseWealthSummary(
            household_wealth=household_wealth,
            financial_assets=financial_assets,
            property_assets=property_assets,
            enterprise_wealth=enterprise_wealth,
            economic_household_wealth=economic_household_wealth,
            enterprise_wealth_ratio=enterprise_wealth_ratio,
        ),
        income=EnterpriseIncomeSummary(
            enterprise_annual_income=annual_enterprise_income,
            household_annual_income=annual_household_income,
            dependency_ratio=income_dependency_ratio,
            low_stability_annual_income=low_stability_income,
        ),
        guarantees=EnterpriseGuaranteeSummary(
            guaranteed_amount=guaranteed_amount,
            outstanding_exposure=guarantee_exposure,
            active_count=len(active_guarantees),
        ),
        dependency=EnterpriseDependencyAssessment(
            components=components,
            score=dependency_score,
            level=dependency_level,
            label=labels[dependency_level],
            disclaimer="该分数只用于家庭财富规划中的暴露识别，不是监管评级、征信评分或企业估值结论。",
        ),
        economic_capital=EconomicCapitalExposure(
            unlisted_company_equity=money(unlisted_equity),
            listed_employer_stock=money(listed_employer_stock),
            equity_incentives=money(equity_incentives),
            liquid_securities_equity=liquid_securities_equity,
            enterprise_salary_and_dividend_dependency=money(
                sum(
                    (
                        annualize(item.amount, item.frequency)
                        for item in records.cashflows
                        if item.cashflow_type
                        in {EnterpriseCashflowType.SALARY, EnterpriseCashflowType.DIVIDEND}
                    ),
                    ZERO,
                )
            ),
            guarantee_exposure=guarantee_exposure,
            pledge_exposure=pledge_exposure,
            total_economic_equity_exposure=total_economic_equity,
            economic_equity_ratio=economic_equity_ratio,
            risk_budget_ceiling_ratio=risk_ceiling_ratio,
            risk_budget_ceiling_amount=risk_ceiling_amount,
            remaining_incremental_equity_capacity=remaining_capacity,
            additional_equity_risk_allowed=additional_allowed,
            explanation=(
                "经济权益暴露同时纳入非上市股权、雇主股、股权激励和证券账户权益。"
                "证券账户持股低不代表家庭权益风险低。"
            ),
        ),
        liquidity_events=all_events,
        cfs_implication=CFSImplication(
            status="constraints_available" if records.profiles else "not_enabled",
            constraints=constraints,
            explanation=(
                "E06 才会组装 CFS；E05 只输出必须传递给 CFS 的家企风险约束，"
                "不提前生成产品或方案。"
            ),
        ),
    )
