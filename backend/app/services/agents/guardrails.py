from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.privacy import scan_prompt_injection


@dataclass(frozen=True, slots=True)
class GuardrailFinding:
    code: str
    message: str
    action: str


_FINANCIAL_AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    (
        "highest_return_product_request",
        re.compile(r"(?:最高|最大|最强).{0,8}(?:收益|回报).{0,8}(?:产品|基金)"),
        "不得按最高收益导向筛选或推荐产品；只能比较受控事实与差异。",
        "fail_closed",
    ),
    (
        "purchase_amount_request",
        re.compile(
            r"(?:直接|替我|帮我).{0,12}(?:告诉|决定|算|建议)?.{0,8}"
            r"(?:买|购买|配置|投入).{0,8}(?:多少|金额|比例)"
        ),
        "Agent 无权决定客户应购买或配置的金额，必须转确定性规划与适当性工具。",
        "deterministic_tool_required",
    ),
    (
        "risk_level_override_request",
        re.compile(
            r"(?:替我|帮我|直接).{0,12}(?:"
            r"(?:提高|调高|上调|改高).{0,12}(?:风险等级|风险承受|风险偏好)|"
            r"(?:风险等级|风险承受|风险偏好).{0,12}(?:提高|调高|上调|改高))"
        ),
        "Agent 无权提高客户风险等级；风险上限只能由已确认事实和确定性规则得出。",
        "fail_closed",
    ),
    (
        "eligibility_override_request",
        re.compile(r"(?:绕过|忽略|覆盖).{0,12}(?:适当性|准入|资格|eligibility)", re.IGNORECASE),
        "Agent 无权绕过或覆盖产品适当性引擎。",
        "fail_closed",
    ),
)


def evaluate_agent_guardrails(message: str) -> list[GuardrailFinding]:
    findings = [
        GuardrailFinding(
            code=f"prompt_injection:{code}",
            message="检测到试图覆盖系统或规则边界的指令，已关闭本次 Agent 运行。",
            action="fail_closed",
        )
        for code in scan_prompt_injection(message)
    ]
    findings.extend(
        GuardrailFinding(code=code, message=message_text, action=action)
        for code, pattern, message_text, action in _FINANCIAL_AUTHORITY_PATTERNS
        if pattern.search(message)
    )
    unique: dict[str, GuardrailFinding] = {}
    for finding in findings:
        unique.setdefault(finding.code, finding)
    return list(unique.values())
