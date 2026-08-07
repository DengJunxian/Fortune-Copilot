from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from io import BytesIO
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from pypdf import PdfReader
from pytest import MonkeyPatch
from sqlalchemy import inspect, select

from app.core.database import SessionLocal
from app.domain.enums import AuditEventType
from app.main import app
from app.models.family import Household
from app.models.governance import ActionItem, AuditEvent, PlanReport
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
PORTFOLIO_RULES_PATH = "../data/rules/portfolio_policy_v1.json"
PRODUCT_CATALOG_PATH = "../data/products/mock_products_v1.json"
TWIN_RULES_PATH = "../data/rules/twin_simulation_v1.json"
BEHAVIOR_RULES_PATH = "../data/rules/behavior_finance_v1.json"
KNOWLEDGE_PATH = "../data/knowledge/controlled_knowledge_v1.json"

FORMAL_TITLES = [
    "家庭基础情况",
    "理财目标",
    "大额支出计划",
    "理财假设",
    "家庭财务报表",
    "家庭财务比率分析",
    "投资规划建议",
    "免责声明",
]


async def api_request(
    method: str,
    path: str,
    *,
    role: str = "client",
    payload: Mapping[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={"X-Actor-ID": f"report-{role}", "X-Actor-Role": role},
        )


def call(
    method: str,
    path: str,
    *,
    role: str = "client",
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, role=role, payload=payload))


def seed_demo_b() -> str:
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


def generate(household_id: str, *, role: str = "client") -> dict[str, Any]:
    response = call(
        "POST",
        f"/api/v1/households/{household_id}/reports",
        role=role,
        payload={
            "analysis_date": "2026-08-04",
            "trigger": "manual",
            "reason": "提示词十一自动报告测试",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_one_click_report_is_exactly_eight_chapters_and_all_key_numbers_are_traced() -> None:
    household_id = seed_demo_b()
    with SessionLocal() as session:
        inspector = inspect(session.get_bind())
        report_constraints = {
            item["name"] for item in inspector.get_unique_constraints("plan_reports")
        }
        action_constraints = {
            item["name"] for item in inspector.get_unique_constraints("action_items")
        }
        assert "uq_plan_reports_household_sequence" in report_constraints
        assert "uq_action_items_household_action_code" in action_constraints
    empty = call("GET", f"/api/v1/households/{household_id}/reports/current")
    assert empty.status_code == 200
    assert empty.json() is None

    report = generate(household_id)
    assert report["chapter_count"] == 8
    assert [item["number"] for item in report["chapters"]] == list(range(1, 9))
    assert [item["title"] for item in report["chapters"]] == FORMAL_TITLES
    assert [item["code"] for item in report["chapters"][6]["sections"]] == [
        f"7.{index}" for index in range(1, 14)
    ]
    fund_section = report["chapters"][6]["sections"][12]
    assert fund_section["title"] == "真实基金智能投顾补充"
    assert "六位代码" in fund_section["tables"][0]["columns"]
    assert report["versions"]["fund_advisory_catalog_version"] == "1.0.0"
    assert report["consistency_status"] == "passed"
    assert report["mock_mode_supported"] is True
    assert report["versions"]["model_version"].startswith("mock-template")
    assert report["versions"]["prompt_version"] == "formal-eight-chapter-contract-v1.0.0"
    assert report["status"] == "draft_requires_human_review"
    assert report["execution_metrics"]["total"] >= 12

    ledger = {item["code"]: item for item in report["numeric_ledger"]}
    assert ledger["balance.total_assets"]["raw_value"] == "2850000.00"
    assert ledger["balance.total_liabilities"]["raw_value"] == "1208000.00"
    assert ledger["balance.net_worth"]["raw_value"] == "1642000.00"
    assert all(
        item["calculation_source"]
        in {
            "deterministic_tools",
            "deterministic_simulation_engine",
            "deterministic_review_schedule",
        }
        for item in report["numeric_ledger"]
    )
    assert len(report["numeric_ledger"]) > 150
    assert report["report_hash"] != "pending"

    citation_ids = {item["citation_id"] for item in report["citations"]}
    assert citation_ids
    assert all(set(claim["citation_ids"]) <= citation_ids for claim in report["sourced_claims"])
    assert all(item["last_verified_date"] for item in report["citations"])


def test_html_and_pdf_exports_are_self_contained_openable_and_audited() -> None:
    household_id = seed_demo_b()
    report = generate(household_id)
    report_id = report["report_id"]

    html = call("GET", f"/api/v1/reports/{report_id}/html", role="advisor")
    assert html.status_code == 200, html.text
    assert html.headers["content-type"].startswith("text/html")
    assert html.headers["x-report-hash"] == report["report_hash"]
    text = html.text
    assert "<script" not in text.casefold()
    assert "@import" not in text.casefold()
    assert all(title in text for title in FORMAL_TITLES)
    assert len(re.findall(r"<h2>", text)) == 8
    assert "<h2>目录</h2>" not in text
    assert "<h2>附录" not in text
    assert "报告结束" in text
    assert "重大决定必须人工复核" in text

    pdf = call("GET", f"/api/v1/reports/{report_id}/pdf", role="advisor")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf.content))
    assert len(reader.pages) >= 8
    assert reader.metadata is not None
    assert reader.metadata.title == report["title"]

    with SessionLocal() as session:
        events = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == report_id,
                    AuditEvent.event_type == AuditEventType.REPORT_EXPORT_SUCCEEDED,
                )
            ).all()
        )
        assert {item.evidence["format"] for item in events} == {"html", "pdf"}
        assert all(item.evidence["diagnostics"]["sha256"] for item in events)
        assert all(
            item.evidence["diagnostics"].get("font_bundled_in_repository") is False
            for item in events
            if item.evidence["format"] == "pdf"
        )


def test_pdf_render_failure_returns_safe_error_and_persists_diagnostics(
    monkeypatch: MonkeyPatch,
) -> None:
    household_id = seed_demo_b()
    report = generate(household_id)

    def fail_render(_: object) -> tuple[bytes, dict[str, object]]:
        raise RuntimeError("simulated CJK font registration failure")

    monkeypatch.setattr(
        "app.api.v1.endpoints.reports.render_formal_pdf",
        fail_render,
    )
    response = call(
        "GET",
        f"/api/v1/reports/{report['report_id']}/pdf",
        role="advisor",
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "report_export_failed"
    diagnostic_id = response.json()["error"]["details"]["diagnostic_event_id"]

    with SessionLocal() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.id == diagnostic_id,
                AuditEvent.event_type == AuditEventType.REPORT_EXPORT_FAILED,
            )
        )
        assert event is not None
        assert event.evidence["format"] == "pdf"
        assert event.evidence["diagnostics"] == {
            "stage": "render",
            "error_type": "RuntimeError",
            "error_message": "simulated CJK font registration failure",
            "report_version": report["versions"]["report_version"],
        }


def test_action_completion_defer_and_not_applicable_create_new_snapshots_and_metrics() -> None:
    household_id = seed_demo_b()
    initial = generate(household_id)
    actions_response = call("GET", f"/api/v1/households/{household_id}/report-actions")
    assert actions_response.status_code == 200
    actions = actions_response.json()["items"]
    assert len(actions) == initial["execution_metrics"]["total"]

    updates = [
        (actions[0], "completed", None),
        (actions[1], "deferred", "2026-09-04"),
        (actions[2], "not_applicable", None),
    ]
    latest_sequence = 1
    for action, next_status, deferred_until in updates:
        payload: dict[str, Any] = {
            "status": next_status,
            "expected_version": action["record_version"],
            "reason": f"测试标记为 {next_status}",
        }
        if deferred_until:
            payload["deferred_until"] = deferred_until
        response = call(
            "POST",
            f"/api/v1/households/{household_id}/report-actions/{action['action_code']}",
            payload=payload,
        )
        assert response.status_code == 200, response.text
        result = response.json()
        latest_sequence += 1
        assert result["action"]["status"] == next_status
        assert result["report"]["sequence"] == latest_sequence

    current = call("GET", f"/api/v1/households/{household_id}/reports/current").json()
    assert current["sequence"] == 4
    assert current["execution_metrics"]["completed"] == 1
    assert current["execution_metrics"]["deferred"] == 1
    assert current["execution_metrics"]["not_applicable"] == 1

    old = call("GET", f"/api/v1/reports/{initial['report_id']}").json()
    assert old["execution_metrics"]["completed"] == 0
    assert old["execution_metrics"]["deferred"] == 0

    denied = call(
        "GET",
        f"/api/v1/households/{household_id}/reports/generation-chain",
        role="client",
    )
    assert denied.status_code == 403
    chain_response = call(
        "GET",
        f"/api/v1/households/{household_id}/reports/generation-chain",
        role="compliance",
    )
    assert chain_response.status_code == 200
    chain = chain_response.json()
    assert chain["chain_verified"] is True
    assert [item["sequence"] for item in chain["items"]] == [1, 2, 3, 4]

    with SessionLocal() as session:
        records = list(
            session.scalars(
                select(PlanReport)
                .where(PlanReport.household_id == household_id)
                .order_by(PlanReport.sequence)
            ).all()
        )
        assert len(records) == 4
        assert sum(item.is_current for item in records) == 1
        persisted = list(
            session.scalars(
                select(ActionItem).where(
                    ActionItem.household_id == household_id,
                    ActionItem.data_source == "formal-report-action-calendar-v1.0.0",
                )
            ).all()
        )
        assert {item.status for item in persisted} >= {
            "completed",
            "deferred",
            "not_applicable",
        }
        event_types = set(
            session.scalars(
                select(AuditEvent.event_type).where(AuditEvent.household_id == household_id)
            ).all()
        )
        assert AuditEventType.REPORT_ACTION_UPDATED in event_types
        assert AuditEventType.REPORT_RECALCULATED in event_types


def test_monthly_and_major_event_recalculation_append_history_without_overwrite() -> None:
    household_id = seed_demo_b()
    first = generate(household_id, role="advisor")
    monthly = call(
        "POST",
        f"/api/v1/households/{household_id}/reports/recalculate",
        role="advisor",
        payload={
            "analysis_date": "2026-08-04",
            "trigger": "monthly_review",
            "reason": "月度家庭事实复盘",
            "expected_report_sequence": 1,
        },
    )
    assert monthly.status_code == 200, monthly.text
    assert monthly.json()["sequence"] == 2
    assert monthly.json()["parent_report_id"] == first["report_id"]

    major = call(
        "POST",
        f"/api/v1/households/{household_id}/reports/recalculate",
        role="advisor",
        payload={
            "analysis_date": "2026-08-04",
            "trigger": "major_event",
            "reason": "家庭收入发生重大变化后重算",
            "expected_report_sequence": 2,
        },
    )
    assert major.status_code == 200, major.text
    assert major.json()["sequence"] == 3
    assert major.json()["generation_trigger"] == "major_event"

    stale = call(
        "POST",
        f"/api/v1/households/{household_id}/reports/recalculate",
        role="advisor",
        payload={
            "analysis_date": "2026-08-04",
            "trigger": "monthly_review",
            "reason": "陈旧版本重算",
            "expected_report_sequence": 1,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "report_version_conflict"


def test_compliance_can_read_chain_but_cannot_generate_or_change_family_actions() -> None:
    household_id = seed_demo_b()
    report = generate(household_id)
    actions = call(
        "GET",
        f"/api/v1/households/{household_id}/report-actions",
        role="compliance",
    ).json()["items"]
    blocked_generate = call(
        "POST",
        f"/api/v1/households/{household_id}/reports",
        role="compliance",
        payload={"reason": "合规越权生成", "trigger": "manual"},
    )
    assert blocked_generate.status_code == 403
    blocked_action = call(
        "POST",
        f"/api/v1/households/{household_id}/report-actions/{actions[0]['action_code']}",
        role="compliance",
        payload={
            "status": "completed",
            "expected_version": actions[0]["record_version"],
            "reason": "合规越权完成",
        },
    )
    assert blocked_action.status_code == 403
    readable = call("GET", f"/api/v1/reports/{report['report_id']}", role="compliance")
    assert readable.status_code == 200
    chain = call(
        "GET",
        f"/api/v1/households/{household_id}/reports/generation-chain",
        role="compliance",
    )
    assert chain.status_code == 200
    assert chain.json()["chain_verified"] is True


def test_client_cannot_read_or_generate_a_pre_compliance_internal_report() -> None:
    household_id = seed_demo_b()
    workflow = call(
        "POST",
        f"/api/v1/households/{household_id}/plan-workflows",
        role="advisor",
        payload={"reason": "建立合规前正式报告可见性测试"},
    )
    assert workflow.status_code == 201, workflow.text

    report = generate(household_id, role="advisor")
    assert report["status"] == "workflow_linked"

    blocked_paths = [
        f"/api/v1/households/{household_id}/reports/current",
        f"/api/v1/households/{household_id}/report-actions",
        f"/api/v1/reports/{report['report_id']}",
        f"/api/v1/reports/{report['report_id']}/html",
        f"/api/v1/reports/{report['report_id']}/pdf",
    ]
    for path in blocked_paths:
        response = call("GET", path, role="client")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "report_not_ready_for_client"

    blocked_generate = call(
        "POST",
        f"/api/v1/households/{household_id}/reports",
        role="client",
        payload={
            "analysis_date": "2026-08-04",
            "trigger": "manual",
            "reason": "客户尝试生成内部审核关联报告",
        },
    )
    assert blocked_generate.status_code == 403
    assert blocked_generate.json()["error"]["code"] == "report_not_ready_for_client"
