import { ClockCounterClockwiseIcon, WarningCircleIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { fetchCFSSolution, type CFSSolutionResponse } from "../api/cfs";
import { fetchHouseholds, type HouseholdSummary } from "../api/financial";
import { fetchEventTimeline, fetchWealthTwin, type EventTimelineResponse, type WealthTwinResponse } from "../api/persistentTwin";
import { Button } from "../components/ui/Button";
import { TwinChangeLedger } from "../components/wealth/TwinChangeLedger";
import { TwinSnapshotReport } from "../components/wealth/TwinSnapshotReport";
import { TwinTimeline } from "../components/wealth/TwinTimeline";
import { AppLink } from "../router/Link";

function storedSolutionId(householdId: string): string | null {
  try {
    return window.sessionStorage?.getItem(`fortune-copilot:cfs-solution:${householdId}`) ?? null;
  } catch {
    return null;
  }
}

export function WealthHistoryPage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [twin, setTwin] = useState<WealthTwinResponse | null>(null);
  const [timeline, setTimeline] = useState<EventTimelineResponse | null>(null);
  const [solution, setSolution] = useState<CFSSolutionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHouseholds = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const items = await fetchHouseholds(signal);
      if (items.length === 0) throw new Error("尚无家庭资料");
      setHouseholds(items);
      const requested = new URLSearchParams(window.location.search).get("case");
      const preferred = items.find((item) => item.code === requested)
        ?? items.find((item) => item.code === "DEMO_B")
        ?? items[0];
      if (preferred) setHouseholdId(preferred.id);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError("无法读取家庭资料，请检查服务后重试。");
      setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async (selectedHouseholdId: string, signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    setSolution(null);
    try {
      const [twinPayload, timelinePayload] = await Promise.all([
        fetchWealthTwin(selectedHouseholdId, signal),
        fetchEventTimeline(selectedHouseholdId, signal),
      ]);
      setTwin(twinPayload);
      setTimeline(timelinePayload);
      const solutionId = storedSolutionId(selectedHouseholdId);
      if (solutionId) {
        fetchCFSSolution(selectedHouseholdId, solutionId, signal).then(setSolution).catch(() => setSolution(null));
      }
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setTwin(null);
      setTimeline(null);
      setError(loadError instanceof Error ? loadError.message : "历史快照加载失败");
    } finally {
      setLoading(false);
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
    void loadHistory(householdId, controller.signal);
    return () => controller.abort();
  }, [householdId, loadHistory]);

  return (
    <main className="page-shell wealth-history-page" id="main-content">
      <header className="wealth-twin-hero wealth-history-hero">
        <div><p className="page-kicker">Snapshot history · report evidence</p><h1>每次家庭变化，都能追溯到对应快照。</h1><p>这里把当前报告版本、前后差异和已确认事件放在同一条证据链上。</p><AppLink to="/wealth">返回家庭财富总览</AppLink></div>
        <div className="wealth-profile-controls"><label htmlFor="history-household-select">当前家庭</label><select id="history-household-select" value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0 || loading}>{households.length === 0 ? <option value="">等待家庭资料</option> : null}{households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}</select><Button type="button" variant="secondary" disabled={!householdId || loading} onClick={() => void loadHistory(householdId)}><ClockCounterClockwiseIcon size={17} aria-hidden="true" /> 重新核对</Button></div>
      </header>
      {loading ? <section className="profile-loading" role="status" aria-live="polite"><ClockCounterClockwiseIcon size={28} weight="duotone" aria-hidden="true" /><div><h2>正在读取快照证据</h2><p>核对家庭状态、版本引用和事件账本。</p></div></section> : null}
      {!loading && error ? <section className="profile-loading profile-loading-error" role="alert"><WarningCircleIcon size={28} weight="duotone" aria-hidden="true" /><div><h2>历史快照暂时无法读取</h2><p>{error}</p></div><Button type="button" variant="secondary" onClick={() => void loadHistory(householdId)}>重新连接</Button></section> : null}
      {!loading && twin && timeline ? <><TwinSnapshotReport twin={twin} solution={solution} /><TwinChangeLedger comparison={twin.comparison} /><TwinTimeline events={timeline.events} /></> : null}
    </main>
  );
}
