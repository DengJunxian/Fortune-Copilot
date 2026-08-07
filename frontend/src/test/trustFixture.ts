import type {
  AgentCatalog,
  HouseholdGraph,
  IntakeDraft,
  KnowledgeCatalog,
  KnowledgeSearch,
  Orchestration,
} from "../api/trust";

export const knowledgeCatalogFixture: KnowledgeCatalog = {
  dataset_version: "controlled-knowledge-v1.0.0",
  updated_at: "2026-08-04",
  retrieval_version: "hybrid-rag-v1.0.0",
  vectorizer_version: "hashed-char-ngram-v1",
  source_summary: "测试受控本地快照，运行时不访问网络。",
  document_count: 9,
  active_document_count: 8,
  chunk_count: 16,
  quarantined_chunk_count: 1,
  categories: ["personal_pension", "social_security", "consumer_protection"],
  runtime_network_required: false,
};

export const knowledgeSearchFixture: KnowledgeSearch = {
  query: "个人养老金每年缴费限额和家庭适配需要核对什么?",
  as_of_date: "2026-08-04",
  answer: "个人养老金缴费按每年12000元限额标准据实扣除；是否缴满仍需结合家庭现金流和税务事实。",
  claims: [{ text: "个人养老金缴费按每年12000元限额标准据实扣除。", citation_ids: ["cite:pension"] }],
  matches: [{ chunk_id: "chunk-pension", chunk_code: "personal_pension_tax_limit", excerpt: "缴费限额规则", keyword_score: "1.000000", vector_score: "0.810000", metadata_score: "0.500000", combined_score: "0.883500", citation_id: "cite:pension" }],
  citations: [{ citation_id: "cite:pension", chunk_id: "chunk-pension", chunk_code: "personal_pension_tax_limit", document_code: "personal_pension_tax_2024", title: "关于在全国范围实施个人养老金个人所得税优惠政策的公告", issuing_authority: "财政部、国家税务总局", category: "personal_pension", source_uri: "https://www.gov.cn/", source_type: "official_snapshot", publication_date: "2024-12-12", effective_date: "2024-01-01", expiry_date: null, last_verified_date: "2026-08-04", applicable_audiences: ["个人养老金参加人"], applicable_regions: ["全国"], page_ref: "网页", paragraph_ref: "第一条", document_version: "财政部 税务总局公告2024年第21号", content_hash: "fixture-document-hash" }],
  insufficient_information: false,
  filtered_expired_count: 1,
  filtered_not_yet_effective_count: 0,
  filtered_quarantined_count: 1,
  retrieval_version: "hybrid-rag-v1.0.0",
  vectorizer_version: "hashed-char-ngram-v1",
  calculation_source: "deterministic_hybrid_retrieval",
  limitations: ["比赛版受控快照"],
};

export const shanghaiGraphFixture: HouseholdGraph = {
  graph_id: "shanghai-dual-income-demo",
  graph_version: "relational-household-graph-v1.0.0",
  title: "35岁上海双收入家庭关系推导图",
  subtitle: "5岁子女 · 有房贷 · 父母保障信息不足 · 完全合成示例",
  as_of_date: "2026-08-04",
  synthetic: true,
  nodes: [
    { id: "member", node_type: "household_member", label: "本人 · 35岁", lane: "family", properties: { age: 35 }, source_entity_type: "ControlledGraphFixture", source_entity_id: null, calculation_source: "confirmed_relational_fact" },
    { id: "income", node_type: "income", label: "双收入现金流", lane: "facts", properties: { earner_count: 2 }, source_entity_type: "ControlledGraphFixture", source_entity_id: null, calculation_source: "confirmed_relational_fact" },
    { id: "goal", node_type: "goal", label: "子女教育目标", lane: "goals", properties: { horizon_years: 13 }, source_entity_type: "ControlledGraphFixture", source_entity_id: null, calculation_source: "confirmed_relational_fact" },
    { id: "restriction", node_type: "restriction", label: "安全层优先", lane: "controls", properties: { fixed_ratio: false }, source_entity_type: "PlanningGuardrail", source_entity_id: null, calculation_source: "deterministic_graph_rule" },
    { id: "policy", node_type: "policy", label: "个人养老金政策", lane: "knowledge", properties: { source_required: true }, source_entity_type: "ControlledKnowledgeBase", source_entity_id: null, calculation_source: "confirmed_relational_fact" },
  ],
  edges: [
    { id: "e1", source: "income", target: "member", relation: "earned_by", label: "收入来源", evidence: ["双收入"] },
    { id: "e2", source: "member", target: "goal", relation: "supports", label: "支持教育", evidence: ["13年期限"] },
    { id: "e3", source: "restriction", target: "goal", relation: "gates", label: "安全约束", evidence: ["不得固定比例"] },
    { id: "e4", source: "policy", target: "restriction", relation: "governs", label: "政策有效期", evidence: ["来源必填"] },
  ],
  inferences: [
    { code: "responsibility_period", title: "家庭责任期", conclusion: "育儿、按揭和赡养责任并存。", evidence_node_ids: ["member", "goal"], rule: "关系事实推导", human_review_required: false },
    { code: "property_concentration", title: "房产集中", conclusion: "住房资产占总资产80.00%。", evidence_node_ids: ["restriction"], rule: "确定性金额计算", human_review_required: false },
    { code: "growth_ceiling", title: "增长上限", conclusion: "70%不是家庭总资产统一比例。", evidence_node_ids: ["restriction"], rule: "五硬一软", human_review_required: false },
  ],
  node_type_coverage: ["household_member", "income", "goal", "restriction", "policy"],
  calculation_source: "deterministic_relational_graph_service",
  limitations: ["完全合成示例"],
};

export const householdGraphFixture: HouseholdGraph = {
  ...shanghaiGraphFixture,
  graph_id: "household-b",
  title: "B 家庭（测试夹具）关系图谱",
  subtitle: "上海 · 关系表实时推导",
};

export function intakeDraftFixture(confirmed = false): IntakeDraft {
  const fields = [
    { code: "joint_monthly_salary", label: "夫妻月工资合计", value: "30000.00", value_type: "money" as const, unit: "CNY/month", evidence: "每月工资合计三万元", confidence: "0.980000", confirmed },
    { code: "monthly_mortgage_payment", label: "每月房贷", value: "8000.00", value_type: "money" as const, unit: "CNY/month", evidence: "房贷八千", confidence: "0.980000", confirmed },
    { code: "spouse_present", label: "配偶关系", value: "true", value_type: "relationship" as const, unit: null, evidence: "我和爱人", confidence: "0.990000", confirmed },
    { code: "child_education_stage", label: "子女教育阶段", value: "幼儿园", value_type: "stage" as const, unit: null, evidence: "孩子上幼儿园", confidence: "0.970000", confirmed },
  ];
  return {
    draft_id: "intake-draft-fixture",
    household_id: "household-b",
    status: confirmed ? "confirmed" : "pending_confirmation",
    parser_version: "deterministic-zh-intake-v1.0.0",
    source_text_hash: "fixture-source-text-hash-0123456789",
    redacted_preview: "我和爱人每月工资合计[金额]元，房贷[金额]，孩子上幼儿园",
    extracted_fields: fields,
    missing_fields: [{ code: "mortgage_balance", label: "房贷余额", reason: "月供不能推导贷款余额", required_for: ["资产负债表", "偿债压力"] }],
    confirmed_values: confirmed ? Object.fromEntries(fields.map((item) => [item.code, item.value])) : {},
    contains_untrusted_instruction: false,
    confirmation_required: !confirmed,
    created_at: "2026-08-04T08:00:00Z",
    confirmed_at: confirmed ? "2026-08-04T08:01:00Z" : null,
    boundary_note: "这是结构化草稿，不会直接写入家庭事实；每个提取值都需确认，未提供的金额保持缺失。",
  };
}

export const agentCatalogFixture: AgentCatalog = {
  orchestrator_version: "trusted-agent-state-machine-v1.0.0",
  state_machine: ["information_collection", "financial_statement", "financial_diagnosis", "goal_planning", "behavior_finance", "asset_allocation", "policy_knowledge", "report_generation", "compliance_audit"],
  agent_count: 9,
  agents: Array.from({ length: 9 }, (_, index) => ({
    code: ["information_collection", "financial_statement", "financial_diagnosis", "goal_planning", "behavior_finance", "asset_allocation", "policy_knowledge", "report_generation", "compliance_audit"][index]!,
    name: ["信息采集智能体", "财务报表智能体", "财务诊断智能体", "目标规划智能体", "行为金融智能体", "资产配置智能体", "政策知识智能体", "报告生成智能体", "合规审计智能体"][index]!,
    purpose: "测试中的真实工具受限步骤",
    sequence: index + 1,
    input_schema_name: "HouseholdAgentInput",
    input_json_schema: { type: "object" },
    output_schema_name: "AgentOutput",
    output_json_schema: { type: "object" },
    allowed_tools: [`deterministic_tool_${index + 1}`],
    prohibited_actions: ["不得心算关键数字", "不得绕过适当性"],
    timeout_seconds: 10,
    failure_fallback: "本地安全模板",
    audit_event: "agent_step_completed_or_degraded",
  })),
  hard_gates: ["数字工具账本", "政策有效期", "产品目录版本", "适当性"],
};

export const orchestrationFixture: Orchestration = {
  run_id: "orchestration-fixture-001",
  household_id: "household-b",
  request_kind: "trusted_plan_explanation",
  status: "completed",
  current_state: "finished",
  orchestrator_version: agentCatalogFixture.orchestrator_version,
  provider_mode: "mock_template",
  steps: agentCatalogFixture.agents.map((agent) => ({
    step_id: `step-${agent.sequence}`,
    agent_code: agent.code,
    agent_name: agent.name,
    sequence: agent.sequence,
    status: "completed",
    input_schema_name: agent.input_schema_name,
    output_schema_name: agent.output_schema_name,
    tool_calls: [{ tool: agent.allowed_tools[0]!, status: "completed", input_reference: "confirmed_database_state", output_reference: `step.${agent.code}`, calculation_source: "deterministic_tools" }],
    structured_output: { completed: true },
    citations: agent.code === "policy_knowledge" ? ["chunk-pension"] : [],
    prohibitions_checked: agent.prohibited_actions,
    timeout_seconds: agent.timeout_seconds,
    failure_code: null,
    degraded: false,
    started_at: "2026-08-04T08:00:00Z",
    completed_at: "2026-08-04T08:00:01Z",
  })),
  numeric_ledger: [{ code: "net_worth", value: "1642000.00", unit: "CNY", source_tool: "analyze_household", source_path: "financial.statements.balance_sheet.net_worth", value_hash: "fixture-value-hash" }],
  citation_chunk_ids: ["chunk-pension"],
  structured_output: { governance: { passed: true } },
  blocked_issues: [],
  requires_human_review: false,
  degraded: false,
  started_at: "2026-08-04T08:00:00Z",
  completed_at: "2026-08-04T08:00:09Z",
  boundary_note: "九个步骤均受状态机和工具白名单约束；模型只可理解与解释。",
};
