from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.governance import Product
from app.schemas.portfolio import (
    ProductCatalogFile,
    ProductCatalogItem,
    ProductCatalogResponse,
    ProductOut,
)


def resolve_product_catalog_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/products/mock_products_v1.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "product_catalog_missing",
        "找不到受控模拟产品目录",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_product_catalog(configured_path: str) -> ProductCatalogFile:
    path = resolve_product_catalog_path(configured_path)
    try:
        return ProductCatalogFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "product_catalog_invalid",
            "受控模拟产品目录未通过结构和保本边界校验",
            status_code=500,
        ) from exc


def _record_values(item: ProductCatalogItem, catalog: ProductCatalogFile) -> dict[str, object]:
    return {
        **item.model_dump(mode="python"),
        "catalog_version": catalog.catalog_version,
        "valuation_date": catalog.data_date,
        "data_source": catalog.source,
        "is_user_confirmed": True,
    }


def ensure_mock_product_catalog(
    session: Session,
    catalog: ProductCatalogFile,
) -> list[Product]:
    existing = {
        item.code: item
        for item in session.scalars(
            select(Product).where(Product.is_simulated.is_(True), Product.is_deleted.is_(False))
        )
    }
    records: list[Product] = []
    for item in catalog.products:
        record = existing.get(item.code)
        values = _record_values(item, catalog)
        if record is None:
            record = Product(**values)
            session.add(record)
        elif record.catalog_version != catalog.catalog_version:
            for key, value in values.items():
                setattr(record, key, value)
            record.version += 1
        records.append(record)
    session.flush()
    return records


def product_to_schema(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        code=product.code,
        name=product.name,
        product_type=product.product_type,
        asset_class=product.asset_class,
        risk_level=product.risk_level,
        term_months=product.term_months,
        minimum_holding_months=product.minimum_holding_months,
        liquidity_level=product.liquidity_level,
        redemption_rules=product.redemption_rules,
        annual_fee_rate=product.annual_fee_rate,
        underlying_assets=product.underlying_assets,
        historical_volatility_min=product.historical_volatility_min,
        historical_volatility_max=product.historical_volatility_max,
        minimum_investment=product.minimum_investment,
        suitable_accounts=product.suitable_accounts,
        principal_guaranteed=product.principal_guaranteed,
        guarantee_basis=product.guarantee_basis,
        guarantee_disclosure=product.guarantee_disclosure,
        non_guaranteed_disclosure=product.non_guaranteed_disclosure,
        complexity_level=product.complexity_level,
        professional_only=product.professional_only,
        education_only=product.education_only,
        enabled=product.enabled,
        is_simulated=product.is_simulated,
        terms=product.terms,
        catalog_version=product.catalog_version,
        data_date=product.valuation_date or product.created_at.date(),
        source=product.data_source,
    )


def build_catalog_response(
    session: Session,
    configured_path: str,
) -> ProductCatalogResponse:
    catalog = load_product_catalog(configured_path)
    products = ensure_mock_product_catalog(session, catalog)
    ordered = sorted(products, key=lambda item: (int(item.terms.get("priority", 50)), item.code))
    return ProductCatalogResponse(
        catalog_code=catalog.catalog_code,
        catalog_version=catalog.catalog_version,
        data_date=catalog.data_date,
        source_summary=catalog.source_summary,
        product_count=len(ordered),
        products=[product_to_schema(item) for item in ordered],
        professional_hedge_lab_enabled=False,
    )
