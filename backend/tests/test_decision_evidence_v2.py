from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.auth import ActorContext
from app.core.database import SessionLocal
from app.main import app
from app.models.family import Household
from app.models.governance import ProductSnapshot
from app.schemas.cfs import CFSComposeRequest
from app.services.cfs_composer.engine import compose_cfs_solution
from app.services.governance.evidence import (
    calculate_decision_hash,
    minimal_v2_from_legacy,
    seal_decision_evidence,
)
from app.services.seed import seed_synthetic_data

ANALYSIS_DATE = date(2026, 8, 10)


def _legacy() -> dict[str, Any]:
    return {
        "household_input_version": "input-v1",
        "methodology_version": "method-v1",
        "financial_rule_version": "financial-v1",
        "planning_rule_version": "planning-v1",
        "product_snapshot_version": "product-v1",
        "risk_assessment_version": "risk-v1",
        "behavior_assessment_version": "behavior-v1",
        "hard_gate_results": {"liquidity": "pass"},
    }


def _actor() -> ActorContext:
    now = datetime.now(UTC)
    return ActorContext(
        actor_id="decision-evidence-admin",
        role="admin",
        household_ids=("*",),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        auth_source="demo_headers",
    )


async def _api_request(
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
                "X-Actor-ID": f"e08-{role}",
                "X-Actor-Role": role,
                "X-Request-ID": f"e08-{method.lower()}-{role}",
            },
        )


def _call(
    method: str,
    path: str,
    *,
    role: str,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(_api_request(method, path, role=role, payload=payload))


def _seed_cfs() -> tuple[str, str]:
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            "../data/synthetic/families.json",
            rules_path="../data/rules/financial_health_v1.json",
            planning_rules_path="../data/rules/planning_waterfall_v1.json",
            methodology_rules_path="../data/rules/wealth_methodology_v3.json",
            portfolio_rules_path="../data/rules/portfolio_policy_v1.json",
            twin_rules_path="../data/rules/twin_simulation_v1.json",
            behavior_rules_path="../data/rules/behavior_finance_v1.json",
            knowledge_base_path="../data/knowledge/controlled_knowledge_v1.json",
        )
        household = session.scalar(select(Household).where(Household.code == "DEMO_B"))
        assert household is not None
        solution = compose_cfs_solution(
            session,
            household.id,
            CFSComposeRequest(is_user_confirmed=True),
            _actor(),
            financial_rules_path="../data/rules/financial_health_v1.json",
            planning_rules_path="../data/rules/planning_waterfall_v1.json",
            methodology_rules_path="../data/rules/wealth_methodology_v3.json",
            public_data_snapshot_path="../data/public/authoritative_public_snapshot_v1.json",
            client_profile_rules_path="../data/rules/client_profile_v1.json",
            liability_rules_path="../data/rules/liability_engine_v1.json",
            family_enterprise_rules_path="../data/rules/family_enterprise_v1.json",
            cfs_rules_path="../data/rules/cfs_composer_v1.json",
            analysis_date=ANALYSIS_DATE,
        )
        return household.id, solution.solution.id


def _action(workflow: dict[str, Any], action_name: str, **extra: object) -> dict[str, Any]:
    response = _call(
        "POST",
        f"/api/v1/plan-workflows/{workflow['workflow_id']}/actions",
        role="advisor",
        payload={
            "action": action_name,
            "expected_version": workflow["current"]["version_number"],
            "reason": f"E08 {action_name}",
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_hash_is_deterministic_and_only_decision_material_changes_identity() -> None:
    first = minimal_v2_from_legacy(
        decision_id="decision-a",
        decision_type="recommendation",
        household_id="household-a",
        legacy=_legacy(),
        generated_at=datetime(2026, 8, 10, tzinfo=UTC),
    )
    display_change = first.model_dump(mode="json")
    display_change["decision_id"] = "decision-b"
    display_change["generated_at"] = datetime(2026, 8, 11, tzinfo=UTC)
    display_change["advisor"]["display_only_text"] = "新的界面说明"
    display_change["advisor"]["decision_inputs"]["request_id"] = "request-2"
    replay = seal_decision_evidence(display_change)
    assert replay.decision_hash == first.decision_hash

    for section_name, key, value in (
        ("wealth_needs", "need_set_hash", "need-v2"),
        ("product_snapshot", "product_snapshot_version", "product-v2"),
        ("risk_budget", "risk_assessment_version", "risk-v2"),
        ("client_profile", "profile_hash", "profile-v2"),
    ):
        changed = first.model_dump(mode="json")
        changed[section_name]["status"] = "bound"
        changed[section_name]["version"] = str(value)
        changed[section_name]["decision_inputs"] = {key: value}
        assert seal_decision_evidence(changed).decision_hash != first.decision_hash


def test_workflow_freezes_cfs_product_snapshots_and_replay_never_reads_latest() -> None:
    household_id, solution_id = _seed_cfs()
    created = _call(
        "POST",
        f"/api/v1/households/{household_id}/plan-workflows",
        role="advisor",
        payload={"reason": "冻结 CFS 与产品证据"},
    )
    assert created.status_code == 201, created.text
    workflow = _action(created.json(), "calculate")
    snapshot = workflow["current"]["recommendation_snapshot"]
    assert snapshot["cfs_solution_id"] == solution_id
    assert snapshot["cfs_version"] == 1
    assert snapshot["selected_components"]
    assert "professional_referrals" in snapshot

    evidence_response = _call(
        "GET",
        f"/api/v1/decisions/{workflow['workflow_id']}/evidence",
        role="compliance",
    )
    assert evidence_response.status_code == 200, evidence_response.text
    evidence = evidence_response.json()
    assert evidence["evidence_version"] == "decision-evidence-v2.0.0"
    assert evidence["CFS"]["decision_inputs"]["solution_id"] == solution_id
    assert len(evidence["product_snapshot"]["decision_inputs"]["snapshots"]) == 8
    assert all(
        name in evidence
        for name in (
            "household_input",
            "financial_graph",
            "client_profile",
            "wealth_needs",
            "liability",
            "ELTC",
            "risk_budget",
            "enterprise",
            "CFS",
            "product_snapshot",
            "suitability",
            "calibration",
            "advisor",
            "client_confirmation",
        )
    )
    frozen_hash = evidence["product_snapshot"]["decision_inputs"]["snapshots"][0][
        "snapshot_hash"
    ]
    with SessionLocal() as session:
        product_snapshot = session.scalar(select(ProductSnapshot).order_by(ProductSnapshot.id))
        assert product_snapshot is not None
        product_snapshot.snapshot_hash = "f" * 64
        session.commit()

    replay = _call(
        "POST",
        f"/api/v1/decisions/{workflow['workflow_id']}/replay",
        role="compliance",
    )
    assert replay.status_code == 200, replay.text
    replay_payload = replay.json()
    assert replay_payload["hash_identical"] is True
    assert replay_payload["latest_product_data_used"] is False
    assert (
        replay_payload["evidence"]["product_snapshot"]["decision_inputs"]["snapshots"][0][
            "snapshot_hash"
        ]
        == frozen_hash
    )
    assert calculate_decision_hash(replay_payload["evidence"]) == evidence["decision_hash"]


def test_advisor_and_client_confirmation_extend_the_same_frozen_package() -> None:
    household_id, _solution_id = _seed_cfs()
    workflow = _call(
        "POST",
        f"/api/v1/households/{household_id}/plan-workflows",
        role="advisor",
        payload={"reason": "验证审批证据增量"},
    ).json()
    workflow = _action(workflow, "calculate")
    original_product_version = workflow["current"]["recommendation_snapshot"][
        "decision_evidence"
    ]["product_snapshot"]["version"]
    workflow = _action(workflow, "suitability_check")
    workflow = _action(
        workflow,
        "advisor_review",
        selected_candidate="balanced",
        manual_high_risk_confirmed=True,
        advisor_note="已人工复核",
    )
    evidence = workflow["current"]["recommendation_snapshot"]["decision_evidence"]
    assert evidence["advisor"]["status"] == "bound"
    assert evidence["advisor"]["decision_inputs"]["selected_candidate"] == "balanced"
    assert evidence["product_snapshot"]["version"] == original_product_version

    copied = copy.deepcopy(evidence)
    copied["generated_at"] = datetime(2030, 1, 1, tzinfo=UTC).isoformat()
    assert calculate_decision_hash(copied) == evidence["decision_hash"]
