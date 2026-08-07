from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domain.enums import RiskLevel
from app.schemas.records import Ratio, RecordInput, RecordOut, RecordUpdate


class RiskAssessmentCreate(RecordInput):
    capacity_score: Ratio
    willingness_score: Ratio
    knowledge_score: Ratio
    behavior_score: Ratio
    final_risk_limit: RiskLevel
    explanation: str = Field(min_length=1, max_length=800)


class RiskAssessmentUpdate(RecordUpdate):
    capacity_score: Ratio | None = None
    willingness_score: Ratio | None = None
    knowledge_score: Ratio | None = None
    behavior_score: Ratio | None = None
    final_risk_limit: RiskLevel | None = None
    explanation: str | None = Field(default=None, min_length=1, max_length=800)


class RiskAssessmentOut(RecordOut):
    household_id: str
    capacity_score: Ratio
    willingness_score: Ratio
    knowledge_score: Ratio
    behavior_score: Ratio
    final_risk_limit: RiskLevel
    explanation: str


class BehaviorAssessmentCreate(RecordInput):
    questionnaire_score: Ratio
    experiment_score: Ratio
    final_behavior_limit: RiskLevel
    detected_biases: list[str] = Field(default_factory=list)
    experiment_answers: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(min_length=1, max_length=800)
