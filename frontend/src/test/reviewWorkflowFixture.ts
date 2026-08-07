import type {
  AdvisorDossier,
  AdvisorHouseholdList,
  ComplianceEvidence,
  ComplianceQueue,
  PlanWorkflow,
  PlanWorkflowAction,
  PlanWorkflowState,
  PlanWorkflowVersion,
} from "../api/reviewWorkflow";
import { portfolioFixture } from "./portfolioFixture";

const stateOrder: PlanWorkflowState[] = [
  "draft",
  "calculated",
  "suitability_checked",
  "advisor_reviewed",
  "compliance_reviewed",
  "customer_confirmed",
  "active",
  "superseded",
];

const stateHistory: Array<[PlanWorkflowState, PlanWorkflowAction]> = [
  ["draft", "create"],
  ["calculated", "calculate"],
  ["suitability_checked", "suitability_check"],
  ["advisor_reviewed", "advisor_review"],
  ["advisor_reviewed", "submit_compliance"],
];

function version(index: number, state: PlanWorkflowState, action: PlanWorkflowAction): PlanWorkflowVersion {
  return {
    id: `workflow-version-0000000000000000000000000${index}`,
    workflow_id: "workflow-fixture-0000000000000000000",
    household_id: "household-b",
    version_number: index,
    cycle: 1,
    prior_version_id: index === 1 ? null : `workflow-version-0000000000000000000000000${index - 1}`,
    state,
    action,
    reason: `${action} 测试理由`,
    actor_id: action.startsWith("compliance") ? "demo-compliance" : "demo-advisor",
    actor_role: action.startsWith("compliance") ? "compliance" : "advisor",
    selected_candidate: index >= 4 ? "balanced" : null,
    recommendation_snapshot: index >= 2 ? { advisor_modification: { manual_high_risk_confirmed: true } } : {},
    suitability_snapshot: index >= 3 ? { calculation_source: "deterministic_suitability_engine" } : {},
    communication_draft: index >= 4 ? "所有金额来自确定性工具；本方案不承诺保本或收益，需人工复核。" : "",
    advisor_decision: index >= 4 ? "manually_reviewed" : null,
    compliance_decision: index === 5 ? "pending" : null,
    customer_confirmation: {},
    submitted_for_compliance: index === 5,
    requires_human_review: true,
    is_current: index === 5,
    versions: {
      input_version: "fixture-input-version",
      rule_version: "1.0.0",
      model_version: "mock-editable-template-v1.0.0",
      prompt_version: "advisor-communication-contract-v1.0.0",
      knowledge_version: "controlled-knowledge-v1.0.0",
      product_catalog_version: "1.0.0",
    },
    before_hash: index === 1 ? "0".repeat(64) : String(index - 1).repeat(64),
    after_hash: String(index).repeat(64),
    request_id: `workflow-request-${index}`,
    created_at: `2026-08-04T0${index}:00:00Z`,
  };
}

const workflowVersions = stateHistory.map(([state, action], index) => version(index + 1, state, action));

export const workflowFixture: PlanWorkflow = {
  workflow_id: "workflow-fixture-0000000000000000000",
  household_id: "household-b",
  current: workflowVersions[4]!,
  versions: workflowVersions,
  state_order: stateOrder,
  next_actions: [],
  traceable: true,
};

export const advisorHouseholdsFixture: AdvisorHouseholdList = {
  generated_at: "2026-08-04T09:00:00Z",
  calculation_source: "deterministic_advisor_queue",
  items: [{
    household_id: "household-b",
    household_code: "DEMO_B",
    household_name: "B 家庭（测试夹具）",
    lifecycle_stage: "parenting",
    region: "上海",
    data_as_of: "2026-08-04",
    net_worth: "1642000.00",
    annual_surplus: "72000.00",
    anomaly_count: 2,
    goal_conflict_count: 1,
    highest_attention: "warning",
    workflow_id: workflowFixture.workflow_id,
    workflow_state: "advisor_reviewed",
    workflow_version: 5,
    signature_status: "not_ready",
    synthetic_data: true,
  }],
};

export const advisorDossierFixture: AdvisorDossier = {
  generated_at: "2026-08-04T09:00:00Z",
  household: advisorHouseholdsFixture.items[0]!,
  members: [{ display_name: "李先生", relationship: "self" }],
  premeeting_questions: ["请确认授权范围与数据日。", "是否优先补足家庭应急储备?"],
  financial_anomalies: [{ title: "应急储备不足", detail: "当前安全层未通过。" }],
  goal_conflicts: [{ title: "教育与养老投入冲突", detail: "月度投入超过结余。" }],
  candidates: portfolioFixture.candidates.map((item) => ({
    candidate_type: item.candidate_type,
    name: item.name,
    decision: item.decision,
    investment_amount: item.investment_amount,
    expected_nominal_return: item.expected_nominal_return,
    max_drawdown_estimate: item.max_drawdown_estimate,
    extreme_loss_amount: item.extreme_loss_amount,
    liquidity_score: item.liquidity_score,
    annual_fee_estimate: item.annual_fee_estimate,
    product_type_reasons: ["宽基基金：仅适用于长期资金，并受适当性上限约束。"],
    primary_risks: item.primary_risks,
  })),
  risk_and_liquidity_notes: ["家庭安全闸门阻断执行。", "当前版本仅用于教育与安全层修复。"],
  suggested_communication_draft: "所有金额来自确定性工具；本方案不承诺保本或收益，需人工复核。",
  communication_source: "editable_mock_template",
  monthly_review_reminders: Array.from({ length: 12 }, (_, index) => ({
    code: `review-${index + 1}`,
    title: `第 ${index + 1} 月复盘`,
    detail: "核对家庭变化与再平衡阈值。",
    due_date: `2026-${String(((index + 8) % 12) + 1).padStart(2, "0")}-04`,
  })),
  mock_bank: {
    adapter: "mock_bank_adapter",
    adapter_version: "mock-bank-adapter-v1.0.0",
    mock: true,
    official_connection: false,
    household_id: "household-b",
    household_code: "DEMO_B",
    data_as_of: "2026-08-04",
    interfaces: ["accounts", "credit_cards", "mortgages", "wealth_management", "funds", "insurance", "personal_pension", "cash_flow"].map((code) => ({
      code: code as AdvisorDossier["mock_bank"]["interfaces"][number]["code"],
      label: code,
      status: code === "wealth_management" ? "empty" : "available",
      entries: [],
    })),
    reconciled_asset_total: "2850000.00",
    reconciled_liability_total: "1208000.00",
    credit_limit_in_total_assets: false,
    source: "synthetic_household_records",
    boundary_note: "全部记录为合成数据，未使用任何银行官方标识。",
  },
  boundary_note: "Mock 沟通模板不能替代客户经理判断。",
};

export const complianceEvidenceFixture: ComplianceEvidence = {
  workflow_id: workflowFixture.workflow_id,
  version_id: workflowFixture.current.id,
  version_number: 5,
  household_id: "household-b",
  overall_decision: "human_review",
  controls: [
    { code: "gate_family_safety", category: "family_suitability", status: "warning", title: "家庭安全闸门", explanation: "产品执行被阻断，方案降为教育与修复。", rule: "安全层优先。", source_record_ids: ["asset-1"] },
    { code: "gate_customer", category: "customer_suitability", status: "pass", title: "客户适当性闸门", explanation: "客户风险上限已核对。", rule: "行为只能下调。", source_record_ids: ["risk-1"] },
    { code: "gate_product", category: "product_suitability", status: "warning", title: "产品适当性闸门", explanation: "仅教育展示。", rule: "产品风险不得越级。", source_record_ids: ["product-1"] },
    { code: "prohibited_wording", category: "prohibited_wording", status: "pass", title: "禁止性表述", explanation: "未发现禁止词。", rule: "不得保本保收益。", source_record_ids: [] },
    { code: "numeric_consistency", category: "numeric_consistency", status: "pass", title: "数值一致性", explanation: "数字可回到工具账本。", rule: "LLM 不算数。", source_record_ids: [] },
  ],
  three_gate_statuses: { family_safety: "block", customer: "pass", product: "restrict" },
  blocked_codes: [],
  warning_codes: ["gate_family_safety", "gate_product"],
  prohibited_phrases: [],
  numeric_ledger: { "balanced.investment_amount": "0.00" },
  security_events: [],
  versions: workflowFixture.current.versions,
  hash_chain_verified: true,
  explanation: "阻断 0 项，预警 2 项；需人工复核。",
};

export const complianceQueueFixture: ComplianceQueue = {
  generated_at: "2026-08-04T09:00:00Z",
  items: [{
    workflow_id: workflowFixture.workflow_id,
    household_id: "household-b",
    household_code: "DEMO_B",
    household_name: "B 家庭（测试夹具）",
    version_id: workflowFixture.current.id,
    version_number: 5,
    state: "advisor_reviewed",
    submitted_for_compliance: true,
    requires_human_review: true,
    selected_candidate: "balanced",
    created_at: "2026-08-04T05:00:00Z",
    blocked_count: 0,
    warning_count: 2,
    recommendation_reason: "提交合规测试理由",
  }],
};
