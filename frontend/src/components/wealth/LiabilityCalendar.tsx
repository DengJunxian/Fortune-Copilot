import type { LiabilityCalendarEntry } from "../../api/liability";
import { formatDate, formatMoney } from "../../utils/format";

interface CalendarRow {
  id: string;
  streamName: string;
  dueDate: string;
  sequence: number;
  count: number;
  target: string;
  minimum: string;
  rigidity: string;
}

export function LiabilityCalendar({ entries }: { entries: LiabilityCalendarEntry[] }) {
  const rows = entries.flatMap((entry) => entry.cashflows.map((cashflow) => ({
    id: cashflow.id,
    streamName: entry.stream.name,
    dueDate: cashflow.due_date,
    sequence: cashflow.sequence,
    count: entry.cashflows.length,
    target: cashflow.target_amount,
    minimum: cashflow.minimum_amount,
    rigidity: entry.stream.rigidity,
  } satisfies CalendarRow))).sort((left, right) => left.dueDate.localeCompare(right.dueDate));
  return (
    <section className="liability-calendar" aria-labelledby="liability-calendar-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">到期日历</p>
          <h2 id="liability-calendar-title">每一笔责任何时需要资金</h2>
        </div>
        <p>最低金额与目标金额分列；序号来自版本化现金流引擎。</p>
      </header>
      <div className="liability-calendar-table" role="region" aria-label="负债现金流日历" tabIndex={0}>
        <table>
          <thead>
            <tr><th>到期日</th><th>责任</th><th>期次</th><th>最低金额</th><th>目标金额</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-rigidity={row.rigidity}>
                <td><time dateTime={row.dueDate}>{formatDate(row.dueDate)}</time></td>
                <td>{row.streamName}</td>
                <td>第 {row.sequence} / {row.count} 期</td>
                <td>{formatMoney(row.minimum)}</td>
                <td><strong>{formatMoney(row.target)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
