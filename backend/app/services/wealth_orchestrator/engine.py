from __future__ import annotations

from collections.abc import Sequence

from app.domain.enums import CFSComponentStatus, CFSComponentType, RiskLevel
from app.models.cfs import CFSSolutionComponent
from app.schemas.cfs import CFSOrchestrationStep, HouseholdRiskBudget

_SAFETY_COMPONENTS = {
    CFSComponentType.LIQUIDITY,
    CFSComponentType.DEBT,
    CFSComponentType.PROTECTION,
}
_GOAL_COMPONENTS = {
    CFSComponentType.HOUSING,
    CFSComponentType.EDUCATION,
    CFSComponentType.RETIREMENT,
}


def orchestrate_cfs_components(
    components: Sequence[CFSSolutionComponent],
    risk_budget: HouseholdRiskBudget,
) -> list[CFSOrchestrationStep]:
    steps: list[CFSOrchestrationStep] = []
    for component in sorted(components, key=lambda item: (item.priority, item.id)):
        tool = str(component.evidence.get("deterministic_tool", "professional_routing"))
        if component.status == CFSComponentStatus.NO_ACTION_REQUIRED:
            allowed_risk = RiskLevel.LOW
            step_status = "blocked"
            tool = "no_action"
        elif component.professional_review_required:
            allowed_risk = min(
                risk_budget.household_economic_risk_capacity,
                RiskLevel.MEDIUM_LOW,
                key=lambda item: list(RiskLevel).index(item),
            )
            step_status = "professional_review"
        elif component.component_type in _SAFETY_COMPONENTS:
            allowed_risk = RiskLevel.LOW
            step_status = "ready"
        elif component.component_type in _GOAL_COMPONENTS:
            allowed_risk = min(
                risk_budget.household_economic_risk_capacity,
                RiskLevel.MEDIUM_LOW,
                key=lambda item: list(RiskLevel).index(item),
            )
            step_status = "ready"
        else:
            allowed_risk = risk_budget.household_economic_risk_capacity
            step_status = "ready" if risk_budget.additional_risk_allowed else "blocked"
        steps.append(
            CFSOrchestrationStep(
                component_id=component.id,
                purpose=component.component_type.value,
                allowed_risk=allowed_risk,
                deterministic_tool=tool,
                status=step_status,
                output_summary=component.recommended_action,
            )
        )
    return steps
