import type {
  EventTimelineResponse,
  FinancialEvent,
  HouseholdSnapshot,
  LifeEventResponse,
  SnapshotComparison,
  WealthTwinResponse,
} from "../api/persistentTwin";

const baseState = {
  facts: {
    household_code: "DEMO_B",
    household_name: "成长三口之家",
    members: [
      { id: "member-1", display_name: "陈先生", relationship: "本人" },
      { id: "member-2", display_name: "周女士", relationship: "配偶" },
    ],
    incomes: [
      { id: "income-1", member_id: "member-1", name: "陈先生工资", annual_amount: "240000.00" },
      { id: "income-2", member_id: "member-2", name: "周女士工资", annual_amount: "120000.00" },
    ],
    annual_income: "360000.00",
    annual_expenses: "288000.00",
    total_assets: "2850000.00",
    total_liabilities: "1208000.00",
    net_worth: "1642000.00",
  },
  profile: {
    profile_version: 1,
    lifecycle_stage: "parenting",
    wealth_tier: "affluent",
    service_complexity: "enhanced",
    risk_capacity: "medium" as const,
    risk_willingness: "medium" as const,
    behavior_limit: "medium_low" as const,
    status: "active",
  },
  needs: [
    { id: "need-1", need_type: "education", priority: 3, status: "partially_prepared" as const, target_amount: "800000.00", minimum_amount: "600000.00" },
  ],
  liability: {
    stream_count: 3,
    cashflow_count: 6,
    target_total: "1700000.00",
    prepared_total: "250000.00",
    funding_gap: "1450000.00",
    next_due_date: "2028-09-01",
  },
  risk_budget: {
    risk_capacity: "medium" as const,
    risk_willingness: "medium" as const,
    behavior_limit: "medium_low" as const,
    eligible_long_term_capital: "0.00",
    formally_eligible: false,
    decision: "repair_first" as const,
  },
  cfs: {
    status: "not_enabled" as const,
    score: null,
    explanation: "CFS 方案保存在独立方案账本；当前家庭快照尚未绑定具体 CFS 版本。",
  },
  monitoring: { status: "not_enabled" as const, alerts: [] },
};

export const baselineSnapshot: HouseholdSnapshot = {
  id: "snapshot-0",
  household_id: "household-b",
  parent_snapshot_id: null,
  snapshot_date: "2026-08-10",
  event_cursor: 0,
  financial_graph_version: "graph-v1",
  profile_version: 1,
  need_version: "needs-v1",
  liability_version: "liability-v1",
  input_hash: "input-baseline",
  snapshot_hash: "0123456789abcdef",
  status: "active",
  created_at: "2026-08-10T08:00:00Z",
  state: baseState,
};

export const emptyComparison: SnapshotComparison = {
  from_snapshot_id: null,
  to_snapshot_id: baselineSnapshot.id,
  changed_facts: [],
  changed_needs: [],
  changed_profile: { changed: false, before_version: null, after_version: 1, changed_fields: [] },
  changed_risk_budget: { changed: false, before: null, after: baseState.risk_budget },
  changed_cfs: { changed: false, before: null, after: baseState.cfs },
  has_material_change: false,
};

export const wealthTwinFixture: WealthTwinResponse = {
  meta: {
    household_id: "household-b",
    analysis_date: "2026-08-10",
    snapshot_count: 1,
    event_count: 0,
    calculation_source: "deterministic_tools",
  },
  current: baselineSnapshot,
  previous: null,
  comparison: emptyComparison,
};

export const salaryEvent: FinancialEvent = {
  id: "event-1",
  household_id: "household-b",
  event_domain: "life",
  event_type: "salary_change",
  effective_at: "2026-08-10T00:00:00Z",
  recorded_at: "2026-08-10T09:00:00Z",
  source_kind: "user_confirmed_life_event",
  source_reference: "client-confirmed-life-event",
  confirmation_status: "processed",
  payload: { income_change_ratio: "-0.300000" },
  event_hash: "event-hash-1",
  processed_snapshot_id: "snapshot-1",
  life_event: {
    id: "life-1",
    member_id: null,
    life_event_type: "salary_change",
    event_date: "2026-08-10",
    expected_financial_impact: "-108000.00",
    metadata_json: {},
  },
};

const changedSnapshot: HouseholdSnapshot = {
  ...baselineSnapshot,
  id: "snapshot-1",
  parent_snapshot_id: baselineSnapshot.id,
  event_cursor: 1,
  input_hash: "input-after-event",
  snapshot_hash: "fedcba9876543210",
  state: {
    ...baseState,
    facts: {
      ...baseState.facts,
      incomes: [
        {
          id: "income-1",
          member_id: "member-1",
          name: "陈先生工资",
          annual_amount: "168000.00",
        },
        {
          id: "income-2",
          member_id: "member-2",
          name: "周女士工资",
          annual_amount: "84000.00",
        },
      ],
      annual_income: "252000.00",
    },
  },
};

export const changedComparison: SnapshotComparison = {
  ...emptyComparison,
  from_snapshot_id: baselineSnapshot.id,
  to_snapshot_id: changedSnapshot.id,
  changed_facts: [
    { code: "annual_income", label: "年度收入", before: "360000.00", after: "252000.00", direction: "decreased" },
  ],
  has_material_change: true,
};

export const changedWealthTwinFixture: WealthTwinResponse = {
  meta: { ...wealthTwinFixture.meta, snapshot_count: 2, event_count: 1 },
  current: changedSnapshot,
  previous: {
    id: baselineSnapshot.id,
    snapshot_date: baselineSnapshot.snapshot_date,
    event_cursor: 0,
    snapshot_hash: baselineSnapshot.snapshot_hash,
  },
  comparison: changedComparison,
};

export const emptyTimelineFixture: EventTimelineResponse = {
  household_id: "household-b",
  events: [],
  total: 0,
};

export const changedTimelineFixture: EventTimelineResponse = {
  household_id: "household-b",
  events: [salaryEvent],
  total: 1,
};

export const salaryEventResponseFixture: LifeEventResponse = {
  event: salaryEvent,
  snapshot: changedSnapshot,
  comparison: changedComparison,
  idempotent_replay: false,
};
