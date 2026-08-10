from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from app.domain.financial import HouseholdFacts
from app.schemas.methodology import DecisionEvidencePackage, MethodologyAssessment


def build_decision_evidence(
    *,
    facts: HouseholdFacts,
    household_input_version: str,
    financial_rule_version: str,
    planning_rule_version: str,
    methodology: MethodologyAssessment,
    hard_gate_results: dict[str, str],
    portfolio_version: str = "not_applicable_planning_stage",
    product_snapshot_version: str = "not_applicable_planning_stage",
    llm_model_version: str | None = None,
    llm_prompt_version: str | None = None,
    generated_at: datetime | None = None,
) -> DecisionEvidencePackage:
    timestamp = generated_at or datetime.now(UTC)
    risk_version = (
        f"risk-assessment-record-v{facts.risk_assessments[-1].version}"
        if facts.risk_assessments
        else "risk-assessment-missing-explicit"
    )
    behavior_version = (
        f"behavior-assessment-record-v{facts.behavior_assessments[-1].version}"
        if facts.behavior_assessments
        else "behavior-assessment-missing-explicit"
    )
    payload = {
        "evidence_version": "decision-evidence-package-v1.0.0",
        "household_input_version": household_input_version,
        "methodology_version": methodology.methodology_version,
        "financial_rule_version": financial_rule_version,
        "planning_rule_version": planning_rule_version,
        "regional_parameter_version": methodology.regional_threshold.policy_version,
        "market_regime_version": methodology.market_regime.snapshot_version,
        "minimum_wage_snapshot_version": methodology.minimum_wage_snapshot.version,
        "public_data_snapshot_version": methodology.public_data_snapshot_version,
        "pension_policy_version": methodology.personal_pension.policy.policy_version,
        "portfolio_version": portfolio_version,
        "product_snapshot_version": product_snapshot_version,
        "risk_assessment_version": risk_version,
        "behavior_assessment_version": behavior_version,
        "llm_model_version": llm_model_version,
        "llm_prompt_version": llm_prompt_version,
        "hard_gate_results": dict(sorted(hard_gate_results.items())),
        "generated_at": timestamp,
        "calculation_source": "deterministic_tools",
    }
    # The package records when it was emitted, while the decision identity must
    # remain replay-stable for identical governed inputs and gate outcomes.
    hash_payload = {key: value for key, value in payload.items() if key != "generated_at"}
    canonical = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), default=str)
    payload["decision_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return DecisionEvidencePackage.model_validate(payload)
