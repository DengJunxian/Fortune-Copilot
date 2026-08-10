from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.governance import RuleVersion
from app.services.methodology.models import MethodologyRules


def resolve_methodology_rules_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(
            Path(__file__).resolve().parents[4] / "data/rules/wealth_methodology_v3.json"
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AppError(
        "methodology_rules_missing",
        "找不到 CHFH 与 GRB 动态四账户方法论规则",
        status_code=500,
        details={"configured_path": configured_path},
    )


@lru_cache(maxsize=8)
def load_methodology_rules(configured_path: str) -> MethodologyRules:
    path = resolve_methodology_rules_path(configured_path)
    try:
        return MethodologyRules.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            "methodology_rules_invalid",
            "CHFH 与 GRB 动态四账户方法论未通过结构校验",
            status_code=500,
        ) from exc


def ensure_methodology_rule_version(
    session: Session,
    rules: MethodologyRules,
) -> RuleVersion:
    existing = session.scalar(
        select(RuleVersion).where(
            RuleVersion.code == rules.code,
            RuleVersion.semantic_version == rules.semantic_version,
            RuleVersion.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    record = RuleVersion(
        code=rules.code,
        semantic_version=rules.semantic_version,
        effective_from=rules.effective_from,
        effective_to=rules.effective_to,
        rules=rules.model_dump(mode="json"),
        source_summary=rules.source_summary,
        valuation_date=rules.effective_from,
        data_source="fortune-copilot-controlled-methodology",
        is_user_confirmed=True,
    )
    session.add(record)
    session.flush()
    return record
