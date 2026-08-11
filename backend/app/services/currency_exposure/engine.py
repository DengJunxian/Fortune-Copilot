from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import (
    AuditEventType,
    CFSComponentType,
    CurrencyExposureDirection,
    CurrencyExposureHorizon,
    CurrencyExposureType,
    LiabilityStreamType,
    ProfessionalSpecialistType,
    SpecializedComplexity,
)
from app.models.family import HouseholdMember
from app.models.family_enterprise import EnterpriseCashflow
from app.models.finance import Asset, FinancialGoal, IncomeSource, Liability
from app.models.liability import LiabilityStream
from app.models.specialized_cfs import CurrencyExposure
from app.models.wealth_graph import FinancialEntity, Position
from app.schemas.specialized_cfs import (
    CurrencyExposureOut,
    CurrencyExposureResponse,
    CurrencyExposureSummary,
    SpecializedResponseMeta,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.professional_routing.engine import resolve_professional_route
from app.services.specialized_cfs.common import (
    ZERO,
    annualize,
    canonical_hash,
    exposure_horizon,
    money,
)
from app.services.specialized_cfs.rules import load_specialized_cfs_rules

BOUNDARY = "本页只识别币种暴露和责任匹配需要，不提供法律、税务、外汇交易或跨境结构建议。"


def _member_entities(session: Session, household_id: str) -> dict[str, str]:
    members = list(
        session.scalars(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.is_deleted.is_(False),
            )
        ).all()
    )
    references = {f"legacy:member:{item.id}": item.id for item in members}
    entities = list(
        session.scalars(
            select(FinancialEntity).where(
                FinancialEntity.household_id == household_id,
                FinancialEntity.external_reference.in_(references),
                FinancialEntity.is_deleted.is_(False),
            )
        ).all()
    )
    return {
        references[item.external_reference]: item.id
        for item in entities
        if item.external_reference in references
    }


def _sync_exposures(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> tuple[str, list[CurrencyExposure]]:
    household = ensure_household(session, household_id)
    rules = load_specialized_cfs_rules(rules_path)
    base_currency = household.currency
    member_entities = _member_entities(session, household_id)
    buckets: dict[
        tuple[
            str | None,
            str,
            CurrencyExposureType,
            CurrencyExposureDirection,
            CurrencyExposureHorizon,
        ],
        dict[str, Any],
    ] = {}

    def add(
        *,
        entity_id: str | None,
        currency: str,
        exposure_type: CurrencyExposureType,
        amount: Decimal,
        direction: CurrencyExposureDirection,
        horizon: CurrencyExposureHorizon,
        source_id: str,
    ) -> None:
        if currency == base_currency or amount <= 0:
            return
        key = (entity_id, currency, exposure_type, direction, horizon)
        bucket = buckets.setdefault(key, {"amount": ZERO, "source_record_ids": []})
        bucket["amount"] = money(Decimal(bucket["amount"]) + amount)
        bucket["source_record_ids"].append(source_id)

    positions = list(
        session.scalars(
            select(Position).where(
                Position.household_id == household_id,
                Position.is_deleted.is_(False),
            )
        ).all()
    )
    projected_asset_ids = {item.legacy_asset_id for item in positions if item.legacy_asset_id}
    for position in positions:
        add(
            entity_id=position.owner_entity_id,
            currency=position.currency,
            exposure_type=CurrencyExposureType.ASSET_CURRENCY,
            amount=position.market_value,
            direction=CurrencyExposureDirection.INFLOW,
            horizon=CurrencyExposureHorizon.CURRENT,
            source_id=position.id,
        )
    for asset in session.scalars(
        select(Asset).where(
            Asset.household_id == household_id,
            Asset.is_deleted.is_(False),
        )
    ).all():
        if asset.id in projected_asset_ids:
            continue
        add(
            entity_id=member_entities.get(asset.owner_member_id or ""),
            currency=asset.currency,
            exposure_type=CurrencyExposureType.ASSET_CURRENCY,
            amount=asset.market_value,
            direction=CurrencyExposureDirection.INFLOW,
            horizon=CurrencyExposureHorizon.CURRENT,
            source_id=asset.id,
        )
    for income in session.scalars(
        select(IncomeSource).where(
            IncomeSource.household_id == household_id,
            IncomeSource.is_deleted.is_(False),
        )
    ).all():
        add(
            entity_id=member_entities.get(income.member_id or ""),
            currency=income.currency,
            exposure_type=CurrencyExposureType.INCOME_CURRENCY,
            amount=annualize(income.amount, income.frequency),
            direction=CurrencyExposureDirection.INFLOW,
            horizon=CurrencyExposureHorizon.CURRENT,
            source_id=income.id,
        )
    for liability in session.scalars(
        select(Liability).where(
            Liability.household_id == household_id,
            Liability.is_deleted.is_(False),
        )
    ).all():
        add(
            entity_id=member_entities.get(liability.borrower_member_id or ""),
            currency=liability.currency,
            exposure_type=CurrencyExposureType.LIABILITY_CURRENCY,
            amount=liability.outstanding_balance,
            direction=CurrencyExposureDirection.OUTFLOW,
            horizon=exposure_horizon(
                analysis_date,
                liability.maturity_date,
                short_term_days=rules.cross_border.short_term_days,
                medium_term_days=rules.cross_border.medium_term_days,
            ),
            source_id=liability.id,
        )
    streams = list(
        session.scalars(
            select(LiabilityStream).where(
                LiabilityStream.household_id == household_id,
                LiabilityStream.is_deleted.is_(False),
            )
        ).all()
    )
    linked_goal_ids = {item.source_goal_id for item in streams if item.source_goal_id}
    for stream in streams:
        add(
            entity_id=None,
            currency=stream.currency,
            exposure_type=(
                CurrencyExposureType.EDUCATION_LIABILITY
                if stream.stream_type == LiabilityStreamType.EDUCATION
                else CurrencyExposureType.FUTURE_OBLIGATION
            ),
            amount=stream.base_amount,
            direction=CurrencyExposureDirection.OUTFLOW,
            horizon=exposure_horizon(
                analysis_date,
                stream.start_date,
                short_term_days=rules.cross_border.short_term_days,
                medium_term_days=rules.cross_border.medium_term_days,
            ),
            source_id=stream.id,
        )
    for goal in session.scalars(
        select(FinancialGoal).where(
            FinancialGoal.household_id == household_id,
            FinancialGoal.is_deleted.is_(False),
        )
    ).all():
        if goal.id in linked_goal_ids:
            continue
        add(
            entity_id=None,
            currency=goal.currency,
            exposure_type=CurrencyExposureType.FUTURE_OBLIGATION,
            amount=goal.target_amount,
            direction=CurrencyExposureDirection.OUTFLOW,
            horizon=exposure_horizon(
                analysis_date,
                goal.target_date,
                short_term_days=rules.cross_border.short_term_days,
                medium_term_days=rules.cross_border.medium_term_days,
            ),
            source_id=goal.id,
        )
    for cashflow in session.scalars(
        select(EnterpriseCashflow).where(
            EnterpriseCashflow.household_id == household_id,
            EnterpriseCashflow.is_deleted.is_(False),
        )
    ).all():
        add(
            entity_id=None,
            currency=cashflow.currency,
            exposure_type=CurrencyExposureType.ENTERPRISE_REVENUE,
            amount=annualize(cashflow.amount, cashflow.frequency),
            direction=CurrencyExposureDirection.INFLOW,
            horizon=CurrencyExposureHorizon.CURRENT,
            source_id=cashflow.id,
        )

    existing = list(
        session.scalars(
            select(CurrencyExposure).where(CurrencyExposure.household_id == household_id)
        ).all()
    )
    by_key = {
        (
            item.entity_id,
            item.currency,
            item.exposure_type,
            item.direction,
            item.horizon,
        ): item
        for item in existing
    }
    active_ids: set[str] = set()
    for key, values in buckets.items():
        record = by_key.get(key)
        record_values = {
            "amount": money(values["amount"]),
            "source_record_ids": sorted(set(values["source_record_ids"])),
        }
        if record is None:
            entity_id, currency, exposure_type, direction, horizon = key
            record = CurrencyExposure(
                household_id=household_id,
                entity_id=entity_id,
                currency=currency,
                exposure_type=exposure_type,
                amount=record_values["amount"],
                direction=direction,
                horizon=horizon,
                source_record_ids=record_values["source_record_ids"],
                valuation_date=analysis_date,
                data_source="v5_currency_exposure_engine",
                is_user_confirmed=False,
            )
            session.add(record)
            session.flush()
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_CREATED,
                "识别外币暴露",
            )
        else:
            changed = any(getattr(record, name) != value for name, value in record_values.items())
            if changed or record.is_deleted:
                for name, value in record_values.items():
                    setattr(record, name, value)
                record.is_deleted = False
                record.deleted_at = None
                record.version += 1
                record.valuation_date = analysis_date
                add_audit_event(
                    session,
                    record,
                    actor,
                    AuditEventType.DATA_UPDATED,
                    "更新外币暴露",
                )
        active_ids.add(record.id)
    for record in existing:
        if record.id not in active_ids and not record.is_deleted:
            record.is_deleted = True
            record.version += 1
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_UPDATED,
                "外币暴露来源失效",
            )
    session.commit()
    records = list(
        session.scalars(
            select(CurrencyExposure)
            .where(
                CurrencyExposure.household_id == household_id,
                CurrencyExposure.is_deleted.is_(False),
            )
            .order_by(
                CurrencyExposure.currency,
                CurrencyExposure.exposure_type,
                CurrencyExposure.id,
            )
        ).all()
    )
    return base_currency, records


def get_currency_exposures(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> CurrencyExposureResponse:
    rules = load_specialized_cfs_rules(rules_path)
    base_currency, records = _sync_exposures(
        session,
        household_id,
        actor,
        rules_path,
        analysis_date,
    )
    inflow_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    outflow_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    source_ids: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.direction == CurrencyExposureDirection.INFLOW:
            inflow_totals[record.currency] = money(
                inflow_totals[record.currency] + record.amount
            )
        else:
            outflow_totals[record.currency] = money(
                outflow_totals[record.currency] + record.amount
            )
        source_ids[record.currency].update(record.source_record_ids)
    currencies = sorted(set(inflow_totals) | set(outflow_totals))
    summaries = [
        CurrencyExposureSummary(
            currency=currency,
            inflow=money(inflow_totals[currency]),
            outflow=money(outflow_totals[currency]),
            net_exposure=money(inflow_totals[currency] - outflow_totals[currency]),
            source_count=len(source_ids[currency]),
        )
        for currency in currencies
    ]
    material = any(
        max(item.inflow, item.outflow) >= rules.cross_border.material_amount
        for item in summaries
    ) or any(
        item.exposure_type
        in {CurrencyExposureType.EDUCATION_LIABILITY, CurrencyExposureType.ENTERPRISE_REVENUE}
        for item in records
    )
    complexity = (
        SpecializedComplexity.HIGH
        if material and (len(summaries) > 1 or any(item.outflow > 0 for item in summaries))
        else SpecializedComplexity.MEDIUM
        if material
        else SpecializedComplexity.LOW
        if records
        else SpecializedComplexity.NONE
    )
    route = resolve_professional_route(
        session,
        household_id,
        need="currency_matching",
        complexity=complexity,
        specialist_type=ProfessionalSpecialistType.CROSS_BORDER_SPECIALIST,
        component_types={CFSComponentType.CROSS_BORDER},
        reason=(
            "资产、收入和未来责任存在币种不一致，需要专业人员核对合规与执行边界。"
            if records
            else "当前已确认资料未识别到外币暴露；资料变化后再重新核对。"
        ),
    )
    input_hash = canonical_hash(
        {
            "records": [
                (
                    item.id,
                    item.version,
                    item.currency,
                    item.exposure_type.value,
                    str(item.amount),
                    item.direction.value,
                    item.horizon.value,
                )
                for item in records
            ],
            "rules": rules.formula_version,
            "analysis_date": analysis_date.isoformat(),
        }
    )
    return CurrencyExposureResponse(
        meta=SpecializedResponseMeta(
            household_id=household_id,
            analysis_date=analysis_date,
            data_as_of=max(
                (item.valuation_date for item in records if item.valuation_date),
                default=None,
            ),
            input_hash=input_hash,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
        ),
        base_currency=base_currency,
        material_exposure_detected=material,
        exposures=[CurrencyExposureOut.model_validate(item) for item in records],
        summaries=summaries,
        route=route,
        detection_notes=[
            "按资产、收入、负债、教育责任、企业收入和未来责任六类来源识别。",
            "不同币种金额不使用未经核验的实时汇率强行折算或汇总。",
        ],
        boundary=BOUNDARY,
    )
