from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import ActorContext, require_actor
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.domain.enums import ProductFamily
from app.models.governance import Product, ProductSnapshot
from app.schemas.fund_advisory import VerifiedFundCatalogFile
from app.schemas.product_ontology import (
    CFSProductCompositionResponse,
    ProductDetailResponse,
    ProductEligibilityRequest,
    ProductEligibilityResponse,
    ProductOntologyItem,
    ProductRankRequest,
    ProductRankResponse,
    ProductSearchResponse,
    SnapshotFreshness,
)
from app.services.fund_advisory.catalog import catalog_is_stale
from app.services.product_eligibility.engine import evaluate_product_eligibility
from app.services.product_ontology.adapter import (
    CLASSIFICATION_VERSION,
    EXECUTION_BOUNDARY,
    ensure_verified_fund_ontology,
)
from app.services.product_ontology.composition import compose_cfs_product_candidates
from app.services.product_ontology.ranking import rank_products

SessionDependency = Annotated[Session, Depends(get_session)]
ActorDependency = Annotated[ActorContext, Depends(require_actor)]
AnalysisDateQuery = Annotated[date | None, Query(description="产品证据与快照复核日")]

router = APIRouter(tags=["v5-product-ontology"])


def require_product_ontology_enabled() -> None:
    if not get_settings().enable_v5_product_ontology:
        raise AppError(
            "feature_not_enabled",
            "当前环境尚未启用 V5 产品本体",
            status_code=404,
        )


FeatureDependency = Annotated[None, Depends(require_product_ontology_enabled)]


def _ontology_records(
    session: Session,
) -> tuple[VerifiedFundCatalogFile, list[Product], dict[str, ProductSnapshot]]:
    catalog, products, snapshots = ensure_verified_fund_ontology(
        session, get_settings().fund_advisory_catalog_path
    )
    session.commit()
    return catalog, products, {item.product_id: item for item in snapshots}


@router.get("/products/search", response_model=ProductSearchResponse)
def search_products(
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
    q: Annotated[str | None, Query(max_length=160)] = None,
    family: Annotated[ProductFamily | None, Query()] = None,
    client_role: Annotated[str | None, Query(max_length=80)] = None,
    analysis_date: AnalysisDateQuery = None,
) -> ProductSearchResponse:
    catalog, products, _snapshots = _ontology_records(session)
    as_of = analysis_date or date.today()
    query = (q or "").strip().casefold()
    filtered = [
        item
        for item in products
        if item.classification_version == CLASSIFICATION_VERSION
        and (family is None or item.product_family == family)
        and (client_role is None or client_role in item.client_role_in_cfs)
        and (
            not query
            or query in item.code.casefold()
            or query in item.name.casefold()
            or query in item.issuer.casefold()
        )
    ]
    filtered.sort(key=lambda item: (int(item.terms.get("selection_priority", 100)), item.code))
    stale = catalog_is_stale(catalog, as_of)
    return ProductSearchResponse(
        query=q,
        taxonomy_version=CLASSIFICATION_VERSION,
        catalog_version=catalog.catalog_version,
        catalog_as_of=catalog.verified_on,
        catalog_stale=stale,
        executable_recommendations_allowed=False,
        product_count=len(filtered),
        products=[ProductOntologyItem.model_validate(item) for item in filtered],
        execution_boundary=EXECUTION_BOUNDARY,
    )


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
def get_product(
    product_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> ProductDetailResponse:
    _catalog, products, snapshots = _ontology_records(session)
    product = next((item for item in products if item.id == product_id), None)
    snapshot = snapshots.get(product_id)
    if product is None or snapshot is None:
        raise AppError("product_not_found", "找不到可核验的产品本体记录", status_code=404)
    as_of = analysis_date or date.today()
    age_days = max(0, (as_of - snapshot.as_of_date).days)
    stale = age_days > 45
    return ProductDetailResponse(
        product=ProductOntologyItem.model_validate(product),
        snapshot=snapshot,
        freshness=SnapshotFreshness(
            as_of_date=snapshot.as_of_date,
            age_days=age_days,
            maximum_age_days=45,
            stale=stale,
            sale_status=snapshot.sale_status,
            executable=not stale and snapshot.sale_status == "available",
        ),
        execution_boundary=EXECUTION_BOUNDARY,
    )


@router.post("/products/eligibility-check", response_model=ProductEligibilityResponse)
def check_product_eligibility(
    payload: ProductEligibilityRequest,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> ProductEligibilityResponse:
    _catalog, products, snapshots = _ontology_records(session)
    product = next((item for item in products if item.id == payload.product_id), None)
    snapshot = snapshots.get(payload.product_id)
    if product is None or snapshot is None:
        raise AppError("product_not_found", "找不到可核验的产品本体记录", status_code=404)
    return evaluate_product_eligibility(product, snapshot, payload.context)


@router.post("/products/rank", response_model=ProductRankResponse)
def rank_product_candidates(
    payload: ProductRankRequest,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
) -> ProductRankResponse:
    catalog, products, snapshots = _ontology_records(session)
    return rank_products(products, snapshots, payload, catalog)


@router.get(
    "/households/{household_id}/cfs-solutions/{solution_id}/product-candidates",
    response_model=CFSProductCompositionResponse,
)
def get_cfs_product_candidates(
    household_id: str,
    solution_id: str,
    session: SessionDependency,
    _actor: ActorDependency,
    _feature: FeatureDependency,
    analysis_date: AnalysisDateQuery = None,
) -> CFSProductCompositionResponse:
    result = compose_cfs_product_candidates(
        session,
        household_id,
        solution_id,
        get_settings().fund_advisory_catalog_path,
        analysis_date=analysis_date or date.today(),
    )
    session.commit()
    return result
