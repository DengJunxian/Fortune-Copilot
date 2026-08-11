from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.config import Settings
from app.core.errors import AppError
from app.models.family import Household
from app.schemas.cfs import CFSComposeRequest
from app.schemas.monitoring import MonitoringEvaluateRequest
from app.schemas.persona_release import (
    GoldenAssertionResult,
    PersonaDatasetQuality,
    PersonaPipelineResult,
    PersonaReleaseResponse,
    ReleaseBenchmarkMetric,
)
from app.schemas.product_ontology import (
    ProductEligibilityContext,
    ProductRankRequest,
    ProductRiskBudgetInput,
)
from app.services.cfs_composer.engine import compose_cfs_solution
from app.services.client_profile.engine import get_client_profile
from app.services.currency_exposure.engine import get_currency_exposures
from app.services.family_enterprise.engine import get_family_enterprise_view
from app.services.financial.engine import analyze_facts
from app.services.financial.facts import load_household_facts
from app.services.financial.rules import load_financial_rules
from app.services.liability_engine.engine import materialize_liability_streams
from app.services.monitoring.engine import evaluate_monitoring
from app.services.philanthropy.engine import get_philanthropy_goals
from app.services.product_ontology.adapter import ensure_verified_fund_ontology
from app.services.product_ontology.ranking import rank_products
from app.services.retirement.engine import get_retirement_plan
from app.services.seed import read_dataset, seed_synthetic_data
from app.services.trust_succession.engine import get_trust_succession_needs
from app.services.wealth_needs.engine import get_wealth_needs

ZERO = Decimal("0")
ONE = Decimal("1")
BOUNDARY = (
    "V5 Release Benchmark 仅验证合成 Persona 的本地确定性流水线；"
    "不代表银行生产数据、客户结果、产品销售资格或投资表现。"
)


class ComposeKwargs(TypedDict):
    financial_rules_path: str
    planning_rules_path: str
    methodology_rules_path: str
    public_data_snapshot_path: str
    client_profile_rules_path: str
    liability_rules_path: str
    family_enterprise_rules_path: str
    cfs_rules_path: str
    analysis_date: date


def _actor(actor_id: str = "v5-persona-release") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=actor_id,
        role="admin",
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        auth_source="demo_headers",
    )


def _read_json(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(
            "v5_release_fixture_invalid",
            "V5 发布基准或 Golden Outcome 无法读取",
            status_code=500,
            details={"path": path},
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            "v5_release_fixture_invalid",
            "V5 发布基准必须是 JSON 对象",
            status_code=500,
            details={"path": path},
        )
    return payload


def _dataset_quality(settings: Settings) -> PersonaDatasetQuality:
    dataset = read_dataset(settings.v5_persona_data_path)
    household_codes = [item.household.code for item in dataset.households]
    profile_codes = [item.household.demo_profile for item in dataset.households]
    required_collections = (
        "members",
        "consents",
        "incomes",
        "expenses",
        "assets",
        "insurance_policies",
        "goals",
        "risk_assessments",
        "behavior_assessments",
    )
    complete = sum(
        bool(getattr(bundle, collection))
        for bundle in dataset.households
        for collection in required_collections
    )
    expected = len(dataset.households) * len(required_collections)
    household_unique = Decimal(len(set(household_codes))) / Decimal(len(household_codes))
    profile_unique = Decimal(len(set(profile_codes))) / Decimal(len(profile_codes))
    completeness = Decimal(complete) / Decimal(expected)
    reference_integrity = ONE
    passed = all(
        value == ONE
        for value in (
            household_unique,
            profile_unique,
            completeness,
            reference_integrity,
        )
    ) and len(dataset.households) == 8
    return PersonaDatasetQuality(
        household_count=len(dataset.households),
        persona_count=len(dataset.personas),
        enterprise_extension_count=len(dataset.enterprise_extensions),
        unique_household_code_rate=household_unique,
        unique_profile_code_rate=profile_unique,
        required_collection_completeness_rate=completeness,
        reference_integrity_rate=reference_integrity,
        passed=passed,
        evidence={
            "schema_version": dataset.schema_version,
            "household_codes": household_codes,
            "required_collection_checks": expected,
            "required_collection_checks_passed": complete,
            "reference_validation": "pydantic_model_validator",
        },
    )


def _resolve_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppError(
            "v5_golden_value_invalid",
            "Golden Outcome 数值无法比较",
            status_code=500,
            details={"value": value},
        ) from exc


def _assertion_passed(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return bool(actual == expected)
    if operator == "contains":
        return isinstance(actual, list) and expected in actual
    if operator == "contains_all":
        return bool(
            isinstance(actual, list)
            and isinstance(expected, list)
            and set(expected) <= set(actual)
        )
    if operator == "gte":
        return _decimal(actual) >= _decimal(expected)
    if operator == "lte":
        return _decimal(actual) <= _decimal(expected)
    raise AppError(
        "v5_golden_operator_invalid",
        "Golden Outcome 使用了未知比较符",
        status_code=500,
        details={"operator": operator},
    )


def _evaluate_assertions(
    normalized: dict[str, Any],
    assertions: list[dict[str, Any]],
) -> list[GoldenAssertionResult]:
    results: list[GoldenAssertionResult] = []
    for assertion in assertions:
        code = str(assertion["code"])
        path = str(assertion["path"])
        operator = str(assertion["operator"])
        expected = assertion.get("expected")
        actual = _resolve_path(normalized, path)
        results.append(
            GoldenAssertionResult(
                code=code,
                path=path,
                operator=operator,
                expected=expected,
                actual=actual,
                passed=_assertion_passed(actual, operator, expected),
            )
        )
    return results


def _specialist_types(*routes: Any, cfs_referrals: list[Any]) -> list[str]:
    result = {
        item.specialist_type.value
        for item in cfs_referrals
        if item.specialist_type is not None
    }
    for route in routes:
        if route is not None and route.specialist_type is not None:
            result.add(route.specialist_type.value)
    return sorted(result)


def _run_persona(
    session: Session,
    household: Household,
    settings: Settings,
    golden: dict[str, Any],
    analysis_date: date,
    actor: ActorContext,
) -> PersonaPipelineResult:
    compose_kwargs: ComposeKwargs = {
        "financial_rules_path": settings.financial_rules_path,
        "planning_rules_path": settings.planning_rules_path,
        "methodology_rules_path": settings.methodology_rules_path,
        "public_data_snapshot_path": settings.public_data_snapshot_path,
        "client_profile_rules_path": settings.client_profile_rules_path,
        "liability_rules_path": settings.liability_rules_path,
        "family_enterprise_rules_path": settings.family_enterprise_rules_path,
        "cfs_rules_path": settings.cfs_rules_path,
        "analysis_date": analysis_date,
    }
    cfs = compose_cfs_solution(
        session,
        household.id,
        CFSComposeRequest(is_user_confirmed=True),
        actor,
        **compose_kwargs,
    )
    replay = compose_cfs_solution(
        session,
        household.id,
        CFSComposeRequest(is_user_confirmed=True),
        actor,
        **compose_kwargs,
    )
    profile = get_client_profile(session, household.id)
    needs = get_wealth_needs(session, household.id)
    liabilities = materialize_liability_streams(
        session,
        household.id,
        actor,
        settings.liability_rules_path,
        analysis_date,
    )
    currency = get_currency_exposures(
        session,
        household.id,
        actor,
        settings.specialized_cfs_rules_path,
        analysis_date,
    )
    trust = get_trust_succession_needs(
        session,
        household.id,
        actor,
        settings.specialized_cfs_rules_path,
        analysis_date,
    )
    philanthropy = get_philanthropy_goals(
        session,
        household.id,
        actor,
        settings.specialized_cfs_rules_path,
        analysis_date,
    )
    retirement = get_retirement_plan(
        session,
        household.id,
        actor,
        settings.specialized_cfs_rules_path,
        analysis_date,
    )
    enterprise = get_family_enterprise_view(
        session,
        household.id,
        settings.family_enterprise_rules_path,
        analysis_date,
    )
    monitoring = evaluate_monitoring(
        session,
        household.id,
        actor,
        MonitoringEvaluateRequest(
            analysis_date=analysis_date,
            is_user_confirmed=True,
        ),
        settings.monitoring_rules_path,
        settings.family_enterprise_rules_path,
        settings.specialized_cfs_rules_path,
    )
    facts = load_household_facts(session, household.id)
    financial = analyze_facts(
        facts,
        load_financial_rules(settings.financial_rules_path),
        analysis_date,
    )
    balance = financial.statements.balance_sheet
    cash_flow = financial.statements.cash_flow
    financial_correct = (
        balance.total_assets - balance.total_liabilities == balance.net_worth
        and cash_flow.annual_income - cash_flow.annual_expenses == cash_flow.annual_surplus
        and all(item.market_value >= ZERO for item in balance.assets)
        and all(item.outstanding_balance >= ZERO for item in balance.liabilities)
    )
    no_action_required = any(item.component_type.value == "no_action" for item in cfs.components)
    specialists = _specialist_types(
        currency.route,
        *trust.routes,
        philanthropy.route,
        retirement.route,
        cfs_referrals=cfs.referrals,
    )
    preference_target = facts.planning_preferences.get("family_liquidity_isolation_target")
    family_liquidity_isolation_exists = (
        preference_target is not None
        and _decimal(preference_target) > ZERO
        and financial.statements.liquidity.emergency_liquid_assets > ZERO
        and enterprise.guarantees.outstanding_exposure > ZERO
    )
    normalized: dict[str, Any] = {
        "profile": {
            "completeness_score": str(profile.profile.completeness_score),
            "enterprise_dependency_level": profile.profile.enterprise_dependency_level.value,
            "cross_border_complexity": profile.profile.cross_border_complexity.value,
            "succession_complexity": profile.profile.succession_complexity.value,
            "pension_stage": profile.profile.pension_stage.value,
            "tags": sorted(item.tag_code for item in profile.tags),
        },
        "needs": {"types": sorted({item.need_type.value for item in needs.needs})},
        "liability": {
            "types": sorted({item.stream.stream_type.value for item in liabilities.entries})
        },
        "cfs": {
            "component_types": sorted({item.component_type.value for item in cfs.components}),
            "no_action_required": no_action_required,
            "additional_risk_allowed": cfs.risk_budget.additional_risk_allowed,
            "decision": cfs.risk_budget.decision,
        },
        "monitoring": {
            "alert_types": sorted({item.policy_type.value for item in monitoring.alerts})
        },
        "specialists": {"types": specialists},
        "currency": {"currencies": sorted(item.currency for item in currency.summaries)},
        "enterprise": {
            "dependency_level": enterprise.dependency.level.value,
            "family_liquidity_isolation_exists": family_liquidity_isolation_exists,
            "additional_equity_risk_allowed": (
                enterprise.economic_capital.additional_equity_risk_allowed
            ),
        },
        "financial": {
            "accounting_identity_valid": financial_correct,
            "total_assets": str(balance.total_assets),
            "total_liabilities": str(balance.total_liabilities),
            "net_worth": str(balance.net_worth),
        },
    }
    assertion_rows = golden.get("assertions", [])
    if not isinstance(assertion_rows, list):
        raise AppError(
            "v5_golden_fixture_invalid",
            "Persona Golden assertions 必须是数组",
            status_code=500,
            details={"household_code": household.code},
        )
    assertions = _evaluate_assertions(normalized, assertion_rows)
    decision_replay = replay.meta.idempotent_replay and replay.solution.id == cfs.solution.id
    return PersonaPipelineResult(
        household_id=household.id,
        household_code=household.code,
        passed=all(item.passed for item in assertions)
        and decision_replay
        and financial_correct,
        profile_completeness=profile.profile.completeness_score,
        wealth_need_types=normalized["needs"]["types"],
        liability_stream_types=normalized["liability"]["types"],
        cfs_component_types=normalized["cfs"]["component_types"],
        monitoring_alert_types=normalized["monitoring"]["alert_types"],
        specialist_types=specialists,
        no_action_required=no_action_required,
        additional_risk_allowed=cfs.risk_budget.additional_risk_allowed,
        decision_replay=decision_replay,
        financial_correct=financial_correct,
        normalized_outcome=normalized,
        assertions=assertions,
    )


def _product_ranking_conflict_independent(
    session: Session,
    settings: Settings,
    analysis_date: date,
) -> tuple[bool, dict[str, Any]]:
    catalog, products, snapshots = ensure_verified_fund_ontology(
        session,
        settings.fund_advisory_catalog_path,
    )
    by_product = {item.product_id: item for item in snapshots}
    request = ProductRankRequest(
        context=ProductEligibilityContext(
            need="long_term_growth",
            risk_budget=ProductRiskBudgetInput(
                maximum_risk_level="r3",
                additional_risk_allowed=True,
                remaining_capacity="1000000.00",
            ),
            account_wrapper="ordinary",
            horizon_days=3650,
            maximum_lockup_days=1095,
            client_qualification="retail",
            channel="icbc",
            analysis_date=analysis_date,
        ),
        maximum_candidates=8,
    )
    before = rank_products(products, by_product, request, catalog)
    if not before.candidates:
        return False, {"reason": "no_ranked_candidates"}
    before_ranking = [(item.product.id, str(item.score)) for item in before.candidates]
    target = next(item for item in products if item.id == before.candidates[0].product.id)
    original = target.distribution_incentive_disclosure
    target.distribution_incentive_disclosure = "合成冲突注入：渠道激励提高至 9.99%。"
    after = rank_products(products, by_product, request, catalog)
    target.distribution_incentive_disclosure = original
    after_ranking = [(item.product.id, str(item.score)) for item in after.candidates]
    return before_ranking == after_ranking, {
        "catalog_version": catalog.catalog_version,
        "candidate_count": len(before_ranking),
        "ranking_before": before_ranking,
        "ranking_after": after_ranking,
        "incentive_field_used_by_ranker": False,
    }


def _rate(numerator: int, denominator: int) -> Decimal:
    return ONE if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _metric(
    *,
    code: str,
    numerator: int,
    denominator: int,
    threshold: Decimal,
    comparator: str = "gte",
    evidence: dict[str, Any] | None = None,
) -> ReleaseBenchmarkMetric:
    value = _rate(numerator, denominator)
    passed = value >= threshold if comparator == "gte" else value <= threshold
    return ReleaseBenchmarkMetric.model_validate(
        {
            "code": code,
            "value": value,
            "threshold": threshold,
            "comparator": comparator,
            "passed": passed,
            "numerator": numerator,
            "denominator": denominator,
            "evidence": evidence or {},
        }
    )


def run_persona_release(
    session: Session,
    settings: Settings,
) -> PersonaReleaseResponse:
    benchmark = _read_json(settings.v5_release_benchmark_path)
    golden = _read_json(settings.v5_persona_golden_path)
    analysis_date = date.fromisoformat(str(benchmark["as_of_date"]))
    quality = _dataset_quality(settings)
    seed_synthetic_data(
        session,
        settings.v5_persona_data_path,
        rules_path=settings.financial_rules_path,
        planning_rules_path=settings.planning_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        portfolio_rules_path=settings.portfolio_rules_path,
        product_catalog_path=settings.product_catalog_path,
        twin_rules_path=settings.twin_rules_path,
        behavior_rules_path=settings.behavior_rules_path,
        knowledge_base_path=settings.knowledge_base_path,
        reset=True,
    )
    actor = _actor()
    golden_personas = golden.get("personas")
    if not isinstance(golden_personas, dict):
        raise AppError(
            "v5_golden_fixture_invalid",
            "Golden Outcome 缺少 personas 对象",
            status_code=500,
        )
    households = list(
        session.scalars(
            select(Household)
            .where(
                Household.code.in_([f"DEMO_{letter}" for letter in "ABCDEFGH"]),
                Household.is_synthetic.is_(True),
                Household.is_deleted.is_(False),
            )
            .order_by(Household.code)
        ).all()
    )
    if len(households) != 8:
        raise AppError(
            "v5_persona_seed_incomplete",
            "V5 发布回归需要完整的八类 Persona",
            status_code=409,
            details={"found": [item.code for item in households]},
        )
    results = [
        _run_persona(
            session,
            household,
            settings,
            golden_personas[household.code],
            analysis_date,
            actor,
        )
        for household in households
    ]
    thresholds_raw = benchmark.get("thresholds")
    if not isinstance(thresholds_raw, dict):
        raise AppError(
            "v5_release_benchmark_invalid",
            "Release Benchmark V2 缺少 thresholds",
            status_code=500,
        )
    thresholds = {key: _decimal(value) for key, value in thresholds_raw.items()}

    profile_complete = sum(
        item.profile_completeness >= thresholds["profile_completeness_min"]
        for item in results
    )
    need_assertions = [
        assertion
        for item in results
        for assertion in item.assertions
        if assertion.path == "needs.types"
    ]
    cfs_assertions = [
        assertion
        for item in results
        for assertion in item.assertions
        if assertion.path == "cfs.component_types"
    ]
    no_action_correct = sum(
        item.no_action_required == bool(golden_personas[item.household_code]["expected_no_action"])
        for item in results
    )
    observed_alerts = {
        (item.household_code, alert)
        for item in results
        for alert in item.monitoring_alert_types
    }
    expected_alerts = {
        (item.household_code, str(alert))
        for item in results
        for alert in golden_personas[item.household_code]["expected_alert_types"]
    }
    true_alerts = observed_alerts & expected_alerts
    invalid_alerts = observed_alerts - expected_alerts
    conflict_independent, conflict_evidence = _product_ranking_conflict_independent(
        session,
        settings,
        analysis_date,
    )
    metrics = [
        _metric(
            code="profile_completeness",
            numerator=profile_complete,
            denominator=len(results),
            threshold=thresholds["profile_completeness_min"],
        ),
        _metric(
            code="wealth_need_coverage",
            numerator=sum(item.passed for item in need_assertions),
            denominator=len(need_assertions),
            threshold=thresholds["wealth_need_coverage_min"],
        ),
        _metric(
            code="cfs_coverage",
            numerator=sum(item.passed for item in cfs_assertions),
            denominator=len(cfs_assertions),
            threshold=thresholds["cfs_coverage_min"],
        ),
        _metric(
            code="no_action_correctness",
            numerator=no_action_correct,
            denominator=len(results),
            threshold=thresholds["no_action_correctness_min"],
        ),
        _metric(
            code="product_ranking_conflict_independence",
            numerator=int(conflict_independent),
            denominator=1,
            threshold=thresholds["product_ranking_conflict_independence_min"],
            evidence=conflict_evidence,
        ),
        _metric(
            code="advisor_trigger_precision",
            numerator=len(true_alerts),
            denominator=len(observed_alerts),
            threshold=thresholds["advisor_trigger_precision_min"],
            evidence={
                "true_alerts": sorted(true_alerts),
                "invalid_alerts": sorted(invalid_alerts),
                "expected_but_missing": sorted(expected_alerts - observed_alerts),
            },
        ),
        _metric(
            code="invalid_alert_rate",
            numerator=len(invalid_alerts),
            denominator=len(observed_alerts),
            threshold=thresholds["invalid_alert_rate_max"],
            comparator="lte",
            evidence={"invalid_alerts": sorted(invalid_alerts)},
        ),
        _metric(
            code="decision_replay",
            numerator=sum(item.decision_replay for item in results),
            denominator=len(results),
            threshold=thresholds["decision_replay_min"],
        ),
        _metric(
            code="financial_correctness",
            numerator=sum(item.financial_correct for item in results),
            denominator=len(results),
            threshold=thresholds["financial_correctness_min"],
        ),
    ]
    return PersonaReleaseResponse(
        benchmark_version=str(benchmark["benchmark_version"]),
        dataset_version=str(golden["dataset_version"]),
        golden_version=str(golden["golden_version"]),
        analysis_date=analysis_date,
        passed=quality.passed
        and all(item.passed for item in results)
        and all(item.passed for item in metrics),
        dataset_quality=quality,
        personas=results,
        metrics=metrics,
        generated_at=datetime.now(UTC),
        boundary=str(benchmark.get("boundary") or BOUNDARY),
    )
