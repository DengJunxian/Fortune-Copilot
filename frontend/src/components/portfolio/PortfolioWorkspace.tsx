import { useEffect, useMemo, useState } from "react";
import {
  checkPortfolioSuitability,
  fetchPortfolio,
  persistPortfolio,
  portfolioExportUrl,
  type CandidateType,
  type MarketScenario,
  type PortfolioCandidate,
  type PortfolioResponse,
  type SuitabilityDecision,
  type SuitabilityGate,
  type SuitabilityProbeRequest,
  type SuitabilityProbeResponse,
  type SuitabilityStatus,
} from "../../api/portfolio";
import { fetchHouseholds, type HouseholdSummary } from "../../api/financial";
import { formatDate, formatMoney, formatRatio } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { FundAdvisoryWorkspace } from "./FundAdvisoryWorkspace";

type PortfolioView = "client" | "advisor" | "risk";

const decisionCopy: Record<SuitabilityDecision, string> = {
  allow: "允许进入复核",
  downgrade: "已降级",
  reject: "拒绝执行",
  education_only: "仅教育展示",
  escalate: "转人工复核",
};

const scenarioCopy: Record<MarketScenario, string> = {
  neutral: "中性，不做战术偏移",
  risk_off: "风险收缩，最多偏移 5 个百分点",
  risk_on: "风险扩张，最多偏移 5 个百分点",
};

function badgeTone(status: SuitabilityStatus | SuitabilityDecision) {
  if (status === "pass" || status === "allow") return "success" as const;
  if (status === "block" || status === "reject") return "danger" as const;
  if (status === "restrict" || status === "downgrade") return "warning" as const;
  return "info" as const;
}

export function PortfolioWorkspace({ householdId, view = "client" }: { householdId: string; view?: PortfolioView }) {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [scenario, setScenario] = useState<MarketScenario>("neutral");
  const [selectedType, setSelectedType] = useState<CandidateType>("balanced");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setMessage(null);
    fetchPortfolio(householdId, scenario, controller.signal)
      .then((payload) => {
        setPortfolio(payload);
        setLoading(false);
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setPortfolio(null);
        setLoading(false);
        setError("组合优化当前不可用；页面不会使用缓存比例或伪造产品映射。");
      });
    return () => controller.abort();
  }, [householdId, scenario]);

  const selectedCandidate = useMemo(
    () => portfolio?.candidates.find((item) => item.candidate_type === selectedType) ?? portfolio?.candidates[0],
    [portfolio, selectedType],
  );

  async function saveDraft() {
    setSaving(true);
    setMessage(null);
    try {
      const result = await persistPortfolio(householdId, scenario);
      setMessage(`已保存 ${result.candidate_count} 套候选与 ${result.suitability_check_count} 条闸门记录。`);
    } catch {
      setMessage("保存失败；当前确定性计算结果没有被更改。");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <section className="portfolio-workspace portfolio-loading" aria-live="polite">
        <p className="section-index">组合与适当性</p>
        <h2>正在运行五道闸门和确定性组合求解</h2>
        <p>先确认长期资金，再比较回撤、目标缺口、流动性、费用和分散度。</p>
      </section>
    );
  }

  if (error || !portfolio || !selectedCandidate) {
    return (
      <section className="portfolio-workspace portfolio-unavailable" role="alert">
        <p className="section-index">组合与适当性</p>
        <h2>组合计算当前不可用</h2>
        <p>{error}</p>
      </section>
    );
  }

  return (
    <section className="portfolio-workspace" data-view={view} aria-labelledby={`portfolio-heading-${view}`}>
      <header className="portfolio-header">
        <div>
          <p className="section-index">ELTC → Risk Budget → Goal → Allocation</p>
          <h2 id={`portfolio-heading-${view}`}>{view === "risk" ? "适当性证据与拒绝链" : view === "advisor" ? "三方案顾问复核台" : "先确认本次能配置多少钱，再看资产方向"}</h2>
          <p>{portfolio.counting_note}</p>
        </div>
        <div className="portfolio-actions">
          {view !== "risk" ? <Button type="button" variant="secondary" loading={saving} onClick={() => void saveDraft()}>保存候选草案</Button> : null}
          <a className="button export-link" data-variant="primary" href={portfolioExportUrl(householdId, scenario)} download>导出组合 JSON</a>
        </div>
      </header>

      <div className="portfolio-context-rail">
        <ContextValue label="长期可投资资本 ELTC" value={formatMoney(portfolio.context.eligible_long_term_amount)} />
        <ContextValue label="当前增长资产" value={formatMoney(portfolio.context.current_growth_assets)} />
        <ContextValue label="应补回安全层" value={formatMoney(portfolio.context.amount_to_restore_safety_layers)} />
        <ContextValue label="客户审慎上限" value={(portfolio.customer_suitability_gate.effective_risk_limit ?? "r1").toUpperCase()} />
        <ContextValue label="购买力门槛 PPH" value={formatRatio(portfolio.context.purchasing_power_hurdle)} />
        <ContextValue label="单只股票卫星暴露" value={formatMoney(portfolio.context.single_equity_amount)} />
        <ContextValue label="模拟产品目录" value={`${portfolio.catalog.product_count} 类 · Mock`} />
        <label className="portfolio-scenario-control">
          <span>有限战术情景</span>
          <select value={scenario} onChange={(event) => setScenario(event.target.value as MarketScenario)}>
            {Object.entries(scenarioCopy).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>

      <ol className="portfolio-decision-path" aria-label="家庭组合决策五步">
        <li><span>Step 1</span><small>本次可以配置多少钱？</small><strong>{formatMoney(portfolio.context.eligible_long_term_amount)}</strong><p>只使用通过家庭责任扣减与安全闸门的 ELTC。</p></li>
        <li><span>Step 2</span><small>家庭风险预算</small><strong>{(portfolio.customer_suitability_gate.effective_risk_limit ?? "r1").toUpperCase()}</strong><p>能力、意愿、行为与适当性共同约束。</p></li>
        <li><span>Step 3</span><small>家庭目标</small><strong>{formatMoney(portfolio.context.long_term_goal_present_value_gap, true)}</strong><p>长期责任目标的现值缺口，不用近期责任资金补足。</p></li>
        <li><span>Step 4</span><small>建议资产方向</small><strong>{selectedCandidate.name}</strong><p>{selectedCandidate.strategic_allocations.map((line) => line.asset_class_name).join(" · ")}</p></li>
        <li><span>Step 5</span><small>为什么这样配置？</small><strong>七项证据</strong><p>Goal · Risk · Behavior · 流动性 · CVaR · 购买力 · 分散度</p></li>
      </ol>

      {Number(portfolio.context.eligible_long_term_amount) <= 0 ? (
        <aside className="portfolio-block-note" role="note">
          <strong>当前没有可执行的长期新增资金</strong>
          <p>三套比例只用于教育比较；先按四账户顺序补足应急、债务、保障和近期目标，系统不会为了展示组合而绕过安全闸门。</p>
        </aside>
      ) : null}
      {portfolio.catalog.catalog_stale ? <aside className="portfolio-block-note" role="alert"><strong>产品快照已过期</strong><p>当前只保留教育展示，不产生可执行购买建议。</p></aside> : null}

      <CandidateComparison candidates={portfolio.candidates} selectedType={selectedType} onSelect={setSelectedType} />

      <div className="portfolio-detail-layout">
        <AllocationLedger candidate={selectedCandidate} />
        <GateChain gates={selectedCandidate.gates} />
      </div>

      <ProductMappingTable candidate={selectedCandidate} />
      <FundAdvisoryWorkspace householdId={householdId} />
      <RebalanceWorkspace candidate={selectedCandidate} />

      {view === "risk" ? <SuitabilityProbePanel householdId={householdId} portfolio={portfolio} /> : null}

      <div className="portfolio-education-layout">
        <section aria-labelledby={`education-heading-${view}`}>
          <p className="section-index">投资者教育</p>
          <h3 id={`education-heading-${view}`}>名称相近，不代表风险相同</h3>
          <ol className="education-ledger">
            {portfolio.education_cards.map((card) => (
              <li key={card.code}>
                <div><strong>{card.title}</strong><p>{card.summary}</p></div>
                <ul>{card.points.map((point) => <li key={point}>{point}</li>)}</ul>
              </li>
            ))}
          </ol>
        </section>
        <aside className="hedge-lab-boundary">
          <span>只读教育占位 · 默认关闭</span>
          <h3>{portfolio.professional_hedge_lab.title}</h3>
          <p>{portfolio.professional_hedge_lab.reason}</p>
          <ul>{portfolio.professional_hedge_lab.prerequisites.map((item) => <li key={item}>{item}</li>)}</ul>
        </aside>
      </div>

      <details className="mock-catalog-disclosure">
        <summary>查看全部 {portfolio.catalog.product_count} 条 Mock 产品类型与保证／非保证说明</summary>
        <div className="data-table-wrap" tabIndex={0} role="region" aria-label="模拟产品目录">
          <table className="data-table">
            <thead><tr><th>模拟类型</th><th>风险 / 期限</th><th>流动性</th><th>保证说明</th><th>非保证与风险</th></tr></thead>
            <tbody>{portfolio.catalog.products.map((product) => (
              <tr key={product.code}>
                <td><strong>{product.name}</strong><small>{product.code} · Mock</small></td>
                <td>{product.risk_level.toUpperCase()} / {product.minimum_holding_months} 个月</td>
                <td>{product.liquidity_level}<small>{product.redemption_rules}</small></td>
                <td>{product.guarantee_disclosure}</td>
                <td>{product.non_guaranteed_disclosure}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>

      {message ? <p className="portfolio-status" role="status">{message}</p> : null}
      <footer className="portfolio-version">
        <span>公式 {portfolio.meta.formula_version}</span>
        <span>规则 {portfolio.meta.rule_version}</span>
        <span>优化器 {portfolio.meta.optimizer_version}</span>
        <span>目录 {portfolio.meta.catalog_version} · Mock</span>
        <span>输入 {portfolio.meta.input_version.slice(0, 12)}</span>
      </footer>
    </section>
  );
}

function ContextValue({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function CandidateComparison({ candidates, selectedType, onSelect }: { candidates: PortfolioCandidate[]; selectedType: CandidateType; onSelect: (type: CandidateType) => void }) {
  return (
    <section className="candidate-comparison" aria-labelledby="candidate-comparison-heading">
      <header><div><p className="section-index">三方案对照</p><h3 id="candidate-comparison-heading">同一资金口径，不同风险取舍</h3></div><p>情景成功率来自五个离线加权场景，不是 Monte Carlo 或收益承诺。</p></header>
      <div className="data-table-wrap" tabIndex={0} role="region" aria-label="稳健基准进取方案比较">
        <table className="candidate-matrix">
          <thead><tr><th>比较项</th>{candidates.map((candidate) => <th key={candidate.candidate_type}><button type="button" aria-pressed={selectedType === candidate.candidate_type} onClick={() => onSelect(candidate.candidate_type)}><strong>{candidate.name}</strong><StatusBadge tone={badgeTone(candidate.decision)}>{decisionCopy[candidate.decision]}</StatusBadge></button></th>)}</tr></thead>
          <tbody>
            <ComparisonRow label="可执行金额" candidates={candidates} render={(item) => formatMoney(item.investment_amount)} />
            <ComparisonRow label="目标情景成功率" candidates={candidates} render={(item) => formatRatio(item.goal_success_probability)} />
            <ComparisonRow label="刚性责任违约概率" candidates={candidates} render={(item) => formatRatio(item.responsibility_breach_probability)} />
            <ComparisonRow label="购买力成功概率" candidates={candidates} render={(item) => formatRatio(item.purchasing_power_success_probability)} />
            <ComparisonRow label="情景区间" candidates={candidates} render={(item) => `${formatMoney(item.simulated_range_low, true)}—${formatMoney(item.simulated_range_high, true)}`} />
            <ComparisonRow label="极端损失估计" candidates={candidates} render={(item) => `${formatMoney(item.extreme_loss_amount, true)} / ${formatRatio(item.extreme_loss_ratio)}`} />
            <ComparisonRow label="最大回撤估计" candidates={candidates} render={(item) => formatRatio(item.max_drawdown_estimate)} />
            <ComparisonRow label="流动性 / 年费" candidates={candidates} render={(item) => `${item.liquidity_description} / ${formatMoney(item.annual_fee_estimate, true)}`} />
            <ComparisonRow label="费后实际回报" candidates={candidates} render={(item) => formatRatio(item.real_return_after_fee)} />
            <ComparisonRow label="求解状态" candidates={candidates} render={(item) => item.optimization.method === "deterministic_grid_search" ? `网格最优 · ${item.optimization.evaluated_candidates} 个` : "规则降级"} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ComparisonRow({ label, candidates, render }: { label: string; candidates: PortfolioCandidate[]; render: (candidate: PortfolioCandidate) => string }) {
  return <tr><th scope="row">{label}</th>{candidates.map((candidate) => <td key={candidate.candidate_type}>{render(candidate)}</td>)}</tr>;
}

function AllocationLedger({ candidate }: { candidate: PortfolioCandidate }) {
  return (
    <article className="allocation-ledger">
      <header><div><p className="section-index">战略配置</p><h3>{candidate.name}方案的资产类别</h3></div><StatusBadge tone={badgeTone(candidate.decision)}>{decisionCopy[candidate.decision]}</StatusBadge></header>
      <ol>{candidate.strategic_allocations.map((line) => (
        <li key={line.asset_class}>
          <div><strong>{line.asset_class_name}</strong><small>CVaR {formatRatio(line.cvar_loss)} · 最大回撤 {formatRatio(line.max_drawdown)}</small></div>
          <progress className="allocation-track" aria-label={`${line.asset_class_name} ${formatRatio(line.ratio)}`} max="1" value={line.ratio}>{formatRatio(line.ratio)}</progress>
          <b>{formatRatio(line.ratio)}</b><span>{formatMoney(line.amount)}</span>
        </li>
      ))}</ol>
      <div className="candidate-rationale"><strong>为何不是另外两套</strong><p>{candidate.why_not_other_candidates}</p><ul>{candidate.primary_risks.map((risk) => <li key={risk}>{risk}</li>)}</ul></div>
      <details><summary>查看求解证据</summary><dl><div><dt>方法</dt><dd>{candidate.optimization.method}</dd></div><div><dt>状态</dt><dd>{candidate.optimization.status}</dd></div><div><dt>随机种子</dt><dd>{candidate.optimization.random_seed}</dd></div><div><dt>参数哈希</dt><dd><code>{candidate.optimization.parameter_hash.slice(0, 16)}</code></dd></div></dl>{candidate.optimization.fallback_reason ? <p>{candidate.optimization.fallback_reason}</p> : null}</details>
    </article>
  );
}

function GateChain({ gates }: { gates: SuitabilityGate[] }) {
  return (
    <article className="suitability-chain">
      <header><div><p className="section-index">适当性链</p><h3>任何一关都不能被说明文字覆盖</h3></div></header>
      <ol>{gates.map((gate, index) => (
        <li key={gate.gate}>
          <div className="gate-summary"><span>0{index + 1}</span><div><strong>{gate.name}</strong><p>{gate.explanation}</p></div><StatusBadge tone={badgeTone(gate.status)}>{gate.status === "pass" ? "通过" : gate.status === "block" ? "拦截" : "限制"}</StatusBadge></div>
          <details><summary>查看 {gate.checks.length} 项检查与拒绝原因</summary><ul>{gate.checks.map((check) => <li key={check.check_code} data-status={check.status}><div><strong>{check.label}</strong><span>{check.observed_value}</span></div><p>{check.reason}</p><small>{check.rule}</small></li>)}</ul></details>
        </li>
      ))}</ol>
    </article>
  );
}

function ProductMappingTable({ candidate }: { candidate: PortfolioCandidate }) {
  return (
    <section className="product-mapping-section" aria-labelledby="product-mapping-heading">
      <header><div><p className="section-index">产品类型映射</p><h3 id="product-mapping-heading">只匹配 Mock 类型，不伪装真实产品接口</h3></div><p>单一模拟产品类型最多占组合 30%；宽基与分散化工具优先。</p></header>
      <div className="data-table-wrap" tabIndex={0} role="region" aria-label="模拟产品类型匹配表"><table className="data-table"><thead><tr><th>资产类别</th><th>模拟产品类型</th><th>比例 / 金额</th><th>风险 / 流动性</th><th>决定与原因</th></tr></thead><tbody>{candidate.product_mappings.map((mapping, index) => <tr key={`${mapping.asset_class}-${mapping.product_code ?? index}`}><td>{mapping.asset_class_name}</td><td><strong>{mapping.product_name}</strong><small>{mapping.product_code ?? "未匹配"} · Mock</small></td><td>{formatRatio(mapping.allocation_ratio)}<small>{formatMoney(mapping.allocation_amount)}</small></td><td>{mapping.risk_level?.toUpperCase() ?? "—"}<small>{mapping.liquidity_level ?? "—"}</small></td><td><StatusBadge tone={badgeTone(mapping.decision)}>{decisionCopy[mapping.decision]}</StatusBadge><small>{mapping.reasons.join("；")}</small></td></tr>)}</tbody></table></div>
    </section>
  );
}

function RebalanceWorkspace({ candidate }: { candidate: PortfolioCandidate }) {
  const plan = candidate.rebalancing;
  return (
    <section className="rebalance-workspace" aria-labelledby="rebalance-heading">
      <header><div><p className="section-index">战略与再平衡</p><h3 id="rebalance-heading">阈值先于观点，安全闸门先于市场</h3></div><StatusBadge tone={plan.status === "within_band" ? "success" : plan.status === "rebalance_due" ? "warning" : "danger"}>{plan.status === "within_band" ? "区间内" : plan.status === "rebalance_due" ? "达到复核线" : "安全闸门拦截"}</StatusBadge></header>
      <p>{plan.explanation}</p><p className="rebalance-rule">绝对偏离 {formatRatio(plan.absolute_threshold)} · 相对偏离 {formatRatio(plan.relative_threshold)} · 战术最多 {formatRatio(plan.maximum_tactical_shift)} · 下次例行复核 {formatDate(plan.next_scheduled_review)}</p>
      <ol>{plan.lines.map((line) => <li key={line.asset_class} data-trigger={line.trigger}><strong>{line.asset_class_name}</strong><span>当前 {formatRatio(line.current_ratio)}</span><span>战略 {formatRatio(line.strategic_ratio)}</span><span>战术 {formatRatio(line.tactical_ratio)}</span><b>{line.action}</b></li>)}</ol>
    </section>
  );
}

const probePresets: Record<string, SuitabilityProbeRequest> = {
  leverage: { investment_amount: "100000.00", target_horizon_months: 120, requested_high_risk_ratio: "0.800000", leverage_ratio: "0.500000", concentration_ratio: "0.500000", requested_product_codes: ["MOCK-FUTURES-LAB-001"], purpose: "professional_hedge" },
  tuition: { investment_amount: "100000.00", target_horizon_months: 6, requested_high_risk_ratio: "1.000000", concentration_ratio: "1.000000", requested_product_codes: ["MOCK-INDEX-BROAD-001"], purpose: "tuition" },
  complex: { investment_amount: "1000000.00", target_horizon_months: 120, requested_high_risk_ratio: "0.800000", concentration_ratio: "1.000000", requested_product_codes: ["MOCK-TRUST-001"], purpose: "retirement" },
  emergency: { investment_amount: "50000.00", target_horizon_months: 120, requested_high_risk_ratio: "0.500000", concentration_ratio: "0.200000", requested_product_codes: ["MOCK-INDEX-BROAD-001"], purpose: "long_term_growth" },
  debt: { investment_amount: "50000.00", target_horizon_months: 120, requested_high_risk_ratio: "0.300000", leverage_ratio: "0.300000", concentration_ratio: "0.200000", requested_product_codes: ["MOCK-FUND-MONEY-001"], purpose: "long_term_growth" },
};

function SuitabilityProbePanel({ householdId, portfolio }: { householdId: string; portfolio: PortfolioResponse }) {
  const [preset, setPreset] = useState("leverage");
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<SuitabilityProbeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function runProbe() {
    setChecking(true); setError(null); setResult(null);
    try {
      const request = probePresets[preset] ?? probePresets.leverage;
      if (!request) throw new Error("适当性对抗预设缺失");
      setResult(await checkPortfolioSuitability(householdId, { ...request, analysis_date: portfolio.meta.analysis_date }));
    }
    catch { setError("对抗检查失败；未生成任何通过结论。"); }
    finally { setChecking(false); }
  }
  return (
    <section className="suitability-probe" aria-labelledby="probe-heading"><header><div><p className="section-index">适当性对抗台</p><h3 id="probe-heading">主动要求也不能绕过规则</h3></div></header><div className="probe-controls"><label><span>不适配案例</span><select value={preset} onChange={(event) => setPreset(event.target.value)}><option value="leverage">低风险路径要求高杠杆／期指</option><option value="tuition">半年后学费投入高波动资产</option><option value="complex">临退休集中复杂产品</option><option value="emergency">应急不足仍扩大投资</option><option value="debt">高负债仍加杠杆</option></select></label><Button type="button" loading={checking} onClick={() => void runProbe()}>运行并写入审计</Button></div>{error ? <p role="alert">{error}</p> : null}{result ? <div className="probe-result" data-decision={result.decision}><StatusBadge tone={badgeTone(result.decision)}>{decisionCopy[result.decision]}</StatusBadge><p>{result.explanation}</p><strong>失败检查 {result.failed_check_codes.length} 项</strong><code>审计 {result.audit_event_id.slice(0, 12)}</code></div> : null}</section>
  );
}

export function PortfolioPortalWorkspace({ view }: { view: "advisor" | "risk" }) {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetchHouseholds(controller.signal).then((items) => { setHouseholds(items); setHouseholdId((items.find((item) => item.code === "DEMO_B") ?? items[0])?.id ?? ""); }).catch(() => setError("无法读取家庭列表；未展示组合或适当性结论。"));
    return () => controller.abort();
  }, []);
  return <section className="portfolio-portal-wrapper"><label className="portal-household-control"><span>复核家庭</span><select value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0}>{households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}</select></label>{error ? <p role="alert">{error}</p> : null}{householdId ? <PortfolioWorkspace householdId={householdId} view={view} /> : null}</section>;
}
