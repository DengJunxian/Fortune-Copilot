from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from pytest import MonkeyPatch
from sqlalchemy import func, select

from app.api.v1.endpoints import calibration as calibration_endpoint
from app.api.v1.endpoints import liability as liability_endpoint
from app.api.v1.endpoints import reports as reports_endpoint
from app.core.config import Settings
from app.core.database import SessionLocal
from app.domain.enums import CalibrationMode
from app.main import app
from app.models.calibration import CalibrationDataset, CalibrationParameter
from app.models.family import Household
from app.models.governance import PlanReport
from app.services.calibration.registry import (
    build_calibration_catalog,
    build_database_calibration_port,
    ensure_calibration_registry,
    load_calibration_registry,
)
from app.services.governance.evidence import calibration_evidence_section
from app.services.seed import seed_synthetic_data

ANALYSIS_DATE = date(2026, 8, 11)
CALIBRATION_PATH = "../data/calibration/china_purchasing_power_v1.json"


def _settings(*, calibration_enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="sqlite://",
        LLM_PROVIDER="mock",
        ENABLE_V5_LIABILITY_ENGINE=True,
        ENABLE_V5_CALIBRATION=calibration_enabled,
        FINANCIAL_RULES_PATH="../data/rules/financial_health_v1.json",
        PLANNING_RULES_PATH="../data/rules/planning_waterfall_v1.json",
        METHODOLOGY_RULES_PATH="../data/rules/wealth_methodology_v3.json",
        PUBLIC_DATA_SNAPSHOT_PATH="../data/public/authoritative_public_snapshot_v1.json",
        LIABILITY_RULES_PATH="../data/rules/liability_engine_v1.json",
        PORTFOLIO_RULES_PATH="../data/rules/portfolio_policy_v1.json",
        PRODUCT_CATALOG_PATH="../data/products/mock_products_v1.json",
        FUND_ADVISORY_CATALOG_PATH="../data/products/verified_real_funds_v1.json",
        TWIN_RULES_PATH="../data/rules/twin_simulation_v1.json",
        BEHAVIOR_RULES_PATH="../data/rules/behavior_finance_v1.json",
        KNOWLEDGE_BASE_PATH="../data/knowledge/controlled_knowledge_v1.json",
        CALIBRATION_REGISTRY_PATH=CALIBRATION_PATH,
    )


def _seed_household(code: str = "DEMO_B") -> str:
    settings = _settings()
    with SessionLocal() as session:
        seed_synthetic_data(
            session,
            "../data/synthetic/families.json",
            rules_path=settings.financial_rules_path,
            planning_rules_path=settings.planning_rules_path,
            methodology_rules_path=settings.methodology_rules_path,
            portfolio_rules_path=settings.portfolio_rules_path,
            product_catalog_path=settings.product_catalog_path,
            twin_rules_path=settings.twin_rules_path,
            behavior_rules_path=settings.behavior_rules_path,
            knowledge_base_path=settings.knowledge_base_path,
        )
        household_id = session.scalar(select(Household.id).where(Household.code == code))
        assert household_id is not None
        return household_id


async def _api_request(
    method: str,
    path: str,
    *,
    role: str = "advisor",
    payload: Mapping[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=payload,
            headers={"X-Actor-ID": "e13-test", "X-Actor-Role": role},
        )


def _call(
    method: str,
    path: str,
    *,
    role: str = "advisor",
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(_api_request(method, path, role=role, payload=payload))


def _override_settings(monkeypatch: MonkeyPatch, settings: Settings) -> None:
    for module in (calibration_endpoint, liability_endpoint, reports_endpoint):
        monkeypatch.setattr(module, "get_settings", lambda: settings)


def test_calibration_registry_is_valid_idempotent_and_keeps_modes_separate() -> None:
    registry = load_calibration_registry(CALIBRATION_PATH)
    assert registry.registry_version == "china-purchasing-power-calibration-v1.0.0"
    assert {item.mode for item in registry.datasets} == {
        CalibrationMode.CONTROLLED_DEMO,
        CalibrationMode.EMPIRICALLY_CALIBRATED,
    }
    assert CalibrationMode.BANK_AUTHORIZED not in {item.mode for item in registry.datasets}

    with SessionLocal() as session:
        ensure_calibration_registry(session, registry)
        ensure_calibration_registry(session, registry)
        session.commit()
        assert session.scalar(select(func.count()).select_from(CalibrationDataset)) == 5
        assert session.scalar(select(func.count()).select_from(CalibrationParameter)) == 17
        assert all(
            Decimal("0") <= item.confidence <= Decimal("1")
            for item in session.scalars(select(CalibrationParameter))
        )


def test_calibration_port_resolves_scope_and_fails_closed_without_bank_data() -> None:
    with SessionLocal() as session:
        port = build_database_calibration_port(session, CALIBRATION_PATH)
        cpi = port.get_parameter("HCI.official_cpi_anchor", "all", "CN", ANALYSIS_DATE)
        assert cpi.status == "available"
        assert cpi.mode == CalibrationMode.EMPIRICALLY_CALIBRATED
        assert cpi.value == Decimal("0.00900000")

        education = port.get_parameter(
            "HCI.expense_category_rate", "child_education", "330100", ANALYSIS_DATE
        )
        assert education.status == "degraded"
        assert education.mode == CalibrationMode.CONTROLLED_DEMO
        assert education.value == Decimal("0.05000000")

        wage = port.get_parameter("IAI.minimum_wage_cagr", "all", "330100", ANALYSIS_DATE)
        assert wage.status == "available"
        assert wage.mode == CalibrationMode.EMPIRICALLY_CALIBRATED
        assert wage.value == Decimal("0.03707400")

        bank_port = build_database_calibration_port(
            session,
            CALIBRATION_PATH,
            allowed_modes=(CalibrationMode.BANK_AUTHORIZED,),
        )
        unavailable = bank_port.get_parameter("HCI.official_cpi_anchor", "all", "CN", ANALYSIS_DATE)
        assert unavailable.status == "needs_review"
        assert unavailable.value is None
        assert unavailable.mode is None
        assert unavailable.reason == "missing_verified_parameter"
        assert any("禁止静默猜测" in item for item in unavailable.limitations)


def test_catalog_and_decision_evidence_freeze_mode_availability() -> None:
    with SessionLocal() as session:
        catalog = build_calibration_catalog(session, CALIBRATION_PATH)
        evidence = calibration_evidence_section(catalog)

    modes = {item.mode: item for item in catalog.modes}
    assert modes[CalibrationMode.CONTROLLED_DEMO].available is True
    assert modes[CalibrationMode.EMPIRICALLY_CALIBRATED].available is True
    assert modes[CalibrationMode.BANK_AUTHORIZED].available is False
    assert evidence["status"] == "bound"
    assert evidence["version"] == catalog.registry_version
    assert evidence["decision_inputs"]["no_silent_guessing"] is True
    assert {item["mode"] for item in evidence["decision_inputs"]["modes"]} == {
        item.value for item in CalibrationMode
    }


def test_eligible_capital_exposes_distinct_hci_gci_iai_calibration_traces(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = _settings()
    _override_settings(monkeypatch, settings)
    household_id = _seed_household()

    response = _call(
        "GET",
        f"/api/v1/households/{household_id}/eligible-capital?analysis_date={ANALYSIS_DATE}",
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    power = payload["calculation"]["purchasing_power"]

    assert payload["meta"]["calibration_version"] == ("china-purchasing-power-calibration-v1.0.0")
    assert power["calibration_status"] == "degraded"
    assert power["requires_human_review"] is True
    assert set(power["calibration_modes"]) == {
        "controlled_demo",
        "empirically_calibrated",
    }
    hci = power["household_cost_inflation"]
    assert {item["code"] for item in hci["parameter_references"]} >= {
        "HCI.official_cpi_anchor",
        "HCI.expense_category_rate",
    }
    assert all(
        item["code"] == "GCI.annual_growth_assumption"
        for gci in power["goal_cost_inflation"]
        for item in gci["parameter_references"]
    )
    iai = power["income_adequacy"]
    wage = next(
        item for item in iai["parameter_references"] if item["code"] == "IAI.minimum_wage_cagr"
    )
    assert wage["mode"] == "empirically_calibrated"
    assert wage["status"] == "available"


def test_calibration_api_and_report_never_present_demo_as_bank_authorized(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = _settings()
    _override_settings(monkeypatch, settings)
    household_id = _seed_household()

    catalog_response = _call("GET", "/api/v1/calibration/catalog")
    assert catalog_response.status_code == 200, catalog_response.text
    modes = {item["mode"]: item for item in catalog_response.json()["modes"]}
    assert modes["bank_authorized"]["available"] is False

    bank_response = _call(
        "GET",
        "/api/v1/calibration/parameters/HCI.official_cpi_anchor"
        f"?effective_date={ANALYSIS_DATE}&mode=bank_authorized",
    )
    assert bank_response.status_code == 200, bank_response.text
    assert bank_response.json()["status"] == "needs_review"
    assert bank_response.json()["value"] is None

    report_response = _call(
        "POST",
        f"/api/v1/households/{household_id}/reports",
        payload={"analysis_date": str(ANALYSIS_DATE), "reason": "E13 校准报告验收"},
    )
    assert report_response.status_code == 201, report_response.text
    report = report_response.json()
    calibration_table = next(
        table
        for table in report["chapters"][3]["sections"][0]["tables"]
        if table["title"] == "HCI／GCI／IAI 校准模式"
    )
    bank_row = next(row for row in calibration_table["rows"] if row[0] == "银行授权")
    assert bank_row[2] == "当前不可用；禁止自动回退后标成银行授权"
    assert report["versions"]["calibration_version"] == (
        "china-purchasing-power-calibration-v1.0.0"
    )
    assert report["consistency_status"] == "needs_review"
    gate_response = _call(
        "POST",
        f"/api/v1/reports/{report['report_id']}/quality-gate",
        role="compliance",
        payload={
            "human_review_completed": True,
            "reason": "已人工复核受控演示校准边界",
        },
    )
    assert gate_response.status_code == 200, gate_response.text
    gate = gate_response.json()
    assert gate["passed"] is True
    numeric_gate = next(item for item in gate["gates"] if item["code"] == "numeric_consistency")
    assert numeric_gate["status"] == "pass"
    calibration_appendix = next(item for item in report["appendices"] if item["code"] == "F")
    assert {row[1] for row in calibration_appendix["tables"][0]["rows"]} == {
        "controlled_demo",
        "empirically_calibrated",
    }
    with SessionLocal() as session:
        record = session.scalar(select(PlanReport).where(PlanReport.id == report["report_id"]))
        assert record is not None
        assert record.calibration_version == "china-purchasing-power-calibration-v1.0.0"
        assert record.decision_evidence["calibration"]["status"] == "bound"


def test_calibration_api_remains_off_by_default(monkeypatch: MonkeyPatch) -> None:
    settings = _settings(calibration_enabled=False)
    _override_settings(monkeypatch, settings)
    response = _call("GET", "/api/v1/calibration/catalog")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "feature_not_enabled"

    household_id = _seed_household()
    report_response = _call(
        "POST",
        f"/api/v1/households/{household_id}/reports",
        payload={"analysis_date": str(ANALYSIS_DATE), "reason": "验证校准关闭报告"},
    )
    assert report_response.status_code == 201, report_response.text
    calibration_table = next(
        table
        for table in report_response.json()["chapters"][3]["sections"][0]["tables"]
        if table["title"] == "HCI／GCI／IAI 校准模式"
    )
    assert {row[1] for row in calibration_table["rows"]} == {"not_enabled"}
