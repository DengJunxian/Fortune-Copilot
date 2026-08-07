from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.enums import AuditEventType
from app.main import app
from app.models.family import Household
from app.models.governance import AuditEvent
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
BEHAVIOR_RULES_PATH = "../data/rules/behavior_finance_v1.json"
KNOWLEDGE_PATH = "../data/knowledge/controlled_knowledge_v1.json"

CHAPTER_TITLES = [
    "家庭画像与生命周期",
    "资产负债与现金流",
    "财务健康与家庭保障",
    "家庭目标与冲突",
    "四账户动态规划",
    "方案比较与数字孪生",
    "行动日历与复盘",
    "计算依据、引用与风险边界",
]


async def api_request(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={"X-Actor-ID": "client-stage-nine", "X-Actor-Role": "client"},
        )


def call(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, payload=payload))


def seed_client_demo() -> str:
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
        household_id = session.scalar(select(Household.id).where(Household.code == "DEMO_B"))
        assert household_id is not None
        return household_id


def test_client_experience_composes_real_engines_into_strict_journey_and_eight_chapters() -> None:
    household_id = seed_client_demo()
    response = call(
        "GET",
        f"/api/v1/households/{household_id}/client-experience?analysis_date=2026-08-04",
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["mock_mode_supported"] is True
    assert payload["delivery"] == {
        "report": "not_generated",
        "workflow": "not_created",
        "actions": "not_generated",
        "explanation": "尚未生成正式报告；客户端可从确定性预览创建新快照。",
    }
    assert len(payload["journey"]) == 13
    assert {step["code"] for step in payload["journey"]} == {
        "privacy",
        "quick",
        "deep",
        "profile",
        "checkup",
        "goals",
        "behavior",
        "accounts",
        "comparison",
        "twin",
        "report",
        "calendar",
        "review",
    }
    assert len(payload["state_catalog"]) == 14
    assert len(payload["action_calendar"]) == 5
    monthly = next(
        group for group in payload["action_calendar"] if group["code"] == "next_12_months"
    )
    assert len(monthly["items"]) == 12
    assert all(
        item["calculation_source"] == "deterministic_review_schedule" for item in monthly["items"]
    )
    assert all(
        item["why"]
        and item["constraint_or_formula"]
        and item["change_trigger"]
        and item["risk_and_assumptions"]
        for group in payload["action_calendar"]
        for item in group["items"]
    )

    report = payload["report"]
    assert report["chapter_count"] == 8
    assert [chapter["number"] for chapter in report["chapters"]] == list(range(1, 9))
    assert [chapter["title"] for chapter in report["chapters"]] == CHAPTER_TITLES
    assert report["calculation_source"] == "deterministic_client_experience_composer"
    assert (
        payload["calculation_versions"]["knowledge_retrieval"]
        == report["knowledge_retrieval_version"]
    )
    assert payload["calculation_versions"]["report"] == report["report_version"]
    for citation in report["citations"]:
        assert citation["source_uri"]
        assert citation["publication_date"]
        assert citation["effective_date"]
        assert citation["document_version"]


def test_client_export_keeps_deterministic_numbers_and_never_capitalizes_credit_limit() -> None:
    household_id = seed_client_demo()
    response = call(
        "GET",
        f"/api/v1/households/{household_id}/client-experience/export?analysis_date=2026-08-04",
    )
    assert response.status_code == 200, response.text
    assert (
        "wealthtwin-demo_b-client-data-2026-08-04.json" in response.headers["content-disposition"]
    )
    package = response.json()
    balance = package["financial_analysis"]["statements"]["balance_sheet"]
    assert balance["total_assets"] == "2850000.00"
    assert balance["total_liabilities"] == "1208000.00"
    assert balance["net_worth"] == "1642000.00"
    assert all("credit_limit" not in asset for asset in balance["assets"])
    assert package["planning"]["meta"]["calculation_source"] == "deterministic_tools"
    assert package["client_experience"]["report"]["chapter_count"] == 8
    assert "不包含信用卡额度资产化结果" in package["boundary_note"]


def test_three_demo_households_produce_materially_different_client_outputs() -> None:
    seed_client_demo()
    with SessionLocal() as session:
        household_rows = list(
            session.execute(
                select(Household.code, Household.id)
                .where(Household.code.in_(["DEMO_A", "DEMO_B", "DEMO_C"]))
                .order_by(Household.code)
            ).all()
        )

    payloads = [
        call(
            "GET",
            f"/api/v1/households/{household_id}/client-experience?analysis_date=2026-08-04",
        ).json()
        for _, household_id in household_rows
    ]
    assert [code for code, _ in household_rows] == ["DEMO_A", "DEMO_B", "DEMO_C"]
    assert len({payload["report"]["chapters"][1]["summary"] for payload in payloads}) == 3
    action_signatures = {
        tuple(
            (item["code"], item["amount"])
            for group in payload["action_calendar"][:4]
            for item in group["items"]
        )
        for payload in payloads
    }
    assert len(action_signatures) == 3


def test_privacy_withdrawal_and_human_review_are_versioned_and_audited() -> None:
    household_id = seed_client_demo()
    experience = call(
        "GET",
        f"/api/v1/households/{household_id}/client-experience?analysis_date=2026-08-04",
    ).json()
    consent = next(item for item in experience["privacy"]["consents"] if item["status"] == "active")

    withdrawn = call(
        "POST",
        f"/api/v1/households/{household_id}/privacy/consents/{consent['id']}/withdraw",
        payload={"expected_version": consent["record_version"], "reason": "客户测试撤回"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "withdrawn"
    assert withdrawn.json()["record_version"] == consent["record_version"] + 1

    stale = call(
        "POST",
        f"/api/v1/households/{household_id}/privacy/consents/{consent['id']}/withdraw",
        payload={"expected_version": consent["record_version"], "reason": "重复提交"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"

    review = call(
        "POST",
        f"/api/v1/households/{household_id}/privacy/human-review-requests",
        payload={"reason": "请人工解释高风险边界", "context": "stage_nine_test"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "queued"
    assert review.json()["queue"] == "demo_advisor_queue"

    with SessionLocal() as session:
        events = list(
            session.scalars(
                select(AuditEvent)
                .where(AuditEvent.household_id == household_id)
                .order_by(AuditEvent.occurred_at)
            ).all()
        )
        assert any(event.event_type == AuditEventType.CONSENT_WITHDRAWN for event in events)
        review_event = next(event for event in events if event.id == review.json()["request_id"])
        assert review_event.event_type == AuditEventType.REVIEW_RECORDED
        assert review_event.actor_role == "client"
        assert review_event.evidence["context"] == "stage_nine_test"
