from fastapi import APIRouter

from app.core.config import get_settings
from app.services.public_data.models import PublicDataSnapshotResponse
from app.services.public_data.rules import build_public_data_response

router = APIRouter(prefix="/public-data", tags=["governed-public-data"])


@router.get("/authoritative-snapshot", response_model=PublicDataSnapshotResponse)
def get_authoritative_public_snapshot() -> PublicDataSnapshotResponse:
    return build_public_data_response(get_settings().public_data_snapshot_path)
