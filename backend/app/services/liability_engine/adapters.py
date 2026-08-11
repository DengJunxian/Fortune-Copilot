from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from datetime import date
from decimal import Decimal

from app.domain.enums import CashFlowFrequency, GoalType, LiabilityStreamType
from app.domain.financial import GoalFact, HouseholdFacts, ResponsibilityFact
from app.schemas.liability import LiabilityStreamDraft
from app.services.liability_engine.rules import LiabilityRules


def _safe_date(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def _stream_version(payload: dict[str, object], rules: LiabilityRules) -> str:
    canonical = json.dumps(
        {
            "rule_version": rules.semantic_version,
            "formula_version": rules.formula_version,
            **payload,
        },
        default=str,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_GOAL_STREAM_TYPES = {
    GoalType.EDUCATION: LiabilityStreamType.EDUCATION,
    GoalType.HOME: LiabilityStreamType.HOUSING,
    GoalType.RETIREMENT: LiabilityStreamType.RETIREMENT,
    GoalType.MEDICAL: LiabilityStreamType.MEDICAL,
    GoalType.DEBT_REPAYMENT: LiabilityStreamType.DEBT_SERVICE,
    GoalType.FAMILY_SUPPORT: LiabilityStreamType.FAMILY_SUPPORT,
    GoalType.WEALTH_TRANSFER: LiabilityStreamType.SUCCESSION,
}


def _responsibility_type(value: str) -> LiabilityStreamType:
    normalized = value.casefold()
    mappings = (
        (("educat", "教育", "学费"), LiabilityStreamType.EDUCATION),
        (("medic", "医疗", "健康"), LiabilityStreamType.MEDICAL),
        (("elder", "parent", "赡养", "养老"), LiabilityStreamType.FAMILY_SUPPORT),
        (("housing", "mortgage", "住房", "房贷"), LiabilityStreamType.HOUSING),
        (("debt", "loan", "债务", "还款"), LiabilityStreamType.DEBT_SERVICE),
        (("insurance", "protection", "保障", "保费"), LiabilityStreamType.PROTECTION),
        (("succession", "legacy", "传承"), LiabilityStreamType.SUCCESSION),
        (("philanthropy", "charity", "慈善"), LiabilityStreamType.PHILANTHROPY),
    )
    return next(
        (stream_type for keys, stream_type in mappings if any(key in normalized for key in keys)),
        LiabilityStreamType.OTHER,
    )


def _installment_base(total: Decimal, annual_growth: Decimal, count: int) -> Decimal:
    divisor = sum(((Decimal("1") + annual_growth) ** index for index in range(count)), Decimal(0))
    return total / divisor if divisor > 0 else total / Decimal(count)


def adapt_goal(
    goal: GoalFact,
    facts: HouseholdFacts,
    rules: LiabilityRules,
    analysis_date: date,
    need_links: dict[str, tuple[str, str | None]],
) -> LiabilityStreamDraft:
    stream_type = _GOAL_STREAM_TYPES.get(goal.goal_type, LiabilityStreamType.OTHER)
    is_education = stream_type == LiabilityStreamType.EDUCATION
    installments = rules.education_installment_years if is_education else 1
    start_date = (
        _safe_date(
            goal.target_date.year - installments + 1,
            goal.target_date.month,
            goal.target_date.day,
        )
        if is_education
        else goal.target_date
    )
    start_date = min(start_date, goal.target_date)
    frequency = CashFlowFrequency.ANNUAL if is_education else CashFlowFrequency.ONE_TIME
    base_amount = _installment_base(
        goal.target_amount,
        goal.annual_cost_growth_rate,
        installments,
    )
    minimum_amount = _installment_base(
        goal.minimum_acceptable_amount,
        goal.annual_cost_growth_rate,
        installments,
    )
    wealth_need_id, beneficiary_id = need_links.get(goal.id, (None, None))
    version_payload: dict[str, object] = {
        "source": "financial_goal",
        "id": goal.id,
        "version": goal.version,
        "target_amount": goal.target_amount,
        "minimum_amount": goal.minimum_acceptable_amount,
        "target_date": goal.target_date,
        "growth": goal.annual_cost_growth_rate,
        "prepared_amount": goal.prepared_amount,
        "installments": installments,
    }
    return LiabilityStreamDraft(
        wealth_need_id=wealth_need_id,
        source_goal_id=goal.id,
        beneficiary_entity_id=beneficiary_id,
        name=goal.name,
        stream_type=stream_type,
        currency=facts.currency,
        start_date=start_date,
        end_date=goal.target_date,
        frequency=frequency,
        base_amount=base_amount.quantize(Decimal("0.01")),
        minimum_amount=minimum_amount.quantize(Decimal("0.01")),
        inflation_index_code=rules.inflation_indexes[stream_type],
        annual_growth_assumption=goal.annual_cost_growth_rate,
        rigidity=goal.rigidity,
        deferrable=goal.can_defer,
        funding_sources=[
            {
                "source_type": "prepared_goal_capital",
                "source_id": goal.id,
                "amount": str(goal.prepared_amount),
                "target_total": str(goal.target_amount),
                "minimum_total": str(goal.minimum_acceptable_amount),
            }
        ],
        fallback_action="调整目标日期或金额并由客户重新确认"
        if goal.can_defer
        else "补足资金缺口或升级人工复核",
        stream_version=_stream_version(version_payload, rules),
        data_source="financial_goal_adapter",
        is_user_confirmed=goal.version > 0,
    )


def adapt_responsibility(
    responsibility: ResponsibilityFact,
    facts: HouseholdFacts,
    rules: LiabilityRules,
    analysis_date: date,
    need_links: dict[str, tuple[str, str | None]],
) -> LiabilityStreamDraft:
    del analysis_date
    stream_type = _responsibility_type(responsibility.responsibility_type)
    wealth_need_id, beneficiary_id = need_links.get(responsibility.id, (None, None))
    version_payload: dict[str, object] = {
        "source": "responsibility",
        "id": responsibility.id,
        "version": responsibility.version,
        "target_amount": responsibility.target_amount,
        "minimum_amount": responsibility.minimum_acceptable_amount,
        "target_date": responsibility.target_date,
        "growth": responsibility.annual_growth_assumption,
        "prepared_amount": responsibility.prepared_amount,
        "institutional_coverage": responsibility.institutional_coverage,
    }
    return LiabilityStreamDraft(
        wealth_need_id=wealth_need_id,
        source_responsibility_id=responsibility.id,
        beneficiary_entity_id=beneficiary_id,
        name=f"{responsibility.beneficiary} · {responsibility.responsibility_type}",
        stream_type=stream_type,
        currency=facts.currency,
        start_date=responsibility.target_date,
        end_date=responsibility.target_date,
        frequency=CashFlowFrequency.ONE_TIME,
        base_amount=responsibility.target_amount,
        minimum_amount=responsibility.minimum_acceptable_amount,
        inflation_index_code=rules.inflation_indexes[stream_type],
        annual_growth_assumption=responsibility.annual_growth_assumption,
        rigidity=responsibility.rigidity,
        deferrable=responsibility.deferrable,
        funding_sources=[
            {
                "source_type": "prepared_responsibility_capital",
                "source_id": responsibility.id,
                "amount": str(responsibility.prepared_amount),
                "target_total": str(responsibility.target_amount),
                "minimum_total": str(responsibility.minimum_acceptable_amount),
            },
            {
                "source_type": "institutional_coverage",
                "source_id": responsibility.id,
                "amount": str(responsibility.institutional_coverage),
                "note": responsibility.funding_source,
            },
        ],
        fallback_action=(
            "与家庭协商延期或替代安排"
            if responsibility.deferrable
            else "补足刚性责任资金并升级人工复核"
        ),
        stream_version=_stream_version(version_payload, rules),
        data_source="responsibility_adapter",
        is_user_confirmed=responsibility.version > 0,
    )


def adapt_goals_and_responsibilities(
    facts: HouseholdFacts,
    rules: LiabilityRules,
    analysis_date: date,
    need_links: dict[str, tuple[str, str | None]] | None = None,
) -> tuple[LiabilityStreamDraft, ...]:
    links = need_links or {}
    goals = [adapt_goal(item, facts, rules, analysis_date, links) for item in facts.goals]
    responsibilities = [
        adapt_responsibility(item, facts, rules, analysis_date, links)
        for item in facts.responsibilities
    ]
    return tuple(goals + responsibilities)
