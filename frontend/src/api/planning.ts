export type LifecycleStage =
  | "early_career"
  | "family_formation"
  | "parenting"
  | "mature_family"
  | "retirement_preparation"
  | "retirement_and_legacy";

export type AccountBucket =
  | "daily_liquidity"
  | "risk_protection"
  | "stable_goals"
  | "long_term_growth";

export type DenominatorId =
  | "total_assets"
  | "investable_financial_assets"
  | "annual_new_surplus";

export interface PlanningResponse {
  meta: {
    household_id: string;
    household_code: string;
    analysis_date: string;
    data_as_of: string;
    input_version: string;
    formula_version: string;
    rule_code: string;
    rule_version: string;
    rule_source_type: "internal_demo";
    calculation_source: "deterministic_tools";
    currency: string;
    synthetic_data: boolean;
    scenario_type: "base" | "counterfactual";
  };
  lifecycle: {
    detected_stage: LifecycleStage;
    recorded_stage: LifecycleStage;
    effective_stage: LifecycleStage;
    override_applied: boolean;
    dynamic_safety_months: string;
    base_safety_months: string;
    formula: string;
    substitution: string;
    explanation: string;
    evidence: Array<{
      factor: string;
      label: string;
      observed_value: string;
      adjustment_months: string;
      source_record_ids: string[];
    }>;
  };
  goals: GoalProjection[];
  conflicts: GoalConflict[];
  denominators: {
    total_assets: string;
    investable_financial_assets: string;
    net_financial_assets_after_debt: string;
    growth_entry_threshold: string;
    annual_new_surplus: string;
    available_planning_resources: string;
    high_interest_debt_before_plan: string;
    high_interest_debt_after_counterfactual: string;
    same_period_cashflow_committed: string;
  };
  waterfall_steps: WaterfallStep[];
  constraints: ConstraintResult[];
  accounts: AccountAllocation[];
  investment_learning: {
    applicable: boolean;
    eligible: boolean;
    cap_ratio: string;
    recommended_ratio: string | null;
    recommended_amount: string;
    denominator_name: string;
    denominator_value: string;
    conditions: string[];
    failed_conditions: string[];
    explanation: string;
  };
  growth_70: {
    eligible: boolean;
    threshold: string;
    actual_ratio: string | null;
    denominator_name: string;
    denominator_value: string;
    conditions: string[];
    failed_conditions: string[];
    explanation: string;
  };
  growth_benchmark: {
    benchmark_rate: string;
    components: Record<string, string>;
    formula: string;
    explanation: string;
    minimum_wage_is_cpi: false;
    is_return_guarantee: false;
  };
  actions: ActionDraft[];
  applied_counterfactual: CounterfactualRequest;
  counting_note: string;
}

export interface GoalProjection {
  goal_id: string;
  name: string;
  goal_type: string;
  target_date: string;
  adjusted_target_date: string;
  months_remaining: number;
  current_cost: string;
  future_amount: string;
  present_value: string;
  minimum_present_value: string;
  prepared_amount: string;
  funding_gap: string;
  minimum_funding_gap: string;
  monthly_required: string;
  annual_required: string;
  priority: number;
  rigidity: string;
  can_defer: boolean;
  annual_cost_growth_rate: string;
  status: "funded" | "on_track" | "gap" | "conflict";
  formula: string;
  substitution: string;
  source_record_ids: string[];
}

export interface GoalConflict {
  conflict_id: string;
  severity: "attention" | "warning" | "critical";
  title: string;
  detail: string;
  affected_goal_ids: string[];
  available_monthly_surplus: string;
  required_monthly_contribution: string;
  monthly_shortfall: string;
  adjustments: Array<{
    action_code: string;
    title: string;
    detail: string;
    affected_goal_ids: string[];
    monthly_effect: string;
    preserves_minimum: boolean;
  }>;
}

export interface RatioMeasure {
  denominator_id: DenominatorId;
  denominator_name: string;
  denominator_value: string;
  ratio: string | null;
  applicable: boolean;
  reason: string;
}

export interface AccountAllocation {
  bucket: AccountBucket;
  name: string;
  sequence: number;
  current_amount: string;
  target_amount: string;
  recommended_amount: string;
  recommended_range_min: string;
  recommended_range_max: string;
  gap_amount: string;
  annual_cost_amount: string;
  coverage_gap_amount: string;
  primary_denominator_name: string;
  reference_band: {
    denominator_id: DenominatorId;
    denominator_name: string;
    minimum_ratio: string;
    maximum_ratio: string;
    target_ratio: string;
    overall_minimum_ratio: string;
    overall_maximum_ratio: string;
    market_regime: "favorable" | "neutral" | "defensive";
    market_regime_label: string;
    binding: boolean;
    conditions: string[];
    explanation: string;
  } | null;
  current_measures: RatioMeasure[];
  target_measures: RatioMeasure[];
  measures: RatioMeasure[];
  formula: string;
  substitution: string;
  rationale: string;
  constraint_ids: string[];
  source_record_ids: string[];
  product_education: string[];
}

export interface WaterfallStep {
  sequence: number;
  step_code: string;
  name: string;
  required_amount: string;
  allocated_amount: string;
  remaining_resources: string;
  status: "covered" | "partial" | "unfunded" | "cashflow_covered" | "informational";
  formula: string;
  explanation: string;
  source_record_ids: string[];
}

export interface ConstraintResult {
  constraint_id: string;
  constraint_type: "hard" | "soft";
  name: string;
  status: "pass" | "limit" | "block" | "not_evaluated";
  observed_value: string;
  required_condition: string;
  effect: string;
  limits_growth: boolean;
  source_record_ids: string[];
}

export interface ActionDraft {
  priority: number;
  action_code: string;
  title: string;
  detail: string;
  amount: string;
  due_date: string | null;
  account_bucket: AccountBucket | null;
  source_record_ids: string[];
}

export interface CounterfactualRequest {
  analysis_date?: string | null;
  emergency_fund_addition?: string;
  high_interest_debt_reduction?: string;
  protection_gap_reduction?: string;
  monthly_savings_increase?: string;
  goal_prepared_additions?: Record<string, string>;
  defer_goal_ids?: string[];
  defer_months?: number;
  lifecycle_override?: LifecycleStage | null;
}

export interface CounterfactualResponse {
  base: PlanningResponse;
  scenario: PlanningResponse;
  changes: Array<{
    code: string;
    label: string;
    before: string | boolean;
    after: string | boolean;
    delta: string | null;
    explanation: string;
  }>;
  explanation: string;
}

export interface GoalCreateInput {
  name: string;
  goal_type: string;
  target_amount: string;
  target_date: string;
  rigidity: string;
  priority: number;
  can_defer: boolean;
  minimum_acceptable_amount: string;
  prepared_amount: string;
  annual_cost_growth_rate: string;
}

export interface PersistedPlanningRun {
  recommendation_id: string;
  account_plan_ids: string[];
  action_item_ids: string[];
  household_id: string;
  input_version: string;
  rule_version_id: string;
  rule_version: string;
  account_count: number;
  action_count: number;
  created_at: string;
  calculation_source: "deterministic_tools";
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

export function fetchPlanning(
  householdId: string,
  signal?: AbortSignal,
  lifecycleOverride?: LifecycleStage,
): Promise<PlanningResponse> {
  const query = lifecycleOverride
    ? `?lifecycle_override=${encodeURIComponent(lifecycleOverride)}`
    : "";
  return readJson<PlanningResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/planning${query}`,
    signal,
  );
}

export function recalculatePlanning(
  householdId: string,
  request: CounterfactualRequest,
): Promise<CounterfactualResponse> {
  return readJson<CounterfactualResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/planning/counterfactual`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export function createGoal(householdId: string, input: GoalCreateInput): Promise<unknown> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/goals`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...input,
        currency: "CNY",
        data_source: "client_confirmed_input",
        is_user_confirmed: true,
      }),
    },
  );
}

export function persistPlanning(householdId: string): Promise<PersistedPlanningRun> {
  return readJson<PersistedPlanningRun>(
    `/api/v1/households/${encodeURIComponent(householdId)}/planning/runs`,
    undefined,
    { method: "POST" },
  );
}

export function planningExportUrl(householdId: string): string {
  return apiBase + `/api/v1/households/${encodeURIComponent(householdId)}/planning/export`;
}
