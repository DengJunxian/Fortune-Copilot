import { actorHeaders, demoActor } from "./actor";

export interface AdversarialCase {
  code: string;
  title: string;
  passed: boolean;
  expected: string;
  observed: string;
  evidence: string[];
}

export interface EvaluationMetrics {
  environment: "test";
  calculation_correctness_pct: string;
  citation_coverage_pct: string;
  unsupported_fact_rate_pct: string;
  suitability_block_rate_pct: string;
  prompt_injection_block_rate_pct: string;
  report_consistency_pct: string;
  runtime_ms: number;
  failure_rate_pct: string;
  adversarial_passed: number;
  adversarial_total: number;
  not_production_metric: true;
}

export interface SecurityEvaluation {
  run_id: string;
  suite_version: string;
  passed: boolean;
  cases: AdversarialCase[];
  metrics: EvaluationMetrics;
  started_at: string;
  completed_at: string;
  boundary_note: string;
}

export interface SecurityDashboard {
  environment: "test";
  generated_at: string;
  latest_evaluation: SecurityEvaluation | null;
  model_run_counts: Record<string, number>;
  privacy_request_counts: Record<string, number>;
  quality_gate_counts: { passed?: number; blocked?: number };
  controls: Array<{ code: string; implemented: boolean; scope: string }>;
  boundary_note: string;
}

export interface QualityGateItem {
  code: string;
  label: string;
  status: "pass" | "block";
  explanation: string;
  evidence: string[];
}

export interface QualityGate {
  gate_run_id: string;
  report_id: string;
  household_id: string;
  gate_version: string;
  environment: string;
  passed: boolean;
  gates: QualityGateItem[];
  evaluated_at: string;
  calculation_source: "deterministic_release_gate";
  boundary_note: string;
}

export interface PublishReportResult {
  report_id: string;
  publication_status: "published";
  published_at: string;
  gate: QualityGate;
  watermark: string;
  boundary_note: string;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const complianceHeaders = actorHeaders(demoActor("compliance"));

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    headers: { Accept: "application/json", ...complianceHeaders, ...init?.headers },
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return (await response.json()) as T;
}

export function fetchSecurityDashboard(signal?: AbortSignal): Promise<SecurityDashboard> {
  return readJson("/api/v1/security/dashboard", { signal });
}

export function runSecurityEvaluation(): Promise<SecurityEvaluation> {
  return readJson("/api/v1/security/evaluations/run", { method: "POST" });
}

export function evaluateReportQualityGate(reportId: string): Promise<QualityGate> {
  return readJson(`/api/v1/reports/${encodeURIComponent(reportId)}/quality-gate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      human_review_completed: true,
      reason: "合规端人工执行发布前十项质量门禁",
    }),
  });
}

export function publishReport(
  reportId: string,
  expectedReportSequence: number,
): Promise<PublishReportResult> {
  return readJson(`/api/v1/reports/${encodeURIComponent(reportId)}/publish`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Confirm-Action": "publish_report",
    },
    body: JSON.stringify({
      expected_report_sequence: expectedReportSequence,
      human_review_completed: true,
      reason: "合规人员确认十项门禁全部通过并发布",
    }),
  });
}
