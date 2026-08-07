from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import AuditEventType
from app.domain.financial import HouseholdFacts
from app.models.assessment import FinancialMetric, FinancialSnapshot
from app.models.governance import AuditEvent
from app.schemas.financial_analysis import (
    AnalysisMeta,
    FinancialAnalysisResponse,
    HouseholdProfile,
    MemberSummary,
    PersistedAnalysisRun,
)
from app.services.financial.diagnostics import diagnose_data
from app.services.financial.facts import load_household_facts
from app.services.financial.metrics import (
    MetricContext,
    build_health_dimensions,
    build_metrics,
)
from app.services.financial.protection import assess_protection
from app.services.financial.purchasing_power import assess_purchasing_power
from app.services.financial.rules import (
    FinancialRules,
    ensure_rule_version,
    load_financial_rules,
)
from app.services.financial.statements import build_statements


def _age_on(birth_date: date, on_date: date) -> int:
    return (
        on_date.year
        - birth_date.year
        - ((on_date.month, on_date.day) < (birth_date.month, birth_date.day))
    )


def _input_version(facts: HouseholdFacts, analysis_date: date) -> str:
    payload = {
        "analysis_date": analysis_date.isoformat(),
        "facts": asdict(facts),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _data_as_of(facts: HouseholdFacts, analysis_date: date) -> date:
    dates = [
        record.valuation_date
        for collection in (
            facts.incomes,
            facts.expenses,
            facts.assets,
            facts.liabilities,
            facts.insurance_policies,
            facts.social_security_accounts,
            facts.goals,
        )
        for record in collection
        if record.valuation_date is not None
    ]
    return min(dates) if dates else analysis_date


def _profile(facts: HouseholdFacts, analysis_date: date) -> HouseholdProfile:
    return HouseholdProfile(
        name=facts.name,
        lifecycle_stage=facts.lifecycle_stage.value,
        region=facts.region,
        members=[
            MemberSummary(
                id=item.id,
                display_name=item.display_name,
                relationship=item.relationship,
                age=max(0, _age_on(item.birth_date, analysis_date)),
                occupation=item.occupation,
                employment_stability=item.employment_stability.value,
                health_risk_level=item.health_risk_level.value,
            )
            for item in facts.members
        ],
        data_source=facts.data_source,
        is_user_confirmed=facts.is_user_confirmed,
    )


def analyze_facts(
    facts: HouseholdFacts,
    rules: FinancialRules,
    analysis_date: date,
) -> FinancialAnalysisResponse:
    data_as_of = _data_as_of(facts, analysis_date)
    statements = build_statements(facts, rules, analysis_date)
    protection = assess_protection(facts, statements, rules, analysis_date)
    purchasing_power = assess_purchasing_power(facts, statements, rules, data_as_of)
    diagnostics = diagnose_data(facts, statements, rules, analysis_date)
    metric_context = MetricContext(
        facts=facts,
        statements=statements,
        protection=protection,
        rules=rules,
        data_as_of=data_as_of,
        analysis_date=analysis_date,
    )
    metrics = build_metrics(metric_context)
    return FinancialAnalysisResponse(
        meta=AnalysisMeta(
            household_id=facts.id,
            household_code=facts.code,
            analysis_date=analysis_date,
            data_as_of=data_as_of,
            input_version=_input_version(facts, analysis_date),
            formula_version=rules.formula_version,
            rule_code=rules.code,
            rule_version=rules.semantic_version,
            currency=facts.currency,
            synthetic_data=facts.is_synthetic,
        ),
        profile=_profile(facts, analysis_date),
        statements=statements,
        metrics=metrics,
        diagnostics=diagnostics,
        protection=protection,
        purchasing_power=purchasing_power,
        health_dimensions=build_health_dimensions(metrics),
    )


def analyze_household(
    session: Session,
    household_id: str,
    rules_path: str,
    analysis_date: date,
) -> FinancialAnalysisResponse:
    facts = load_household_facts(session, household_id)
    rules = load_financial_rules(rules_path)
    return analyze_facts(facts, rules, analysis_date)


def persist_analysis(
    session: Session,
    analysis: FinancialAnalysisResponse,
    rules: FinancialRules,
    actor: ActorContext,
) -> PersistedAnalysisRun:
    rule_version = ensure_rule_version(session, rules)
    snapshot = FinancialSnapshot(
        household_id=analysis.meta.household_id,
        snapshot_date=analysis.meta.analysis_date,
        input_version=analysis.meta.input_version,
        rule_version_id=rule_version.id,
        calculation_source="deterministic_tools",
        structured_data=analysis.model_dump(mode="json"),
        currency=analysis.meta.currency,
        valuation_date=analysis.meta.data_as_of,
        data_source="deterministic_financial_engine",
        is_user_confirmed=False,
    )
    session.add(snapshot)
    session.flush()
    for metric in analysis.metrics:
        session.add(
            FinancialMetric(
                household_id=analysis.meta.household_id,
                snapshot_id=snapshot.id,
                metric_code=metric.metric_id,
                value=metric.result,
                numerator=metric.numerator,
                denominator=metric.denominator,
                unit=metric.unit,
                status=metric.status,
                is_applicable=metric.applicability.applicable,
                formula_version=analysis.meta.formula_version,
                threshold_version=metric.threshold_version,
                evidence=metric.model_dump(mode="json"),
                currency=analysis.meta.currency,
                valuation_date=analysis.meta.data_as_of,
                data_source="deterministic_financial_engine",
                is_user_confirmed=False,
            )
        )
    event = AuditEvent(
        household_id=analysis.meta.household_id,
        event_type=AuditEventType.CALCULATION_EXECUTED,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        entity_type="FinancialSnapshot",
        entity_id=snapshot.id,
        event_version=snapshot.version,
        summary=(
            f"执行确定性财务体检，公式 {analysis.meta.formula_version}，"
            f"规则 {analysis.meta.rule_version}"
        ),
        occurred_at=snapshot.created_at,
        valuation_date=analysis.meta.data_as_of,
        data_source="deterministic_financial_engine",
        is_user_confirmed=True,
    )
    session.add(event)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "analysis_persistence_failed",
            "财务体检结果无法保存",
            status_code=409,
        ) from exc
    session.refresh(snapshot)
    return PersistedAnalysisRun(
        snapshot_id=snapshot.id,
        household_id=analysis.meta.household_id,
        input_version=analysis.meta.input_version,
        rule_version_id=rule_version.id,
        rule_version=rules.semantic_version,
        metric_count=len(analysis.metrics),
        created_at=snapshot.created_at,
    )


def json_export_payload(analysis: FinancialAnalysisResponse) -> dict[str, Any]:
    return analysis.model_dump(mode="json")
