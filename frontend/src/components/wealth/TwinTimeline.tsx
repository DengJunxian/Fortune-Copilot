import { BriefcaseIcon, CheckCircleIcon, TrendDownIcon } from "@phosphor-icons/react";
import type { FinancialEvent } from "../../api/persistentTwin";
import {
  formatDate,
  formatDateTime,
  formatDomainLabel,
  formatMoney,
  formatRatio,
} from "../../utils/format";

export function TwinTimeline({ events }: { events: FinancialEvent[] }) {
  return (
    <section className="twin-timeline-section" aria-labelledby="twin-timeline-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Event timeline</p>
          <h2 id="twin-timeline-title">家庭事件时间线</h2>
        </div>
        <p>事件只应用一次，并保留生效时间、记录时间、财务影响和目标快照。</p>
      </header>
      {events.length === 0 ? (
        <div className="twin-timeline-empty"><CheckCircleIcon size={24} weight="duotone" aria-hidden="true" /><p>还没有已确认事件。当前快照是家庭事实的初始基线。</p></div>
      ) : (
        <ol className="twin-event-list">
          {events.map((event) => {
            if (event.event_domain === "enterprise") {
              const enterpriseName = typeof event.payload.enterprise_name === "string"
                ? event.payload.enterprise_name
                : "关联企业";
              const estimatedValue = typeof event.payload.estimated_value === "string"
                ? event.payload.estimated_value
                : "0";
              return (
                <li key={event.id}>
                  <span className="twin-event-mark twin-event-mark-enterprise"><BriefcaseIcon size={18} weight="bold" aria-hidden="true" /></span>
                  <div className="twin-event-main">
                    <div><strong>{enterpriseName} · {formatDomainLabel(event.event_type)}</strong><span>{formatDate(event.effective_at.slice(0, 10))}</span></div>
                    <p>经济暴露 {formatMoney(estimatedValue)}，已纳入家庭—企业风险预算并生成快照 #{String(event.processed_snapshot_id ?? "").slice(0, 8)}。</p>
                    <small>记录于 {formatDateTime(event.recorded_at)} · {event.confirmation_status === "processed" ? "已重算并留痕" : "处理中"}</small>
                  </div>
                </li>
              );
            }
            if (event.life_event === null) return null;
            const ratio = typeof event.payload.income_change_ratio === "string"
              ? event.payload.income_change_ratio
              : "0";
            return (
              <li key={event.id}>
                <span className="twin-event-mark"><TrendDownIcon size={18} weight="bold" aria-hidden="true" /></span>
                <div className="twin-event-main">
                  <div><strong>工资收入调整 {formatRatio(ratio)}</strong><span>{formatDate(event.life_event.event_date)}</span></div>
                  <p>预计年度影响 {formatMoney(event.life_event.expected_financial_impact)}，已生成快照 #{String(event.processed_snapshot_id ?? "").slice(0, 8)}。</p>
                  <small>记录于 {formatDateTime(event.recorded_at)} · {event.confirmation_status === "processed" ? "已重算并留痕" : "处理中"}</small>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
