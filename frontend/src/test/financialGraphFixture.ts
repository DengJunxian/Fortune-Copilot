import type { FinancialGraphResponse, GraphPosition } from "../api/financialGraph";

export const graphPositionFixture: GraphPosition = {
  id: "position-fixture",
  account_id: "account-fixture",
  owner_entity_id: "entity-household",
  legacy_asset_id: "legacy-asset-fixture",
  instrument_type: "time_deposit",
  instrument_code: null,
  name: "三年期定期存款",
  quantity: null,
  acquisition_cost: "80000.00",
  market_value: "80000.00",
  currency: "CNY",
  valuation_date: "2026-08-10",
  purpose_dimension: "stable",
  risk_level: "low",
  liquidity_days: 365,
  complexity_level: "basic",
  principal_loss_possible: false,
  legally_principal_guaranteed: true,
  lock_up: true,
  withdrawable_date: "2029-08-10",
  source_kind: "user_self_report",
  evidence_json: { ownership: "本人" },
  is_user_confirmed: true,
  version: 1,
};

export const financialGraphFixture: FinancialGraphResponse = {
  meta: {
    household_id: "household-fixture",
    data_as_of: "2026-08-10",
    calculation_source: "deterministic_tools",
  },
  entities: [
    {
      id: "entity-household",
      entity_type: "household",
      display_name: "林家庭",
      jurisdiction: "CN",
    },
    {
      id: "entity-person",
      entity_type: "person",
      display_name: "林女士",
      jurisdiction: "CN",
    },
  ],
  accounts: [
    {
      id: "account-fixture",
      owner_entity_id: "entity-household",
      provider_name: "家庭资产汇总账户",
      account_type: "legacy_aggregate",
      account_wrapper: "ordinary",
      currency: "CNY",
    },
  ],
  positions: [graphPositionFixture],
  integrity: { status: "passed", issues: [] },
  projection_diagnostic: {
    status: "matched",
    legacy_asset_total: "80000.00",
    projected_asset_total: "80000.00",
    difference: "0.00",
    details: [],
  },
};
