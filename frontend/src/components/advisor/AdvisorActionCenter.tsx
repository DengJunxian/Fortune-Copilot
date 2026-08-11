import {
  BellSimpleRingingIcon,
  CalendarCheckIcon,
  CaretDownIcon,
  CheckCircleIcon,
  ClockCounterClockwiseIcon,
  ShieldWarningIcon,
  StethoscopeIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { demoActor } from "../../api/actor";
import {
  fetchAdvisorActionCenter,
  type AdvisorActionCenterItem,
  type AdvisorActionCenterResponse,
} from "../../api/monitoring";
import { fetchWealthTwin, type WealthTwinResponse } from "../../api/persistentTwin";
import { fetchAdvisorHouseholds, type AdvisorHouseholdSummary } from "../../api/reviewWorkflow";
import { formatDate, formatDomainLabel, formatMoney } from "../../utils/format";
import { Button } from "../ui/Button";

interface ActionGroup {
  code: "critical" | "today" | "week" | "no_action" | "specialist";
  title: string;
  description: string;
  icon: typeof WarningCircleIcon;
  items: AdvisorActionCenterItem[];
}

function dayNumber(value: string): number {
  return Math.floor(new Date(`${value}T00:00:00`).getTime() / 86_400_000);
}

function groupActions(items: AdvisorActionCenterItem[], today: string): ActionGroup[] {
  const todayNumber = dayNumber(today);
  const assigned = new Set<string>();
  const take = (predicate: (item: AdvisorActionCenterItem) => boolean) => items.filter((item) => {
    if (assigned.has(item.trigger_id) || !predicate(item)) return false;
    assigned.add(item.trigger_id);
    return true;
  });
  const critical = take((item) => item.urgency === "critical");
  const todayItems = take((item) => Boolean(item.follow_up_due) && dayNumber(item.follow_up_due!) <= todayNumber);
  const specialist = take((item) => Boolean(item.required_specialist));
  const week = take((item) => !item.follow_up_due || dayNumber(item.follow_up_due) <= todayNumber + 7);
  week.push(...take(() => true));
  return [
    { code: "critical", title: "Critical", description: "家庭安全边界已触发，需要优先核对。", icon: ShieldWarningIcon, items: critical },
    { code: "today", title: "Today", description: "今天到期或已经逾期的跟进。", icon: BellSimpleRingingIcon, items: todayItems },
    { code: "week", title: "This Week", description: "本周需要纳入沟通计划的事项，保留实际截止日。", icon: CalendarCheckIcon, items: week },
    { code: "specialist", title: "Specialist Routing", description: "需要养老、保障、跨境、信托或法税专家承接。", icon: StethoscopeIcon, items: specialist },
  ];
}

export function AdvisorActionCenter({ compact = false }: { compact?: boolean }) {
  const [center, setCenter] = useState<AdvisorActionCenterResponse | null>(null);
  const [households, setHouseholds] = useState<AdvisorHouseholdSummary[]>([]);
  const [selected, setSelected] = useState<AdvisorActionCenterItem | null>(null);
  const [twin, setTwin] = useState<WealthTwinResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (options: { force?: boolean; signal?: AbortSignal } = {}) => {
    if (options.force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const [centerResult, householdResult] = await Promise.allSettled([
        fetchAdvisorActionCenter(options.signal),
        fetchAdvisorHouseholds(demoActor("advisor"), options.signal),
      ] as const);
      if (options.signal?.aborted) return;
      if (centerResult.status === "rejected") throw centerResult.reason;
      setCenter(centerResult.value);
      setHouseholds(householdResult.status === "fulfilled" ? householdResult.value.items : []);
      setSelected((current) => current
        ? centerResult.value.items.find((item) => item.trigger_id === current.trigger_id) ?? null
        : null);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError(loadError instanceof Error ? loadError.message : "顾问行动中心加载失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load({ signal: controller.signal });
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!selected) {
      setTwin(null);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    setTwin(null);
    fetchWealthTwin(selected.household_id, controller.signal)
      .then(setTwin)
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setTwin(null);
      })
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [selected]);

  const today = new Date().toISOString().slice(0, 10);
  const groups = useMemo(() => groupActions(center?.items ?? [], today), [center?.items, today]);
  const activeHouseholdIds = new Set(center?.items.map((item) => item.household_id) ?? []);
  const noActionHouseholds = households.filter((item) => !activeHouseholdIds.has(item.household_id));

  if (loading) {
    return <section className="action-center-state" role="status" aria-live="polite"><span className="loading-mark" aria-hidden="true" /><div><h2>正在整理客户行动队列</h2><p>按紧急度、到期日和专业路由核对已触发事项。</p></div></section>;
  }
  if (error || !center) {
    return <section className="action-center-state action-center-state-error" role="alert"><WarningCircleIcon size={27} weight="duotone" aria-hidden="true" /><div><h2>行动中心暂时无法读取</h2><p>{error ?? "服务没有返回行动队列。"}</p></div><Button type="button" variant="secondary" onClick={() => void load()}>重新连接</Button></section>;
  }

  return (
    <section className={`advisor-action-center ${compact ? "advisor-action-center-compact" : ""}`.trim()} aria-labelledby="action-center-title">
      <header className="action-center-header">
        <div>
          <p className="page-kicker">Trigger → evidence → conversation</p>
          <h2 id="action-center-title">Action Center</h2>
          <p>先处理家庭变化和安全边界，再决定是否需要方案更新；这里不会直接发出销售指令。</p>
        </div>
        <div className="action-center-stats" aria-label="行动中心统计">
          <span><strong>{center.open_count}</strong> 待跟进</span>
          <span data-overdue={center.overdue_count > 0}><strong>{center.overdue_count}</strong> 已逾期</span>
          <Button type="button" variant="secondary" loading={refreshing} onClick={() => void load({ force: true })}><ClockCounterClockwiseIcon size={17} aria-hidden="true" /> 刷新</Button>
        </div>
      </header>

      <div className="action-center-groups">
        {groups.map((group) => {
          const Icon = group.icon;
          return (
            <section key={group.code} className="action-center-group" data-group={group.code} data-expanded={group.items.some((item) => item.trigger_id === selected?.trigger_id)} aria-labelledby={`action-group-${group.code}`}>
              <header><Icon size={22} weight="duotone" aria-hidden="true" /><div><h3 id={`action-group-${group.code}`}>{group.title}</h3><p>{group.description}</p></div><strong>{group.items.length}</strong></header>
              {group.items.length > 0 ? (
                <ul>
                  {group.items.map((item) => (
                    <li key={item.trigger_id}>
                      <button type="button" aria-expanded={selected?.trigger_id === item.trigger_id} onClick={() => setSelected(selected?.trigger_id === item.trigger_id ? null : item)}>
                        <span className="action-urgency" data-urgency={item.urgency}>{formatDomainLabel(item.urgency)}</span>
                        <span><strong>{item.household_name}</strong><small>{item.title ?? formatDomainLabel(item.trigger_type)}</small></span>
                        <span className="action-due">{item.follow_up_due ? formatDate(item.follow_up_due) : "持续跟进"}</span>
                        <CaretDownIcon size={17} aria-hidden="true" />
                      </button>
                      {selected?.trigger_id === item.trigger_id ? <ActionDetail item={item} twin={twin} loading={detailLoading} /> : null}
                    </li>
                  ))}
                </ul>
              ) : <p className="action-group-empty">当前没有这一组的待办。</p>}
            </section>
          );
        })}

        <section className="action-center-group" data-group="no_action" aria-labelledby="action-group-no-action">
          <header><CheckCircleIcon size={22} weight="duotone" aria-hidden="true" /><div><h3 id="action-group-no-action">No Action Required</h3><p>当前没有开放触发项的家庭，继续按既定节奏观察。</p></div><strong>{noActionHouseholds.length}</strong></header>
          {noActionHouseholds.length > 0 ? <ul className="no-action-households">{noActionHouseholds.map((household) => <li key={household.household_id}><CheckCircleIcon size={17} weight="fill" aria-hidden="true" /><span><strong>{household.household_name}</strong><small>{household.household_code} · 暂无需新行动</small></span></li>)}</ul> : <p className="action-group-empty">当前客户均有开放跟进事项。</p>}
        </section>
      </div>
      <p className="action-center-boundary">{center.boundary}</p>
    </section>
  );
}

function ActionDetail({ item, twin, loading }: { item: AdvisorActionCenterItem; twin: WealthTwinResponse | null; loading: boolean }) {
  const facts = twin?.comparison.changed_facts ?? [];
  const needs = twin?.comparison.changed_needs ?? [];
  const evidenceEntries = Object.entries(item.evidence).slice(0, 6);
  return (
    <div className="action-detail" role="region" aria-label={`${item.household_name}行动证据`}>
      <section><h4>Trigger</h4><p>{item.reason}</p><span>{formatDomainLabel(item.trigger_type)} · {formatDomainLabel(item.urgency)}</span></section>
      <section><h4>Changed Facts</h4>{loading ? <p>正在核对最新快照…</p> : facts.length > 0 ? <ul>{facts.map((fact) => <li key={fact.code}><strong>{fact.label}</strong><span>{fact.before ?? "—"} → {fact.after ?? "—"}</span></li>)}</ul> : <p>本次触发没有形成新的事实差异，需在沟通中再次确认。</p>}</section>
      <section><h4>Changed Needs</h4>{needs.length > 0 ? <ul>{needs.map((need) => <li key={`${need.need_type}-${need.change_type}`}><strong>{formatDomainLabel(need.need_type)}</strong><span>{formatDomainLabel(need.change_type)}</span></li>)}</ul> : <p>当前需求种类和目标金额没有记录到变化。</p>}</section>
      <section><h4>Changed CFS</h4>{twin?.comparison.changed_cfs.changed ? <p>{twin.comparison.changed_cfs.after.explanation}</p> : <p>当前 CFS 未变化；先核对触发事实，不自动改方案。</p>}</section>
      <section className="action-detail-evidence"><h4>Evidence</h4>{evidenceEntries.length > 0 ? <dl>{evidenceEntries.map(([key, value]) => <div key={key}><dt>{formatDomainLabel(key)}</dt><dd>{evidenceValue(value)}</dd></div>)}</dl> : <p>触发记录未附加扩展证据。</p>}</section>
      <section className="action-conversation"><h4>Recommended Conversation</h4><ol><li>先说明：{item.reason}</li><li>请客户确认近期事实是否准确，以及对家庭的实际影响。</li><li>再讨论：{(item.title ?? "是否需要重新核对当前规划").replace(/[。！？!?]+$/, "")}。</li><li>{item.do_not_sell_flag ? "本次沟通只核对事实和规划，不进行产品销售。" : "如需产品讨论，先完成适当性与人工复核。"}</li></ol>{item.required_specialist ? <p>建议协同：{formatDomainLabel(item.required_specialist)}</p> : null}</section>
    </div>
  );
}

function evidenceValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value && typeof value === "object") {
    const amount = (value as Record<string, unknown>).amount;
    if (typeof amount === "string" && Number.isFinite(Number(amount))) return formatMoney(amount, true);
    return Object.keys(value as Record<string, unknown>).slice(0, 4).join("、") || "已记录";
  }
  return "—";
}
