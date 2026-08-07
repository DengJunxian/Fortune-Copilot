import type {
  AllocationLine,
  CandidateType,
  PortfolioCandidate,
  PortfolioResponse,
  ProductMapping,
  SuitabilityGate,
} from "../api/portfolio";

const assetNames: Record<string, string> = {
  cash_equivalent: "现金与现金等价物",
  fixed_income: "存款与分散固定收益",
  diversified_equity: "宽基与分散权益",
  real_assets: "公募 REITs 等实物资产工具",
  gold: "黄金分散工具",
};

function allocations(weights: Record<string, string>): AllocationLine[] {
  return Object.entries(weights).map(([assetClass, value]) => ({
    asset_class: assetClass,
    asset_class_name: assetNames[assetClass] ?? assetClass,
    ratio: value,
    amount: "0.00",
    expected_nominal_return: assetClass === "diversified_equity" ? "0.075000" : "0.035000",
    cvar_loss: assetClass === "diversified_equity" ? "0.350000" : "0.080000",
    max_drawdown: assetClass === "diversified_equity" ? "0.450000" : "0.100000",
    liquidity_score: "0.800000",
  }));
}

const familyGate: SuitabilityGate = {
  gate: "family_safety",
  name: "家庭安全闸门",
  status: "block",
  decision: "education_only",
  effective_risk_limit: null,
  high_risk_cap: "0.000000",
  failed_check_codes: ["family_liquidity", "family_debt", "family_protection"],
  explanation: "应急、债务、保障或近期目标仍有限制；市场情景不得覆盖这些前置条件。",
  checks: [
    { check_code: "family_liquidity", label: "应急与流动性", status: "block", observed_value: "应急资金不足", rule: "先满足动态安全月数", reason: "限制新增高风险配置。", source_record_ids: ["asset-cash"] },
    { check_code: "family_debt", label: "债务负担", status: "block", observed_value: "存在高息债务", rule: "高息债务优先", reason: "不得借款扩大投资。", source_record_ids: ["debt"] },
    { check_code: "family_protection", label: "保障缺口", status: "block", observed_value: "保障覆盖不足", rule: "先覆盖不可承受风险", reason: "限制长期增长。", source_record_ids: ["policy"] },
  ],
};

const customerGate: SuitabilityGate = {
  gate: "customer",
  name: "客户适当性闸门",
  status: "pass",
  decision: "allow",
  effective_risk_limit: "r3",
  high_risk_cap: "0.350000",
  failed_check_codes: [],
  explanation: "能力、意愿、知识与行为取审慎下限 R3；高风险资产上限 35%。",
  checks: [
    { check_code: "customer_capacity", label: "风险承担能力", status: "pass", observed_value: "58% → R3", rule: "四维取审慎下限", reason: "该维度允许上限为 R3。", source_record_ids: ["risk"] },
  ],
};

const productGate: SuitabilityGate = {
  gate: "product",
  name: "产品适当性闸门",
  status: "restrict",
  decision: "education_only",
  effective_risk_limit: "r3",
  high_risk_cap: "0.350000",
  failed_check_codes: ["mapping_education"],
  explanation: "产品类型仅作教育展示；家庭安全闸门仍优先。",
  checks: [
    { check_code: "mapping_education", label: "模拟短债基金类型", status: "restrict", observed_value: "固定收益 30% / R2", rule: "风险、期限、流动性与金额同时匹配", reason: "没有可执行长期金额，只展示类型教育。", source_record_ids: ["mock-product"] },
  ],
};

function mappings(weights: Record<string, string>): ProductMapping[] {
  return Object.entries(weights).filter(([, value]) => Number(value) > 0).map(([assetClass, value], index) => ({
    asset_class: assetClass,
    asset_class_name: assetNames[assetClass] ?? assetClass,
    allocation_ratio: value,
    allocation_amount: "0.00",
    product_id: `mock-product-${index}`,
    product_code: assetClass === "diversified_equity" ? "MOCK-INDEX-BROAD-001" : `MOCK-TYPE-${index}`,
    product_name: assetClass === "diversified_equity" ? "模拟宽基指数基金类型" : `模拟${assetNames[assetClass] ?? assetClass}类型`,
    product_type: assetClass,
    risk_level: assetClass === "diversified_equity" ? "r4" : "r2",
    liquidity_level: "within_7_days",
    decision: "education_only",
    reasons: ["家庭安全闸门未通过，只展示产品类型教育"],
    is_mock: true,
  }));
}

const weightsByType: Record<CandidateType, Record<string, string>> = {
  conservative: { cash_equivalent: "0.300000", fixed_income: "0.650000", diversified_equity: "0.000000", real_assets: "0.000000", gold: "0.050000" },
  balanced: { cash_equivalent: "0.200000", fixed_income: "0.700000", diversified_equity: "0.000000", real_assets: "0.000000", gold: "0.100000" },
  growth: { cash_equivalent: "0.150000", fixed_income: "0.700000", diversified_equity: "0.000000", real_assets: "0.000000", gold: "0.150000" },
};

function candidate(type: CandidateType, name: string, index: number): PortfolioCandidate {
  const weights = weightsByType[type];
  const lines = allocations(weights);
  return {
    candidate_type: type,
    name,
    decision: "education_only",
    investment_amount: "0.00",
    strategic_allocations: lines,
    tactical_allocations: lines,
    expected_nominal_return: `0.0${3 + index}0000`,
    expected_real_return: `0.00${5 + index}000`,
    goal_success_probability: "0.000000",
    simulation_method: "deterministic_weighted_scenarios_not_monte_carlo",
    simulation_horizon_months: 120,
    simulated_range_low: "0.00",
    simulated_range_base: "0.00",
    simulated_range_high: "0.00",
    extreme_loss_ratio: `0.0${8 + index}0000`,
    extreme_loss_amount: "0.00",
    max_drawdown_estimate: `0.1${index}0000`,
    liquidity_score: "0.800000",
    liquidity_description: "较高流动性",
    annual_fee_rate: "0.004000",
    annual_fee_estimate: "0.00",
    applicable_conditions: ["仅使用动态四账户确认的长期资金", "三道闸门均优先于市场情景"],
    primary_risks: ["利率和净值仍会变化", "当前不可执行"],
    why_not_other_candidates: `${name}方案按当前风险取舍生成；家庭安全闸门未通过时只作教育展示。`,
    gates: [familyGate, customerGate, productGate],
    product_mappings: mappings(weights),
    optimization: {
      method: type === "conservative" ? "deterministic_grid_search" : "rule_based_fallback",
      status: type === "conservative" ? "optimal" : "fallback",
      optimizer_version: "deterministic-grid-v1.0.0",
      random_seed: 20260804,
      grid_step: "0.050000",
      evaluated_candidates: type === "conservative" ? 37 : 0,
      objective_score: `0.${index + 1}00000`,
      parameter_hash: `${type}-parameter-hash-0123456789`,
      parameters: { candidate: type },
      fallback_reason: type === "conservative" ? null : "候选原始边界与安全上限无可行交集。",
    },
    rebalancing: {
      market_scenario: "neutral",
      status: "blocked_by_safety",
      absolute_threshold: "0.050000",
      relative_threshold: "0.200000",
      maximum_tactical_shift: "0.050000",
      next_scheduled_review: "2027-02-04",
      explanation: "家庭安全闸门未通过；暂停按市场情景扩张。",
      lines: lines.map((line) => ({ asset_class: line.asset_class, asset_class_name: line.asset_class_name, current_ratio: line.asset_class === "diversified_equity" ? "1.000000" : "0.000000", strategic_ratio: line.ratio, tactical_ratio: line.ratio, absolute_drift: line.asset_class === "diversified_equity" ? "1.000000" : line.ratio, relative_drift: line.ratio === "0.000000" ? null : "1.000000", trigger: true, action: "安全闸门通过后复核" })),
    },
  };
}

const mockProduct = {
  id: "mock-product",
  code: "MOCK-BWM-NAV-006",
  name: "模拟净值型银行理财类型",
  product_type: "bank_wealth_management",
  asset_class: "fixed_income",
  risk_level: "r2" as const,
  term_months: 6,
  minimum_holding_months: 6,
  liquidity_level: "within_1_year",
  redemption_rules: "封闭期内不可赎回。",
  annual_fee_rate: "0.008000",
  underlying_assets: ["债券"],
  historical_volatility_min: "0.005000",
  historical_volatility_max: "0.060000",
  minimum_investment: "10000.00",
  suitable_accounts: ["stable_goals", "long_term_growth"],
  principal_guaranteed: false,
  guarantee_basis: null,
  guarantee_disclosure: "银行理财不是存款，不承诺保本保收益。",
  non_guaranteed_disclosure: "净值会波动，业绩比较基准不是收益承诺。",
  complexity_level: "standard",
  professional_only: false,
  education_only: false,
  enabled: true,
  is_simulated: true,
  terms: { priority: 3 },
  catalog_version: "1.0.0",
  data_date: "2026-08-04",
  source: "test-fixture",
};

export const portfolioFixture: PortfolioResponse = {
  meta: { household_id: "household-b", household_code: "DEMO_B", analysis_date: "2026-08-04", data_as_of: "2026-08-04", input_version: "fixture-portfolio-input", formula_version: "portfolio-gates-v1.0.0", rule_code: "portfolio_optimization_and_suitability", rule_version: "1.0.0", optimizer_version: "deterministic-grid-v1.0.0", catalog_version: "1.0.0", calculation_source: "deterministic_tools", currency: "CNY", synthetic_data: true, market_scenario: "neutral" },
  context: { current_growth_assets: "120000.00", eligible_long_term_amount: "0.00", amount_to_restore_safety_layers: "120000.00", long_term_goal_present_value_gap: "1510000.00", simulation_horizon_months: 120, annual_new_surplus: "72000.00", counting_note: "组合金额只取通过前置顺序后的长期资金。" },
  family_safety_gate: familyGate,
  customer_suitability_gate: customerGate,
  candidates: [candidate("conservative", "稳健", 0), candidate("balanced", "基准", 1), candidate("growth", "进取", 2)],
  catalog: { catalog_code: "wealthtwin_mock_product_catalog", catalog_version: "1.0.0", data_date: "2026-08-04", source_type: "mock", source_summary: "竞赛受控模拟产品类型库。", product_count: 19, products: [mockProduct], professional_hedge_lab_enabled: false },
  education_cards: [{ code: "deposit_vs_wealth", title: "存款与银行理财不是同一种承诺", summary: "存款合同属性与净值型资管风险分开阅读。", points: ["银行理财不是存款。", "业绩比较基准不是收益承诺。"] }, { code: "diversified_index", title: "普通家庭默认从宽基分散开始", summary: "不默认推荐个股或热点主题。", points: ["指数化不等于保本。", "只有长期资金才可执行。"] }],
  professional_hedge_lab: { enabled: false, mode: "read_only_education", title: "专业对冲实验室默认关闭", reason: "普通家庭不提供股指期货、杠杆或交易入口。", prerequisites: ["专业投资者资格", "明确套保头寸", "人工复核"] },
  counting_note: "三套比例来自确定性网格优化或规则降级；不是 Monte Carlo 或收益承诺。",
};
