import { useCallback, useEffect, useState } from "react";
import {
  WorkflowApiError,
  downloadWorkflowAudit,
  fetchComplianceEvidence,
  fetchComplianceQueue,
  fetchWorkflow,
  replayComplaint,
  transitionWorkflow,
  type ComplaintReplay,
  type ComplianceEvidence,
  type ComplianceQueue,
  type PlanWorkflow,
  type WorkflowActionInput,
} from "../../api/reviewWorkflow";
import { usePortalContext } from "../../contexts/PortalContext";
import { fetchReportGenerationChain, type ReportGenerationChain } from "../../api/formalReport";
import { formatDateTime } from "../../utils/format";
import { ReportGenerationChainPanel } from "../report/FormalReportPortalPanels";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import {
  WorkflowStateRail,
  WorkflowVersionLedger,
} from "./WorkflowShared";
import { workflowStateLabels, workflowTone } from "./workflowLabels";

const controlStatusLabels = {
  pass: "通过",
  warning: "预警 / 人工复核",
  block: "阻断",
  information: "信息事件",
};

function controlTone(status: ComplianceEvidence["controls"][number]["status"]): "success" | "warning" | "danger" | "info" {
  if (status === "pass") return "success";
  if (status === "block") return "danger";
  if (status === "warning") return "warning";
  return "info";
}

export function RiskWorkflowWorkspace() {
  const { actor, setActorRole } = usePortalContext();
  const [queue, setQueue] = useState<ComplianceQueue | null>(null);
  const [workflowId, setWorkflowId] = useState("");
  const [workflow, setWorkflow] = useState<PlanWorkflow | null>(null);
  const [evidence, setEvidence] = useState<ComplianceEvidence | null>(null);
  const [reportChain, setReportChain] = useState<ReportGenerationChain | null>(null);
  const [reportChainLoading, setReportChainLoading] = useState(false);
  const [reason, setReason] = useState("复核三道闸门、文案、数字、来源、授权与版本链");
  const [humanReviewCompleted, setHumanReviewCompleted] = useState(false);
  const [replayVersionId, setReplayVersionId] = useState("");
  const [replay, setReplay] = useState<ComplaintReplay | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const roleAllowed = actor.role === "compliance" || actor.role === "admin";

  const loadQueue = useCallback(async (signal?: AbortSignal) => {
    if (!roleAllowed) {
      setQueue(null);
      setWorkflow(null);
      setEvidence(null);
      setReportChain(null);
      setLoading(false);
      setError("当前模拟账号没有风险合规控制台权限。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await fetchComplianceQueue(actor, signal);
      setQueue(next);
      setWorkflowId((current) => current || next.items.find((item) => item.submitted_for_compliance)?.workflow_id || next.items[0]?.workflow_id || "");
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError(loadError instanceof Error ? loadError.message : "待审队列读取失败。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [actor, roleAllowed]);

  const loadWorkflow = useCallback(async (target: string, signal?: AbortSignal) => {
    if (!target || !roleAllowed) return;
    setLoading(true);
    setError(null);
    setReplay(null);
    setReportChainLoading(true);
    try {
      const [nextWorkflow, nextEvidence] = await Promise.all([
        fetchWorkflow(target, actor, signal),
        fetchComplianceEvidence(target, actor, signal),
      ]);
      setWorkflow(nextWorkflow);
      setEvidence(nextEvidence);
      setReplayVersionId(nextWorkflow.current.id);
      try {
        setReportChain(await fetchReportGenerationChain(nextWorkflow.household_id, actor, signal));
      } catch (chainError) {
        if (chainError instanceof DOMException && chainError.name === "AbortError") return;
        setReportChain(null);
      }
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setWorkflow(null);
      setEvidence(null);
      setReportChain(null);
      setError(loadError instanceof Error ? loadError.message : "合规证据读取失败。");
    } finally {
      if (!signal?.aborted) setLoading(false);
      if (!signal?.aborted) setReportChainLoading(false);
    }
  }, [actor, roleAllowed]);

  useEffect(() => {
    const controller = new AbortController();
    setWorkflowId("");
    void loadQueue(controller.signal);
    return () => controller.abort();
  }, [loadQueue]);

  useEffect(() => {
    const controller = new AbortController();
    void loadWorkflow(workflowId, controller.signal);
    return () => controller.abort();
  }, [loadWorkflow, workflowId]);

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
      setReplayVersionId(next.current.id);
      setStatus(`${message} 已生成 V${next.current.version_number}，旧版本未覆盖。`);
      const refreshedQueue = await fetchComplianceQueue(actor);
      setQueue(refreshedQueue);
      if (next.current.state === "advisor_reviewed") {
        setEvidence(await fetchComplianceEvidence(next.workflow_id, actor));
      } else if (["compliance_reviewed", "customer_confirmed", "active", "superseded"].includes(next.current.state)) {
        setEvidence(await fetchComplianceEvidence(next.workflow_id, actor));
      } else {
        setEvidence(null);
      }
    } catch (actionError) {
      const prefix = actionError instanceof WorkflowApiError && actionError.code === "compliance_blocked" ? "规则阻断：" : "";
      setError(prefix + (actionError instanceof Error ? actionError.message : "审核操作失败。"));
    } finally {
      setBusy(false);
    }
  }

  async function runReplay() {
    if (!workflow || !replayVersionId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await replayComplaint(workflow.workflow_id, replayVersionId, reason, actor);
      setReplay(result);
      setStatus(`投诉场景已按 V${workflow.versions.find((item) => item.id === replayVersionId)?.version_number ?? "?"} 回放，未修改历史。`);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "投诉回放失败。");
    } finally {
      setBusy(false);
    }
  }

  async function exportAudit() {
    if (!workflow) return;
    setBusy(true);
    setError(null);
    try {
      await downloadWorkflowAudit(workflow.workflow_id, actor);
      setStatus("审计包已导出；包内含版本、哈希链、操作者、理由、规则／模型版本和请求 ID。");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "审计包导出失败。");
    } finally {
      setBusy(false);
    }
  }

  if (!roleAllowed) {
    return (
      <section className="workflow-permission-state" role="alert">
        <p className="section-index">RBAC · PermissionDenied</p>
        <h2>当前账号不能操作风险合规控制台</h2>
        <p>客户与客户经理不能审核自己的方案、回放投诉或导出内部审计包。</p>
        <Button type="button" onClick={() => setActorRole("compliance")}>切换为合规审核员演示账号</Button>
      </section>
    );
  }

  return (
    <section className="risk-workflow" aria-labelledby="risk-workflow-heading">
      <header className="workflow-portal-heading">
        <div>
          <p className="page-kicker">共享方案闭环 · 合规审核权限</p>
          <h2 id="risk-workflow-heading">从阻断原因回到每一条证据</h2>
          <p>三道闸门、十类控制、版本治理、投诉回放与审计导出使用同一不可变方案链。</p>
        </div>
        <dl>
          <div><dt>模拟账号</dt><dd>{actor.label}</dd></div>
          <div><dt>外部模型</dt><dd>未调用</dd></div>
          <div><dt>银行接口</dt><dd>合成 Mock</dd></div>
        </dl>
      </header>

      {error ? <div className="workflow-alert" data-tone="danger" role="alert"><strong>审核未推进</strong><p>{error}</p></div> : null}
      {status ? <div className="workflow-alert" data-tone="success" role="status"><strong>审计事件已记录</strong><p>{status}</p></div> : null}

      <section aria-labelledby="compliance-queue-heading">
        <header className="section-header-row"><div><p className="section-index">合规待审队列</p><h3 id="compliance-queue-heading">提交状态、阻断与预警</h3></div><span>{queue ? `${queue.items.length} 个可复核方案` : "正在读取"}</span></header>
        {loading && !queue ? <p className="workflow-loading" role="status">正在校验权限和版本链…</p> : null}
        {queue?.items.length === 0 ? <p className="empty-state">当前没有完成客户经理审核的方案。请先在顾问端创建、计算、做适当性检查并提交。</p> : null}
        {queue && queue.items.length > 0 ? (
          <div className="data-table-wrap" tabIndex={0} role="region" aria-label="合规待审队列，可横向滚动">
            <table className="data-table compliance-queue-table"><thead><tr><th>家庭 / 方案</th><th>版本状态</th><th>提交 / 人工复核</th><th>阻断 / 预警</th><th>修改理由</th><th><span className="visually-hidden">操作</span></th></tr></thead><tbody>{queue.items.map((item) => (
              <tr key={item.workflow_id} data-selected={workflowId === item.workflow_id || undefined}>
                <td><strong>{item.household_name}</strong><small>{item.household_code} · {item.workflow_id.slice(0, 8)}</small></td>
                <td>{workflowStateLabels[item.state]}<small>V{item.version_number} · {formatDateTime(item.created_at)}</small></td>
                <td><StatusBadge tone={item.submitted_for_compliance ? "warning" : "info"}>{item.submitted_for_compliance ? "已提交" : "未提交"}</StatusBadge><small>{item.requires_human_review ? "要求人工复核" : "常规复核"}</small></td>
                <td><span className="compliance-counts"><b data-tone={item.blocked_count ? "danger" : "neutral"}>{item.blocked_count} 阻断</b><b data-tone={item.warning_count ? "warning" : "neutral"}>{item.warning_count} 预警</b></span></td>
                <td>{item.recommendation_reason}</td>
                <td><button className="text-button" type="button" aria-pressed={workflowId === item.workflow_id} onClick={() => setWorkflowId(item.workflow_id)}>打开证据</button></td>
              </tr>
            ))}</tbody></table>
          </div>
        ) : null}
      </section>

      {workflow && evidence ? (
        <>
          <WorkflowStateRail workflow={workflow} />
          <section className="compliance-decision-summary" data-decision={evidence.overall_decision} aria-labelledby="compliance-decision-heading">
            <div><p className="section-index">风险结论</p><h3 id="compliance-decision-heading">{evidence.overall_decision === "block" ? "当前版本必须阻断" : evidence.overall_decision === "human_review" ? "规则允许进入人工复核" : "当前证据可通过"}</h3><p>{evidence.explanation}</p></div>
            <dl><div><dt>阻断</dt><dd>{evidence.blocked_codes.length}</dd></div><div><dt>预警</dt><dd>{evidence.warning_codes.length}</dd></div><div><dt>版本</dt><dd>V{evidence.version_number}</dd></div></dl>
          </section>

          <section aria-labelledby="control-matrix-heading">
            <header className="section-header-row"><div><p className="section-index">三道闸门与十类控制</p><h3 id="control-matrix-heading">为什么通过或被拦截</h3></div><span>状态不只依赖颜色</span></header>
            <div className="data-table-wrap" tabIndex={0} role="region" aria-label="合规控制矩阵，可横向滚动">
              <table className="data-table compliance-control-table"><thead><tr><th>控制</th><th>类别</th><th>结论</th><th>证据解释</th><th>规则</th><th>来源记录</th></tr></thead><tbody>{evidence.controls.map((control) => (
                <tr key={control.code} data-status={control.status}>
                  <td><strong>{control.title}</strong><small>{control.code}</small></td>
                  <td>{control.category}</td>
                  <td><StatusBadge tone={controlTone(control.status)}>{controlStatusLabels[control.status]}</StatusBadge></td>
                  <td>{control.explanation}</td>
                  <td>{control.rule}</td>
                  <td><code>{control.source_record_ids.length ? `${control.source_record_ids.length} 条` : "规则级"}</code></td>
                </tr>
              ))}</tbody></table>
            </div>
          </section>

          <section className="governance-version-grid" aria-labelledby="governance-version-heading">
            <header><p className="section-index">治理版本</p><h3 id="governance-version-heading">模型、Prompt、规则、知识、产品与方案</h3></header>
            <dl><div><dt>方案</dt><dd>V{workflow.current.version_number} · {workflow.current.after_hash.slice(0, 12)}</dd></div><div><dt>哈希链</dt><dd>{evidence.hash_chain_verified ? "已验证" : "异常"}</dd></div><div><dt>规则</dt><dd>{evidence.versions.rule_version}</dd></div><div><dt>模型</dt><dd>{evidence.versions.model_version}</dd></div><div><dt>Prompt</dt><dd>{evidence.versions.prompt_version}</dd></div><div><dt>知识库</dt><dd>{evidence.versions.knowledge_version}</dd></div><div><dt>产品库</dt><dd>{evidence.versions.product_catalog_version}</dd></div><div><dt>输入</dt><dd>{evidence.versions.input_version.slice(0, 16)}</dd></div><div><dt>请求 ID</dt><dd>{workflow.current.request_id}</dd></div></dl>
          </section>

          <ReportGenerationChainPanel chain={reportChain} loading={reportChainLoading} />

          <section className="compliance-action-panel" aria-labelledby="compliance-action-heading">
            <header className="section-header-row"><div><p className="section-index">审核动作</p><h3 id="compliance-action-heading">通过、退回或要求人工复核</h3></div><StatusBadge tone={workflowTone(workflow.current.state)}>{workflowStateLabels[workflow.current.state]}</StatusBadge></header>
            <label><span>审核理由 / 投诉回放原因</span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
            <label className="workflow-check"><input type="checkbox" checked={humanReviewCompleted} onChange={(event) => setHumanReviewCompleted(event.target.checked)} /><span><strong>人工复核已完成并留痕</strong><small>存在预警或高风险类型时，未勾选不得通过。</small></span></label>
            <div className="workflow-action-row">
              {workflow.next_actions.includes("compliance_approve") ? <Button type="button" loading={busy} onClick={() => void runAction({ action: "compliance_approve", human_review_completed: humanReviewCompleted, compliance_note: reason }, "合规通过")}>审核通过</Button> : null}
              {workflow.next_actions.includes("compliance_return") ? <Button type="button" variant="secondary" loading={busy} onClick={() => void runAction({ action: "compliance_return", compliance_note: reason }, "已退回客户经理重新计算")}>退回修订</Button> : null}
              {workflow.next_actions.includes("require_human_review") ? <Button type="button" variant="secondary" loading={busy} onClick={() => void runAction({ action: "require_human_review", compliance_note: reason }, "人工复核要求")}>要求人工复核</Button> : null}
            </div>
          </section>

          <WorkflowVersionLedger workflow={workflow} />

          <section className="complaint-replay-panel" aria-labelledby="complaint-replay-heading">
            <header className="section-header-row"><div><p className="section-index">投诉回溯与审计包</p><h3 id="complaint-replay-heading">按任一版本重建当时证据</h3></div><span>只读，不修改历史</span></header>
            <label><span>投诉指定版本</span><select value={replayVersionId} onChange={(event) => setReplayVersionId(event.target.value)}>{workflow.versions.map((item) => <option key={item.id} value={item.id}>V{item.version_number} · {workflowStateLabels[item.state]} · {item.after_hash.slice(0, 8)}</option>)}</select></label>
            <div className="workflow-action-row"><Button type="button" variant="secondary" loading={busy} onClick={() => void runReplay()}>回放投诉场景</Button><Button type="button" loading={busy} onClick={() => void exportAudit()}>导出审计包</Button></div>
            {replay ? <div className="complaint-replay-result" role="status"><strong>完整性 {replay.integrity_status} · {replay.timeline.length} 个版本</strong><p>{replay.boundary_note}</p><code>包哈希 {replay.package_hash}</code><small>回放 ID {replay.replay_id} · 请求 {replay.request_id}</small></div> : null}
          </section>
        </>
      ) : workflowId && loading ? <p className="workflow-loading" role="status">正在读取三道闸门、十类控制和版本哈希…</p> : null}
    </section>
  );
}
