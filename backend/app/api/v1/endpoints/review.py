from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor, require_roles
from app.core.database import get_session
from app.schemas.review_workflow import (
    AdvisorDossier,
    AdvisorHouseholdList,
    ComplaintReplayRequest,
    ComplaintReplayResponse,
    ComplianceEvidence,
    ComplianceQueue,
    CreatePlanWorkflowRequest,
    MockBankSnapshot,
    PlanWorkflowResponse,
    WorkflowActionRequest,
)
from app.services.mock_bank import audit_mock_bank_access, build_mock_bank_snapshot
from app.services.review_workflow import (
    ADVISOR_ROLES,
    build_advisor_dossier,
    build_advisor_household_list,
    build_audit_package,
    build_compliance_queue,
    create_plan_workflow,
    get_compliance_evidence,
    get_latest_household_workflow,
    get_plan_workflow,
    replay_complaint,
    transition_plan_workflow,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["advisor-compliance-workflow"])


def _request_id(request: Request) -> str:
    return str(request.state.request_id)


@router.get("/advisor/households", response_model=AdvisorHouseholdList)
def get_advisor_households(
    session: SessionDependency,
    actor: ActorDependency,
) -> AdvisorHouseholdList:
    return build_advisor_household_list(session, actor)


@router.get(
    "/households/{household_id}/advisor-dossier",
    response_model=AdvisorDossier,
)
def get_advisor_dossier(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> AdvisorDossier:
    return build_advisor_dossier(session, household_id, actor)


@router.get(
    "/households/{household_id}/mock-bank-snapshot",
    response_model=MockBankSnapshot,
)
def get_mock_bank_snapshot(
    request: Request,
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> MockBankSnapshot:
    require_roles(actor, ADVISOR_ROLES)
    snapshot = build_mock_bank_snapshot(session, household_id, date.today())
    audit_mock_bank_access(session, snapshot, actor, _request_id(request))
    return snapshot


@router.post(
    "/households/{household_id}/plan-workflows",
    response_model=PlanWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_plan_workflow(
    request_context: Request,
    household_id: str,
    payload: CreatePlanWorkflowRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PlanWorkflowResponse:
    return create_plan_workflow(
        session,
        household_id,
        payload,
        actor,
        _request_id(request_context),
    )


@router.get(
    "/households/{household_id}/plan-workflows/current",
    response_model=PlanWorkflowResponse | None,
)
def get_current_household_plan_workflow(
    household_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> PlanWorkflowResponse | None:
    return get_latest_household_workflow(session, household_id, actor)


@router.get("/plan-workflows/{workflow_id}", response_model=PlanWorkflowResponse)
def get_workflow(
    workflow_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> PlanWorkflowResponse:
    return get_plan_workflow(session, workflow_id, actor)


@router.post(
    "/plan-workflows/{workflow_id}/actions",
    response_model=PlanWorkflowResponse,
)
def post_workflow_action(
    request_context: Request,
    workflow_id: str,
    payload: WorkflowActionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PlanWorkflowResponse:
    return transition_plan_workflow(
        session,
        workflow_id,
        payload,
        actor,
        _request_id(request_context),
    )


@router.get("/compliance/review-queue", response_model=ComplianceQueue)
def get_compliance_review_queue(
    session: SessionDependency,
    actor: ActorDependency,
) -> ComplianceQueue:
    return build_compliance_queue(session, actor)


@router.get(
    "/plan-workflows/{workflow_id}/compliance-evidence",
    response_model=ComplianceEvidence,
)
def get_workflow_compliance_evidence(
    workflow_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> ComplianceEvidence:
    return get_compliance_evidence(session, workflow_id, actor)


@router.post(
    "/plan-workflows/{workflow_id}/complaint-replays",
    response_model=ComplaintReplayResponse,
)
def post_complaint_replay(
    request_context: Request,
    workflow_id: str,
    payload: ComplaintReplayRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ComplaintReplayResponse:
    return replay_complaint(
        session,
        workflow_id,
        payload,
        actor,
        _request_id(request_context),
    )


@router.get("/plan-workflows/{workflow_id}/audit-export")
def get_workflow_audit_export(
    request_context: Request,
    workflow_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> Response:
    package = build_audit_package(
        session,
        workflow_id,
        actor,
        _request_id(request_context),
    )
    return Response(
        content=package.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="wealthtwin-workflow-{workflow_id[:8]}-audit.json"'
            )
        },
    )
