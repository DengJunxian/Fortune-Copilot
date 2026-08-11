import { actorHeaders, demoActor } from "./actor";

export type GraphEntityType = "household" | "person" | "enterprise" | "trust" | "other";
export type GraphInstrumentType =
  | "cash"
  | "demand_deposit"
  | "money_market"
  | "time_deposit"
  | "bank_wealth_management"
  | "bond"
  | "bond_fund"
  | "public_fund"
  | "equity_fund"
  | "stock"
  | "pension_account"
  | "insurance_cash_value"
  | "trust"
  | "primary_residence"
  | "investment_property"
  | "vehicle"
  | "other";
export type GraphPurpose = "daily" | "protection" | "stable" | "growth";
export type GraphRisk = "low" | "medium_low" | "medium" | "medium_high" | "high";
export type GraphComplexity = "basic" | "standard" | "complex" | "professional";
export type GraphAccountWrapper =
  | "ordinary"
  | "demand_account"
  | "personal_pension"
  | "social_security"
  | "enterprise_annuity"
  | "occupational_annuity"
  | "provident_fund"
  | "insurance"
  | "other";

export interface FinancialEntity {
  id: string;
  entity_type: GraphEntityType;
  display_name: string;
  jurisdiction: string;
}

export interface FinancialAccount {
  id: string;
  owner_entity_id: string;
  provider_name: string;
  account_type: string;
  account_wrapper: GraphAccountWrapper;
  currency: string;
}

export interface GraphPosition {
  id: string;
  account_id: string;
  owner_entity_id: string;
  legacy_asset_id: string | null;
  instrument_type: GraphInstrumentType;
  instrument_code: string | null;
  name: string;
  quantity: string | null;
  acquisition_cost: string;
  market_value: string;
  currency: string;
  valuation_date: string | null;
  purpose_dimension: GraphPurpose;
  risk_level: GraphRisk;
  liquidity_days: number;
  complexity_level: GraphComplexity;
  principal_loss_possible: boolean;
  legally_principal_guaranteed: boolean;
  lock_up: boolean;
  withdrawable_date: string | null;
  source_kind: string;
  evidence_json: Record<string, unknown>;
  is_user_confirmed: boolean;
  version: number;
}

export interface FinancialGraphResponse {
  meta: {
    household_id: string;
    data_as_of: string | null;
    calculation_source: "deterministic_tools";
  };
  entities: FinancialEntity[];
  accounts: FinancialAccount[];
  positions: GraphPosition[];
  integrity: { status: "passed" | "needs_review"; issues: string[] };
  projection_diagnostic: {
    status: "matched" | "mismatch";
    legacy_asset_total: string;
    projected_asset_total: string;
    difference: string;
    details: string[];
  };
}

export interface PositionDraft {
  owner_entity_id?: string;
  account?: {
    provider_name: string;
    account_type: string;
    account_wrapper: GraphAccountWrapper;
    jurisdiction: string;
  };
  instrument_type: GraphInstrumentType;
  instrument_code?: string;
  name: string;
  quantity?: string;
  acquisition_cost: string;
  market_value: string;
  currency: string;
  valuation_date: string;
  purpose_dimension: GraphPurpose;
  risk_level: GraphRisk;
  liquidity_days: number;
  complexity_level: GraphComplexity;
  principal_loss_possible: boolean;
  legally_principal_guaranteed: boolean;
  lock_up: boolean;
  withdrawable_date?: string;
  source_kind: "user_self_report";
  evidence_json: Record<string, unknown>;
  data_source: "client_intake";
  is_user_confirmed: true;
}

export type PositionPatch = Partial<Omit<PositionDraft, "account" | "data_source">> & {
  expected_version: number;
  data_source?: "client_intake";
};

export const financialGraphFeatureEnabled =
  import.meta.env.VITE_ENABLE_V5_FINANCIAL_GRAPH === "true";

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
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

function positionPath(householdId: string): string {
  return `/api/v1/households/${encodeURIComponent(householdId)}/financial-graph/positions`;
}

export function fetchFinancialGraph(
  householdId: string,
  signal?: AbortSignal,
): Promise<FinancialGraphResponse> {
  return request<FinancialGraphResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/financial-graph`,
    { signal },
  );
}

export function createGraphPosition(
  householdId: string,
  payload: PositionDraft,
): Promise<GraphPosition> {
  return request<GraphPosition>(positionPath(householdId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateGraphPosition(
  householdId: string,
  positionId: string,
  payload: PositionPatch,
): Promise<GraphPosition> {
  return request<GraphPosition>(
    `${positionPath(householdId)}/${encodeURIComponent(positionId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function deleteGraphPosition(
  householdId: string,
  positionId: string,
  expectedVersion: number,
): Promise<void> {
  return request<void>(
    `${positionPath(householdId)}/${encodeURIComponent(positionId)}`
      + `?expected_version=${expectedVersion}`,
    {
      method: "DELETE",
      headers: { "X-Confirm-Action": "delete_financial_graph_position" },
    },
  );
}
