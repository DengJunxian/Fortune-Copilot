import {
  ArrowDownRightIcon,
  ArrowUpRightIcon,
  ClockCounterClockwiseIcon,
  WalletIcon,
} from "@phosphor-icons/react";
import type { HouseholdSnapshot } from "../../api/persistentTwin";
import { formatDate, formatDomainLabel, formatMoney } from "../../utils/format";

export function TwinStateOverview({ snapshot }: { snapshot: HouseholdSnapshot }) {
  const { facts, profile, liability, risk_budget: riskBudget } = snapshot.state;
  const cashflowDelta = Number(facts.annual_income) - Number(facts.annual_expenses);
  const metrics = [
    ["家庭净资产", facts.net_worth, "资产减全部负债"],
    ["年度收入", facts.annual_income, `${facts.incomes.length} 项收入来源`],
    ["年度收支差", String(cashflowDelta), cashflowDelta >= 0 ? "当前年度有结余" : "当前年度存在缺口"],
    ["长期可配置资本", riskBudget.eligible_long_term_capital, riskBudget.formally_eligible ? "安全门已通过" : "先修复前置责任"],
  ] as const;
  return (
    <section className="twin-current-state" aria-labelledby="twin-current-state-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Current state</p>
          <h2 id="twin-current-state-title">当前家庭状态</h2>
        </div>
        <p>快照 #{snapshot.event_cursor} · {formatDate(snapshot.snapshot_date)}，所有金额来自已确认事实与确定性重算。</p>
      </header>
      <div className="twin-metric-ledger">
        {metrics.map(([label, value, note], index) => (
          <article key={label}>
            <span>{String(index + 1).padStart(2, "0")} · {label}</span>
            <strong>{formatMoney(value)}</strong>
            <small>{note}</small>
          </article>
        ))}
      </div>
      <div className="twin-state-band">
        <div>
          <WalletIcon size={22} weight="duotone" aria-hidden="true" />
          <span>画像版本</span>
          <strong>V{profile.profile_version ?? "—"} · {formatDomainLabel(profile.lifecycle_stage ?? "")}</strong>
        </div>
        <div>
          {cashflowDelta >= 0
            ? <ArrowUpRightIcon size={22} weight="duotone" aria-hidden="true" />
            : <ArrowDownRightIcon size={22} weight="duotone" aria-hidden="true" />}
          <span>风险预算</span>
          <strong>{formatDomainLabel(profile.risk_capacity ?? "")} / {formatDomainLabel(profile.behavior_limit ?? "")}</strong>
        </div>
        <div>
          <ClockCounterClockwiseIcon size={22} weight="duotone" aria-hidden="true" />
          <span>未来责任</span>
          <strong>{liability.stream_count} 项 · 缺口 {formatMoney(liability.funding_gap, true)}</strong>
        </div>
      </div>
    </section>
  );
}
