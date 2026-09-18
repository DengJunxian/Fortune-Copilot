import {
  ArrowsClockwiseIcon,
  ArrowRightIcon,
  CheckSquareOffsetIcon,
  ClockCounterClockwiseIcon,
  FileTextIcon,
  GlobeHemisphereWestIcon,
  PiggyBankIcon,
  UsersThreeIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import {
  createCFSSolution,
  fetchCFSSolution,
  recalculateCFSSolution,
  type CFSSolutionResponse,
} from "../api/cfs";
import { fetchHouseholds, type HouseholdSummary } from "../api/financial";
import { CFSDecisionLedger } from "../components/wealth/CFSDecisionLedger";
import { CFSRiskBudgetPanel } from "../components/wealth/CFSRiskBudgetPanel";
import { CfsOverview } from "../components/wealth/cfs/CfsOverview";
import { ProductCandidateComparison } from "../components/wealth/cfs/ProductCandidateComparison";
import { ProfessionalReferralCard } from "../components/wealth/cfs/ProfessionalReferralCard";
import {
  fetchCFSProductCandidates,
  productOntologyFeatureEnabled,
  type CFSProductCompositionResponse,
} from "../api/productOntology";
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

function storageKey(householdId: string): string {
  return `fortune-copilot:cfs-solution:${householdId}`;
}

function storedSolutionId(householdId: string): string | null {
  try {
    return window.sessionStorage?.getItem(storageKey(householdId)) ?? null;
  } catch {
    return null;
  }
}

function rememberSolution(householdId: string, solutionId: string): void {
  try {
    window.sessionStorage?.setItem(storageKey(householdId), solutionId);
  } catch {
    // The current result remains visible even when browser storage is unavailable.
  }
}

export function WealthCFSPage() {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [solution, setSolution] = useState<CFSSolutionResponse | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [productComposition, setProductComposition] = useState<CFSProductCompositionResponse | null>(null);
  const [productError, setProductError] = useState<string | null>(null);

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
      setError("无法读取家庭资料，请检查服务后重试。");
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
    setSolution(null);
    setConfirmed(false);
    setMessage(null);
    const solutionId = storedSolutionId(householdId);
    if (!solutionId) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchCFSSolution(householdId, solutionId, controller.signal)
      .then(setSolution)
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setError(loadError instanceof Error ? loadError.message : "综合方案加载失败");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [householdId]);

  useEffect(() => {
    if (!productOntologyFeatureEnabled || !householdId || !solution) {
      setProductComposition(null);
      setProductError(null);
      return;
    }
    const controller = new AbortController();
    setProductComposition(null);
    setProductError(null);
    fetchCFSProductCandidates(
      householdId,
      solution.solution.id,
      solution.meta.analysis_date,
      controller.signal,
    )
      .then(setProductComposition)
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setProductError(loadError instanceof Error ? loadError.message : "候选产品读取失败");
      });
    return () => controller.abort();
  }, [householdId, solution]);

  async function composeSolution() {
    if (!householdId || !confirmed) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await createCFSSolution(householdId);
      setSolution(result);
      rememberSolution(householdId, result.solution.id);
      setMessage("已根据当前确认的家庭事实生成综合方案。");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "综合方案生成失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function recalculate() {
    if (!householdId || !solution) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await recalculateCFSSolution(householdId, solution.solution.id);
      setSolution(result);
      rememberSolution(householdId, result.solution.id);
      setMessage(result.meta.idempotent_replay
        ? "家庭事实没有变化，原方案继续有效。"
        : "家庭事实或风险预算已变化，方案已更新。");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "综合方案重算失败");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedHousehold = households.find((item) => item.id === householdId);
  const componentTypes = new Set(solution?.components.map((item) => item.component_type) ?? []);
  const specializedEntries = [
    componentTypes.has("retirement") ? {
      to: "/wealth/retirement",
      label: "退休收入底线",
      description: "核对制度权益、保障收入、长寿与流动性缺口。",
      icon: PiggyBankIcon,
    } : null,
    componentTypes.has("cross_border") ? {
      to: "/wealth/global",
      label: "币种与跨境暴露",
      description: "追溯资产、收入、负债和未来责任的币种错配。",
      icon: GlobeHemisphereWestIcon,
    } : null,
    componentTypes.has("succession")
      || componentTypes.has("trust")
      || componentTypes.has("philanthropy") ? {
        to: "/wealth/family",
        label: "家庭长期安排",
        description: "仅展示已触发的照护、代际延续或公益目标。",
        icon: UsersThreeIcon,
      } : null,
  ].filter((item) => item !== null);
  return (
    <main className="page-shell wealth-cfs-page" id="main-content">
      <header className="wealth-twin-hero cfs-hero">
        <div>
          <p className="page-kicker">CFS Composer · Wealth Orchestrator</p>
          <h1>先决定家庭该做什么，再谈用什么产品。</h1>
          <p>系统先对齐家庭需要、责任现金流、ELTC、保障缺口与经济风险预算，再把每项行动交给确定性工具或专业人员。</p>
          <AppLink to="/wealth/family-enterprise">返回家企财富底稿</AppLink>
        </div>
        <div className="wealth-profile-controls">
          <label htmlFor="cfs-household-select">当前家庭</label>
          <select id="cfs-household-select" value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0 || submitting}>
            {households.length === 0 ? <option value="">等待家庭资料</option> : null}
            {households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}
          </select>
          {solution ? <Button type="button" variant="secondary" loading={submitting} onClick={() => void recalculate()}><ArrowsClockwiseIcon size={17} aria-hidden="true" /> 核对并重算</Button> : null}
        </div>
      </header>

      {loading ? <CFSLoadingState /> : null}
      {!loading && error ? <CFSErrorState message={error} onRetry={() => void loadHouseholds()} /> : null}
      {!loading && !error && !solution ? (
        <section className="cfs-compose-gate">
          <div>
            <span><FileTextIcon size={22} weight="duotone" aria-hidden="true" /> 待客户确认</span>
            <h2>为{selectedHousehold?.name ?? "当前家庭"}生成第一版综合方案</h2>
            <p>这一操作会保存方案版本、风险预算、行动组件和专业转介。如果当前不适合投资，系统会明确记录“无新增行动”。</p>
          </div>
          <div className="cfs-compose-action">
            <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span><CheckSquareOffsetIcon size={18} aria-hidden="true" /> 我确认以当前家庭事实生成并保存本次方案。</span></label>
            <Button type="button" loading={submitting} disabled={!confirmed || !householdId} onClick={() => void composeSolution()}>确认并生成综合方案</Button>
          </div>
        </section>
      ) : null}
      {!loading && !error && solution ? (
        <>
          <CfsOverview householdName={selectedHousehold?.name ?? "当前家庭"} solution={solution} />
          {message ? <p className="twin-success-message" role="status">{message}</p> : null}
          <CFSDecisionLedger solution={solution} />
          <ProfessionalReferralCard referrals={solution.referrals} />
          {specializedEntries.length > 0 ? (
            <section className="cfs-specialized-entry" aria-labelledby="specialized-entry-title">
              <header><span>Need → Complexity Gate → Professional Referral</span><h2 id="specialized-entry-title">按家庭需要展开专业模块</h2><p>入口由当前方案组件动态生成；未识别到对应需要时，不展示该模块。</p></header>
              <div>
                {specializedEntries.map((entry) => {
                  const Icon = entry.icon;
                  return (
                    <AppLink key={entry.to} to={entry.to}>
                      <Icon size={26} weight="duotone" aria-hidden="true" />
                      <span><strong>{entry.label}</strong><small>{entry.description}</small></span>
                      <ArrowRightIcon size={18} aria-hidden="true" />
                    </AppLink>
                  );
                })}
              </div>
            </section>
          ) : null}
          <CFSRiskBudgetPanel budget={solution.risk_budget} />
          {productOntologyFeatureEnabled && !productComposition && !productError ? (
            <section className="profile-loading" role="status"><ClockCounterClockwiseIcon size={25} weight="duotone" aria-hidden="true" /><div><h2>正在核对产品资格</h2><p>先核对快照、用途、风险、期限和渠道，不会直接生成购买指令。</p></div></section>
          ) : null}
          {productError ? <p className="cfs-catalog-alert" role="alert">{productError} 当前方案仍有效，但不会用旧目录补出产品。</p> : null}
          {productComposition ? <ProductCandidateComparison composition={productComposition} /> : null}
        </>
      ) : null}
    </main>
  );
}

function CFSLoadingState() {
  return <section className="profile-loading" role="status" aria-live="polite"><ClockCounterClockwiseIcon size={29} weight="duotone" aria-hidden="true" /><div><h2>正在核对家庭决策链</h2><p>系统正在合并需要、责任流、ELTC、保障和经济风险暴露。</p></div></section>;
}

function CFSErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <section className="profile-loading profile-loading-error" role="alert"><WarningCircleIcon size={28} weight="duotone" aria-hidden="true" /><div><h2>综合方案暂时无法读取</h2><p>{message} 页面不会用产品清单或模拟金额替代缺失结果。</p></div><Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button></section>;
}
