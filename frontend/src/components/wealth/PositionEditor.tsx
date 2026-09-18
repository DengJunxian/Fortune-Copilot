import {
  ArrowLeftIcon,
  BuildingsIcon,
  CheckCircleIcon,
  PencilSimpleIcon,
  PlusIcon,
  SpinnerGapIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createGraphPosition,
  deleteGraphPosition,
  fetchFinancialGraph,
  updateGraphPosition,
  type FinancialGraphResponse,
  type GraphAccountWrapper,
  type GraphPosition,
  type PositionDraft,
} from "../../api/financialGraph";
import { familyEnterpriseFeatureEnabled } from "../../api/familyEnterprise";
import { AppLink } from "../../router/Link";
import { formatMoney } from "../../utils/format";

interface PositionEditorProps {
  householdId: string;
  onBack: () => void;
  onContinue: () => void;
  showEnterpriseBridge?: boolean;
}

interface EditorDraft {
  ownerEntityId: string;
  providerName: string;
  accountType: string;
  accountWrapper: GraphAccountWrapper;
  currency: string;
  instrumentType: PositionDraft["instrument_type"];
  instrumentCode: string;
  name: string;
  quantity: string;
  acquisitionCost: string;
  marketValue: string;
  valuationDate: string;
  purpose: PositionDraft["purpose_dimension"];
  riskLevel: PositionDraft["risk_level"];
  liquidityDays: string;
  complexity: PositionDraft["complexity_level"];
  principalLossPossible: boolean;
  legallyPrincipalGuaranteed: boolean;
  lockUp: boolean;
  withdrawableDate: string;
  confirmed: boolean;
}

const instrumentOptions: Array<[PositionDraft["instrument_type"], string]> = [
  ["cash", "现金"],
  ["demand_deposit", "活期存款"],
  ["money_market", "货币基金"],
  ["time_deposit", "定期存款"],
  ["bank_wealth_management", "银行理财"],
  ["bond", "债券"],
  ["bond_fund", "债券基金"],
  ["public_fund", "公募基金"],
  ["equity_fund", "权益基金"],
  ["stock", "股票"],
  ["pension_account", "养老金账户"],
  ["insurance_cash_value", "保险现金价值"],
  ["trust", "信托"],
  ["primary_residence", "自住房产"],
  ["investment_property", "投资性房产"],
  ["vehicle", "车辆"],
  ["other", "其他资产"],
];

const purposeLabels: Record<PositionDraft["purpose_dimension"], string> = {
  daily: "日常支付",
  protection: "风险保障",
  stable: "稳健目标",
  growth: "长期增长",
};

const riskLabels: Record<PositionDraft["risk_level"], string> = {
  low: "低",
  medium_low: "中低",
  medium: "中",
  medium_high: "中高",
  high: "高",
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyDraft(): EditorDraft {
  return {
    ownerEntityId: "",
    providerName: "",
    accountType: "bank_account",
    accountWrapper: "ordinary",
    currency: "CNY",
    instrumentType: "public_fund",
    instrumentCode: "",
    name: "",
    quantity: "",
    acquisitionCost: "0.00",
    marketValue: "0.00",
    valuationDate: today(),
    purpose: "stable",
    riskLevel: "medium",
    liquidityDays: "1",
    complexity: "basic",
    principalLossPossible: true,
    legallyPrincipalGuaranteed: false,
    lockUp: false,
    withdrawableDate: "",
    confirmed: false,
  };
}

function draftFromPosition(position: GraphPosition): EditorDraft {
  return {
    ...emptyDraft(),
    ownerEntityId: position.owner_entity_id,
    currency: position.currency,
    instrumentType: position.instrument_type,
    instrumentCode: position.instrument_code ?? "",
    name: position.name,
    quantity: position.quantity ?? "",
    acquisitionCost: position.acquisition_cost,
    marketValue: position.market_value,
    valuationDate: position.valuation_date ?? today(),
    purpose: position.purpose_dimension,
    riskLevel: position.risk_level,
    liquidityDays: String(position.liquidity_days),
    complexity: position.complexity_level,
    principalLossPossible: position.principal_loss_possible,
    legallyPrincipalGuaranteed: position.legally_principal_guaranteed,
    lockUp: position.lock_up,
    withdrawableDate: position.withdrawable_date ?? "",
    confirmed: true,
  };
}

export function PositionEditor({
  householdId,
  onBack,
  onContinue,
  showEnterpriseBridge = familyEnterpriseFeatureEnabled,
}: PositionEditorProps) {
  const [graph, setGraph] = useState<FinancialGraphResponse | null>(null);
  const [draft, setDraft] = useState<EditorDraft>(emptyDraft);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const accountById = useMemo(
    () => new Map(graph?.accounts.map((account) => [account.id, account]) ?? []),
    [graph],
  );

  const load = useCallback((signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    fetchFinancialGraph(householdId, signal)
      .then((payload) => {
        setGraph(payload);
        const household = payload.entities.find((item) => item.entity_type === "household");
        setDraft((current) => ({
          ...current,
          ownerEntityId: current.ownerEntityId || household?.id || "",
        }));
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setError(loadError instanceof Error ? loadError.message : "精细资产暂时无法读取。 ");
      })
      .finally(() => setLoading(false));
  }, [householdId]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  function update<Key extends keyof EditorDraft>(key: Key, value: EditorDraft[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function resetEditor() {
    const household = graph?.entities.find((item) => item.entity_type === "household");
    setDraft({ ...emptyDraft(), ownerEntityId: household?.id ?? "" });
    setEditingId(null);
    setMessage(null);
    setError(null);
  }

  function beginEdit(position: GraphPosition) {
    setEditingId(position.id);
    setDraft(draftFromPosition(position));
    setMessage(null);
    setError(null);
    const editor = document.getElementById("position-editor-form");
    if (typeof editor?.scrollIntoView === "function") {
      editor.scrollIntoView({ behavior: "smooth" });
    }
  }

  async function savePosition() {
    if (!draft.name.trim()) {
      setError("请填写资产名称。 ");
      return;
    }
    if (Number(draft.marketValue) < 0 || Number(draft.acquisitionCost) < 0) {
      setError("资产金额不能为负数。 ");
      return;
    }
    if (!draft.valuationDate) {
      setError("请选择估值日期。 ");
      return;
    }
    if (!draft.confirmed) {
      setError("请确认资料来自本人或已由顾问与客户核对。 ");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const common = {
        owner_entity_id: draft.ownerEntityId || undefined,
        instrument_type: draft.instrumentType,
        instrument_code: draft.instrumentCode || undefined,
        name: draft.name.trim(),
        quantity: draft.quantity || undefined,
        acquisition_cost: draft.acquisitionCost,
        market_value: draft.marketValue,
        currency: draft.currency,
        valuation_date: draft.valuationDate,
        purpose_dimension: draft.purpose,
        risk_level: draft.riskLevel,
        liquidity_days: Number(draft.liquidityDays || 0),
        complexity_level: draft.complexity,
        principal_loss_possible: draft.principalLossPossible,
        legally_principal_guaranteed: draft.legallyPrincipalGuaranteed,
        lock_up: draft.lockUp,
        withdrawable_date: draft.withdrawableDate || undefined,
        source_kind: "user_self_report" as const,
        evidence_json: { confirmation: "explicit", ownership: "client_confirmed" },
        data_source: "client_intake" as const,
        is_user_confirmed: true as const,
      };
      if (editingId) {
        const current = graph?.positions.find((item) => item.id === editingId);
        if (!current) throw new Error("待更新的资产已不存在，请刷新后重试。 ");
        await updateGraphPosition(householdId, editingId, {
          ...common,
          expected_version: current.version,
        });
      } else {
        if (!draft.providerName.trim()) {
          throw new Error("新增持仓时请填写账户机构。 ");
        }
        await createGraphPosition(householdId, {
          ...common,
          account: {
            provider_name: draft.providerName.trim(),
            account_type: draft.accountType,
            account_wrapper: draft.accountWrapper,
            jurisdiction: "CN",
          },
        });
      }
      setGraph(await fetchFinancialGraph(householdId));
      setMessage(editingId ? "资产细节已更新。" : "补充持仓已保存。 ");
      setEditingId(null);
      const household = graph?.entities.find((item) => item.entity_type === "household");
      setDraft({ ...emptyDraft(), ownerEntityId: household?.id ?? "" });
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "资产资料保存失败。 ");
    } finally {
      setSaving(false);
    }
  }

  async function removePosition(position: GraphPosition) {
    setSaving(true);
    setError(null);
    try {
      await deleteGraphPosition(householdId, position.id, position.version);
      setGraph(await fetchFinancialGraph(householdId));
      setRemovingId(null);
      setMessage("补充持仓已移除。 ");
    } catch (removeError) {
      setError(removeError instanceof Error ? removeError.message : "持仓移除失败。 ");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="position-editor-state" role="status" aria-live="polite">
        <SpinnerGapIcon className="spin" size={28} aria-hidden="true" />
        <div><h1>正在准备精细资产清单</h1><p>正在核对汇总报表中的资产，不会重复计入。</p></div>
      </section>
    );
  }

  if (!graph) {
    return (
      <section className="position-editor-state">
        <div><h1>精细资产暂时不可用</h1><p>{error ?? "您可以跳过，不影响基础财务分析。"}</p></div>
        <div className="planning-step-actions">
          <button type="button" className="secondary-action" onClick={() => load()}>重新读取</button>
          <button type="button" className="primary-action" onClick={onContinue}>跳过并继续</button>
        </div>
      </section>
    );
  }

  return (
    <section className="position-editor" aria-labelledby="position-editor-title">
      <header className="position-editor-intro">
        <div>
          <p className="page-kicker">可选 · 约 2 分钟</p>
          <h1 id="position-editor-title">完善账户与持仓细节</h1>
          <p>补充所有权、期限、用途和风险属性。基础规划金额仍以刚才确认的汇总财务报表为准，系统不会重复计算。</p>
        </div>
        <div className="position-editor-summary" aria-label="资产清单摘要">
          <span>当前清单</span>
          <strong>{graph.positions.length} 项</strong>
          <small>合计 {formatMoney(graph.projection_diagnostic.projected_asset_total)}</small>
        </div>
      </header>

      {graph.integrity.status === "needs_review" ? (
        <p className="inline-form-error" role="alert">部分账户关系需要顾问复核：{graph.integrity.issues.join("；")}</p>
      ) : null}
      {error ? <p className="inline-form-error" role="alert">{error}</p> : null}
      {message ? <p className="inline-form-success" role="status"><CheckCircleIcon size={18} weight="fill" aria-hidden="true" />{message}</p> : null}

      <div className="position-list" aria-label="精细资产清单">
        {graph.positions.map((position) => {
          const account = accountById.get(position.account_id);
          const isLegacy = position.legacy_asset_id !== null;
          return (
            <article className="position-row" key={position.id}>
              <div className="position-row-main">
                <span>{instrumentOptions.find(([value]) => value === position.instrument_type)?.[1] ?? "其他资产"}</span>
                <strong>{position.name}</strong>
                <small>{account?.provider_name ?? "未标记账户"} · {position.currency}</small>
              </div>
              <div className="position-row-facts">
                <span>{purposeLabels[position.purpose_dimension]}</span>
                <span>风险 {riskLabels[position.risk_level]}</span>
                <span>{position.lock_up ? "锁定" : `${position.liquidity_days} 天可用`}</span>
              </div>
              <strong className="position-row-value">{formatMoney(position.market_value)}</strong>
              <div className="position-row-actions">
                <button type="button" onClick={() => beginEdit(position)}><PencilSimpleIcon size={16} aria-hidden="true" />完善</button>
                {!isLegacy && removingId !== position.id ? (
                  <button type="button" onClick={() => setRemovingId(position.id)}><TrashIcon size={16} aria-hidden="true" />移除</button>
                ) : null}
                {!isLegacy && removingId === position.id ? (
                  <span className="inline-confirm">
                    <button type="button" disabled={saving} onClick={() => void removePosition(position)}>确认移除</button>
                    <button type="button" onClick={() => setRemovingId(null)}>保留</button>
                  </span>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>

      {showEnterpriseBridge ? (
        <aside className="position-enterprise-bridge" aria-labelledby="position-enterprise-bridge-title">
          <BuildingsIcon size={28} weight="duotone" aria-hidden="true" />
          <div>
            <span>企业关联 · 可选</span>
            <h2 id="position-enterprise-bridge-title">企业股权、担保和分红，放到家企底稿核对</h2>
            <p>这里继续记录个人与家庭账户；企业所有权、未上市估值、个人担保和企业收入依赖另行留痕，避免与金融持仓重复计算。</p>
          </div>
          <AppLink className="secondary-action" to="/wealth/family-enterprise">补充企业关联</AppLink>
        </aside>
      ) : null}

      <form id="position-editor-form" className="position-form" onSubmit={(event) => { event.preventDefault(); void savePosition(); }}>
        <header>
          <div>
            <p className="page-kicker">{editingId ? "完善已有资产" : "补充未列入汇总表的持仓"}</p>
            <h2>{editingId ? "更新资产细节" : "新增一项持仓"}</h2>
          </div>
          {editingId ? <button type="button" className="text-action" onClick={resetEditor}>取消编辑</button> : <PlusIcon size={22} aria-hidden="true" />}
        </header>
        <div className="position-form-grid">
          <label>所有者<select value={draft.ownerEntityId} onChange={(event) => update("ownerEntityId", event.target.value)}>{graph.entities.filter((item) => ["household", "person"].includes(item.entity_type)).map((entity) => <option key={entity.id} value={entity.id}>{entity.display_name}</option>)}</select></label>
          {!editingId ? <label>账户机构<input value={draft.providerName} placeholder="例如：工商银行（客户自报）" onChange={(event) => update("providerName", event.target.value)} /></label> : null}
          {!editingId ? <label>账户类型<select value={draft.accountType} onChange={(event) => update("accountType", event.target.value)}><option value="bank_account">银行账户</option><option value="securities_custody">证券托管</option><option value="pension_account">养老金账户</option><option value="insurance_policy">保险账户</option><option value="other">其他</option></select></label> : null}
          {!editingId ? <label>账户包装<select value={draft.accountWrapper} onChange={(event) => update("accountWrapper", event.target.value as EditorDraft["accountWrapper"])}><option value="ordinary">普通账户</option><option value="demand_account">活期账户</option><option value="personal_pension">个人养老金</option><option value="enterprise_annuity">企业年金</option><option value="provident_fund">公积金</option><option value="insurance">保险</option><option value="other">其他</option></select></label> : null}
          <label>资产类别<select value={draft.instrumentType} onChange={(event) => update("instrumentType", event.target.value as PositionDraft["instrument_type"])}>{instrumentOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>资产名称<input value={draft.name} placeholder="例如：三年期定期存款" onChange={(event) => update("name", event.target.value)} /></label>
          <label>产品代码（如有）<input value={draft.instrumentCode} onChange={(event) => update("instrumentCode", event.target.value)} /></label>
          <label>币种<select value={draft.currency} onChange={(event) => update("currency", event.target.value)}><option value="CNY">人民币 CNY</option><option value="USD">美元 USD</option><option value="HKD">港币 HKD</option><option value="EUR">欧元 EUR</option></select></label>
          <label>当前市值<input type="number" min="0" step="0.01" value={draft.marketValue} onChange={(event) => update("marketValue", event.target.value)} /></label>
          <label>取得成本<input type="number" min="0" step="0.01" value={draft.acquisitionCost} onChange={(event) => update("acquisitionCost", event.target.value)} /></label>
          <label>数量（如适用）<input type="number" min="0" step="0.00000001" value={draft.quantity} onChange={(event) => update("quantity", event.target.value)} /></label>
          <label>估值日期<input type="date" value={draft.valuationDate} onChange={(event) => update("valuationDate", event.target.value)} /></label>
          <label>资金用途<select value={draft.purpose} onChange={(event) => update("purpose", event.target.value as PositionDraft["purpose_dimension"])}>{Object.entries(purposeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>风险等级<select value={draft.riskLevel} onChange={(event) => update("riskLevel", event.target.value as PositionDraft["risk_level"])}>{Object.entries(riskLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>通常几天可用<input type="number" min="0" max="36500" value={draft.liquidityDays} onChange={(event) => update("liquidityDays", event.target.value)} /></label>
          <label>复杂程度<select value={draft.complexity} onChange={(event) => update("complexity", event.target.value as PositionDraft["complexity_level"])}><option value="basic">基础</option><option value="standard">标准</option><option value="complex">复杂</option><option value="professional">需专业人员</option></select></label>
        </div>
        <div className="position-checks">
          <label><input type="checkbox" checked={draft.principalLossPossible} onChange={(event) => { update("principalLossPossible", event.target.checked); if (event.target.checked) update("legallyPrincipalGuaranteed", false); }} />本金可能损失</label>
          <label><input type="checkbox" checked={draft.legallyPrincipalGuaranteed} onChange={(event) => { update("legallyPrincipalGuaranteed", event.target.checked); if (event.target.checked) update("principalLossPossible", false); }} />法律属性保证本金</label>
          <label><input type="checkbox" checked={draft.lockUp} onChange={(event) => update("lockUp", event.target.checked)} />存在锁定期</label>
          {draft.lockUp ? <label>可取日期<input type="date" value={draft.withdrawableDate} onChange={(event) => update("withdrawableDate", event.target.value)} /></label> : null}
        </div>
        <label className="position-confirm"><input type="checkbox" checked={draft.confirmed} onChange={(event) => update("confirmed", event.target.checked)} /><span>我确认以上资料来自本人，或已由顾问与客户共同核对。公开资料或模拟数据不能替代客户确认。</span></label>
        <button className="secondary-action" type="submit" disabled={saving}>{saving ? <SpinnerGapIcon className="spin" size={18} aria-hidden="true" /> : null}{editingId ? "保存修改" : "保存补充持仓"}</button>
      </form>

      <footer className="planning-step-actions position-editor-footer">
        <button type="button" className="secondary-action" onClick={onBack}><ArrowLeftIcon size={18} aria-hidden="true" />返回财务报表</button>
        <p>这一步可以跳过，稍后仍可由客户或顾问补充。</p>
        <button type="button" className="primary-action" onClick={onContinue}>继续查看财务分析</button>
      </footer>
    </section>
  );
}
