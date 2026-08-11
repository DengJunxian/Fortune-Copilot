import { actorHeaders, demoActor } from "./actor";

export type EnterpriseDependencyLevel = "none" | "low" | "medium" | "high";

export interface EnterpriseRecordMeta {
  id: string;
  currency: string;
  valuation_date: string | null;
  data_source: string;
  is_user_confirmed: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  is_deleted: boolean;
  deleted_at: string | null;
}

export interface EnterpriseProfile extends EnterpriseRecordMeta {
  household_id: string;
  name: string;
  industry: string;
  stage: string;
  jurisdiction: string;
  listed_status: string;
  enterprise_type: string;
}

export interface EnterpriseValuation extends EnterpriseRecordMeta {
  household_id: string;
  enterprise_id: string;
  equity_value: string;
  valuation_method: string;
  confidence: string;
  source_kind: string;
  evidence: Record<string, unknown>;
}

export interface EnterpriseOwnership extends EnterpriseRecordMeta {
  household_id: string;
  enterprise_id: string;
  owner_entity_id: string;
  ownership_ratio: string;
  voting_ratio: string;
  instrument_type: string;
  vesting_date: string | null;
  lockup_end_date: string | null;
}

export interface EnterpriseCashflow extends EnterpriseRecordMeta {
  household_id: string;
  enterprise_id: string;
  member_id: string | null;
  cashflow_type: string;
  amount: string;
  frequency: string;
  stability: string;
}

export interface EnterpriseGuarantee extends EnterpriseRecordMeta {
  household_id: string;
  enterprise_id: string;
  member_id: string | null;
  guarantee_type: string;
  guaranteed_amount: string;
  outstanding_exposure: string;
  expiry_date: string | null;
}

export interface EnterpriseLiquidityEvent extends EnterpriseRecordMeta {
  household_id: string;
  enterprise_id: string;
  event_type: string;
  expected_date: string;
  estimated_value: string;
  probability: string;
  lockup: boolean;
  status: string;
}

export interface FamilyEnterpriseView {
  meta: {
    household_id: string;
    analysis_date: string;
    data_as_of: string | null;
    input_hash: string;
    rule_version: string;
    formula_version: string;
    calculation_source: "deterministic_tools";
  };
  enterprises: Array<{
    profile: EnterpriseProfile;
    latest_valuation: EnterpriseValuation | null;
    ownerships: EnterpriseOwnership[];
    cashflows: EnterpriseCashflow[];
    guarantees: EnterpriseGuarantee[];
    liquidity_events: EnterpriseLiquidityEvent[];
    household_owned_value: string;
  }>;
  wealth: {
    household_wealth: string;
    financial_assets: string;
    property_assets: string;
    enterprise_wealth: string;
    economic_household_wealth: string;
    enterprise_wealth_ratio: string;
  };
  income: {
    enterprise_annual_income: string;
    household_annual_income: string;
    dependency_ratio: string;
    low_stability_annual_income: string;
  };
  guarantees: {
    guaranteed_amount: string;
    outstanding_exposure: string;
    active_count: number;
  };
  dependency: {
    components: Array<{
      code: string;
      label: string;
      ratio: string;
      weighted_score: string;
      numerator: string;
      denominator: string;
      explanation: string;
    }>;
    score: string;
    level: EnterpriseDependencyLevel;
    label: string;
    regulatory_rating: false;
    disclaimer: string;
  };
  economic_capital: {
    unlisted_company_equity: string;
    listed_employer_stock: string;
    equity_incentives: string;
    liquid_securities_equity: string;
    enterprise_salary_and_dividend_dependency: string;
    guarantee_exposure: string;
    pledge_exposure: string;
    total_economic_equity_exposure: string;
    economic_equity_ratio: string;
    risk_budget_ceiling_ratio: string;
    risk_budget_ceiling_amount: string;
    remaining_incremental_equity_capacity: string;
    additional_equity_risk_allowed: boolean;
    explanation: string;
  };
  liquidity_events: EnterpriseLiquidityEvent[];
  cfs_implication: {
    status: "not_enabled" | "constraints_available";
    constraints: string[];
    explanation: string;
  };
}

export const familyEnterpriseFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_FAMILY_ENTERPRISE === "true";

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

export function fetchFamilyEnterpriseView(
  householdId: string,
  signal?: AbortSignal,
): Promise<FamilyEnterpriseView> {
  return request(
    `/api/v1/households/${encodeURIComponent(householdId)}/family-enterprise-view`,
    signal,
  );
}
