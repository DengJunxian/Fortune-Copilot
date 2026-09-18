import {
  ArrowRightIcon,
  BellRingingIcon,
  CalendarCheckIcon,
  CheckCircleIcon,
  ClockCounterClockwiseIcon,
  CompassIcon,
  CurrencyCircleDollarIcon,
  HeartbeatIcon,
  ShieldCheckIcon,
  TargetIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchWealthNeeds, type WealthNeedsResponse } from "../api/clientProfile";
import { fetchFinancialAnalysis, fetchHouseholds, type FinancialAnalysis, type HouseholdSummary } from "../api/financial";
import { fetchEligibleCapital, fetchLiabilityCalendar, type EligibleCapitalResponse, type LiabilityCalendarResponse } from "../api/liability";
import {
  fetchMonitoringAlerts,
  fetchNextBestActions,
  monitoringFeatureEnabled,
  type MonitoringAlertsResponse,
  type NextBestActionsResponse,
} from "../api/monitoring";
import { fetchEventTimeline, fetchWealthTwin, type EventTimelineResponse, type WealthTwinResponse } from "../api/persistentTwin";
import { Button } from "../components/ui/Button";
import { DashboardCard, DashboardUnavailable } from "../components/wealth/dashboard/DashboardCard";
import { NeedGraphView } from "../components/wealth/dashboard/NeedGraphView";
import { AppLink } from "../router/Link";
import { formatDate, formatDomainLabel, formatMoney } from "../utils/format";

interface DashboardData {
  analysis: FinancialAnalysis | null;
  needs: WealthNeedsResponse | null;
  liability: LiabilityCalendarResponse | null;
  eligible: EligibleCapitalResponse | null;
  twin: WealthTwinResponse | null;
  timeline: EventTimelineResponse | null;
  alerts: MonitoringAlertsResponse | null;
  actions: NextBestActionsResponse | null;
}

const emptyData: DashboardData = {
  analysis: null,
  needs: null,
  liability: null,
  eligible: null,
  twin: null,
  timeline: null,
  alerts: null,
  actions: null,
};

function requestedCaseCode(): string | null {
  const queryCode = new URLSearchParams(window.location.search).get("case");
  if (queryCode) return queryCode;
  try {
    return window.sessionStorage?.getItem("fortune-copilot:selected-case") ?? null;
  } catch {
    return null;
  }
}

function settledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

export function WealthDashboardPage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHouseholds = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchHouseholds(signal);
      if (items.length === 0) throw new Error("尚无可分析家庭");
      setHouseholds(items);
      const requested = requestedCaseCode();
      const preferred = items.find((item) => item.code === requested)
        ?? items.find((item) => item.code === "DEMO_B")
        ?? items[0];
      if (preferred) setHouseholdId(preferred.id);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError("无法读取家庭清单，请检查服务后重试。");
      setLoading(false);
    }
  }, []);

  const loadDashboard = useCallback(async (
    selectedHouseholdId: string,
    options: { force?: boolean; signal?: AbortSignal } = {},
  ) => {
    if (options.force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    const monitoringAlerts = monitoringFeatureEnabled
      ? fetchMonitoringAlerts(selectedHouseholdId, options.signal)
      : Promise.resolve<MonitoringAlertsResponse | null>(null);
    const nextActions = monitoringFeatureEnabled
      ? fetchNextBestActions(selectedHouseholdId, options.signal)
      : Promise.resolve<NextBestActionsResponse | null>(null);
    try {
      const results = await Promise.allSettled([
        fetchFinancialAnalysis(selectedHouseholdId, options.signal),
        fetchWealthNeeds(selectedHouseholdId, options.signal),
        fetchLiabilityCalendar(selectedHouseholdId, options.signal),
        fetchEligibleCapital(selectedHouseholdId, options.signal),
        fetchWealthTwin(selectedHouseholdId, options.signal),
        fetchEventTimeline(selectedHouseholdId, options.signal),
        monitoringAlerts,
        nextActions,
      ] as const);
      if (options.signal?.aborted) return;
      const nextData: DashboardData = {
        analysis: settledValue(results[0]),
        needs: settledValue(results[1]),
        liability: settledValue(results[2]),
        eligible: settledValue(results[3]),
        twin: settledValue(results[4]),
        timeline: settledValue(results[5]),
        alerts: settledValue(results[6]),
        actions: settledValue(results[7]),
      };
      setData(nextData);
      if (!nextData.analysis && !nextData.liability && !nextData.twin) {
        setError("核心家庭快照暂时无法读取；页面不会用示例值替代。");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadHouseholds(controller.signal);
    return () => controller.abort();
  }, [loadHouseholds]);

  useEffect(() => {
    if (!householdId) return;
    const controller = new AbortController();
    void loadDashboard(householdId, { signal: controller.signal });
    return () => controller.abort();
  }, [householdId, loadDashboard]);

  const selectedHousehold = households.find((item) => item.id === householdId);
  const openAlerts = data.alerts?.alerts.filter((item) => item.status === "open") ?? [];
  const firstAction = data.actions?.actions[0];
  const safetyStatus = data.analysis?.health_assessment.status ?? null;
  const recentChange = data.twin?.comparison.has_material_change ?? false;
  const healthTone = safetyStatus === "healthy" ? "safe" : safetyStatus === "risk" ? "risk" : "watch";
  const priorityText = firstAction?.recommended_action
    ?? data.analysis?.health_assessment.priority_action.detail
    ?? "保持当前安排，并在家庭事实变化后重新核对。";
  const lastEvent = data.timeline?.events[0];
  const metricById = (metricId: string) => data.analysis?.metrics.find(
    (metric) => metric.metric_id === metricId,
  )?.result ?? null;
  const liquidityMonths = metricById("liquidity_reserve_months");
  const debtRatio = metricById("debt_to_asset_ratio");
  const protectionRatio = data.analysis?.protection.coverage_ratio ?? null;
  const goalEntries = [...(data.liability?.entries ?? [])]
    .sort((left, right) => left.stream.start_date.localeCompare(right.stream.start_date))
    .slice(0, 3);
  const nextBestActions = data.actions?.actions.slice(0, 3) ?? [];

  const completeness = useMemo(() => {
    const blocks = [data.analysis, data.needs, data.liability, data.eligible, data.twin];
    return blocks.filter(Boolean).length;
  }, [data]);

  return (
    <main className="page-shell wealth-dashboard-page" id="main-content">
      <header className="wealth-dashboard-hero">
        <div>
          <p className="page-kicker">Family wealth dashboard · current snapshot</p>
          <h1>{selectedHousehold?.name ?? "家庭"}，今天先看最重要的四件事。</h1>
          <p>这里汇总已确认事实与确定性计算；需要深入时，再进入对应专业页面。</p>
        </div>
        <div className="wealth-profile-controls">
          <label htmlFor="dashboard-household-select">当前家庭</label>
          <select id="dashboard-household-select" value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={refreshing || households.length === 0}>
            {households.length === 0 ? <option value="">等待家庭资料</option> : null}
            {households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}
          </select>
          <Button type="button" variant="secondary" loading={refreshing} disabled={!householdId} onClick={() => void loadDashboard(householdId, { force: true })}>
            <ClockCounterClockwiseIcon size={17} aria-hidden="true" /> 核对最新快照
          </Button>
        </div>
      </header>

      {loading ? <DashboardLoading /> : null}
      {!loading && error && completeness === 0 ? <DashboardError message={error} onRetry={() => void loadHouseholds()} /> : null}
      {!loading && completeness > 0 ? (
        <>
          {error ? <p className="dashboard-partial-warning" role="status">{error}</p> : null}
          <section className="dashboard-core-grid" aria-label="家庭财富四项核心回答">
            <article className="dashboard-core-card dashboard-safety-answer" data-tone={healthTone}>
              <header>
                <span><ShieldCheckIcon size={20} weight="duotone" aria-hidden="true" /> 01</span>
                <div><small>家庭安全</small><h2>我家现在安全吗？</h2></div>
              </header>
              <strong>{safetyStatus === "healthy" ? "基础安全" : safetyStatus === "risk" ? "需要优先修复" : "有事项需要关注"}</strong>
              <p>{data.analysis?.health_assessment.priority_action.title ?? "等待完整财务健康结果"}</p>
              <dl className="dashboard-safety-ledger">
                <div><dt>财务健康</dt><dd>{data.analysis ? `${Number(data.analysis.health_assessment.overall_score).toFixed(0)} 分` : "待读取"}</dd></div>
                <div><dt>应急覆盖</dt><dd>{liquidityMonths ? `${Number(liquidityMonths).toFixed(1)} 个月` : "待读取"}</dd></div>
                <div><dt>资产负债率</dt><dd>{debtRatio ? `${(Number(debtRatio) * 100).toFixed(1)}%` : "待读取"}</dd></div>
                <div><dt>保障覆盖</dt><dd>{protectionRatio ? `${(Number(protectionRatio) * 100).toFixed(1)}%` : "待读取"}</dd></div>
              </dl>
              <AppLink to="/wealth/goals">查看安全闸门 <ArrowRightIcon size={16} aria-hidden="true" /></AppLink>
            </article>

            <article className="dashboard-core-card dashboard-goals-answer">
              <header>
                <span><TargetIcon size={20} weight="duotone" aria-hidden="true" /> 02</span>
                <div><small>人生目标</small><h2>我未来有哪些重要目标？</h2></div>
                <strong>{data.liability ? `总缺口 ${formatMoney(data.liability.summary.funding_gap, true)}` : "待读取"}</strong>
              </header>
              {goalEntries.length > 0 ? (
                <ol className="dashboard-goal-timeline">
                  {goalEntries.map((entry) => (
                    <li key={entry.stream.id}>
                      <time dateTime={entry.stream.start_date}>{new Date(`${entry.stream.start_date}T00:00:00`).getFullYear()}</time>
                      <div><strong>{entry.stream.name}</strong><span>{formatDomainLabel(entry.stream.stream_type)} · {entry.stream.deferrable ? "可协商" : "刚性责任"}</span></div>
                      <dl><dt>金额缺口</dt><dd>{formatMoney(entry.funding_gap, true)}</dd></dl>
                    </li>
                  ))}
                </ol>
              ) : <DashboardUnavailable>目标责任时间轴暂时无法读取。</DashboardUnavailable>}
              <AppLink to="/wealth/goals">查看完整目标时间轴 <ArrowRightIcon size={16} aria-hidden="true" /></AppLink>
            </article>

            <article className="dashboard-core-card dashboard-eltc-answer">
              <header>
                <span><CurrencyCircleDollarIcon size={20} weight="duotone" aria-hidden="true" /> 03</span>
                <div><small>资金资格</small><h2>我真正可以长期投资多少钱？</h2></div>
              </header>
              {data.eligible ? (
                <>
                  <div className="dashboard-eltc-outcome" data-eligible={data.eligible.calculation.formally_eligible}>
                    <span>长期可投资资本 ELTC</span>
                    <strong>{formatMoney(data.eligible.calculation.eligible_long_term_capital, true)}</strong>
                    <small>{data.eligible.calculation.formally_eligible ? "可进入长期配置评估" : "前置责任尚未通过，当前先修复而不新增投资"}</small>
                  </div>
                  <ol className="dashboard-eltc-bridge" aria-label="长期可投资资本扣减桥">
                    <li><span>可调度金融资源</span><strong>{formatMoney(data.eligible.calculation.dispatchable_financial_resources, true)}</strong></li>
                    {data.eligible.calculation.bridge.map((step) => (
                      <li key={step.code}><span>{step.label}</span><strong>− {formatMoney(step.deduction, true)}</strong></li>
                    ))}
                  </ol>
                  <details className="dashboard-eltc-explanation">
                    <summary>为什么不是全部金融资产？</summary>
                    <p>日常周转、应急、债务、保障、近期责任、已承诺目标和锁定资金都有明确用途，不能重复用于长期承担市场波动。</p>
                  </details>
                </>
              ) : <DashboardUnavailable>ELTC 结果暂时无法读取。</DashboardUnavailable>}
              <AppLink to="/wealth/goals">查看完整 ELTC Bridge <ArrowRightIcon size={16} aria-hidden="true" /></AppLink>
            </article>

            <article className="dashboard-core-card dashboard-next-actions">
              <header>
                <span><CompassIcon size={20} weight="duotone" aria-hidden="true" /> 04</span>
                <div><small>Next Best Action</small><h2>现在需要做什么？</h2></div>
              </header>
              {nextBestActions.length > 0 ? (
                <ol>
                  {nextBestActions.map((action) => (
                    <li key={action.action_code}>
                      <span>{action.priority}</span>
                      <div><strong>{action.client_impact}</strong><p>{action.recommended_action}</p></div>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="dashboard-next-action-fallback">
                  <CheckCircleIcon size={24} weight="duotone" aria-hidden="true" />
                  <div><strong>按家庭安全顺序安排</strong><p>{priorityText}</p></div>
                </div>
              )}
              <aside>
                <BellRingingIcon size={19} weight="duotone" aria-hidden="true" />
                <p>{recentChange || openAlerts.length > 0 ? "近期变化需要复核当前方案。" : lastEvent ? `${formatDomainLabel(lastEvent.event_type)}已进入事件账本。` : "没有重大变化时，保持当前方案也是正式行动。"}</p>
              </aside>
            </article>
          </section>

          <div className="wealth-dashboard-layout">
            <DashboardCard className="dashboard-needs-card" eyebrow="Need graph" title="最需要先照顾什么" action={<AppLink to="/wealth/goals">完整目标责任</AppLink>}>
              {data.needs ? <NeedGraphView needs={data.needs.needs} priorities={data.needs.priorities} /> : <DashboardUnavailable>财富需要暂时无法读取。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard eyebrow="ELTC" title="可用于长期配置的资本">
              {data.eligible ? (
                <div className="dashboard-capital">
                  <CurrencyCircleDollarIcon size={30} weight="duotone" aria-hidden="true" />
                  <strong>{formatMoney(data.eligible.calculation.eligible_long_term_capital, true)}</strong>
                  <span data-eligible={data.eligible.calculation.formally_eligible}>{data.eligible.calculation.formally_eligible ? "可进入正式配置评估" : "先修复应急、责任或保障缺口"}</span>
                </div>
              ) : <DashboardUnavailable>ELTC 结果暂时无法读取。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard eyebrow="Goals" title="责任现金流">
              {data.liability ? (
                <dl className="dashboard-compact-ledger">
                  <div><dt>责任总额</dt><dd>{formatMoney(data.liability.summary.target_total, true)}</dd></div>
                  <div><dt>已准备</dt><dd>{formatMoney(data.liability.summary.prepared_total, true)}</dd></div>
                  <div><dt>责任现金流</dt><dd>{data.liability.summary.cashflow_count} 笔</dd></div>
                </dl>
              ) : <DashboardUnavailable>责任日历暂时无法读取。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard eyebrow="Risk budget" title="家庭风险预算">
              {data.twin ? (
                <div className="dashboard-risk-budget">
                  <HeartbeatIcon size={27} weight="duotone" aria-hidden="true" />
                  <dl>
                    <div><dt>承受能力</dt><dd>{formatDomainLabel(data.twin.current.state.risk_budget.risk_capacity ?? "待复核")}</dd></div>
                    <div><dt>意愿上限</dt><dd>{formatDomainLabel(data.twin.current.state.risk_budget.risk_willingness ?? "待复核")}</dd></div>
                    <div><dt>行为上限</dt><dd>{formatDomainLabel(data.twin.current.state.risk_budget.behavior_limit ?? "待复核")}</dd></div>
                  </dl>
                </div>
              ) : <DashboardUnavailable>风险预算暂时无法读取。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard eyebrow="CFS status" title="综合方案状态" action={<AppLink to="/wealth/cfs">进入方案</AppLink>}>
              {data.twin ? (
                <div className="dashboard-status-line" data-ready={data.twin.current.state.cfs.status === "available"}>
                  {data.twin.current.state.cfs.status === "available" ? <CheckCircleIcon size={24} weight="fill" aria-hidden="true" /> : <WarningCircleIcon size={24} weight="duotone" aria-hidden="true" />}
                  <div><strong>{data.twin.current.state.cfs.status === "available" ? "方案可用" : "尚未绑定到当前快照"}</strong><span>{data.twin.current.state.cfs.explanation}</span></div>
                </div>
              ) : <DashboardUnavailable>CFS 状态暂时无法读取。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard eyebrow="Recent events" title="最近发生的变化" action={<AppLink to="/wealth/history">查看历史</AppLink>}>
              {lastEvent ? (
                <div className="dashboard-event">
                  <CalendarCheckIcon size={25} weight="duotone" aria-hidden="true" />
                  <div><strong>{formatDomainLabel(lastEvent.event_type)}</strong><span>{formatDate(lastEvent.effective_at.slice(0, 10))} · {formatDomainLabel(lastEvent.confirmation_status)}</span></div>
                </div>
              ) : <DashboardUnavailable>当前没有已确认的家庭变化事件。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard className="dashboard-monitoring-card" eyebrow="Monitoring alerts" title="持续监控提醒">
              {!monitoringFeatureEnabled ? <DashboardUnavailable>当前环境尚未启用持续监控。</DashboardUnavailable> : openAlerts.length > 0 ? (
                <ul className="dashboard-alert-list">
                  {openAlerts.slice(0, 3).map((alert) => (
                    <li key={alert.id} data-severity={alert.severity}>
                      <span>{formatDomainLabel(alert.severity)}</span>
                      <div><strong>{alert.client_impact}</strong><p>{alert.recommended_action}</p></div>
                    </li>
                  ))}
                </ul>
              ) : <DashboardUnavailable>没有需要客户处理的新提醒。</DashboardUnavailable>}
            </DashboardCard>

            <DashboardCard eyebrow="Advisor follow-up" title="顾问下一步">
              {firstAction ? (
                <div className="dashboard-follow-up">
                  <strong>{firstAction.client_impact}</strong>
                  <p>{firstAction.recommended_action}</p>
                  {firstAction.do_not_sell_flag ? <span>本次仅核对事实与规划，不触发销售。</span> : null}
                </div>
              ) : <DashboardUnavailable>当前没有需要顾问跟进的新行动。</DashboardUnavailable>}
            </DashboardCard>
          </div>
        </>
      ) : null}
    </main>
  );
}
function DashboardLoading() {
  return (
    <section className="dashboard-skeleton" role="status" aria-live="polite">
      <span className="loading-mark" aria-hidden="true" />
      <div><h2>正在核对家庭财富全貌</h2><p>同步财务健康、目标责任、风险预算、变化事件与监控提醒。</p></div>
    </section>
  );
}

function DashboardError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="profile-loading profile-loading-error" role="alert">
      <WarningCircleIcon size={28} weight="duotone" aria-hidden="true" />
      <div><h2>家庭财富总览暂时无法读取</h2><p>{message}</p></div>
      <Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button>
    </section>
  );
}
