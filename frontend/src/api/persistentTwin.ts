import { actorHeaders, demoActor } from "./actor";

export type TwinRiskLevel = "low" | "medium_low" | "medium" | "medium_high" | "high";
export type TwinNeedStatus = "identified" | "partially_prepared" | "prepared" | "needs_review";

export interface TwinRiskBudget {
  risk_capacity: TwinRiskLevel | null;
  risk_willingness: TwinRiskLevel | null;
  behavior_limit: TwinRiskLevel | null;
  eligible_long_term_capital: string;
  formally_eligible: boolean;
  decision: "eligible" | "repair_first";
  enterprise_dependency_score?: string | null;
  enterprise_dependency_level?: string | null;
  economic_equity_exposure?: string;
  remaining_incremental_equity_capacity?: string;
  additional_equity_risk_allowed?: boolean;
  enterprise_constraints?: string[];
}

export interface TwinState {
  facts: {
    household_code: string;
    household_name: string;
    members: Array<{ id: string; display_name: string; relationship: string }>;
    incomes: Array<{
      id: string;
      member_id: string | null;
      name: string;
      annual_amount: string;
    }>;
    annual_income: string;
    annual_expenses: string;
    total_assets: string;
    total_liabilities: string;
    net_worth: string;
  };
  profile: {
    profile_version: number | null;
    lifecycle_stage: string | null;
    wealth_tier: string | null;
    service_complexity: string | null;
    risk_capacity: TwinRiskLevel | null;
    risk_willingness: TwinRiskLevel | null;
    behavior_limit: TwinRiskLevel | null;
    status: string;
  };
  needs: Array<{
    id: string;
    need_type: string;
    priority: number;
    status: TwinNeedStatus;
    target_amount: string;
    minimum_amount: string;
  }>;
  liability: {
    stream_count: number;
    cashflow_count: number;
    target_total: string;
    prepared_total: string;
    funding_gap: string;
    next_due_date: string | null;
  };
  risk_budget: TwinRiskBudget;
  cfs: { status: "not_enabled" | "available"; score: string | null; explanation: string };
  monitoring: { status: "not_enabled" | "evaluated"; alerts: string[] };
}

export interface HouseholdSnapshot {
  id: string;
  household_id: string;
  parent_snapshot_id: string | null;
  snapshot_date: string;
  event_cursor: number;
  financial_graph_version: string;
  profile_version: number | null;
  need_version: string;
  liability_version: string;
  input_hash: string;
  snapshot_hash: string;
  status: "active" | "superseded";
  created_at: string;
  state: TwinState;
}

export interface SnapshotComparison {
  from_snapshot_id: string | null;
  to_snapshot_id: string;
  changed_facts: Array<{
    code: string;
    label: string;
    before: string | null;
    after: string | null;
    direction: "increased" | "decreased" | "changed" | "added" | "removed";
  }>;
  changed_needs: Array<{
    need_type: string;
    change_type: "added" | "removed" | "changed";
    before_status: TwinNeedStatus | null;
    after_status: TwinNeedStatus | null;
    before_target_amount: string | null;
    after_target_amount: string | null;
  }>;
  changed_profile: {
    changed: boolean;
    before_version: number | null;
    after_version: number | null;
    changed_fields: string[];
  };
  changed_risk_budget: {
    changed: boolean;
    before: TwinRiskBudget | null;
    after: TwinRiskBudget;
  };
  changed_cfs: {
    changed: boolean;
    before: TwinState["cfs"] | null;
    after: TwinState["cfs"];
  };
  has_material_change: boolean;
}

export interface WealthTwinResponse {
  meta: {
    household_id: string;
    analysis_date: string;
    snapshot_count: number;
    event_count: number;
    calculation_source: "deterministic_tools";
  };
  current: HouseholdSnapshot;
  previous: {
    id: string;
    snapshot_date: string;
    event_cursor: number;
    snapshot_hash: string;
  } | null;
  comparison: SnapshotComparison;
}

export interface FinancialEvent {
  id: string;
  household_id: string;
  event_domain: "life" | "enterprise";
  event_type: string;
  effective_at: string;
  recorded_at: string;
  source_kind: string;
  source_reference: string;
  confirmation_status: "confirmed" | "applied" | "processed" | "failed";
  payload: Record<string, unknown>;
  event_hash: string;
  processed_snapshot_id: string | null;
  life_event: {
    id: string;
    member_id: string | null;
    life_event_type: "salary_change";
    event_date: string;
    expected_financial_impact: string;
    metadata_json: Record<string, unknown>;
  } | null;
}

export interface EventTimelineResponse {
  household_id: string;
  events: FinancialEvent[];
  total: number;
}

export interface LifeEventResponse {
  event: FinancialEvent;
  snapshot: HouseholdSnapshot;
  comparison: SnapshotComparison;
  idempotent_replay: boolean;
}

export interface SalaryChangeInput {
  event_date: string;
  member_id?: string | null;
  income_change_ratio: string;
  source_reference?: string;
}

export const persistentTwinFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_PERSISTENT_TWIN === "true";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

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
      error?: { message?: string };
    } | null;
    throw new Error(payload?.error?.message ?? `请求失败（${response.status}）`);
  }
  return await response.json() as T;
}

function householdPath(householdId: string): string {
  return `/api/v1/households/${encodeURIComponent(householdId)}`;
}

export function fetchWealthTwin(
  householdId: string,
  signal?: AbortSignal,
): Promise<WealthTwinResponse> {
  return request(`${householdPath(householdId)}/wealth-twin`, { signal });
}

export function fetchEventTimeline(
  householdId: string,
  signal?: AbortSignal,
): Promise<EventTimelineResponse> {
  return request(`${householdPath(householdId)}/event-timeline`, { signal });
}

export function createSalaryChange(
  householdId: string,
  input: SalaryChangeInput,
  signal?: AbortSignal,
): Promise<LifeEventResponse> {
  return request(`${householdPath(householdId)}/life-events`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      "X-Confirm-Action": "create_life_event",
    },
    body: JSON.stringify({
      life_event_type: "salary_change",
      event_date: input.event_date,
      member_id: input.member_id ?? null,
      income_source_ids: [],
      income_change_ratio: input.income_change_ratio,
      source_reference: input.source_reference ?? "client-confirmed-life-event",
      metadata_json: { entry_point: "wealth_twin" },
      is_user_confirmed: true,
    }),
  });
}
