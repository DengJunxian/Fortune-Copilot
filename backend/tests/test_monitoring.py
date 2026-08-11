from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.auth import ActorContext
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.enums import (
    AccountWrapper,
    AssetCategory,
    AssetPurposeDimension,
    CashFlowFrequency,
    ComplexityLevel,
    EnterpriseCashflowStability,
    EnterpriseCashflowType,
    EnterpriseInstrumentType,
    EnterpriseListedStatus,
    EnterpriseStage,
    EnterpriseType,
    EnterpriseValuationMethod,
    EvidenceConfidence,
    FinancialEntityType,
    LifecycleStage,
    LiquidityLevel,
    MonitoringPolicyType,
    ProductRiskLevel,
    RiskLevel,
    RiskLimitEffect,
)
from app.main import app
from app.models.assessment import RiskAssessment
from app.models.family import Household
from app.models.family_enterprise import (
    EnterpriseCashflow,
    EnterpriseOwnership,
    EnterpriseProfile,
    EnterpriseValuation,
)
from app.models.finance import Asset
from app.models.governance import ActionItem, CustomerConfirmation, Product
from app.models.monitoring import AdvisorTrigger, BehaviorObservation, MonitoringAlert
from app.models.wealth_graph import FinancialAccount, FinancialEntity, Position
from app.schemas.monitoring import (
    BehaviorObservationInput,
    MonitoringEvaluateRequest,
)
from app.services.monitoring.engine import evaluate_monitoring, list_behavior_interventions
from app.services.next_best_action.engine import get_next_best_actions

ANALYSIS_DATE = date(2026, 8, 10)
MONITORING_RULES_PATH = "../data/rules/monitoring_v1.json"
FAMILY_ENTERPRISE_RULES_PATH = "../data/rules/family_enterprise_v1.json"
SPECIALIZED_RULES_PATH = "../data/rules/specialized_cfs_v1.json"


def _actor(role: str = "admin") -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"monitoring-{role}",
        role=role,  # type: ignore[arg-type]
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


def _household(session: Any, code: str) -> Household:
    household = Household(
        code=code,
        name=f"{code}家庭",
        lifecycle_stage=LifecycleStage.EARLY_CAREER,
        region="上海",
        is_synthetic=True,
        planning_preferences={},
        valuation_date=ANALYSIS_DATE,
        data_source="monitoring-acceptance",
        is_user_confirmed=True,
    )
    session.add(household)
    session.commit()
    return household


def _evaluate(
    session: Any,
    household_id: str,
    request: MonitoringEvaluateRequest | None = None,
) -> Any:
    return evaluate_monitoring(
        session,
        household_id,
        _actor(),
        request
        or MonitoringEvaluateRequest(
            analysis_date=ANALYSIS_DATE,
            is_user_confirmed=True,
        ),
        MONITORING_RULES_PATH,
        FAMILY_ENTERPRISE_RULES_PATH,
        SPECIALIZED_RULES_PATH,
    )


def test_no_material_change_returns_formal_no_action_required() -> None:
    with SessionLocal() as session:
        household = _household(session, "E10-NO-ACTION")
        evaluation = _evaluate(session, household.id)
        assert evaluation.evaluated_policy_count == 11
        assert evaluation.triggered_policy_count == 0

        result = get_next_best_actions(session, household.id, ANALYSIS_DATE)
        assert result.outcome == "NO_ACTION_REQUIRED"
        assert [item.action_code for item in result.actions] == ["NO_ACTION_REQUIRED"]
        assert result.actions[0].do_not_sell_flag is True
        assert result.actions[0].evidence["next_best_sale"] is False


def test_market_shock_behavior_signal_only_reduces_risk_and_never_chases_hot_products() -> None:
    with SessionLocal() as session:
        household = _household(session, "E10-BEHAVIOR")
        session.add(
            RiskAssessment(
                household_id=household.id,
                capacity_score=Decimal("0.80"),
                willingness_score=Decimal("0.80"),
                knowledge_score=Decimal("0.80"),
                behavior_score=Decimal("0.80"),
                final_risk_limit=RiskLevel.HIGH,
                explanation="监控验收基准",
                valuation_date=ANALYSIS_DATE,
                data_source="monitoring-acceptance",
                is_user_confirmed=True,
            )
        )
        session.commit()
        confirmation = CustomerConfirmation(
            household_id=household.id,
            confirmation_type="monitoring_behavior_observation",
            confirmed_at=datetime.now(UTC),
            confirmation_version="e10-acceptance-v1",
            evidence={"scope": "market-shock-observation"},
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        session.add(confirmation)
        session.commit()
        result = _evaluate(
            session,
            household.id,
            MonitoringEvaluateRequest(
                analysis_date=ANALYSIS_DATE,
                market_shock=True,
                hard_facts_changed=False,
                customer_confirmation_id=confirmation.id,
                observations=[
                    BehaviorObservationInput(
                        observation_type="performance_chasing",
                        signal_strength=Decimal("0.90"),
                        occurrence_count=3,
                        source_reference="market-rise-acceptance",
                    )
                ],
                is_user_confirmed=True,
            ),
        )
        assert result.intervention_ids
        observation = session.scalar(
            select(BehaviorObservation).where(
                BehaviorObservation.household_id == household.id
            )
        )
        assert observation is not None
        assert observation.risk_limit_effect == RiskLimitEffect.REDUCE
        assert observation.evidence_snapshot["risk_limit_can_increase"] is False
        assert observation.evidence_snapshot["customer_confirmation_id"] == confirmation.id

        intervention = list_behavior_interventions(session, household.id).interventions[0]
        assert intervention.evidence["customer_confirmation_id"] == confirmation.id
        combined = f"{intervention.personalized_message} {intervention.action_instruction}"
        assert all(term not in combined for term in ("热销基金", "追涨加仓", "立即买入"))
        assert all(term in combined for term in ("冷静期", "压力情景", "不新增产品"))

        actions = get_next_best_actions(session, household.id, ANALYSIS_DATE)
        assert actions.outcome == "ACTIONS_AVAILABLE"
        assert all(item.do_not_sell_flag for item in actions.actions)
        assert all(item.evidence["next_best_sale"] is False for item in actions.actions)


def test_enterprise_dependency_creates_family_enterprise_review_action() -> None:
    with SessionLocal() as session:
        household = _household(session, "E10-ENTERPRISE")
        owner = FinancialEntity(
            household_id=household.id,
            entity_type=FinancialEntityType.PERSON,
            display_name="企业主",
            jurisdiction="CN",
            external_reference="e10-enterprise-owner",
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        session.add(owner)
        session.flush()
        session.add(
            Asset(
                household_id=household.id,
                name="家庭现金",
                category=AssetCategory.DEMAND_DEPOSIT,
                acquisition_cost=Decimal("1000000"),
                market_value=Decimal("1000000"),
                liquidity_days=0,
                liquidity_level=LiquidityLevel.IMMEDIATE,
                risk_level=RiskLevel.LOW,
                purpose="家庭责任",
                pledged=False,
                ownership="家庭共有",
                valuation_date=ANALYSIS_DATE,
                data_source="monitoring-acceptance",
                is_user_confirmed=True,
            )
        )
        enterprise = EnterpriseProfile(
            household_id=household.id,
            name="家族制造企业",
            industry="制造业",
            stage=EnterpriseStage.MATURE,
            jurisdiction="CN",
            listed_status=EnterpriseListedStatus.UNLISTED,
            enterprise_type=EnterpriseType.OPERATING_COMPANY,
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        session.add(enterprise)
        session.flush()
        session.add_all(
            [
                EnterpriseOwnership(
                    household_id=household.id,
                    enterprise_id=enterprise.id,
                    owner_entity_id=owner.id,
                    ownership_ratio=Decimal("1"),
                    voting_ratio=Decimal("1"),
                    instrument_type=EnterpriseInstrumentType.COMMON_EQUITY,
                    valuation_date=ANALYSIS_DATE,
                    data_source="monitoring-acceptance",
                    is_user_confirmed=True,
                ),
                EnterpriseValuation(
                    household_id=household.id,
                    enterprise_id=enterprise.id,
                    equity_value=Decimal("9000000"),
                    valuation_method=EnterpriseValuationMethod.USER_ESTIMATE,
                    confidence=EvidenceConfidence.MEDIUM,
                    source_kind="confirmed_statement",
                    evidence={"document": "e10-enterprise"},
                    valuation_date=ANALYSIS_DATE,
                    data_source="monitoring-acceptance",
                    is_user_confirmed=True,
                ),
                EnterpriseCashflow(
                    household_id=household.id,
                    enterprise_id=enterprise.id,
                    member_id=None,
                    cashflow_type=EnterpriseCashflowType.SALARY,
                    amount=Decimal("1000000"),
                    frequency=CashFlowFrequency.ANNUAL,
                    stability=EnterpriseCashflowStability.LOW,
                    valuation_date=ANALYSIS_DATE,
                    data_source="monitoring-acceptance",
                    is_user_confirmed=True,
                ),
                RiskAssessment(
                    household_id=household.id,
                    capacity_score=Decimal("0.60"),
                    willingness_score=Decimal("0.60"),
                    knowledge_score=Decimal("0.60"),
                    behavior_score=Decimal("0.60"),
                    final_risk_limit=RiskLevel.MEDIUM,
                    explanation="监控验收基准",
                    valuation_date=ANALYSIS_DATE,
                    data_source="monitoring-acceptance",
                    is_user_confirmed=True,
                ),
            ]
        )
        session.commit()

        result = _evaluate(session, household.id)
        alert = next(
            item
            for item in result.alerts
            if item.policy_type == MonitoringPolicyType.ENTERPRISE_DEPENDENCY
        )
        assert "家庭—企业联合复核" in alert.recommended_action
        assert alert.required_specialist == "enterprise_advisor"
        action = session.scalar(
            select(ActionItem).where(
                ActionItem.action_type == "family_enterprise_review"
            )
        )
        assert action is not None
        assert action.do_not_sell_flag is True


def test_product_maturity_triggers_review_without_replacement() -> None:
    with SessionLocal() as session:
        household = _household(session, "E10-MATURITY")
        owner = FinancialEntity(
            household_id=household.id,
            entity_type=FinancialEntityType.PERSON,
            display_name="持有人",
            jurisdiction="CN",
            external_reference="e10-product-owner",
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        session.add(owner)
        session.flush()
        account = FinancialAccount(
            household_id=household.id,
            owner_entity_id=owner.id,
            provider_name="演示银行",
            account_type="wealth_management",
            account_wrapper=AccountWrapper.ORDINARY,
            jurisdiction="CN",
            external_reference="e10-product-account",
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        product = Product(
            code="E10-MATURITY-PRODUCT",
            name="到期复核产品",
            product_type="fixed_term",
            risk_level=ProductRiskLevel.R2,
            liquidity_level=LiquidityLevel.WITHIN_30_DAYS,
            minimum_investment=Decimal("10000"),
            withdrawable_date=ANALYSIS_DATE + timedelta(days=10),
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        session.add_all([account, product])
        session.flush()
        session.add(
            Position(
                household_id=household.id,
                account_id=account.id,
                owner_entity_id=owner.id,
                product_id=product.id,
                instrument_type=AssetCategory.BANK_WEALTH_MANAGEMENT,
                instrument_code=product.code,
                name=product.name,
                quantity=Decimal("1"),
                acquisition_cost=Decimal("100000"),
                market_value=Decimal("100000"),
                purpose_dimension=AssetPurposeDimension.STABLE,
                risk_level=RiskLevel.MEDIUM_LOW,
                liquidity_days=10,
                complexity_level=ComplexityLevel.STANDARD,
                principal_loss_possible=True,
                legally_principal_guaranteed=False,
                lock_up=True,
                withdrawable_date=ANALYSIS_DATE + timedelta(days=10),
                source_kind="confirmed_position",
                evidence_json={},
                valuation_date=ANALYSIS_DATE,
                data_source="monitoring-acceptance",
                is_user_confirmed=True,
            )
        )
        session.commit()

        result = _evaluate(session, household.id)
        alert = next(
            item
            for item in result.alerts
            if item.policy_type == MonitoringPolicyType.PRODUCT_MATURITY
        )
        assert "不自动推荐替代产品" in alert.recommended_action
        assert alert.evidence_snapshot["replacement_product_generated"] is False
        action = get_next_best_actions(session, household.id, ANALYSIS_DATE).actions[0]
        assert action.do_not_sell_flag is True
        assert action.evidence["next_best_sale"] is False


async def _api_request(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
    role: str = "advisor",
    confirm: bool = False,
) -> Response:
    headers = {"X-Actor-ID": "monitoring-api", "X-Actor-Role": role}
    if confirm:
        headers["X-Confirm-Action"] = "evaluate_monitoring"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=payload, headers=headers)


def _call(method: str, path: str, **kwargs: Any) -> Response:
    return asyncio.run(_api_request(method, path, **kwargs))


def test_monitoring_api_feature_gate_confirmation_rbac_and_action_center(monkeypatch: Any) -> None:
    with SessionLocal() as session:
        household = _household(session, "E10-API")
        household_id = household.id
    base = f"/api/v1/households/{household_id}"
    payload = {"analysis_date": ANALYSIS_DATE.isoformat(), "is_user_confirmed": True}

    monkeypatch.setenv("ENABLE_V5_MONITORING", "false")
    get_settings.cache_clear()
    assert _call("GET", f"{base}/monitoring/alerts").status_code == 404

    monkeypatch.setenv("ENABLE_V5_MONITORING", "true")
    monkeypatch.setenv("MONITORING_RULES_PATH", MONITORING_RULES_PATH)
    get_settings.cache_clear()
    assert _call("POST", f"{base}/monitoring/evaluate", payload=payload).status_code == 409
    assert (
        _call(
            "POST",
            f"{base}/monitoring/evaluate",
            payload=payload,
            role="client",
            confirm=True,
        ).status_code
        == 403
    )
    evaluated = _call(
        "POST",
        f"{base}/monitoring/evaluate",
        payload=payload,
        confirm=True,
    )
    assert evaluated.status_code == 200, evaluated.text
    assert evaluated.json()["evaluated_policy_count"] == 11
    for endpoint in ("monitoring/alerts", "behavior-interventions", "next-best-actions"):
        response = _call("GET", f"{base}/{endpoint}")
        assert response.status_code == 200, response.text
    assert _call("GET", "/api/v1/advisor/action-center", role="client").status_code == 403
    center = _call("GET", "/api/v1/advisor/action-center", role="advisor")
    assert center.status_code == 200, center.text
    assert center.json()["open_count"] == 0
    get_settings.cache_clear()


def test_alerts_reuse_advisor_trigger_and_action_item_on_replay() -> None:
    with SessionLocal() as session:
        household = _household(session, "E10-IDEMPOTENT")
        asset = Asset(
            household_id=household.id,
            name="集中资产",
            category=AssetCategory.DEMAND_DEPOSIT,
            acquisition_cost=Decimal("100000"),
            market_value=Decimal("100000"),
            liquidity_days=0,
            liquidity_level=LiquidityLevel.IMMEDIATE,
            risk_level=RiskLevel.LOW,
            purpose="家庭现金",
            pledged=False,
            ownership="个人",
            valuation_date=ANALYSIS_DATE,
            data_source="monitoring-acceptance",
            is_user_confirmed=True,
        )
        session.add(asset)
        session.commit()
        first = _evaluate(session, household.id)
        second = _evaluate(session, household.id)
        assert first.triggered_policy_count == second.triggered_policy_count == 1
        assert len(list(session.scalars(select(MonitoringAlert)).all())) == 1
        assert len(list(session.scalars(select(AdvisorTrigger)).all())) == 1
        assert len(list(session.scalars(select(ActionItem)).all())) == 1

        asset.market_value = Decimal("0")
        asset.version += 1
        session.commit()
        cleared = _evaluate(session, household.id)
        assert cleared.triggered_policy_count == 0
        assert cleared.resolved_alert_count == 1
        trigger = session.scalar(select(AdvisorTrigger))
        action = session.scalar(select(ActionItem))
        assert trigger is not None and trigger.status.value == "completed"
        assert action is not None and action.status == "completed"
        assert action.status_reason == "monitoring_condition_cleared"
        assert get_next_best_actions(session, household.id, ANALYSIS_DATE).outcome == (
            "NO_ACTION_REQUIRED"
        )
