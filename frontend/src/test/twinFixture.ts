import type { SimulationDistribution, TwinResult } from "../api/twin";

function distribution(
  label: string,
  values: {
    success: string;
    depletion: string;
    forced: string;
    forcedAmount: string;
    endingP10: string;
    endingMedian: string;
  },
): SimulationDistribution {
  return {
    label,
    path_count: 100,
    horizon_months: 360,
    goal_success_probability: values.success,
    depletion_probability: values.depletion,
    forced_sale_probability: values.forced,
    median_forced_sale_amount: values.forcedAmount,
    ending_net_worth_median: values.endingMedian,
    ending_net_worth_p10: values.endingP10,
    total_goal_shortfall_median: "0.00",
    required_additional_monthly_savings: "0.00",
    fan: [
      { month: 0, date: "2026-08-04", primary_age: "35.21", p10: "1642000.00", p25: "1642000.00", p50: "1642000.00", p75: "1642000.00", p90: "1642000.00", median_liquid_assets: "200000.00", median_long_term_assets: "250000.00", median_liabilities: "1208000.00" },
      { month: 180, date: "2041-08-04", primary_age: "50.21", p10: "820000.00", p25: "1600000.00", p50: "2800000.00", p75: "3900000.00", p90: "5200000.00", median_liquid_assets: "420000.00", median_long_term_assets: "1800000.00", median_liabilities: "420000.00" },
      { month: 360, date: "2056-08-04", primary_age: "65.21", p10: values.endingP10, p25: "4200000.00", p50: values.endingMedian, p75: "8900000.00", p90: "12600000.00", median_liquid_assets: "350000.00", median_long_term_assets: "6900000.00", median_liabilities: "0.00" },
    ],
    goal_outcomes: [
      { goal_id: "goal-education", name: "子女教育", due_month: 120, required_amount: "977336.78", success_probability: values.success, failure_probability: (1 - Number(values.success)).toFixed(6), median_shortfall: "0.00" },
      { goal_id: "goal-retirement", name: "夫妻退休养老", due_month: 297, required_amount: "4156725.13", success_probability: "1.000000", failure_probability: "0.000000", median_shortfall: "0.00" },
      { goal_id: "goal-support", name: "父母赡养储备", due_month: 60, required_amount: "366298.98", success_probability: "1.000000", failure_probability: "0.000000", median_shortfall: "0.00" },
    ],
    failure_time_distribution: [{ year: 25, path_count: 6, probability: "0.060000", most_common_goal: "夫妻退休养老" }],
    worst_paths: [
      { path_id: 17, ending_net_worth: values.endingP10, minimum_net_worth: "-125000.00", first_failed_goal: "夫妻退休养老", first_failure_month: 297, depletion_month: 302, forced_sale_amount: values.forcedAmount, total_goal_shortfall: "180000.00", explanation: "尾部收益路径叠加退休目标支出。" },
      { path_id: 28, ending_net_worth: "1510000.00", minimum_net_worth: "120000.00", first_failed_goal: null, first_failure_month: null, depletion_month: null, forced_sale_amount: values.forcedAmount, total_goal_shortfall: "0.00", explanation: "低收益路径。" },
    ],
    validation: { all_values_finite: true, primary_income_paid_during_interruption_max: "0.00", goal_spending_events_applied: 300, common_random_numbers: true },
  };
}

const baseline = distribution("无冲击基线", { success: "0.960000", depletion: "0.290000", forced: "1.000000", forcedAmount: "27143.23", endingP10: "1761600.39", endingMedian: "5613217.18" });
const original = distribution("原方案／组合压力", { success: "0.530000", depletion: "0.390000", forced: "1.000000", forcedAmount: "126714.68", endingP10: "1480352.75", endingMedian: "5130539.91" });
const optimized = distribution("优化方案／组合压力", { success: "1.000000", depletion: "0.000000", forced: "0.040000", forcedAmount: "0.00", endingP10: "3583448.43", endingMedian: "7417985.04" });

export const twinFixture = {
  meta: {
    run_id: "twin-run-fixture-001",
    household_id: "household-b",
    household_code: "DEMO_B",
    analysis_date: "2026-08-04",
    data_as_of: "2026-08-04",
    input_version: "fixture-twin-input-version-001",
    rule_code: "wealth_twin_simulation",
    rule_version: "1.0.0",
    formula_version: "wealth-state-transition-v1.0.0",
    engine_version: "wealth-twin-monte-carlo-v1.0.0",
    result_version: "wealth-twin-result-v1.0.0",
    scenario_version: "1.0.0",
    calculation_source: "deterministic_simulation_engine",
    synthetic_data: true,
    currency: "CNY",
  },
  initial_state: {
    members: [{ member_id: "member-1", name: "李先生", relationship: "本人", age_at_start: "35.21", recorded_retirement_age: 60 }],
    annual_income: "360000.00",
    annual_expenses_excluding_debt_service: "216000.00",
    annual_essential_expenses_excluding_debt_service: "156000.00",
    monthly_compressible_expenses: "1950.00",
    asset_buckets: { cash_equivalent: "50000.00", fixed_income: "150000.00", diversified_equity: "120000.00", primary_property: "2400000.00", investment_property: "0.00", real_assets: "0.00", gold: "0.00", pension: "30000.00", other_assets: "100000.00" },
    total_assets: "2850000.00",
    total_liabilities: "1208000.00",
    medical_coverage_available: "500000.00",
    medical_deductible: "10000.00",
    pension_annual_contributions: "12000.00",
    goals: [{ goal_id: "goal-education", name: "子女教育", goal_type: "education", due_month: 120, current_amount: "600000.00", prepared_amount: "80000.00", annual_cost_growth_rate: "0.050000" }],
    source_record_ids: ["asset-1", "income-1", "goal-education"],
    counting_note: "信用卡未付计入负债；信用卡额度从未计入资产。",
  },
  assumptions: {
    seed: 20260804,
    path_count: 100,
    horizon_months: 360,
    time_step_months: 1,
    output_interval_months: 12,
    inflation_rate: "0.025000",
    income_growth_rate: "0.030000",
    asset_classes: ["cash_equivalent", "fixed_income", "diversified_equity", "real_assets", "gold"],
    asset_assumptions: { diversified_equity: { expected_annual_return: "0.060000", annual_volatility: "0.180000" } },
    correlation_matrix: [["1.000000"]],
    property_assumption: { expected_annual_return: "0.020000", annual_volatility: "0.100000" },
    pension_assumption: { expected_annual_return: "0.035000", annual_volatility: "0.080000" },
    scenario_codes: ["unemployment_equity_down_30"],
    scenario_parameters: { income_interruption_months: 6, diversified_equity_shock: "-0.300000" },
    plan_adjustments: { primary_retirement_age: 62, additional_monthly_savings: "2000.00", equity_ratio: "0.300000", liquidity_reallocation_amount: "120000.00" },
    family_events: [],
    parameter_hash: "fixture-parameter-hash-0123456789abcdef",
    source_type: "internal_demo",
  },
  baseline,
  original_stress: original,
  optimized_stress: optimized,
  scenario_impacts: [{
    scenario_code: "unemployment_equity_down_30",
    name: "失业 6 个月 + 权益下跌 30%",
    emergency_support_months: "7.41",
    first_failed_goal: "子女教育",
    forced_sale_probability: "1.000000",
    median_forced_sale_amount: "126714.68",
    insurance_coverage_applied: "0.00",
    remaining_medical_gap: "0.00",
    retirement_delay_needed: false,
    suggested_retirement_delay_years: 0,
    monthly_compressible_expenses: "1950.00",
    required_additional_monthly_savings: "0.00",
    baseline_goal_success_probability: "0.960000",
    scenario_goal_success_probability: "0.530000",
    success_probability_change: "-0.430000",
    applicable: true,
    explanation: "应急月数、目标失败和被迫出售来自同一组状态路径。",
  }],
  comparison: {
    baseline_success_probability: "0.960000",
    original_stress_success_probability: "0.530000",
    optimized_stress_success_probability: "1.000000",
    stress_change: "-0.430000",
    optimization_change: "0.470000",
    baseline_forced_sale_probability: "1.000000",
    original_forced_sale_probability: "1.000000",
    optimized_forced_sale_probability: "0.040000",
    liquidity_reallocation_amount: "120000.00",
    avoided_forced_sale_probability: "0.960000",
    stress_not_better_than_baseline: true,
    positive_override_explanation: null,
    liquidity_explanation: "优化方案把 120000.00 元从长期资产重分类为流动性，起点净资产不变；只报告实际差值。",
  },
  limitations: ["收益、波动和压力参数均为 internal_demo，不是预测或收益承诺。", "自住房不自动作为目标流动资金；信用卡额度从未进入资产。"],
  counting_note: "逐月更新收益与收入，再扣生活支出、债务和到期目标；目标只在到期月扣一次。",
} satisfies TwinResult;
