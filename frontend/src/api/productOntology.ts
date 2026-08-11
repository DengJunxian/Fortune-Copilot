import { actorHeaders, demoActor } from "./actor";
import type { CFSComponentType } from "./cfs";

export type ProductEligibilityDecision =
  | "eligible"
  | "restricted"
  | "blocked"
  | "education_only"
  | "professional_review";

export interface OntologyProduct {
  id: string;
  code: string;
  name: string;
  issuer: string;
  jurisdiction: string;
  currency: string;
  product_family: string;
  product_subtype: string;
  asset_class: string;
  risk_level: string;
  liquidity_level: string;
  minimum_investment: string;
  minimum_holding_months: number;
  redemption_rules: string;
  all_in_cost: string | null;
  distribution_incentive_disclosure: string;
  conflict_of_interest_flag: boolean;
  professional_review_required: boolean;
  client_role_in_cfs: string[];
  account_wrappers: string[];
  complexity_level: string;
  principal_loss_possible: boolean;
  legally_principal_guaranteed: boolean;
  enabled: boolean;
  classification_version: string;
  evidence_json: Record<string, unknown>;
}

export interface ProductSnapshot {
  id: string;
  product_id: string;
  as_of_date: string;
  sale_status: string;
  risk_level: string;
  fee_snapshot: Record<string, unknown>;
  liquidity_snapshot: {
    minimum_holding_days?: number;
    normal_redemption_note?: string;
    lock_up?: boolean;
  };
  terms_snapshot: Record<string, unknown>;
  channel: string;
  source_reference: string;
  evidence: Array<Record<string, unknown>>;
  snapshot_hash: string;
  snapshot_version: string;
}

export interface RankedProductCandidate {
  rank: number;
  product: OntologyProduct;
  snapshot: ProductSnapshot;
  eligibility: {
    decision: ProductEligibilityDecision;
    eligible: boolean;
    executable: boolean;
    reasons: string[];
    restrictions: string[];
    freshness: {
      as_of_date: string;
      age_days: number;
      maximum_age_days: number;
      stale: boolean;
      sale_status: string;
      executable: boolean;
    };
  };
  score: string;
  why_selected: string[];
  why_not_other_candidates: string[];
}

export interface CFSProductCandidateGroup {
  component_id: string;
  component_type: CFSComponentType;
  purpose: string;
  result: "ranked" | "no_product";
  candidates: RankedProductCandidate[];
  no_product_reason: string | null;
}

export interface CFSProductCompositionResponse {
  household_id: string;
  solution_id: string;
  analysis_date: string;
  catalog_as_of: string;
  catalog_stale: boolean;
  executable_recommendation_allowed: boolean;
  groups: CFSProductCandidateGroup[];
  execution_boundary: string;
}

export const productOntologyFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_PRODUCT_ONTOLOGY === "true";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

export async function fetchCFSProductCandidates(
  householdId: string,
  solutionId: string,
  analysisDate: string,
  signal?: AbortSignal,
): Promise<CFSProductCompositionResponse> {
  const path = `/api/v1/households/${encodeURIComponent(householdId)}`
    + `/cfs-solutions/${encodeURIComponent(solutionId)}/product-candidates`
    + `?analysis_date=${encodeURIComponent(analysisDate)}`;
  const response = await fetch(apiBase + path, {
    signal,
    headers: { Accept: "application/json", ...actorHeaders(clientActor) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {
      error?: { message?: string };
    } | null;
    throw new Error(payload?.error?.message ?? `候选产品请求失败（${response.status}）`);
  }
  return await response.json() as CFSProductCompositionResponse;
}
