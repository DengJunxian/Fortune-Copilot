export interface HouseholdSummary {
  id: string;
  code: string;
  name: string;
  lifecycle_stage: string;
  region: string;
  is_synthetic: boolean;
}

interface PageResponse<T> {
  items: T[];
  pagination: { page: number; page_size: number; total: number; pages: number };
}

export interface AnalysisMeta {
  household_id: string;
  household_code: string;
  analysis_date: string;
  data_as_of: string;
  input_version: string;
  formula_version: string;
  rule_code: string;
  rule_version: string;
  calculation_source: "deterministic_tools";
  currency: string;
  synthetic_data: boolean;
}

export interface MemberSummary {
  id: string;
  display_name: string;
  relationship: string;
  age: number;
  occupation: string | null;
  employment_stability: string;
  health_risk_level: string;
}

export interface MetricInput {
  key: string;
  label: string;
  value: string;
  unit: string;
  source_record_ids: string[];
}

export type MetricStatus =
  | "strong"
  | "healthy"
  | "attention"
  | "warning"
  | "critical"
  | "review"
  | "not_applicable";

export interface MetricResult {
  metric_id: string;
  name: string;
  formula: string;
  substitution: string;
  inputs: MetricInput[];
  result: string | null;
  numerator: string | null;
  denominator: string | null;
  unit: string;
  threshold_version: string;
  status: MetricStatus;
  explanation_key: string;
  data_as_of: string;
  source_type: "deterministic_derived";
  applicability: { applicable: boolean; reason: string };
  reference: {
    reference_range: string;
    source_type: "official_rule" | "industry_reference" | "internal_demo";
    source_reference: string;
    parameters: Record<string, string>;
  };
  explanation: string;
  actions: string[];
}

export interface AssetLine {
  id: string;
  name: string;
  category: string;
  subcategory: string | null;
  asset_group: string;
  market_value: string;
  acquisition_cost: string;
  unrealized_change: string;
  liquidity_days: number;
  liquidity_level: string;
  property_use: string;
  pledged: boolean;
  valuation_date: string | null;
}

export interface LiabilityLine {
  id: string;
  name: string;
  category: string;
  outstanding_balance: string;
  annual_interest_rate: string;
  monthly_payment: string;
  scheduled_twelve_month_payment: string;
  maturity_date: string | null;
  rate_type: string;
  linked_asset_id: string | null;
  is_high_interest: boolean;
}

export interface CashFlowLine {
  id: string;
  name: string;
  category: string;
  frequency: string;
  original_amount: string;
  annual_amount: string;
  essential: boolean;
  compressible_amount: string;
}

export interface InsuranceLine {
  id: string;
  name: string;
  policy_type: string;
  insured_member_id: string;
  insured_member_name: string;
  coverage_amount: string;
  annual_premium: string;
  deductible: string;
  waiting_period_days: number;
  start_date: string;
  end_date: string | null;
  guaranteed_benefit: string;
  non_guaranteed_benefit: string;
  cash_value: string;
  active_on_analysis_date: boolean;
}

export interface GoalLine {
  id: string;
  name: string;
  goal_type: string;
  target_amount: string;
  target_date: string;
  years_remaining: string;
  rigidity: string;
  priority: number;
  can_defer: boolean;
  minimum_acceptable_amount: string;
  prepared_amount: string;
  funding_gap: string;
  funding_ratio: string | null;
  annual_cost_growth_rate: string;
}

export interface LiquidityLine {
  asset_id: string;
  name: string;
  category: string;
  market_value: string;
  liquidity_days: number;
  liquidity_level: string;
  liquidity_tier: string;
  included_in_emergency_reserve: boolean;
  included_in_short_term_coverage: boolean;
}

export interface FinancialStatements {
  balance_sheet: {
    assets: AssetLine[];
    liabilities: LiabilityLine[];
    asset_totals_by_group: Record<string, string>;
    liability_totals_by_category: Record<string, string>;
    total_assets: string;
    total_liabilities: string;
    net_worth: string;
    accounting_identity: string;
  };
  cash_flow: {
    income_lines: CashFlowLine[];
    expense_lines: CashFlowLine[];
    income_totals_by_type: Record<string, string>;
    expense_totals_by_category: Record<string, string>;
    annual_income: string;
    annual_expenses: string;
    annual_surplus: string;
    annual_basic_living_expenses: string;
    annual_essential_expenses: string;
    annual_fixed_expenses: string;
    annual_debt_service: string;
    annual_insurance_premiums: string;
  };
  insurance: {
    policies: InsuranceLine[];
    coverage_by_policy_type: Record<string, string>;
    total_annual_premium: string;
    total_cash_value: string;
    counting_note: string;
  };
  goal_funding: {
    goals: GoalLine[];
    total_target_amount: string;
    total_prepared_amount: string;
    total_funding_gap: string;
  };
  liquidity: {
    lines: LiquidityLine[];
    totals_by_tier: Record<string, string>;
    emergency_liquid_assets: string;
    short_term_liquid_assets: string;
    twelve_month_liquid_assets: string;
  };
}

export interface DiagnosticIssue {
  code: string;
  severity: "info" | "attention" | "warning" | "critical";
  title: string;
  detail: string;
  related_record_ids: string[];
  action: string;
}

export interface HealthDimension {
  code: string;
  name: string;
  score: string;
  metric_ids: string[];
  explanation: string;
  is_regulatory_rating: false;
}

export interface FinancialAnalysis {
  meta: AnalysisMeta;
  profile: {
    name: string;
    lifecycle_stage: string;
    region: string;
    members: MemberSummary[];
    data_source: string;
    is_user_confirmed: boolean;
  };
  statements: FinancialStatements;
  metrics: MetricResult[];
  diagnostics: {
    completeness_score: string;
    passed_checks: number;
    issue_count: number;
    issues: DiagnosticIssue[];
  };
  protection: {
    risks: Array<{
      risk_code: string;
      name: string;
      required_amount: string;
      existing_coverage: string;
      coverage_ratio: string | null;
      gap: string;
      priority: number;
      basis: string;
    }>;
    most_significant_risk: string;
    coverage_ratio: string | null;
    protection_gap: string;
    annual_premium: string;
    premium_to_income_ratio: string | null;
    payment_pressure: string;
    counting_note: string;
  };
  purchasing_power: {
    official_cpi: PurchasingPowerFactor;
    family_weighted_inflation: PurchasingPowerFactor;
    goal_specific_cost_growth: Array<{
      goal_id: string;
      goal_name: string;
      goal_type: string;
      annual_cost_growth_rate: string;
      target_date: string;
    }>;
    minimum_wage_catch_up: PurchasingPowerFactor;
    minimum_wage_is_cpi: false;
    minimum_wage_is_return_guarantee: false;
  };
  health_dimensions: HealthDimension[];
}

interface PurchasingPowerFactor {
  code: string;
  name: string;
  rate: string;
  source_type: "official_rule" | "industry_reference" | "internal_demo";
  source_reference: string;
  data_as_of: string;
  note: string;
}

export interface PersistedRun {
  snapshot_id: string;
  household_id: string;
  input_version: string;
  rule_version_id: string;
  rule_version: string;
  metric_count: number;
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

export async function fetchHouseholds(signal?: AbortSignal): Promise<HouseholdSummary[]> {
  const page = await readJson<PageResponse<HouseholdSummary>>(
    "/api/v1/households?page=1&page_size=100",
    signal,
  );
  return page.items;
}

export function fetchFinancialAnalysis(
  householdId: string,
  signal?: AbortSignal,
): Promise<FinancialAnalysis> {
  return readJson<FinancialAnalysis>(
    `/api/v1/households/${encodeURIComponent(householdId)}/financial-analysis`,
    signal,
  );
}

export function persistFinancialAnalysis(householdId: string): Promise<PersistedRun> {
  return readJson<PersistedRun>(
    `/api/v1/households/${encodeURIComponent(householdId)}/financial-analysis/runs`,
    undefined,
    { method: "POST" },
  );
}

export function financialAnalysisExportUrl(householdId: string): string {
  return (
    apiBase +
    `/api/v1/households/${encodeURIComponent(householdId)}/financial-analysis/export`
  );
}
