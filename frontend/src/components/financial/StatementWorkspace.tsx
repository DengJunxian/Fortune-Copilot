import { useState } from "react";
import type { FinancialStatements } from "../../api/financial";
import { formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";

interface StatementWorkspaceProps {
  statements: FinancialStatements;
  initialTab?: StatementKey;
  showTabs?: boolean;
}

type StatementKey = "balance" | "cashflow" | "insurance" | "goals" | "liquidity";

const tabs: Array<{ key: StatementKey; label: string }> = [
  { key: "balance", label: "资产负债表" },
  { key: "cashflow", label: "收支表" },
  { key: "insurance", label: "保障表" },
  { key: "goals", label: "目标资金表" },
  { key: "liquidity", label: "流动性矩阵" },
];

export function StatementWorkspace({
  statements,
  initialTab = "balance",
  showTabs = true,
}: StatementWorkspaceProps) {
  const [active, setActive] = useState<StatementKey>(initialTab);
  return (
    <section className="statement-workspace" aria-labelledby="statements-heading">
      <header className="section-header-row">
        <div>
          <p className="section-index">02 / 核算底稿</p>
          <h2 id="statements-heading">先看五张表，再看比率</h2>
        </div>
        <p>所有指标均由这些底表的确定性字段计算。</p>
      </header>
      {showTabs ? (
        <div className="tab-list" role="tablist" aria-label="家庭财务底表">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={active === tab.key}
              aria-controls={`statement-${tab.key}`}
              id={`tab-${tab.key}`}
              onClick={() => setActive(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      ) : null}
      <div
        role={showTabs ? "tabpanel" : "region"}
        id={`statement-${active}`}
        aria-labelledby={showTabs ? `tab-${active}` : "statements-heading"}
        tabIndex={0}
      >
        {active === "balance" ? <BalanceStatement statements={statements} /> : null}
        {active === "cashflow" ? <CashFlowStatement statements={statements} /> : null}
        {active === "insurance" ? <InsuranceStatement statements={statements} /> : null}
        {active === "goals" ? <GoalStatement statements={statements} /> : null}
        {active === "liquidity" ? <LiquidityStatement statements={statements} /> : null}
      </div>
    </section>
  );
}

function BalanceStatement({ statements }: StatementWorkspaceProps) {
  const balance = statements.balance_sheet;
  return (
    <div className="statement-stack">
      <p className="statement-identity">核算恒等式：{balance.accounting_identity}</p>
      <div className="data-table-wrap">
        <table className="data-table">
          <caption>资产明细</caption>
          <thead><tr><th>资产</th><th>类别</th><th>流动性</th><th>估值日期</th><th>市值</th></tr></thead>
          <tbody>
            {balance.assets.map((asset) => (
              <tr key={asset.id}><td>{asset.name}</td><td>{formatDomainLabel(asset.category)}</td><td>{asset.liquidity_days} 天</td><td>{asset.valuation_date ?? "待补"}</td><td className="numeric-cell">{formatMoney(asset.market_value)}</td></tr>
            ))}
          </tbody>
          <tfoot><tr><th colSpan={4}>资产合计</th><td className="numeric-cell">{formatMoney(balance.total_assets)}</td></tr></tfoot>
        </table>
      </div>
      <div className="data-table-wrap">
        <table className="data-table">
          <caption>负债明细</caption>
          <thead><tr><th>负债</th><th>类别</th><th>年利率</th><th>未来 12 月偿付</th><th>余额</th></tr></thead>
          <tbody>
            {balance.liabilities.map((liability) => (
              <tr key={liability.id}><td>{liability.name}</td><td>{formatDomainLabel(liability.category)}</td><td>{formatRatio(liability.annual_interest_rate)}</td><td className="numeric-cell">{formatMoney(liability.scheduled_twelve_month_payment)}</td><td className="numeric-cell">{formatMoney(liability.outstanding_balance)}</td></tr>
            ))}
          </tbody>
          <tfoot><tr><th colSpan={4}>负债合计 / 净资产</th><td className="numeric-cell">{formatMoney(balance.total_liabilities)} / {formatMoney(balance.net_worth)}</td></tr></tfoot>
        </table>
      </div>
    </div>
  );
}

function CashFlowStatement({ statements }: StatementWorkspaceProps) {
  const cashflow = statements.cash_flow;
  return (
    <div className="statement-stack">
      <div className="statement-totals" aria-label="年度收支汇总">
        <span>年收入<strong>{formatMoney(cashflow.annual_income)}</strong></span>
        <span>年支出<strong>{formatMoney(cashflow.annual_expenses)}</strong></span>
        <span>年结余<strong>{formatMoney(cashflow.annual_surplus)}</strong></span>
      </div>
      <div className="data-table-wrap">
        <table className="data-table">
          <caption>收入与支出明细（均已年化）</caption>
          <thead><tr><th>项目</th><th>类型</th><th>频率</th><th>必要性</th><th>年化金额</th></tr></thead>
          <tbody>
            {cashflow.income_lines.map((line) => <tr key={`income-${line.id}`}><td>{line.name}</td><td>收入 / {formatDomainLabel(line.category)}</td><td>{formatDomainLabel(line.frequency)}</td><td>—</td><td className="numeric-cell">{formatMoney(line.annual_amount)}</td></tr>)}
            {cashflow.expense_lines.map((line) => <tr key={`expense-${line.id}`}><td>{line.name}</td><td>支出 / {formatDomainLabel(line.category)}</td><td>{formatDomainLabel(line.frequency)}</td><td>{line.essential ? "必要" : "可调整"}</td><td className="numeric-cell">{formatMoney(line.annual_amount)}</td></tr>)}
          </tbody>
        </table>
      </div>
      <p className="statement-note">基本生活支出 {formatMoney(cashflow.annual_basic_living_expenses)}；固定支出 {formatMoney(cashflow.annual_fixed_expenses)}；债务偿付 {formatMoney(cashflow.annual_debt_service)}。三者定义独立，避免重复解释。</p>
    </div>
  );
}

function InsuranceStatement({ statements }: StatementWorkspaceProps) {
  const insurance = statements.insurance;
  return (
    <div className="statement-stack">
      <p className="statement-note">{insurance.counting_note}</p>
      <div className="data-table-wrap">
        <table className="data-table">
          <caption>家庭保障明细</caption>
          <thead><tr><th>保单</th><th>被保险人</th><th>险种</th><th>保障额度</th><th>年保费</th><th>有效</th></tr></thead>
          <tbody>{insurance.policies.map((policy) => <tr key={policy.id}><td>{policy.name}</td><td>{policy.insured_member_name}</td><td>{formatDomainLabel(policy.policy_type)}</td><td className="numeric-cell">{formatMoney(policy.coverage_amount)}</td><td className="numeric-cell">{formatMoney(policy.annual_premium)}</td><td>{policy.active_on_analysis_date ? "是" : "否"}</td></tr>)}</tbody>
          <tfoot><tr><th colSpan={4}>年保费合计</th><td className="numeric-cell">{formatMoney(insurance.total_annual_premium)}</td><td /></tr></tfoot>
        </table>
      </div>
    </div>
  );
}

function GoalStatement({ statements }: StatementWorkspaceProps) {
  const goals = statements.goal_funding;
  return (
    <div className="statement-stack">
      <div className="data-table-wrap">
        <table className="data-table">
          <caption>目标资金准备情况</caption>
          <thead><tr><th>目标</th><th>日期</th><th>刚性</th><th>目标金额</th><th>已准备</th><th>缺口</th></tr></thead>
          <tbody>{goals.goals.map((goal) => <tr key={goal.id}><td>{goal.name}<small>成本增速 {formatRatio(goal.annual_cost_growth_rate)}</small></td><td>{goal.target_date}</td><td>{formatDomainLabel(goal.rigidity)}</td><td className="numeric-cell">{formatMoney(goal.target_amount)}</td><td className="numeric-cell">{formatMoney(goal.prepared_amount)}</td><td className="numeric-cell">{formatMoney(goal.funding_gap)}</td></tr>)}</tbody>
          <tfoot><tr><th colSpan={3}>合计</th><td className="numeric-cell">{formatMoney(goals.total_target_amount)}</td><td className="numeric-cell">{formatMoney(goals.total_prepared_amount)}</td><td className="numeric-cell">{formatMoney(goals.total_funding_gap)}</td></tr></tfoot>
        </table>
      </div>
    </div>
  );
}

function LiquidityStatement({ statements }: StatementWorkspaceProps) {
  const liquidity = statements.liquidity;
  return (
    <div className="statement-stack">
      <div className="statement-totals" aria-label="流动性汇总">
        <span>应急资产<strong>{formatMoney(liquidity.emergency_liquid_assets)}</strong></span>
        <span>短期资产<strong>{formatMoney(liquidity.short_term_liquid_assets)}</strong></span>
        <span>12 月内可用<strong>{formatMoney(liquidity.twelve_month_liquid_assets)}</strong></span>
      </div>
      <div className="data-table-wrap">
        <table className="data-table">
          <caption>资产流动性矩阵</caption>
          <thead><tr><th>资产</th><th>类别</th><th>变现天数</th><th>层级</th><th>计入应急</th><th>市值</th></tr></thead>
          <tbody>{liquidity.lines.map((line) => <tr key={line.asset_id}><td>{line.name}</td><td>{formatDomainLabel(line.category)}</td><td>{line.liquidity_days}</td><td>{formatDomainLabel(line.liquidity_tier)}</td><td>{line.included_in_emergency_reserve ? "是" : "否"}</td><td className="numeric-cell">{formatMoney(line.market_value)}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
