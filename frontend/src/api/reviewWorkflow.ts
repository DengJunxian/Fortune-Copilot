import { actorHeaders, type DemoActor } from "./actor";
import type { CandidateType, SuitabilityDecision, SuitabilityStatus } from "./portfolio";

export type PlanWorkflowState =
  | "draft"
  | "calculated"
  | "suitability_checked"
  | "advisor_reviewed"
  | "compliance_reviewed"
  | "customer_confirmed"
  | "active"
  | "superseded";

export type PlanWorkflowAction =
  | "create"
  | "calculate"
  | "suitability_check"
  | "advisor_review"
  | "revise_advice"
  | "edit_communication"
  | "submit_compliance"
  | "compliance_approve"
  | "compliance_return"
  | "require_human_review"
  | "customer_confirm"
  | "activate"
  | "supersede";

export interface WorkflowVersionLedger {
  input_version: string;
  rule_version: string;
  model_version: string;
  prompt_version: string;
  knowledge_version: string;
  product_catalog_version: string;
}

export interface PlanWorkflowVersion {
  id: string;
  workflow_id: string;
  household_id: string;
  version_number: number;
  cycle: number;
  prior_version_id: string | null;
  state: PlanWorkflowState;
  action: PlanWorkflowAction;
  reason: string;
  actor_id: string;
  actor_role: DemoActor["role"];
  selected_candidate: CandidateType | null;
  recommendation_snapshot: Record<string, unknown>;
  suitability_snapshot: Record<string, unknown>;
  communication_draft: string;
  advisor_decision: string | null;
  compliance_decision: string | null;
  customer_confirmation: Record<string, unknown>;
  submitted_for_compliance: boolean;
  requires_human_review: boolean;
  is_current: boolean;
  versions: WorkflowVersionLedger;
  before_hash: string;
  after_hash: string;
  request_id: string;
  created_at: string;
}

export interface PlanWorkflow {
  workflow_id: string;
  household_id: string;
  current: PlanWorkflowVersion;
  versions: PlanWorkflowVersion[];
  state_order: PlanWorkflowState[];
  next_actions: PlanWorkflowAction[];
  traceable: true;
}

export interface AdvisorHouseholdSummary {
  household_id: string;
  household_code: string;
  household_name: string;
  lifecycle_stage: string;
  region: string;
  data_as_of: string;
  net_worth: string;
  annual_surplus: string;
  anomaly_count: number;
  goal_conflict_count: number;
  highest_attention: "normal" | "attention" | "warning" | "critical";
  workflow_id: string | null;
  workflow_state: PlanWorkflowState | null;
  workflow_version: number | null;
  signature_status: "not_ready" | "pending" | "confirmed" | "active";
  synthetic_data: boolean;
}

export interface AdvisorHouseholdList {
  generated_at: string;
  calculation_source: "deterministic_advisor_queue";
  items: AdvisorHouseholdSummary[];
}

export interface AdvisorCandidateSummary {
  candidate_type: CandidateType;
  name: string;
  decision: SuitabilityDecision;
  investment_amount: string;
  expected_nominal_return: string;
  max_drawdown_estimate: string;
  extreme_loss_amount: string;
  liquidity_score: string;
  annual_fee_estimate: string;
  product_type_reasons: string[];
  primary_risks: string[];
}

export interface MockBankEntry {
  record_id: string;
  display_name: string;
  amount: string;
  amount_role: "asset" | "liability" | "coverage" | "cashflow_in" | "cashflow_out" | "information_only";
  source_record_ids: string[];
  details: Record<string, unknown>;
  boundary_note: string;
}

export interface MockBankInterface {
  code: "accounts" | "credit_cards" | "mortgages" | "wealth_management" | "funds" | "insurance" | "personal_pension" | "cash_flow";
  label: string;
  status: "available" | "empty";
  entries: MockBankEntry[];
}

export interface MockBankSnapshot {
  adapter: "mock_bank_adapter";
  adapter_version: string;
  mock: true;
  official_connection: false;
  household_id: string;
  household_code: string;
  data_as_of: string;
  interfaces: MockBankInterface[];
  reconciled_asset_total: string;
  reconciled_liability_total: string;
  credit_limit_in_total_assets: false;
  source: "synthetic_household_records";
  boundary_note: string;
}

export interface AdvisorDossier {
  generated_at: string;
  household: AdvisorHouseholdSummary;
  members: Array<Record<string, unknown>>;
  premeeting_questions: string[];
  financial_anomalies: Array<Record<string, unknown>>;
  goal_conflicts: Array<Record<string, unknown>>;
  candidates: AdvisorCandidateSummary[];
  risk_and_liquidity_notes: string[];
  suggested_communication_draft: string;
  communication_source: "editable_mock_template";
  monthly_review_reminders: Array<Record<string, unknown>>;
  mock_bank: MockBankSnapshot;
  boundary_note: string;
}

export interface ComplianceControl {
  code: string;
  category: string;
  status: "pass" | "warning" | "block" | "information";
  title: string;
  explanation: string;
  rule: string;
  source_record_ids: string[];
}

export interface ComplianceEvidence {
  workflow_id: string;
  version_id: string;
  version_number: number;
  household_id: string;
  overall_decision: "pass" | "block" | "human_review";
  controls: ComplianceControl[];
  three_gate_statuses: Record<string, SuitabilityStatus>;
  blocked_codes: string[];
  warning_codes: string[];
  prohibited_phrases: string[];
  numeric_ledger: Record<string, string>;
  security_events: Array<Record<string, unknown>>;
  versions: WorkflowVersionLedger;
  hash_chain_verified: boolean;
  explanation: string;
}

export interface ComplianceQueueItem {
  workflow_id: string;
  household_id: string;
  household_code: string;
  household_name: string;
  version_id: string;
  version_number: number;
  state: PlanWorkflowState;
  submitted_for_compliance: boolean;
  requires_human_review: boolean;
  selected_candidate: CandidateType | null;
  created_at: string;
  blocked_count: number;
  warning_count: number;
  recommendation_reason: string;
}

export interface ComplianceQueue {
  generated_at: string;
  items: ComplianceQueueItem[];
}

export interface ComplaintReplay {
  replay_id: string;
  workflow_id: string;
  requested_version_id: string;
  household_id: string;
  generated_at: string;
  request_id: string;
  timeline: Array<Record<string, unknown>>;
  audit_events: Array<Record<string, unknown>>;
  integrity_status: "verified";
  package_hash: string;
  boundary_note: string;
}

export type DecisionEvidenceStatus = "bound" | "not_available" | "not_applicable";

export interface DecisionEvidenceSection {
  status: DecisionEvidenceStatus;
  version: string;
  source_record_ids: string[];
  decision_inputs: Record<string, unknown>;
  snapshot: unknown;
  display_only_text: string | null;
}

export interface DecisionEvidenceV2 {
  evidence_version: "decision-evidence-v2.0.0";
  decision_id: string;
  decision_type: "plan_workflow" | "recommendation" | "plan_report";
  household_id: string;
  household_input: DecisionEvidenceSection;
  financial_graph: DecisionEvidenceSection;
  client_profile: DecisionEvidenceSection;
  wealth_needs: DecisionEvidenceSection;
  liability: DecisionEvidenceSection;
  ELTC: DecisionEvidenceSection;
  risk_budget: DecisionEvidenceSection;
  enterprise: DecisionEvidenceSection;
  CFS: DecisionEvidenceSection;
  product_snapshot: DecisionEvidenceSection;
  suitability: DecisionEvidenceSection;
  calibration: DecisionEvidenceSection;
  advisor: DecisionEvidenceSection;
  client_confirmation: DecisionEvidenceSection;
  generated_at: string;
  decision_hash: string;
  calculation_source: "deterministic_evidence_v2";
}

export interface DecisionReplayV2 {
  decision_id: string;
  decision_type: DecisionEvidenceV2["decision_type"];
  household_id: string;
  replayed_from: "frozen_decision_evidence";
  stored_decision_hash: string;
  replay_decision_hash: string;
  hash_identical: boolean;
  used_snapshot_versions: Record<string, string>;
  latest_product_data_used: false;
  replayed_at: string;
  evidence: DecisionEvidenceV2;
}

export interface WorkflowActionInput {
  action: PlanWorkflowAction;
  expected_version: number;
  reason: string;
  selected_candidate?: CandidateType;
  communication_draft?: string;
  advisor_note?: string;
  compliance_note?: string;
  manual_high_risk_confirmed?: boolean;
  human_review_completed?: boolean;
  customer_name?: string;
  acknowledgements?: Array<"risk_read" | "mock_understood" | "not_guaranteed">;
  replacement_workflow_id?: string;
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

export class WorkflowApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, payload: ErrorEnvelope, path: string) {
    super(payload.error?.message ?? `API ${status}: ${path}`);
    this.name = "WorkflowApiError";
    this.status = status;
    this.code = payload.error?.code ?? "workflow_api_error";
    this.details = payload.error?.details;
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
    headers: {
      Accept: "application/json",
      ...actorHeaders(actor),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorEnvelope;
    throw new WorkflowApiError(response.status, payload, path);
  }
  return await response.json() as T;
}

export function fetchAdvisorHouseholds(actor: DemoActor, signal?: AbortSignal): Promise<AdvisorHouseholdList> {
  return readJson("/api/v1/advisor/households", actor, signal);
}

export function fetchAdvisorDossier(householdId: string, actor: DemoActor, signal?: AbortSignal): Promise<AdvisorDossier> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/advisor-dossier`, actor, signal);
}

export function fetchCurrentWorkflow(householdId: string, actor: DemoActor, signal?: AbortSignal): Promise<PlanWorkflow | null> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/plan-workflows/current`, actor, signal);
}

export function fetchWorkflow(workflowId: string, actor: DemoActor, signal?: AbortSignal): Promise<PlanWorkflow> {
  return readJson(`/api/v1/plan-workflows/${encodeURIComponent(workflowId)}`, actor, signal);
}

export function createPlanWorkflow(householdId: string, actor: DemoActor, reason: string): Promise<PlanWorkflow> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/plan-workflows`, actor, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
}

export function transitionWorkflow(workflowId: string, actor: DemoActor, input: WorkflowActionInput): Promise<PlanWorkflow> {
  return readJson(`/api/v1/plan-workflows/${encodeURIComponent(workflowId)}/actions`, actor, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function fetchComplianceQueue(actor: DemoActor, signal?: AbortSignal): Promise<ComplianceQueue> {
  return readJson("/api/v1/compliance/review-queue", actor, signal);
}

export function fetchComplianceEvidence(workflowId: string, actor: DemoActor, signal?: AbortSignal): Promise<ComplianceEvidence> {
  return readJson(`/api/v1/plan-workflows/${encodeURIComponent(workflowId)}/compliance-evidence`, actor, signal);
}

export function replayComplaint(workflowId: string, versionId: string, reason: string, actor: DemoActor): Promise<ComplaintReplay> {
  return readJson(`/api/v1/plan-workflows/${encodeURIComponent(workflowId)}/complaint-replays`, actor, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version_id: versionId, reason }),
  });
}

export function fetchDecisionEvidence(decisionId: string, actor: DemoActor, signal?: AbortSignal): Promise<DecisionEvidenceV2> {
  return readJson(`/api/v1/decisions/${encodeURIComponent(decisionId)}/evidence`, actor, signal);
}

export function replayDecision(decisionId: string, actor: DemoActor): Promise<DecisionReplayV2> {
  return readJson(`/api/v1/decisions/${encodeURIComponent(decisionId)}/replay`, actor, undefined, {
    method: "POST",
  });
}

export async function downloadWorkflowAudit(workflowId: string, actor: DemoActor): Promise<void> {
  const path = `/api/v1/plan-workflows/${encodeURIComponent(workflowId)}/audit-export`;
  const response = await fetch(apiBase + path, {
    headers: { Accept: "application/json", ...actorHeaders(actor) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorEnvelope;
    throw new WorkflowApiError(response.status, payload, path);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `wealthtwin-workflow-${workflowId.slice(0, 8)}-audit.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
