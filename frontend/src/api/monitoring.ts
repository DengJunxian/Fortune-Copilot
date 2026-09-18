import { actorHeaders, demoActor } from "./actor";

export type MonitoringSeverity = "info" | "watch" | "high" | "critical";

export interface MonitoringAlert {
  id: string;
  household_id: string;
  monitoring_policy_id: string;
  financial_event_id: string | null;
  policy_type: string;
  trigger_reason: string;
  client_impact: string;
  severity: MonitoringSeverity;
  recommended_action: string;
  do_not_sell_flag: boolean;
  required_specialist: string | null;
  evidence_snapshot: Record<string, unknown>;
  status: "open" | "acknowledged" | "resolved" | "dismissed";
  detected_at: string;
  resolved_at: string | null;
}

export interface MonitoringAlertsResponse {
  household_id: string;
  rule_version: string;
  alerts: MonitoringAlert[];
}

export interface NextBestAction {
  action_code: string;
  household_id: string;
  priority: number;
  trigger_reason: string;
  client_impact: string;
  recommended_action: string;
  do_not_sell_flag: boolean;
  required_specialist: string | null;
  evidence: Record<string, unknown>;
  due_date: string | null;
}

export interface NextBestActionsResponse {
  household_id: string;
  outcome: "ACTIONS_AVAILABLE" | "NO_ACTION_REQUIRED";
  actions: NextBestAction[];
  boundary: string;
}

export interface AdvisorActionCenterItem {
  trigger_id: string;
  household_id: string;
  household_code: string;
  household_name: string;
  trigger_type: string;
  urgency: MonitoringSeverity;
  reason: string;
  required_role: string;
  follow_up_due: string | null;
  status: "open" | "acknowledged" | "resolved" | "dismissed";
  action_item_id: string | null;
  action_code: string | null;
  action_type: string | null;
  title: string | null;
  do_not_sell_flag: boolean;
  required_specialist: string | null;
  evidence: Record<string, unknown>;
}

export interface AdvisorActionCenterResponse {
  items: AdvisorActionCenterItem[];
  open_count: number;
  overdue_count: number;
  boundary: string;
}

export const monitoringFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_MONITORING === "true";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function request<T>(
  path: string,
  role: "client" | "advisor",
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(apiBase + path, {
    signal,
    headers: {
      Accept: "application/json",
      ...actorHeaders(demoActor(role)),
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

export function fetchMonitoringAlerts(
  householdId: string,
  signal?: AbortSignal,
): Promise<MonitoringAlertsResponse> {
  return request(`${householdPath(householdId)}/monitoring/alerts`, "client", signal);
}

export function fetchNextBestActions(
  householdId: string,
  signal?: AbortSignal,
): Promise<NextBestActionsResponse> {
  return request(`${householdPath(householdId)}/next-best-actions`, "client", signal);
}

export function fetchAdvisorActionCenter(
  signal?: AbortSignal,
): Promise<AdvisorActionCenterResponse> {
  return request("/api/v1/advisor/action-center", "advisor", signal);
}
