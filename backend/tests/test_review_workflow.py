from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.enums import AuditEventType, PlanWorkflowState
from app.main import app
from app.models.family import Household
from app.models.governance import AuditEvent, PlanWorkflowVersion
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
BEHAVIOR_RULES_PATH = "../data/rules/behavior_finance_v1.json"
KNOWLEDGE_PATH = "../data/knowledge/controlled_knowledge_v1.json"


async def api_request(
    method: str,
    path: str,
    *,
    role: str,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={
                "X-Actor-ID": f"stage-ten-{role}",
                "X-Actor-Role": role,
                "X-Request-ID": f"request-{role}-{method.lower()}",
            },
        )


def call(
    method: str,
    path: str,
    *,
    role: str,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, role=role, payload=payload))


def seed_demo() -> tuple[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            portfolio_rules_path=PORTFOLIO_RULES_PATH,
            product_catalog_path=PRODUCT_CATALOG_PATH,
            twin_rules_path=TWIN_RULES_PATH,
            behavior_rules_path=BEHAVIOR_RULES_PATH,
            knowledge_base_path=KNOWLEDGE_PATH,
        )
        household = session.scalar(select(Household).where(Household.code == "DEMO_B"))
        assert household is not None
        consent_id = session.scalar(
            select(AuditEvent.entity_id).where(
                AuditEvent.household_id == household.id,
                AuditEvent.event_type == AuditEventType.CONSENT_GRANTED,
            )
        )
        # Seed creates the consent but not a dedicated grant event. Fetch its id
        # through the client experience endpoint in the consent-withdrawal test.
        return household.id, consent_id or ""


def create_workflow(household_id: str) -> dict[str, Any]:
    response = call(
        "POST",
        f"/api/v1/households/{household_id}/plan-workflows",
        role="advisor",
        payload={"reason": "建立客户面谈后的可审计方案"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def action(
    workflow: dict[str, Any],
    action_name: str,
    *,
    role: str,
    **extra: object,
) -> dict[str, Any]:
    response = call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/actions",
        role=role,
        payload={
            "action": action_name,
            "expected_version": workflow["current"]["version_number"],
            "reason": f"测试动作 {action_name}",
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def to_advisor_submission(household_id: str, draft: str | None = None) -> dict[str, Any]:
    workflow = create_workflow(household_id)
    workflow = action(workflow, "calculate", role="advisor")
    workflow = action(workflow, "suitability_check", role="advisor")
    workflow = action(
        workflow,
        "advisor_review",
        role="advisor",
        selected_candidate="balanced",
        communication_draft=draft,
        manual_high_risk_confirmed=True,
        advisor_note="已逐项核对风险和流动性",
    )
    return action(workflow, "submit_compliance", role="advisor")


def test_rbac_blocks_privilege_escalation_and_hides_internal_drafts() -> None:
    household_id, _ = seed_demo()
    denied = call(
        "POST",
        f"/api/v1/households/{household_id}/plan-workflows",
        role="client",
        payload={"reason": "客户尝试越权创建审核流"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    workflow = create_workflow(household_id)
    hidden = call(
        "GET",
        f"/api/v1/households/{household_id}/plan-workflows/current",
        role="client",
    )
    assert hidden.status_code == 403
    assert hidden.json()["error"]["code"] == "workflow_not_ready_for_client"

    compliance_calculate = call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/actions",
        role="compliance",
        payload={
            "action": "calculate",
            "expected_version": 1,
            "reason": "合规角色尝试代替客户经理计算",
        },
    )
    assert compliance_calculate.status_code == 403
    assert compliance_calculate.json()["error"]["details"]["current_role"] == "compliance"


def test_state_machine_rejects_skips_and_completes_three_portal_flow() -> None:
    household_id, _ = seed_demo()
    workflow = create_workflow(household_id)

    skipped = call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/actions",
        role="advisor",
        payload={
            "action": "advisor_review",
            "expected_version": 1,
            "reason": "尝试跳过计算与适当性",
            "selected_candidate": "balanced",
        },
    )
    assert skipped.status_code == 409
    assert skipped.json()["error"]["code"] == "workflow_transition_forbidden"

    duplicate = call(
        "POST",
        f"/api/v1/households/{household_id}/plan-workflows",
        role="advisor",
        payload={"reason": "尝试并行创建第二个当前方案"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "workflow_already_open"

    workflow = action(workflow, "calculate", role="advisor")
    workflow = action(workflow, "suitability_check", role="advisor")
    workflow = action(
        workflow,
        "advisor_review",
        role="advisor",
        selected_candidate="balanced",
        manual_high_risk_confirmed=True,
        advisor_note="人工确认候选方案",
    )
    workflow = action(workflow, "submit_compliance", role="advisor")

    evidence = call(
        "GET",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/compliance-evidence",
        role="compliance",
    )
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["blocked_codes"] == []
    assert set(evidence.json()["three_gate_statuses"]) == {
        "family_safety",
        "customer",
        "product",
    }
    assert evidence.json()["hash_chain_verified"] is True

    workflow = action(
        workflow,
        "compliance_approve",
        role="compliance",
        human_review_completed=True,
        compliance_note="三道闸门、文案、数字、来源和版本均已复核",
    )
    assert workflow["current"]["state"] == "compliance_reviewed"

    client_view = call(
        "GET",
        f"/api/v1/households/{household_id}/plan-workflows/current",
        role="client",
    )
    assert client_view.status_code == 200
    assert client_view.json()["current"]["communication_draft"]
    assert client_view.json()["current"]["actor_id"] == "redacted-for-client"
    assert client_view.json()["current"]["request_id"] == "redacted-for-client"
    assert len(client_view.json()["versions"]) == 1
    assert "advisor_modification" not in client_view.json()["current"]["recommendation_snapshot"]

    workflow = action(
        workflow,
        "customer_confirm",
        role="client",
        customer_name="李先生",
        acknowledgements=["risk_read", "mock_understood", "not_guaranteed"],
    )
    assert workflow["current"]["customer_confirmation"]["signature_status"] == "confirmed"
    assert "李先生" not in str(workflow["current"]["customer_confirmation"])
    workflow = action(workflow, "activate", role="advisor")

    assert workflow["current"]["state"] == "active"
    assert [item["state"] for item in workflow["versions"]] == [
        "draft",
        "calculated",
        "suitability_checked",
        "advisor_reviewed",
        "advisor_reviewed",
        "compliance_reviewed",
        "customer_confirmed",
        "active",
    ]
    for previous, current in zip(workflow["versions"], workflow["versions"][1:], strict=False):
        assert current["before_hash"] == previous["after_hash"]


def test_every_advisor_edit_creates_a_traceable_version() -> None:
    household_id, _ = seed_demo()
    workflow = create_workflow(household_id)
    workflow = action(workflow, "calculate", role="advisor")
    workflow = action(workflow, "suitability_check", role="advisor")
    workflow = action(
        workflow,
        "advisor_review",
        role="advisor",
        selected_candidate="balanced",
        manual_high_risk_confirmed=True,
    )
    original = workflow["current"]
    revised_text = (
        "已根据客户反馈调整解释顺序。所有金额仍来自确定性工具，"
        "本方案不承诺保本或收益，并需在家庭情况变化后重新计算。"
    )
    workflow = action(
        workflow,
        "edit_communication",
        role="advisor",
        communication_draft=revised_text,
    )
    revised = workflow["current"]
    assert revised["version_number"] == original["version_number"] + 1
    assert revised["prior_version_id"] == original["id"]
    assert revised["communication_draft"] == revised_text
    assert workflow["versions"][-2]["communication_draft"] != revised_text
    assert revised["actor_role"] == "advisor"
    assert revised["reason"] == "测试动作 edit_communication"


def test_consent_withdrawal_blocks_further_workflow_calculation() -> None:
    household_id, _ = seed_demo()
    workflow = create_workflow(household_id)
    experience = call(
        "GET",
        f"/api/v1/households/{household_id}/client-experience",
        role="client",
    ).json()
    consent = next(item for item in experience["privacy"]["consents"] if item["status"] == "active")
    withdrawn = call(
        "POST",
        f"/api/v1/households/{household_id}/privacy/consents/{consent['id']}/withdraw",
        role="client",
        payload={
            "expected_version": consent["record_version"],
            "reason": "客户撤回规划授权",
        },
    )
    assert withdrawn.status_code == 200

    blocked = call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/actions",
        role="advisor",
        payload={
            "action": "calculate",
            "expected_version": 1,
            "reason": "授权撤回后尝试计算",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "consent_required"


def test_prohibited_wording_is_explained_and_cannot_be_approved() -> None:
    household_id, _ = seed_demo()
    workflow = to_advisor_submission(
        household_id,
        draft=("该方案保证收益并且稳赚，投资金额 120000.00 元。客户经理已经确认，可直接执行。"),
    )
    evidence = call(
        "GET",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/compliance-evidence",
        role="compliance",
    )
    assert evidence.status_code == 200
    payload = evidence.json()
    assert "prohibited_wording" in payload["blocked_codes"]
    assert set(payload["prohibited_phrases"]) == {"保证收益", "稳赚"}

    denied = call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/actions",
        role="compliance",
        payload={
            "action": "compliance_approve",
            "expected_version": workflow["current"]["version_number"],
            "reason": "尝试通过违规文案",
            "human_review_completed": True,
        },
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "compliance_blocked"


def test_complaint_replay_and_audit_export_preserve_history() -> None:
    household_id, _ = seed_demo()
    workflow = to_advisor_submission(household_id)
    requested_version = workflow["versions"][3]
    replay = call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/complaint-replays",
        role="compliance",
        payload={
            "version_id": requested_version["id"],
            "reason": "客户投诉沟通内容与建议版本不一致",
        },
    )
    assert replay.status_code == 200, replay.text
    replay_payload = replay.json()
    assert replay_payload["integrity_status"] == "verified"
    assert any(item["is_requested_version"] for item in replay_payload["timeline"])
    assert len(replay_payload["package_hash"]) == 64

    exported = call(
        "GET",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/audit-export",
        role="compliance",
    )
    assert exported.status_code == 200, exported.text
    package = exported.json()
    assert package["hash_chain_verified"] is True
    assert package["versions"][0]["state"] == "draft"
    assert package["versions"][-1]["state"] == "advisor_reviewed"
    assert "wealthtwin-workflow" in exported.headers["content-disposition"]

    with SessionLocal() as session:
        persisted = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.household_id == household_id,
                    AuditEvent.event_type.in_(
                        [
                            AuditEventType.COMPLAINT_REPLAYED,
                            AuditEventType.AUDIT_PACKAGE_EXPORTED,
                        ]
                    ),
                )
            ).all()
        )
        assert {item.event_type for item in persisted} == {
            AuditEventType.COMPLAINT_REPLAYED,
            AuditEventType.AUDIT_PACKAGE_EXPORTED,
        }


def test_mock_bank_adapter_has_eight_interfaces_and_never_capitalizes_credit_limit() -> None:
    household_id, _ = seed_demo()
    denied = call(
        "GET",
        f"/api/v1/households/{household_id}/mock-bank-snapshot",
        role="client",
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    response = call(
        "GET",
        f"/api/v1/households/{household_id}/mock-bank-snapshot",
        role="advisor",
    )
    assert response.status_code == 200, response.text
    snapshot = response.json()
    assert snapshot["mock"] is True
    assert snapshot["official_connection"] is False
    assert len(snapshot["interfaces"]) == 8
    assert snapshot["credit_limit_in_total_assets"] is False
    credit = next(item for item in snapshot["interfaces"] if item["code"] == "credit_cards")
    assert credit["entries"][0]["amount_role"] == "liability"
    assert credit["entries"][0]["details"]["credit_limit_is_asset"] is False
    assert "官方标识" in snapshot["boundary_note"]


def test_persisted_workflow_state_uses_canonical_compliance_role() -> None:
    household_id, _ = seed_demo()
    workflow = to_advisor_submission(household_id)
    workflow = action(
        workflow,
        "require_human_review",
        role="risk",
        compliance_note="使用旧 risk 头回放，持久化必须归一为合规角色",
    )
    with SessionLocal() as session:
        version = session.get(PlanWorkflowVersion, workflow["current"]["id"])
        assert version is not None
        assert version.actor_role == "compliance"
        assert version.state == PlanWorkflowState.ADVISOR_REVIEWED
