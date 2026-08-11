from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ComplexityLevel, LiquidityLevel, ProductFamily
from app.models.governance import Product, ProductSnapshot
from app.schemas.fund_advisory import VerifiedFundCatalogFile, VerifiedFundProduct
from app.services.fund_advisory.catalog import load_fund_advisory_catalog

CLASSIFICATION_VERSION = "product-ontology-v1"
SOURCE_TYPE = "verified_real_public_funds"
EXECUTION_BOUNDARY = (
    "候选来自经核验的公开基金资料，不代表当前账户可售、适当性通过或已经获得交易授权；"
    "执行前必须在持牌渠道核验当日状态、费用、限额与交易确认页。"
)

FAMILY_BY_CATEGORY: dict[str, ProductFamily] = {
    "money_market": ProductFamily.MONEY_MARKET_FUND,
    "short_bond": ProductFamily.BOND_FUND,
    "pure_bond": ProductFamily.BOND_FUND,
    "domestic_broad_index": ProductFamily.EQUITY_INDEX_FUND,
    "pension_bond_fof": ProductFamily.PERSONAL_PENSION_PRODUCT,
    "pension_broad_index": ProductFamily.PERSONAL_PENSION_PRODUCT,
}

ASSET_CLASS_BY_CATEGORY = {
    "money_market": "cash_equivalent",
    "short_bond": "fixed_income",
    "pure_bond": "fixed_income",
    "domestic_broad_index": "equity",
    "pension_bond_fof": "retirement_fixed_income",
    "pension_broad_index": "retirement_equity",
}


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _liquidity_level(product: VerifiedFundProduct) -> LiquidityLevel:
    if product.minimum_holding_days >= 365:
        return LiquidityLevel.WITHIN_1_YEAR
    if product.minimum_holding_days >= 30:
        return LiquidityLevel.WITHIN_30_DAYS
    return LiquidityLevel.WITHIN_7_DAYS


def _product_values(
    product: VerifiedFundProduct,
    catalog: VerifiedFundCatalogFile,
) -> dict[str, object]:
    source_reference = product.evidence[0].url
    evidence = [item.model_dump(mode="json") for item in product.evidence]
    wrappers = ["personal_pension"] if product.personal_pension_eligible else ["ordinary"]
    underlying_assets: list[str] = [product.category]
    if product.tracked_index:
        underlying_assets.append(product.tracked_index)
    return {
        "name": product.name,
        "product_type": product.category,
        "asset_class": ASSET_CLASS_BY_CATEGORY[product.category],
        "risk_level": product.internal_risk_level,
        "liquidity_level": _liquidity_level(product),
        "minimum_investment": Decimal("0"),
        "term_months": 0,
        "minimum_holding_months": (product.minimum_holding_days + 29) // 30,
        "redemption_rules": product.normal_redemption_note,
        "annual_fee_rate": Decimal("0"),
        "underlying_assets": underlying_assets,
        "historical_volatility_min": Decimal("0"),
        "historical_volatility_max": Decimal("0"),
        "suitable_accounts": wrappers,
        "principal_guaranteed": False,
        "guarantee_basis": None,
        "guarantee_disclosure": "公开募集基金不属于依法保本的银行存款。",
        "non_guaranteed_disclosure": "基金净值会波动，本金可能损失。",
        "complexity_level": (
            ComplexityLevel.COMPLEX
            if product.personal_pension_eligible
            else ComplexityLevel.STANDARD
        ),
        "catalog_version": catalog.catalog_version,
        "professional_only": False,
        "education_only": False,
        "enabled": True,
        "is_simulated": False,
        "terms": {
            "share_class": product.share_class,
            "trade_venue": product.trade_venue,
            "tracked_index": product.tracked_index,
            "broad_index": product.broad_index,
            "personal_pension_eligible": product.personal_pension_eligible,
            "icbc_publicly_listed": product.icbc_publicly_listed,
            "icbc_channel_status": product.icbc_channel_status,
            "selection_priority": product.selection_priority,
            "catalog_data_date": catalog.data_date.isoformat(),
            "catalog_verified_on": catalog.verified_on.isoformat(),
        },
        "account_wrappers": wrappers,
        "principal_loss_possible": True,
        "legally_principal_guaranteed": False,
        "liquidity_days": max(1, product.minimum_holding_days),
        "lock_up": product.minimum_holding_days > 0,
        "withdrawable_date": None,
        "volatility": Decimal("0"),
        "sale_status": "channel_verification_required",
        "channel": (
            "icbc_public_listing"
            if product.icbc_publicly_listed
            else "verified_public_catalog"
        ),
        "source_reference": source_reference,
        "snapshot_version": f"{catalog.catalog_code}@{catalog.catalog_version}:{product.code}",
        "issuer": product.manager,
        "jurisdiction": "CN",
        "currency": "CNY",
        "product_family": FAMILY_BY_CATEGORY[product.category],
        "product_subtype": product.category,
        "all_in_cost": None,
        "distribution_incentive_disclosure": (
            "公开目录未提供客户全口径费用和渠道激励；执行前必须补充核验。"
        ),
        "conflict_of_interest_flag": False,
        "professional_review_required": product.personal_pension_eligible,
        "client_role_in_cfs": product.eligible_sleeves,
        "classification_version": CLASSIFICATION_VERSION,
        "evidence_json": {
            "source_type": SOURCE_TYPE,
            "catalog_code": catalog.catalog_code,
            "catalog_version": catalog.catalog_version,
            "catalog_scope": catalog.scope,
            "evidence": evidence,
        },
        "valuation_date": catalog.data_date,
        "data_source": SOURCE_TYPE,
        "is_user_confirmed": False,
    }


def _snapshot_payload(
    product: VerifiedFundProduct,
    catalog: VerifiedFundCatalogFile,
) -> dict[str, object]:
    evidence = [item.model_dump(mode="json") for item in product.evidence]
    channel = (
        "icbc_public_listing" if product.icbc_publicly_listed else "verified_public_catalog"
    )
    sale_status = "channel_verification_required"
    fee_snapshot = {
        "all_in_cost": None,
        "status": "not_available_in_controlled_catalog",
        "required_action": "执行前核验申购费、赎回费、管理费及销售服务费。",
    }
    liquidity_snapshot = {
        "minimum_holding_days": product.minimum_holding_days,
        "normal_redemption_note": product.normal_redemption_note,
        "lock_up": product.minimum_holding_days > 0,
    }
    terms_snapshot = {
        "share_class": product.share_class,
        "category": product.category,
        "trade_venue": product.trade_venue,
        "tracked_index": product.tracked_index,
        "broad_index": product.broad_index,
        "personal_pension_eligible": product.personal_pension_eligible,
        "icbc_publicly_listed": product.icbc_publicly_listed,
        "icbc_channel_status": product.icbc_channel_status,
        "channel_note": product.icbc_channel_note,
    }
    canonical = {
        "product_code": product.code,
        "catalog_code": catalog.catalog_code,
        "catalog_version": catalog.catalog_version,
        "catalog_data_date": catalog.data_date,
        "verified_on": catalog.verified_on,
        "sale_status": sale_status,
        "risk_level": product.internal_risk_level,
        "fee_snapshot": fee_snapshot,
        "liquidity_snapshot": liquidity_snapshot,
        "terms_snapshot": terms_snapshot,
        "channel": channel,
        "evidence": evidence,
    }
    return {
        "as_of_date": catalog.verified_on,
        "sale_status": sale_status,
        "risk_level": product.internal_risk_level,
        "fee_snapshot": fee_snapshot,
        "liquidity_snapshot": liquidity_snapshot,
        "terms_snapshot": terms_snapshot,
        "channel": channel,
        "source_reference": product.evidence[0].url,
        "evidence": evidence,
        "snapshot_hash": _canonical_hash(canonical),
        "snapshot_version": f"{catalog.catalog_code}@{catalog.catalog_version}:{product.code}",
        "currency": "CNY",
        "valuation_date": catalog.data_date,
        "data_source": SOURCE_TYPE,
        "is_user_confirmed": False,
    }


def ensure_verified_fund_ontology(
    session: Session,
    configured_path: str,
) -> tuple[VerifiedFundCatalogFile, list[Product], list[ProductSnapshot]]:
    catalog = load_fund_advisory_catalog(configured_path)
    codes = [item.code for item in catalog.products]
    existing_products = {
        item.code: item
        for item in session.scalars(select(Product).where(Product.code.in_(codes))).all()
    }
    products: list[Product] = []
    snapshots: list[ProductSnapshot] = []
    for source in catalog.products:
        product = existing_products.get(source.code)
        values = _product_values(source, catalog)
        if product is None:
            product = Product(code=source.code, **values)
            session.add(product)
            session.flush()
        else:
            changed = any(getattr(product, key) != value for key, value in values.items())
            if changed:
                for key, value in values.items():
                    setattr(product, key, value)
                product.is_deleted = False
                product.deleted_at = None
                product.version += 1
                session.flush()
        products.append(product)

        snapshot_values = _snapshot_payload(source, catalog)
        snapshot = session.scalar(
            select(ProductSnapshot).where(
                ProductSnapshot.product_id == product.id,
                ProductSnapshot.snapshot_hash == snapshot_values["snapshot_hash"],
            )
        )
        if snapshot is None:
            snapshot = ProductSnapshot(product_id=product.id, **snapshot_values)
            session.add(snapshot)
            session.flush()
        snapshots.append(snapshot)
    return catalog, products, snapshots


def latest_product_snapshot(session: Session, product_id: str) -> ProductSnapshot | None:
    return session.scalar(
        select(ProductSnapshot)
        .where(
            ProductSnapshot.product_id == product_id,
            ProductSnapshot.is_deleted.is_(False),
        )
        .order_by(ProductSnapshot.as_of_date.desc(), ProductSnapshot.created_at.desc())
        .limit(1)
    )


def snapshot_is_stale(snapshot: ProductSnapshot, as_of: date, maximum_age_days: int) -> bool:
    return max(0, (as_of - snapshot.as_of_date).days) > maximum_age_days
