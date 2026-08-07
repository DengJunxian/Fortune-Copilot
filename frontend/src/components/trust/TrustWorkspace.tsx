import { useEffect, useMemo, useState } from "react";
import {
  confirmIntakeDraft,
  createIntakeDraft,
  fetchAgentCatalog,
  fetchHouseholdGraph,
  fetchKnowledgeCatalog,
  fetchLatestOrchestration,
  fetchShanghaiGraph,
  runTrustOrchestration,
  searchKnowledge,
  type AgentCatalog,
  type GraphLane,
  type HouseholdGraph,
  type IntakeDraft,
  type KnowledgeCatalog,
  type KnowledgeSearch,
  type Orchestration,
} from "../../api/trust";
import { fetchHouseholds, type HouseholdSummary } from "../../api/financial";
import { formatDate, formatMoney, safeExternalUrl } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

type TrustView = "client" | "advisor" | "risk";
type GraphMode = "shanghai" | "household";

const DEFAULT_POLICY_QUERY = "个人养老金每年缴费限额和家庭适配需要核对什么?";
const DEFAULT_INTAKE_TEXT = "我和爱人每月工资合计三万元，房贷八千，孩子上幼儿园";
const laneLabels: Record<GraphLane, string> = {
  family: "家庭关系",
  facts: "事实底稿",
  goals: "目标期限",
  controls: "风险约束",
  knowledge: "政策产品",
};
const laneOrder: GraphLane[] = ["family", "facts", "goals", "controls", "knowledge"];

export function TrustWorkspace({ householdId, view = "client" }: { householdId: string; view?: TrustView }) {
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [searchResult, setSearchResult] = useState<KnowledgeSearch | null>(null);
  const [shanghaiGraph, setShanghaiGraph] = useState<HouseholdGraph | null>(null);
  const [householdGraph, setHouseholdGraph] = useState<HouseholdGraph | null>(null);
  const [agentCatalog, setAgentCatalog] = useState<AgentCatalog | null>(null);
  const [orchestration, setOrchestration] = useState<Orchestration | null>(null);
  const [query, setQuery] = useState(DEFAULT_POLICY_QUERY);
  const [intakeText, setIntakeText] = useState(DEFAULT_INTAKE_TEXT);
  const [draft, setDraft] = useState<IntakeDraft | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [selectedFields, setSelectedFields] = useState<Record<string, boolean>>({});
  const [graphMode, setGraphMode] = useState<GraphMode>("shanghai");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const orchestrationRequest = view === "risk"
      ? fetchLatestOrchestration(householdId, controller.signal)
      : Promise.resolve(null);
    Promise.allSettled([
      fetchKnowledgeCatalog(controller.signal),
      searchKnowledge(DEFAULT_POLICY_QUERY, controller.signal),
      fetchShanghaiGraph(controller.signal),
      fetchHouseholdGraph(householdId, controller.signal),
      fetchAgentCatalog(controller.signal),
      orchestrationRequest,
    ]).then((results) => {
      if (controller.signal.aborted) return;
      const [catalogResult, searchResponse, shanghaiResult, householdResult, agentsResult, runResult] = results;
      if (catalogResult.status === "fulfilled") setCatalog(catalogResult.value);
      if (searchResponse.status === "fulfilled") setSearchResult(searchResponse.value);
      if (shanghaiResult.status === "fulfilled") setShanghaiGraph(shanghaiResult.value);
      if (householdResult.status === "fulfilled") setHouseholdGraph(householdResult.value);
      if (agentsResult.status === "fulfilled") setAgentCatalog(agentsResult.value);
      if (runResult.status === "fulfilled") setOrchestration(runResult.value);
      if (results.every((result) => result.status === "rejected")) {
        setError("可信 AI 服务不可用；财务计算、规划和 Mock 主流程仍可独立运行。");
      }
      setLoading(false);
    });
    return () => controller.abort();
  }, [householdId, view]);

  const graph = graphMode === "shanghai" ? shanghaiGraph : householdGraph;

  async function submitSearch() {
    if (query.trim().length < 2) return;
    setSearching(true);
    setError(null);
    try {
      setSearchResult(await searchKnowledge(query.trim()));
    } catch {
      setError("受控知识检索失败；系统没有使用模型常识补写政策。");
    } finally {
      setSearching(false);
    }
  }

  async function parseDraft() {
    if (intakeText.trim().length < 2) return;
    setParsing(true);
    setError(null);
    try {
      const nextDraft = await createIntakeDraft(householdId, intakeText.trim());
      setDraft(nextDraft);
      setDraftValues(Object.fromEntries(nextDraft.extracted_fields.map((item) => [item.code, item.value])));
      setSelectedFields(Object.fromEntries(nextDraft.extracted_fields.map((item) => [item.code, false])));
    } catch {
      setError("自然语言草稿生成失败；没有写入或覆盖家庭事实。");
    } finally {
      setParsing(false);
    }
  }

  async function confirmDraftFields() {
    if (!draft) return;
    const confirmedValues = Object.fromEntries(
      Object.entries(draftValues).filter(([code]) => selectedFields[code]),
    );
    if (Object.keys(confirmedValues).length === 0) {
      setError("请先逐项勾选已经核对的字段。");
      return;
    }
    setConfirming(true);
    setError(null);
    try {
      setDraft(await confirmIntakeDraft(draft.draft_id, confirmedValues));
    } catch {
      setError("字段确认失败；草稿没有写入正式家庭事实。");
    } finally {
      setConfirming(false);
    }
  }

  async function executeOrchestration() {
    setRunning(true);
    setError(null);
    try {
      setOrchestration(await runTrustOrchestration(householdId));
    } catch {
      setError("可信编排运行失败；未绕过适当性或数值校验生成替代结论。");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="trust-workspace" data-view={view} aria-labelledby={`trust-heading-${view}`}>
      <header className="trust-header">
        <div>
          <p className="section-index">可信 AI / 可追溯证据</p>
          <h2 id={`trust-heading-${view}`}>政策、关系与智能体都要留下证据</h2>
          <p>知识只来自受控快照；数字只来自确定性工具；缺失、过期、隔离和高风险结果都会明确阻断。</p>
        </div>
        <aside className="trust-boundary" aria-label="可信 AI 边界">
          <strong>{catalog ? `知识更新 ${formatDate(catalog.updated_at)}` : "等待知识目录"}</strong>
          <span>Mock 可完整运行 · 不依赖外部模型或网络</span>
        </aside>
      </header>

      {loading ? <TrustLoading /> : null}
      {error ? <p className="trust-error" role="alert">{error}</p> : null}
      {!loading && catalog ? <KnowledgeLedger catalog={catalog} query={query} onQuery={setQuery} searching={searching} onSearch={() => void submitSearch()} result={searchResult} /> : null}

      {!loading && (view === "client" || view === "advisor") ? (
        <IntakeLedger
          text={intakeText}
          onText={setIntakeText}
          parsing={parsing}
          onParse={() => void parseDraft()}
          draft={draft}
          values={draftValues}
          onValue={(code, value) => setDraftValues((current) => ({ ...current, [code]: value }))}
          selected={selectedFields}
          onSelected={(code, value) => setSelectedFields((current) => ({ ...current, [code]: value }))}
          confirming={confirming}
          onConfirm={() => void confirmDraftFields()}
        />
      ) : null}

      {!loading && (shanghaiGraph || householdGraph) ? (
        <GraphLedger graph={graph} mode={graphMode} onMode={setGraphMode} hasHousehold={Boolean(householdGraph)} />
      ) : null}

      {!loading && view === "risk" ? (
        <AgentChain
          catalog={agentCatalog}
          run={orchestration}
          running={running}
          onRun={() => void executeOrchestration()}
        />
      ) : null}
    </section>
  );
}

function TrustLoading() {
  return (
    <div className="trust-loading" aria-live="polite">
      <span className="loading-mark" aria-hidden="true" />
      <div><strong>正在核对知识版本和图谱关系</strong><p>不会在等待时显示缓存政策或伪造智能体结果。</p></div>
    </div>
  );
}

function KnowledgeLedger({ catalog, query, onQuery, searching, onSearch, result }: {
  catalog: KnowledgeCatalog;
  query: string;
  onQuery: (value: string) => void;
  searching: boolean;
  onSearch: () => void;
  result: KnowledgeSearch | null;
}) {
  return (
    <section className="trust-section knowledge-ledger" aria-labelledby="knowledge-heading">
      <header>
        <div><p className="section-index">01 / 受控 RAG</p><h3 id="knowledge-heading">先筛时效和适用范围，再组织解释</h3></div>
        <dl className="knowledge-stats">
          <div><dt>文档 / 切片</dt><dd>{catalog.document_count} / {catalog.chunk_count}</dd></div>
          <div><dt>隔离切片</dt><dd>{catalog.quarantined_chunk_count}</dd></div>
          <div><dt>运行时网络</dt><dd>{catalog.runtime_network_required ? "需要" : "不需要"}</dd></div>
        </dl>
      </header>
      <form className="knowledge-query" onSubmit={(event) => { event.preventDefault(); onSearch(); }}>
        <label htmlFor="policy-query"><span>政策或产品规则问题</span><input id="policy-query" value={query} onChange={(event) => onQuery(event.target.value)} minLength={2} required /></label>
        <Button type="submit" loading={searching}>检索受控依据</Button>
      </form>
      {result ? (
        <div className="knowledge-result" data-insufficient={result.insufficient_information}>
          <div className="knowledge-answer">
            <StatusBadge tone={result.insufficient_information ? "warning" : "info"}>{result.insufficient_information ? "依据不足" : "已找到受控依据"}</StatusBadge>
            <p>{result.answer}</p>
            <small>查询日 {formatDate(result.as_of_date)} · 过期过滤 {result.filtered_expired_count} · 隔离过滤 {result.filtered_quarantined_count} · {result.retrieval_version}</small>
          </div>
          <ol className="citation-ledger" aria-label="政策引用">
            {result.citations.map((citation, index) => (
              <li key={citation.citation_id}>
                <span className="citation-number">{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{citation.title}</strong><span>{citation.issuing_authority} · {citation.document_version}</span><span>发布 {formatDate(citation.publication_date)} · 生效 {formatDate(citation.effective_date)} · 核验 {citation.last_verified_date ? formatDate(citation.last_verified_date) : "待核验"}</span><small>{citation.paragraph_ref} · {citation.applicable_regions.join("、")} · {citation.source_type}</small></div>
                {safeExternalUrl(citation.source_uri) ? <a href={safeExternalUrl(citation.source_uri) ?? undefined} target="_blank" rel="noopener noreferrer">查看来源<span className="visually-hidden">：{citation.title}</span></a> : <span>本地受控快照</span>}
              </li>
            ))}
          </ol>
        </div>
      ) : <p className="trust-empty">尚未运行政策检索。</p>}
    </section>
  );
}

function IntakeLedger({ text, onText, parsing, onParse, draft, values, onValue, selected, onSelected, confirming, onConfirm }: {
  text: string;
  onText: (value: string) => void;
  parsing: boolean;
  onParse: () => void;
  draft: IntakeDraft | null;
  values: Record<string, string>;
  onValue: (code: string, value: string) => void;
  selected: Record<string, boolean>;
  onSelected: (code: string, value: boolean) => void;
  confirming: boolean;
  onConfirm: () => void;
}) {
  return (
    <section className="trust-section intake-ledger" aria-labelledby="intake-heading">
      <header><div><p className="section-index">02 / 自然语言录入</p><h3 id="intake-heading">先形成草稿，再逐项确认</h3></div><p>原文只保存哈希和脱敏预览；草稿不会直接改写家庭事实。</p></header>
      <div className="intake-entry">
        <label htmlFor="intake-text"><span>家庭描述</span><textarea id="intake-text" value={text} onChange={(event) => onText(event.target.value)} rows={3} /></label>
        <Button type="button" loading={parsing} onClick={onParse}>解析为待确认草稿</Button>
      </div>
      {draft ? (
        <div className="draft-review">
          <div className="draft-meta"><StatusBadge tone={draft.status === "confirmed" ? "success" : "warning"}>{draft.status === "confirmed" ? "提取项已确认" : "等待逐项确认"}</StatusBadge><code>{draft.parser_version}</code><span>原文哈希 {draft.source_text_hash.slice(0, 12)}</span></div>
          <fieldset disabled={draft.status === "confirmed"}>
            <legend>勾选并核对每一项</legend>
            {draft.extracted_fields.map((field) => (
              <div className="draft-field" key={field.code}>
                <input id={`confirm-${field.code}`} type="checkbox" checked={field.confirmed || Boolean(selected[field.code])} disabled={field.confirmed} onChange={(event) => onSelected(field.code, event.target.checked)} />
                <label htmlFor={`confirm-${field.code}`}><strong>{field.label}</strong><small>原文：{field.evidence}</small></label>
                <input aria-label={`${field.label}确认值`} value={values[field.code] ?? field.value} disabled={field.confirmed} onChange={(event) => onValue(field.code, event.target.value)} />
                <span>{field.unit ?? field.value_type} · 置信度 {(Number(field.confidence) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </fieldset>
          {draft.status !== "confirmed" ? <Button type="button" variant="secondary" loading={confirming} onClick={onConfirm}>确认已勾选字段</Button> : null}
          <details className="missing-fields"><summary>仍缺少 {draft.missing_fields.length} 项，不会自动猜测</summary><ul>{draft.missing_fields.map((field) => <li key={field.code}><strong>{field.label}</strong><span>{field.reason} · 用于 {field.required_for.join("、")}</span></li>)}</ul></details>
          <p className="boundary-copy">{draft.boundary_note}</p>
        </div>
      ) : null}
    </section>
  );
}

function graphPositions(graph: HouseholdGraph) {
  const positions = new Map<string, { x: number; y: number }>();
  laneOrder.forEach((lane, laneIndex) => {
    graph.nodes.filter((node) => node.lane === lane).forEach((node, rowIndex) => {
      positions.set(node.id, { x: 24 + laneIndex * 230, y: 70 + rowIndex * 66 });
    });
  });
  return positions;
}

function GraphLedger({ graph, mode, onMode, hasHousehold }: {
  graph: HouseholdGraph | null;
  mode: GraphMode;
  onMode: (mode: GraphMode) => void;
  hasHousehold: boolean;
}) {
  const positions = useMemo(() => graph ? graphPositions(graph) : new Map<string, { x: number; y: number }>(), [graph]);
  if (!graph) return <section className="trust-section"><p className="trust-empty">关系图谱暂不可用，没有补画推导。</p></section>;
  const maximumRows = Math.max(...laneOrder.map((lane) => graph.nodes.filter((node) => node.lane === lane).length));
  const height = Math.max(460, 110 + maximumRows * 66);
  return (
    <section className="trust-section graph-ledger" aria-labelledby="graph-heading">
      <header>
        <div><p className="section-index">03 / 关系图谱</p><h3 id="graph-heading">从家庭事实走到约束，不从标签跳到建议</h3></div>
        <div className="graph-mode" role="group" aria-label="图谱数据范围"><button type="button" aria-pressed={mode === "shanghai"} onClick={() => onMode("shanghai")}>上海推导示例</button><button type="button" aria-pressed={mode === "household"} disabled={!hasHousehold} onClick={() => onMode("household")}>当前家庭关系</button></div>
      </header>
      <div className="graph-contract"><span>{graph.synthetic ? "完全合成数据" : "已授权家庭数据"}</span><span>{graph.graph_version}</span><span>推导日 {formatDate(graph.as_of_date)}</span><span>{graph.calculation_source}</span></div>
      <figure className="relationship-graph">
        <figcaption><strong>{graph.title}</strong><span>{graph.subtitle}</span></figcaption>
        <div className="relationship-canvas" tabIndex={0} role="region" aria-label="可横向滚动的家庭知识图谱">
          <svg viewBox={`0 0 1180 ${height}`} role="img" aria-labelledby="graph-svg-title" aria-describedby="graph-svg-desc">
            <title id="graph-svg-title">{graph.title}</title>
            <desc id="graph-svg-desc">五列关系图，依次展示家庭关系、事实底稿、目标期限、风险约束和政策产品；下方提供完整数据表。</desc>
            <defs><marker id={`graph-arrow-${mode}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>
            {laneOrder.map((lane, index) => <g key={lane}><text className="graph-lane-label" x={24 + index * 230} y={30}>{laneLabels[lane]}</text><line className="graph-lane-rule" x1={24 + index * 230} x2={214 + index * 230} y1={42} y2={42} /></g>)}
            {graph.edges.map((edge) => {
              const source = positions.get(edge.source); const target = positions.get(edge.target);
              if (!source || !target) return null;
              return <line key={edge.id} className="graph-edge" x1={source.x + 95} y1={source.y + 23} x2={target.x + 95} y2={target.y + 23} markerEnd={`url(#graph-arrow-${mode})`} />;
            })}
            {graph.nodes.map((node) => {
              const position = positions.get(node.id); if (!position) return null;
              return <g key={node.id} className="graph-node" data-lane={node.lane} transform={`translate(${position.x} ${position.y})`}><rect width="190" height="46" rx="6" /><text x="10" y="19">{node.label.slice(0, 14)}</text><text className="graph-node-type" x="10" y="35">{node.node_type}</text></g>;
            })}
          </svg>
        </div>
        <details className="graph-data"><summary>查看可访问关系数据表（{graph.nodes.length} 节点 / {graph.edges.length} 关系）</summary><div className="data-table-wrap" tabIndex={0} role="region" aria-label="图谱节点数据"><table className="data-table"><thead><tr><th>节点</th><th>类型</th><th>数据层</th><th>来源实体</th><th>计算来源</th></tr></thead><tbody>{graph.nodes.map((node) => <tr key={node.id}><td>{node.label}</td><td>{node.node_type}</td><td>{laneLabels[node.lane]}</td><td>{node.source_entity_type}</td><td>{node.calculation_source}</td></tr>)}</tbody></table></div></details>
      </figure>
      <ol className="inference-ledger">
        {graph.inferences.map((inference, index) => <li key={inference.code}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{inference.title}</strong><p>{inference.conclusion}</p><small>{inference.rule} · 证据节点 {inference.evidence_node_ids.length} 个</small></div>{inference.human_review_required ? <StatusBadge tone="warning">需人工复核</StatusBadge> : <StatusBadge tone="info">确定性推导</StatusBadge>}</li>)}
      </ol>
    </section>
  );
}

function AgentChain({ catalog, run, running, onRun }: { catalog: AgentCatalog | null; run: Orchestration | null; running: boolean; onRun: () => void }) {
  return (
    <section className="trust-section agent-chain" aria-labelledby="agent-chain-heading">
      <header><div><p className="section-index">04 / 九智能体状态机</p><h3 id="agent-chain-heading">每一步都要有工具、Schema、禁令和审计</h3></div><Button type="button" loading={running} onClick={onRun}>运行可信编排</Button></header>
      {catalog ? <div className="agent-contract"><span>{catalog.agent_count} 类智能体</span><span>{catalog.orchestrator_version}</span><span>{catalog.hard_gates.length} 道硬门禁</span></div> : null}
      {run ? (
        <>
          <div className="run-verdict"><StatusBadge tone={run.status === "completed" ? "success" : run.status === "blocked" ? "danger" : "warning"}>{run.status === "completed" ? "终检通过" : run.status === "blocked" ? "输出已阻断" : "降级完成"}</StatusBadge><strong>运行 {run.run_id.slice(0, 12)}</strong><span>{run.provider_mode} · 数字引用 {run.numeric_ledger.length} · 政策切片 {run.citation_chunk_ids.length}</span></div>
          <ol className="agent-timeline">
            {run.steps.map((step) => <li key={step.step_id} data-status={step.status}><span className="agent-sequence">{String(step.sequence).padStart(2, "0")}</span><div><strong>{step.agent_name}</strong><span>{step.input_schema_name} → {step.output_schema_name}</span><small>{step.tool_calls.map((tool) => tool.tool).join(" · ")} · 禁止事项已核 {step.prohibitions_checked.length} 项 · 超时预算 {step.timeout_seconds}s</small></div><StatusBadge tone={step.status === "completed" ? "success" : step.status === "blocked" ? "danger" : "warning"}>{step.status === "completed" ? "已审计" : step.status === "blocked" ? "阻断" : "降级"}</StatusBadge></li>)}
          </ol>
          <details className="numeric-ledger"><summary>数字工具账本（{run.numeric_ledger.length} 项）</summary><div className="data-table-wrap" tabIndex={0} role="region" aria-label="智能体数字工具账本"><table className="data-table"><thead><tr><th>引用代码</th><th>值</th><th>单位</th><th>确定性工具</th><th>路径</th></tr></thead><tbody>{run.numeric_ledger.map((item) => <tr key={item.code}><td><code>{item.code}</code></td><td className="numeric-cell">{item.unit.startsWith("CNY") ? formatMoney(item.value) : item.value}</td><td>{item.unit}</td><td>{item.source_tool}</td><td><code>{item.source_path}</code></td></tr>)}</tbody></table></div></details>
          <p className="boundary-copy">{run.boundary_note}</p>
        </>
      ) : <div className="trust-empty"><strong>尚无真实调用链</strong><p>点击“运行可信编排”后才会依次执行九个工具受限步骤；目录标签不会冒充运行结果。</p></div>}
    </section>
  );
}

export function TrustPortalWorkspace({ view }: { view: "advisor" | "risk" }) {
  const [households, setHouseholds] = useState<HouseholdSummary[]>([]);
  const [householdId, setHouseholdId] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetchHouseholds(controller.signal)
      .then((items) => {
        setHouseholds(items);
        setHouseholdId((items.find((item) => item.code === "DEMO_B") ?? items[0])?.id ?? "");
      })
      .catch(() => setError("无法读取家庭列表；未运行可信编排或家庭图谱。"));
    return () => controller.abort();
  }, []);
  return (
    <section className="trust-portal-wrapper">
      <label className="portal-household-control"><span>可信 AI 复核家庭</span><select value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0}>{households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}</select></label>
      {error ? <p role="alert">{error}</p> : null}
      {householdId ? <TrustWorkspace householdId={householdId} view={view} /> : null}
    </section>
  );
}
