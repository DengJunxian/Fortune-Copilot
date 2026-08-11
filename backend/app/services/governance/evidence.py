from __future__ import annotations

import copy
import hashlib
import json
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.enums import CFSSolutionStatus
from app.models.cfs import (
    CFSSolution,
    CFSSolutionComponent,
    ProfessionalServiceReferral,
)
from app.models.client_profile import ClientWealthProfile, WealthNeed
from app.models.family_enterprise import (
    EnterpriseGuarantee,
    EnterpriseProfile,
    EnterpriseValuation,
)
from app.models.financial_twin import HouseholdSnapshot
from app.models.governance import Product
from app.models.liability import LiabilityStream
from app.models.wealth_graph import OwnershipEdge, Position
from app.schemas.calibration import CalibrationCatalogResponse
from app.schemas.decision_evidence_v2 import (
    EVIDENCE_SECTION_NAMES,
    DecisionEvidenceSearchFields,
    DecisionEvidenceSection,
    DecisionEvidenceV2,
)
from app.services.calibration.registry import build_calibration_catalog
from app.services.product_ontology.adapter import ensure_verified_fund_ontology

EVIDENCE_VERSION = "decision-evidence-v2.0.0"
EXCLUDED_HASH_KEYS = {
    "generated_at",
    "request_id",
    "requestId",
    "display_only_text",
    "display_text",
    "display_label",
    "label",
    "title",
    "explanation",
    "rationale",
}


def _value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _json_hash(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _clean_hash_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _clean_hash_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in EXCLUDED_HASH_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_clean_hash_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def decision_hash_material(payload: DecisionEvidenceV2 | dict[str, Any]) -> dict[str, Any]:
    raw = payload.model_dump(mode="json") if isinstance(payload, DecisionEvidenceV2) else payload
    material: dict[str, Any] = {
        "evidence_version": raw["evidence_version"],
        "decision_type": raw["decision_type"],
        "household_id": raw["household_id"],
        "calculation_source": raw.get("calculation_source", "deterministic_evidence_v2"),
    }
    for name in EVIDENCE_SECTION_NAMES:
        section = raw[name]
        material[name] = {
            "status": section["status"],
            "version": section["version"],
            "decision_inputs": section.get("decision_inputs", {}),
        }
    return _clean_hash_value(material)  # type: ignore[return-value]


def calculate_decision_hash(payload: DecisionEvidenceV2 | dict[str, Any]) -> str:
    return _json_hash(decision_hash_material(payload))


def seal_decision_evidence(payload: dict[str, Any]) -> DecisionEvidenceV2:
    candidate = {**payload, "decision_hash": "0" * 64}
    candidate["decision_hash"] = calculate_decision_hash(candidate)
    return DecisionEvidenceV2.model_validate(candidate)


def _section(
    status: str,
    version: str,
    *,
    decision_inputs: dict[str, Any] | None = None,
    snapshot: object = None,
    source_record_ids: list[str] | None = None,
    display_only_text: str | None = None,
) -> dict[str, Any]:
    return DecisionEvidenceSection(
        status=status,
        version=version,
        decision_inputs=decision_inputs or {},
        snapshot={} if snapshot is None else snapshot,
        source_record_ids=source_record_ids or [],
        display_only_text=display_only_text,
    ).model_dump(mode="json")


def calibration_evidence_section(
    catalog: CalibrationCatalogResponse | None,
) -> dict[str, Any]:
    if catalog is None:
        return _section(
            "not_applicable",
            "calibration-v1-not-enabled",
            display_only_text="E13 校准功能未启用；不得将现有规则表述为经验校准或银行授权。",
        )
    mode_inputs = [
        {
            "mode": item.mode.value,
            "available": item.available,
            "dataset_count": item.dataset_count,
            "parameter_count": item.parameter_count,
        }
        for item in catalog.modes
    ]
    dataset_inputs = [
        {
            "code": item.code,
            "mode": item.mode.value,
            "version": item.version,
            "effective_date": item.effective_date.isoformat(),
            "data_quality": item.data_quality,
            "parameter_count": item.parameter_count,
        }
        for item in catalog.datasets
    ]
    return _section(
        "bound",
        catalog.registry_version,
        decision_inputs={
            "registry_version": catalog.registry_version,
            "modes": mode_inputs,
            "datasets": dataset_inputs,
            "no_silent_guessing": True,
        },
        snapshot={
            "datasets": [
                {
                    "code": item.code,
                    "source": item.source,
                    "source_reference": item.source_reference,
                    "population": item.population,
                    "sample_period": item.sample_period,
                    "license_or_access_note": item.license_or_access_note,
                    "limitations": item.limitations,
                }
                for item in catalog.datasets
            ]
        },
        source_record_ids=[item.id for item in catalog.datasets],
        display_only_text=(
            "受控演示、经验校准与银行授权模式分开冻结；当前不可用模式不会静默回退或改名。"
        ),
    )


def _calibration_section(session: Session, settings: Settings) -> dict[str, Any]:
    catalog = (
        build_calibration_catalog(session, settings.calibration_registry_path)
        if settings.enable_v5_calibration
        else None
    )
    return calibration_evidence_section(catalog)


def _latest_profile(session: Session, household_id: str) -> ClientWealthProfile | None:
    return session.scalar(
        select(ClientWealthProfile)
        .where(
            ClientWealthProfile.household_id == household_id,
            ClientWealthProfile.is_deleted.is_(False),
        )
        .order_by(
            ClientWealthProfile.profile_version.desc(),
            ClientWealthProfile.created_at.desc(),
        )
    )


def _latest_twin(session: Session, household_id: str) -> HouseholdSnapshot | None:
    return session.scalar(
        select(HouseholdSnapshot)
        .where(
            HouseholdSnapshot.household_id == household_id,
            HouseholdSnapshot.is_deleted.is_(False),
        )
        .order_by(HouseholdSnapshot.event_cursor.desc(), HouseholdSnapshot.created_at.desc())
    )


def _latest_cfs(session: Session, household_id: str) -> CFSSolution | None:
    return session.scalar(
        select(CFSSolution)
        .where(
            CFSSolution.household_id == household_id,
            CFSSolution.status.in_([CFSSolutionStatus.ACTIVE, CFSSolutionStatus.NEEDS_REVIEW]),
            CFSSolution.is_deleted.is_(False),
        )
        .order_by(CFSSolution.solution_version.desc(), CFSSolution.created_at.desc())
    )


def _financial_graph_section(session: Session, household_id: str) -> dict[str, Any]:
    positions = list(
        session.scalars(
            select(Position)
            .where(Position.household_id == household_id, Position.is_deleted.is_(False))
            .order_by(Position.id)
        ).all()
    )
    edges = list(
        session.scalars(
            select(OwnershipEdge)
            .where(
                OwnershipEdge.household_id == household_id,
                OwnershipEdge.is_deleted.is_(False),
            )
            .order_by(OwnershipEdge.id)
        ).all()
    )
    decision_inputs = {
        "positions": [
            {
                "id": item.id,
                "market_value": str(item.market_value),
                "purpose_dimension": _value(item.purpose_dimension),
                "risk_level": _value(item.risk_level),
                "liquidity_days": item.liquidity_days,
                "principal_loss_possible": item.principal_loss_possible,
                "lock_up": item.lock_up,
            }
            for item in positions
        ],
        "ownership_edges": [
            {
                "id": item.id,
                "owner_entity_id": item.owner_entity_id,
                "owned_entity_id": item.owned_entity_id,
                "ownership_type": _value(item.ownership_type),
                "ownership_ratio": str(item.ownership_ratio)
                if item.ownership_ratio is not None
                else None,
            }
            for item in edges
        ],
    }
    if not positions and not edges:
        return _section("not_available", "financial-graph-not-materialized")
    version = f"financial-graph:{_json_hash(decision_inputs)}"
    return _section(
        "bound",
        version,
        decision_inputs=decision_inputs,
        snapshot={"position_count": len(positions), "ownership_edge_count": len(edges)},
        source_record_ids=[item.id for item in positions] + [item.id for item in edges],
    )


def _profile_and_needs_sections(
    session: Session,
    household_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _latest_profile(session, household_id)
    if profile is None:
        unavailable = _section("not_available", "client-profile-not-materialized")
        return unavailable, _section("not_available", "wealth-needs-not-materialized")
    profile_inputs = {
        "profile_id": profile.id,
        "profile_version": profile.profile_version,
        "profile_hash": profile.profile_hash,
        "lifecycle_stage": _value(profile.lifecycle_stage),
        "wealth_tier": _value(profile.wealth_tier),
        "service_complexity": _value(profile.service_complexity),
        "risk_capacity": _value(profile.risk_capacity),
        "risk_willingness": _value(profile.risk_willingness),
        "behavior_limit": _value(profile.behavior_limit),
        "enterprise_dependency_level": _value(profile.enterprise_dependency_level),
        "cross_border_complexity": _value(profile.cross_border_complexity),
        "succession_complexity": _value(profile.succession_complexity),
        "pension_stage": _value(profile.pension_stage),
        "completeness_score": str(profile.completeness_score),
        "status": _value(profile.status),
    }
    needs = list(
        session.scalars(
            select(WealthNeed)
            .where(
                WealthNeed.household_id == household_id,
                WealthNeed.profile_id == profile.id,
                WealthNeed.is_deleted.is_(False),
            )
            .order_by(WealthNeed.priority, WealthNeed.id)
        ).all()
    )
    need_inputs = [
        {
            "id": item.id,
            "record_version": item.version,
            "need_type": _value(item.need_type),
            "target_amount": str(item.target_amount),
            "minimum_amount": str(item.minimum_amount),
            "start_date": item.start_date.isoformat(),
            "end_date": item.end_date.isoformat() if item.end_date else None,
            "rigidity": _value(item.rigidity),
            "priority": item.priority,
            "status": _value(item.status),
            "professional_review_required": item.professional_review_required,
        }
        for item in needs
    ]
    need_hash = _json_hash(need_inputs)
    return (
        _section(
            "bound",
            f"client-profile-v{profile.profile_version}:{profile.profile_hash}",
            decision_inputs=profile_inputs,
            snapshot={"data_gaps": profile.data_gaps, "explanation": profile.explanation},
            source_record_ids=[profile.id],
        ),
        _section(
            "bound" if needs else "not_available",
            f"wealth-need-set:{need_hash}" if needs else "wealth-needs-empty",
            decision_inputs={"need_set_hash": need_hash, "needs": need_inputs} if needs else {},
            snapshot={"need_count": len(needs)},
            source_record_ids=[item.id for item in needs],
        ),
    )


def _liability_section(session: Session, household_id: str) -> dict[str, Any]:
    streams = list(
        session.scalars(
            select(LiabilityStream)
            .where(
                LiabilityStream.household_id == household_id,
                LiabilityStream.is_deleted.is_(False),
            )
            .order_by(LiabilityStream.start_date, LiabilityStream.id)
        ).all()
    )
    inputs = [
        {
            "id": item.id,
            "stream_version": item.stream_version,
            "stream_type": _value(item.stream_type),
            "start_date": item.start_date.isoformat(),
            "end_date": item.end_date.isoformat() if item.end_date else None,
            "frequency": _value(item.frequency),
            "base_amount": str(item.base_amount),
            "minimum_amount": str(item.minimum_amount),
            "annual_growth_assumption": str(item.annual_growth_assumption),
            "rigidity": _value(item.rigidity),
            "deferrable": item.deferrable,
        }
        for item in streams
    ]
    if not inputs:
        return _section("not_available", "liability-streams-not-materialized")
    version = f"liability-set:{_json_hash(inputs)}"
    return _section(
        "bound",
        version,
        decision_inputs={"streams": inputs},
        snapshot={"stream_count": len(streams)},
        source_record_ids=[item.id for item in streams],
    )


def _enterprise_section(session: Session, household_id: str) -> dict[str, Any]:
    profiles = list(
        session.scalars(
            select(EnterpriseProfile)
            .where(
                EnterpriseProfile.household_id == household_id,
                EnterpriseProfile.is_deleted.is_(False),
            )
            .order_by(EnterpriseProfile.id)
        ).all()
    )
    valuations = list(
        session.scalars(
            select(EnterpriseValuation)
            .where(
                EnterpriseValuation.household_id == household_id,
                EnterpriseValuation.is_deleted.is_(False),
            )
            .order_by(EnterpriseValuation.enterprise_id, EnterpriseValuation.valuation_date)
        ).all()
    )
    guarantees = list(
        session.scalars(
            select(EnterpriseGuarantee)
            .where(
                EnterpriseGuarantee.household_id == household_id,
                EnterpriseGuarantee.is_deleted.is_(False),
            )
            .order_by(EnterpriseGuarantee.enterprise_id, EnterpriseGuarantee.id)
        ).all()
    )
    inputs = {
        "profiles": [
            {
                "id": item.id,
                "stage": _value(item.stage),
                "jurisdiction": item.jurisdiction,
                "listed_status": _value(item.listed_status),
                "enterprise_type": _value(item.enterprise_type),
            }
            for item in profiles
        ],
        "valuations": [
            {
                "id": item.id,
                "enterprise_id": item.enterprise_id,
                "valuation_date": (
                    item.valuation_date.isoformat() if item.valuation_date else None
                ),
                "equity_value": str(item.equity_value),
                "valuation_method": _value(item.valuation_method),
                "confidence": _value(item.confidence),
            }
            for item in valuations
        ],
        "guarantees": [
            {
                "id": item.id,
                "enterprise_id": item.enterprise_id,
                "guarantee_type": _value(item.guarantee_type),
                "guaranteed_amount": str(item.guaranteed_amount),
                "outstanding_exposure": str(item.outstanding_exposure),
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
            }
            for item in guarantees
        ],
    }
    record_ids = [item.id for item in profiles + valuations + guarantees]
    if not record_ids:
        return _section("not_available", "enterprise-snapshot-not-materialized")
    version = f"enterprise-snapshot:{_json_hash(inputs)}"
    return _section(
        "bound",
        version,
        decision_inputs=inputs,
        snapshot={
            "enterprise_count": len(profiles),
            "valuation_count": len(valuations),
            "guarantee_count": len(guarantees),
        },
        source_record_ids=record_ids,
    )


def _cfs_context(
    session: Session,
    household_id: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    solution = _latest_cfs(session, household_id)
    if solution is None:
        return (
            _section("not_available", "cfs-solution-not-composed"),
            {
                "cfs_solution_id": None,
                "cfs_version": None,
                "selected_components": [],
                "professional_referrals": [],
            },
        )
    components = list(
        session.scalars(
            select(CFSSolutionComponent)
            .where(
                CFSSolutionComponent.solution_id == solution.id,
                CFSSolutionComponent.is_deleted.is_(False),
            )
            .order_by(CFSSolutionComponent.priority, CFSSolutionComponent.id)
        ).all()
    )
    referrals = list(
        session.scalars(
            select(ProfessionalServiceReferral)
            .where(
                ProfessionalServiceReferral.solution_id == solution.id,
                ProfessionalServiceReferral.is_deleted.is_(False),
            )
            .order_by(ProfessionalServiceReferral.id)
        ).all()
    )
    selected_components = [
        {
            "component_id": item.id,
            "wealth_need_id": item.wealth_need_id,
            "component_type": _value(item.component_type),
            "priority": item.priority,
            "target_amount": str(item.target_amount),
            "minimum_amount": str(item.minimum_amount),
            "time_horizon": _value(item.time_horizon),
            "product_mapping_allowed": item.product_mapping_allowed,
            "professional_review_required": item.professional_review_required,
            "required_specialist": _value(item.required_specialist),
            "status": _value(item.status),
        }
        for item in components
    ]
    professional_referrals = [
        {
            "referral_id": item.id,
            "component_id": item.component_id,
            "specialist_type": _value(item.specialist_type),
            "urgency": _value(item.urgency),
            "status": _value(item.status),
            "due_date": item.due_date.isoformat() if item.due_date else None,
        }
        for item in referrals
    ]
    inputs = {
        "solution_id": solution.id,
        "solution_version": solution.solution_version,
        "status": _value(solution.status),
        "need_set_hash": solution.need_set_hash,
        "risk_budget_version": solution.risk_budget_version,
        "methodology_version": solution.methodology_version,
        "decision_hash": solution.decision_hash,
        "selected_components": selected_components,
        "professional_referrals": professional_referrals,
    }
    return (
        _section(
            "bound",
            f"cfs-v{solution.solution_version}:{solution.decision_hash}",
            decision_inputs=inputs,
            snapshot={"summary": solution.summary},
            source_record_ids=[solution.id]
            + [item.id for item in components]
            + [item.id for item in referrals],
        ),
        {
            "cfs_solution_id": solution.id,
            "cfs_version": solution.solution_version,
            "selected_components": selected_components,
            "professional_referrals": professional_referrals,
        },
    )


def _product_section(session: Session, settings: Settings) -> dict[str, Any]:
    catalog, products, snapshots = ensure_verified_fund_ontology(
        session, settings.fund_advisory_catalog_path
    )
    products_by_id: dict[str, Product] = {item.id: item for item in products}
    snapshot_inputs = [
        {
            "snapshot_id": item.id,
            "snapshot_version": item.snapshot_version,
            "snapshot_hash": item.snapshot_hash,
            "product_id": item.product_id,
            "product_code": products_by_id[item.product_id].code,
            "risk_level": _value(item.risk_level),
            "sale_status": item.sale_status,
            "as_of_date": item.as_of_date.isoformat(),
        }
        for item in sorted(snapshots, key=lambda record: products_by_id[record.product_id].code)
    ]
    return _section(
        "bound",
        f"{catalog.catalog_code}@{catalog.catalog_version}:{_json_hash(snapshot_inputs)}",
        decision_inputs={
            "catalog_version": catalog.catalog_version,
            "catalog_verified_on": catalog.verified_on.isoformat(),
            "snapshots": snapshot_inputs,
        },
        snapshot={
            "products": [
                {
                    "product_id": item.product_id,
                    "fee_snapshot": item.fee_snapshot,
                    "liquidity_snapshot": item.liquidity_snapshot,
                    "terms_snapshot": item.terms_snapshot,
                    "channel": item.channel,
                    "source_reference": item.source_reference,
                    "evidence": item.evidence,
                }
                for item in snapshots
            ]
        },
        source_record_ids=[item.id for item in snapshots],
        display_only_text="产品名称与界面解释不进入哈希；产品快照版本和决策属性进入哈希。",
    )


def _initial_suitability(recommendation_snapshot: dict[str, object]) -> dict[str, Any]:
    candidates_raw = recommendation_snapshot.get("candidates", [])
    candidates = candidates_raw if isinstance(candidates_raw, list) else []
    candidate_inputs = [
        {
            "candidate_type": item.get("candidate_type"),
            "decision": item.get("decision"),
            "gates": item.get("gates", []),
        }
        for item in candidates
        if isinstance(item, dict)
    ]
    if not candidate_inputs:
        return _section("not_available", "suitability-not-calculated")
    return _section(
        "bound",
        f"suitability:{_json_hash(candidate_inputs)}",
        decision_inputs={"candidates": candidate_inputs},
        snapshot={"candidate_count": len(candidate_inputs)},
    )


def build_workflow_decision_evidence(
    session: Session,
    *,
    household_id: str,
    workflow_id: str,
    recommendation_snapshot: dict[str, object],
    settings: Settings,
    generated_at: object,
) -> tuple[DecisionEvidenceV2, dict[str, object]]:
    meta_raw = recommendation_snapshot.get("meta", {})
    meta = meta_raw if isinstance(meta_raw, dict) else {}
    twin = _latest_twin(session, household_id)
    profile_section, needs_section = _profile_and_needs_sections(session, household_id)
    liability_section = _liability_section(session, household_id)
    enterprise_section = _enterprise_section(session, household_id)
    cfs_section, cfs_snapshot = _cfs_context(session, household_id)
    context_raw = recommendation_snapshot.get("context", {})
    context = context_raw if isinstance(context_raw, dict) else {}
    cfs_inputs = cfs_section.get("decision_inputs", {})
    cfs_summary = cfs_section.get("snapshot", {})
    cfs_summary_value = cfs_summary.get("summary", {}) if isinstance(cfs_summary, dict) else {}
    risk_budget = (
        cfs_summary_value.get("risk_budget", {}) if isinstance(cfs_summary_value, dict) else {}
    )
    eltc_inputs = {
        "eligible_long_term_amount": context.get("eligible_long_term_amount", "0"),
        "annual_new_surplus": context.get("annual_new_surplus", "0"),
        "input_version": meta.get("input_version", "not_available"),
    }
    candidates_raw = recommendation_snapshot.get("candidates", [])
    candidates = candidates_raw if isinstance(candidates_raw, list) else []
    risk_inputs = {
        "risk_budget_version": cfs_inputs.get("risk_budget_version", "not_available")
        if isinstance(cfs_inputs, dict)
        else "not_available",
        "risk_budget": risk_budget,
        "candidate_decisions": [
            {
                "candidate_type": item.get("candidate_type"),
                "decision": item.get("decision"),
            }
            for item in candidates
            if isinstance(item, dict)
        ],
    }
    payload: dict[str, Any] = {
        "evidence_version": EVIDENCE_VERSION,
        "decision_id": workflow_id,
        "decision_type": "plan_workflow",
        "household_id": household_id,
        "household_input": _section(
            "bound",
            str(meta.get("input_version", "workflow-input-pending")),
            decision_inputs={
                "input_version": meta.get("input_version", "not_available"),
                "analysis_date": meta.get("analysis_date"),
                "twin_snapshot_version": twin.snapshot_hash if twin else None,
                "monitoring_trigger_id": None,
            },
            snapshot={
                "data_as_of": meta.get("data_as_of"),
                "source_snapshot_id": twin.id if twin else None,
            },
            source_record_ids=[twin.id] if twin else [],
        ),
        "financial_graph": _financial_graph_section(session, household_id),
        "client_profile": profile_section,
        "wealth_needs": needs_section,
        "liability": liability_section,
        "ELTC": _section(
            "bound",
            f"eltc:{_json_hash(eltc_inputs)}",
            decision_inputs=eltc_inputs,
            snapshot=context,
        ),
        "risk_budget": _section(
            "bound",
            f"risk-budget:{_json_hash(risk_inputs)}",
            decision_inputs=risk_inputs,
            snapshot=risk_budget,
        ),
        "enterprise": enterprise_section,
        "CFS": cfs_section,
        "product_snapshot": _product_section(session, settings),
        "suitability": _initial_suitability(recommendation_snapshot),
        "calibration": _calibration_section(session, settings),
        "advisor": _section("not_available", "advisor-review-pending"),
        "client_confirmation": _section("not_available", "client-confirmation-pending"),
        "generated_at": generated_at,
        "calculation_source": "deterministic_evidence_v2",
    }
    return seal_decision_evidence(payload), cfs_snapshot


def refresh_workflow_decision_evidence(
    evidence: dict[str, Any],
    *,
    selected_candidate: object,
    recommendation_snapshot: dict[str, Any],
    suitability_snapshot: dict[str, Any],
    communication_draft: str,
    advisor_decision: object,
    compliance_decision: object,
    customer_confirmation: dict[str, Any],
    generated_at: object,
) -> DecisionEvidenceV2:
    payload = copy.deepcopy(evidence)
    payload["generated_at"] = generated_at
    suitability_inputs = {
        "selected_candidate": selected_candidate,
        "candidate_gate_evidence": suitability_snapshot.get("candidate_gate_evidence", {}),
        "compliance_decision": compliance_decision,
        "compliance_evidence": suitability_snapshot.get("compliance_evidence", {}),
    }
    payload["suitability"] = _section(
        "bound",
        f"suitability:{_json_hash(suitability_inputs)}",
        decision_inputs=suitability_inputs,
        snapshot=suitability_snapshot,
    )
    manual_raw = recommendation_snapshot.get("advisor_modification", {})
    manual = manual_raw if isinstance(manual_raw, dict) else {}
    advisor_inputs = {
        "selected_candidate": selected_candidate,
        "advisor_decision": advisor_decision,
        "manual_high_risk_confirmed": manual.get("manual_high_risk_confirmed", False),
        "execution_mode": manual.get("execution_mode"),
        "communication_hash": _json_hash(communication_draft),
    }
    advisor_status = "bound" if advisor_decision or selected_candidate else "not_available"
    payload["advisor"] = _section(
        advisor_status,
        (
            f"advisor:{_json_hash(advisor_inputs)}"
            if advisor_status == "bound"
            else "advisor-review-pending"
        ),
        decision_inputs=advisor_inputs if advisor_status == "bound" else {},
        snapshot={"advisor_modification": manual},
        display_only_text="沟通稿原文只作展示；其内容哈希进入决策哈希。",
    )
    confirmation_inputs = {
        key: value
        for key, value in customer_confirmation.items()
        if key not in {"confirmed_at", "display_only_text"}
    }
    confirmation_status = "bound" if confirmation_inputs else "not_available"
    payload["client_confirmation"] = _section(
        confirmation_status,
        (
            f"client-confirmation:{_json_hash(confirmation_inputs)}"
            if confirmation_status == "bound"
            else "client-confirmation-pending"
        ),
        decision_inputs=confirmation_inputs,
        snapshot=customer_confirmation,
    )
    return seal_decision_evidence(payload)


def searchable_fields(evidence: DecisionEvidenceV2) -> DecisionEvidenceSearchFields:
    household_inputs = evidence.household_input.decision_inputs
    need_inputs = evidence.wealth_needs.decision_inputs
    cfs_inputs = evidence.CFS.decision_inputs
    return DecisionEvidenceSearchFields(
        client_profile_version=(
            evidence.client_profile.version if evidence.client_profile.status == "bound" else None
        ),
        wealth_need_set_hash=need_inputs.get("need_set_hash"),
        liability_version=(
            evidence.liability.version if evidence.liability.status == "bound" else None
        ),
        twin_snapshot_version=household_inputs.get("twin_snapshot_version"),
        enterprise_snapshot_version=(
            evidence.enterprise.version if evidence.enterprise.status == "bound" else None
        ),
        cfs_solution_id=cfs_inputs.get("solution_id"),
        calibration_version=(
            evidence.calibration.version
            if evidence.calibration.status in {"bound", "not_applicable"}
            else None
        ),
        monitoring_trigger_id=household_inputs.get("monitoring_trigger_id"),
    )


def rebind_decision_evidence(
    evidence: DecisionEvidenceV2 | dict[str, Any],
    *,
    decision_id: str,
    decision_type: str,
    generated_at: object,
) -> DecisionEvidenceV2:
    payload = (
        evidence.model_dump(mode="json")
        if isinstance(evidence, DecisionEvidenceV2)
        else copy.deepcopy(evidence)
    )
    payload["decision_id"] = decision_id
    payload["decision_type"] = decision_type
    payload["generated_at"] = generated_at
    return seal_decision_evidence(payload)


def minimal_v2_from_legacy(
    *,
    decision_id: str,
    decision_type: str,
    household_id: str,
    legacy: dict[str, Any],
    generated_at: object,
    suitability: dict[str, Any] | None = None,
    calibration: CalibrationCatalogResponse | None = None,
) -> DecisionEvidenceV2:
    def not_bound(name: str) -> dict[str, Any]:
        return _section("not_available", f"{name}-not-bound")

    product_version = str(legacy.get("product_snapshot_version", "not_available"))
    risk_inputs = {
        "risk_assessment_version": legacy.get("risk_assessment_version"),
        "behavior_assessment_version": legacy.get("behavior_assessment_version"),
    }
    payload = {
        "evidence_version": EVIDENCE_VERSION,
        "decision_id": decision_id,
        "decision_type": decision_type,
        "household_id": household_id,
        "household_input": _section(
            "bound",
            str(legacy.get("household_input_version", "legacy-input")),
            decision_inputs={
                "input_version": legacy.get("household_input_version"),
                "financial_rule_version": legacy.get("financial_rule_version"),
                "planning_rule_version": legacy.get("planning_rule_version"),
                "methodology_version": legacy.get("methodology_version"),
            },
        ),
        "financial_graph": not_bound("financial-graph"),
        "client_profile": not_bound("client-profile"),
        "wealth_needs": not_bound("wealth-needs"),
        "liability": not_bound("liability"),
        "ELTC": not_bound("eltc"),
        "risk_budget": _section(
            "bound",
            f"legacy-risk:{_json_hash(risk_inputs)}",
            decision_inputs=risk_inputs,
        ),
        "enterprise": not_bound("enterprise"),
        "CFS": not_bound("cfs"),
        "product_snapshot": _section(
            "bound",
            product_version,
            decision_inputs={"product_snapshot_version": product_version},
        ),
        "suitability": _section(
            "bound",
            f"legacy-suitability:{_json_hash(suitability or legacy.get('hard_gate_results', {}))}",
            decision_inputs=suitability or legacy.get("hard_gate_results", {}),
        ),
        "calibration": calibration_evidence_section(calibration),
        "advisor": _section("not_available", "advisor-review-pending"),
        "client_confirmation": _section("not_available", "client-confirmation-pending"),
        "generated_at": generated_at,
        "calculation_source": "deterministic_evidence_v2",
    }
    return seal_decision_evidence(payload)
