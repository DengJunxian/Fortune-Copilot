from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    CFSComponentType,
    CFSSolutionStatus,
    ProfessionalReferralStatus,
    ProfessionalSpecialistType,
    SpecializedComplexity,
)
from app.models.cfs import CFSSolution, CFSSolutionComponent, ProfessionalServiceReferral
from app.schemas.specialized_cfs import ProfessionalRoute

BOUNDARY = "专业转介只建立协作责任节点，不构成法律、税务、信托设立或跨境合规结论。"


def resolve_professional_route(
    session: Session,
    household_id: str,
    *,
    need: str,
    complexity: SpecializedComplexity,
    specialist_type: ProfessionalSpecialistType | None,
    component_types: set[CFSComponentType],
    reason: str,
) -> ProfessionalRoute:
    gate_passed = complexity != SpecializedComplexity.NONE and specialist_type is not None
    if not gate_passed:
        return ProfessionalRoute(
            need=need,
            complexity=complexity,
            complexity_gate_passed=False,
            specialist_type=None,
            referral_id=None,
            referral_status=None,
            advisor_workflow_status="not_required",
            reason=reason,
            boundary=BOUNDARY,
        )
    solution = session.scalar(
        select(CFSSolution)
        .where(
            CFSSolution.household_id == household_id,
            CFSSolution.status.in_([CFSSolutionStatus.ACTIVE, CFSSolutionStatus.NEEDS_REVIEW]),
            CFSSolution.is_deleted.is_(False),
        )
        .order_by(CFSSolution.solution_version.desc())
    )
    if solution is None:
        return ProfessionalRoute(
            need=need,
            complexity=complexity,
            complexity_gate_passed=True,
            specialist_type=specialist_type,
            referral_id=None,
            referral_status=None,
            advisor_workflow_status="cfs_required",
            reason=reason,
            boundary=BOUNDARY,
        )
    component = session.scalar(
        select(CFSSolutionComponent)
        .where(
            CFSSolutionComponent.solution_id == solution.id,
            CFSSolutionComponent.component_type.in_(component_types),
            CFSSolutionComponent.is_deleted.is_(False),
        )
        .order_by(CFSSolutionComponent.priority)
    )
    if component is None:
        status = "cfs_required"
        referral = None
    else:
        referral = session.scalar(
            select(ProfessionalServiceReferral).where(
                ProfessionalServiceReferral.solution_id == solution.id,
                ProfessionalServiceReferral.component_id == component.id,
                ProfessionalServiceReferral.specialist_type == specialist_type,
                ProfessionalServiceReferral.is_deleted.is_(False),
            )
        )
        status = "cfs_required" if referral is None else {
            ProfessionalReferralStatus.OPEN: "referral_open",
            ProfessionalReferralStatus.ACCEPTED: "in_progress",
            ProfessionalReferralStatus.COMPLETED: "completed",
            ProfessionalReferralStatus.CANCELLED: "cfs_required",
        }[referral.status]
    return ProfessionalRoute(
        need=need,
        complexity=complexity,
        complexity_gate_passed=True,
        specialist_type=specialist_type,
        referral_id=referral.id if referral is not None else None,
        referral_status=referral.status if referral is not None else None,
        advisor_workflow_status=status,
        reason=reason,
        boundary=BOUNDARY,
    )
