import {
  ArrowsClockwiseIcon,
  BriefcaseIcon,
  ClockCounterClockwiseIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchFamilyEnterpriseView,
  type FamilyEnterpriseView,
} from "../api/familyEnterprise";
import { fetchHouseholds, type HouseholdSummary } from "../api/financial";
import { EnterpriseDependencyPanel } from "../components/wealth/EnterpriseDependencyPanel";
import { EnterpriseLiquidityCfs } from "../components/wealth/EnterpriseLiquidityCfs";
import { EnterpriseObligations } from "../components/wealth/EnterpriseObligations";
import { EnterpriseWealthOverview } from "../components/wealth/EnterpriseWealthOverview";
import { Button } from "../components/ui/Button";
import { AppLink } from "../router/Link";
import { formatRatio } from "../utils/format";

function requestedCaseCode(): string | null {
  const queryCode = new URLSearchParams(window.location.search).get("case");
  if (queryCode) return queryCode;
  try {
    return window.sessionStorage?.getItem("fortune-copilot:selected-case") ?? null;
  } catch {
    return null;
  }
}

export function FamilyEnterprisePage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [view, setView] = useState<FamilyEnterpriseView | null>(null);
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

  const loadView = useCallback(async (
    selectedHouseholdId: string,
    options: { force?: boolean; signal?: AbortSignal } = {},
  ) => {
    setError(null);
    if (options.force) setRefreshing(true);
    else setLoading(true);
    try {
      setView(await fetchFamilyEnterpriseView(selectedHouseholdId, options.signal));
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setView(null);
      setError(loadError instanceof Error ? loadError.message : "家企财富视图加载失败");
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
    void loadView(householdId, { signal: controller.signal });
    return () => controller.abort();
  }, [householdId, loadView]);

  const selectedHousehold = households.find((household) => household.id === householdId);
  return (
    <main className="page-shell family-enterprise-page" id="main-content">
      <header className="wealth-twin-hero family-enterprise-hero">
        <div>
          <p className="page-kicker">Family–enterprise financial twin</p>
          <h1>家庭资产之外，还要看企业这一张风险底稿。</h1>
          <p>股权、工资、分红、担保与流动性事件共同进入经济风险预算。证券账户股票少，不等于家庭权益风险低。</p>
          <AppLink to="/wealth/twin">返回家庭财富孪生</AppLink>
        </div>
        <div className="wealth-profile-controls">
          <label htmlFor="enterprise-household-select">当前家庭</label>
          <select id="enterprise-household-select" value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0 || refreshing}>
            {households.length === 0 ? <option value="">等待家庭资料</option> : null}
            {households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}
          </select>
          <Button type="button" variant="secondary" loading={refreshing} disabled={!householdId} onClick={() => void loadView(householdId, { force: true })}>
            <ArrowsClockwiseIcon size={17} aria-hidden="true" /> 重算家企暴露
          </Button>
        </div>
      </header>

      {loading ? <EnterpriseLoadingState /> : null}
      {!loading && error ? <EnterpriseErrorState message={error} onRetry={() => householdId ? void loadView(householdId) : void loadHouseholds()} /> : null}
      {!loading && view ? (
        <>
          <section className="twin-meta-strip" aria-label="家企财富视图元数据">
            <div><span>家庭</span><strong>{selectedHousehold?.name ?? "当前家庭"}</strong></div>
            <div><span>关联企业</span><strong>{view.enterprises.length} 家</strong></div>
            <div><span>依赖度</span><strong>{view.dependency.label} · {formatRatio(view.dependency.score)}</strong></div>
            <div><span>输入校验</span><strong>{view.meta.input_hash.slice(0, 10)}</strong></div>
          </section>
          {view.enterprises.length === 0 ? <EnterpriseEmptyState /> : (
            <>
              <EnterpriseWealthOverview view={view} />
              <EnterpriseDependencyPanel view={view} />
              <EnterpriseObligations view={view} />
              <EnterpriseLiquidityCfs view={view} />
            </>
          )}
        </>
      ) : null}
    </main>
  );
}

function EnterpriseLoadingState() {
  return <section className="profile-loading" role="status" aria-live="polite"><ClockCounterClockwiseIcon size={29} weight="duotone" aria-hidden="true" /><div><h2>正在核对家庭与企业暴露</h2><p>系统正在合并股权、收入、担保、质押与流动性事件。</p></div></section>;
}

function EnterpriseErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <section className="profile-loading profile-loading-error" role="alert"><WarningCircleIcon size={28} weight="duotone" aria-hidden="true" /><div><h2>家企财富视图暂时无法读取</h2><p>{message} 页面不会用模拟企业或估值替代缺失资料。</p></div><Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button></section>;
}

function EnterpriseEmptyState() {
  return <section className="enterprise-empty-state"><BriefcaseIcon size={30} weight="duotone" aria-hidden="true" /><div><h2>尚未录入关联企业</h2><p>当前家庭没有已确认的企业、股权或担保资料。本页不会推断企业价值。</p></div></section>;
}
