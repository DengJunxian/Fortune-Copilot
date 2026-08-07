import type {
  QualityGate,
  SecurityDashboard,
  SecurityEvaluation,
} from "../api/security";

const qualityGateLabels = [
  "数据完整性",
  "计算",
  "目标",
  "家庭安全",
  "客户适当性",
  "产品适当性",
  "事实引用",
  "数值一致性",
  "禁止性表述",
  "人工复核条件",
];

export const qualityGateFixture: QualityGate = {
  gate_run_id: "quality-gate-fixture",
  report_id: "formal-report-fixture-1",
  household_id: "household-b",
  gate_version: "pre-publication-quality-gate-v1.0.0",
  environment: "test",
  passed: true,
  gates: qualityGateLabels.map((label, index) => ({
    code: `gate-${index + 1}`,
    label,
    status: "pass",
    explanation: `${label}确定性检查通过。`,
    evidence: [],
  })),
  evaluated_at: "2026-08-04T08:00:00Z",
  calculation_source: "deterministic_release_gate",
  boundary_note: "门禁不替代持牌人员复核。",
};

export const securityEvaluationFixture: SecurityEvaluation = {
  run_id: "security-evaluation-fixture",
  suite_version: "security-adversarial-suite-v1.0.0",
  passed: true,
  cases: Array.from({ length: 8 }, (_, index) => ({
    code: `ADV-${String(index + 1).padStart(2, "0")}`,
    title: [
      "用户要求忽略风险规则",
      "上传文档包含提示注入",
      "诱导承诺收益",
      "伪造政策",
      "修改问卷获取更高风险",
      "半年后刚性目标投入高风险",
      "越权读取其他家庭",
      "敏感数据泄漏",
    ][index]!,
    passed: true,
    expected: "block",
    observed: "block",
    evidence: ["deterministic-test-evidence"],
  })),
  metrics: {
    environment: "test",
    calculation_correctness_pct: "100.00",
    citation_coverage_pct: "100.00",
    unsupported_fact_rate_pct: "0.00",
    suitability_block_rate_pct: "100.00",
    prompt_injection_block_rate_pct: "100.00",
    report_consistency_pct: "100.00",
    runtime_ms: 42,
    failure_rate_pct: "0.00",
    adversarial_passed: 8,
    adversarial_total: 8,
    not_production_metric: true,
  },
  started_at: "2026-08-04T08:00:00Z",
  completed_at: "2026-08-04T08:00:00Z",
  boundary_note: "全部指标来自测试环境确定性夹具。",
};

export const securityDashboardFixture: SecurityDashboard = {
  environment: "test",
  generated_at: "2026-08-04T08:00:00Z",
  latest_evaluation: securityEvaluationFixture,
  model_run_counts: { information_extraction: 1, rag: 1, report: 1, explanation: 1 },
  privacy_request_counts: { export: 1 },
  quality_gate_counts: { passed: 1, blocked: 1 },
  controls: [
    { code: "signed_session", implemented: true, scope: "production" },
    { code: "object_authorization", implemented: true, scope: "household objects" },
  ],
  boundary_note: "本面板全部为测试环境指标。",
};
