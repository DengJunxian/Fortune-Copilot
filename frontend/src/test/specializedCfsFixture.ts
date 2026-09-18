import type {
  CurrencyExposureResponse,
  FamilySpecializedResponse,
  RetirementPlanResponse,
} from "../api/specializedCfs";

const meta = {
  household_id: "household-c",
  analysis_date: "2026-08-10",
  data_as_of: "2026-08-10",
  input_hash: "specialized-input-hash-0123456789",
  rule_version: "1.0.0",
  formula_version: "specialized-cfs-v1",
  calculation_source: "deterministic_tools",
} as const;

const retirementRoute = {
  need: "retirement",
  complexity: "high",
  complexity_gate_passed: true,
  specialist_type: "pension_specialist",
  referral_id: "referral-retirement",
  referral_status: "open",
  advisor_workflow_status: "referral_open",
  reason: "退休收入底线、制度权益和长寿缺口需要在同一方案中复核。",
  boundary: "专业转介只建立协作责任节点。",
} as const;

export const retirementFixture = {
  meta,
  has_retirement_need: true,
  liabilities: {
    basic_retirement_liability: "4320000.00",
    medical_liability: "518400.00",
    long_term_care_liability: "648000.00",
    improved_retirement_goal: "5486400.00",
    retirement_start_date: "2030-06-30",
    retirement_years: 30,
  },
  entitlements: [
    {
      id: "entitlement-social",
      member_id: "member-c",
      entitlement_type: "social_security",
      balance: "620000.00",
      expected_income: "78000.00",
      start_age: 60,
      start_date: "2030-06-30",
      end_date: null,
      guaranteed: true,
      indexed: true,
      lock_up: true,
      source_kind: "social_security",
      confidence: "0.700000",
      evidence: { source_record_ids: ["social-c"] },
    },
  ],
  output: {
    retirement_floor: "162000.00",
    guaranteed_income: "78000.00",
    income_gap: "84000.00",
    longevity_gap: "2520000.00",
    liquidity_gap: "420000.00",
  },
  route: retirementRoute,
  assumptions: ["退休收入底线按必要支出、医疗和长期照护责任拆分。"],
  boundary: "退休测算用于识别收入底线与缺口，不承诺养老金待遇或投资收益。",
} satisfies RetirementPlanResponse;

export const currencyFixture = {
  meta: { ...meta, household_id: "household-b" },
  base_currency: "CNY",
  material_exposure_detected: true,
  exposures: [
    {
      id: "exposure-usd-asset",
      entity_id: "entity-b",
      exposure_type: "asset_currency",
      currency: "USD",
      amount: "300000.00",
      direction: "inflow",
      horizon: "current",
      source_record_ids: ["asset-b"],
    },
    {
      id: "exposure-usd-education",
      entity_id: null,
      exposure_type: "education_liability",
      currency: "USD",
      amount: "180000.00",
      direction: "outflow",
      horizon: "medium_term",
      source_record_ids: ["goal-b"],
    },
  ],
  summaries: [
    {
      currency: "USD",
      inflow: "300000.00",
      outflow: "180000.00",
      net_exposure: "120000.00",
      source_count: 2,
    },
  ],
  route: {
    ...retirementRoute,
    need: "cross_border",
    specialist_type: "cross_border_specialist",
    reason: "外币资产与未来教育责任需要核对。",
  },
  detection_notes: ["金额保持原币种。"],
  boundary: "本页只识别币种暴露和责任匹配需要，不提供法律、税务或外汇交易建议。",
} satisfies CurrencyExposureResponse;

export const familySpecializedFixture = {
  trust: {
    meta,
    need_detected: true,
    outcome: "EXPERT_REVIEW_REQUIRED",
    needs: [
      {
        id: "need-minor",
        need_type: "minor_beneficiary",
        beneficiaries: [{ member_id: "child-c", age: 12 }],
        assets_in_scope: [{ asset_id: "asset-c" }],
        enterprise_in_scope: [],
        urgency: "high",
        complexity: "medium",
        professional_review_required: true,
        evidence: { minor_member_ids: ["child-c"] },
      },
    ],
    routes: [
      {
        ...retirementRoute,
        need: "minor_beneficiary",
        specialist_type: "trust_specialist",
        reason: "家庭受益人与照护安排达到专业复核复杂度门。",
      },
    ],
    boundary: "系统只识别家庭安排的复杂度和资料缺口，不输出遗嘱或信托设立结论。",
  },
  philanthropy: {
    meta,
    has_explicit_goal: true,
    goals: [
      {
        id: "goal-philanthropy",
        annual_budget: "180000.00",
        target_cause: "乡村青少年金融教育",
        funding_asset: null,
        time_horizon: "ongoing",
        family_participation: "家庭成员共同参与年度复盘",
        governance_preference: "预算与受益结果分开复核",
        professional_review_required: true,
      },
    ],
    route: {
      ...retirementRoute,
      need: "philanthropy",
      specialist_type: "philanthropy_specialist",
      reason: "公益预算达到专业复核门槛。",
    },
    boundary: "公益目标作为家庭需要进入规划，不与产品销售绑定。",
  },
} satisfies FamilySpecializedResponse;

export const emptyFamilySpecializedFixture = {
  trust: {
    ...familySpecializedFixture.trust,
    need_detected: false,
    outcome: "NO_NEED_DETECTED",
    needs: [],
    routes: [],
  },
  philanthropy: {
    ...familySpecializedFixture.philanthropy,
    has_explicit_goal: false,
    goals: [],
    route: {
      ...familySpecializedFixture.philanthropy.route,
      complexity: "none",
      complexity_gate_passed: false,
      specialist_type: null,
      referral_id: null,
      referral_status: null,
      advisor_workflow_status: "not_required",
    },
  },
} satisfies FamilySpecializedResponse;
