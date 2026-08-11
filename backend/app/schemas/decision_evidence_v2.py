from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecisionType = Literal["plan_workflow", "recommendation", "plan_report"]
EvidenceStatus = Literal["bound", "not_available", "not_applicable"]


class DecisionEvidenceSection(BaseModel):
    """One frozen evidence domain and the material that can change a decision."""

    model_config = ConfigDict(extra="forbid")

    status: EvidenceStatus
    version: str = Field(min_length=1, max_length=160)
    source_record_ids: list[str] = Field(default_factory=list)
    decision_inputs: dict[str, Any] = Field(default_factory=dict)
    snapshot: Any = Field(default_factory=dict)
    display_only_text: str | None = None


class DecisionEvidenceV2(BaseModel):
    """Immutable cross-domain package used by approvals and historical replay."""

    model_config = ConfigDict(extra="forbid")

    evidence_version: Literal["decision-evidence-v2.0.0"] = "decision-evidence-v2.0.0"
    decision_id: str
    decision_type: DecisionType
    household_id: str
    household_input: DecisionEvidenceSection
    financial_graph: DecisionEvidenceSection
    client_profile: DecisionEvidenceSection
    wealth_needs: DecisionEvidenceSection
    liability: DecisionEvidenceSection
    ELTC: DecisionEvidenceSection
    risk_budget: DecisionEvidenceSection
    enterprise: DecisionEvidenceSection
    CFS: DecisionEvidenceSection
    product_snapshot: DecisionEvidenceSection
    suitability: DecisionEvidenceSection
    calibration: DecisionEvidenceSection
    advisor: DecisionEvidenceSection
    client_confirmation: DecisionEvidenceSection
    generated_at: datetime
    decision_hash: str = Field(min_length=64, max_length=64)
    calculation_source: Literal["deterministic_evidence_v2"] = (
        "deterministic_evidence_v2"
    )

    @model_validator(mode="after")
    def require_all_bound_versions(self) -> DecisionEvidenceV2:
        for name in EVIDENCE_SECTION_NAMES:
            section = getattr(self, name)
            if section.status == "bound" and not section.decision_inputs:
                raise ValueError(f"{name} 已绑定但缺少决策输入")
        return self


EVIDENCE_SECTION_NAMES: tuple[str, ...] = (
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


class DecisionEvidenceSearchFields(BaseModel):
    client_profile_version: str | None
    wealth_need_set_hash: str | None
    liability_version: str | None
    twin_snapshot_version: str | None
    enterprise_snapshot_version: str | None
    cfs_solution_id: str | None
    calibration_version: str | None
    monitoring_trigger_id: str | None


class DecisionReplayResponse(BaseModel):
    decision_id: str
    decision_type: DecisionType
    household_id: str
    replayed_from: Literal["frozen_decision_evidence"] = "frozen_decision_evidence"
    stored_decision_hash: str
    replay_decision_hash: str
    hash_identical: bool
    used_snapshot_versions: dict[str, str]
    latest_product_data_used: Literal[False] = False
    replayed_at: datetime
    evidence: DecisionEvidenceV2
