from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database
from app.schemas.common import DependencyStatus, HealthResponse

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
