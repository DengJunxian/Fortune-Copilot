from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.auth import (
    ActorContext,
    require_actor,
    require_roles,
    require_sensitive_confirmation,
)
from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.demo import (
    DemoControlResponse,
    DemoManifestResponse,
    DemoPreheatResponse,
    DemoRunRequest,
    DemoRunResponse,
    ExperimentSuiteResponse,
    FamilyComparisonResponse,
)
from app.schemas.persona_release import FounderStoryResponse, PersonaReleaseResponse
from app.services.demo_release import (
    compare_demo_families,
    demo_manifest,
    get_demo_run,
    latest_experiment_suite,
    load_demo_data,
    preheat_demo,
    reset_demo_data,
    retry_demo_run,
    run_experiment_suite,
    run_main_demo,
)
from app.services.founder_story import run_founder_story
from app.services.persona_release import run_persona_release

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(prefix="/demo", tags=["complete-demo-release"])


@router.get("/manifest", response_model=DemoManifestResponse)
def get_demo_manifest(
    session: SessionDependency, actor: ActorDependency
) -> DemoManifestResponse:
    require_roles(actor, ("client", "advisor", "compliance", "admin"))
    return demo_manifest(session, get_settings())


@router.post("/load", response_model=DemoControlResponse)
def post_demo_load(
    session: SessionDependency, actor: ActorDependency
) -> DemoControlResponse:
    require_roles(actor, ("admin",))
    return load_demo_data(session, get_settings(), actor)


@router.post("/reset", response_model=DemoControlResponse)
def post_demo_reset(
    request: Request,
    session: SessionDependency,
    actor: ActorDependency,
) -> DemoControlResponse:
    require_roles(actor, ("admin",))
    require_sensitive_confirmation(request, "reset_synthetic_demo")
    return reset_demo_data(session, get_settings(), actor)


@router.post("/preheat", response_model=DemoPreheatResponse)
def post_demo_preheat(
    session: SessionDependency, actor: ActorDependency
) -> DemoPreheatResponse:
    require_roles(actor, ("admin",))
    return preheat_demo(session, get_settings(), actor)


@router.get("/families/comparison", response_model=FamilyComparisonResponse)
def get_demo_family_comparison(
    session: SessionDependency, actor: ActorDependency
) -> FamilyComparisonResponse:
    require_roles(actor, ("client", "advisor", "compliance", "admin"))
    return compare_demo_families(session, get_settings())


@router.post(
    "/runs",
    response_model=DemoRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_main_demo_run(
    payload: DemoRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> DemoRunResponse:
    require_roles(actor, ("admin",))
    return run_main_demo(session, payload, actor, get_settings())


@router.get("/runs/{run_id}", response_model=DemoRunResponse)
def get_main_demo_run(
    run_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> DemoRunResponse:
    require_roles(actor, ("advisor", "compliance", "admin"))
    return get_demo_run(session, run_id)


@router.post("/runs/{run_id}/retry", response_model=DemoRunResponse)
def post_main_demo_retry(
    run_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> DemoRunResponse:
    require_roles(actor, ("admin",))
    return retry_demo_run(session, run_id, actor, get_settings())


@router.post("/experiments/run", response_model=ExperimentSuiteResponse)
def post_demo_experiment_suite(
    session: SessionDependency,
    actor: ActorDependency,
) -> ExperimentSuiteResponse:
    require_roles(actor, ("compliance", "admin"))
    return run_experiment_suite(session, actor, get_settings())


@router.get("/experiments/latest", response_model=ExperimentSuiteResponse | None)
def get_latest_demo_experiment_suite(
    session: SessionDependency,
    actor: ActorDependency,
) -> ExperimentSuiteResponse | None:
    require_roles(actor, ("advisor", "compliance", "admin"))
    return latest_experiment_suite(session)


@router.post("/v5/release-benchmark", response_model=PersonaReleaseResponse)
def post_v5_release_benchmark(
    request: Request,
    session: SessionDependency,
    actor: ActorDependency,
) -> PersonaReleaseResponse:
    require_roles(actor, ("admin",))
    require_sensitive_confirmation(request, "run_v5_release_benchmark")
    return run_persona_release(session, get_settings())


@router.post("/v5/founder-story", response_model=FounderStoryResponse)
def post_v5_founder_story(
    request: Request,
    session: SessionDependency,
    actor: ActorDependency,
) -> FounderStoryResponse:
    require_roles(actor, ("admin",))
    require_sensitive_confirmation(request, "run_founder_story")
    return run_founder_story(session, get_settings())
