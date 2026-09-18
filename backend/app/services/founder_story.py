from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import FinancialEntityType, SimulationStatus
from app.models.family import Household
from app.models.family_enterprise import (
    EnterpriseOwnership,
    EnterpriseProfile,
    EnterpriseValuation,
)
from app.models.wealth_graph import FinancialEntity
from app.schemas.cfs import CFSComposeRequest
from app.schemas.family_enterprise import EnterpriseExposureCreate
from app.schemas.monitoring import MonitoringEvaluateRequest
from app.schemas.persona_release import FounderStoryResponse, FounderStoryStage
from app.schemas.review_workflow import (
    CreatePlanWorkflowRequest,
    PlanWorkflowResponse,
    WorkflowActionRequest,
)
from app.schemas.twin import TwinRunRequest
from app.services.cfs_composer.engine import compose_cfs_solution
from app.services.client_profile.engine import get_client_profile
from app.services.family_enterprise.events import process_enterprise_exposures
from app.services.financial_twin.engine import materialize_current_twin
from app.services.monitoring.engine import evaluate_monitoring
from app.services.product_ontology.composition import compose_cfs_product_candidates
from app.services.review_workflow import create_plan_workflow, transition_plan_workflow
from app.services.seed import seed_synthetic_data
from app.services.twin.engine import advance_twin_run, start_twin_run
from app.services.wealth_needs.engine import get_wealth_needs

STORY_VERSION = "founder-funding-e2e-v5.0.0"
BOUNDARY = (
    "Founder E2E 使用合成家庭、合成企业与本地确定性工具；融资估值、产品映射和"
    "客户确认均不代表真实银行业务、交易执行或法律意见。"
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


def _actor(role: str) -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id=f"founder-story-{role}",
        role=role,
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        auth_source="demo_headers",
    )


def _compose_kwargs(settings: Settings, analysis_date: date) -> ComposeKwargs:
    return {
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


def _stage(code: str, label: str, passed: bool, **evidence: object) -> FounderStoryStage:
    return FounderStoryStage(
        code=code,
        label=label,
        passed=passed,
        evidence=evidence,
    )


def _transition(
    session: Session,
    workflow_id: str,
    version: int,
    action: str,
    role: str,
    **fields: object,
) -> PlanWorkflowResponse:
    return transition_plan_workflow(
        session,
        workflow_id,
        WorkflowActionRequest.model_validate(
            {
                "action": action,
                "expected_version": version,
                "reason": f"Founder E2E：{action}",
                **fields,
            }
        ),
        _actor(role),
        f"founder-e2e-{action}-{version}",
    )


def run_founder_story(session: Session, settings: Settings) -> FounderStoryResponse:
    analysis_date = date(2026, 8, 10)
    funding_date = date(2026, 8, 11)
    admin = _actor("admin")
    result = seed_synthetic_data(
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
    household = session.scalar(
        select(Household).where(
            Household.code == "DEMO_D",
            Household.is_synthetic.is_(True),
            Household.is_deleted.is_(False),
        )
    )
    if household is None:
        raise AppError(
            "founder_persona_missing",
            "Founder E2E 缺少 DEMO_D",
            status_code=409,
        )
    stages = [
        _stage(
            "load_founder",
            "Load Founder Demo",
            "DEMO_D" in result.household_codes,
            dataset_version=result.dataset_version,
            household_count=result.loaded,
        )
    ]

    initial_twin = materialize_current_twin(
        session,
        household.id,
        admin,
        financial_rules_path=settings.financial_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        client_profile_rules_path=settings.client_profile_rules_path,
        liability_rules_path=settings.liability_rules_path,
        family_enterprise_rules_path=settings.family_enterprise_rules_path,
        analysis_date=analysis_date,
    )
    profile_before = get_client_profile(session, household.id)
    needs_before = get_wealth_needs(session, household.id)
    cfs_before = compose_cfs_solution(
        session,
        household.id,
        CFSComposeRequest(is_user_confirmed=True),
        admin,
        **_compose_kwargs(settings, analysis_date),
    )
    stages.append(
        _stage(
            "financial_twin",
            "See Financial Twin",
            bool(initial_twin.snapshot_hash and initial_twin.input_hash),
            snapshot_id=initial_twin.id,
            snapshot_hash=initial_twin.snapshot_hash,
        )
    )

    enterprise = session.scalar(
        select(EnterpriseProfile).where(
            EnterpriseProfile.household_id == household.id,
            EnterpriseProfile.is_deleted.is_(False),
        )
    )
    if enterprise is None:
        raise AppError(
            "founder_enterprise_missing",
            "Founder Persona 缺少企业档案",
            status_code=409,
        )
    ownership = session.scalar(
        select(EnterpriseOwnership).where(
            EnterpriseOwnership.enterprise_id == enterprise.id,
            EnterpriseOwnership.is_deleted.is_(False),
        )
    )
    latest_valuation = session.scalar(
        select(EnterpriseValuation)
        .where(
            EnterpriseValuation.enterprise_id == enterprise.id,
            EnterpriseValuation.is_deleted.is_(False),
        )
        .order_by(EnterpriseValuation.valuation_date.desc())
    )
    if ownership is None or latest_valuation is None:
        raise AppError(
            "founder_exposure_missing",
            "Founder Persona 缺少权益或估值暴露",
            status_code=409,
        )
    owner_entity = session.scalar(
        select(FinancialEntity).where(
            FinancialEntity.id == ownership.owner_entity_id,
            FinancialEntity.household_id == household.id,
            FinancialEntity.entity_type.in_(
                {FinancialEntityType.HOUSEHOLD, FinancialEntityType.PERSON}
            ),
            FinancialEntity.is_deleted.is_(False),
        )
    )
    if owner_entity is None:
        raise AppError(
            "founder_owner_missing",
            "Founder 企业权益缺少金融图所有者",
            status_code=409,
        )
    ownership_before = str(ownership.ownership_ratio)
    valuation_before = str(latest_valuation.equity_value)
    funding_payload = EnterpriseExposureCreate.model_validate(
        {
            "enterprise_id": enterprise.id,
            "ownerships": [
                {
                    "owner_entity_id": owner_entity.id,
                    "ownership_ratio": "0.620000",
                    "voting_ratio": "0.680000",
                    "instrument_type": ownership.instrument_type.value,
                    "vesting_date": (
                        ownership.vesting_date.isoformat() if ownership.vesting_date else None
                    ),
                    "lockup_end_date": "2029-12-31",
                }
            ],
            "valuations": [
                {
                    "valuation_date": funding_date.isoformat(),
                    "equity_value": "50000000.00",
                    "valuation_method": "transaction",
                    "confidence": "high",
                    "source_kind": "synthetic_funding_term_sheet",
                    "evidence": {
                        "round": "Series C",
                        "synthetic": True,
                        "pre_money_value": str(latest_valuation.equity_value),
                    },
                    "currency": "CNY",
                }
            ],
            "liquidity_events": [
                {
                    "event_type": "funding",
                    "expected_date": funding_date.isoformat(),
                    "estimated_value": "20000000.00",
                    "probability": "1.000000",
                    "lockup": True,
                    "currency": "CNY",
                    "status": "completed",
                }
            ],
            "source_reference": "founder-e2e-series-c-2026-08-11",
            "is_user_confirmed": True,
        }
    )
    funding = process_enterprise_exposures(
        session,
        household.id,
        funding_payload,
        admin,
        financial_rules_path=settings.financial_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        client_profile_rules_path=settings.client_profile_rules_path,
        liability_rules_path=settings.liability_rules_path,
        family_enterprise_rules_path=settings.family_enterprise_rules_path,
        analysis_date=funding_date,
    )
    stages.append(
        _stage(
            "funding_event",
            "Enterprise Funding Event",
            bool(funding.financial_event_ids),
            financial_event_ids=funding.financial_event_ids,
            ownership_before=ownership_before,
            ownership_after="0.620000",
            valuation_before=valuation_before,
            valuation_after="50000000.00",
        )
    )
    if funding.snapshot_id is None:
        raise AppError(
            "founder_funding_snapshot_missing",
            "融资事件未生成新快照",
            status_code=500,
        )
    stages.append(
        _stage(
            "funding_snapshot",
            "New Snapshot",
            funding.snapshot_id != initial_twin.id,
            initial_snapshot_id=initial_twin.id,
            funding_snapshot_id=funding.snapshot_id,
        )
    )

    profile_after = get_client_profile(session, household.id)
    needs_after = get_wealth_needs(session, household.id)
    stages.append(
        _stage(
            "profile_change",
            "Profile Changes",
            profile_before.profile.profile_hash != profile_after.profile.profile_hash,
            before_hash=profile_before.profile.profile_hash,
            after_hash=profile_after.profile.profile_hash,
            enterprise_dependency=profile_after.profile.enterprise_dependency_level.value,
        )
    )
    stages.append(
        _stage(
            "need_change",
            "Need Changes",
            needs_before.meta.profile_hash != needs_after.meta.profile_hash,
            before_profile_hash=needs_before.meta.profile_hash,
            after_profile_hash=needs_after.meta.profile_hash,
            need_types=sorted({item.need_type.value for item in needs_after.needs}),
        )
    )

    cfs_after = compose_cfs_solution(
        session,
        household.id,
        CFSComposeRequest(is_user_confirmed=True, source_snapshot_id=funding.snapshot_id),
        admin,
        **_compose_kwargs(settings, funding_date),
    )
    risk_before = cfs_before.risk_budget
    risk_after = cfs_after.risk_budget
    risk_changed = (
        risk_before.existing_economic_exposure != risk_after.existing_economic_exposure
        or risk_before.remaining_risk_capacity != risk_after.remaining_risk_capacity
        or risk_before.decision != risk_after.decision
    )
    stages.append(
        _stage(
            "risk_budget_change",
            "Risk Budget Changes",
            risk_changed,
            exposure_before=str(risk_before.existing_economic_exposure),
            exposure_after=str(risk_after.existing_economic_exposure),
            decision_before=risk_before.decision,
            decision_after=risk_after.decision,
            additional_risk_allowed=risk_after.additional_risk_allowed,
        )
    )

    monitoring = evaluate_monitoring(
        session,
        household.id,
        admin,
        MonitoringEvaluateRequest(
            analysis_date=funding_date,
            hard_facts_changed=True,
            is_user_confirmed=True,
        ),
        settings.monitoring_rules_path,
        settings.family_enterprise_rules_path,
        settings.specialized_cfs_rules_path,
    )
    alert_types = sorted({item.policy_type.value for item in monitoring.alerts})
    stages.append(
        _stage(
            "advisor_trigger",
            "Advisor Trigger",
            "enterprise_dependency" in alert_types,
            alert_types=alert_types,
            triggered_policy_count=monitoring.triggered_policy_count,
        )
    )

    twin_run = start_twin_run(
        session,
        household.id,
        TwinRunRequest(
            analysis_date=funding_date,
            household_snapshot_id=funding.snapshot_id,
            path_count=100,
            horizon_years=20,
            scenario_codes=["unemployment_equity_down_30"],
        ),
        admin,
        settings.financial_rules_path,
        settings.planning_rules_path,
        settings.twin_rules_path,
    )
    for _ in range(8):
        if twin_run.status == SimulationStatus.COMPLETED:
            break
        twin_run = advance_twin_run(
            session,
            household.id,
            twin_run.run_id,
            admin,
            settings.twin_rules_path,
        )
    stages.append(
        _stage(
            "scenario_lab",
            "Scenario Lab",
            twin_run.status == SimulationStatus.COMPLETED,
            run_id=twin_run.run_id,
            status=twin_run.status.value,
            scenario_codes=twin_run.scenario_codes,
            household_snapshot_id=twin_run.household_snapshot_id,
        )
    )
    stages.append(
        _stage(
            "cfs_recalculated",
            "CFS Recalculated",
            cfs_after.solution.id != cfs_before.solution.id
            and cfs_after.solution.solution_version > cfs_before.solution.solution_version,
            before_solution_id=cfs_before.solution.id,
            after_solution_id=cfs_after.solution.id,
            component_types=sorted(
                {item.component_type.value for item in cfs_after.components}
            ),
        )
    )

    product_mapping = compose_cfs_product_candidates(
        session,
        household.id,
        cfs_after.solution.id,
        settings.fund_advisory_catalog_path,
        analysis_date=funding_date,
    )
    specialist_types = sorted({item.specialist_type.value for item in cfs_after.referrals})
    stages.append(
        _stage(
            "product_specialist_mapping",
            "Product / Specialist Mapping",
            bool(product_mapping.groups) and bool(specialist_types),
            product_group_count=len(product_mapping.groups),
            product_results=sorted({item.result for item in product_mapping.groups}),
            specialist_types=specialist_types,
            executable_recommendations_allowed=False,
        )
    )

    workflow = create_plan_workflow(
        session,
        household.id,
        CreatePlanWorkflowRequest(reason="Founder 融资事件后的顾问复核"),
        _actor("advisor"),
        "founder-e2e-create",
    )
    workflow = _transition(
        session,
        workflow.workflow_id,
        workflow.current.version_number,
        "calculate",
        "advisor",
    )
    workflow = _transition(
        session,
        workflow.workflow_id,
        workflow.current.version_number,
        "suitability_check",
        "advisor",
    )
    advisor_review = _transition(
        session,
        workflow.workflow_id,
        workflow.current.version_number,
        "advisor_review",
        "advisor",
        selected_candidate="balanced",
        manual_high_risk_confirmed=True,
        advisor_note="已复核融资稀释、家企隔离、担保、跨境责任与风险预算。",
    )
    stages.append(
        _stage(
            "advisor_review",
            "Advisor Review",
            advisor_review.current.state.value == "advisor_reviewed",
            workflow_id=advisor_review.workflow_id,
            version=advisor_review.current.version_number,
            state=advisor_review.current.state.value,
        )
    )
    workflow = _transition(
        session,
        workflow.workflow_id,
        advisor_review.current.version_number,
        "submit_compliance",
        "advisor",
    )
    workflow = _transition(
        session,
        workflow.workflow_id,
        workflow.current.version_number,
        "compliance_approve",
        "compliance",
        human_review_completed=True,
        compliance_note="融资后方案、三道适当性闸门与证据链已人工复核。",
    )
    customer_confirmed = _transition(
        session,
        workflow.workflow_id,
        workflow.current.version_number,
        "customer_confirm",
        "client",
        customer_name="沈先生",
        acknowledgements=["risk_read", "mock_understood", "not_guaranteed"],
    )
    stages.append(
        _stage(
            "client_confirmation",
            "Client Confirmation",
            customer_confirmed.current.state.value == "customer_confirmed",
            workflow_id=customer_confirmed.workflow_id,
            version=customer_confirmed.current.version_number,
            signature_status=customer_confirmed.current.customer_confirmation.get(
                "signature_status"
            ),
        )
    )
    confirmed_snapshot = materialize_current_twin(
        session,
        household.id,
        _actor("client"),
        financial_rules_path=settings.financial_rules_path,
        methodology_rules_path=settings.methodology_rules_path,
        public_data_snapshot_path=settings.public_data_snapshot_path,
        client_profile_rules_path=settings.client_profile_rules_path,
        liability_rules_path=settings.liability_rules_path,
        family_enterprise_rules_path=settings.family_enterprise_rules_path,
        analysis_date=funding_date,
        force_new=True,
    )
    stages.append(
        _stage(
            "confirmed_snapshot",
            "New Confirmed Snapshot",
            confirmed_snapshot.id != funding.snapshot_id,
            funding_snapshot_id=funding.snapshot_id,
            confirmed_snapshot_id=confirmed_snapshot.id,
            source_confirmation_state=customer_confirmed.current.state.value,
        )
    )
    return FounderStoryResponse(
        story_version=STORY_VERSION,
        household_id=household.id,
        passed=all(item.passed for item in stages),
        stages=stages,
        initial_snapshot_id=initial_twin.id,
        funding_snapshot_id=funding.snapshot_id,
        confirmed_snapshot_id=confirmed_snapshot.id,
        workflow_id=customer_confirmed.workflow_id,
        cfs_solution_id=cfs_after.solution.id,
        generated_at=datetime.now(UTC),
        boundary=BOUNDARY,
    )
