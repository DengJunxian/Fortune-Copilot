from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import MonitoringAlertStatus, MonitoringSeverity
from app.models.governance import ActionItem
from app.models.monitoring import AdvisorTrigger, MonitoringAlert, MonitoringPolicy
from app.schemas.monitoring import NextBestActionOut, NextBestActionsResponse
from app.services.crud import ensure_household

BOUNDARY = (
    "Next Best Action 只按客户影响安排复核、教育、冷静期和专业转介；"
    "不得变成 Next Best Sale，不自动选产品或执行交易。"
)

PRIORITY = {
    MonitoringSeverity.CRITICAL: 1,
    MonitoringSeverity.HIGH: 2,
    MonitoringSeverity.WATCH: 3,
    MonitoringSeverity.INFO: 4,
}


def get_next_best_actions(
    session: Session,
    household_id: str,
    analysis_date: date,
) -> NextBestActionsResponse:
    ensure_household(session, household_id)
    rows = list(
        session.execute(
            select(MonitoringAlert, MonitoringPolicy, AdvisorTrigger, ActionItem)
            .join(MonitoringPolicy, MonitoringAlert.monitoring_policy_id == MonitoringPolicy.id)
            .outerjoin(
                AdvisorTrigger,
                AdvisorTrigger.monitoring_alert_id == MonitoringAlert.id,
            )
            .outerjoin(ActionItem, ActionItem.advisor_trigger_id == AdvisorTrigger.id)
            .where(
                MonitoringAlert.household_id == household_id,
                MonitoringAlert.status.in_(
                    {MonitoringAlertStatus.OPEN, MonitoringAlertStatus.ACKNOWLEDGED}
                ),
                MonitoringAlert.is_deleted.is_(False),
            )
            .order_by(
                MonitoringAlert.severity.desc(),
                MonitoringAlert.detected_at,
                MonitoringAlert.id,
            )
        ).all()
    )
    if not rows:
        return NextBestActionsResponse(
            household_id=household_id,
            outcome="NO_ACTION_REQUIRED",
            actions=[
                NextBestActionOut(
                    action_code="NO_ACTION_REQUIRED",
                    household_id=household_id,
                    priority=0,
                    trigger_reason="当前没有达到监控阈值的重大变化。",
                    client_impact="没有新的客户影响需要立即处理。",
                    recommended_action="保持现有计划并按既定节奏复核，不新增销售动作。",
                    do_not_sell_flag=True,
                    required_specialist=None,
                    evidence={
                        "analysis_date": analysis_date.isoformat(),
                        "formal_no_action": True,
                        "next_best_sale": False,
                    },
                    due_date=None,
                )
            ],
            boundary=BOUNDARY,
        )
    actions = [
        NextBestActionOut(
            action_code=(
                action.action_code
                if action is not None and action.action_code is not None
                else f"MONITOR_{policy.policy_type.value.upper()}"
            ),
            household_id=household_id,
            priority=PRIORITY[alert.severity],
            trigger_reason=alert.trigger_reason,
            client_impact=alert.client_impact,
            recommended_action=alert.recommended_action,
            do_not_sell_flag=True,
            required_specialist=alert.required_specialist,
            evidence={
                "monitoring_alert_id": alert.id,
                "monitoring_policy_id": policy.id,
                "advisor_trigger_id": trigger.id if trigger is not None else None,
                "evidence_snapshot": alert.evidence_snapshot,
                "next_best_sale": False,
            },
            due_date=(
                action.due_date
                if action is not None
                else trigger.follow_up_due
                if trigger is not None
                else None
            ),
        )
        for alert, policy, trigger, action in rows
    ]
    actions.sort(key=lambda item: (item.priority, item.due_date or date.max, item.action_code))
    return NextBestActionsResponse(
        household_id=household_id,
        outcome="ACTIONS_AVAILABLE",
        actions=actions,
        boundary=BOUNDARY,
    )
