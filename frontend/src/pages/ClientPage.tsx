import { useCallback, useEffect, useState } from "react";
import {
  fetchFinancialAnalysis,
  fetchHouseholds,
  financialAnalysisExportUrl,
  persistFinancialAnalysis,
  type FinancialAnalysis,
  type HouseholdSummary,
} from "../api/financial";
import { ClientExperienceWorkspace } from "../components/client/ClientExperienceWorkspace";
import { Button } from "../components/ui/Button";
import { usePortalContext } from "../contexts/PortalContext";
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

function requestedClientView(): "accounts" | "family" {
  return new URLSearchParams(window.location.search).get("view") === "accounts"
    ? "accounts"
    : "family";
}

export function ClientPage() {
  const { source } = usePortalContext();
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [analysis, setAnalysis] = useState<FinancialAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const loadHouseholds = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchHouseholds(signal);
      if (items.length === 0) throw new Error("尚无可分析家庭");
      setHouseholds(items);
      const requestedCode = requestedCaseCode();
      const preferred = items.find((item) => item.code === requestedCode)
        ?? items.find((item) => item.code === "DEMO_B")
        ?? items[0];
      if (preferred) setHouseholdId(preferred.id);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setLoading(false);
      setError("无法读取家庭财务数据；请启动后端与数据库后重试。");
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
    setLoading(true);
    setError(null);
    setSavedMessage(null);
    fetchFinancialAnalysis(householdId, controller.signal)
      .then((payload) => {
        setAnalysis(payload);
        setLoading(false);
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setAnalysis(null);
        setLoading(false);
        setError("财务体检计算失败；未展示任何估算或缓存金额。");
      });
    return () => controller.abort();
  }, [householdId]);

  async function saveRun() {
    if (!analysis) return;
    setSaving(true);
    setSavedMessage(null);
    try {
      const run = await persistFinancialAnalysis(analysis.meta.household_id);
      setSavedMessage(`已保存本次体检：${run.metric_count} 项指标，快照 ${run.snapshot_id.slice(0, 8)}。`);
    } catch {
      setSavedMessage("保存失败；当前页面结果未受影响，请检查后端后重试。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page-shell financial-page client-page" id="main-content">
      <header className="financial-hero client-hero">
        <div>
          <p className="page-kicker">客户端 · 确定性家庭财富规划</p>
          <h1>家庭财富驾驶舱</h1>
          <p>从家庭画像到八章规划书，每一步都能回到数据、公式、规则、授权与行动期限。</p>
        </div>
        <div className="household-control">
          <label htmlFor="household-select">演示家庭</label>
          <select id="household-select" value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0}>
            {households.length === 0 ? <option value="">等待后端数据</option> : null}
            {households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}
          </select>
          <span>{source === "api" ? "后端确定性数据" : "离线能力清单"}</span>
        </div>
      </header>

      {households.length > 1 ? (
        <nav className="household-quick-switch" aria-label="一键切换演示家庭">
          <span>家庭差异演示</span>
          {households.slice(0, 3).map((household) => (
            <button key={household.id} type="button" aria-pressed={household.id === householdId} onClick={() => setHouseholdId(household.id)}>
              <strong>{household.code}</strong><small>{household.name}</small>
            </button>
          ))}
        </nav>
      ) : null}

      {loading ? <LoadingState /> : null}
      {!loading && error ? <UnavailableState message={error} onRetry={() => void loadHouseholds()} /> : null}
      {!loading && analysis ? (
        <>
          <AnalysisHeader analysis={analysis} onSave={() => void saveRun()} saving={saving} savedMessage={savedMessage} />
          <ClientExperienceWorkspace analysis={analysis} initialView={requestedClientView()} />
          <BoundaryNotes />
        </>
      ) : null}
    </main>
  );
}

function LoadingState() {
  return <section className="analysis-state" aria-live="polite"><span className="loading-mark" aria-hidden="true" /><div><h2>正在生成家庭底表</h2><p>确定性引擎正在核对资产、负债、收支、保障、目标和授权版本。</p></div></section>;
}

function UnavailableState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <section className="analysis-state analysis-state-error" role="alert"><div><h2>财务测算当前不可用</h2><p>{message}</p><p>纯前端模式不会嵌入家庭金额或伪造计算结果。</p></div><Button type="button" variant="secondary" onClick={onRetry}>重新连接</Button><BoundaryNotes /></section>;
}

function AnalysisHeader({ analysis, onSave, saving, savedMessage }: { analysis: FinancialAnalysis; onSave: () => void; saving: boolean; savedMessage: string | null }) {
  return (
    <section className="analysis-meta-bar" aria-label="本次体检元数据">
      <div><span>家庭</span><strong>{analysis.profile.name}</strong></div>
      <div><span>分析日 / 数据日</span><strong>{formatDate(analysis.meta.analysis_date)} / {formatDate(analysis.meta.data_as_of)}</strong></div>
      <div><span>公式 / 规则</span><strong>{analysis.meta.formula_version} / {analysis.meta.rule_version}</strong></div>
      <div><span>模式</span><strong>{analysis.meta.synthetic_data ? "合成数据 · Mock" : "已授权家庭数据"}</strong></div>
      <div className="analysis-actions"><Button type="button" variant="secondary" loading={saving} onClick={onSave}>保存本次体检</Button><a className="button export-link" data-variant="primary" href={financialAnalysisExportUrl(analysis.meta.household_id)} download>导出财务底稿</a></div>
      {savedMessage ? <p className="save-message" role="status">{savedMessage}</p> : null}
    </section>
  );
}

function BoundaryNotes() {
  return (
    <aside className="boundary-notes" aria-labelledby="boundary-heading">
      <h2 id="boundary-heading">计算与产品边界</h2>
      <ul>
        <li>信用卡只作为支付工具，额度不计入资产；待还款余额计入负债。</li>
        <li>四账户按家庭目标、安全闸门和资金期限动态生成，不采用固定比例。</li>
        <li>银行理财、信托、基金或保险不统一描述为保本产品。</li>
        <li>长期增长账户的条件不等同于家庭总资产统一配置，更不默认推荐个股、杠杆或股指期货。</li>
        <li>最低工资追赶参数不等同于 CPI；语言模型不参与关键金额、比率或配置计算。</li>
      </ul>
    </aside>
  );
}
