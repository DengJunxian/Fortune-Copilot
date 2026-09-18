import { actorHeaders, type DemoActor } from "./actor";

export interface CompetitionDemoResponse {
  demo_status: "synthetic_demo";
  bank_connection: false;
  client: {
    personal_profile: {
      name: string;
      age: number;
      city: string;
      occupation: string;
      marital_status: string;
    };
    family_profile: {
      members: Array<{ relationship: string; age: number; financially_dependent: boolean }>;
      dependent_count: number;
      has_minor_child: boolean;
      has_elder_support: boolean;
    };
    income_profile: {
      annual_income: string;
      spouse_annual_income: string;
      passive_annual_income: string;
      stability_score: string;
    };
  };
  balance_sheet: {
    total_assets: string;
    financial_assets: string;
    total_liabilities: string;
    net_worth: string;
    liquid_assets: string;
    investment_assets: string;
    monthly_cash_flow: string;
    debt_to_income_ratio: string;
    emergency_fund_months: string;
    asset_concentration: string;
    insurance_protection_gap: string;
    accounting_identity: string;
  };
  cash_flow: {
    annual_income: string;
    annual_expense: string;
    annual_debt_service: string;
    annual_surplus: string;
  };
  wealth_accounts: Array<{
    code: "liquidity" | "protection" | "liability_goal_matching" | "growth";
    chinese_name: string;
    target_amount: string;
    share_of_financial_assets: string;
    drivers: string[];
    explanation: string;
  }>;
  goals: Array<{
    goal_id: string;
    name: string;
    future_value: string;
    projected_assets: string;
    required_monthly_saving: string;
    allocated_monthly_saving: string;
    funding_gap: string;
    success_probability: string;
    coordination_status: "funded" | "on_track" | "resource_constrained";
  }>;
  risk_budget: {
    risk_capacity: string;
    risk_tolerance: string;
    risk_requirement: string;
    effective_risk_budget: string;
    maximum_portfolio_volatility: string;
    maximum_cvar_loss: string;
    risk_level: number;
    binding_dimension: "capacity" | "tolerance";
    requirement_conflict: boolean;
    evidence: string[];
  };
  quant: {
    input_hash: string;
    engine_version: string;
    selected_method: string;
    selection_reason: string;
    methods: Array<{
      method: "mean_variance" | "risk_parity" | "cvar" | "black_litterman";
      status: "optimal" | "fallback";
      weights: Record<string, string>;
      metrics: {
        expected_return: string;
        volatility: string;
        sharpe_ratio: string;
        cvar_loss: string;
        max_drawdown: string;
        liquidity_score: string;
      };
      evaluated_candidates: number;
      binding_constraints: string[];
    }>;
  };
  product_pipeline: {
    stages: string[];
    recommendations: Array<{
      product: {
        product_id: string;
        product_name: string;
        product_type: string;
        asset_class: string;
        risk_level: number;
        fees: string;
        is_demo: true;
      };
      target_weight: string;
      target_amount: string;
      rank_score: string;
      compliance: { passed: boolean; violations: string[]; checked_rules: string[] };
      why_selected: string[];
    }>;
    rejected_products: Array<{
      product_id: string;
      passed: boolean;
      violations: string[];
      checked_rules: string[];
    }>;
    suitability_violation_rate: string;
    no_executable_product: boolean;
  };
  behavior_findings: Array<{
    bias: string;
    evidence: string[];
    risk: string;
    intervention: string;
  }>;
  citations: Array<{
    citation_id: string;
    title: string;
    source_type: "official_snapshot" | "internal_demo";
    source_uri: string;
    excerpt: string;
  }>;
  advisor_summary: string[];
  rm_copilot: {
    current_wealth_issues: string[];
    priority_goals: string[];
    holding_risks: string[];
    service_opportunities: string[];
    next_best_action: string;
    communication_guide: string[];
    human_review_items: string[];
  };
  human_escalation: {
    required: boolean;
    triggers: string[];
    service_level: "routine" | "priority" | "urgent";
    next_best_action: string;
  };
  audit: {
    engine_version: string;
    analysis_date: string;
    input_hash: string;
    output_hash: string;
    calculation_source: "deterministic_tools";
    llm_modified_quant_output: false;
    external_network_calls: number;
    data_boundary: string;
  };
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function fetchCompetitionDemo(
  actor: DemoActor,
  signal?: AbortSignal,
): Promise<CompetitionDemoResponse> {
  const response = await fetch(apiBase + "/api/v1/competition/demo", {
    signal,
    headers: { Accept: "application/json", ...actorHeaders(actor) },
  });
  if (!response.ok) throw new Error(`Competition demo endpoint returned ${response.status}`);
  return (await response.json()) as CompetitionDemoResponse;
}
