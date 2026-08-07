import { actorHeaders, demoActor } from "./actor";

export interface DemoHousehold {
  household_id: string;
  code: string;
  name: string;
  profile: string;
  valuation_date: string | null;
}

export interface DemoManifest {
  release_version: string;
  story_version: string;
  dataset_version: string;
  runtime_mode: string;
  mock_mode: boolean;
  external_network_required: false;
  ready: boolean;
  seeded_household_count: number;
  main_household_code: "DEMO_B";
  households: DemoHousehold[];
  latest_run_id: string | null;
  latest_run_status: string | null;
  preheated: boolean;
  preheated_at: string | null;
  cache_ttl_seconds: number;
  release_assets: Record<string, boolean>;
  boundaries: string[];
}

export interface DemoControlResult {
  action: "load" | "reset";
  dataset_version: string;
  loaded: number;
  skipped: number;
  removed: number;
  household_codes: string[];
  cache_cleared: boolean;
  message: string;
}

export interface DemoPreheatResult {
  story_version: string;
  status: "ready";
  warmed_components: string[];
  timings_ms: Record<string, number>;
  cache_expires_at: string;
  external_network_calls: 0;
  boundary_note: string;
}

export interface DemoStage {
  code: string;
  label: string;
  status: "completed" | "failed";
  progress_percent: number;
  duration_ms: number;
  evidence: Record<string, unknown>;
}

export interface DemoRun {
  run_id: string;
  household_id: string;
  household_code: string;
  story_version: string;
  status: "running" | "completed" | "failed";
  current_stage: string;
  progress_percent: number;
  stages: DemoStage[];
  artifacts: Record<string, Record<string, unknown>>;
  metrics: Record<string, unknown>;
  recovered_from_run_id: string | null;
  offline_mode: boolean;
  external_network_required: false;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  boundary_note: string;
}

export interface FourAccountComparison {
  bucket: string;
  name: string;
  recommended_amount: string;
  gap_amount: string;
}

export interface FamilyComparisonRow {
  household_id: string;
  code: string;
  name: string;
  profile: string;
  lifecycle_stage: string;
  total_assets: string;
  net_worth: string;
  annual_surplus: string;
  property_concentration: string | null;
  emergency_months: string | null;
  dynamic_safety_months: string;
  protection_gap: string;
  accounts: FourAccountComparison[];
  candidate_decisions: Record<string, string>;
  long_term_eligible_amount: string;
  configuration_signature: string;
  calculation_source: "deterministic_tools";
}

export interface FamilyComparison {
  comparison_version: string;
  generated_at: string;
  analysis_date: string;
  cache_status: "hit" | "miss";
  rows: FamilyComparisonRow[];
  unique_configuration_count: number;
  fixed_ratio_model: false;
  conclusion: string;
  boundary_note: string;
}

export interface ExperimentCase {
  code: string;
  name: string;
  status: "passed" | "protocol_ready" | "failed";
  measured: boolean;
  evidence: string[];
  metrics: Record<string, unknown>;
  boundary_note: string;
}

export interface ExperimentSuite {
  run_id: string;
  suite_version: string;
  status: "completed";
  passed: boolean;
  main_demo_run_id: string | null;
  cases: ExperimentCase[];
  metrics: Record<string, unknown>;
  started_at: string;
  completed_at: string;
  environment: "test";
  real_bank_results_claimed: false;
  boundary_note: string;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const adminHeaders = actorHeaders(demoActor("admin"));

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    headers: { Accept: "application/json", ...adminHeaders, ...init?.headers },
  });
  if (!response.ok) {
    let detail = `API ${response.status}: ${path}`;
    try {
      const payload = (await response.json()) as { error?: { message?: string } };
      detail = payload.error?.message ?? detail;
    } catch {
      // Keep the stable status/path fallback when the body is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function fetchDemoManifest(signal?: AbortSignal): Promise<DemoManifest> {
  return readJson("/api/v1/demo/manifest", { signal });
}

export function loadDemoData(): Promise<DemoControlResult> {
  return readJson("/api/v1/demo/load", { method: "POST" });
}

export function resetDemoData(): Promise<DemoControlResult> {
  return readJson("/api/v1/demo/reset", {
    method: "POST",
    headers: { "X-Confirm-Action": "reset_synthetic_demo" },
  });
}

export function preheatDemo(): Promise<DemoPreheatResult> {
  return readJson("/api/v1/demo/preheat", { method: "POST" });
}

export function fetchFamilyComparison(signal?: AbortSignal): Promise<FamilyComparison> {
  return readJson("/api/v1/demo/families/comparison", { signal });
}

export function runMainDemo(): Promise<DemoRun> {
  return readJson("/api/v1/demo/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path_count: 100 }),
  });
}

export function retryMainDemo(runId: string): Promise<DemoRun> {
  return readJson(`/api/v1/demo/runs/${encodeURIComponent(runId)}/retry`, {
    method: "POST",
  });
}

export function fetchLatestExperiments(signal?: AbortSignal): Promise<ExperimentSuite | null> {
  return readJson("/api/v1/demo/experiments/latest", { signal });
}

export function runDemoExperiments(): Promise<ExperimentSuite> {
  return readJson("/api/v1/demo/experiments/run", { method: "POST" });
}
