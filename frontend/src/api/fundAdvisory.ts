export type AdvisorySleeveCode =
  | "daily_liquidity"
  | "stable_capital"
  | "personal_pension"
  | "long_term_growth";

export type AdvisorySleeveStatus =
  | "recommended"
  | "education_only"
  | "not_applicable"
  | "channel_verification_required";

export interface FundEvidence {
  evidence_id: string;
  title: string;
  issuer: string;
  url: string;
  published_or_as_of: string | null;
  verified_on: string;
  supports: string[];
  note: string;
}

export interface VerifiedFundProduct {
  code: string;
  name: string;
  short_name: string;
  manager: string;
  share_class: string;
  category: string;
  trade_venue: "off_exchange" | "exchange";
  tracked_index: string | null;
  broad_index: boolean;
  sector_or_thematic: false;
  leveraged: false;
  inverse: false;
  qdii: boolean;
  internal_risk_level: "r1" | "r2" | "r3" | "r4" | "r5";
  minimum_holding_days: number;
  normal_redemption_note: string;
  eligible_sleeves: AdvisorySleeveCode[];
  personal_pension_eligible: boolean;
  icbc_publicly_listed: boolean;
  icbc_channel_status:
    | "official_public_listing_app_confirmation_required"
    | "not_verified";
  icbc_channel_note: string;
  principal_guaranteed: false;
  selection_priority: number;
  evidence: FundEvidence[];
}

export interface VerifiedFundCatalog {
  catalog_code: string;
  catalog_version: string;
  data_date: string;
  verified_on: string;
  source_type: "verified_real_public_funds";
  catalog_stale: boolean;
  scope: string;
  mandatory_channel_notice: string;
  personal_pension_catalog_observation: string;
  product_count: number;
  products: VerifiedFundProduct[];
}

export interface AdvisoryAllocation {
  allocation_type: "bank_cash_reserve" | "fund" | "unallocated_guardrail";
  ratio: string;
  amount: string;
  product_code: string | null;
  product_name: string | null;
  product_risk_level: "r1" | "r2" | "r3" | "r4" | "r5" | null;
  icbc_publicly_listed: boolean | null;
  purchase_route: string;
  reasons: string[];
  warnings: string[];
  evidence_urls: string[];
}

export interface AdvisoryCandidate {
  product_code: string;
  product_name: string;
  role: string;
  status: "eligible" | "channel_verification_required";
  reason: string;
}

export interface AdvisorySleeve {
  sleeve_code: AdvisorySleeveCode;
  name: string;
  source_amount: string;
  status: AdvisorySleeveStatus;
  objective: string;
  allocations: AdvisoryAllocation[];
  candidate_products: AdvisoryCandidate[];
  guardrails: string[];
  explanation: string;
}

export interface FundAdvisoryResponse {
  meta: {
    household_id: string;
    household_code: string;
    analysis_date: string;
    data_as_of: string;
    input_version: string;
    engine_version: string;
    catalog_version: string;
    catalog_data_date: string;
    catalog_stale: boolean;
    icbc_only: boolean;
    calculation_source: "deterministic_tools";
    currency: string;
    synthetic_data: boolean;
  };
  effective_customer_risk: "low" | "medium_low" | "medium" | "medium_high" | "high";
  family_safety_status: "pass" | "restrict" | "block";
  sleeves: AdvisorySleeve[];
  catalog: VerifiedFundCatalog;
  hard_boundaries: string[];
  execution_checklist: string[];
  disclaimer: string;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function readJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiBase + path, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return (await response.json()) as T;
}

export function fetchFundAdvisory(
  householdId: string,
  icbcOnly = true,
  signal?: AbortSignal,
): Promise<FundAdvisoryResponse> {
  const query = `?icbc_only=${icbcOnly ? "true" : "false"}`;
  return readJson(
    `/api/v1/households/${encodeURIComponent(householdId)}/fund-advisory${query}`,
    signal,
  );
}
