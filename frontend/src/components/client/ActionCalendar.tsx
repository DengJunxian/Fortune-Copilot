import { useCallback, useEffect, useMemo, useState } from "react";
import type { ActionCalendarGroup, ClientDeliveryState } from "../../api/clientExperience";
import {
  fetchReportActions,
  updateReportAction,
  type ReportAction,
  type ReportActionList,
  type ReportActionStatus,
} from "../../api/formalReport";
import { usePortalContext } from "../../contexts/PortalContext";
import { formatDate, formatDateTime } from "../../utils/format";
import { Button } from "../ui/Button";
import { MoneyValue } from "../ui/FinancialValue";
import { StatusBadge } from "../ui/StatusBadge";

const statusLabels: Record<ReportActionStatus, string> = {
  open: "待处理",
  completed: "已完成",
  deferred: "已延期",
  not_applicable: "不适用",
};

function defaultDeferredDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  return date.toISOString().slice(0, 10);
}

export function ActionCalendar({
  householdId,
  groups,
  delivery,
}: {
  householdId: string;
  groups: ActionCalendarGroup[];
  delivery: ClientDeliveryState;
}) {
  const { actor } = usePortalContext();
  const [activeCode, setActiveCode] = useState<ActionCalendarGroup["code"]>("immediate");
  const [ledger, setLedger] = useState<ReportActionList | null>(null);
  const [pendingStatus, setPendingStatus] = useState<Record<string, ReportActionStatus>>({});
  const [deferredDates, setDeferredDates] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingCode, setSavingCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadLedger = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    if (delivery.actions === "under_review") {
      setLedger(null);
      setLoading(false);
      return;
    }
    try {
      setLedger(await fetchReportActions(householdId, actor, signal));
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setLedger(null);
      setError("行动状态账本暂不可用；当前列表仍可查看，但不会在浏览器里伪造完成记录。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [actor, delivery.actions, householdId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadLedger(controller.signal);
    return () => controller.abort();
  }, [loadLedger]);

  const active = useMemo(
    () => groups.find((group) => group.code === activeCode) ?? groups[0],
    [groups, activeCode],
  );
  const actionByCode = useMemo(
    () => new Map(ledger?.items.map((item) => [item.action_code, item]) ?? []),
    [ledger],
  );

  if (!active) {
    return <section className="client-inline-state"><h2>行动日历暂无数据</h2><p>保存规划草案后生成行动与复盘任务。</p></section>;
  }

  async function saveStatus(action: ReportAction, nextStatus: ReportActionStatus) {
    const deferredUntil = nextStatus === "deferred"
      ? (deferredDates[action.action_code] ?? defaultDeferredDate())
      : undefined;
    setSavingCode(action.action_code);
    setError(null);
    setNotice(null);
    try {
      const response = await updateReportAction(
        householdId,
        action,
        nextStatus,
        actor,
        deferredUntil,
        `客户在行动日历中将“${action.title}”更新为“${statusLabels[nextStatus]}”`,
      );
      setLedger((current) => current ? {
        ...current,
        report_id: response.report.report_id,
        report_sequence: response.report.sequence,
        metrics: response.metrics,
        items: current.items.map((item) => item.action_code === action.action_code ? response.action : item),
      } : current);
      setPendingStatus((current) => ({ ...current, [action.action_code]: response.action.status }));
      setNotice(`行动状态已保存，并生成正式规划书 R${response.report.sequence} 新快照；旧报告未覆盖。`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "行动状态保存失败。");
    } finally {
      setSavingCode(null);
    }
  }

  const metrics = ledger?.metrics;
  return (
    <section className="action-calendar" aria-labelledby="client-view-heading">
      <header className="client-view-header">
        <div>
          <p className="page-kicker">行动与复盘 · 持久化状态</p>
          <h2 id="client-view-heading" tabIndex={-1}>把建议变成有期限的家庭任务</h2>
          <p>完成、延期和不适用都会写入审计记录并触发正式报告重算；状态变化不代表银行或产品交易已执行。</p>
        </div>
        <div className="action-progress" aria-label="行动执行进度">
          <strong>{metrics ? `${metrics.completed}/${metrics.total}` : "—"}</strong>
          <span>{metrics ? `完成率 ${metrics.completion_ratio}` : "等待正式报告"}</span>
          {ledger?.report_sequence ? <small>当前报告 R{ledger.report_sequence}</small> : null}
        </div>
      </header>

      {loading ? <p className="action-ledger-state" role="status">正在核对行动状态与报告快照…</p> : null}
      {!loading && !ledger?.report_id ? <p className="action-ledger-state" data-tone="warning">{delivery.actions === "under_review" ? "正式报告仍在顾问与合规审核；审核完成前不展示或修改内部行动账本。" : "请先在“家庭规划书”中一键生成正式报告，再记录行动状态。"}</p> : null}
      {notice ? <p className="action-ledger-state" data-tone="success" role="status">{notice}</p> : null}
      {error ? <p className="action-ledger-state" data-tone="danger" role="alert">{error}</p> : null}

      <div className="action-horizon-tabs" role="tablist" aria-label="行动时间范围">
        {groups.map((group) => (
          <button key={group.code} type="button" role="tab" aria-selected={group.code === active.code} onClick={() => setActiveCode(group.code)}>
            {group.label}<span>{group.items.length}</span>
          </button>
        ))}
      </div>
      <article className="action-group" role="tabpanel">
        <header><h3>{active.label}</h3><p>{active.description}</p></header>
        {active.items.length === 0 ? <div className="empty-state"><strong>当前没有这一时间范围的任务</strong><p>家庭事实变化后会由同一规划规则重新生成。</p></div> : (
          <ol>
            {active.items.map((item) => {
              const stored = actionByCode.get(item.code);
              const currentStatus = stored?.status ?? "open";
              const selectedStatus = pendingStatus[item.code] ?? currentStatus;
              const deferredDate = deferredDates[item.code] ?? stored?.deferred_until ?? defaultDeferredDate();
              return (
                <li key={item.code} data-status={currentStatus} data-completed={currentStatus === "completed"}>
                  <span className="action-state-marker" aria-hidden="true">{currentStatus === "completed" ? "✓" : currentStatus === "deferred" ? "↷" : currentStatus === "not_applicable" ? "—" : "○"}</span>
                  <time dateTime={item.due_date ?? undefined}>{item.due_date ? formatDate(item.due_date) : "按条件触发"}</time>
                  <div>
                    <div className="action-title-row"><strong>{item.title}</strong><StatusBadge tone={currentStatus === "completed" ? "success" : currentStatus === "open" ? "warning" : "info"}>{statusLabels[currentStatus]}</StatusBadge></div>
                    <p>{item.detail}</p><small>{item.calculation_source}</small>
                    <details className="action-why">
                      <summary>为什么建议这一步</summary>
                      <dl>
                        <div><dt>家庭数据与原因</dt><dd>{item.why}{item.source_record_ids.length > 0 ? ` · ${item.source_record_ids.length} 条来源记录` : ""}</dd></div>
                        <div><dt>约束／公式</dt><dd><code>{item.constraint_or_formula}</code></dd></div>
                        <div><dt>什么变化会重算</dt><dd>{item.change_trigger}</dd></div>
                        <div><dt>风险与假设</dt><dd>{item.risk_and_assumptions}</dd></div>
                      </dl>
                    </details>
                    <div className="action-state-controls">
                      <label>
                        <span>执行状态</span>
                        <select
                          aria-label={`${item.title}执行状态`}
                          value={selectedStatus}
                          disabled={!stored || savingCode === item.code}
                          onChange={(event) => setPendingStatus((current) => ({ ...current, [item.code]: event.target.value as ReportActionStatus }))}
                        >
                          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </label>
                      {selectedStatus === "deferred" ? (
                        <label>
                          <span>延期至</span>
                          <input aria-label={`${item.title}延期至`} type="date" min={new Date().toISOString().slice(0, 10)} value={deferredDate} onChange={(event) => setDeferredDates((current) => ({ ...current, [item.code]: event.target.value }))} />
                        </label>
                      ) : null}
                      <Button type="button" variant="secondary" loading={savingCode === item.code} disabled={!stored || selectedStatus === currentStatus} onClick={() => stored ? void saveStatus(stored, selectedStatus) : undefined}>保存状态</Button>
                    </div>
                    {stored?.completed_at ? <small>完成记录：{formatDateTime(stored.completed_at)}</small> : null}
                    {stored?.deferred_until ? <small>延期复盘：{formatDate(stored.deferred_until)}</small> : null}
                    {stored?.status_reason ? <small>最近理由：{stored.status_reason}</small> : null}
                  </div>
                  <div className="action-amount">{Number(item.amount) > 0 ? <MoneyValue value={item.amount} label={`${item.title}金额`} /> : <span>先确认</span>}</div>
                </li>
              );
            })}
          </ol>
        )}
      </article>
    </section>
  );
}
