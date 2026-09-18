import { actorHeaders, demoActor } from "./actor";
import type { ProfessionalSpecialistType } from "./cfs";

export type SpecializedComplexity = "none" | "low" | "medium" | "high";

export interface SpecializedMeta {
  household_id: string;
  analysis_date: string;
  data_as_of: string | null;
  input_hash: string;
  rule_version: string;
  formula_version: string;
  calculation_source: "deterministic_tools";
}

export interface ProfessionalRoute {
  need: string;
  complexity: SpecializedComplexity;
  complexity_gate_passed: boolean;
  specialist_type: ProfessionalSpecialistType | null;
  referral_id: string | null;
  referral_status: "open" | "accepted" | "completed" | "cancelled" | null;
  advisor_workflow_status:
    | "not_required"
    | "cfs_required"
    | "referral_open"
    | "in_progress"
    | "completed";
  reason: string;
  boundary: string;
}

export interface InstitutionalEntitlement {
  id: string;
  member_id: string | null;
  entitlement_type:
    | "social_security"
    | "enterprise_pension"
    | "occupational_pension"
    | "personal_pension"
    | "annuity"
    | "rental"
    | "financial_withdrawal";
  balance: string;
  expected_income: string;
  start_age: number | null;
  start_date: string | null;
  end_date: string | null;
  guaranteed: boolean;
  indexed: boolean;
  lock_up: boolean;
  source_kind: string;
  confidence: string;
  evidence: Record<string, unknown>;
}

export interface RetirementPlanResponse {
  meta: SpecializedMeta;
  has_retirement_need: boolean;
  liabilities: {
    basic_retirement_liability: string;
    medical_liability: string;
    long_term_care_liability: string;
    improved_retirement_goal: string;
    retirement_start_date: string | null;
    retirement_years: number;
  };
  entitlements: InstitutionalEntitlement[];
  output: {
    retirement_floor: string;
    guaranteed_income: string;
    income_gap: string;
    longevity_gap: string;
    liquidity_gap: string;
  };
  route: ProfessionalRoute;
  assumptions: string[];
  boundary: string;
}

export interface CurrencyExposure {
  id: string;
  entity_id: string | null;
  exposure_type:
    | "asset_currency"
    | "income_currency"
    | "liability_currency"
    | "education_liability"
    | "enterprise_revenue"
    | "future_obligation";
  currency: string;
  amount: string;
  direction: "inflow" | "outflow";
  horizon: "current" | "short_term" | "medium_term" | "long_term";
  source_record_ids: string[];
}

export interface CurrencyExposureResponse {
  meta: SpecializedMeta;
  base_currency: string;
  material_exposure_detected: boolean;
  exposures: CurrencyExposure[];
  summaries: Array<{
    currency: string;
    inflow: string;
    outflow: string;
    net_exposure: string;
    source_count: number;
  }>;
  route: ProfessionalRoute;
  detection_notes: string[];
  boundary: string;
}

export interface TrustSuccessionNeed {
  id: string;
  need_type:
    | "minor_beneficiary"
    | "special_care"
    | "multi_generation"
    | "enterprise_succession"
    | "ownership_complexity"
    | "insurance_trust_coordination";
  beneficiaries: Array<Record<string, unknown>>;
  assets_in_scope: Array<Record<string, unknown>>;
  enterprise_in_scope: string[];
  urgency: "low" | "medium" | "high" | "urgent";
  complexity: SpecializedComplexity;
  professional_review_required: boolean;
  evidence: Record<string, unknown>;
}

export interface TrustSuccessionResponse {
  meta: SpecializedMeta;
  need_detected: boolean;
  outcome: "NO_NEED_DETECTED" | "NEED_DETECTED" | "EXPERT_REVIEW_REQUIRED";
  needs: TrustSuccessionNeed[];
  routes: ProfessionalRoute[];
  boundary: string;
}

export interface PhilanthropyGoal {
  id: string;
  annual_budget: string;
  target_cause: string;
  funding_asset: string | null;
  time_horizon: "immediate" | "short_term" | "medium_term" | "long_term" | "ongoing";
  family_participation: string;
  governance_preference: string;
  professional_review_required: boolean;
}

export interface PhilanthropyGoalsResponse {
  meta: SpecializedMeta;
  has_explicit_goal: boolean;
  goals: PhilanthropyGoal[];
  route: ProfessionalRoute;
  boundary: string;
}

export interface FamilySpecializedResponse {
  trust: TrustSuccessionResponse;
  philanthropy: PhilanthropyGoalsResponse;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiBase + path, {
    signal,
    headers: { Accept: "application/json", ...actorHeaders(clientActor) },
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

export function fetchRetirementPlan(
  householdId: string,
  signal?: AbortSignal,
): Promise<RetirementPlanResponse> {
  return request(`${householdPath(householdId)}/retirement-plan`, signal);
}

export function fetchCurrencyExposures(
  householdId: string,
  signal?: AbortSignal,
): Promise<CurrencyExposureResponse> {
  return request(`${householdPath(householdId)}/currency-exposures`, signal);
}

export async function fetchFamilySpecializedNeeds(
  householdId: string,
  signal?: AbortSignal,
): Promise<FamilySpecializedResponse> {
  const [trust, philanthropy] = await Promise.all([
    request<TrustSuccessionResponse>(
      `${householdPath(householdId)}/trust-succession-needs`,
      signal,
    ),
    request<PhilanthropyGoalsResponse>(
      `${householdPath(householdId)}/philanthropy-goals`,
      signal,
    ),
  ]);
  return { trust, philanthropy };
}
