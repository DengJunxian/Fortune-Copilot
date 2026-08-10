from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.main import app
from app.models.family import Household
from app.models.governance import AuditEvent
from app.schemas.integrations import IntegrationRequest
from app.services.integrations.registry import default_registry
from app.services.public_data.rules import load_public_data_snapshot
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
FINANCIAL_RULES_PATH = "../data/rules/financial_health_v1.json"
PLANNING_RULES_PATH = "../data/rules/planning_waterfall_v1.json"
METHODOLOGY_RULES_PATH = "../data/rules/wealth_methodology_v3.json"
PUBLIC_DATA_PATH = "../data/public/authoritative_public_snapshot_v1.json"


def call(
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
    role: str | None = None,
) -> Response:
    async def _request() -> Response:
        transport = ASGITransport(app=app)
        headers = {"X-Actor-ID": f"integration-{role}", "X-Actor-Role": role} if role else None
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json_payload, headers=headers)

    return asyncio.run(_request())


def test_authoritative_public_snapshot_is_source_attributed_and_not_live() -> None:
    response = call("GET", "/api/v1/public-data/authoritative-snapshot")
    assert response.status_code == 200, response.text
    payload = response.json()
    snapshot = payload["snapshot"]
    assert len(payload["integrity_hash"]) == 64
    assert payload["update_mode"] == "controlled_snapshot_not_runtime_scraping"
    assert snapshot["official_cpi"]["is_cpi"] is True
    assert snapshot["official_cpi"]["is_demo"] is False
    assert snapshot["living_cost_observation"]["can_be_used_as_cpi"] is False
    assert snapshot["regional_living_cost_observations"]["320100"]["amount"] == (
        "44578.00"
    )
    assert snapshot["regional_living_cost_observations"]["440100"]["amount"] == (
        "49177.00"
    )
    assert all(
        item["can_be_used_as_cpi"] is False
        for item in snapshot["regional_living_cost_observations"].values()
    )
    assert snapshot["regional_minimum_wages"]["330100"]["values"][-1][
        "monthly_amount"
    ] == "2490.00"
    assert snapshot["regional_minimum_wages"]["440100"]["values"][-1][
        "monthly_amount"
    ] == "2500.00"
    assert all(
        item["source_reference"].startswith("https://")
        for item in snapshot["policy_sources"]
    )


def test_public_snapshot_rejects_non_official_source_host(tmp_path: Path) -> None:
    source = Path(PUBLIC_DATA_PATH)
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["official_cpi"]["source_reference"] = "https://example.com/fake-cpi"
    target = tmp_path / "tampered-public-data.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    try:
        load_public_data_snapshot(str(target))
    except AppError as exc:
        assert exc.code == "public_data_source_not_allowlisted"
    else:
        raise AssertionError("non-official public-data host must fail closed")


def test_private_bank_ports_and_production_readiness_fail_closed() -> None:
    readiness = call("GET", "/api/v1/integrations/readiness")
    assert readiness.status_code == 200, readiness.text
    payload = readiness.json()
    assert payload["production_ready"] is False
    assert payload["has_live_icbc_connection"] is False
    assert payload["has_live_government_connection"] is False
    by_code = {item["capability"]: item for item in payload["capabilities"]}
    assert by_code["regional_public_data_pipeline"]["execution_allowed"] is True
    for code in (
        "identity_access_management",
        "kyc_cdd_edd_aml",
        "bank_account_and_cashflow_data",
        "product_master_and_channel_inventory",
        "transaction_suitability_order_settlement_positions",
        "advisor_crm_and_human_accountability",
        "market_property_regime_committee",
    ):
        assert by_code[code]["execution_allowed"] is False
        assert by_code[code]["production_blocking"] is True

    try:
        default_registry.execute(
            "bank_account_and_cashflow_data",
            IntegrationRequest(
                request_id="fail-closed-test",
                purpose="读取已授权账户事实",
            ),
        )
    except AppError as exc:
        assert exc.code == "external_integration_unavailable"
        assert exc.status_code == 503
        assert exc.details["mock_substitution_allowed"] is False
    else:
        raise AssertionError("unconfigured bank-private adapter must fail closed")


def test_demo_readiness_checks_local_dependencies_without_claiming_production_ready() -> None:
    response = call("GET", "/api/v1/health/ready")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["production_integrations_ready"] is False
    assert payload["blocking_dependencies"] == []


def test_production_readiness_returns_503_without_bank_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = Settings(
        _env_file=None,
        APP_ENV="production",
        CORS_ORIGINS="https://fortune.example",
        DEMO_AUTH_ENABLED=False,
        SESSION_SIGNING_KEY="production-session-signing-key-at-least-32-characters",
    )
    monkeypatch.setattr("app.api.v1.endpoints.health.get_settings", lambda: production)
    response = call("GET", "/api/v1/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert "identity_access_management" in payload["blocking_dependencies"]


def test_model_governance_blocks_drift_and_records_audit() -> None:
    payload: dict[str, object] = {
        "model_id": "explanation-model",
        "model_version": "candidate-v1",
        "risk_class": "high",
        "observed_at": datetime(2026, 8, 8, tzinfo=UTC).isoformat(),
        "sample_size": 1500,
        "minimum_group_sample_size": 80,
        "input_drift_score": "0.30",
        "output_drift_score": "0.04",
        "fairness_max_gap": "0.03",
        "unsupported_fact_rate": "0.001",
        "availability_rate": "0.999",
        "independent_validation_completed": True,
        "data_security_review_completed": True,
        "explainability_review_completed": True,
        "approval_reference": "independent-validation-case-2026-001",
        "baseline_version": "production-baseline-v1",
    }
    response = call(
        "POST",
        "/api/v1/security/model-governance/evaluate",
        json_payload=payload,
        role="compliance",
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["decision"] == "block"
    assert result["production_eligible"] is False
    assert result["deterministic_fallback_required"] is True
    controls = {item["code"]: item for item in result["controls"]}
    assert controls["input_drift"]["status"] == "block"
    assert set(result["allowed_llm_tasks"]) == {
        "information_extraction",
        "explanation",
        "rag",
        "report",
    }
    with SessionLocal() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "ModelGovernanceEvaluation"
            )
        )
        assert event is not None
        assert event.evidence["metric_source_attested_by_bank"] is False


def test_planning_uses_public_cpi_and_wage_versions_in_decision_evidence() -> None:
    with SessionLocal() as session:
        seeded = seed_synthetic_data(
            session,
            DATASET_PATH,
            rules_path=FINANCIAL_RULES_PATH,
            planning_rules_path=PLANNING_RULES_PATH,
            methodology_rules_path=METHODOLOGY_RULES_PATH,
            reset=True,
        )
        household_id = session.scalar(select(Household.id).where(Household.code == "DEMO_A"))
        assert seeded.loaded == 3
        assert household_id is not None

    response = call(
        "GET",
        f"/api/v1/households/{household_id}/planning?analysis_date=2026-08-08",
        role="client",
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    methodology = payload["methodology"]
    evidence = payload["decision_evidence"]
    official = next(
        item
        for item in methodology["purchasing_power_hurdle"]["components"]
        if item["code"] == "official_cpi_trend"
    )
    assert official["rate"] == "0.009000"
    assert official["version"] == "nbs-cpi-2026-jan-apr-v1"
    assert evidence["public_data_snapshot_version"] == "authoritative-public-cn-2026-08-08"
    assert payload["meta"]["public_data_snapshot_version"] == evidence[
        "public_data_snapshot_version"
    ]
