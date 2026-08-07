from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.fund_advisory import (
    VerifiedFundCatalogFile,
    VerifiedFundCatalogResponse,
)


def resolve_fund_advisory_catalog_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4]
            / "data/products/verified_real_funds_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "fund_advisory_catalog_missing",
        "找不到经核验的真实基金目录",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_fund_advisory_catalog(configured_path: str) -> VerifiedFundCatalogFile:
    path = resolve_fund_advisory_catalog_path(configured_path)
    try:
        return VerifiedFundCatalogFile.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "fund_advisory_catalog_invalid",
            "真实基金目录未通过代码、宽基、养老资格或工行证据校验",
            status_code=500,
        ) from exc


def catalog_is_stale(catalog: VerifiedFundCatalogFile, as_of: date) -> bool:
    return as_of > catalog.verified_on + timedelta(days=catalog.verification_expiry_days)


def build_fund_catalog_response(
    configured_path: str,
    as_of: date,
) -> VerifiedFundCatalogResponse:
    catalog = load_fund_advisory_catalog(configured_path)
    products = sorted(catalog.products, key=lambda item: (item.selection_priority, item.code))
    return VerifiedFundCatalogResponse(
        catalog_code=catalog.catalog_code,
        catalog_version=catalog.catalog_version,
        data_date=catalog.data_date,
        verified_on=catalog.verified_on,
        source_type=catalog.source_type,
        catalog_stale=catalog_is_stale(catalog, as_of),
        scope=catalog.scope,
        mandatory_channel_notice=catalog.mandatory_channel_notice,
        personal_pension_catalog_observation=catalog.personal_pension_catalog_observation,
        product_count=len(products),
        products=products,
    )
