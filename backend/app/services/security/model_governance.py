from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.privacy import stable_hash
from app.domain.enums import AuditEventType
from app.models.governance import AuditEvent
from app.schemas.security import (
    ModelGovernanceControlResult,
    ModelGovernanceEvaluationRequest,
    ModelGovernanceEvaluationResponse,
)

EVALUATION_VERSION = "model-governance-thresholds-v1.0.0"
ALLOWED_LLM_TASKS = ["information_extraction", "explanation", "rag", "report"]

THRESHOLDS: dict[str, dict[str, Decimal | int]] = {
    "low": {
        "sample_size": 100,
        "minimum_group_sample_size": 20,
        "input_drift_score": Decimal("0.20"),
        "output_drift_score": Decimal("0.20"),
        "fairness_max_gap": Decimal("0.10"),
        "unsupported_fact_rate": Decimal("0.02"),
        "availability_rate": Decimal("0.98"),
    },
    "medium": {
        "sample_size": 500,
        "minimum_group_sample_size": 30,
        "input_drift_score": Decimal("0.15"),
        "output_drift_score": Decimal("0.15"),
        "fairness_max_gap": Decimal("0.08"),
        "unsupported_fact_rate": Decimal("0.01"),
        "availability_rate": Decimal("0.99"),
    },
    "high": {
        "sample_size": 1000,
        "minimum_group_sample_size": 50,
        "input_drift_score": Decimal("0.10"),
        "output_drift_score": Decimal("0.10"),
        "fairness_max_gap": Decimal("0.05"),
        "unsupported_fact_rate": Decimal("0.005"),
        "availability_rate": Decimal("0.995"),
    },
}


def _control(
    code: str,
    passed: bool,
    observed: str,
    threshold: str,
    explanation: str,
) -> ModelGovernanceControlResult:
    return ModelGovernanceControlResult(
        code=code,
        status="pass" if passed else "block",
        observed=observed,
        threshold=threshold,
        explanation=explanation,
    )


def evaluate_model_governance(
    session: Session,
    request: ModelGovernanceEvaluationRequest,
    actor: ActorContext,
) -> ModelGovernanceEvaluationResponse:
    thresholds = THRESHOLDS[request.risk_class]
    controls = [
        _control(
            "independent_validation",
            request.independent_validation_completed and bool(request.approval_reference),
            str(request.independent_validation_completed),
            "completed=true and approval_reference present",
            "高风险模型上线前必须完成独立验证并绑定批准编号。",
        ),
        _control(
            "data_security_review",
            request.data_security_review_completed,
            str(request.data_security_review_completed),
            "completed=true",
            "上线前完成数据安全审查。",
        ),
        _control(
            "explainability_review",
            request.explainability_review_completed,
            str(request.explainability_review_completed),
            "completed=true",
            "上线前完成可解释性审查。",
        ),
        _control(
            "baseline_version",
            bool(request.baseline_version),
            request.baseline_version or "missing",
            "versioned baseline required",
            "漂移判断必须绑定受控基线版本。",
        ),
        _control(
            "sample_size",
            request.sample_size >= int(thresholds["sample_size"]),
            str(request.sample_size),
            f">={thresholds['sample_size']}",
            "总体样本不足时不得据此放行生产模型。",
        ),
        _control(
            "protected_group_coverage",
            request.minimum_group_sample_size
            >= int(thresholds["minimum_group_sample_size"]),
            str(request.minimum_group_sample_size),
            f">={thresholds['minimum_group_sample_size']}",
            "群体样本不足时公平性指标视为证据不足。",
        ),
        _control(
            "input_drift",
            request.input_drift_score <= Decimal(str(thresholds["input_drift_score"])),
            str(request.input_drift_score),
            f"<={thresholds['input_drift_score']}",
            "输入分布漂移超过阈值时切换确定性降级路径。",
        ),
        _control(
            "output_drift",
            request.output_drift_score <= Decimal(str(thresholds["output_drift_score"])),
            str(request.output_drift_score),
            f"<={thresholds['output_drift_score']}",
            "结构化输出漂移超过阈值时禁止生产调用。",
        ),
        _control(
            "fairness_gap",
            request.fairness_max_gap <= Decimal(str(thresholds["fairness_max_gap"])),
            str(request.fairness_max_gap),
            f"<={thresholds['fairness_max_gap']}",
            "公平性最大差异超限时必须复核数据、阈值与人群影响。",
        ),
        _control(
            "unsupported_fact_rate",
            request.unsupported_fact_rate
            <= Decimal(str(thresholds["unsupported_fact_rate"])),
            str(request.unsupported_fact_rate),
            f"<={thresholds['unsupported_fact_rate']}",
            "无依据事实率超限时不得让模型面向客户生成解释。",
        ),
        _control(
            "availability",
            request.availability_rate >= Decimal(str(thresholds["availability_rate"])),
            str(request.availability_rate),
            f">={thresholds['availability_rate']}",
            "可用性不足时必须使用本地确定性回退。",
        ),
    ]
    passed = all(item.status == "pass" for item in controls)
    evaluated_at = datetime.now(UTC)
    response = ModelGovernanceEvaluationResponse(
        evaluation_version=EVALUATION_VERSION,
        model_id=request.model_id,
        model_version=request.model_version,
        production_eligible=passed,
        decision="pass" if passed else "block",
        deterministic_fallback_required=not passed,
        allowed_llm_tasks=ALLOWED_LLM_TASKS,
        controls=controls,
        evaluated_at=evaluated_at,
        boundary_note=(
            "这里只评估调用方提交的汇总指标，不采集客户级样本，也不等同于工行独立验证批准；"
            "LLM 即使通过也只能用于信息提取、RAG、解释和报告表达，不能计算金额、适当性或产品资格。"
        ),
    )
    session.add(
        AuditEvent(
            household_id=None,
            event_type=AuditEventType.COMPLIANCE_DECISION_RECORDED,
            actor_id=stable_hash(actor.actor_id)[:16],
            actor_role=actor.role,
            entity_type="ModelGovernanceEvaluation",
            entity_id=f"{request.model_id}:{request.model_version}",
            event_version=1,
            summary=f"模型治理阈值评估：{response.decision}",
            evidence={
                "evaluation_version": EVALUATION_VERSION,
                "model_id": request.model_id,
                "model_version": request.model_version,
                "risk_class": request.risk_class,
                "decision": response.decision,
                "blocked_controls": [
                    item.code for item in controls if item.status == "block"
                ],
                "raw_customer_data_logged": False,
                "metric_source_attested_by_bank": False,
            },
            occurred_at=evaluated_at,
            data_source="caller_supplied_aggregate_metrics",
            is_user_confirmed=True,
        )
    )
    session.flush()
    return response
