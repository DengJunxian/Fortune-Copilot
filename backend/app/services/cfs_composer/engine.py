from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.errors import AppError
from app.domain.enums import (
    AuditEventType,
    CFSComponentStatus,
    CFSComponentType,
    CFSSolutionStatus,
    CFSTimeHorizon,
    ComplexityBand,
    PensionStage,
    ProfessionalReferralStatus,
    ProfessionalReferralUrgency,
    ProfessionalSpecialistType,
    WealthNeedStatus,
    WealthNeedType,
)
from app.models.cfs import CFSSolution, CFSSolutionComponent, ProfessionalServiceReferral
from app.models.common import utc_now
from app.schemas.cfs import (
    CFSComponentOut,
    CFSComposeRequest,
    CFSResponseMeta,
    CFSSolutionOut,
    CFSSolutionResponse,
    HouseholdRiskBudget,
    ProfessionalReferralCreate,
    ProfessionalReferralOut,
)
from app.schemas.client_profile import WealthNeedOut
from app.services.client_profile.engine import get_client_profile
from app.services.crud import add_audit_event, ensure_household
from app.services.eligible_capital.engine import calculate_household_eligible_capital
from app.services.family_enterprise.engine import get_family_enterprise_view
from app.services.financial.engine import analyze_facts
from app.services.financial.facts import load_household_facts
from app.services.financial.rules import load_financial_rules
from app.services.financial.utils import ZERO, money
from app.services.financial_twin.engine import materialize_current_twin
from app.services.liability_engine.engine import materialize_liability_streams
from app.services.methodology.rules import load_methodology_rules
from app.services.planning.engine import empty_counterfactual, plan_facts
from app.services.planning.rules import load_planning_rules
from app.services.protection_planner.engine import build_protection_plan
from app.services.public_data.rules import load_public_data_snapshot
from app.services.risk_budget.engine import build_household_risk_budget
from app.services.wealth_needs.engine import get_wealth_needs
from app.services.wealth_orchestrator.engine import orchestrate_cfs_components

from .rules import CFSComposerRules, CFSNeedPolicy, ensure_cfs_rule_version, load_cfs_rules


@dataclass(frozen=True, slots=True)
class ComponentDraft:
    wealth_need_id: str | None
    component_type: CFSComponentType
    priority: int
    target_amount: Decimal
    minimum_amount: Decimal
    time_horizon: CFSTimeHorizon
    recommended_action: str
    product_mapping_allowed: bool
    professional_review_required: bool
    required_specialist: ProfessionalSpecialistType | None
    status: CFSComponentStatus
    rationale: str
    evidence: dict[str, object]


def _hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _prepared_amount(need: WealthNeedOut) -> Decimal:
    try:
        return max(ZERO, Decimal(str(need.evidence.get("prepared_amount", "0"))))
    except InvalidOperation:
        return ZERO


def _horizon(need: WealthNeedOut, analysis_date: date) -> CFSTimeHorizon:
    if need.end_date is None:
        return CFSTimeHorizon.ONGOING
    days = max(0, (need.end_date - analysis_date).days)
    if days <= 90:
        return CFSTimeHorizon.IMMEDIATE
    if days <= 1095:
        return CFSTimeHorizon.SHORT_TERM
    if days <= 2555:
        return CFSTimeHorizon.MEDIUM_TERM
    return CFSTimeHorizon.LONG_TERM


def _requires_professional_review(
    need: WealthNeedOut,
    policy: CFSNeedPolicy,
    profile_pension_stage: PensionStage,
) -> bool:
    if need.professional_review_required:
        return True
    if policy.component_type == CFSComponentType.PROTECTION:
        return need.status != WealthNeedStatus.PREPARED
    if policy.component_type == CFSComponentType.RETIREMENT:
        return profile_pension_stage in {PensionStage.TRANSITION, PensionStage.RETIREMENT}
    return False


def _no_action_reason(risk_budget: HouseholdRiskBudget) -> str:
    if risk_budget.constraints:
        return risk_budget.constraints[0]
    return "当前没有通过前置责任与风险预算门，不新增投资。"


def _component_drafts(
    needs: list[WealthNeedOut],
    rules: CFSComposerRules,
    risk_budget: HouseholdRiskBudget,
    *,
    eligible_capital: Decimal,
    family_enterprise_wealth: Decimal,
    family_guarantee_exposure: Decimal,
    family_dependency_level: ComplexityBand,
    profile_pension_stage: PensionStage,
    protection_gap: Decimal,
    planning_input_version: str,
    analysis_date: date,
) -> list[ComponentDraft]:
    drafts: list[ComponentDraft] = []
    for need in needs:
        policy = rules.need_policies[need.need_type]
        prepared = _prepared_amount(need)
        target = need.target_amount
        minimum = need.minimum_amount
        component_type = policy.component_type
        action = policy.recommended_action
        product_mapping_allowed = policy.product_mapping_allowed
        specialist = policy.specialist
        review_required = _requires_professional_review(
            need,
            policy,
            profile_pension_stage,
        )
        status = (
            CFSComponentStatus.COMPLETED
            if need.status == WealthNeedStatus.PREPARED
            else CFSComponentStatus.PROFESSIONAL_REVIEW_REQUIRED
            if review_required
            else CFSComponentStatus.RECOMMENDED
        )

        if need.need_type == WealthNeedType.LONG_TERM_GROWTH:
            if not risk_budget.additional_risk_allowed or eligible_capital <= ZERO:
                component_type = CFSComponentType.NO_ACTION
                action = "当前不新增投资，先完成前置责任并等待风险预算重新开放。"
                product_mapping_allowed = False
                specialist = None
                review_required = False
                status = CFSComponentStatus.NO_ACTION_REQUIRED
            else:
                target = eligible_capital
                minimum = eligible_capital
                status = CFSComponentStatus.RECOMMENDED
                review_required = False
        elif need.need_type == WealthNeedType.ENTERPRISE_CONCENTRATION:
            target = max(target, family_enterprise_wealth)
            minimum = max(minimum, family_guarantee_exposure)
            if family_dependency_level != ComplexityBand.NONE:
                review_required = True
                status = CFSComponentStatus.PROFESSIONAL_REVIEW_REQUIRED

        rationale = (
            f"需求优先级 #{need.priority}；目标 {target:.2f} 元，"
            f"已准备 {prepared:.2f} 元。"
        )
        if status == CFSComponentStatus.NO_ACTION_REQUIRED:
            rationale = _no_action_reason(risk_budget)
        drafts.append(
            ComponentDraft(
                wealth_need_id=need.id,
                component_type=component_type,
                priority=need.priority,
                target_amount=money(target),
                minimum_amount=money(minimum),
                time_horizon=_horizon(need, analysis_date),
                recommended_action=action,
                product_mapping_allowed=product_mapping_allowed,
                professional_review_required=review_required,
                required_specialist=specialist if review_required else None,
                status=status,
                rationale=rationale,
                evidence={
                    "wealth_need_type": need.need_type.value,
                    "wealth_need_status": need.status.value,
                    "prepared_amount": str(money(prepared)),
                    "source_kind": need.source_kind,
                    "source_record_ids": need.source_record_ids,
                    "deterministic_tool": (
                        "no_action"
                        if status == CFSComponentStatus.NO_ACTION_REQUIRED
                        else policy.deterministic_tool
                    ),
                    "risk_budget_version": risk_budget.version,
                    "planning_input_version": planning_input_version,
                    "protection_gap": (
                        str(protection_gap)
                        if policy.component_type == CFSComponentType.PROTECTION
                        else None
                    ),
                },
            )
        )
    return sorted(drafts, key=lambda item: (item.priority, item.component_type.value))


def _summary(
    drafts: list[ComponentDraft],
    risk_budget: HouseholdRiskBudget,
) -> dict[str, object]:
    component_types = [item.component_type.value for item in drafts]
    no_action = any(item.status == CFSComponentStatus.NO_ACTION_REQUIRED for item in drafts)
    professional_count = sum(1 for item in drafts if item.professional_review_required)
    if CFSComponentType.DEBT.value in component_types and no_action:
        headline = "先还债，当前不新增投资"
    elif CFSComponentType.ENTERPRISE_RISK.value in component_types:
        headline = "先处理家企集中与专业治理，再安排新增风险"
    elif {
        CFSComponentType.PROTECTION.value,
        CFSComponentType.RETIREMENT.value,
        CFSComponentType.INVESTMENT.value,
    } <= set(component_types):
        headline = "保障、退休与长期配置按风险预算并行"
    elif no_action:
        headline = "当前最优行动是不新增投资"
    else:
        headline = "按需要优先级逐项落实家庭财务方案"
    return {
        "headline": headline,
        "component_count": len(drafts),
        "professional_referral_count": professional_count,
        "no_action_required": no_action,
        "priority_component_types": component_types[:5],
        "risk_budget": risk_budget.model_dump(mode="json"),
        "boundary": (
            "CFS 先确定目的、金额、风险预算、工具与专业路由；"
            "产品本体只在通过映射闸门后，以独立候选层承接。"
        ),
    }


def _records(
    session: Session,
    household_id: str,
    solution_id: str,
) -> tuple[CFSSolution, list[CFSSolutionComponent], list[ProfessionalServiceReferral]]:
    solution = session.scalar(
        select(CFSSolution).where(
            CFSSolution.id == solution_id,
            CFSSolution.household_id == household_id,
            CFSSolution.is_deleted.is_(False),
        )
    )
    if solution is None:
        raise AppError("cfs_solution_not_found", "找不到家庭综合财务方案", status_code=404)
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
                ProfessionalServiceReferral.household_id == household_id,
                ProfessionalServiceReferral.solution_id == solution.id,
                ProfessionalServiceReferral.is_deleted.is_(False),
            )
            .order_by(ProfessionalServiceReferral.created_at)
        ).all()
    )
    return solution, components, referrals


def _response(
    session: Session,
    household_id: str,
    solution_id: str,
    rules: CFSComposerRules,
    *,
    idempotent_replay: bool,
) -> CFSSolutionResponse:
    solution, components, referrals = _records(session, household_id, solution_id)
    risk_budget = HouseholdRiskBudget.model_validate(solution.summary["risk_budget"])
    return CFSSolutionResponse(
        meta=CFSResponseMeta(
            household_id=household_id,
            analysis_date=solution.valuation_date or date.today(),
            data_as_of=solution.valuation_date,
            source_snapshot_id=solution.source_snapshot_id,
            rule_version=rules.semantic_version,
            formula_version=rules.formula_version,
            idempotent_replay=idempotent_replay,
        ),
        solution=CFSSolutionOut.model_validate(solution),
        components=[CFSComponentOut.model_validate(item) for item in components],
        risk_budget=risk_budget,
        orchestration=orchestrate_cfs_components(components, risk_budget),
        referrals=[ProfessionalReferralOut.model_validate(item) for item in referrals],
    )


def compose_cfs_solution(
    session: Session,
    household_id: str,
    payload: CFSComposeRequest,
    actor: ActorContext,
    *,
    financial_rules_path: str,
    planning_rules_path: str,
    methodology_rules_path: str,
    public_data_snapshot_path: str,
    client_profile_rules_path: str,
    liability_rules_path: str,
    family_enterprise_rules_path: str,
    cfs_rules_path: str,
    analysis_date: date,
) -> CFSSolutionResponse:
    ensure_household(session, household_id)
    rules = load_cfs_rules(cfs_rules_path)
    snapshot = materialize_current_twin(
        session,
        household_id,
        actor,
        financial_rules_path=financial_rules_path,
        methodology_rules_path=methodology_rules_path,
        public_data_snapshot_path=public_data_snapshot_path,
        client_profile_rules_path=client_profile_rules_path,
        liability_rules_path=liability_rules_path,
        family_enterprise_rules_path=family_enterprise_rules_path,
        analysis_date=analysis_date,
    )
    if payload.source_snapshot_id is not None and payload.source_snapshot_id != snapshot.id:
        raise AppError(
            "cfs_snapshot_not_current",
            "E06 仅从当前已确认快照生成 CFS；历史快照工作流将在 E08 接入",
            status_code=409,
        )
    profile = get_client_profile(session, household_id)
    needs = get_wealth_needs(session, household_id)
    liability = materialize_liability_streams(
        session,
        household_id,
        actor,
        liability_rules_path,
        analysis_date,
    )
    eligible = calculate_household_eligible_capital(
        session,
        household_id,
        actor,
        financial_rules_path=financial_rules_path,
        methodology_rules_path=methodology_rules_path,
        public_data_snapshot_path=public_data_snapshot_path,
        liability_rules_path=liability_rules_path,
        analysis_date=analysis_date,
    )
    family_enterprise = get_family_enterprise_view(
        session,
        household_id,
        family_enterprise_rules_path,
        analysis_date,
    )
    risk_budget = build_household_risk_budget(
        profile,
        liability,
        eligible,
        family_enterprise,
        rules,
        analysis_date,
    )
    facts = load_household_facts(session, household_id)
    financial = analyze_facts(facts, load_financial_rules(financial_rules_path), analysis_date)
    protection = build_protection_plan(facts, financial)
    planning = plan_facts(
        facts,
        financial_rules_path,
        load_planning_rules(planning_rules_path),
        analysis_date,
        empty_counterfactual(),
        methodology_rules=load_methodology_rules(methodology_rules_path),
        public_data_snapshot=load_public_data_snapshot(public_data_snapshot_path),
        eligible_capital=eligible.calculation,
    )
    protection_gap = money(sum((item.coverage_gap for item in protection.needs), ZERO))
    drafts = _component_drafts(
        needs.needs,
        rules,
        risk_budget,
        eligible_capital=eligible.calculation.eligible_long_term_capital,
        family_enterprise_wealth=family_enterprise.wealth.enterprise_wealth,
        family_guarantee_exposure=family_enterprise.guarantees.outstanding_exposure,
        family_dependency_level=family_enterprise.dependency.level,
        profile_pension_stage=profile.profile.pension_stage,
        protection_gap=protection_gap,
        planning_input_version=planning.meta.input_version,
        analysis_date=analysis_date,
    )
    need_set_hash = _hash(
        [(item.id, item.version, item.need_type.value, item.status.value) for item in needs.needs]
    )
    decision_payload = {
        "household_id": household_id,
        "source_snapshot_id": snapshot.id,
        "need_set_hash": need_set_hash,
        "risk_budget": risk_budget.model_dump(mode="json"),
        "rules": [rules.semantic_version, rules.formula_version],
        "components": [
            {
                "need": item.wealth_need_id,
                "type": item.component_type.value,
                "priority": item.priority,
                "target": str(item.target_amount),
                "minimum": str(item.minimum_amount),
                "status": item.status.value,
                "specialist": item.required_specialist.value
                if item.required_specialist
                else None,
            }
            for item in drafts
        ],
    }
    decision_hash = _hash(decision_payload)
    existing = session.scalar(
        select(CFSSolution).where(
            CFSSolution.household_id == household_id,
            CFSSolution.decision_hash == decision_hash,
            CFSSolution.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return _response(
            session,
            household_id,
            existing.id,
            rules,
            idempotent_replay=True,
        )

    ensure_cfs_rule_version(session, rules)
    current = session.scalar(
        select(CFSSolution)
        .where(
            CFSSolution.household_id == household_id,
            CFSSolution.status.in_([CFSSolutionStatus.ACTIVE, CFSSolutionStatus.NEEDS_REVIEW]),
            CFSSolution.is_deleted.is_(False),
        )
        .order_by(CFSSolution.solution_version.desc())
    )
    if current is not None:
        current.status = CFSSolutionStatus.SUPERSEDED
        current.version += 1
        current.updated_at = utc_now()
        add_audit_event(
            session,
            current,
            actor,
            AuditEventType.DATA_UPDATED,
            "CFS 被新的家庭事实与风险预算替代",
        )
    next_version = int(
        session.scalar(
            select(func.max(CFSSolution.solution_version)).where(
                CFSSolution.household_id == household_id
            )
        )
        or 0
    ) + 1
    solution = CFSSolution(
        household_id=household_id,
        profile_id=profile.profile.id,
        source_snapshot_id=snapshot.id,
        solution_version=next_version,
        status=(
            CFSSolutionStatus.NEEDS_REVIEW
            if any(item.professional_review_required for item in drafts)
            else CFSSolutionStatus.ACTIVE
        ),
        need_set_hash=need_set_hash,
        risk_budget_version=risk_budget.version,
        methodology_version=planning.meta.methodology_version,
        summary=_summary(drafts, risk_budget),
        decision_hash=decision_hash,
        currency=facts.currency,
        valuation_date=analysis_date,
        data_source="v5_cfs_composer",
        is_user_confirmed=True,
    )
    session.add(solution)
    session.flush()
    add_audit_event(
        session,
        solution,
        actor,
        AuditEventType.RECOMMENDATION_GENERATED,
        "生成确定性家庭综合财务方案",
    )
    for draft in drafts:
        component = CFSSolutionComponent(
            solution_id=solution.id,
            wealth_need_id=draft.wealth_need_id,
            component_type=draft.component_type,
            priority=draft.priority,
            target_amount=draft.target_amount,
            minimum_amount=draft.minimum_amount,
            time_horizon=draft.time_horizon,
            recommended_action=draft.recommended_action,
            product_mapping_allowed=draft.product_mapping_allowed,
            professional_review_required=draft.professional_review_required,
            required_specialist=draft.required_specialist,
            status=draft.status,
            rationale=draft.rationale,
            evidence=draft.evidence,
            currency=facts.currency,
            valuation_date=analysis_date,
            data_source="v5_cfs_composer",
            is_user_confirmed=True,
        )
        session.add(component)
        session.flush()
        add_audit_event(
            session,
            component,
            actor,
            AuditEventType.RECOMMENDATION_GENERATED,
            f"生成 CFS 组件 {component.component_type.value}",
        )
        if draft.professional_review_required and draft.required_specialist is not None:
            urgency = (
                ProfessionalReferralUrgency.HIGH
                if draft.priority <= 3
                else ProfessionalReferralUrgency.MEDIUM
            )
            referral = ProfessionalServiceReferral(
                household_id=household_id,
                solution_id=solution.id,
                component_id=component.id,
                specialist_type=draft.required_specialist,
                trigger_reason=draft.rationale,
                urgency=urgency,
                status=ProfessionalReferralStatus.OPEN,
                due_date=analysis_date + timedelta(days=rules.referral_due_days[urgency.value]),
                evidence={
                    "auto_routed": True,
                    "complexity_gate": "professional_review_required",
                    "advisor_workflow": "professional_referral",
                    "specialized_domain": component.component_type.value,
                    "wealth_need_id": draft.wealth_need_id,
                    "risk_budget_version": risk_budget.version,
                },
                currency=facts.currency,
                valuation_date=analysis_date,
                data_source="v5_professional_routing",
                is_user_confirmed=True,
            )
            session.add(referral)
            session.flush()
            add_audit_event(
                session,
                referral,
                actor,
                AuditEventType.RECOMMENDATION_GENERATED,
                f"生成专业转介 {referral.specialist_type.value}",
            )
    session.commit()
    return _response(
        session,
        household_id,
        solution.id,
        rules,
        idempotent_replay=False,
    )


def get_cfs_solution(
    session: Session,
    household_id: str,
    solution_id: str,
    cfs_rules_path: str,
) -> CFSSolutionResponse:
    ensure_household(session, household_id)
    return _response(
        session,
        household_id,
        solution_id,
        load_cfs_rules(cfs_rules_path),
        idempotent_replay=False,
    )


def create_professional_referral(
    session: Session,
    household_id: str,
    payload: ProfessionalReferralCreate,
    actor: ActorContext,
) -> ProfessionalReferralOut:
    ensure_household(session, household_id)
    solution, components, _referrals = _records(
        session,
        household_id,
        payload.solution_id,
    )
    component = next((item for item in components if item.id == payload.component_id), None)
    if component is None:
        raise AppError("cfs_component_not_found", "找不到该方案组件", status_code=404)
    existing = session.scalar(
        select(ProfessionalServiceReferral).where(
            ProfessionalServiceReferral.solution_id == solution.id,
            ProfessionalServiceReferral.component_id == component.id,
            ProfessionalServiceReferral.specialist_type == payload.specialist_type,
            ProfessionalServiceReferral.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return ProfessionalReferralOut.model_validate(existing)
    referral = ProfessionalServiceReferral(
        household_id=household_id,
        solution_id=solution.id,
        component_id=component.id,
        specialist_type=payload.specialist_type,
        trigger_reason=payload.trigger_reason,
        urgency=payload.urgency,
        status=ProfessionalReferralStatus.OPEN,
        due_date=payload.due_date,
        evidence=payload.evidence,
        currency=solution.currency,
        valuation_date=solution.valuation_date,
        data_source="user_confirmed_professional_routing",
        is_user_confirmed=True,
    )
    session.add(referral)
    session.flush()
    add_audit_event(
        session,
        referral,
        actor,
        AuditEventType.CONFIRMATION_RECORDED,
        f"客户确认专业转介 {referral.specialist_type.value}",
    )
    session.commit()
    session.refresh(referral)
    return ProfessionalReferralOut.model_validate(referral)
