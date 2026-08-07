export type BehaviorRiskLevel = "low" | "medium_low" | "medium" | "medium_high" | "high";
export type BehaviorSessionState = "active" | "completed" | "exited";
export type InterventionState = "active" | "completed" | "dismissed";

export interface QuestionnaireDimension {
  code: keyof BehaviorQuestionnaire;
  name: string;
  prompt: string;
  low_label: string;
  high_label: string;
  weight: string;
}

export interface BehaviorExperiment {
  code: string;
  name: string;
  scenario: string;
  options: Array<{ code: string; label: string }>;
}

export interface ABVariant {
  code: string;
  name: string;
  description: string;
}

export interface BehaviorCatalog {
  rule_version: string;
  formula_version: string;
  experiment_version: string;
  ab_framework_version: string;
  source_type: "internal_demo";
  source_summary: string;
  questionnaire_dimensions: QuestionnaireDimension[];
  experiments: BehaviorExperiment[];
  bias_definitions: Array<{ code: string; name: string; description: string }>;
  intervention_definitions: Array<{
    code: string;
    name: string;
    trigger_biases: string[];
    scenario_code: string;
    action_instruction: string;
  }>;
  ab_variants: ABVariant[];
  required_experiment_count: 6;
  behavior_boundary: string;
}

export interface BehaviorQuestionnaire {
  risk_willingness: string;
  loss_tolerance_claim: string;
  investment_experience: string;
  knowledge: string;
  trading_frequency: string;
  attention: string;
  goal_discipline: string;
}

export interface BehaviorResponse {
  response_id: string;
  experiment_code: string;
  choice_code: string;
  choice_label: string;
  response_time_ms: number;
  modification_count: number;
  consistency_score: string;
  answered_at: string;
  evidence: string;
}

export interface BiasScore {
  code: string;
  name: string;
  description: string;
  score: string;
  severity: "low" | "watch" | "high";
  evidence: Array<{
    source: string;
    source_label: string;
    observation: string;
    contribution: string;
  }>;
  explanation: string;
}

export interface DualProfile {
  objective_capacity_score: string;
  objective_capacity_limit: BehaviorRiskLevel;
  questionnaire_score: string;
  questionnaire_claim_limit: BehaviorRiskLevel;
  experiment_score: string;
  experiment_limit: BehaviorRiskLevel;
  behavioral_limit_before_capacity: BehaviorRiskLevel;
  effective_risk_limit: BehaviorRiskLevel;
  risk_downshifted: boolean;
  conflict_detected: boolean;
  conflict_codes: string[];
  explanation: string;
  capacity_source_record_id: string;
}

export interface BehaviorIntervention {
  intervention_id: string | null;
  code: string;
  name: string;
  status: InterventionState;
  trigger_biases: string[];
  scenario_code: string;
  linked_goal_id: string | null;
  linked_goal_name: string | null;
  personalized_message: string;
  action_instruction: string;
  cooling_period_hours: number | null;
  starts_at: string | null;
  eligible_at: string | null;
  completed_at: string | null;
  dismissed_at: string | null;
  assigned_variant: string;
  audit_note: string;
}

export interface BehaviorProfile {
  meta: {
    household_id: string;
    household_code: string;
    household_name: string;
    analysis_date: string;
    data_as_of: string;
    source: "completed_session" | "synthetic_behavior_input";
    source_type: "synthetic_or_authorized_test_data";
    rule_version: string;
    formula_version: string;
    experiment_version: string;
    input_version: string;
    calculation_source: "deterministic_behavior_engine";
  };
  dual_profile: DualProfile;
  biases: BiasScore[];
  interventions: BehaviorIntervention[];
  responses: BehaviorResponse[];
  assigned_variant: string;
  assigned_variant_name: string;
  average_response_time_ms: number;
  total_modification_count: number;
  overall_consistency_score: string;
  limitations: string[];
}

export interface BehaviorSession {
  session_id: string;
  household_id: string;
  status: BehaviorSessionState;
  information_status: "collecting" | "sufficient" | "exited";
  answered_count: number;
  required_count: 6;
  remaining_experiment_codes: string[];
  assigned_variant: string;
  assigned_variant_name: string;
  experiment_key: string;
  questionnaire_score: string;
  questionnaire_claim_limit: BehaviorRiskLevel;
  objective_capacity_limit: BehaviorRiskLevel;
  effective_risk_limit: BehaviorRiskLevel | null;
  started_at: string;
  completed_at: string | null;
  exited_at: string | null;
  responses: BehaviorResponse[];
  profile: BehaviorProfile | null;
}

export interface BehaviorOverview {
  household_id: string;
  information_status: "sufficient" | "insufficient";
  information_message: string;
  profile: BehaviorProfile | null;
  latest_session: BehaviorSession | null;
  can_start_experiment: boolean;
  authorization_basis: string | null;
  limitations: string[];
}

export interface BehaviorABFramework {
  framework_version: string;
  experiment_key: string;
  eligible_data_policy: string;
  variants: ABVariant[];
  metrics: Array<{
    variant_code: string;
    variant_name: string;
    assigned_count: number;
    completed_count: number;
    exited_count: number;
    completion_rate: string | null;
    average_response_time_ms: number | null;
    risk_downshift_count: number;
    intervention_completed_count: number;
  }>;
  metric_definitions: Record<string, string>;
  privacy_note: string;
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

export function fetchBehaviorCatalog(signal?: AbortSignal): Promise<BehaviorCatalog> {
  return readJson("/api/v1/behavior/catalog", signal);
}

export function fetchBehaviorOverview(
  householdId: string,
  signal?: AbortSignal,
): Promise<BehaviorOverview> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/behavior`, signal);
}

export function startBehaviorSession(
  householdId: string,
  questionnaire: BehaviorQuestionnaire,
): Promise<BehaviorSession> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/behavior/sessions`, undefined, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_date: "2026-08-04", experiment_key: "behavior_nudge_main", questionnaire }),
  });
}

export function submitBehaviorResponse(
  householdId: string,
  sessionId: string,
  experimentCode: string,
  choiceCode: string,
  responseTimeMs: number,
  modificationCount: number,
): Promise<BehaviorSession> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/behavior/sessions/${encodeURIComponent(sessionId)}/responses/${encodeURIComponent(experimentCode)}`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ choice_code: choiceCode, response_time_ms: responseTimeMs, modification_count: modificationCount }),
    },
  );
}

export function completeBehaviorSession(
  householdId: string,
  sessionId: string,
): Promise<BehaviorSession> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/behavior/sessions/${encodeURIComponent(sessionId)}/complete`,
    undefined,
    { method: "POST" },
  );
}

export function exitBehaviorSession(
  householdId: string,
  sessionId: string,
): Promise<{ session_id: string; status: "exited"; exited_at: string; audit_event_id: string; message: string }> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/behavior/sessions/${encodeURIComponent(sessionId)}/exit`,
    undefined,
    { method: "POST" },
  );
}

export function updateBehaviorIntervention(
  householdId: string,
  interventionId: string,
  action: "complete" | "dismiss",
): Promise<BehaviorIntervention> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/behavior/interventions/${encodeURIComponent(interventionId)}/actions`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, reason_code: "user_choice" }),
    },
  );
}

export function fetchBehaviorABFramework(signal?: AbortSignal): Promise<BehaviorABFramework> {
  return readJson("/api/v1/behavior/ab-framework?experiment_key=behavior_nudge_main", signal);
}

export function behaviorExportUrl(householdId: string): string {
  return `${apiBase}/api/v1/households/${encodeURIComponent(householdId)}/behavior/export`;
}
