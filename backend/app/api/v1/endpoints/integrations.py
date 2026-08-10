from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.integrations import IntegrationReadinessResponse
from app.services.integrations.registry import build_integration_readiness

router = APIRouter(prefix="/integrations", tags=["production-integration-readiness"])


@router.get("/readiness", response_model=IntegrationReadinessResponse)
def get_integration_readiness() -> IntegrationReadinessResponse:
    return build_integration_readiness(get_settings())
