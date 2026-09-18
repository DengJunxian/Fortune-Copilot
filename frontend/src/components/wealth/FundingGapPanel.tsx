import { ArrowRightIcon } from "@phosphor-icons/react";
import type { LiabilityCalendarResponse } from "../../api/liability";
import { formatMoney } from "../../utils/format";

export function FundingGapPanel({ calendar }: { calendar: LiabilityCalendarResponse }) {
  return (
    <section className="funding-gap-panel" aria-labelledby="funding-gap-title">
      <header>
        <div>
          <p className="section-eyebrow">资金缺口</p>
          <h2 id="funding-gap-title">先看责任，再决定长期配置</h2>
        </div>
        <div className="funding-gap-equation" aria-label="目标、已准备与资金缺口">
          <span><small>目标责任</small><strong>{formatMoney(calendar.summary.target_total, true)}</strong></span>
          <ArrowRightIcon size={18} aria-hidden="true" />
          <span><small>已有准备</small><strong>{formatMoney(calendar.summary.prepared_total, true)}</strong></span>
          <ArrowRightIcon size={18} aria-hidden="true" />
          <span data-tone="warning"><small>待覆盖</small><strong>{formatMoney(calendar.summary.funding_gap, true)}</strong></span>
        </div>
      </header>
      <ol>
        {calendar.entries.map((entry) => (
          <li key={entry.stream.id}>
            <div><strong>{entry.stream.name}</strong><span>{entry.stream.fallback_action}</span></div>
            <dl>
              <div><dt>已准备</dt><dd>{formatMoney(entry.prepared_amount, true)}</dd></div>
              <div><dt>缺口</dt><dd>{formatMoney(entry.funding_gap, true)}</dd></div>
            </dl>
          </li>
        ))}
      </ol>
    </section>
  );
}
