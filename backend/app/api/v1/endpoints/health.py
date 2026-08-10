from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.database import check_database
from app.schemas.common import (
    DependencyStatus,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
)
from app.services.integrations.registry import build_integration_readiness

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    database_status, database_detail = check_database()
    overall = "ok" if database_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        runtime_mode=settings.app_env,
        mock_mode=settings.is_mock_mode,
        database=DependencyStatus(status=database_status, detail=database_detail),
    )


@router.get("/health/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse(version=get_settings().app_version)


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(response: Response) -> ReadinessResponse:
    settings = get_settings()
    database_status, database_detail = check_database()
    integration_readiness = build_integration_readiness(settings)
    requires_production_integrations = settings.is_production
    blocking = []
    if database_status != "ok":
        blocking.append("database")
    if requires_production_integrations and not integration_readiness.production_ready:
        blocking.extend(
            item.capability
            for item in integration_readiness.capabilities
            if item.production_blocking
        )
    ready = not blocking
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        runtime_mode=settings.app_env,
        database=DependencyStatus(status=database_status, detail=database_detail),
        production_integrations_ready=integration_readiness.production_ready,
        blocking_dependencies=blocking,
        boundary_note=(
            "开发/演示环境仅检查本地运行依赖；生产环境会把未接入的银行能力和未验证的"
            "运维控制列为就绪硬阻断。"
        ),
    )
