from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.orm import Session

from app.domain.enums import (
    AccountWrapper,
    ComplexityLevel,
    LiquidityLevel,
    PropertyUse,
)
from app.domain.financial import AssetFact, HouseholdFacts
from app.models.wealth_graph import Position
from app.schemas.financial_graph import ProjectionDiagnostic
from app.services.financial.facts import load_household_facts

from .repository import FinancialGraphRecords, load_financial_graph


def _enum_value[EnumT: StrEnum](
    enum_type: type[EnumT],
    raw: object,
    default: EnumT,
) -> EnumT:
    if isinstance(raw, enum_type):
        return raw
    if isinstance(raw, str):
        try:
            return enum_type(raw.casefold())
        except ValueError:
            try:
                return enum_type[raw.upper()]
            except KeyError:
                return default
    return default


def _liquidity_default(days: int) -> LiquidityLevel:
    if days <= 1:
        return LiquidityLevel.IMMEDIATE
    if days <= 7:
        return LiquidityLevel.WITHIN_7_DAYS
    if days <= 30:
        return LiquidityLevel.WITHIN_30_DAYS
    if days <= 365:
        return LiquidityLevel.WITHIN_1_YEAR
    return LiquidityLevel.ILLIQUID


def _asset_fact(position: Position, graph: FinancialGraphRecords) -> AssetFact:
    evidence = position.evidence_json or {}
    account = next((item for item in graph.accounts if item.id == position.account_id), None)
    account_wrapper = account.account_wrapper if account is not None else AccountWrapper.ORDINARY
    legacy_version = evidence.get("version", evidence.get("legacy_version", position.version))
    return AssetFact(
        id=position.legacy_asset_id or position.id,
        owner_member_id=(
            str(evidence["owner_member_id"])
            if evidence.get("owner_member_id") is not None
            else None
        ),
        name=position.name,
        category=position.instrument_type,
        subcategory=(str(evidence["subcategory"]) if evidence.get("subcategory") else None),
        acquisition_cost=position.acquisition_cost,
        market_value=position.market_value,
        liquidity_days=position.liquidity_days,
        liquidity_level=_enum_value(
            LiquidityLevel,
            evidence.get("liquidity_level"),
            _liquidity_default(position.liquidity_days),
        ),
        risk_level=position.risk_level,
        purpose=str(evidence.get("purpose") or "精细资产持仓"),
        pledged=bool(evidence.get("pledged", False)),
        property_use=_enum_value(
            PropertyUse,
            evidence.get("property_use"),
            PropertyUse.NOT_PROPERTY,
        ),
        purpose_dimension=position.purpose_dimension,
        account_wrapper=_enum_value(
            AccountWrapper,
            evidence.get("account_wrapper"),
            account_wrapper,
        ),
        principal_loss_possible=position.principal_loss_possible,
        legally_principal_guaranteed=position.legally_principal_guaranteed,
        lock_up=position.lock_up,
        withdrawable_date=position.withdrawable_date,
        volatility=Decimal(str(evidence.get("volatility", "0"))),
        product_complexity=_enum_value(
            ComplexityLevel,
            evidence.get("product_complexity", evidence.get("complexity_level")),
            position.complexity_level,
        ),
        institution_type=str(evidence.get("institution_type") or "ordinary"),
        source_kind=position.source_kind,
        household_role=str(evidence.get("household_role") or "household_shared"),
        region_code=(str(evidence["region_code"]) if evidence.get("region_code") else None),
        valuation_date=position.valuation_date,
        version=int(legacy_version),
    )


def project_graph_to_household_facts(
    session: Session,
    household_id: str,
    graph: FinancialGraphRecords | None = None,
) -> HouseholdFacts:
    """Project canonical positions into the existing V4 facts contract.

    Non-asset facts intentionally remain on the legacy loader during E01. Planning,
    portfolio and twin continue to call that loader directly until later epics opt in.
    """

    legacy = load_household_facts(session, household_id)
    active_graph = graph or load_financial_graph(session, household_id)
    ordered_positions = sorted(
        active_graph.positions,
        key=lambda item: (
            str((item.evidence_json or {}).get("legacy_created_at") or item.created_at.isoformat()),
            item.legacy_asset_id or item.id,
        ),
    )
    assets = tuple(_asset_fact(item, active_graph) for item in ordered_positions)
    return replace(legacy, assets=assets)


def compare_legacy_projection(
    session: Session,
    household_id: str,
    graph: FinancialGraphRecords | None = None,
) -> ProjectionDiagnostic:
    legacy = load_household_facts(session, household_id)
    projected = project_graph_to_household_facts(session, household_id, graph)
    legacy_total = sum((item.market_value for item in legacy.assets), Decimal("0.00"))
    projected_total = sum((item.market_value for item in projected.assets), Decimal("0.00"))
    details: list[str] = []
    if len(legacy.assets) != len(projected.assets):
        details.append(
            f"资产记录数不一致：legacy={len(legacy.assets)}，graph={len(projected.assets)}"
        )
    legacy_by_id = {item.id: item for item in legacy.assets}
    for item in projected.assets:
        source = legacy_by_id.get(item.id)
        if source is not None and source.market_value != item.market_value:
            details.append(f"资产 {item.id} 的市值不一致")
    difference = abs(legacy_total - projected_total)
    if difference > Decimal("0.01"):
        details.append("资产总额差异超过 0.01 CNY")
    return ProjectionDiagnostic(
        status="matched" if not details else "mismatch",
        legacy_asset_total=legacy_total,
        projected_asset_total=projected_total,
        difference=difference,
        details=details,
    )
