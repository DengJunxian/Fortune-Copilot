from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.privacy import redact_mapping, stable_hash
from app.domain.enums import AuditEventType
from app.models.common import utc_now
from app.models.governance import AuditEvent, ModelRun
from app.schemas.security import ModelRunListResponse, ModelRunSummary

MODEL_LEDGER_VERSION = "model-risk-ledger-v1.0.0"
MODEL_TASKS = {"information_extraction", "explanation", "rag", "report"}


def record_model_run(
    session: Session,
    *,
    household_id: str | None,
    actor: ActorContext,
    provider: str,
    model_name: str,
    task: str,
    prompt_version: str,
    inputs: dict[str, Any],
    output: dict[str, Any],
    started_at: datetime,
    completed_at: datetime | None = None,
    degraded: bool = False,
    prompt_injection_detected: bool = False,
    human_review_required: bool = False,
    fallback_reason: str | None = None,
) -> ModelRun:
    if task not in MODEL_TASKS:
        raise ValueError(f"unsupported model task: {task}")
    finished = completed_at or utc_now()
    safe_input = redact_mapping(inputs)
    safe_output = redact_mapping(output)
    safe_input["ledger_version"] = MODEL_LEDGER_VERSION
    safe_input["input_fields"] = sorted(inputs)
    safe_input["prompt_injection_detected"] = prompt_injection_detected
    safe_output["human_review_required"] = human_review_required
    safe_output["fallback_reason"] = fallback_reason
    run = ModelRun(
        household_id=household_id,
        provider=provider,
        model_name=model_name,
        task=task,
        prompt_hash=hashlib.sha256(prompt_version.encode("utf-8")).hexdigest(),
        redacted_input=safe_input,
        structured_output=safe_output,
        started_at=started_at,
        completed_at=finished,
        degraded=degraded,
        currency="CNY",
        valuation_date=finished.date(),
        data_source=MODEL_LEDGER_VERSION,
        is_user_confirmed=False,
    )
    session.add(run)
    session.flush()
    session.add(
        AuditEvent(
            household_id=household_id,
            event_type=AuditEventType.MODEL_EXECUTED,
            actor_id=stable_hash(actor.actor_id)[:16],
            actor_role=actor.role,
            entity_type="ModelRun",
            entity_id=run.id,
            event_version=run.version,
            summary=f"记录模型运行：{task}{'（安全降级）' if degraded else ''}",
            evidence={
                "provider": provider,
                "model_name": model_name,
                "task": task,
                "degraded": degraded,
                "prompt_injection_detected": prompt_injection_detected,
                "human_review_required": human_review_required,
                "input_value_logging": False,
                "output_hash": hashlib.sha256(
                    json.dumps(safe_output, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest(),
            },
            occurred_at=finished,
            data_source=MODEL_LEDGER_VERSION,
            is_user_confirmed=True,
        )
    )
    return run


def record_orchestration_model_ledger(
    session: Session,
    *,
    household_id: str,
    actor: ActorContext,
    provider: str,
    model_name: str,
    prompt_version: str,
    started_at: datetime,
    outputs: dict[str, dict[str, Any]],
    degraded: bool,
    human_review_required: bool,
) -> list[ModelRun]:
    tasks = {
        "information_extraction": outputs.get("information_collection", {}),
        "rag": outputs.get("policy_knowledge", {}),
        "report": outputs.get("report_generation", {}),
        "explanation": outputs.get("compliance_audit", {}),
    }
    return [
        record_model_run(
            session,
            household_id=household_id,
            actor=actor,
            provider=provider,
            model_name=model_name,
            task=task,
            prompt_version=f"{prompt_version}:{task}",
            inputs={
                "verified_fact_refs": [f"household:{stable_hash(household_id)[:12]}"],
                "citation_ids": output.get("citation_chunk_ids", []),
                "risk_flags": output.get("issues", []),
            },
            output={
                "status": "degraded" if degraded else "completed",
                "output_field_names": sorted(output),
            },
            started_at=started_at,
            degraded=degraded,
            human_review_required=human_review_required,
            fallback_reason="upstream_or_model_degraded" if degraded else None,
        )
        for task, output in tasks.items()
    ]


def list_model_runs(session: Session, *, limit: int = 100) -> ModelRunListResponse:
    records = list(
        session.scalars(
            select(ModelRun)
            .where(ModelRun.is_deleted.is_(False))
            .order_by(ModelRun.started_at.desc(), ModelRun.id.desc())
            .limit(limit)
        ).all()
    )
    total = (
        session.scalar(
            select(func.count()).select_from(ModelRun).where(ModelRun.is_deleted.is_(False))
        )
        or 0
    )
    return ModelRunListResponse(
        items=[
            ModelRunSummary(
                run_id=item.id,
                household_id=item.household_id,
                task=item.task,
                provider=item.provider,
                model_name=item.model_name,
                degraded=item.degraded,
                started_at=item.started_at,
                completed_at=item.completed_at,
                input_fields=[str(value) for value in item.redacted_input.get("input_fields", [])],
                prompt_injection_detected=bool(
                    item.redacted_input.get("prompt_injection_detected", False)
                ),
                human_review_required=bool(
                    item.structured_output.get("human_review_required", False)
                ),
            )
            for item in records
        ],
        total=total,
        boundary_note=(
            "台账只保存字段名、哈希、状态与降级原因；不保存 API Key、原始身份字段或完整提示词。"
        ),
    )
