export type MarketScenario = "neutral" | "risk_off" | "risk_on";
export type CandidateType = "conservative" | "balanced" | "growth";
export type SuitabilityDecision = "allow" | "downgrade" | "reject" | "education_only";
export type SuitabilityStatus = "pass" | "restrict" | "block";
export type ProductRiskLevel = "r1" | "r2" | "r3" | "r4" | "r5";

export interface SuitabilityCheckItem {
  check_code: string;
  label: string;
  status: SuitabilityStatus;
  observed_value: string;
  rule: string;
  reason: string;
  source_record_ids: string[];
}

export interface SuitabilityGate {
  gate: "family_safety" | "customer" | "product";
  name: string;
  status: SuitabilityStatus;
  decision: SuitabilityDecision;
  effective_risk_limit: ProductRiskLevel | null;
  high_risk_cap: string | null;
  checks: SuitabilityCheckItem[];
  failed_check_codes: string[];
  explanation: string;
}

export interface AllocationLine {
  asset_class: string;
  asset_class_name: string;
  ratio: string;
  amount: string;
  expected_nominal_return: string;
  cvar_loss: string;
  max_drawdown: string;
  liquidity_score: string;
}

export interface ProductMapping {
  asset_class: string;
  asset_class_name: string;
  allocation_ratio: string;
  allocation_amount: string;
  product_id: string | null;
  product_code: string | null;
  product_name: string;
  product_type: string;
  risk_level: ProductRiskLevel | null;
  liquidity_level: string | null;
  decision: SuitabilityDecision;
  reasons: string[];
  is_mock: boolean;
}

export interface RebalanceLine {
  asset_class: string;
  asset_class_name: string;
  current_ratio: string;
  strategic_ratio: string;
  tactical_ratio: string;
  absolute_drift: string;
  relative_drift: string | null;
  trigger: boolean;
  action: string;
}

export interface PortfolioCandidate {
  candidate_type: CandidateType;
  name: string;
  decision: SuitabilityDecision;
  investment_amount: string;
  strategic_allocations: AllocationLine[];
  tactical_allocations: AllocationLine[];
  expected_nominal_return: string;
  expected_real_return: string;
  goal_success_probability: string;
  simulation_method: "deterministic_weighted_scenarios_not_monte_carlo";
  simulation_horizon_months: number;
  simulated_range_low: string;
  simulated_range_base: string;
  simulated_range_high: string;
  extreme_loss_ratio: string;
  extreme_loss_amount: string;
  max_drawdown_estimate: string;
  liquidity_score: string;
  liquidity_description: string;
  annual_fee_rate: string;
  annual_fee_estimate: string;
  applicable_conditions: string[];
  primary_risks: string[];
  why_not_other_candidates: string;
  gates: SuitabilityGate[];
  product_mappings: ProductMapping[];
  optimization: {
    method: "deterministic_grid_search" | "rule_based_fallback";
    status: "optimal" | "fallback" | "infeasible";
    optimizer_version: string;
    random_seed: number;
    grid_step: string;
    evaluated_candidates: number;
    objective_score: string;
    parameter_hash: string;
    parameters: Record<string, unknown>;
    fallback_reason: string | null;
  };
  rebalancing: {
    market_scenario: MarketScenario;
    status: "within_band" | "rebalance_due" | "blocked_by_safety";
    absolute_threshold: string;
    relative_threshold: string;
    maximum_tactical_shift: string;
    next_scheduled_review: string;
    lines: RebalanceLine[];
    explanation: string;
  };
}

export interface MockProduct {
  id: string;
  code: string;
  name: string;
  product_type: string;
  asset_class: string;
  risk_level: ProductRiskLevel;
  term_months: number;
  minimum_holding_months: number;
  liquidity_level: string;
  redemption_rules: string;
  annual_fee_rate: string;
  underlying_assets: string[];
  historical_volatility_min: string;
  historical_volatility_max: string;
  minimum_investment: string;
  suitable_accounts: string[];
  principal_guaranteed: boolean;
  guarantee_basis: string | null;
  guarantee_disclosure: string;
  non_guaranteed_disclosure: string;
  complexity_level: string;
  professional_only: boolean;
  education_only: boolean;
  enabled: boolean;
  is_simulated: boolean;
  terms: Record<string, unknown>;
  catalog_version: string;
  data_date: string;
  source: string;
}

export interface ProductCatalog {
  catalog_code: string;
  catalog_version: string;
  data_date: string;
  source_type: "mock";
  source_summary: string;
  product_count: number;
  products: MockProduct[];
  professional_hedge_lab_enabled: false;
}

export interface PortfolioResponse {
  meta: {
    household_id: string;
    household_code: string;
    analysis_date: string;
    data_as_of: string;
    input_version: string;
    formula_version: string;
    rule_code: string;
    rule_version: string;
    optimizer_version: string;
    catalog_version: string;
    calculation_source: "deterministic_tools";
    currency: string;
    synthetic_data: boolean;
    market_scenario: MarketScenario;
  };
  context: {
    current_growth_assets: string;
    eligible_long_term_amount: string;
    amount_to_restore_safety_layers: string;
    long_term_goal_present_value_gap: string;
    simulation_horizon_months: number;
    annual_new_surplus: string;
    counting_note: string;
  };
  family_safety_gate: SuitabilityGate;
  customer_suitability_gate: SuitabilityGate;
  candidates: PortfolioCandidate[];
  catalog: ProductCatalog;
  education_cards: Array<{ code: string; title: string; summary: string; points: string[] }>;
  professional_hedge_lab: {
    enabled: false;
    mode: "read_only_education";
    title: string;
    reason: string;
    prerequisites: string[];
  };
  counting_note: string;
}

export interface SuitabilityProbeRequest {
  analysis_date?: string;
  investment_amount: string;
  target_horizon_months: number;
  requested_high_risk_ratio: string;
  leverage_ratio?: string;
  concentration_ratio?: string;
  requested_product_codes: string[];
  purpose: "long_term_growth" | "tuition" | "home_purchase" | "retirement" | "professional_hedge";
}

export interface SuitabilityProbeResponse {
  household_id: string;
  decision: SuitabilityDecision;
  gates: SuitabilityGate[];
  failed_check_codes: string[];
  audit_event_id: string;
  rule_version: string;
  calculation_source: "deterministic_tools";
  explanation: string;
}

export interface PersistedPortfolioRun {
  recommendation_id: string;
  portfolio_plan_ids: string[];
  suitability_check_ids: string[];
  household_id: string;
  input_version: string;
  rule_version_id: string;
  rule_version: string;
  candidate_count: number;
  suitability_check_count: number;
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

export function fetchPortfolio(
  householdId: string,
  marketScenario: MarketScenario = "neutral",
  signal?: AbortSignal,
): Promise<PortfolioResponse> {
  const query = `?market_scenario=${encodeURIComponent(marketScenario)}`;
  return readJson(`/api/v1/households/${encodeURIComponent(householdId)}/portfolio${query}`, signal);
}

export function persistPortfolio(
  householdId: string,
  marketScenario: MarketScenario = "neutral",
): Promise<PersistedPortfolioRun> {
  const query = `?market_scenario=${encodeURIComponent(marketScenario)}`;
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/portfolio/runs${query}`,
    undefined,
    { method: "POST" },
  );
}

export function checkPortfolioSuitability(
  householdId: string,
  request: SuitabilityProbeRequest,
): Promise<SuitabilityProbeResponse> {
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/portfolio/suitability-check`,
    undefined,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export function portfolioExportUrl(
  householdId: string,
  marketScenario: MarketScenario = "neutral",
): string {
  return `${apiBase}/api/v1/households/${encodeURIComponent(householdId)}/portfolio/export?market_scenario=${encodeURIComponent(marketScenario)}`;
}
