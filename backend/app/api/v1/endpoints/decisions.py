from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.database import get_session
from app.schemas.decision_evidence_v2 import DecisionEvidenceV2, DecisionReplayResponse
from app.services.governance.replay import get_decision_evidence, replay_decision

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(tags=["v5-decision-evidence"])


@router.get("/decisions/{decision_id}/evidence", response_model=DecisionEvidenceV2)
def read_decision_evidence(
    decision_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> DecisionEvidenceV2:
    return get_decision_evidence(session, decision_id, actor)


@router.post("/decisions/{decision_id}/replay", response_model=DecisionReplayResponse)
def post_decision_replay(
    request: Request,
    decision_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> DecisionReplayResponse:
    return replay_decision(
        session,
        decision_id,
        actor,
        str(request.state.request_id),
    )
