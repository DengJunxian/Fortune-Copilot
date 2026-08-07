from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.trust import (
    AgentCatalogResponse,
    ConfirmIntakeDraftRequest,
    GovernanceValidationRequest,
    GovernanceValidationResponse,
    HouseholdGraphResponse,
    IntakeDraftRequest,
    IntakeDraftResponse,
    KnowledgeCatalogResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    OrchestrationRequest,
    OrchestrationResponse,
)
from app.services.trust.agents import agent_catalog
from app.services.trust.governance import validate_governed_output
from app.services.trust.graph import household_graph, shanghai_demo_graph
from app.services.trust.intake import (
    confirm_intake_draft,
    create_intake_draft,
    get_intake_draft,
)
from app.services.trust.knowledge import (
    ensure_knowledge_base,
    knowledge_catalog,
    search_knowledge,
)
from app.services.trust.orchestrator import (
    get_orchestration,
    latest_orchestration,
    run_orchestration,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AsOfDate = Annotated[date | None, Query(description="政策与关系推导的可复现日期")]

router = APIRouter(tags=["trusted-ai"])


def _ensure_knowledge(session: Session) -> None:
    ensure_knowledge_base(session, get_settings().knowledge_base_path)


@router.get("/trust/knowledge/catalog", response_model=KnowledgeCatalogResponse)
def get_knowledge_catalog(
    session: SessionDependency,
    _actor: ActorDependency,
    as_of_date: AsOfDate = None,
) -> KnowledgeCatalogResponse:
    settings = get_settings()
    _ensure_knowledge(session)
    return knowledge_catalog(
        session,
        settings.knowledge_base_path,
        as_of=as_of_date or date.today(),
    )


@router.post("/trust/knowledge/search", response_model=KnowledgeSearchResponse)
def post_knowledge_search(
    request: KnowledgeSearchRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> KnowledgeSearchResponse:
    settings = get_settings()
    _ensure_knowledge(session)
    return search_knowledge(session, settings.knowledge_base_path, request, actor=actor)


@router.get("/trust/graphs/shanghai-demo", response_model=HouseholdGraphResponse)
def get_shanghai_demo_graph(
    _actor: ActorDependency,
    as_of_date: AsOfDate = None,
) -> HouseholdGraphResponse:
    return shanghai_demo_graph(as_of=as_of_date or date.today())


@router.get(
    "/households/{household_id}/trust-graph",
    response_model=HouseholdGraphResponse,
)
def get_household_trust_graph(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    analysis_date: AsOfDate = None,
) -> HouseholdGraphResponse:
    settings = get_settings()
    _ensure_knowledge(session)
    return household_graph(
        session,
        household_id,
        analysis_date=analysis_date or date.today(),
        financial_rules_path=settings.financial_rules_path,
    )


@router.get("/trust/agents/catalog", response_model=AgentCatalogResponse)
def get_agent_catalog(_actor: ActorDependency) -> AgentCatalogResponse:
    return agent_catalog()


@router.post(
    "/households/{household_id}/trust-orchestrations",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_trust_orchestration(
    household_id: str,
    request: OrchestrationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> OrchestrationResponse:
    settings = get_settings()
    _ensure_knowledge(session)
    return run_orchestration(session, household_id, request, actor, settings)


@router.get(
    "/households/{household_id}/trust-orchestrations/latest",
    response_model=OrchestrationResponse | None,
)
def get_latest_trust_orchestration(
    household_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> OrchestrationResponse | None:
    return latest_orchestration(session, household_id, get_settings())


@router.get(
    "/households/{household_id}/trust-orchestrations/{run_id}",
    response_model=OrchestrationResponse,
)
def get_trust_orchestration(
    household_id: str,
    run_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
) -> OrchestrationResponse:
    return get_orchestration(session, household_id, run_id, get_settings())


@router.post(
    "/trust/intake/drafts",
    response_model=IntakeDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_intake_draft(
    request: IntakeDraftRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> IntakeDraftResponse:
    return create_intake_draft(session, request, actor)


@router.get("/trust/intake/drafts/{draft_id}", response_model=IntakeDraftResponse)
def get_intake_draft_by_id(
    draft_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> IntakeDraftResponse:
    return get_intake_draft(session, draft_id, actor)


@router.post(
    "/trust/intake/drafts/{draft_id}/confirm",
    response_model=IntakeDraftResponse,
)
def post_intake_draft_confirmation(
    draft_id: str,
    request: ConfirmIntakeDraftRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> IntakeDraftResponse:
    return confirm_intake_draft(session, draft_id, request, actor)


@router.post(
    "/trust/governance/validate",
    response_model=GovernanceValidationResponse,
)
def post_governance_validation(
    request: GovernanceValidationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> GovernanceValidationResponse:
    return validate_governed_output(session, request, actor=actor)
