import { CalendarDotsIcon, FlagPennantIcon } from "@phosphor-icons/react";
import type { LiabilityCalendarEntry } from "../../api/liability";
import { formatDate, formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";

export function GoalTimeline({ entries }: { entries: LiabilityCalendarEntry[] }) {
  const ordered = [...entries].sort((left, right) =>
    left.stream.start_date.localeCompare(right.stream.start_date));
  return (
    <section className="goal-stream-timeline" aria-labelledby="goal-stream-timeline-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">责任时间轴</p>
          <h2 id="goal-stream-timeline-title">目标不再只是终点金额</h2>
        </div>
        <p>教育、医疗、养老等责任按真实到期节奏展开，原目标记录仍保留为来源证据。</p>
      </header>
      <ol>
        {ordered.map((entry) => (
          <li key={entry.stream.id} data-rigidity={entry.stream.rigidity}>
            <span className="goal-stream-marker" aria-hidden="true">
              <FlagPennantIcon size={17} weight="fill" />
            </span>
            <time dateTime={entry.stream.start_date}>
              {new Date(`${entry.stream.start_date}T00:00:00`).getFullYear()}
            </time>
            <article>
              <div>
                <span>{formatDomainLabel(entry.stream.stream_type)}</span>
                <span>{formatDomainLabel(entry.stream.rigidity)}</span>
                {entry.stream.deferrable ? <span>可协商延期</span> : <span>不可延期</span>}
              </div>
              <h3>{entry.stream.name}</h3>
              <p>
                <CalendarDotsIcon size={16} aria-hidden="true" />
                {formatDate(entry.stream.start_date)}
                {entry.stream.end_date && entry.stream.end_date !== entry.stream.start_date
                  ? ` 至 ${formatDate(entry.stream.end_date)}`
                  : " 到期"}
                · {entry.cashflows.length} 笔现金流
              </p>
              <dl>
                <div><dt>目标合计</dt><dd>{formatMoney(entry.target_total, true)}</dd></div>
                <div><dt>成本增长</dt><dd>{formatRatio(entry.stream.annual_growth_assumption)}</dd></div>
              </dl>
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}
