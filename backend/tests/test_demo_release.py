from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.main import app
from app.models.demo import DemoRun, ExperimentSuiteRun
from app.models.governance import AuditEvent
from app.services.demo_backup import backup_demo_database, restore_demo_database


async def api_request(
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    request_headers = {
        "X-Actor-ID": f"demo-release-{role}",
        "X-Actor-Role": role,
        **(dict(headers) if headers else {}),
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, json=payload, headers=request_headers)


def call(
    method: str,
    path: str,
    *,
    role: str = "admin",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, role=role, payload=payload, headers=headers))


def load_demo() -> None:
    response = call("POST", "/api/v1/demo/load")
    assert response.status_code == 200, response.text


def test_demo_controls_are_synthetic_only_admin_guarded_and_confirmed() -> None:
    empty = call("GET", "/api/v1/demo/manifest", role="client")
    assert empty.status_code == 200
    assert empty.json()["ready"] is False

    denied = call("POST", "/api/v1/demo/load", role="client")
    assert denied.status_code == 403
    load_demo()
    loaded = call("GET", "/api/v1/demo/manifest", role="advisor").json()
    assert loaded["ready"] is True
    assert loaded["seeded_household_count"] == 8
    assert loaded["mock_mode"] is True
    assert loaded["external_network_required"] is False

    unconfirmed = call("POST", "/api/v1/demo/reset")
    assert unconfirmed.status_code == 409
    reset = call(
        "POST",
        "/api/v1/demo/reset",
        headers={"X-Confirm-Action": "reset_synthetic_demo"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["removed"] == 8
    assert reset.json()["loaded"] == 8


def test_preheat_and_three_family_comparison_prove_dynamic_configurations() -> None:
    load_demo()
    warmed = call("POST", "/api/v1/demo/preheat")
    assert warmed.status_code == 200, warmed.text
    assert warmed.json()["external_network_calls"] == 0
    assert "three_family_comparison" in warmed.json()["warmed_components"]

    comparison = call("GET", "/api/v1/demo/families/comparison", role="compliance")
    assert comparison.status_code == 200, comparison.text
    payload = comparison.json()
    assert payload["fixed_ratio_model"] is False
    assert payload["unique_configuration_count"] == 3
    assert {item["code"] for item in payload["rows"]} == {"DEMO_A", "DEMO_B", "DEMO_C"}
    signatures = {item["configuration_signature"] for item in payload["rows"]}
    assert len(signatures) == 3
    assert all(len(item["accounts"]) == 4 for item in payload["rows"])


def test_one_click_main_demo_and_seven_experiments_are_durable_and_offline() -> None:
    load_demo()
    response = call("POST", "/api/v1/demo/runs", payload={"path_count": 100})
    assert response.status_code == 201, response.text
    demo = response.json()
    assert demo["status"] == "completed", demo
    assert demo["progress_percent"] == 100
    assert demo["offline_mode"] is True
    assert demo["external_network_required"] is False
    assert len(demo["stages"]) == 10
    assert all(item["status"] == "completed" for item in demo["stages"])
    assert demo["artifacts"]["diagnosis"]["credit_limit_in_assets"] is False
    assert float(demo["artifacts"]["diagnosis"]["property_concentration"]) > 0.8
    assert float(demo["artifacts"]["diagnosis"]["protection_gap"]) > 0
    assert demo["artifacts"]["planning"]["education_goal"]["months_remaining"] == 120
    assert demo["artifacts"]["planning"]["fixed_ratio_model"] is False
    assert demo["artifacts"]["planning"]["growth_70_total_assets_interpretation"] is False
    assert demo["artifacts"]["twin"]["scenario_codes"] == [
        "unemployment_equity_down_30"
    ]
    assert demo["artifacts"]["twin"]["common_random_numbers"] is True
    assert demo["artifacts"]["behavior"]["loss_aversion"]["severity"] == "high"
    assert demo["artifacts"]["review"]["hash_chain_verified"] is True
    assert demo["artifacts"]["report"]["chapter_count"] == 8
    assert len(demo["artifacts"]["report"]["chapter_titles"]) == 8
    assert demo["artifacts"]["audit"]["agent_step_count"] == 9
    assert all(demo["metrics"]["target_results"].values())

    client_delivery = call(
        "GET",
        f"/api/v1/households/{demo['household_id']}/client-experience?analysis_date=2026-08-04",
        role="client",
    )
    assert client_delivery.status_code == 200, client_delivery.text
    assert client_delivery.json()["delivery"] == {
        "report": "under_review",
        "workflow": "under_review",
        "actions": "under_review",
        "explanation": "内部草稿仍在顾问或合规审核中；客户端只显示确定性预览。",
    }

    suite_response = call("POST", "/api/v1/demo/experiments/run", role="compliance")
    assert suite_response.status_code == 200, suite_response.text
    suite = suite_response.json()
    assert suite["passed"] is True, suite
    assert suite["real_bank_results_claimed"] is False
    assert len(suite["cases"]) == 7
    assert {item["status"] for item in suite["cases"]} <= {"passed", "protocol_ready"}
    comprehension = next(item for item in suite["cases"] if item["code"] == "user_comprehension")
    advisor_time = next(item for item in suite["cases"] if item["code"] == "advisor_process_time")
    assert comprehension["measured"] is False
    assert comprehension["metrics"]["observed_participants"] == 0
    assert advisor_time["measured"] is False

    with SessionLocal() as session:
        run = session.scalar(select(DemoRun).where(DemoRun.id == demo["run_id"]))
        experiment = session.scalar(
            select(ExperimentSuiteRun).where(ExperimentSuiteRun.id == suite["run_id"])
        )
        assert run is not None and run.status == "completed"
        assert experiment is not None and experiment.passed is True
        event_types = {
            item.event_type.value
            for item in session.scalars(
                select(AuditEvent).where(AuditEvent.household_id == run.household_id)
            )
        }
        assert "demo_run_completed" in event_types
        assert "experiment_suite_completed" in event_types

    no_retry = call("POST", f"/api/v1/demo/runs/{demo['run_id']}/retry")
    assert no_retry.status_code == 409


def _create_release_database(
    path: Path,
    *,
    synthetic_only: bool = True,
    household_codes: tuple[str, ...] = ("DEMO_A", "DEMO_B", "DEMO_C"),
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);
            CREATE TABLE households (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_synthetic INTEGER NOT NULL,
                is_deleted INTEGER NOT NULL
            );
            CREATE TABLE demo_runs (id TEXT PRIMARY KEY);
            CREATE TABLE experiment_suite_runs (id TEXT PRIMARY KEY);
            """
        )
        connection.execute("INSERT INTO alembic_version VALUES ('0013_demo_release')")
        for code in household_codes:
            connection.execute(
                "INSERT INTO households VALUES (?, ?, 1, 0)", (code, f"{code} 初始")
            )
        if not synthetic_only:
            connection.execute(
                "INSERT INTO households VALUES ('REAL', '非合成家庭', 0, 0)"
            )


def test_demo_backup_restore_is_verified_synthetic_only_and_recoverable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wealthtwin.db"
    backup = tmp_path / "backups" / "release.sqlite"
    _create_release_database(database)
    settings = Settings(APP_ENV="test", DATABASE_URL=f"sqlite:///{database}")

    backup_result = backup_demo_database(settings, backup)
    assert backup_result.synthetic_only is True
    assert backup_result.household_codes == ["DEMO_A", "DEMO_B", "DEMO_C"]
    assert backup.is_file()
    assert Path(f"{backup}.manifest.json").is_file()

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE households SET name = '已修改' WHERE code = 'DEMO_B'")
    restored = restore_demo_database(
        settings, backup, confirmation="restore_synthetic_demo"
    )
    assert restored.recovery_artifact is not None
    assert Path(restored.recovery_artifact).is_file()
    with sqlite3.connect(database) as connection:
        name = connection.execute(
            "SELECT name FROM households WHERE code = 'DEMO_B'"
        ).fetchone()[0]
    assert name == "DEMO_B 初始"

    unsafe = tmp_path / "unsafe.sqlite"
    _create_release_database(unsafe, synthetic_only=False)
    with pytest.raises(AppError, match="非合成家庭"):
        backup_demo_database(
            Settings(APP_ENV="test", DATABASE_URL=f"sqlite:///{unsafe}"),
            tmp_path / "unsafe-backup.sqlite",
        )


def test_demo_backup_accepts_v5_persona_set_and_rejects_partial_sets(tmp_path: Path) -> None:
    v5_database = tmp_path / "v5.sqlite"
    v5_codes = tuple(f"DEMO_{letter}" for letter in "ABCDEFGH")
    _create_release_database(v5_database, household_codes=v5_codes)
    settings = Settings(APP_ENV="test", DATABASE_URL=f"sqlite:///{v5_database}")
    result = backup_demo_database(settings, tmp_path / "v5-backup.sqlite")
    assert result.household_codes == list(v5_codes)

    partial_database = tmp_path / "partial.sqlite"
    _create_release_database(partial_database, household_codes=v5_codes[:-1])
    with pytest.raises(AppError, match="V5 A-H"):
        backup_demo_database(
            Settings(APP_ENV="test", DATABASE_URL=f"sqlite:///{partial_database}"),
            tmp_path / "partial-backup.sqlite",
        )
