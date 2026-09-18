from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from threading import Lock

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AssetCategory,
    AuditEventType,
    ClientProfileStatus,
    ComplexityBand,
    FinancialEntityType,
    IncomeType,
    LifecycleStage,
    PensionStage,
    ProfileTagSeverity,
    RiskLevel,
    ServiceComplexity,
    WealthTier,
)
from app.domain.financial import HouseholdFacts
from app.models.client_profile import ClientProfileTag, ClientWealthProfile
from app.models.common import utc_now
from app.schemas.client_profile import (
    ClientProfileMeta,
    ClientProfileResponse,
    ClientProfileTagOut,
    ClientWealthProfileOut,
    ProfileCalculation,
    ProfileDataGap,
    ProfileTagDraft,
    quantize_ratio,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.financial.facts import load_household_facts
from app.services.financial_graph.engine import build_financial_graph
from app.services.financial_graph.repository import FinancialGraphRecords

from .rules import (
    ClientProfileRules,
    ensure_client_profile_rule_version,
    load_client_profile_rules,
)

_PROFILE_LOCKS = tuple(Lock() for _ in range(64))
_PROPERTY_CATEGORIES = {
    AssetCategory.PRIMARY_RESIDENCE,
    AssetCategory.INVESTMENT_PROPERTY,
}
_ANNUAL_MULTIPLIERS = {
    "monthly": Decimal("12"),
    "quarterly": Decimal("4"),
    "annual": Decimal("1"),
    "one_time": Decimal("1"),
    "irregular": Decimal("1"),
}
_LIFECYCLE_LABELS = {
    LifecycleStage.EARLY_CAREER: "初入职场",
    LifecycleStage.FAMILY_FORMATION: "家庭组建",
    LifecycleStage.PARENTING: "育儿成长",
    LifecycleStage.MATURE_FAMILY: "家庭成熟",
    LifecycleStage.RETIREMENT_PREPARATION: "退休准备",
    LifecycleStage.RETIREMENT_AND_LEGACY: "养老传承",
}
_RISK_LABELS = {
    RiskLevel.LOW: "较低",
    RiskLevel.MEDIUM_LOW: "中低",
    RiskLevel.MEDIUM: "中等",
    RiskLevel.MEDIUM_HIGH: "中高",
    RiskLevel.HIGH: "较高",
}


def _annual_amount(amount: Decimal, frequency: object) -> Decimal:
    raw = getattr(frequency, "value", str(frequency))
    return amount * _ANNUAL_MULTIPLIERS.get(str(raw), Decimal("1"))


def _money_label(amount: Decimal, currency: str) -> str:
    unit = "元" if currency == "CNY" else currency
    return f"{amount.quantize(Decimal('0.01')):,.2f} {unit}"


def _ratio_label(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.1'))}%"


def _age(birth_date: date, analysis_date: date) -> int:
    return (
        analysis_date.year
        - birth_date.year
        - ((analysis_date.month, analysis_date.day) < (birth_date.month, birth_date.day))
    )


def _risk_level(score: Decimal | None, rules: ClientProfileRules) -> RiskLevel:
    if score is None:
        return RiskLevel.LOW
    for level in RiskLevel:
        if score <= rules.risk_score_thresholds[level]:
            return level
    return RiskLevel.HIGH


def _wealth_tier(net_worth: Decimal, rules: ClientProfileRules) -> WealthTier:
    thresholds = rules.wealth_tiers
    if net_worth >= thresholds.high_net_worth_minimum:
        return WealthTier.HIGH_NET_WORTH
    if net_worth >= thresholds.affluent_minimum:
        return WealthTier.AFFLUENT
    if net_worth >= thresholds.emerging_affluent_minimum:
        return WealthTier.EMERGING_AFFLUENT
    return WealthTier.FOUNDATIONAL


def _canonical_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if hasattr(value, "value"):
        return str(value.value)
    return value


def profile_input_hash(
    facts: HouseholdFacts,
    graph: FinancialGraphRecords,
    analysis_date: date,
    rule_version: str,
    formula_version: str,
) -> str:
    graph_payload = {
        "entities": [
            {
                "id": item.id,
                "type": item.entity_type.value,
                "external_reference": item.external_reference,
                "metadata": item.metadata_json,
                "version": item.version,
            }
            for item in graph.entities
        ],
        "positions": [
            {
                "id": item.id,
                "owner": item.owner_entity_id,
                "instrument_type": item.instrument_type.value,
                "market_value": str(item.market_value),
                "currency": item.currency,
                "purpose": item.purpose_dimension.value,
                "risk": item.risk_level.value,
                "evidence": item.evidence_json,
                "version": item.version,
            }
            for item in graph.positions
        ],
        "edges": [
            {
                "id": item.id,
                "owner": item.owner_entity_id,
                "owned": item.owned_entity_id,
                "type": item.ownership_type.value,
                "version": item.version,
            }
            for item in graph.ownership_edges
        ],
    }
    payload = {
        "analysis_date": analysis_date,
        "rule_version": rule_version,
        "formula_version": formula_version,
        "facts": asdict(facts),
        "graph": graph_payload,
    }
    encoded = json.dumps(
        _canonical_value(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tag(
    code: str,
    category: str,
    value: str,
    rule: str,
    source_record_ids: list[str],
    *,
    confidence: Decimal = Decimal("0.90"),
    severity: ProfileTagSeverity = ProfileTagSeverity.INFO,
    observed: object | None = None,
) -> ProfileTagDraft:
    return ProfileTagDraft(
        tag_code=code,
        tag_category=category,
        value=value,
        confidence=confidence,
        severity=severity,
        source_record_ids=source_record_ids,
        evidence={
            "observed_value": _canonical_value(observed if observed is not None else value),
            "rule": rule,
        },
    )


def _contains_keyword(value: str | None, keywords: list[str]) -> bool:
    normalized = (value or "").casefold()
    return any(keyword.casefold() in normalized for keyword in keywords)


def _profile_gaps(
    facts: HouseholdFacts,
    graph: FinancialGraphRecords,
    rules: ClientProfileRules,
) -> tuple[Decimal, list[ProfileDataGap]]:
    available = {
        "members": bool(facts.members),
        "income": bool(facts.incomes),
        "assets": bool(graph.positions),
        "expenses": bool(facts.expenses),
        "risk": bool(facts.risk_assessments),
        "behavior": bool(facts.behavior_assessments),
        "goals": bool(facts.goals or facts.responsibilities),
    }
    descriptions = {
        "members": ("家庭成员", "补充共同承担责任的家庭成员"),
        "income": ("收入来源", "补充税后收入、稳定性与收入人"),
        "assets": ("资产与账户", "补充当前资产余额及所有权"),
        "expenses": ("家庭支出", "补充最近完整年度的实际支出"),
        "risk": ("风险能力", "完成客观风险承受能力评估"),
        "behavior": ("行为风险", "完成行为问卷或情境选择"),
        "goals": ("目标与责任", "补充教育、住房、养老等目标责任"),
    }
    gaps = [
        ProfileDataGap(
            code=domain,
            label=descriptions[domain][0],
            detail=f"尚缺少{descriptions[domain][0]}资料，相关结论将保持审慎。",
            action=descriptions[domain][1],
        )
        for domain in rules.required_profile_domains
        if not available[domain]
    ]
    score = Decimal(len(rules.required_profile_domains) - len(gaps)) / Decimal(
        len(rules.required_profile_domains)
    )
    return quantize_ratio(score), gaps


def derive_client_profile(
    facts: HouseholdFacts,
    graph: FinancialGraphRecords,
    rules: ClientProfileRules,
    analysis_date: date,
) -> ProfileCalculation:
    positions = tuple(graph.positions)
    total_assets = sum((item.market_value for item in positions), Decimal("0.00"))
    total_liabilities = sum(
        (item.outstanding_balance for item in facts.liabilities), Decimal("0.00")
    )
    net_worth = total_assets - total_liabilities
    annual_incomes = [(_annual_amount(item.amount, item.frequency), item) for item in facts.incomes]
    annual_income = sum((amount for amount, _ in annual_incomes), Decimal("0.00"))
    weighted_stability = (
        sum((amount * item.stability for amount, item in annual_incomes), Decimal("0"))
        / annual_income
        if annual_income > 0
        else Decimal("0")
    )
    largest_income_share = (
        max((amount for amount, _ in annual_incomes), default=Decimal("0")) / annual_income
        if annual_income > 0
        else Decimal("0")
    )
    property_total = sum(
        (item.market_value for item in positions if item.instrument_type in _PROPERTY_CATEGORIES),
        Decimal("0.00"),
    )
    property_ratio = property_total / total_assets if total_assets > 0 else Decimal("0")
    largest_security = max(
        (item.market_value for item in positions if item.instrument_type == AssetCategory.STOCK),
        default=Decimal("0.00"),
    )
    security_ratio = largest_security / total_assets if total_assets > 0 else Decimal("0")
    currencies = sorted({item.currency for item in positions if item.market_value > 0})
    primary_member = next(
        (item for item in facts.members if item.relationship in {"本人", "self"}),
        facts.members[0] if facts.members else None,
    )
    primary_age = _age(primary_member.birth_date, analysis_date) if primary_member else None
    child_members = [item for item in facts.members if item.relationship in {"子女", "child"}]
    occupations = [item.occupation for item in facts.members if item.occupation]
    business_income = sum(
        (amount for amount, item in annual_incomes if item.income_type == IncomeType.BUSINESS),
        Decimal("0.00"),
    )
    enterprise_entities = [
        item for item in graph.entities if item.entity_type == FinancialEntityType.ENTERPRISE
    ]
    founder = bool(enterprise_entities or business_income > 0) or any(
        _contains_keyword(occupation, rules.tag_thresholds.founder_occupation_keywords)
        for occupation in occupations
    )
    scientist = any(
        _contains_keyword(occupation, rules.tag_thresholds.scientist_occupation_keywords)
        for occupation in occupations
    )
    professional = any(
        _contains_keyword(occupation, rules.tag_thresholds.professional_occupation_keywords)
        for occupation in occupations
    )
    equity_incentive = bool(facts.planning_preferences.get("equity_incentive_holder")) or any(
        bool((item.evidence_json or {}).get("equity_incentive")) for item in positions
    )
    tier = _wealth_tier(net_worth, rules)

    risk = facts.risk_assessments[-1] if facts.risk_assessments else None
    behavior = facts.behavior_assessments[-1] if facts.behavior_assessments else None
    risk_capacity = _risk_level(risk.capacity_score if risk else None, rules)
    risk_willingness = _risk_level(risk.willingness_score if risk else None, rules)
    behavior_limit = behavior.final_behavior_limit if behavior else RiskLevel.LOW

    business_share = business_income / annual_income if annual_income > 0 else Decimal("0")
    enterprise_dependency = (
        ComplexityBand.HIGH
        if enterprise_entities or business_share >= Decimal("0.50")
        else ComplexityBand.MEDIUM
        if founder
        else ComplexityBand.NONE
    )
    cross_border = (
        ComplexityBand.HIGH
        if len(currencies) >= 3
        else ComplexityBand.MEDIUM
        if len(currencies) >= rules.tag_thresholds.cross_border_currency_count
        else ComplexityBand.NONE
    )
    has_succession_goal = any(item.goal_type.value == "wealth_transfer" for item in facts.goals)
    succession = (
        ComplexityBand.HIGH
        if net_worth >= rules.tag_thresholds.succession_high_net_worth
        else ComplexityBand.MEDIUM
        if has_succession_goal or net_worth >= rules.tag_thresholds.succession_watch_net_worth
        else ComplexityBand.NONE
    )
    if facts.lifecycle_stage == LifecycleStage.RETIREMENT_AND_LEGACY:
        pension_stage = PensionStage.RETIREMENT
    elif facts.lifecycle_stage == LifecycleStage.RETIREMENT_PREPARATION:
        pension_stage = PensionStage.TRANSITION
    elif facts.social_security_accounts or any(
        item.goal_type.value == "retirement" for item in facts.goals
    ):
        pension_stage = PensionStage.ACCUMULATION
    else:
        pension_stage = PensionStage.NOT_STARTED

    tags: list[ProfileTagDraft] = [
        _tag(
            f"life_stage_{facts.lifecycle_stage.value}",
            "life_stage",
            facts.lifecycle_stage.value,
            "采用已确认家庭阶段，并由成员年龄与目标资料交叉核对",
            [facts.id, *(item.id for item in facts.members)],
            confidence=Decimal("0.98"),
            observed=facts.lifecycle_stage.value,
        ),
        _tag(
            f"wealth_tier_{tier.value}",
            "wealth_tier",
            tier.value,
            "按金融图资产减现有负债后的净值区间分类，仅用于规划复杂度",
            [*(item.id for item in positions), *(item.id for item in facts.liabilities)],
            observed=str(net_worth),
        ),
    ]
    if primary_age is not None and primary_age <= rules.tag_thresholds.young_worker_max_age:
        tags.append(
            _tag(
                "young_worker",
                "life_stage",
                f"主要规划人 {primary_age} 岁",
                "主要规划人年龄不高于青年工作者上限",
                [primary_member.id] if primary_member else [],
                observed=primary_age,
            )
        )
    if facts.lifecycle_stage in {LifecycleStage.PARENTING, LifecycleStage.MATURE_FAMILY}:
        tags.append(
            _tag(
                "middle_class_family",
                "family_structure",
                f"{len(facts.members)} 位家庭成员，处于{facts.lifecycle_stage.value}",
                "家庭处于育儿或成熟阶段且存在共同责任",
                [item.id for item in facts.members],
                observed={"member_count": len(facts.members)},
            )
        )
    if professional and annual_income >= rules.tag_thresholds.high_income_annual_amount:
        tags.append(
            _tag(
                "high_income_professional",
                "income_structure",
                "专业职业收入达到高收入观察线",
                "专业职业关键词与家庭年收入观察线同时满足",
                [*(item.id for item in facts.members), *(item.id for item in facts.incomes)],
                observed=str(annual_income),
            )
        )
    if founder:
        tags.append(
            _tag(
                "founder",
                "enterprise_link",
                "家庭收入或所有权关系与企业相关",
                "企业主体、经营收入或创始人职业信息任一成立",
                [*(item.id for item in enterprise_entities), *(item.id for item in facts.incomes)],
                severity=ProfileTagSeverity.WATCH,
                observed={
                    "enterprise_entities": len(enterprise_entities),
                    "business_share": str(business_share),
                },
            )
        )
    if scientist:
        tags.append(
            _tag(
                "scientist",
                "career_structure",
                "科研或学术职业特征",
                "职业信息命中科研、研究员、科学家或教授关键词",
                [item.id for item in facts.members],
                observed=occupations,
            )
        )
    if pension_stage == PensionStage.RETIREMENT:
        tags.append(
            _tag(
                "retiree",
                "pension_stage",
                "已进入退休与传承阶段",
                "家庭生命周期为退休与传承",
                [facts.id],
                observed=facts.lifecycle_stage.value,
            )
        )
    elif pension_stage in {PensionStage.ACCUMULATION, PensionStage.TRANSITION}:
        tags.append(
            _tag(
                "retirement_accumulation",
                "pension_stage",
                pension_stage.value,
                "存在退休目标、养老账户或处于退休准备阶段",
                [
                    *(item.id for item in facts.goals),
                    *(item.id for item in facts.social_security_accounts),
                ],
                observed=pension_stage.value,
            )
        )
    if len([item for item in annual_incomes if item[1].income_type == IncomeType.EMPLOYMENT]) >= 2:
        tags.append(
            _tag(
                "dual_income_household",
                "income_structure",
                "至少两项工作收入",
                "活动工作收入来源数量不少于两项",
                [item.id for _, item in annual_incomes],
                observed=len(annual_incomes),
            )
        )
    if weighted_stability < rules.tag_thresholds.income_stability_watch_below:
        tags.append(
            _tag(
                "income_stability_watch",
                "income_stability",
                "收入稳定性需要关注",
                "按年化收入加权后的稳定性低于观察阈值",
                [item.id for _, item in annual_incomes],
                severity=ProfileTagSeverity.WATCH,
                observed=str(weighted_stability),
            )
        )
    if largest_income_share > rules.tag_thresholds.income_concentration_watch_above:
        tags.append(
            _tag(
                "single_income_concentration",
                "income_structure",
                "收入集中在单一来源",
                "最大收入来源占比高于观察阈值",
                [item.id for _, item in annual_incomes],
                severity=ProfileTagSeverity.WATCH,
                observed=str(largest_income_share),
            )
        )
    if property_ratio > rules.tag_thresholds.property_concentration_watch_above:
        tags.append(
            _tag(
                "property_concentration",
                "asset_structure",
                "房产占家庭资产比例较高",
                "房产市值占金融图资产总额比例高于观察阈值",
                [item.id for item in positions if item.instrument_type in _PROPERTY_CATEGORIES],
                severity=ProfileTagSeverity.WATCH,
                observed=str(property_ratio),
            )
        )
    if security_ratio > rules.tag_thresholds.single_security_concentration_watch_above:
        tags.append(
            _tag(
                "single_security_concentration",
                "asset_structure",
                "单一股票持仓集中",
                "最大单一股票占金融图资产总额比例高于观察阈值",
                [item.id for item in positions if item.instrument_type == AssetCategory.STOCK],
                severity=ProfileTagSeverity.HIGH,
                observed=str(security_ratio),
            )
        )
    if enterprise_dependency != ComplexityBand.NONE:
        tags.append(
            _tag(
                "enterprise_link",
                "enterprise_link",
                enterprise_dependency.value,
                "存在企业主体、经营收入或创始人职业证据",
                [*(item.id for item in enterprise_entities), *(item.id for item in facts.incomes)],
                severity=ProfileTagSeverity.WATCH,
                observed=enterprise_dependency.value,
            )
        )
    if equity_incentive:
        tags.append(
            _tag(
                "equity_incentive_holder",
                "asset_structure",
                "存在已确认股权激励信息",
                "客户偏好或持仓证据明确标记股权激励",
                [facts.id, *(item.id for item in positions)],
                severity=ProfileTagSeverity.WATCH,
                observed=True,
            )
        )
    if len(child_members) >= 2:
        tags.append(
            _tag(
                "two_child_family",
                "family_structure",
                f"{len(child_members)} 名子女",
                "家庭成员中子女数量不少于两名",
                [item.id for item in child_members],
                observed=len(child_members),
            )
        )
    if len(facts.members) >= rules.tag_thresholds.family_complexity_member_count:
        tags.append(
            _tag(
                "family_complexity",
                "family_structure",
                f"{len(facts.members)} 位共同责任成员",
                "共同责任成员数量达到复杂家庭观察线",
                [item.id for item in facts.members],
                severity=ProfileTagSeverity.WATCH,
                observed=len(facts.members),
            )
        )
    if cross_border != ComplexityBand.NONE:
        tags.append(
            _tag(
                "currency_exposure",
                "currency_exposure",
                "、".join(currencies),
                "金融图中非零持仓涉及至少两种币种",
                [item.id for item in positions],
                severity=ProfileTagSeverity.WATCH,
                observed=currencies,
            )
        )
    education_goals = [item for item in facts.goals if item.goal_type.value == "education"]
    if education_goals and cross_border != ComplexityBand.NONE:
        tags.append(
            _tag(
                "foreign_education_liability",
                "goal_structure",
                "教育目标存在跨币种匹配需求",
                "教育目标与多币种资产暴露同时存在",
                [*(item.id for item in education_goals), *(item.id for item in positions)],
                severity=ProfileTagSeverity.WATCH,
                observed=currencies,
            )
        )

    complexity_score = sum(
        (
            2
            if enterprise_dependency == ComplexityBand.HIGH
            else 1
            if enterprise_dependency != ComplexityBand.NONE
            else 0,
            2
            if cross_border == ComplexityBand.HIGH
            else 1
            if cross_border != ComplexityBand.NONE
            else 0,
            2
            if succession == ComplexityBand.HIGH
            else 1
            if succession != ComplexityBand.NONE
            else 0,
            1 if len(facts.members) >= rules.tag_thresholds.family_complexity_member_count else 0,
            1 if property_ratio > rules.tag_thresholds.property_concentration_watch_above else 0,
        )
    )
    complexity_rules = rules.service_complexity
    service_complexity = (
        ServiceComplexity.SPECIALIST
        if complexity_score >= complexity_rules.specialist_score
        else ServiceComplexity.COMPLEX
        if complexity_score >= complexity_rules.complex_score
        else ServiceComplexity.ENHANCED
        if complexity_score >= complexity_rules.enhanced_score
        else ServiceComplexity.STANDARD
    )
    completeness, gaps = _profile_gaps(facts, graph, rules)
    profile_hash = profile_input_hash(
        facts,
        graph,
        analysis_date,
        rules.semantic_version,
        rules.formula_version,
    )
    status = ClientProfileStatus.NEEDS_REVIEW if gaps else ClientProfileStatus.ACTIVE
    age_label = (
        f"主要规划人年龄 {primary_age} 岁" if primary_age is not None else "主要规划人年龄待补充"
    )
    income_label = _money_label(annual_income, facts.currency)
    stability_label = _ratio_label(weighted_stability)
    assets_label = _money_label(total_assets, facts.currency)
    liabilities_label = _money_label(total_liabilities, facts.currency)
    property_label = _ratio_label(property_ratio)
    behavior_count = len(behavior.detected_biases) if behavior else 0
    explanation = {
        "household_stage": (
            f"家庭当前处于{_LIFECYCLE_LABELS[facts.lifecycle_stage]}阶段，{age_label}。"
        ),
        "income_and_career": (
            f"已识别 {len(facts.incomes)} 项收入来源，年化收入合计 {income_label}，"
            f"加权稳定性 {stability_label}。"
        ),
        "asset_liability_features": (
            f"金融图资产 {assets_label}，现有负债 {liabilities_label}；房产占比 {property_label}。"
        ),
        "goals_and_responsibilities": (
            f"已识别 {len(facts.goals)} 项目标与 {len(facts.responsibilities)} 项家庭责任。"
        ),
        "risk_capacity": (
            f"风险能力为{_RISK_LABELS[risk_capacity]}，风险意愿为{_RISK_LABELS[risk_willingness]}。"
        ),
        "behavior_risk": (
            f"行为风险上限为{_RISK_LABELS[behavior_limit]}；已记录 {behavior_count} 项行为观察。"
        ),
        "profile_boundary": "本页是动态财富规划画像，不是营销分群，也不直接生成产品推荐。",
    }
    return ProfileCalculation(
        lifecycle_stage=facts.lifecycle_stage,
        wealth_tier=tier,
        service_complexity=service_complexity,
        risk_capacity=risk_capacity,
        risk_willingness=risk_willingness,
        behavior_limit=behavior_limit,
        enterprise_dependency_level=enterprise_dependency,
        cross_border_complexity=cross_border,
        succession_complexity=succession,
        pension_stage=pension_stage,
        completeness_score=completeness,
        data_gaps=gaps,
        profile_hash=profile_hash,
        source_snapshot_id=f"profile-input:{profile_hash[:48]}",
        status=status,
        explanation=explanation,
        tags=sorted(tags, key=lambda item: item.tag_code),
        rule_version=rules.semantic_version,
        formula_version=rules.formula_version,
    )


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


def _profile_tags(
    session: Session,
    household_id: str,
    profile_id: str,
) -> tuple[ClientProfileTag, ...]:
    return tuple(
        session.scalars(
            select(ClientProfileTag)
            .where(
                ClientProfileTag.household_id == household_id,
                ClientProfileTag.profile_id == profile_id,
                ClientProfileTag.is_deleted.is_(False),
            )
            .order_by(ClientProfileTag.tag_category, ClientProfileTag.tag_code)
        ).all()
    )


def _response(
    session: Session,
    household_id: str,
    profile: ClientWealthProfile,
) -> ClientProfileResponse:
    household = ensure_household(session, household_id)
    tags = _profile_tags(session, household_id, profile.id)
    return ClientProfileResponse(
        meta=ClientProfileMeta(
            household_id=household_id,
            analysis_date=profile.valuation_date or date.today(),
            data_as_of=profile.valuation_date,
            input_version=household.version,
            source_snapshot_id=profile.source_snapshot_id,
            rule_version=profile.rule_version,
            formula_version=profile.formula_version,
            synthetic_data=household.is_synthetic,
        ),
        profile=ClientWealthProfileOut.model_validate(profile),
        tags=[ClientProfileTagOut.model_validate(item) for item in tags],
    )


def get_client_profile(
    session: Session,
    household_id: str,
) -> ClientProfileResponse:
    profile = _latest_profile(session, household_id)
    if profile is None:
        ensure_household(session, household_id)
        raise AppError(
            "client_profile_not_calculated",
            "客户财富画像尚未计算",
            status_code=404,
        )
    return _response(session, household_id, profile)


def recalculate_client_profile(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> ClientProfileResponse:
    profile_lock = _PROFILE_LOCKS[hash(household_id) % len(_PROFILE_LOCKS)]
    with profile_lock:
        household = ensure_household(session, household_id)
        graph = build_financial_graph(session, household_id, actor)
        facts = load_household_facts(session, household_id)
        rules = load_client_profile_rules(rules_path)
        calculation = derive_client_profile(facts, graph, rules, analysis_date)
        current = _latest_profile(session, household_id)
        if current is not None and current.profile_hash == calculation.profile_hash:
            return _response(session, household_id, current)

        ensure_client_profile_rule_version(session, rules)
        if current is not None:
            current.status = ClientProfileStatus.SUPERSEDED
            current.version += 1
            current.updated_at = utc_now()
            add_audit_event(
                session,
                current,
                actor,
                AuditEventType.DATA_UPDATED,
                "客户财富画像被新事实版本替代",
            )
        next_version = (
            int(
                session.scalar(
                    select(func.max(ClientWealthProfile.profile_version)).where(
                        ClientWealthProfile.household_id == household_id
                    )
                )
                or 0
            )
            + 1
        )
        profile = ClientWealthProfile(
            household_id=household_id,
            profile_version=next_version,
            source_snapshot_id=calculation.source_snapshot_id,
            rule_version=calculation.rule_version,
            formula_version=calculation.formula_version,
            lifecycle_stage=calculation.lifecycle_stage,
            wealth_tier=calculation.wealth_tier,
            service_complexity=calculation.service_complexity,
            risk_capacity=calculation.risk_capacity,
            risk_willingness=calculation.risk_willingness,
            behavior_limit=calculation.behavior_limit,
            enterprise_dependency_level=calculation.enterprise_dependency_level,
            cross_border_complexity=calculation.cross_border_complexity,
            succession_complexity=calculation.succession_complexity,
            pension_stage=calculation.pension_stage,
            completeness_score=calculation.completeness_score,
            data_gaps=[item.model_dump(mode="json") for item in calculation.data_gaps],
            profile_hash=calculation.profile_hash,
            status=calculation.status,
            explanation=calculation.explanation,
            currency=facts.currency,
            valuation_date=analysis_date,
            data_source="v5_client_profile_engine",
            is_user_confirmed=household.is_user_confirmed,
        )
        session.add(profile)
        session.flush()
        add_audit_event(
            session,
            profile,
            actor,
            AuditEventType.CALCULATION_EXECUTED,
            "确定性计算动态客户财富画像",
        )
        for draft in calculation.tags:
            tag = ClientProfileTag(
                household_id=household_id,
                profile_id=profile.id,
                **draft.model_dump(mode="python"),
                currency=facts.currency,
                valuation_date=analysis_date,
                data_source="v5_profile_tag_engine",
                is_user_confirmed=household.is_user_confirmed,
            )
            session.add(tag)
            session.flush()
            add_audit_event(
                session,
                tag,
                actor,
                AuditEventType.RULE_APPLIED,
                f"生成客户画像标签 {tag.tag_code}",
            )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            winner = _latest_profile(session, household_id)
            if winner is not None and winner.profile_hash == calculation.profile_hash:
                return _response(session, household_id, winner)
            raise AppError(
                "client_profile_conflict",
                "客户画像计算与另一版本冲突，请重试",
                status_code=409,
            ) from exc
        session.refresh(profile)
        return _response(session, household_id, profile)
