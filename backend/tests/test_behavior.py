from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.domain.enums import (
    AuditEventType,
    BehaviorInterventionStatus,
    BehaviorSessionStatus,
    LifecycleStage,
    RiskLevel,
)
from app.main import app
from app.models.assessment import BehaviorAssessment, RiskAssessment
from app.models.behavior import (
    BehaviorBiasFinding,
    BehaviorExperimentAssignment,
    BehaviorExperimentResponse,
    BehaviorExperimentSession,
    BehaviorIntervention,
)
from app.models.common import utc_now
from app.models.family import Household
from app.models.governance import AuditEvent, RuleVersion
from app.services.seed import seed_synthetic_data

DATASET_PATH = "../data/synthetic/families.json"
BEHAVIOR_RULES_PATH = "../data/rules/behavior_finance_v1.json"
EXPECTED_PATH = Path("../data/expected/demo_b_behavior_v1.json")

QUESTIONNAIRE_B = {
    "risk_willingness": "0.70",
    "loss_tolerance_claim": "0.80",
    "investment_experience": "0.60",
    "knowledge": "0.60",
    "trading_frequency": "0.50",
    "attention": "0.45",
    "goal_discipline": "0.55",
}


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
            headers={"X-Actor-ID": "behavior-test", "X-Actor-Role": "client"},
        )


def call(
    method: str,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> Response:
    return asyncio.run(api_request(method, path, payload=payload))


def seed_households() -> dict[str, str]:
    with SessionLocal() as session:
        result = seed_synthetic_data(
            session,
            DATASET_PATH,
            behavior_rules_path=BEHAVIOR_RULES_PATH,
        )
        assert result.behavior_rule_version == "1.0.0"
        return {
            item.code: item.id
            for item in session.scalars(select(Household).where(Household.is_deleted.is_(False)))
        }


def _legacy_profile(household_id: str) -> dict[str, Any]:
    response = call("GET", f"/api/v1/households/{household_id}/behavior")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["information_status"] == "sufficient"
    return cast(dict[str, Any], payload["profile"])


def _start_session(household_id: str) -> dict[str, Any]:
    response = call(
        "POST",
        f"/api/v1/households/{household_id}/behavior/sessions",
        payload={"analysis_date": "2026-08-04", "questionnaire": QUESTIONNAIRE_B},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _complete_like_legacy(household_id: str) -> dict[str, Any]:
    legacy = _legacy_profile(household_id)
    started = _start_session(household_id)
    session_id = started["session_id"]
    for expected_count, item in enumerate(legacy["responses"], start=1):
        response = call(
            "POST",
            (
                f"/api/v1/households/{household_id}/behavior/sessions/{session_id}/"
                f"responses/{item['experiment_code']}"
            ),
            payload={
                "choice_code": item["choice_code"],
                "response_time_ms": item["response_time_ms"],
                "modification_count": item["modification_count"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["answered_count"] == expected_count
    completed = call(
        "POST",
        f"/api/v1/households/{household_id}/behavior/sessions/{session_id}/complete",
    )
    assert completed.status_code == 200, completed.text
    return cast(dict[str, Any], completed.json())


def test_behavior_catalog_is_complete_and_versioned() -> None:
    seed_households()
    response = call("GET", "/api/v1/behavior/catalog")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rule_version"] == "1.0.0"
    assert payload["source_type"] == "internal_demo"
    assert len(payload["questionnaire_dimensions"]) == 7
    assert len(payload["experiments"]) == 6
    assert len(payload["bias_definitions"]) == 11
    assert len(payload["intervention_definitions"]) == 12
    assert len(payload["ab_variants"]) == 4
    assert "不得高于客观承担能力" in payload["behavior_boundary"]
    with SessionLocal() as session:
        version = session.scalar(
            select(RuleVersion).where(RuleVersion.code == "behavior_finance_policy")
        )
        assert version is not None
        assert version.semantic_version == "1.0.0"


def test_seed_refreshes_only_authoritative_behavior_inputs_on_existing_demo() -> None:
    household_id = seed_households()["DEMO_B"]
    with SessionLocal() as session:
        record = session.scalar(
            select(BehaviorAssessment).where(
                BehaviorAssessment.household_id == household_id,
                BehaviorAssessment.data_source == "synthetic-families-v1.0.0",
            )
        )
        assert record is not None
        record.experiment_answers = {"legacy": {"choice_code": "unknown"}}
        session.commit()

        result = seed_synthetic_data(
            session,
            DATASET_PATH,
            behavior_rules_path=BEHAVIOR_RULES_PATH,
            if_empty=True,
        )
        assert result.loaded == 0
        assert result.behavior_inputs_refreshed == 1
        session.refresh(record)
        assert set(record.experiment_answers) == {"questionnaire", "responses"}
        assert set(record.experiment_answers["responses"]) == {
            "market_up_20",
            "market_down_10",
            "market_down_30",
            "hot_product_choice",
            "winner_loser_disposal",
            "consume_or_goal",
        }


def test_three_demos_have_distinct_profiles_and_demo_b_matches_standard_answer() -> None:
    household_ids = seed_households()
    profiles = {code: _legacy_profile(household_id) for code, household_id in household_ids.items()}
    significant_biases = {
        code: tuple(item["code"] for item in profile["biases"] if item["severity"] != "low")
        for code, profile in profiles.items()
    }
    assert len(set(significant_biases.values())) == 3
    assert profiles["DEMO_A"]["dual_profile"]["effective_risk_limit"] == "low"
    assert profiles["DEMO_B"]["dual_profile"]["effective_risk_limit"] == "low"
    assert profiles["DEMO_C"]["dual_profile"]["effective_risk_limit"] == "medium_low"

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    profile = profiles["DEMO_B"]
    dual = profile["dual_profile"]
    for key in (
        "questionnaire_score",
        "questionnaire_claim_limit",
        "experiment_score",
        "experiment_limit",
        "objective_capacity_score",
        "objective_capacity_limit",
        "behavioral_limit_before_capacity",
        "effective_risk_limit",
        "risk_downshifted",
        "conflict_codes",
    ):
        assert dual[key] == expected[key], key
    for key in (
        "average_response_time_ms",
        "total_modification_count",
        "overall_consistency_score",
    ):
        assert profile[key] == expected[key], key
    responses = {item["experiment_code"]: item for item in profile["responses"]}
    for code, item in expected["responses"].items():
        assert responses[code]["choice_code"] == item["choice_code"]
        assert responses[code]["consistency_score"] == item["consistency_score"]
    biases = {item["code"]: item for item in profile["biases"]}
    assert len(biases) == 11
    for code, item in expected["biases"].items():
        assert biases[code]["score"] == item["score"]
        assert biases[code]["severity"] == item["severity"]
        assert biases[code]["evidence"]
    assert [item["code"] for item in profile["interventions"]] == expected["intervention_codes"]
    cooling = next(item for item in profile["interventions"] if item["code"] == "cooling_period")
    assert cooling["cooling_period_hours"] == expected["cooling_period_hours"]
    assert cooling["intervention_id"] is None


def test_completed_session_persists_conflict_bias_interventions_and_cooling_audit() -> None:
    household_id = seed_households()["DEMO_B"]
    completed = _complete_like_legacy(household_id)
    assert completed["status"] == "completed"
    assert completed["answered_count"] == 6
    profile = completed["profile"]
    assert profile["dual_profile"]["objective_capacity_limit"] == "medium"
    assert profile["dual_profile"]["effective_risk_limit"] == "low"
    assert profile["dual_profile"]["risk_downshifted"] is True
    assert profile["dual_profile"]["conflict_detected"] is True
    assert len(profile["biases"]) == 11
    assert all(item["evidence"] for item in profile["biases"])
    assert all(item["intervention_id"] for item in profile["interventions"])
    assert all(item["status"] == "active" for item in profile["interventions"])
    combined_copy = " ".join(
        f"{item['personalized_message']} {item['action_instruction']}"
        for item in profile["interventions"]
    )
    assert all(term not in combined_copy for term in ("稳赚", "保本", "保证收益", "必然获利"))

    cooling = next(item for item in profile["interventions"] if item["code"] == "cooling_period")
    early = call(
        "POST",
        (
            f"/api/v1/households/{household_id}/behavior/interventions/"
            f"{cooling['intervention_id']}/actions"
        ),
        payload={"action": "complete", "reason_code": "test_early"},
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "behavior_cooling_period_active"

    with SessionLocal() as session:
        intervention = session.get(BehaviorIntervention, cooling["intervention_id"])
        assert intervention is not None
        intervention.eligible_at = utc_now() - timedelta(minutes=1)
        session.commit()
    finished = call(
        "POST",
        (
            f"/api/v1/households/{household_id}/behavior/interventions/"
            f"{cooling['intervention_id']}/actions"
        ),
        payload={"action": "complete", "reason_code": "cooling_elapsed"},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    assert finished.json()["completed_at"] is not None

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(BehaviorExperimentResponse)) == 6
        assert session.scalar(select(func.count()).select_from(BehaviorBiasFinding)) == 11
        assert session.scalar(select(func.count()).select_from(BehaviorIntervention)) == 6
        assert session.scalar(select(func.count()).select_from(BehaviorExperimentAssignment)) == 1
        assert session.scalar(select(func.count()).select_from(BehaviorAssessment)) == 4
        session_record = session.scalar(select(BehaviorExperimentSession))
        assert session_record is not None
        assert session_record.status == BehaviorSessionStatus.COMPLETED
        assert session_record.effective_risk_limit == RiskLevel.LOW
        assessment = session.get(BehaviorAssessment, session_record.assessment_id)
        assert assessment is not None
        assert assessment.final_behavior_limit == RiskLevel.LOW
        intervention = session.get(BehaviorIntervention, cooling["intervention_id"])
        assert intervention is not None
        assert intervention.status == BehaviorInterventionStatus.COMPLETED
        audit_types = set(session.scalars(select(AuditEvent.event_type)).all())
        assert {
            AuditEventType.BEHAVIOR_SESSION_STARTED,
            AuditEventType.BEHAVIOR_RESPONSE_RECORDED,
            AuditEventType.BEHAVIOR_ASSESSMENT_COMPLETED,
            AuditEventType.BEHAVIOR_INTERVENTION_UPDATED,
        } <= audit_types


def test_user_can_exit_without_generating_profile_or_intervention() -> None:
    household_id = seed_households()["DEMO_B"]
    started = _start_session(household_id)
    session_id = started["session_id"]
    answered = call(
        "POST",
        (
            f"/api/v1/households/{household_id}/behavior/sessions/{session_id}/"
            "responses/market_up_20"
        ),
        payload={
            "choice_code": "keep_plan",
            "response_time_ms": 1500,
            "modification_count": 0,
        },
    )
    assert answered.status_code == 200
    exited = call(
        "POST",
        f"/api/v1/households/{household_id}/behavior/sessions/{session_id}/exit",
    )
    assert exited.status_code == 200, exited.text
    assert exited.json()["status"] == "exited"
    assert "未生成画像或干预" in exited.json()["message"]
    with SessionLocal() as session:
        record = session.get(BehaviorExperimentSession, session_id)
        assert record is not None
        assert record.status == BehaviorSessionStatus.EXITED
        assert record.assessment_id is None
        assert session.scalar(select(func.count()).select_from(BehaviorIntervention)) == 0
        assert session.scalar(select(func.count()).select_from(BehaviorAssessment)) == 3
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == AuditEventType.BEHAVIOR_EXPERIMENT_EXITED
            )
        )
        assert audit is not None
        assert audit.evidence["profile_generated"] is False


def test_missing_behavior_data_is_explicit_and_unconsented_real_data_is_blocked() -> None:
    with SessionLocal() as session:
        synthetic = Household(
            code="NO_BEHAVIOR",
            name="缺少行为数据家庭",
            lifecycle_stage=LifecycleStage.FAMILY_FORMATION,
            region="测试地区",
            is_synthetic=True,
            data_source="test",
            is_user_confirmed=True,
        )
        real = Household(
            code="NO_CONSENT",
            name="未授权测试家庭",
            lifecycle_stage=LifecycleStage.FAMILY_FORMATION,
            region="测试地区",
            is_synthetic=False,
            data_source="test",
            is_user_confirmed=True,
        )
        session.add_all([synthetic, real])
        session.flush()
        for household in (synthetic, real):
            session.add(
                RiskAssessment(
                    household_id=household.id,
                    capacity_score="0.50",
                    willingness_score="0.50",
                    knowledge_score="0.50",
                    behavior_score="0.50",
                    final_risk_limit=RiskLevel.MEDIUM,
                    explanation="测试客观风险记录",
                    data_source="test",
                    is_user_confirmed=True,
                )
            )
        session.commit()
        synthetic_id = synthetic.id
        real_id = real.id

    overview = call("GET", f"/api/v1/households/{synthetic_id}/behavior")
    assert overview.status_code == 200
    assert overview.json()["information_status"] == "insufficient"
    assert overview.json()["profile"] is None
    assert "信息不足" in overview.json()["information_message"]

    blocked = call(
        "POST",
        f"/api/v1/households/{real_id}/behavior/sessions",
        payload={"questionnaire": QUESTIONNAIRE_B},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "behavior_experiment_not_authorized"

    binary_float = call(
        "POST",
        f"/api/v1/households/{synthetic_id}/behavior/sessions",
        payload={"questionnaire": {key: float(value) for key, value in QUESTIONNAIRE_B.items()}},
    )
    assert binary_float.status_code == 422


def test_ab_framework_reports_only_eligible_session_metrics() -> None:
    household_id = seed_households()["DEMO_B"]
    completed = _complete_like_legacy(household_id)
    completed_variant = completed["assigned_variant"]
    second = _start_session(household_id)
    second_variant = second["assigned_variant"]
    exit_response = call(
        "POST",
        f"/api/v1/households/{household_id}/behavior/sessions/{second['session_id']}/exit",
    )
    assert exit_response.status_code == 200

    response = call("GET", "/api/v1/behavior/ab-framework?experiment_key=behavior_nudge_main")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["framework_version"] == "behavior-ab-1.0.0"
    assert len(payload["variants"]) == 4
    metrics = {item["variant_code"]: item for item in payload["metrics"]}
    assert sum(item["assigned_count"] for item in metrics.values()) == 2
    assert sum(item["completed_count"] for item in metrics.values()) == 1
    assert sum(item["exited_count"] for item in metrics.values()) == 1
    assert metrics[completed_variant]["completed_count"] >= 1
    assert metrics[second_variant]["exited_count"] >= 1
    assert "不代表投资收益" in payload["privacy_note"]
