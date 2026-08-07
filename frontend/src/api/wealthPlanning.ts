import { actorHeaders, demoActor } from "./actor";
import type { FinancialAnalysis } from "./financial";
import type { PlanningResponse } from "./planning";

export type PlanningScope = "individual" | "family";
export type EmploymentStability = "low" | "medium" | "high";
export type CityTier = "tier_one_or_new_tier_one" | "developed_city" | "other_city";
export type InvestmentExperience = "none" | "basic" | "experienced";
export type RiskPreference = "conservative" | "balanced" | "growth";
export type LossTolerance = "low" | "medium" | "high";
export type FundsSource =
  | "salary"
  | "business"
  | "accumulated_savings"
  | "property_income"
  | "investment_income"
  | "family_support"
  | "other";
export type AssetIntakeCategory =
  | "cash_and_equivalents"
  | "time_deposit_and_bank_wealth"
  | "non_bank_financial"
  | "primary_residence"
  | "investment_property"
  | "vehicle_and_other";
export type LiabilityIntakeCategory =
  | "mortgage"
  | "auto_loan"
  | "consumer_loan"
  | "credit_card_unpaid"
  | "non_bank_loan"
  | "other";
export type IncomeIntakeCategory =
  | "self_employment"
  | "spouse_employment"
  | "asset_income"
  | "rental_income"
  | "other";
export type ExpenseIntakeCategory =
  | "living"
  | "parent_support"
  | "child_education"
  | "insurance_premium"
  | "debt_service"
  | "other";

export interface IntakeMember {
  display_name: string;
  relationship: string;
  birth_date: string;
  occupation: string;
  employment_stability: EmploymentStability;
  expected_retirement_age: number | null;
}

export interface IntakeAsset {
  category: AssetIntakeCategory;
  label: string;
  amount: string;
}

export interface IntakeLiability {
  category: LiabilityIntakeCategory;
  label: string;
  balance: string;
  monthly_payment: string;
  annual_interest_rate: string;
}

export interface IntakeIncome {
  category: IncomeIntakeCategory;
  label: string;
  annual_amount: string;
}

export interface IntakeExpense {
  category: ExpenseIntakeCategory;
  label: string;
  annual_amount: string;
}

export interface KycProfile {
  city_tier: CityTier;
  growth_entry_threshold: string;
  investment_experience: InvestmentExperience;
  risk_preference: RiskPreference;
  loss_tolerance: LossTolerance;
  investment_horizon_years: number;
  funds_sources: FundsSource[];
  personal_pension_status: "opened" | "not_opened" | "not_sure";
}

export interface PlanningIntake {
  planning_scope: PlanningScope;
  case_name: string;
  region: string;
  kyc: KycProfile;
  members: IntakeMember[];
  assets: IntakeAsset[];
  liabilities: IntakeLiability[];
  incomes: IntakeIncome[];
  expenses: IntakeExpense[];
}

export interface PlanningCaseResponse {
  household_id: string;
  analysis: FinancialAnalysis;
}

export interface RatioExplanationItem {
  metric_id:
    | "liquidity_reserve_months"
    | "debt_to_asset_ratio"
    | "savings_ratio"
    | "debt_service_burden_ratio"
    | "investable_assets_to_net_worth"
    | "property_to_assets_ratio";
  interpretation: string;
  focus: string;
  next_step: string;
}

export interface RatioExplanationResponse {
  provider: string;
  model: string;
  used_external_model: boolean;
  degraded: boolean;
  calculation_source: "deterministic_tools";
  items: RatioExplanationItem[];
}

export interface PlanningGoalDraft {
  name: string;
  goal_type:
    | "emergency_fund"
    | "education"
    | "home"
    | "retirement"
    | "medical"
    | "travel"
    | "debt_repayment"
    | "family_support"
    | "wealth_transfer"
    | "other";
  target_amount: string;
  target_date: string;
  prepared_amount: string;
  rigidity: "flexible" | "important" | "rigid";
  priority: number;
  can_defer: boolean;
}

export interface NarrativeMajorExpenseInput {
  name: string;
  target_amount: string;
  target_date: string;
  prepared_amount: string;
  planned_source: string;
}

export interface PlanNarrative {
  family_analysis: string;
  goal_analysis: string;
  major_expense_analysis: string;
  statement_analysis: string;
  ratio_analysis_summary: string;
  four_account_analysis: string;
  review_triggers: string[];
}

export interface PlanNarrativeResponse {
  provider: string;
  model: string;
  used_external_model: boolean;
  degraded: boolean;
  calculation_source: "deterministic_tools";
  planning: PlanningResponse;
  narrative: PlanNarrative;
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const clientActor = demoActor("client");

async function readJson<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    signal,
    headers: {
      Accept: "application/json",
      ...actorHeaders(clientActor),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new Error(payload?.error?.message ?? `请求失败（${response.status}）`);
  }
  return await response.json() as T;
}

export function createPlanningCase(payload: PlanningIntake): Promise<PlanningCaseResponse> {
  return readJson<PlanningCaseResponse>("/api/v1/wealth-planning/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function requestRatioExplanations(
  householdId: string,
  signal?: AbortSignal,
): Promise<RatioExplanationResponse> {
  return readJson<RatioExplanationResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/ratio-explanations`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "请逐项解释当前家庭财务比率说明了什么、需要关注什么，以及下一步如何处理。",
      }),
    },
    signal,
  );
}

export function requestPlanNarrative(
  householdId: string,
  goals: PlanningGoalDraft[],
  majorExpenses: NarrativeMajorExpenseInput[],
  signal?: AbortSignal,
): Promise<PlanNarrativeResponse> {
  return readJson<PlanNarrativeResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/plan-narrative`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goals: goals.map((goal) => ({
          name: goal.name,
          goal_type: goal.goal_type,
          target_amount: goal.target_amount,
          target_date: goal.target_date,
          prepared_amount: goal.prepared_amount,
          rigidity: goal.rigidity,
        })),
        major_expenses: majorExpenses,
      }),
    },
    signal,
  );
}

export async function createGoalRecords(
  householdId: string,
  goals: PlanningGoalDraft[],
): Promise<void> {
  const today = new Date().toISOString().slice(0, 10);
  for (const goal of goals) {
    await readJson(`/api/v1/households/${encodeURIComponent(householdId)}/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        currency: "CNY",
        valuation_date: today,
        data_source: "client_intake",
        is_user_confirmed: true,
        name: goal.name,
        goal_type: goal.goal_type,
        target_amount: goal.target_amount,
        target_date: goal.target_date,
        rigidity: goal.rigidity,
        priority: goal.priority,
        can_defer: goal.can_defer,
        minimum_acceptable_amount: goal.target_amount,
        prepared_amount: goal.prepared_amount,
        annual_cost_growth_rate: goal.goal_type === "education" ? "0.050000" : "0.030000",
      }),
    });
  }
}
