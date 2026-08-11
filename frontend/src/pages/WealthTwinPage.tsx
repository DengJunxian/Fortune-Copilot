import {
  ArrowsClockwiseIcon,
  ClockCounterClockwiseIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { fetchHouseholds, type HouseholdSummary } from "../api/financial";
import {
  createSalaryChange,
  fetchEventTimeline,
  fetchWealthTwin,
  type EventTimelineResponse,
  type WealthTwinResponse,
} from "../api/persistentTwin";
import { LifeEventComposer } from "../components/wealth/LifeEventComposer";
import { TwinChangeLedger } from "../components/wealth/TwinChangeLedger";
import { TwinStateOverview } from "../components/wealth/TwinStateOverview";
import { TwinTimeline } from "../components/wealth/TwinTimeline";
import { ScenarioLab } from "../components/wealth/ScenarioLab";
import { Button } from "../components/ui/Button";
import { AppLink } from "../router/Link";

function requestedCaseCode(): string | null {
  const queryCode = new URLSearchParams(window.location.search).get("case");
  if (queryCode) return queryCode;
  try {
    return window.sessionStorage?.getItem("fortune-copilot:selected-case") ?? null;
  } catch {
    return null;
  }
}

export function WealthTwinPage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [twin, setTwin] = useState<WealthTwinResponse | null>(null);
  const [timeline, setTimeline] = useState<EventTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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
      setLoading(false);
      setError("无法读取家庭资料，请检查服务后重试。");
    }
  }, []);

  const loadTwin = useCallback(async (
    selectedHouseholdId: string,
    options: { force?: boolean; signal?: AbortSignal } = {},
  ) => {
    setError(null);
    setMessage(null);
    if (options.force) setRefreshing(true);
    else setLoading(true);
    try {
      const [twinPayload, timelinePayload] = await Promise.all([
        fetchWealthTwin(selectedHouseholdId, options.signal),
        fetchEventTimeline(selectedHouseholdId, options.signal),
      ]);
      setTwin(twinPayload);
      setTimeline(timelinePayload);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setTwin(null);
      setTimeline(null);
      setError(loadError instanceof Error ? loadError.message : "家庭财富孪生加载失败");
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
    void loadTwin(householdId, { signal: controller.signal });
    return () => controller.abort();
  }, [householdId, loadTwin]);

  async function submitSalaryEvent(input: {
    eventDate: string;
    memberId: string | null;
    ratio: string;
  }) {
    if (!householdId) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await createSalaryChange(householdId, {
        event_date: input.eventDate,
        member_id: input.memberId,
        income_change_ratio: input.ratio,
      });
      const [updatedTwin, updatedTimeline] = await Promise.all([
        fetchWealthTwin(householdId),
        fetchEventTimeline(householdId),
      ]);
      setTwin(updatedTwin);
      setTimeline(updatedTimeline);
      setMessage(result.idempotent_replay
        ? "该事件已经处理过，家庭事实没有再次扣减。"
        : "新快照已生成，画像、需求、责任与 ELTC 已重新计算。");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "事件处理失败");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedHousehold = households.find((item) => item.id === householdId);
  return (
    <main className="page-shell wealth-twin-page" id="main-content">
      <header className="wealth-twin-hero">
        <div>
          <p className="page-kicker">Persistent financial twin · event sourced</p>
          <h1>Scenario Lab：家庭变化发生后，规划也要跟着更新。</h1>
          <p>先选择要核对的生活场景，再决定是否写入已发生事实。这里不是市场预测模型。</p>
          <AppLink to="/wealth/goals">返回目标责任与 ELTC</AppLink>
        </div>
        <div className="wealth-profile-controls">
          <label htmlFor="twin-household-select">当前家庭</label>
          <select id="twin-household-select" value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0 || refreshing || submitting}>
            {households.length === 0 ? <option value="">等待家庭资料</option> : null}
            {households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}
          </select>
          <Button type="button" variant="secondary" loading={refreshing} disabled={!householdId || submitting} onClick={() => void loadTwin(householdId, { force: true })}>
            <ArrowsClockwiseIcon size={17} aria-hidden="true" /> 核对当前状态
          </Button>
        </div>
      </header>

      {loading ? <TwinLoadingState /> : null}
      {!loading && error ? <TwinErrorState message={error} onRetry={() => householdId ? void loadTwin(householdId) : void loadHouseholds()} /> : null}
      {!loading && twin && timeline ? (
        <>
          <section className="twin-meta-strip" aria-label="家庭财富孪生元数据">
            <div><span>家庭</span><strong>{selectedHousehold?.name ?? twin.current.state.facts.household_name}</strong></div>
            <div><span>状态快照</span><strong>{twin.meta.snapshot_count} 个 · 当前 #{twin.current.event_cursor}</strong></div>
            <div><span>已确认事件</span><strong>{twin.meta.event_count} 项</strong></div>
            <div><span>快照校验</span><strong>{twin.current.snapshot_hash.slice(0, 10)}</strong></div>
          </section>
          {message ? <p className="twin-success-message" role="status">{message}</p> : null}
          <TwinStateOverview snapshot={twin.current} />
          <ScenarioLab />
          <LifeEventComposer members={twin.current.state.facts.members} submitting={submitting} onSubmit={submitSalaryEvent} />
          <TwinChangeLedger comparison={twin.comparison} />
          <TwinTimeline events={timeline.events} />
        </>
      ) : null}
    </main>
  );
}

function TwinLoadingState() {
  return <section className="profile-loading" role="status" aria-live="polite"><ClockCounterClockwiseIcon size={29} weight="duotone" aria-hidden="true" /><div><h2>正在建立家庭状态快照</h2><p>系统正在核对事实、画像、需求、责任与长期可配置资本。</p></div></section>;
}

function TwinErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <section className="profile-loading profile-loading-error" role="alert"><WarningCircleIcon size={28} weight="duotone" aria-hidden="true" /><div><h2>家庭财富孪生暂时无法读取</h2><p>{message} 页面不会用模拟值替代缺失快照。</p></div><Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button></section>;
}
