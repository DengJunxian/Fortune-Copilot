import type {
  DemoControlResult,
  DemoManifest,
  DemoPreheatResult,
  DemoRun,
  ExperimentSuite,
  FamilyComparison,
  FamilyComparisonRow,
} from "../api/demo";

const buckets = [
  ["emergency_liquidity", "日用周转与应急", "133000.00"],
  ["risk_protection", "风险保障", "18000.00"],
  ["stable_goals", "稳健目标", "360000.00"],
  ["long_term_growth", "长期增长", "257000.00"],
] as const;

function familyRow(code: "DEMO_A" | "DEMO_B" | "DEMO_C", index: number): FamilyComparisonRow {
  return {
    household_id: `household-${code.at(-1)?.toLowerCase()}`,
    code,
    name: `${code} 合成家庭`,
    profile: ["单身职场新人", "35 岁双收入育儿家庭", "临近退休家庭"][index]!,
    lifecycle_stage: ["early_career", "parenting", "retirement_preparation"][index]!,
    total_assets: ["680000.00", "2850000.00", "5600000.00"][index]!,
    net_worth: ["580000.00", "1642000.00", "5350000.00"][index]!,
    annual_surplus: ["96000.00", "156000.00", "120000.00"][index]!,
    property_concentration: ["0.000000", "0.736842", "0.446429"][index]!,
    emergency_months: ["7.20", "2.30", "15.00"][index]!,
    dynamic_safety_months: ["6.00", "9.00", "12.00"][index]!,
    protection_gap: ["250000.00", "920000.00", "0.00"][index]!,
    accounts: buckets.map(([bucket, name, amount], bucketIndex) => ({
      bucket,
      name,
      recommended_amount: String(Number(amount) + index * 70000 + bucketIndex * index * 5000),
      gap_amount: String(index === 1 ? 50000 + bucketIndex * 10000 : bucketIndex * 1000),
    })),
    candidate_decisions: { conservative: "allowed", balanced: index === 1 ? "review" : "allowed", growth: "rejected" },
    long_term_eligible_amount: ["300000.00", "257000.00", "950000.00"][index]!,
    configuration_signature: [`a1-fixture-config`, `b2-fixture-config`, `c3-fixture-config`][index]!,
    calculation_source: "deterministic_tools",
  };
}

export const demoManifestFixture: DemoManifest = {
  release_version: "0.14.0",
  story_version: "main-demo-v1.0.0",
  dataset_version: "synthetic-v5-personas-v2.0.0",
  runtime_mode: "test",
  mock_mode: true,
  external_network_required: false,
  ready: true,
  seeded_household_count: 8,
  main_household_code: "DEMO_B",
  households: [0, 1, 2, 3, 4, 5, 6, 7].map((index) => ({
    household_id: `household-${String.fromCharCode(97 + index)}`,
    code: `DEMO_${String.fromCharCode(65 + index)}`,
    name: `合成家庭 ${String.fromCharCode(65 + index)}`,
    profile: [
      "刚工作的个人／新市民",
      "上海双职工中产家庭",
      "高收入专业人士",
      "科创企业创始人",
      "科创专家／科学家",
      "多代际高净值家族",
      "跨境家庭",
      "退休家庭",
    ][index]!,
    valuation_date: "2026-08-10",
  })) as DemoManifest["households"],
  latest_run_id: null,
  latest_run_status: null,
  preheated: false,
  preheated_at: null,
  cache_ttl_seconds: 300,
  release_assets: {
    docker_compose: true,
    migration_0013: true,
    acceptance_script: true,
    warmup_script: true,
    license: true,
    third_party_notice: true,
    changelog: true,
    v5_persona_dataset: true,
    v5_golden_outcomes: true,
    v5_release_benchmark: true,
  },
  boundaries: ["只使用合成数据", "信用卡额度不计入资产", "关键数字来自确定性工具"],
};

export const demoComparisonFixture: FamilyComparison = {
  comparison_version: "three-family-dynamic-comparison-v1.0.0",
  generated_at: "2026-08-04T08:00:00Z",
  analysis_date: "2026-08-04",
  cache_status: "miss",
  rows: [familyRow("DEMO_A", 0), familyRow("DEMO_B", 1), familyRow("DEMO_C", 2)],
  unique_configuration_count: 3,
  fixed_ratio_model: false,
  conclusion: "A／B／C 使用各自事实计算，三个配置签名互不相同。",
  boundary_note: "长期增长比例不得套用于家庭总资产。",
};

const stageLabels = [
  ["family_loaded", "加载 35 岁双收入育儿家庭"],
  ["intake_confirmed", "自然语言录入与逐项确认"],
  ["diagnosis_completed", "生成底表并识别集中、保障与应急缺口"],
  ["dynamic_accounts_planned", "建立十年教育目标并动态重配四账户"],
  ["portfolio_checked", "生成三候选并执行三道适当性闸门"],
  ["twin_completed", "模拟失业六个月与权益下跌 30%"],
  ["behavior_identified", "用六项选择证据识别损失厌恶"],
  ["review_evidence_ready", "生成顾问底稿与合规证据"],
  ["report_generated", "生成严格八章规划书与行动清单"],
  ["audit_closed", "运行九智能体终检并封存审计索引"],
] as const;

export const demoRunFixture: DemoRun = {
  run_id: "demo-run-fixture-001",
  household_id: "household-b",
  household_code: "DEMO_B",
  story_version: "main-demo-v1.0.0",
  status: "completed",
  current_stage: "completed",
  progress_percent: 100,
  stages: stageLabels.map(([code, label], index) => ({
    code,
    label,
    status: "completed",
    progress_percent: (index + 1) * 10,
    duration_ms: 10 + index,
    evidence: { calculation_source: "deterministic_tools" },
  })),
  artifacts: {
    diagnosis: {
      net_worth: "1642000.00",
      property_concentration: "0.736842",
      protection_gap: "920000.00",
      emergency_months: "2.30",
      credit_limit_in_assets: false,
    },
    planning: {
      fixed_ratio_model: false,
      growth_70_total_assets_interpretation: false,
      accounts: Object.fromEntries(buckets.map(([bucket, name, amount]) => [bucket, { name, recommended_amount: amount, gap_amount: "50000.00" }])),
    },
    report: { chapter_count: 8, action_count: 6, report_id: "report-fixture" },
    review: { workflow_state: "advisor_reviewed", workflow_id: "workflow-fixture" },
    audit: { agent_step_count: 9, audit_event_count: 42 },
  },
  metrics: {
    complete_demo_ms: 1240,
    target_results: { first_diagnosis: true, monte_carlo_100_paths: true, formal_report: true, complete_demo: true },
  },
  recovered_from_run_id: null,
  offline_mode: true,
  external_network_required: false,
  error_code: null,
  error_message: null,
  started_at: "2026-08-04T08:00:00Z",
  completed_at: "2026-08-04T08:00:02Z",
  boundary_note: "只处理合成家庭。",
};

const experimentCodes = [
  "calculation_benchmark",
  "suitability_adversarial",
  "controlled_policy_qa",
  "prompt_injection",
  "user_comprehension",
  "behavior_intervention_ab",
  "advisor_process_time",
] as const;

export const demoExperimentsFixture: ExperimentSuite = {
  run_id: "experiment-suite-fixture",
  suite_version: "wealthtwin-release-experiments-v1.0.0",
  status: "completed",
  passed: true,
  main_demo_run_id: demoRunFixture.run_id,
  cases: experimentCodes.map((code, index) => ({
    code,
    name: code,
    status: index === 4 || index === 6 ? "protocol_ready" : "passed",
    measured: index !== 4 && index !== 6,
    evidence: ["test/internal_demo 证据"],
    metrics: {},
    boundary_note: index === 4 || index === 6 ? "协议已就绪，未虚构真实参与者或工行员工结果。" : "只记录本地合成测试。",
  })),
  metrics: { case_count: 7 },
  started_at: "2026-08-04T08:01:00Z",
  completed_at: "2026-08-04T08:01:02Z",
  environment: "test",
  real_bank_results_claimed: false,
  boundary_note: "不是工行真实客户、员工或生产结果。",
};

export const demoLoadFixture: DemoControlResult = {
  action: "load",
  dataset_version: demoManifestFixture.dataset_version,
  loaded: 0,
  skipped: 8,
  removed: 0,
  household_codes: ["DEMO_A", "DEMO_B", "DEMO_C", "DEMO_D", "DEMO_E", "DEMO_F", "DEMO_G", "DEMO_H"],
  cache_cleared: true,
  message: "八类 V5 合成 Persona 已存在，未重复写入。",
};

export const demoResetFixture: DemoControlResult = {
  ...demoLoadFixture,
  action: "reset",
  loaded: 8,
  skipped: 0,
  removed: 8,
  message: "只删除并重建了标记为合成数据的家庭及其演示运行记录。",
};

export const demoPreheatFixture: DemoPreheatResult = {
  story_version: demoManifestFixture.story_version,
  status: "ready",
  warmed_components: ["release_manifest", "three_family_comparison", "twin_scenario_catalog", "behavior_rule_catalog", "controlled_knowledge_base"],
  timings_ms: { manifest: 1, three_family_comparison: 5 },
  cache_expires_at: "2026-08-04T08:05:00Z",
  external_network_calls: 0,
  boundary_note: "预热只读取本地资源。",
};
