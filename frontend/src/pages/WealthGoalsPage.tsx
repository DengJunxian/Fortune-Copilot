import {
  ArrowsClockwiseIcon,
  CalendarCheckIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchEligibleCapital,
  fetchLiabilityCalendar,
  type EligibleCapitalResponse,
  type LiabilityCalendarResponse,
} from "../api/liability";
import { fetchHouseholds, type HouseholdSummary } from "../api/financial";
import { EligibleCapitalBridge } from "../components/wealth/EligibleCapitalBridge";
import { FundingGapPanel } from "../components/wealth/FundingGapPanel";
import { GoalTimeline } from "../components/wealth/GoalTimeline";
import { LiabilityCalendar } from "../components/wealth/LiabilityCalendar";
import { Button } from "../components/ui/Button";
import { AppLink } from "../router/Link";
import { formatDate } from "../utils/format";

function requestedCaseCode(): string | null {
  const queryCode = new URLSearchParams(window.location.search).get("case");
  if (queryCode) return queryCode;
  try {
    return window.sessionStorage?.getItem("fortune-copilot:selected-case") ?? null;
  } catch {
    return null;
  }
}

export function WealthGoalsPage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [calendar, setCalendar] = useState<LiabilityCalendarResponse | null>(null);
  const [eligible, setEligible] = useState<EligibleCapitalResponse | null>(null);
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
      setLoading(false);
      setError("无法读取家庭资料，请检查服务后重试。");
    }
  }, []);

  const loadAnalysis = useCallback(async (
    selectedHouseholdId: string,
    options: { force?: boolean; signal?: AbortSignal } = {},
  ) => {
    setError(null);
    if (options.force) setRefreshing(true);
    else setLoading(true);
    try {
      const [calendarPayload, eligiblePayload] = await Promise.all([
        fetchLiabilityCalendar(selectedHouseholdId, options.signal),
        fetchEligibleCapital(selectedHouseholdId, options.signal),
      ]);
      setCalendar(calendarPayload);
      setEligible(eligiblePayload);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setCalendar(null);
      setEligible(null);
      setError(loadError instanceof Error ? loadError.message : "责任分析失败");
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
    void loadAnalysis(householdId, { signal: controller.signal });
    return () => controller.abort();
  }, [householdId, loadAnalysis]);

  const selectedHousehold = households.find((item) => item.id === householdId);
  return (
    <main className="page-shell wealth-goals-page" id="main-content">
      <header className="wealth-goals-hero">
        <div>
          <p className="page-kicker">Liability Stream · ELTC · Purchasing Power V2</p>
          <h1>把未来责任，落到每一笔现金流。</h1>
          <p>
            先展开教育、住房、医疗、养老与家庭责任，再从可调度金融资源逐层扣减，
            得到真正可以进入长期配置的资本。
          </p>
          <AppLink to="/wealth/profile">返回财富画像查看事实来源</AppLink>
        </div>
        <div className="wealth-profile-controls">
          <label htmlFor="goals-household-select">当前家庭</label>
          <select
            id="goals-household-select"
            value={householdId}
            onChange={(event) => setHouseholdId(event.target.value)}
            disabled={households.length === 0 || refreshing}
          >
            {households.length === 0 ? <option value="">等待家庭资料</option> : null}
            {households.map((household) => (
              <option key={household.id} value={household.id}>
                {household.name} · {household.code}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="secondary"
            loading={refreshing}
            disabled={!householdId}
            onClick={() => void loadAnalysis(householdId, { force: true })}
          >
            <ArrowsClockwiseIcon size={17} aria-hidden="true" /> 重新计算责任
          </Button>
        </div>
      </header>

      {loading ? <GoalsLoadingState /> : null}
      {!loading && error ? (
        <GoalsErrorState
          message={error}
          onRetry={() => householdId
            ? void loadAnalysis(householdId)
            : void loadHouseholds()}
        />
      ) : null}
      {!loading && calendar && eligible && calendar.entries.length === 0 ? (
        <section className="goals-empty-state">
          <CalendarCheckIcon size={30} weight="duotone" aria-hidden="true" />
          <div><h2>还没有可展开的目标责任</h2><p>先在家庭规划中录入目标金额与日期，本页不会自行估算责任。</p></div>
        </section>
      ) : null}
      {!loading && calendar && eligible && calendar.entries.length > 0 ? (
        <>
          <section className="goals-meta-strip" aria-label="责任分析元数据">
            <div><span>家庭</span><strong>{selectedHousehold?.name ?? "当前家庭"}</strong></div>
            <div><span>责任 / 现金流</span><strong>{calendar.summary.stream_count} 项 / {calendar.summary.cashflow_count} 笔</strong></div>
            <div><span>下一到期</span><strong>{calendar.summary.next_due_date ? formatDate(calendar.summary.next_due_date) : "暂无"}</strong></div>
            <div><span>规则版本</span><strong>{calendar.meta.rule_version} · {eligible.meta.formula_version}</strong></div>
          </section>
          <GoalTimeline entries={calendar.entries} />
          <LiabilityCalendar entries={calendar.entries} />
          <FundingGapPanel calendar={calendar} />
          <EligibleCapitalBridge result={eligible} />
        </>
      ) : null}
    </main>
  );
}

function GoalsLoadingState() {
  return (
    <section className="profile-loading" role="status" aria-live="polite">
      <CalendarCheckIcon size={29} weight="duotone" aria-hidden="true" />
      <div><h2>正在展开未来责任</h2><p>确定性引擎正在生成到期日历并逐步计算长期可配置资本。</p></div>
    </section>
  );
}

function GoalsErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="profile-loading profile-loading-error" role="alert">
      <WarningCircleIcon size={28} weight="duotone" aria-hidden="true" />
      <div><h2>责任与 ELTC 暂时无法生成</h2><p>{message} 页面不会用固定 30 万或 100 万门槛替代后端结果。</p></div>
      <Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button>
    </section>
  );
}
