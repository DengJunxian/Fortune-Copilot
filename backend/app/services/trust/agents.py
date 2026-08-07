from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.schemas.trust import AgentCatalogResponse, AgentSpecOut, GovernanceIssue

ORCHESTRATOR_VERSION = "trusted-agent-state-machine-v1.0.0"


class HouseholdAgentInput(BaseModel):
    household_id: str
    analysis_date: str
    confirmed_fact_version: str


class PolicyAgentInput(BaseModel):
    household_id: str
    query: str
    as_of_date: str
    allowed_categories: list[str]


class SynthesisAgentInput(BaseModel):
    household_id: str
    numeric_reference_codes: list[str]
    citation_chunk_ids: list[str]
    prior_step_codes: list[str]


class InformationCollectionOutput(BaseModel):
    household_code: str
    synthetic: bool
    confirmed: bool
    fact_counts: dict[str, int]
    missing_information: list[str]


class FinancialStatementOutput(BaseModel):
    input_version: str
    net_worth: str
    annual_income: str
    annual_expenses: str
    annual_surplus: str
    accounting_identity: str


class FinancialDiagnosisOutput(BaseModel):
    completeness_score: str
    diagnostic_codes: list[str]
    protection_gap: str
    most_significant_risk: str
    calculation_source: str


class GoalPlanningOutput(BaseModel):
    lifecycle_stage: str
    goal_count: int
    conflict_count: int
    available_planning_resources: str
    eligible_long_term_amount: str
    growth_70_eligible: bool
    failed_growth_conditions: list[str]


class BehaviorAgentOutput(BaseModel):
    information_status: str
    effective_risk_limit: str | None
    risk_downshifted: bool | None
    bias_codes: list[str]
    intervention_codes: list[str]


class AllocationAgentOutput(BaseModel):
    catalog_version: str
    product_source_type: str
    eligible_long_term_amount: str
    candidate_decisions: dict[str, str]
    family_gate: str
    customer_gate: str


class PolicyKnowledgeOutput(BaseModel):
    answer: str
    insufficient_information: bool
    citation_chunk_ids: list[str]
    citation_titles: list[str]
    as_of_date: str


class ReportSynthesisOutput(BaseModel):
    summary: str
    numeric_reference_codes: list[str]
    citation_chunk_ids: list[str]
    missing_information: list[str]
    template_fallback_used: bool


class ComplianceAuditOutput(BaseModel):
    passed: bool
    blocked: bool
    requires_human_review: bool
    issues: list[GovernanceIssue]
    checked_numeric_reference_count: int
    checked_citation_count: int


@dataclass(frozen=True)
class AgentSpec:
    code: str
    name: str
    purpose: str
    sequence: int
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    allowed_tools: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    timeout_seconds: int
    failure_fallback: str

    @property
    def audit_event(self) -> str:
        return "agent_step_completed_or_degraded"

    def to_schema(self) -> AgentSpecOut:
        return AgentSpecOut(
            code=self.code,
            name=self.name,
            purpose=self.purpose,
            sequence=self.sequence,
            input_schema_name=self.input_model.__name__,
            input_json_schema=self.input_model.model_json_schema(),
            output_schema_name=self.output_model.__name__,
            output_json_schema=self.output_model.model_json_schema(),
            allowed_tools=list(self.allowed_tools),
            prohibited_actions=list(self.prohibited_actions),
            timeout_seconds=self.timeout_seconds,
            failure_fallback=self.failure_fallback,
            audit_event=self.audit_event,
        )


SHARED_PROHIBITIONS = (
    "不得自行计算或改写金额、比率和配置",
    "不得绕过家庭安全、客户适当性和产品适当性",
    "不得把缺失信息猜成零或行业平均值",
)

AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(
        "information_collection",
        "信息采集智能体",
        "读取已确认结构化事实并列出缺口",
        1,
        HouseholdAgentInput,
        InformationCollectionOutput,
        ("load_household_facts", "read_intake_drafts"),
        (*SHARED_PROHIBITIONS, "不得将自然语言草稿直接写入家庭事实"),
        5,
        "返回事实计数和信息不足清单",
    ),
    AgentSpec(
        "financial_statement",
        "财务报表智能体",
        "调用确定性工具形成五张底表摘要",
        2,
        HouseholdAgentInput,
        FinancialStatementOutput,
        ("analyze_household",),
        (*SHARED_PROHIBITIONS, "不得由模型心算资产负债或现金流"),
        10,
        "标记报表暂不可用，不生成估算金额",
    ),
    AgentSpec(
        "financial_diagnosis",
        "财务诊断智能体",
        "读取指标、保障和数据质量结果",
        3,
        HouseholdAgentInput,
        FinancialDiagnosisOutput,
        ("financial_diagnostics", "protection_assessment"),
        SHARED_PROHIBITIONS,
        8,
        "仅返回待复核状态",
    ),
    AgentSpec(
        "goal_planning",
        "目标规划智能体",
        "执行生命周期、目标现值和动态四账户瀑布",
        4,
        HouseholdAgentInput,
        GoalPlanningOutput,
        ("plan_household",),
        (*SHARED_PROHIBITIONS, "不得把四账户改成固定比例或把70%套到家庭总资产"),
        12,
        "保留原事实并阻断配置输出",
    ),
    AgentSpec(
        "behavior_finance",
        "行为金融智能体",
        "读取双画像、偏差和干预证据",
        5,
        HouseholdAgentInput,
        BehaviorAgentOutput,
        ("behavior_overview",),
        (*SHARED_PROHIBITIONS, "行为结果不得提高客观承受能力"),
        8,
        "返回信息不足，不贴人格标签",
    ),
    AgentSpec(
        "asset_allocation",
        "资产配置智能体",
        "调用优化器和三道适当性闸门",
        6,
        HouseholdAgentInput,
        AllocationAgentOutput,
        ("portfolio_household", "controlled_product_catalog"),
        (*SHARED_PROHIBITIONS, "不得默认推荐个股、杠杆或股指期货"),
        15,
        "只保留教育内容，不输出执行建议",
    ),
    AgentSpec(
        "policy_knowledge",
        "政策知识智能体",
        "执行关键词、向量和元数据混合检索",
        7,
        PolicyAgentInput,
        PolicyKnowledgeOutput,
        ("hybrid_knowledge_search",),
        (*SHARED_PROHIBITIONS, "不得使用无来源、未生效、已失效或隔离片段"),
        8,
        "明确返回没有足够受控依据",
    ),
    AgentSpec(
        "report_generation",
        "报告生成智能体",
        "只引用工具数字和受控政策生成模板解释",
        8,
        SynthesisAgentInput,
        ReportSynthesisOutput,
        ("template_explanation", "numeric_ledger", "citation_ledger"),
        (*SHARED_PROHIBITIONS, "不得新增任何账本外数字或来源外政策事实"),
        10,
        "使用本地模板，核心流程继续",
    ),
    AgentSpec(
        "compliance_audit",
        "合规审计智能体",
        "对数字、政策、产品、提示注入和高风险建议做终检",
        9,
        SynthesisAgentInput,
        ComplianceAuditOutput,
        ("deterministic_governance_validator",),
        (*SHARED_PROHIBITIONS, "不得放行未通过数值或适当性校验的输出"),
        10,
        "阻断输出并转人工复核",
    ),
)


def agent_catalog() -> AgentCatalogResponse:
    return AgentCatalogResponse(
        orchestrator_version=ORCHESTRATOR_VERSION,
        state_machine=[spec.code for spec in AGENT_SPECS],
        agents=[spec.to_schema() for spec in AGENT_SPECS],
        hard_gates=[
            "所有数字必须在确定性 numeric ledger 中逐值匹配",
            "政策引用必须有效、未隔离并保留来源和更新时间",
            "产品必须来自当前启用的 Mock 受控目录且版本匹配",
            "家庭、客户、产品适当性不得被任何智能体跳过",
            "高风险建议必须阻断普通家庭默认路径并转人工复核",
        ],
    )


def spec_by_code(code: str) -> AgentSpec:
    for spec in AGENT_SPECS:
        if spec.code == code:
            return spec
    raise KeyError(code)


def validate_agent_output(code: str, output: dict[str, Any]) -> dict[str, Any]:
    validated = spec_by_code(code).output_model.model_validate(output)
    return validated.model_dump(mode="json")
