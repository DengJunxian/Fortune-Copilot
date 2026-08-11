import { actorHeaders, demoActor } from "./actor";
import type { RiskLevel } from "./clientProfile";

export type CFSComponentType =
  | "liquidity"
  | "debt"
  | "protection"
  | "housing"
  | "education"
  | "retirement"
  | "investment"
  | "enterprise_risk"
  | "cross_border"
  | "succession"
  | "trust"
  | "philanthropy"
  | "professional_service"
  | "no_action";

export type CFSComponentStatus =
  | "recommended"
  | "no_action_required"
  | "professional_review_required"
  | "completed";

export type ProfessionalSpecialistType =
  | "private_banker"
  | "investment_advisor"
  | "pension_specialist"
  | "insurance_specialist"
  | "cross_border_specialist"
  | "trust_specialist"
  | "legal_tax_professional"
  | "philanthropy_specialist";

export interface RiskBudgetFactor {
  code:
    | "capacity"
    | "willingness"
    | "behavior"
    | "existing_economic_exposure"
    | "liquidity"
    | "liability_rigidity"
    | "time_horizon";
  label: string;
  level: RiskLevel | null;
  amount: string;
  ratio: string;
  explanation: string;
}

export interface HouseholdRiskBudget {
  factors: RiskBudgetFactor[];
  capacity: RiskLevel;
  willingness: RiskLevel;
  behavior: RiskLevel;
  household_economic_risk_capacity: RiskLevel;
  existing_economic_exposure: string;
  economic_exposure_ratio: string;
  liquidity_reserve_required: string;
  liquidity_gap: string;
  rigid_liability_target: string;
  rigid_liability_gap: string;
  shortest_time_horizon_days: number | null;
  risk_ceiling_ratio: string;
  risk_ceiling_amount: string;
  remaining_risk_capacity: string;
  additional_risk_allowed: boolean;
  decision: "open" | "repair_first" | "professional_only";
  constraints: string[];
  input_hash: string;
  version: string;
  explanation: string;
}

export interface CFSComponent {
  id: string;
  solution_id: string;
  wealth_need_id: string | null;
  component_type: CFSComponentType;
  priority: number;
  target_amount: string;
  minimum_amount: string;
  time_horizon: "immediate" | "short_term" | "medium_term" | "long_term" | "ongoing";
  recommended_action: string;
  product_mapping_allowed: boolean;
  professional_review_required: boolean;
  required_specialist: ProfessionalSpecialistType | null;
  status: CFSComponentStatus;
  rationale: string;
  evidence: Record<string, unknown>;
  currency: string;
}

export interface CFSOrchestrationStep {
  component_id: string;
  purpose: string;
  allowed_risk: RiskLevel;
  deterministic_tool:
    | "financial_health"
    | "liability_calendar"
    | "protection_planner"
    | "pension_planner"
    | "planning_waterfall"
    | "portfolio_optimizer"
    | "family_enterprise"
    | "professional_routing"
    | "no_action";
  status: "ready" | "blocked" | "professional_review";
  output_summary: string;
}

export interface ProfessionalReferral {
  id: string;
  household_id: string;
  solution_id: string;
  component_id: string;
  specialist_type: ProfessionalSpecialistType;
  trigger_reason: string;
  urgency: "low" | "medium" | "high" | "urgent";
  status: "open" | "accepted" | "completed" | "cancelled";
  due_date: string | null;
  evidence: Record<string, unknown>;
}

export interface CFSSolutionResponse {
  meta: {
    household_id: string;
    analysis_date: string;
    data_as_of: string | null;
    source_snapshot_id: string;
    rule_version: string;
    formula_version: string;
    calculation_source: "deterministic_tools";
    idempotent_replay: boolean;
  };
  solution: {
    id: string;
    household_id: string;
    source_snapshot_id: string;
    solution_version: number;
    status: "active" | "superseded" | "needs_review";
    summary: {
      headline?: string;
      no_action_required?: boolean;
      boundary?: string;
    };
    decision_hash: string;
    risk_budget_version: string;
  };
  components: CFSComponent[];
  risk_budget: HouseholdRiskBudget;
  orchestration: CFSOrchestrationStep[];
  referrals: ProfessionalReferral[];
}

export const cfsFeatureEnabled = import.meta.env.VITE_ENABLE_V5_CFS === "true";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

export class CFSApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
  ) {
    super(message);
    this.name = "CFSApiError";
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
    throw new CFSApiError(
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

export function createCFSSolution(
  householdId: string,
  signal?: AbortSignal,
): Promise<CFSSolutionResponse> {
  return request(`${householdPath(householdId)}/cfs-solutions`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      "X-Confirm-Action": "create_cfs_solution",
    },
    body: JSON.stringify({ is_user_confirmed: true }),
  });
}

export function fetchCFSSolution(
  householdId: string,
  solutionId: string,
  signal?: AbortSignal,
): Promise<CFSSolutionResponse> {
  return request(
    `${householdPath(householdId)}/cfs-solutions/${encodeURIComponent(solutionId)}`,
    { signal },
  );
}

export function recalculateCFSSolution(
  householdId: string,
  solutionId: string,
  signal?: AbortSignal,
): Promise<CFSSolutionResponse> {
  return request(
    `${householdPath(householdId)}/cfs-solutions/${encodeURIComponent(solutionId)}/recalculate`,
    {
      method: "POST",
      signal,
      headers: {
        "Content-Type": "application/json",
        "X-Confirm-Action": "recalculate_cfs_solution",
      },
      body: JSON.stringify({ is_user_confirmed: true }),
    },
  );
}
