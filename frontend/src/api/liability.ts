import { actorHeaders, demoActor } from "./actor";

export type LiabilityStreamType =
  | "education"
  | "housing"
  | "retirement"
  | "medical"
  | "family_support"
  | "debt_service"
  | "protection"
  | "living"
  | "succession"
  | "philanthropy"
  | "other";

export interface LiabilityStream {
  id: string;
  household_id: string;
  wealth_need_id: string | null;
  source_goal_id: string | null;
  source_responsibility_id: string | null;
  beneficiary_entity_id: string | null;
  name: string;
  stream_type: LiabilityStreamType;
  currency: string;
  start_date: string;
  end_date: string | null;
  frequency: "monthly" | "quarterly" | "annual" | "one_time" | "irregular";
  base_amount: string;
  minimum_amount: string;
  inflation_index_code: string;
  annual_growth_assumption: string;
  rigidity: "rigid" | "important" | "flexible";
  deferrable: boolean;
  funding_sources: Array<Record<string, unknown>>;
  fallback_action: string;
  stream_version: string;
  version: number;
}

export interface LiabilityCashflow {
  id: string;
  liability_stream_id: string;
  due_date: string;
  target_amount: string;
  minimum_amount: string;
  sequence: number;
  calculation_version: string;
}

export interface LiabilityCalendarEntry {
  stream: LiabilityStream;
  cashflows: LiabilityCashflow[];
  target_total: string;
  minimum_total: string;
  prepared_amount: string;
  funding_gap: string;
}

export interface LiabilityCalendarResponse {
  meta: {
    household_id: string;
    analysis_date: string;
    data_as_of: string | null;
    rule_version: string;
    formula_version: string;
    calculation_source: "deterministic_tools";
    adapter_sources: string[];
  };
  summary: {
    stream_count: number;
    cashflow_count: number;
    target_total: string;
    minimum_total: string;
    prepared_total: string;
    funding_gap: string;
    next_due_date: string | null;
  };
  entries: LiabilityCalendarEntry[];
}

export interface EligibleCapitalBridgeStep {
  code: string;
  label: string;
  before: string;
  requested_deduction: string;
  deduction: string;
  after: string;
  unfunded: string;
  source: string;
  reason: string;
}

export type CalibrationMode =
  | "controlled_demo"
  | "empirically_calibrated"
  | "bank_authorized";

export type CalibrationStatus = "available" | "degraded" | "needs_review";

export interface CalibrationParameterReference {
  parameter_id: string;
  code: string;
  value: string | null;
  lower_bound: string | null;
  upper_bound: string | null;
  segment: string;
  region: string;
  mode: CalibrationMode | null;
  status: CalibrationStatus;
  source: string;
  source_reference: string;
  version: string;
  method: string;
  confidence: string;
  limitations: string[];
  effective_from: string | null;
  effective_to: string | null;
  dataset_code: string | null;
  reason: string;
}

interface CalibrationTrace {
  calibration_status: CalibrationStatus;
  calibration_modes: CalibrationMode[];
  parameter_references: CalibrationParameterReference[];
}

export interface EligibleCapitalResponse {
  meta: {
    household_id: string;
    analysis_date: string;
    data_as_of: string | null;
    input_hash: string;
    rule_version: string;
    formula_version: string;
    calibration_version: string;
    calculation_source: "deterministic_tools";
  };
  calculation: {
    dispatchable_financial_resources: string;
    bridge: EligibleCapitalBridgeStep[];
    eligible_long_term_capital: string;
    eligibility_gates: Array<{
      code: string;
      label: string;
      passed: boolean;
      reason: string;
    }>;
    formally_eligible: boolean;
    decision: "eligible" | "repair_first";
    growth_entry_threshold: {
      amount: string;
      currency: string;
      source: string;
      deprecated_as_hard_gate: true;
      determines_eligibility: false;
      communication_note: string;
    };
    purchasing_power: {
      formula_version: string;
      calibration_registry_version: string;
      calibration_status: CalibrationStatus;
      calibration_modes: CalibrationMode[];
      parameter_references: CalibrationParameterReference[];
      requires_human_review: boolean;
      household_cost_inflation: CalibrationTrace & {
        code: "HCI";
        annual_rate: string;
        interpretation: string;
      };
      goal_cost_inflation: Array<CalibrationTrace & {
        code: "GCI";
        stream_id: string;
        stream_name: string;
        stream_type: LiabilityStreamType;
        inflation_index_code: string;
        annual_rate: string;
        interpretation: string;
      }>;
      income_adequacy: CalibrationTrace & {
        code: "IAI";
        sustainable_annual_income: string;
        essential_annual_cost: string;
        ratio: string;
        status: "critical" | "watch" | "adequate" | "comfortable";
        minimum_wage_trend: string;
        minimum_wage_scope: "income_adequacy_only";
        minimum_wage_used_as_portfolio_hurdle: false;
        interpretation: string;
      };
      minimum_wage_used_as_cpi_proxy: false;
      minimum_wage_used_as_return_hurdle: false;
    };
  };
}

export const liabilityFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_LIABILITY_ENGINE === "true";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiBase + path, {
    signal,
    headers: {
      Accept: "application/json",
      ...actorHeaders(clientActor),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {
      error?: { message?: string };
    } | null;
    throw new Error(payload?.error?.message ?? `请求失败（${response.status}）`);
  }
  return await response.json() as T;
}

function householdPath(householdId: string): string {
  return `/api/v1/households/${encodeURIComponent(householdId)}`;
}

export function fetchLiabilityCalendar(
  householdId: string,
  signal?: AbortSignal,
): Promise<LiabilityCalendarResponse> {
  return request(`${householdPath(householdId)}/liability-calendar`, signal);
}

export function fetchEligibleCapital(
  householdId: string,
  signal?: AbortSignal,
): Promise<EligibleCapitalResponse> {
  return request(`${householdPath(householdId)}/eligible-capital`, signal);
}
