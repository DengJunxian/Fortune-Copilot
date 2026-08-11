from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth import ActorContext
from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.agents import (
    AgentToolOut,
    AgentToolRegistryResponse,
    BoundedAgentCode,
    BoundedAgentSpecOut,
)

REGISTRY_VERSION = "bounded-financial-agent-tools-v1.0.0"


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: Session
    household_id: str
    actor: ActorContext
    settings: Settings
    analysis_date: date


@dataclass(frozen=True, slots=True)
class ToolResult:
    data: dict[str, Any]
    output_reference: str
    calculation_source: str
    citations: tuple[str, ...] = ()


ToolHandler = Callable[[ToolContext, Mapping[str, Any]], ToolResult]


@dataclass(frozen=True, slots=True)
class AgentToolDefinition:
    code: str
    description: str
    read_only: bool = True
    requires_confirmation: bool = False

    def to_schema(self) -> AgentToolOut:
        return AgentToolOut(
            code=self.code,
            description=self.description,
            read_only=self.read_only,
            requires_confirmation=self.requires_confirmation,
        )


@dataclass(frozen=True, slots=True)
class BoundedAgentSpec:
    code: BoundedAgentCode
    name: str
    purpose: str
    allowed_tools: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    timeout_seconds: int
    failure_fallback: str

    def to_schema(self) -> BoundedAgentSpecOut:
        return BoundedAgentSpecOut(
            code=self.code,
            name=self.name,
            purpose=self.purpose,
            allowed_tools=list(self.allowed_tools),
            prohibited_actions=list(self.prohibited_actions),
            timeout_seconds=self.timeout_seconds,
            failure_fallback=self.failure_fallback,
        )


TOOL_DEFINITIONS: tuple[AgentToolDefinition, ...] = (
    AgentToolDefinition("guardrail_check", "扫描提示注入与越权金融指令"),
    AgentToolDefinition("parse_document", "把自然语言解析为候选事实和缺失事实"),
    AgentToolDefinition("read_current_profile", "读取当前已确认画像与事实版本"),
    AgentToolDefinition(
        "create_intake_draft",
        "创建待逐项确认的 IntakeDraft，不写入客户事实",
        read_only=False,
        requires_confirmation=True,
    ),
    AgentToolDefinition("parse_goal_request", "解析目标类型、期限和用户明确提供的假设"),
    AgentToolDefinition("read_current_goals", "读取已确认目标，不补造金额或日期"),
    AgentToolDefinition("read_liability_assumption_sources", "读取受控目标假设来源及其限制"),
    AgentToolDefinition("read_financial_diagnosis", "读取确定性家庭财务诊断"),
    AgentToolDefinition("read_wealth_needs", "读取确定性财富需求与优先级"),
    AgentToolDefinition("read_cfs", "读取当前 CFS 方案及专业转介"),
    AgentToolDefinition("read_scenario_catalog", "读取受控 Scenario Catalog"),
    AgentToolDefinition("select_scenarios", "仅从已读取目录中选择值得比较的场景"),
    AgentToolDefinition("read_product_ontology", "读取 Product Ontology 事实"),
    AgentToolDefinition("read_product_snapshot", "读取版本化 Product Snapshot"),
    AgentToolDefinition("search_approved_knowledge", "检索有效且未隔离的 Approved Knowledge"),
    AgentToolDefinition("read_monitoring_trigger", "读取监控触发与 Next Best Action 证据"),
    AgentToolDefinition("read_profile_changes", "读取已确认的家庭变化事件"),
    AgentToolDefinition("read_decision_evidence", "读取冻结的决策证据摘要"),
)

_COMMON_PROHIBITIONS = (
    "不得执行交易、购买或调仓",
    "不得绕过客户确认、家庭安全、风险预算或适当性",
    "不得把缺失金融事实猜成零、行业平均值或模型常识",
)

AGENT_SPECS: tuple[BoundedAgentSpec, ...] = (
    BoundedAgentSpec(
        code="intake",
        name="Intake Agent",
        purpose="从文档或自然语言生成候选事实、缺失事实和待确认草稿",
        allowed_tools=(
            "guardrail_check",
            "parse_document",
            "read_current_profile",
            "create_intake_draft",
        ),
        prohibited_actions=(*_COMMON_PROHIBITIONS, "不得未经逐项确认写入客户事实"),
        timeout_seconds=8,
        failure_fallback="保留原始已确认事实，仅返回无法形成草稿",
    ),
    BoundedAgentSpec(
        code="goal",
        name="Goal Agent",
        purpose="把自然语言目标整理为 Goal Draft 和待确认责任假设",
        allowed_tools=(
            "guardrail_check",
            "parse_goal_request",
            "read_current_goals",
            "read_liability_assumption_sources",
        ),
        prohibited_actions=(*_COMMON_PROHIBITIONS, "不得虚构学费、通胀或汇率"),
        timeout_seconds=8,
        failure_fallback="只返回缺失假设，不创建目标记录",
    ),
    BoundedAgentSpec(
        code="household_analyst",
        name="Household Analyst",
        purpose="解释确定性诊断、财富需求和 CFS，不重新计算数字",
        allowed_tools=(
            "guardrail_check",
            "read_financial_diagnosis",
            "read_wealth_needs",
            "read_cfs",
        ),
        prohibited_actions=(*_COMMON_PROHIBITIONS, "不得在确定性诊断之外生成新数字"),
        timeout_seconds=15,
        failure_fallback="明确资料不足并保留确定性诊断原文",
    ),
    BoundedAgentSpec(
        code="scenario",
        name="Scenario Agent",
        purpose="从受控 Scenario Catalog 选择值得比较的压力场景",
        allowed_tools=("guardrail_check", "read_scenario_catalog", "select_scenarios"),
        prohibited_actions=(*_COMMON_PROHIBITIONS, "不得生成任意收益预测或目录外场景"),
        timeout_seconds=8,
        failure_fallback="不选择场景，不生成任何预测",
    ),
    BoundedAgentSpec(
        code="product_research",
        name="Product Research Agent",
        purpose="比较产品事实、差异和证据，不形成购买建议",
        allowed_tools=(
            "guardrail_check",
            "read_product_ontology",
            "read_product_snapshot",
            "search_approved_knowledge",
        ),
        prohibited_actions=(
            *_COMMON_PROHIBITIONS,
            "不得覆盖 Product Eligibility Engine",
            "不得按最高收益、渠道激励或销售目标推荐产品",
        ),
        timeout_seconds=12,
        failure_fallback="返回证据不足，不给出产品结论",
    ),
    BoundedAgentSpec(
        code="advisor_copilot",
        name="Advisor Copilot",
        purpose="把触发、变化、需求、CFS 和证据整理为会前材料",
        allowed_tools=(
            "guardrail_check",
            "read_monitoring_trigger",
            "read_profile_changes",
            "read_current_profile",
            "read_wealth_needs",
            "read_cfs",
            "read_decision_evidence",
        ),
        prohibited_actions=(*_COMMON_PROHIBITIONS, "不得把行动中心变成 Next Best Sale"),
        timeout_seconds=15,
        failure_fallback="只列待核实问题并转人工复核",
    ),
)

_TOOL_BY_CODE = {item.code: item for item in TOOL_DEFINITIONS}
_AGENT_BY_CODE = {item.code: item for item in AGENT_SPECS}


class AgentToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, code: str, handler: ToolHandler) -> None:
        if code not in _TOOL_BY_CODE:
            raise ValueError(f"unknown agent tool: {code}")
        if code in self._handlers:
            raise ValueError(f"duplicate agent tool: {code}")
        self._handlers[code] = handler

    def spec(self, agent_code: BoundedAgentCode) -> BoundedAgentSpec:
        return _AGENT_BY_CODE[agent_code]

    def assert_allowed(self, agent_code: BoundedAgentCode, tool_code: str) -> None:
        spec = self.spec(agent_code)
        if tool_code not in spec.allowed_tools:
            raise AppError(
                "agent_tool_not_allowed",
                "该 Agent 无权调用请求的工具",
                status_code=403,
                details={"agent_code": agent_code, "tool_code": tool_code},
            )

    def invoke(
        self,
        agent_code: BoundedAgentCode,
        tool_code: str,
        context: ToolContext,
        payload: Mapping[str, Any],
    ) -> ToolResult:
        self.assert_allowed(agent_code, tool_code)
        handler = self._handlers.get(tool_code)
        if handler is None:
            raise AppError(
                "agent_tool_unavailable",
                "受控工具当前不可用",
                status_code=503,
                details={"tool_code": tool_code},
            )
        return handler(context, payload)

    def catalog(self) -> AgentToolRegistryResponse:
        registered = set(self._handlers)
        return AgentToolRegistryResponse(
            registry_version=REGISTRY_VERSION,
            tools=[item.to_schema() for item in TOOL_DEFINITIONS if item.code in registered],
            agents=[item.to_schema() for item in AGENT_SPECS],
            boundary_note=(
                "所有 Agent 工具调用默认拒绝，只有角色 Allowlist 中已注册的确定性工具可以执行；"
                "E12 复用既有 AgentOrchestrationRun 与 AgentStepRun。"
            ),
        )
