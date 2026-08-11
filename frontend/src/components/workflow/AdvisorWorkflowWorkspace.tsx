import { useCallback, useEffect, useMemo, useState } from "react";
import {
  WorkflowApiError,
  createPlanWorkflow,
  fetchAdvisorDossier,
  fetchAdvisorHouseholds,
  fetchCurrentWorkflow,
  transitionWorkflow,
  type AdvisorCandidateSummary,
  type AdvisorDossier,
  type AdvisorHouseholdList,
  type PlanWorkflow,
  type WorkflowActionInput,
} from "../../api/reviewWorkflow";
import { usePortalContext } from "../../contexts/PortalContext";
import { formatDate, formatDateTime, formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { AdvisorFormalReportPanel } from "../report/FormalReportPortalPanels";
import {
  WorkflowBoundary,
  WorkflowStateRail,
  WorkflowVersionLedger,
} from "./WorkflowShared";
import { workflowStateLabels, workflowTone } from "./workflowLabels";

const candidateLabels = {
  conservative: "稳健",
  balanced: "基准",
  growth: "进取",
};

const decisionLabels = {
  allow: "可执行",
  downgrade: "降级后可用",
  reject: "拒绝",
  education_only: "仅教育与修复",
  escalate: "转人工复核",
};

export function AdvisorWorkflowWorkspace() {
  const { actor, setActorRole } = usePortalContext();
  const [queue, setQueue] = useState<AdvisorHouseholdList | null>(null);
  const [householdId, setHouseholdId] = useState("");
  const [dossier, setDossier] = useState<AdvisorDossier | null>(null);
  const [workflow, setWorkflow] = useState<PlanWorkflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<"conservative" | "balanced" | "growth">("balanced");
  const [communicationDraft, setCommunicationDraft] = useState("");
  const [reason, setReason] = useState("依据面谈记录与确定性测算推进方案");
  const [manualHighRisk, setManualHighRisk] = useState(false);

  const roleAllowed = actor.role === "advisor" || actor.role === "admin";

  const loadQueue = useCallback(async (signal?: AbortSignal) => {
    if (!roleAllowed) {
      setQueue(null);
      setDossier(null);
      setWorkflow(null);
      setLoading(false);
      setError("当前模拟账号没有客户经理工作台权限。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchAdvisorHouseholds(actor, signal);
      setQueue(payload);
      const preferred = payload.items.find((item) => item.household_code === "DEMO_B") ?? payload.items[0];
      setHouseholdId((current) => current || preferred?.household_id || "");
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError(loadError instanceof Error ? loadError.message : "客户队列读取失败。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [actor, roleAllowed]);

  const loadHousehold = useCallback(async (target: string, signal?: AbortSignal) => {
    if (!target || !roleAllowed) return;
    setLoading(true);
    setError(null);
    try {
      const [nextDossier, nextWorkflow] = await Promise.all([
        fetchAdvisorDossier(target, actor, signal),
        fetchCurrentWorkflow(target, actor, signal),
      ]);
      setDossier(nextDossier);
      setWorkflow(nextWorkflow);
      setCommunicationDraft(nextWorkflow?.current.communication_draft || nextDossier.suggested_communication_draft);
      setCandidate(nextWorkflow?.current.selected_candidate ?? "balanced");
      setManualHighRisk(Boolean(
        (nextWorkflow?.current.recommendation_snapshot.advisor_modification as Record<string, unknown> | undefined)?.manual_high_risk_confirmed,
      ));
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setDossier(null);
      setWorkflow(null);
      setError(loadError instanceof Error ? loadError.message : "面谈底稿读取失败。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [actor, roleAllowed]);

  useEffect(() => {
    const controller = new AbortController();
    setHouseholdId("");
    void loadQueue(controller.signal);
    return () => controller.abort();
  }, [loadQueue]);

  useEffect(() => {
    const controller = new AbortController();
    void loadHousehold(householdId, controller.signal);
    return () => controller.abort();
  }, [householdId, loadHousehold]);

  async function createWorkflow() {
    if (!householdId) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const next = await createPlanWorkflow(householdId, actor, reason);
      setWorkflow(next);
      setStatus("已创建不可变草稿 V1；下一步必须运行确定性计算。");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "创建方案失败。");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(input: Omit<WorkflowActionInput, "expected_version" | "reason">, message: string) {
    if (!workflow) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const next = await transitionWorkflow(workflow.workflow_id, actor, {
        ...input,
        expected_version: workflow.current.version_number,
        reason,
      });
      setWorkflow(next);
      setCommunicationDraft(next.current.communication_draft || communicationDraft);
      setStatus(`${message} 当前为 V${next.current.version_number}。`);
      const refreshed = await fetchAdvisorHouseholds(actor);
      setQueue(refreshed);
    } catch (actionError) {
      const prefix = actionError instanceof WorkflowApiError && actionError.status === 403 ? "权限拦截：" : "";
      setError(prefix + (actionError instanceof Error ? actionError.message : "操作失败。"));
    } finally {
      setBusy(false);
    }
  }

  const selectedCandidate = useMemo(
    () => dossier?.candidates.find((item) => item.candidate_type === candidate) ?? null,
    [candidate, dossier],
  );

  if (!roleAllowed) {
    return (
      <section className="workflow-permission-state" role="alert">
        <p className="section-index">RBAC · PermissionDenied</p>
        <h2>当前账号不能操作客户经理工作台</h2>
        <p>客户和合规审核员不能创建、计算、修改或提交客户经理方案。</p>
        <Button type="button" onClick={() => setActorRole("advisor")}>切换为客户经理演示账号</Button>
      </section>
    );
  }

  return (
    <section className="advisor-workflow" aria-labelledby="advisor-workflow-heading">
      <header className="workflow-portal-heading">
        <div>
          <p className="page-kicker">共享方案闭环 · 客户经理权限</p>
          <h2 id="advisor-workflow-heading">从面谈底稿推进到合规与客户确认</h2>
          <p>客户队列、三方案、沟通稿、修改理由、签署与复盘读取同一 workflow id。</p>
        </div>
        <dl>
          <div><dt>模拟账号</dt><dd>{actor.label}</dd></div>
          <div><dt>计算边界</dt><dd>确定性工具</dd></div>
          <div><dt>文案边界</dt><dd>可编辑 Mock 模板</dd></div>
        </dl>
      </header>

      {error ? <div className="workflow-alert" data-tone="danger" role="alert"><strong>工作台未推进</strong><p>{error}</p></div> : null}
      {status ? <div className="workflow-alert" data-tone="success" role="status"><strong>版本已记录</strong><p>{status}</p></div> : null}

      <section className="advisor-queue" aria-labelledby="advisor-queue-heading">
        <header className="section-header-row">
          <div><p className="section-index">客户队列</p><h3 id="advisor-queue-heading">家庭摘要与闭环状态</h3></div>
          <span>{queue ? `${queue.items.length} 个合成家庭` : "等待确定性队列"}</span>
        </header>
        {loading && !queue ? <p className="workflow-loading" role="status">正在核对客户、异常、目标冲突与方案状态…</p> : null}
        {queue ? (
          <div className="data-table-wrap" tabIndex={0} role="region" aria-label="客户经理家庭队列，可横向滚动">
            <table className="data-table advisor-queue-table">
              <thead><tr><th>家庭</th><th>生命周期 / 地区</th><th>净资产 / 年结余</th><th>异常 / 冲突</th><th>方案 / 签署</th><th><span className="visually-hidden">操作</span></th></tr></thead>
              <tbody>{queue.items.map((item) => (
                <tr key={item.household_id} data-selected={item.household_id === householdId || undefined}>
                  <td><strong>{item.household_name}</strong><small>{item.household_code} · 合成 Mock</small></td>
                  <td>{formatDomainLabel(item.lifecycle_stage)}<small>{item.region} · 数据日 {formatDate(item.data_as_of)}</small></td>
                  <td className="numeric-cell">{formatMoney(item.net_worth)}<small>年结余 {formatMoney(item.annual_surplus)}</small></td>
                  <td><StatusBadge tone={item.highest_attention === "critical" ? "danger" : item.highest_attention === "normal" ? "success" : "warning"}>{item.anomaly_count} 异常</StatusBadge><small>{item.goal_conflict_count} 个目标冲突</small></td>
                  <td>{item.workflow_state ? workflowStateLabels[item.workflow_state] : "尚未建案"}<small>{item.workflow_version ? `V${item.workflow_version}` : "无版本"} · {item.signature_status}</small></td>
                  <td><button className="text-button" type="button" aria-pressed={item.household_id === householdId} onClick={() => setHouseholdId(item.household_id)}>打开底稿</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : null}
      </section>

      {dossier ? (
        <>
          <div className="advisor-dossier-grid">
            <section aria-labelledby="premeeting-heading">
              <header><p className="section-index">面谈前准备</p><h3 id="premeeting-heading">{dossier.household.household_name}</h3><p>生成 {formatDateTime(dossier.generated_at)}，所有金额来自当前家庭事实。</p></header>
              <ol className="premeeting-list">{dossier.premeeting_questions.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ol>
            </section>
            <section aria-labelledby="exception-heading">
              <header><p className="section-index">异常与目标冲突</p><h3 id="exception-heading">先处理阻塞，再谈配置</h3></header>
              {dossier.financial_anomalies.length === 0 && dossier.goal_conflicts.length === 0 ? <p className="empty-state">没有发现需要面谈核实的异常或冲突。</p> : (
                <ul className="advisor-exception-list">
                  {dossier.financial_anomalies.slice(0, 4).map((item, index) => <li key={`a-${index}`}><strong>{String(item.title ?? "财务异常")}</strong><span>{String(item.detail ?? item.action ?? "请复核底稿")}</span></li>)}
                  {dossier.goal_conflicts.slice(0, 3).map((item, index) => <li key={`g-${index}`}><strong>{String(item.title ?? "目标冲突")}</strong><span>{String(item.detail ?? "请调整期限或投入")}</span></li>)}
                </ul>
              )}
            </section>
          </div>

          <AdvisorFormalReportPanel householdId={householdId} analysisDate={dossier.household.data_as_of} />

          <CandidateMatrix candidates={dossier.candidates} candidate={candidate} onCandidate={setCandidate} />

          <section className="advisor-evidence-grid" aria-label="产品、风险与 Mock 接口证据">
            <article><p className="section-index">产品类型适配理由</p><h3>{selectedCandidate ? selectedCandidate.name : "请选择候选"}</h3><ul>{selectedCandidate?.product_type_reasons.map((item) => <li key={item}>{item}</li>)}</ul></article>
            <article><p className="section-index">风险与流动性提示</p><h3>执行前人工核对</h3><ul>{dossier.risk_and_liquidity_notes.map((item) => <li key={item}>{item}</li>)}</ul></article>
          </section>

          <MockBankLedger dossier={dossier} />

          <section className="workflow-action-panel" aria-labelledby="advisor-action-heading">
            <header className="section-header-row"><div><p className="section-index">建议、沟通与提交</p><h3 id="advisor-action-heading">每次修改都创建新版本</h3></div>{workflow ? <StatusBadge tone={workflowTone(workflow.current.state)}>{workflowStateLabels[workflow.current.state]} · V{workflow.current.version_number}</StatusBadge> : <StatusBadge tone="info">尚未建案</StatusBadge>}</header>
            <label><span>本次修改／推进理由</span><input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
            {!workflow ? <Button type="button" loading={busy} onClick={() => void createWorkflow()}>创建方案草稿</Button> : (
              <>
                <WorkflowStateRail workflow={workflow} />
                <AdvisorActions
                  workflow={workflow}
                  candidate={candidate}
                  draft={communicationDraft}
                  manualHighRisk={manualHighRisk}
                  busy={busy}
                  onDraft={setCommunicationDraft}
                  onManualHighRisk={setManualHighRisk}
                  onAction={runAction}
                />
                <WorkflowVersionLedger workflow={workflow} />
              </>
            )}
          </section>

          <section className="review-reminders" aria-labelledby="review-reminder-heading">
            <header className="section-header-row"><div><p className="section-index">月度复盘与再平衡</p><h3 id="review-reminder-heading">未来 12 个月提醒</h3></div><span>不自动交易</span></header>
            <ol>{dossier.monthly_review_reminders.map((item, index) => <li key={`${index}-${String(item.code)}`}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{String(item.title ?? "月度复盘")}</strong><p>{String(item.detail ?? item.why ?? "核对家庭变化")}</p></div><small>{String(item.due_date ?? "按月")}</small></li>)}</ol>
          </section>
          <WorkflowBoundary />
        </>
      ) : !loading ? <p className="empty-state">请选择可访问家庭；系统不会用前端夹具补造面谈金额。</p> : null}
    </section>
  );
}

function CandidateMatrix({ candidates, candidate, onCandidate }: { candidates: AdvisorCandidateSummary[]; candidate: "conservative" | "balanced" | "growth"; onCandidate: (candidate: "conservative" | "balanced" | "growth") => void }) {
  return (
    <section aria-labelledby="advisor-candidate-heading">
      <header className="section-header-row"><div><p className="section-index">三方案对比</p><h3 id="advisor-candidate-heading">只比较通过同一分母与规则计算的候选</h3></div><span>收益为假设，不是承诺</span></header>
      <div className="data-table-wrap" tabIndex={0} role="region" aria-label="顾问端三方案对比，可横向滚动">
        <table className="data-table candidate-review-table"><thead><tr><th>选择 / 方案</th><th>适当性决定</th><th>长期资金</th><th>假设名义收益</th><th>最大回撤估计</th><th>压力损失</th><th>流动性 / 年费用</th></tr></thead><tbody>{candidates.map((item) => (
          <tr key={item.candidate_type} data-selected={candidate === item.candidate_type || undefined}>
            <td><label className="table-radio"><input type="radio" name="advisor-candidate" value={item.candidate_type} checked={candidate === item.candidate_type} onChange={() => onCandidate(item.candidate_type)} /><span><strong>{candidateLabels[item.candidate_type]}</strong><small>{item.name}</small></span></label></td>
            <td><StatusBadge tone={item.decision === "allow" ? "success" : item.decision === "reject" ? "danger" : "warning"}>{decisionLabels[item.decision]}</StatusBadge></td>
            <td className="numeric-cell">{formatMoney(item.investment_amount)}</td>
            <td className="numeric-cell">{formatRatio(item.expected_nominal_return)}</td>
            <td className="numeric-cell">{formatRatio(item.max_drawdown_estimate)}</td>
            <td className="numeric-cell">{formatMoney(item.extreme_loss_amount)}</td>
            <td>{formatRatio(item.liquidity_score)}<small>{formatMoney(item.annual_fee_estimate)} / 年</small></td>
          </tr>
        ))}</tbody></table>
      </div>
    </section>
  );
}

function AdvisorActions({ workflow, candidate, draft, manualHighRisk, busy, onDraft, onManualHighRisk, onAction }: { workflow: PlanWorkflow; candidate: "conservative" | "balanced" | "growth"; draft: string; manualHighRisk: boolean; busy: boolean; onDraft: (value: string) => void; onManualHighRisk: (value: boolean) => void; onAction: (input: Omit<WorkflowActionInput, "expected_version" | "reason">, message: string) => Promise<void> }) {
  const next = new Set(workflow.next_actions);
  return (
    <div className="advisor-action-body">
      {next.has("calculate") ? <div className="workflow-next-action"><p>草稿仅保存任务边界，尚无金额或配置。</p><Button type="button" loading={busy} onClick={() => void onAction({ action: "calculate" }, "确定性金额、比率和三候选已写入")}>运行确定性计算</Button></div> : null}
      {next.has("suitability_check") ? <div className="workflow-next-action"><p>计算完成后必须逐一执行家庭安全、客户和产品三道闸门。</p><Button type="button" loading={busy} onClick={() => void onAction({ action: "suitability_check" }, "三道适当性闸门已写入")}>执行三道闸门</Button></div> : null}
      {next.has("advisor_review") || next.has("revise_advice") || next.has("edit_communication") ? (
        <div className="advisor-draft-editor">
          <label><span>客户沟通草稿，可编辑</span><textarea rows={7} value={draft} onChange={(event) => onDraft(event.target.value)} /><small>不得添加保本、保证收益、稳赚、零风险或无来源政策断言；关键数字必须与工具账本一致。</small></label>
          <label className="workflow-check"><input type="checkbox" checked={manualHighRisk} onChange={(event) => onManualHighRisk(event.target.checked)} /><span><strong>我已人工核对较高风险产品类型</strong><small>智能辅助不替代客户经理判断；没有较高风险类型时也可保留本次人工核对记录。</small></span></label>
          <div className="workflow-action-row">
            {next.has("advisor_review") ? <Button type="button" loading={busy} onClick={() => void onAction({ action: "advisor_review", selected_candidate: candidate, communication_draft: draft, manual_high_risk_confirmed: manualHighRisk, advisor_note: "已核对三方案、流动性与风险" }, "客户经理人工复核已记录")}>完成客户经理复核</Button> : null}
            {next.has("revise_advice") ? <Button type="button" variant="secondary" loading={busy} onClick={() => void onAction({ action: "revise_advice", selected_candidate: candidate, communication_draft: draft, manual_high_risk_confirmed: manualHighRisk, advisor_note: "根据面谈修改候选与解释" }, "建议修改已保存")}>保存建议修改</Button> : null}
            {next.has("edit_communication") ? <Button type="button" variant="secondary" loading={busy} onClick={() => void onAction({ action: "edit_communication", communication_draft: draft }, "沟通稿新版本已保存")}>仅保存沟通稿</Button> : null}
          </div>
        </div>
      ) : null}
      {next.has("submit_compliance") ? <div className="workflow-next-action"><p>提交后合规端读取同一版本；再次编辑会自动撤回本次提交并生成新版本。</p><Button type="button" loading={busy} onClick={() => void onAction({ action: "submit_compliance" }, "当前版本已提交合规队列")}>提交合规审核</Button></div> : null}
      {workflow.current.state === "advisor_reviewed" && workflow.current.submitted_for_compliance ? <p className="workflow-waiting" role="status">当前版本已提交合规，等待通过、退回或人工复核决定。</p> : null}
      {workflow.current.state === "compliance_reviewed" ? <p className="workflow-waiting" role="status">合规已通过，等待客户在客户端逐项确认与演示签署。</p> : null}
      {next.has("activate") ? <div className="workflow-next-action"><p>客户已确认风险、Mock 与非保本边界；激活只表示规划版本生效，不代表自动交易。</p><Button type="button" loading={busy} onClick={() => void onAction({ action: "activate" }, "方案已激活")}>激活已确认方案</Button></div> : null}
      {workflow.current.state === "active" ? <p className="workflow-waiting" role="status">方案已生效。按月复盘，家庭数据、目标或授权变化时建立新方案，不覆盖历史。</p> : null}
    </div>
  );
}

function MockBankLedger({ dossier }: { dossier: AdvisorDossier }) {
  return (
    <details className="mock-bank-ledger">
      <summary>查看 Mock 银行接口适配层（8 类）</summary>
      <header><StatusBadge tone="info">Mock · 非真实银行连接</StatusBadge><span>{dossier.mock_bank.adapter_version} · 数据日 {formatDate(dossier.mock_bank.data_as_of)}</span></header>
      <div className="mock-interface-grid">{dossier.mock_bank.interfaces.map((item) => (
        <article key={item.code}><span>{item.code}</span><strong>{item.label}</strong><small>{item.status === "available" ? `${item.entries.length} 条合成记录` : "无合成记录"}</small></article>
      ))}</div>
      <p>{dossier.mock_bank.boundary_note}</p>
      <p><strong>信用卡额度计入资产：</strong>否。对账资产 {formatMoney(dossier.mock_bank.reconciled_asset_total)}，负债 {formatMoney(dossier.mock_bank.reconciled_liability_total)}。</p>
    </details>
  );
}
