from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

from app.core.errors import AppError

EXTERNAL_MODEL_FIELD_ALLOWLIST = frozenset(
    {
        "intent",
        "missing_fields",
        "verified_statements",
        "verified_fact_refs",
        "citation_ids",
        "risk_flags",
        "language",
        "tone",
        "fortune_copilot_philosophy",
        "mandatory_boundaries",
        "verified_family",
        "verified_financial_summary",
        "verified_ratios",
        "client_goals",
        "major_expenses",
        "verified_four_accounts",
        "growth_entry",
        "writing_rules",
    }
)
SENSITIVE_KEY_MARKERS = (
    "name",
    "phone",
    "mobile",
    "email",
    "address",
    "birth",
    "identity",
    "id_card",
    "bank_account",
    "card_number",
    "api_key",
    "authorization",
    "token",
    "password",
)
INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_rules_zh", re.compile(r"忽略.{0,18}(规则|指令|系统|风险)", re.IGNORECASE)),
    ("override_priority_zh", re.compile(r"(?:最高|新的)优先级指令", re.IGNORECASE)),
    ("ignore_previous_en", re.compile(r"ignore\s+(all\s+)?previous", re.IGNORECASE)),
    ("system_prompt", re.compile(r"system\s*prompt|系统提示词", re.IGNORECASE)),
    (
        "role_override",
        re.compile(
            r"(?:你现在是|act\s+as).{0,30}(管理员|system|developer)",
            re.IGNORECASE,
        ),
    ),
    ("script_tag", re.compile(r"<\s*script\b", re.IGNORECASE)),
)
PROHIBITED_PROMISE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "guaranteed_principal_or_return",
        re.compile(
            r"(?<!不)(?<!非)(?<!无)(?<!止)(?<!得)(?<!不是)(?<!不承诺)"
            r"(?<!不能承诺)保本保收益|稳赚不赔|(?<!不)(?<!得)保证.{0,12}(?:收益|回报)"
        ),
    ),
    ("minimum_wage_as_cpi", re.compile(r"最低工资(?:等于|就是|相当于)\s*CPI", re.IGNORECASE)),
    (
        "ordinary_household_high_risk_default",
        re.compile(
            r"(?:建议|默认|应当|可以)(?:买入|配置|加仓).{0,12}(?:集中个股|杠杆|股指期货|场外配资)"
        ),
    ),
)

_TEXT_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b1[3-9]\d{9}\b"), "[REDACTED_PHONE]"),
    (
        re.compile(
            r"\b\d{6}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]\b"
        ),
        "[REDACTED_ID]",
    ),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\d[ -]?){16,19}\b"), "[REDACTED_ACCOUNT]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_SECRET]"),
)


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_sensitive_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _TEXT_REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively redact values whose keys or text look sensitive."""

    result: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = key.casefold()
        if any(marker in normalized for marker in SENSITIVE_KEY_MARKERS):
            result[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            result[key] = redact_mapping(value)
        elif isinstance(value, list):
            result[key] = [
                redact_mapping(item)
                if isinstance(item, Mapping)
                else redact_sensitive_text(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = redact_sensitive_text(value)
        else:
            result[key] = value
    return result


def external_model_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    unexpected = sorted(set(payload) - EXTERNAL_MODEL_FIELD_ALLOWLIST)
    if unexpected:
        raise AppError(
            "external_model_field_blocked",
            "外部模型上下文包含未授权字段",
            status_code=422,
            details={"blocked_fields": unexpected},
        )
    return redact_mapping(payload)


def scan_prompt_injection(text: str) -> list[str]:
    return [code for code, pattern in INJECTION_PATTERNS if pattern.search(text)]


def scan_prohibited_language(text: str) -> list[str]:
    return [code for code, pattern in PROHIBITED_PROMISE_PATTERNS if pattern.search(text)]
