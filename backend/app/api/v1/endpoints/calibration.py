from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.domain.enums import CalibrationMode
from app.schemas.calibration import (
    CalibrationCatalogResponse,
    CalibrationParameterResolution,
)
from app.services.calibration.registry import (
    build_calibration_catalog,
    build_database_calibration_port,
)

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]

router = APIRouter(prefix="/calibration", tags=["v5-china-calibration"])


def require_calibration_enabled() -> None:
    if not get_settings().enable_v5_calibration:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 中国本地化校准层",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_calibration_enabled)]


@router.get("/catalog", response_model=CalibrationCatalogResponse)
def read_calibration_catalog(
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> CalibrationCatalogResponse:
    return build_calibration_catalog(session, get_settings().calibration_registry_path)


@router.get(
    "/parameters/{parameter_code:path}",
    response_model=CalibrationParameterResolution,
)
def read_calibration_parameter(
    parameter_code: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
    segment: Annotated[str, Query(min_length=1, max_length=100)] = "all",
    region: Annotated[str, Query(min_length=1, max_length=40)] = "CN",
    effective_date: Annotated[date | None, Query()] = None,
    mode: Annotated[CalibrationMode | None, Query()] = None,
) -> CalibrationParameterResolution:
    allowed_modes = (mode,) if mode is not None else None
    port = build_database_calibration_port(
        session,
        get_settings().calibration_registry_path,
        allowed_modes=allowed_modes,
    )
    return port.get_parameter(
        parameter_code,
        segment,
        region,
        effective_date or date.today(),
    )
