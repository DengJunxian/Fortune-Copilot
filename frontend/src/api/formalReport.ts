import { actorHeaders, type DemoActor } from "./actor";
import type { KnowledgeCitation } from "./trust";

export const formalChapterTitles = [
  "家庭基础情况",
  "理财目标",
  "大额支出计划",
  "理财假设",
  "家庭财务报表",
  "家庭财务比率分析",
  "投资规划建议",
  "免责声明",
] as const;

export type ReportStatus = "draft_requires_human_review" | "workflow_linked" | "client_ready";
export type ReportTrigger = "manual" | "monthly_review" | "major_event" | "action_status_change";
export type ReportActionStatus = "open" | "completed" | "deferred" | "not_applicable";

export interface ReportTable {
  title: string;
  columns: string[];
  rows: string[][];
  note: string;
  calculation_source: string;
}

export interface ReportAdvice {
  code: string;
  title: string;
  reason: string;
  priority: number;
  action: string;
  completion_criteria: string;
  review_cycle: string;
  status: ReportActionStatus;
  due_date: string | null;
  citation_ids: string[];
  calculation_source: string;
}

export interface FormalReportSection {
  code: string;
  title: string;
  narratives: string[];
  tables: ReportTable[];
  advice: ReportAdvice[];
  citation_ids: string[];
}

export interface FormalReportChapter {
  number: number;
  title: string;
  summary: string;
  sections: FormalReportSection[];
}

export interface ReportExecutionMetrics {
  total: number;
  open: number;
  completed: number;
  deferred: number;
  not_applicable: number;
  completion_ratio: string;
}

export interface FormalReport {
  report_id: string;
  household_id: string;
  household_code: string;
  household_name: string;
  sequence: number;
  parent_report_id: string | null;
  workflow_id: string | null;
  workflow_version_id: string | null;
  workflow_state: string | null;
  status: ReportStatus;
  title: string;
  subtitle: string;
  watermark: string;
  chapter_count: 8;
  chapters: FormalReportChapter[];
  appendices: Array<{ code: string; title: string; tables: ReportTable[]; narratives: string[] }>;
  citations: KnowledgeCitation[];
  sourced_claims: Array<{ text: string; citation_ids: string[] }>;
  numeric_ledger: Array<{
    code: string;
    label: string;
    raw_value: string;
    display_value: string;
    unit: string;
    source_path: string;
    calculation_source: string;
  }>;
  versions: {
    report_version: string;
    input_version: string;
    formula_version: string;
    planning_rule_version: string;
    portfolio_rule_version: string;
    twin_result_version: string;
    model_version: string;
    prompt_version: string;
    knowledge_version: string;
    product_catalog_version: string;
    fund_advisory_catalog_version?: string | null;
    workflow_version: string | null;
  };
  execution_metrics: ReportExecutionMetrics;
  consistency_checks: Array<{ code: string; status: "passed" | "needs_review"; explanation: string }>;
  consistency_status: "passed" | "needs_review";
  generation_trigger: ReportTrigger;
  generation_reason: string;
  generated_at: string;
  analysis_date: string;
  data_as_of: string;
  report_hash: string;
  mock_mode_supported: true;
  boundary_note: string;
}

export interface FormalReportSummary {
  report_id: string;
  household_id: string;
  sequence: number;
  report_version: string;
  parent_report_id: string | null;
  workflow_id: string | null;
  workflow_version_id: string | null;
  status: ReportStatus;
  consistency_status: "passed" | "needs_review";
  generation_trigger: ReportTrigger;
  generated_at: string;
  data_as_of: string;
  report_hash: string;
  watermark: string;
  html_url: string;
  pdf_url: string;
}

export interface ReportAction {
  id: string;
  action_code: string;
  group_code: string;
  title: string;
  detail: string;
  why: string;
  completion_criteria: string;
  review_cycle: string;
  amount: string;
  due_date: string | null;
  priority: number;
  status: ReportActionStatus;
  completed_at: string | null;
  deferred_until: string | null;
  status_reason: string | null;
  record_version: number;
  calculation_source: string;
}

export interface ReportActionList {
  household_id: string;
  report_id: string | null;
  report_sequence: number | null;
  items: ReportAction[];
  metrics: ReportExecutionMetrics;
}

export interface ReportGenerationChain {
  household_id: string;
  current_report_id: string | null;
  chain_verified: boolean;
  items: FormalReportSummary[];
  audit_event_ids: string[];
  boundary_note: string;
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

export class ReportApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, payload: ErrorEnvelope, path: string) {
    super(payload.error?.message ?? `API ${status}: ${path}`);
    this.name = "ReportApiError";
    this.status = status;
    this.code = payload.error?.code ?? "report_api_error";
  }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function readJson<T>(
  path: string,
  actor: DemoActor,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    signal,
    headers: { Accept: "application/json", ...actorHeaders(actor), ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorEnvelope;
    throw new ReportApiError(response.status, payload, path);
  }
  return await response.json() as T;
}

export function fetchCurrentFormalReport(
  householdId: string,
  actor: DemoActor,
  signal?: AbortSignal,
): Promise<FormalReport | null> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/reports/current`, actor, signal);
}

export function generateFormalReport(
  householdId: string,
  actor: DemoActor,
  analysisDate: string,
): Promise<FormalReport> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/reports`, actor, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      analysis_date: analysisDate,
      trigger: "manual",
      reason: "客户端一键生成完整八章家庭财富规划书",
    }),
  });
}

export function recalculateFormalReport(
  householdId: string,
  actor: DemoActor,
  report: FormalReport,
  trigger: "monthly_review" | "major_event",
): Promise<FormalReport> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/reports/recalculate`, actor, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      analysis_date: report.analysis_date,
      trigger,
      reason: trigger === "monthly_review" ? "月度家庭事实与行动复盘" : "家庭重大事件后创建新快照并重算",
      expected_report_sequence: report.sequence,
    }),
  });
}

export function fetchReportActions(
  householdId: string,
  actor: DemoActor,
  signal?: AbortSignal,
): Promise<ReportActionList> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/report-actions`, actor, signal);
}

export function updateReportAction(
  householdId: string,
  action: ReportAction,
  status: ReportActionStatus,
  actor: DemoActor,
  deferredUntil?: string,
  reason?: string,
): Promise<{ action: ReportAction; metrics: ReportExecutionMetrics; report: FormalReportSummary }> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/report-actions/${encodeURIComponent(action.action_code)}`,
    actor,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status,
        expected_version: action.record_version,
        reason: reason ?? `客户将“${action.title}”标记为 ${status}`,
        deferred_until: status === "deferred" ? deferredUntil : undefined,
      }),
    },
  );
}

export function fetchReportGenerationChain(
  householdId: string,
  actor: DemoActor,
  signal?: AbortSignal,
): Promise<ReportGenerationChain> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/reports/generation-chain`,
    actor,
    signal,
  );
}

export function reportExportUrl(reportId: string, format: "html" | "pdf"): string {
  return `${apiBase}/api/v1/reports/${encodeURIComponent(reportId)}/${format}`;
}

export async function downloadFormalReport(
  report: Pick<FormalReport, "report_id" | "household_code" | "sequence">,
  format: "html" | "pdf",
  actor: DemoActor,
): Promise<void> {
  const path = reportExportUrl(report.report_id, format);
  const response = await fetch(path, { headers: actorHeaders(actor) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorEnvelope;
    throw new ReportApiError(response.status, payload, path);
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `wealthtwin-${report.household_code.toLowerCase()}-report-r${report.sequence}.${format}`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
