import { actorHeaders, demoActor } from "./actor";

export type RiskLevel = "low" | "medium_low" | "medium" | "medium_high" | "high";
export type ComplexityBand = "none" | "low" | "medium" | "high";
export type WealthNeedStatus =
  | "identified"
  | "partially_prepared"
  | "prepared"
  | "needs_review";

export interface ProfileDataGap {
  code: string;
  label: string;
  detail: string;
  action: string;
}

export interface ClientWealthProfile {
  id: string;
  household_id: string;
  profile_version: number;
  lifecycle_stage: string;
  wealth_tier: string;
  service_complexity: string;
  risk_capacity: RiskLevel;
  risk_willingness: RiskLevel;
  behavior_limit: RiskLevel;
  enterprise_dependency_level: ComplexityBand;
  cross_border_complexity: ComplexityBand;
  succession_complexity: ComplexityBand;
  pension_stage: string;
  completeness_score: string;
  data_gaps: ProfileDataGap[];
  profile_hash: string;
  status: "active" | "superseded" | "needs_review";
  explanation: Record<string, string>;
  currency: string;
  valuation_date: string | null;
}

export interface ClientProfileResponse {
  meta: {
    household_id: string;
    analysis_date: string;
    data_as_of: string | null;
    input_version: number;
    source_snapshot_id: string;
    rule_version: string;
    formula_version: string;
    calculation_source: "deterministic_tools";
    synthetic_data: boolean;
  };
  profile: ClientWealthProfile;
  tags: Array<{
    id: string;
    tag_code: string;
    tag_category: string;
    confidence: string;
    severity: "info" | "watch" | "high";
  }>;
}

export interface WealthNeed {
  id: string;
  need_type: string;
  target_amount: string;
  minimum_amount: string;
  currency: string;
  start_date: string;
  end_date: string | null;
  rigidity: "rigid" | "important" | "flexible";
  priority: number;
  status: WealthNeedStatus;
  confidence: string;
  professional_review_required: boolean;
  source_kind: string;
}

export interface WealthNeedPriority {
  wealth_need_id: string;
  priority_rank: number;
  hard_constraint: boolean;
  priority_score: string;
  reason: string;
  rule_version: string;
}

export interface WealthNeedsResponse {
  meta: {
    household_id: string;
    profile_id: string;
    profile_hash: string;
    analysis_date: string;
    data_as_of: string | null;
    rule_version: string;
    formula_version: string;
    calculation_source: "deterministic_tools";
    professional_review_count: number;
  };
  needs: WealthNeed[];
  priorities: WealthNeedPriority[];
}

export const clientProfileFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_CLIENT_PROFILE === "true";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

export class ClientProfileApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
  ) {
    super(message);
    this.name = "ClientProfileApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...actorHeaders(clientActor),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {
      error?: { code?: string; message?: string };
    } | null;
    throw new ClientProfileApiError(
      payload?.error?.message ?? `请求失败（${response.status}）`,
      response.status,
      payload?.error?.code ?? null,
    );
  }
  return await response.json() as T;
}

function householdPath(householdId: string): string {
  return `/api/v1/households/${encodeURIComponent(householdId)}`;
}

export function fetchClientProfile(
  householdId: string,
  signal?: AbortSignal,
): Promise<ClientProfileResponse> {
  return request<ClientProfileResponse>(`${householdPath(householdId)}/client-profile`, {
    signal,
  });
}

export function recalculateClientProfile(
  householdId: string,
  signal?: AbortSignal,
): Promise<ClientProfileResponse> {
  return request<ClientProfileResponse>(
    `${householdPath(householdId)}/client-profile/recalculate`,
    { method: "POST", signal },
  );
}

export function fetchWealthNeeds(
  householdId: string,
  signal?: AbortSignal,
): Promise<WealthNeedsResponse> {
  return request<WealthNeedsResponse>(`${householdPath(householdId)}/wealth-needs`, {
    signal,
  });
}

export function recalculateWealthNeeds(
  householdId: string,
  signal?: AbortSignal,
): Promise<WealthNeedsResponse> {
  return request<WealthNeedsResponse>(
    `${householdPath(householdId)}/wealth-needs/recalculate`,
    { method: "POST", signal },
  );
}
