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
  | "total_household_assets"
  | "investable_financial_assets"
  | "annual_new_surplus"
  | "residual_long_term_plannable_capital";

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
    methodology_version: string;
    regional_parameter_version: string;
    market_regime_version: string;
    minimum_wage_snapshot_version: string;
    pension_policy_version: string;
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
    total_household_assets: string;
    investable_financial_assets: string;
    net_financial_assets_after_debt: string;
    plannable_financial_net_worth: string;
    growth_entry_threshold: string;
    residual_long_term_plannable_capital: string;
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
    denominator_id: "residual_long_term_plannable_capital";
    denominator_value: string;
    formal_growth_amount: string;
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
  methodology: MethodologyAssessment;
  asset_liquidity: {
    daily_liquid_assets: string;
    liquid_stable_assets: string;
    withdrawable_institutional_assets: string;
    locked_institutional_assets: string;
    growth_assets: string;
    locked_asset_ids: string[];
    withdrawable_asset_ids: string[];
    explanation: string;
  };
  current_allocation_plan: {
    denominator_id: "investable_financial_assets";
    current_investable_balance: string;
    debt_settlement_from_current_balance: string;
    current_balance_available_after_debt: string;
    explanation: string;
  };
  contribution_plan: {
    denominator_id: "annual_new_surplus";
    annual_new_surplus: string;
    recorded_premium_reclassification: string;
    same_period_commitments: string;
    future_contribution_available: string;
    explanation: string;
  };
  protection_plan: {
    version: string;
    annual_premium_cost: string;
    premium_affordability_ratio: string | null;
    needs: Array<{
      risk_code: string;
      label: string;
      required_coverage: string;
      existing_coverage: string;
      coverage_gap: string;
      annual_premium_cost: string;
      status: "covered" | "gap" | "needs_review" | "not_applicable";
      quote_status: "not_required" | "product_quote_required";
      explanation: string;
    }>;
    savings_and_protection_split_required: boolean;
    explanation: string;
  };
  decision_evidence: DecisionEvidencePackage;
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
  deprecated: boolean;
}

export interface AccountAllocation {
  bucket: AccountBucket;
  name: string;
  methodology_domain: "DAILY_LIQUIDITY" | "RISK_PROTECTION" | "STABILITY_AND_GOALS" | "LONG_TERM_GROWTH";
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
  primary_denominator_id: DenominatorId;
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

export interface DecisionEvidencePackage {
  evidence_version: string;
  household_input_version: string;
  methodology_version: string;
  financial_rule_version: string;
  planning_rule_version: string;
  regional_parameter_version: string;
  market_regime_version: string;
  minimum_wage_snapshot_version: string;
  pension_policy_version: string;
  portfolio_version: string;
  product_snapshot_version: string;
  risk_assessment_version: string;
  behavior_assessment_version: string;
  llm_model_version: string | null;
  llm_prompt_version: string | null;
  hard_gate_results: Record<string, string>;
  generated_at: string;
  decision_hash: string;
  calculation_source: "deterministic_tools";
}

export interface MethodologyAssessment {
  framework_code: "chfh";
  framework_name: "中国家庭财富健康理论";
  optimization_objective: string;
  methodology_code: string;
  methodology_version: string;
  formula_version: string;
  constitution: Array<{ code: string; title: string; rule: string; hard: boolean }>;
  regional_threshold: {
    policy_version: string;
    region_code: string;
    region_name: string;
    city_tier: string;
    policy_minimum: string;
    recommended_minimum: string;
    recommended_maximum: string;
    customer_selected_threshold: string;
    effective_threshold: string;
    explanation: string;
    evidence: Array<{
      factor: string;
      observed_value: string;
      adjustment_amount: string;
      explanation: string;
      source_record_ids: string[];
    }>;
  };
  market_regime: {
    snapshot_version: string;
    regime: "favorable" | "neutral" | "defensive";
    label: string;
    valuation_date: string;
    effective_from: string;
    effective_to: string | null;
    source: string;
    methodology: string;
    evidence: string[];
    rule_version: string;
    approved_by: string;
    is_demo: boolean;
    customer_editable: false;
    llm_generated: false;
  };
  minimum_wage_snapshot: {
    region_code: string;
    region_name: string;
    cagr: string;
    period_years: string;
    status: "available" | "degraded" | "fallback";
    source_reference: string;
    observed_at: string;
    version: string;
    is_live: boolean;
    is_demo: boolean;
    is_cpi: false;
  };
  purchasing_power_hurdle: {
    version: string;
    rate: string;
    formula: string;
    components: Array<{
      code: "official_cpi_trend" | "family_weighted_expense_inflation" | "regional_minimum_wage_cagr";
      label: string;
      rate: string;
      data_as_of: string;
      source: string;
      version: string;
      status: "available" | "degraded" | "fallback";
      is_cpi: boolean;
    }>;
    explanation: string;
    minimum_wage_is_cpi: false;
    is_return_guarantee: false;
  };
  responsibility_ledger: {
    version: string;
    entries: Array<{
      responsibility_id: string;
      beneficiary: string;
      responsibility_type: string;
      target_amount: string;
      minimum_acceptable_amount: string;
      target_date: string;
      rigidity: string;
      deferrable: boolean;
      prepared_amount: string;
      institutional_coverage: string;
    }>;
    total_target_amount: string;
    total_minimum_amount: string;
    total_prepared_amount: string;
    total_institutional_coverage: string;
    explanation: string;
  };
  institutional_coverage: {
    version: string;
    social_security_balance: string;
    provident_fund_balance: string;
    enterprise_annuity_balance: string;
    occupational_annuity_balance: string;
    personal_pension_balance: string;
    locked_balance: string;
    withdrawable_balance: string;
    retirement_income_floor: {
      required_annual_floor: string | null;
      covered_annual_income: string | null;
      coverage_ratio: string | null;
      status: "available" | "needs_review" | "not_applicable";
      explanation: string;
    };
    explanation: string;
  };
  personal_pension: {
    policy: {
      policy_version: string;
      annual_contribution_limit: string;
      withdrawal_tax_rate: string;
      effective_from: string;
      effective_to: string | null;
      source_system: string;
      source_reference: string;
      observed_at: string;
      effective_at: string;
      ingested_at: string;
      version: string;
      data_quality: string;
      is_live: boolean;
      is_demo: boolean;
      lineage: string;
    };
    eligibility_status: "eligible" | "not_eligible" | "needs_review";
    annual_contribution_amount: string;
    contribution_limit: string;
    contribution_progress_ratio: string;
    remaining_contribution_capacity: string;
    assumed_marginal_tax_rate: string;
    estimated_current_year_tax_benefit: string;
    account_balance: string;
    product_risk_allocation: Array<{
      asset_id: string;
      asset_name: string;
      market_value: string;
      risk_level: string;
      principal_loss_possible: boolean;
      liquidity_days: number;
      lock_up: boolean;
    }>;
    reminder_state: "not_needed" | "review_eligibility" | "contribution_available";
    retirement_projection_status: "available" | "needs_more_data";
    explanation: string;
  };
  property_policy: {
    policy_version: string;
    status: "restricted_by_default" | "review_required" | "available";
    valuation_date: string;
    source: string;
    is_demo: boolean;
    rules: string[];
  };
  financial_journey: {
    state: "financial_recovery" | "wealth_accumulation" | "wealth_growth" | "complex_wealth_management";
    label: string;
    investment_mode: "no_investment_sales" | "safety_and_learning" | "full_portfolio" | "human_in_loop";
    explanation: string;
  };
  grb: {
    code: "grb";
    version: string;
    formula: string;
    goal_count: number;
    rigid_goal_count: number;
    nearest_goal_date: string | null;
    goal_status: "ready" | "needs_input";
    goal_summary: string;
    risk_status: "ready" | "partial" | "needs_input";
    capacity_score: string | null;
    willingness_score: string | null;
    effective_risk_limit: string | null;
    risk_summary: string;
    behavior_status: "ready" | "partial" | "needs_input";
    revealed_behavior_score: string | null;
    detected_biases: string[];
    behavior_summary: string;
    behavior_can_only_downshift: true;
    formal_suitability_required: true;
  };
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
