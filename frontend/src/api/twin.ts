export type TwinRunState = "queued" | "running" | "completed" | "cancelled" | "failed";

export interface ScenarioDefinition {
  code: string;
  name: string;
  category: string;
  description: string;
  parameters: Record<string, unknown>;
  explanation: string;
  scenario_version: string;
  source_type: "internal_demo";
  is_composable: boolean;
  enabled: boolean;
}

export interface ScenarioCatalog {
  scenario_version: string;
  source_type: "internal_demo";
  source_summary: string;
  scenario_count: number;
  scenarios: ScenarioDefinition[];
}

export interface TwinRunRequest {
  analysis_date: string;
  seed: number;
  path_count: number;
  horizon_years: number;
  output_interval_months: 1 | 3 | 6 | 12;
  scenario_codes: string[];
  scenario_overrides: {
    unemployment_months?: number;
    income_reduction_ratio?: string;
    medical_shock_amount?: string;
    education_overrun_amount?: string;
    property_value_change_ratio?: string;
    mortgage_rate_change?: string;
  };
  plan_adjustments: {
    primary_retirement_age: number;
    additional_monthly_savings: string;
    equity_ratio: string;
    liquidity_reallocation_amount: string;
  };
  assumption_overrides: {
    inflation_rate?: string;
    income_growth_rate?: string;
  };
  family_events: Array<{
    code: string;
    name: string;
    start_month: number;
    duration_months: number;
    one_time_cost: string;
    monthly_income_loss: string;
    monthly_expense_increase: string;
  }>;
}

export interface FanPoint {
  month: number;
  date: string;
  primary_age: string;
  p10: string;
  p25: string;
  p50: string;
  p75: string;
  p90: string;
  median_liquid_assets: string;
  median_long_term_assets: string;
  median_liabilities: string;
}

export interface GoalSimulationOutcome {
  goal_id: string;
  name: string;
  due_month: number;
  required_amount: string;
  success_probability: string;
  failure_probability: string;
  median_shortfall: string;
}

export interface SimulationDistribution {
  label: string;
  path_count: number;
  horizon_months: number;
  goal_success_probability: string;
  depletion_probability: string;
  forced_sale_probability: string;
  median_forced_sale_amount: string;
  ending_net_worth_median: string;
  ending_net_worth_p10: string;
  total_goal_shortfall_median: string;
  required_additional_monthly_savings: string;
  fan: FanPoint[];
  goal_outcomes: GoalSimulationOutcome[];
  failure_time_distribution: Array<{
    year: number;
    path_count: number;
    probability: string;
    most_common_goal: string | null;
  }>;
  worst_paths: Array<{
    path_id: number;
    ending_net_worth: string;
    minimum_net_worth: string;
    first_failed_goal: string | null;
    first_failure_month: number | null;
    depletion_month: number | null;
    forced_sale_amount: string;
    total_goal_shortfall: string;
    explanation: string;
  }>;
  validation: {
    all_values_finite: boolean;
    primary_income_paid_during_interruption_max: string;
    goal_spending_events_applied: number;
    common_random_numbers: boolean;
  };
}

export interface ScenarioImpact {
  scenario_code: string;
  name: string;
  emergency_support_months: string;
  first_failed_goal: string | null;
  forced_sale_probability: string;
  median_forced_sale_amount: string;
  insurance_coverage_applied: string;
  remaining_medical_gap: string;
  retirement_delay_needed: boolean;
  suggested_retirement_delay_years: number;
  monthly_compressible_expenses: string;
  required_additional_monthly_savings: string;
  baseline_goal_success_probability: string;
  scenario_goal_success_probability: string;
  success_probability_change: string;
  applicable: boolean;
  explanation: string;
}

export interface TwinResult {
  meta: {
    run_id: string;
    household_id: string;
    household_code: string;
    analysis_date: string;
    data_as_of: string;
    input_version: string;
    rule_code: string;
    rule_version: string;
    formula_version: string;
    engine_version: string;
    result_version: string;
    scenario_version: string;
    calculation_source: "deterministic_simulation_engine";
    synthetic_data: boolean;
    currency: string;
  };
  initial_state: {
    members: Array<{
      member_id: string;
      name: string;
      relationship: string;
      age_at_start: string;
      recorded_retirement_age: number | null;
    }>;
    annual_income: string;
    annual_expenses_excluding_debt_service: string;
    annual_essential_expenses_excluding_debt_service: string;
    monthly_compressible_expenses: string;
    asset_buckets: Record<string, string>;
    total_assets: string;
    total_liabilities: string;
    medical_coverage_available: string;
    medical_deductible: string;
    pension_annual_contributions: string;
    goals: Array<{
      goal_id: string;
      name: string;
      goal_type: string;
      due_month: number;
      current_amount: string;
      prepared_amount: string;
      annual_cost_growth_rate: string;
    }>;
    source_record_ids: string[];
    counting_note: string;
  };
  assumptions: {
    seed: number;
    path_count: number;
    horizon_months: number;
    time_step_months: number;
    output_interval_months: number;
    inflation_rate: string;
    income_growth_rate: string;
    asset_classes: string[];
    asset_assumptions: Record<string, { expected_annual_return: string; annual_volatility: string }>;
    correlation_matrix: string[][];
    property_assumption: { expected_annual_return: string; annual_volatility: string };
    pension_assumption: { expected_annual_return: string; annual_volatility: string };
    scenario_codes: string[];
    scenario_parameters: Record<string, unknown>;
    plan_adjustments: TwinRunRequest["plan_adjustments"];
    family_events: TwinRunRequest["family_events"];
    parameter_hash: string;
    source_type: "internal_demo";
  };
  baseline: SimulationDistribution;
  original_stress: SimulationDistribution;
  optimized_stress: SimulationDistribution;
  scenario_impacts: ScenarioImpact[];
  comparison: {
    baseline_success_probability: string;
    original_stress_success_probability: string;
    optimized_stress_success_probability: string;
    stress_change: string;
    optimization_change: string;
    baseline_forced_sale_probability: string;
    original_forced_sale_probability: string;
    optimized_forced_sale_probability: string;
    liquidity_reallocation_amount: string;
    avoided_forced_sale_probability: string;
    stress_not_better_than_baseline: boolean;
    positive_override_explanation: string | null;
    liquidity_explanation: string;
  };
  limitations: string[];
  counting_note: string;
}

export interface TwinRunStatus {
  run_id: string;
  household_id: string;
  status: TwinRunState;
  progress_percent: number;
  phase: string;
  scenario_codes: string[];
  path_count: number;
  horizon_months: number;
  seed: number;
  input_version: string;
  rule_version: string;
  engine_version: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  cancel_requested: boolean;
  audit_event_id: string | null;
  error_code: string | null;
  result: TwinResult | null;
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

export function fetchTwinScenarios(signal?: AbortSignal): Promise<ScenarioCatalog> {
  return readJson("/api/v1/twin/scenarios", signal);
}

export function createTwinRun(
  householdId: string,
  request: TwinRunRequest,
  signal?: AbortSignal,
): Promise<TwinRunStatus> {
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/twin/runs`, signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function advanceTwinRun(
  householdId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<TwinRunStatus> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/twin/runs/${encodeURIComponent(runId)}/advance`,
    signal,
    { method: "POST" },
  );
}

export function fetchTwinRun(
  householdId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<TwinRunStatus> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/twin/runs/${encodeURIComponent(runId)}`,
    signal,
  );
}

export function cancelTwinRun(householdId: string, runId: string): Promise<TwinRunStatus> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/twin/runs/${encodeURIComponent(runId)}/cancel`,
    undefined,
    { method: "POST" },
  );
}

export function twinExportUrl(householdId: string, runId: string): string {
  return `${apiBase}/api/v1/households/${encodeURIComponent(householdId)}/twin/runs/${encodeURIComponent(runId)}/export`;
}
