from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.family import Household
from app.models.family_enterprise import (
    EnterpriseGuarantee,
    EnterpriseOwnership,
    EnterpriseProfile,
    EnterpriseValuation,
)
from app.schemas.seed import SyntheticDataset
from app.services.seed import read_dataset, seed_synthetic_data

DATASET_PATH = "../data/synthetic/v5_personas/personas_v2.json"


async def _api_request(
    method: str,
    path: str,
    *,
    role: str = "admin",
    headers: Mapping[str, str] | None = None,
) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json={},
            headers={
                "X-Actor-ID": f"v5-persona-{role}",
                "X-Actor-Role": role,
                **(dict(headers) if headers else {}),
            },
        )


def _call(
    method: str,
    path: str,
    *,
    role: str = "admin",
    headers: Mapping[str, str] | None = None,
) -> Response:
    return asyncio.run(_api_request(method, path, role=role, headers=headers))


def test_persona_v2_schema_enforces_grain_references_and_eight_archetypes() -> None:
    dataset = read_dataset(DATASET_PATH)
    assert dataset.schema_version == "canonical-v5-persona-v2"
    assert [item.household.code for item in dataset.households] == [
        f"DEMO_{letter}" for letter in "ABCDEFGH"
    ]
    assert len(dataset.personas) == 8
    assert {item.household.demo_profile for item in dataset.households} == set("ABCDEFGH")
    assert len(dataset.enterprise_extensions) == 3
    assert all(item.household.is_synthetic for item in dataset.households)

    duplicate = dataset.model_dump(mode="python")
    duplicate["households"][1]["household"]["code"] = "DEMO_A"
    with pytest.raises(ValidationError, match="code 必须在家庭粒度唯一"):
        SyntheticDataset.model_validate(duplicate)


def test_v5_seed_maps_stable_references_to_canonical_enterprise_records_idempotently() -> None:
    with SessionLocal() as session:
        first = seed_synthetic_data(session, DATASET_PATH, reset=True)
        second = seed_synthetic_data(session, DATASET_PATH)
        assert first.loaded == 8
        assert first.enterprise_profiles_loaded == 3
        assert first.enterprise_exposures_refreshed == 3
        assert second.loaded == 0
        assert second.skipped == 8
        assert second.enterprise_profiles_loaded == 0
        assert second.enterprise_exposures_refreshed == 0
        assert session.scalar(select(func.count()).select_from(Household)) == 8
        assert session.scalar(select(func.count()).select_from(EnterpriseProfile)) == 3
        assert session.scalar(select(func.count()).select_from(EnterpriseOwnership)) == 3
        assert session.scalar(select(func.count()).select_from(EnterpriseValuation)) == 3
        assert session.scalar(select(func.count()).select_from(EnterpriseGuarantee)) == 1


def test_release_benchmark_v2_runs_same_pipeline_for_all_personas() -> None:
    get_settings.cache_clear()
    denied = _call("POST", "/api/v1/demo/v5/release-benchmark", role="client")
    assert denied.status_code == 403
    unconfirmed = _call("POST", "/api/v1/demo/v5/release-benchmark")
    assert unconfirmed.status_code == 409
    response = _call(
        "POST",
        "/api/v1/demo/v5/release-benchmark",
        headers={"X-Confirm-Action": "run_v5_release_benchmark"},
    )
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    assert payload["passed"] is True
    assert payload["external_network_calls"] == 0
    assert payload["dataset_quality"]["household_count"] == 8
    assert payload["dataset_quality"]["passed"] is True
    assert [item["household_code"] for item in payload["personas"]] == [
        f"DEMO_{letter}" for letter in "ABCDEFGH"
    ]
    assert all(item["passed"] for item in payload["personas"])
    assert all(item["decision_replay"] for item in payload["personas"])
    assert all(item["financial_correct"] for item in payload["personas"])
    metrics = {item["code"]: item for item in payload["metrics"]}
    assert set(metrics) == {
        "profile_completeness",
        "wealth_need_coverage",
        "cfs_coverage",
        "no_action_correctness",
        "product_ranking_conflict_independence",
        "advisor_trigger_precision",
        "invalid_alert_rate",
        "decision_replay",
        "financial_correctness",
    }
    assert all(item["passed"] for item in metrics.values())
    assert metrics["invalid_alert_rate"]["value"] == "0"
    founder = next(item for item in payload["personas"] if item["household_code"] == "DEMO_D")
    assert founder["normalized_outcome"]["profile"]["enterprise_dependency_level"] == "high"
    assert founder["normalized_outcome"]["enterprise"][
        "family_liquidity_isolation_exists"
    ] is True
    assert founder["additional_risk_allowed"] is False


def test_founder_funding_story_reaches_confirmation_and_new_snapshot() -> None:
    get_settings.cache_clear()
    unconfirmed = _call("POST", "/api/v1/demo/v5/founder-story")
    assert unconfirmed.status_code == 409
    response = _call(
        "POST",
        "/api/v1/demo/v5/founder-story",
        headers={"X-Confirm-Action": "run_founder_story"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["passed"] is True
    assert payload["household_code"] == "DEMO_D"
    assert len(payload["stages"]) == 14
    assert all(item["passed"] for item in payload["stages"])
    assert payload["initial_snapshot_id"] != payload["funding_snapshot_id"]
    assert payload["funding_snapshot_id"] != payload["confirmed_snapshot_id"]
    by_code = {item["code"]: item for item in payload["stages"]}
    assert by_code["profile_change"]["evidence"]["enterprise_dependency"] == "high"
    assert by_code["risk_budget_change"]["evidence"]["additional_risk_allowed"] is False
    assert "enterprise_dependency" in by_code["advisor_trigger"]["evidence"]["alert_types"]
    assert by_code["scenario_lab"]["evidence"]["status"] == "completed"
    assert by_code["client_confirmation"]["evidence"]["signature_status"] == "confirmed"
