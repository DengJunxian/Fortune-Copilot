import type { KnowledgeCitation } from "./trust";

export type ClientView =
  | "family"
  | "balance"
  | "cashflow"
  | "health"
  | "accounts"
  | "pension"
  | "goals"
  | "twin"
  | "behavior"
  | "report"
  | "actions"
  | "privacy";

export interface ClientJourneyStep {
  code: string;
  label: string;
  status: "completed" | "ready" | "needs_action" | "blocked";
  reason: string;
  action: string;
  view: ClientView;
}

export interface PrivacyConsent {
  id: string;
  scopes: string[];
  purpose: string;
  granted_at: string;
  withdrawn_at: string | null;
  consent_version: string;
  record_version: number;
  status: "active" | "withdrawn";
  withdrawal_allowed: boolean;
  scenario: string;
  sensitive: boolean;
  explicit: boolean;
  minimum_necessary: boolean;
}

export interface ClientPrivacySummary {
  active_consent_count: number;
  withdrawn_consent_count: number;
  consents: PrivacyConsent[];
  export_path: string;
  delete_path: string;
  deletion_mode: "logical_erasure_with_confirmation";
  human_review_path: string;
  boundary_note: string;
}

export interface ActionCalendarItem {
  code: string;
  title: string;
  detail: string;
  why: string;
  constraint_or_formula: string;
  change_trigger: string;
  risk_and_assumptions: string;
  amount: string;
  due_date: string | null;
  priority: number;
  source_record_ids: string[];
  calculation_source: "deterministic_planning_rules" | "deterministic_review_schedule";
}

export interface ActionCalendarGroup {
  code: "immediate" | "three_months" | "one_year" | "long_term" | "next_12_months";
  label: string;
  description: string;
  items: ActionCalendarItem[];
}

export interface ClientReportChapter {
  number: number;
  title: string;
  summary: string;
  calculation_basis: string[];
  citation_ids: string[];
  status: "ready" | "pending_twin" | "needs_review";
}

export interface ClientReportPreview {
  report_version: string;
  knowledge_retrieval_version: string;
  title: string;
  subtitle: string;
  chapter_count: 8;
  chapters: ClientReportChapter[];
  citations: KnowledgeCitation[];
  generated_at: string;
  data_as_of: string;
  calculation_source: "deterministic_client_experience_composer";
  boundary_note: string;
}

export interface ClientDeliveryState {
  report: "not_generated" | "under_review" | "client_ready";
  workflow: "not_created" | "under_review" | "client_ready";
  actions: "not_generated" | "under_review" | "client_ready";
  explanation: string;
}

export interface ClientExperience {
  household_id: string;
  household_code: string;
  household_name: string;
  household_version: number;
  synthetic_data: boolean;
  analysis_date: string;
  data_as_of: string;
  journey: ClientJourneyStep[];
  privacy: ClientPrivacySummary;
  action_calendar: ActionCalendarGroup[];
  report: ClientReportPreview;
  delivery: ClientDeliveryState;
  calculation_versions: Record<string, string>;
  state_catalog: string[];
  mock_mode_supported: true;
}

export interface HumanReviewResponse {
  request_id: string;
  household_id: string;
  status: "queued";
  queue: "demo_advisor_queue";
  created_at: string;
  message: string;
}

export interface PrivacyRequestResult {
  request_id: string;
  request_type: "export" | "erase";
  status: "completed" | "rejected";
  result_summary: Record<string, unknown>;
}

export interface PrivacyExportResponse {
  request: PrivacyRequestResult;
  package_version: string;
  exported_at: string;
  household_ref: string;
  data: Record<string, unknown>;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function readJson<T>(path: string, signal?: AbortSignal, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    signal,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return (await response.json()) as T;
}

export function fetchClientExperience(
  householdId: string,
  signal?: AbortSignal,
): Promise<ClientExperience> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/client-experience`,
    signal,
  );
}

export function clientExperienceExportUrl(householdId: string): string {
  return `${apiBase}/api/v1/households/${encodeURIComponent(householdId)}/client-experience/export`;
}

export async function exportHouseholdData(householdId: string): Promise<void> {
  const result = await readJson<PrivacyExportResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/privacy/exports`,
    undefined,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Confirm-Action": "export_household_data",
      },
      body: JSON.stringify({ reason: "客户在隐私中心主动导出家庭数据" }),
    },
  );
  const blobUrl = URL.createObjectURL(
    new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = `wealthtwin-privacy-export-${result.household_ref}.json`;
  link.click();
  URL.revokeObjectURL(blobUrl);
}

export function withdrawPrivacyConsent(
  householdId: string,
  consentId: string,
  expectedVersion: number,
  reason: string,
): Promise<PrivacyConsent> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/privacy/consents/${encodeURIComponent(consentId)}/withdraw`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_version: expectedVersion, reason }),
    },
  );
}

export function requestHumanReview(
  householdId: string,
  reason: string,
): Promise<HumanReviewResponse> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/privacy/human-review-requests`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, context: "client_privacy_center" }),
    },
  );
}

export async function deleteHouseholdData(
  householdId: string,
  expectedVersion: number,
  householdCode: string,
  reason: string,
): Promise<PrivacyRequestResult> {
  return readJson<PrivacyRequestResult>(
    `/api/v1/households/${encodeURIComponent(householdId)}/privacy/deletion-requests`,
    undefined,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Confirm-Action": "erase_household_data",
      },
      body: JSON.stringify({
        expected_version: expectedVersion,
        household_code_confirmation: householdCode,
        reason,
      }),
    },
  );
}
