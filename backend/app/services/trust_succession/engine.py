from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.domain.enums import (
    AuditEventType,
    CFSComponentType,
    ProfessionalReferralUrgency,
    ProfessionalSpecialistType,
    RiskLevel,
    SpecializedComplexity,
    TrustSuccessionNeedType,
    WealthNeedType,
)
from app.models.client_profile import WealthNeed
from app.models.family import HouseholdMember
from app.models.family_enterprise import EnterpriseOwnership, EnterpriseProfile
from app.models.finance import Asset, InsurancePolicy
from app.models.specialized_cfs import TrustSuccessionNeed
from app.schemas.specialized_cfs import (
    SpecializedResponseMeta,
    TrustSuccessionNeedOut,
    TrustSuccessionResponse,
)
from app.services.crud import add_audit_event, ensure_household
from app.services.professional_routing.engine import resolve_professional_route
from app.services.specialized_cfs.common import age_on, canonical_hash
from app.services.specialized_cfs.rules import load_specialized_cfs_rules

BOUNDARY = "系统只识别家庭安排的复杂度和资料缺口，不输出遗嘱、税务、信托设立或资产权属法律结论。"


def _sync_needs(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> list[TrustSuccessionNeed]:
    household = ensure_household(session, household_id)
    rules = load_specialized_cfs_rules(rules_path)
    members = list(
        session.scalars(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.is_deleted.is_(False),
            )
        ).all()
    )
    assets = list(
        session.scalars(
            select(Asset).where(
                Asset.household_id == household_id,
                Asset.is_deleted.is_(False),
            )
        ).all()
    )
    policies = list(
        session.scalars(
            select(InsurancePolicy).where(
                InsurancePolicy.household_id == household_id,
                InsurancePolicy.is_deleted.is_(False),
            )
        ).all()
    )
    enterprises = list(
        session.scalars(
            select(EnterpriseProfile).where(
                EnterpriseProfile.household_id == household_id,
                EnterpriseProfile.is_deleted.is_(False),
            )
        ).all()
    )
    ownership_count = int(
        session.scalar(
            select(func.count())
            .select_from(EnterpriseOwnership)
            .where(
                EnterpriseOwnership.household_id == household_id,
                EnterpriseOwnership.is_deleted.is_(False),
            )
        )
        or 0
    )
    wealth_needs = list(
        session.scalars(
            select(WealthNeed).where(
                WealthNeed.household_id == household_id,
                WealthNeed.need_type.in_([WealthNeedType.SUCCESSION, WealthNeedType.TRUST]),
                WealthNeed.is_deleted.is_(False),
            )
        ).all()
    )
    explicit_succession = any(item.need_type == WealthNeedType.SUCCESSION for item in wealth_needs)
    explicit_trust = any(item.need_type == WealthNeedType.TRUST for item in wealth_needs)
    beneficiaries = [
        {
            "member_id": item.id,
            "name": item.display_name,
            "relationship": item.relationship,
            "age": age_on(item.birth_date, analysis_date),
        }
        for item in members
    ]
    minors = [
        item
        for item in beneficiaries
        if isinstance(item["age"], int) and item["age"] < rules.trust_succession.minor_age
    ]
    special_care = [
        item
        for item in members
        if item.health_risk_level in {RiskLevel.MEDIUM_HIGH, RiskLevel.HIGH}
    ]
    assets_in_scope = [
        {
            "asset_id": item.id,
            "name": item.name,
            "category": item.category.value,
            "value": str(item.market_value),
            "currency": item.currency,
        }
        for item in assets
        if item.market_value >= rules.trust_succession.high_value_asset_threshold
        or item.category.value == "trust"
    ]
    enterprise_ids = [item.id for item in enterprises]
    relationships = {item.relationship for item in members}
    multi_generation = len(relationships) >= 3 or explicit_succession
    drafts: dict[TrustSuccessionNeedType, dict[str, Any]] = {}

    def add(
        need_type: TrustSuccessionNeedType,
        *,
        urgency: ProfessionalReferralUrgency,
        complexity: SpecializedComplexity,
        evidence: dict[str, Any],
    ) -> None:
        drafts[need_type] = {
            "need_type": need_type,
            "beneficiaries": beneficiaries,
            "assets_in_scope": assets_in_scope,
            "enterprise_in_scope": enterprise_ids,
            "urgency": urgency,
            "complexity": complexity,
            "professional_review_required": True,
            "evidence": evidence,
        }

    if minors:
        add(
            TrustSuccessionNeedType.MINOR_BENEFICIARY,
            urgency=ProfessionalReferralUrgency.HIGH,
            complexity=SpecializedComplexity.MEDIUM,
            evidence={"minor_member_ids": [str(item["member_id"]) for item in minors]},
        )
    if special_care:
        add(
            TrustSuccessionNeedType.SPECIAL_CARE,
            urgency=ProfessionalReferralUrgency.HIGH,
            complexity=SpecializedComplexity.HIGH,
            evidence={"member_ids": [item.id for item in special_care]},
        )
    if multi_generation:
        add(
            TrustSuccessionNeedType.MULTI_GENERATION,
            urgency=ProfessionalReferralUrgency.MEDIUM,
            complexity=SpecializedComplexity.MEDIUM,
            evidence={
                "relationships": sorted(relationships),
                "explicit_succession_need": explicit_succession,
                "beneficiary_details_complete": bool(len(members) >= 3),
            },
        )
    if enterprises and explicit_succession:
        add(
            TrustSuccessionNeedType.ENTERPRISE_SUCCESSION,
            urgency=ProfessionalReferralUrgency.HIGH,
            complexity=SpecializedComplexity.HIGH,
            evidence={"enterprise_ids": enterprise_ids},
        )
    if ownership_count >= rules.trust_succession.ownership_complexity_count or (
        explicit_trust and assets_in_scope
    ):
        add(
            TrustSuccessionNeedType.OWNERSHIP_COMPLEXITY,
            urgency=ProfessionalReferralUrgency.MEDIUM,
            complexity=SpecializedComplexity.HIGH,
            evidence={
                "ownership_record_count": ownership_count,
                "explicit_trust_need": explicit_trust,
            },
        )
    if policies and (bool(minors) or bool(special_care) or explicit_trust):
        add(
            TrustSuccessionNeedType.INSURANCE_TRUST_COORDINATION,
            urgency=ProfessionalReferralUrgency.MEDIUM,
            complexity=SpecializedComplexity.MEDIUM,
            evidence={"insurance_policy_ids": [item.id for item in policies]},
        )

    existing = list(
        session.scalars(
            select(TrustSuccessionNeed).where(
                TrustSuccessionNeed.household_id == household_id
            )
        ).all()
    )
    by_type = {item.need_type: item for item in existing}
    active_ids: set[str] = set()
    for need_type, values in drafts.items():
        record = by_type.get(need_type)
        if record is None:
            record = TrustSuccessionNeed(
                household_id=household_id,
                currency=household.currency,
                valuation_date=analysis_date,
                data_source="v5_trust_succession_engine",
                is_user_confirmed=False,
                **values,
            )
            session.add(record)
            session.flush()
            add_audit_event(
                session,
                record,
                actor,
                AuditEventType.DATA_CREATED,
                "识别信托与传承专业复核需要",
            )
        else:
            changed = any(getattr(record, name) != value for name, value in values.items())
            if changed or record.is_deleted:
                for name, value in values.items():
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
                    "更新信托与传承专业复核需要",
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
                "信托与传承触发条件已失效",
            )
    session.commit()
    return list(
        session.scalars(
            select(TrustSuccessionNeed)
            .where(
                TrustSuccessionNeed.household_id == household_id,
                TrustSuccessionNeed.is_deleted.is_(False),
            )
            .order_by(TrustSuccessionNeed.need_type)
        ).all()
    )


def get_trust_succession_needs(
    session: Session,
    household_id: str,
    actor: ActorContext,
    rules_path: str,
    analysis_date: date,
) -> TrustSuccessionResponse:
    rules = load_specialized_cfs_rules(rules_path)
    records = _sync_needs(session, household_id, actor, rules_path, analysis_date)
    routes = []
    for record in records:
        trust_route = record.need_type in {
            TrustSuccessionNeedType.MINOR_BENEFICIARY,
            TrustSuccessionNeedType.SPECIAL_CARE,
            TrustSuccessionNeedType.OWNERSHIP_COMPLEXITY,
            TrustSuccessionNeedType.INSURANCE_TRUST_COORDINATION,
        }
        routes.append(
            resolve_professional_route(
                session,
                household_id,
                need=record.need_type.value,
                complexity=record.complexity,
                specialist_type=(
                    ProfessionalSpecialistType.TRUST_SPECIALIST
                    if trust_route
                    else ProfessionalSpecialistType.LEGAL_TAX_PROFESSIONAL
                ),
                component_types=(
                    {CFSComponentType.TRUST, CFSComponentType.SUCCESSION}
                    if trust_route
                    else {CFSComponentType.SUCCESSION}
                ),
                reason="家庭受益人、资产或企业安排达到专业复核复杂度门。",
            )
        )
    input_hash = canonical_hash(
        {
            "records": [
                (item.id, item.version, item.need_type.value, item.complexity.value)
                for item in records
            ],
            "rules": rules.formula_version,
            "analysis_date": analysis_date.isoformat(),
        }
    )
    return TrustSuccessionResponse(
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
        need_detected=bool(records),
        outcome="EXPERT_REVIEW_REQUIRED" if records else "NO_NEED_DETECTED",
        needs=[TrustSuccessionNeedOut.model_validate(item) for item in records],
        routes=routes,
        boundary=BOUNDARY,
    )
