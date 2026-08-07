import { useCallback, useEffect, useState } from "react";
import {
  WorkflowApiError,
  fetchCurrentWorkflow,
  transitionWorkflow,
  type PlanWorkflow,
} from "../../api/reviewWorkflow";
import { usePortalContext } from "../../contexts/PortalContext";
import type { ClientDeliveryState } from "../../api/clientExperience";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { WorkflowStateRail } from "./WorkflowShared";
import { workflowStateLabels, workflowTone } from "./workflowLabels";

export function ClientPlanConfirmation({ householdId, delivery }: { householdId: string; delivery: ClientDeliveryState }) {
  const { actor, setActorRole } = usePortalContext();
  const [workflow, setWorkflow] = useState<PlanWorkflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [waitingReason, setWaitingReason] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [riskRead, setRiskRead] = useState(false);
  const [mockUnderstood, setMockUnderstood] = useState(false);
  const [notGuaranteed, setNotGuaranteed] = useState(false);

  const roleAllowed = actor.role === "client" || actor.role === "admin";

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!roleAllowed) {
      setWorkflow(null);
      setWaitingReason("只有客户或管理员可逐项确认方案。");
      setLoading(false);
      return;
    }
    if (delivery.workflow === "under_review") {
      setWorkflow(null);
      setWaitingReason("内部草稿仍在客户经理或合规审核中；通过前不会向客户展示。");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setWaitingReason(null);
    try {
      const result = await fetchCurrentWorkflow(householdId, actor, signal);
      setWorkflow(result);
      if (!result) setWaitingReason("客户经理尚未创建方案审核流。");
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      if (loadError instanceof WorkflowApiError && loadError.code === "workflow_not_ready_for_client") {
        setWorkflow(null);
        setWaitingReason("内部草稿仍在客户经理或合规审核中；通过前不会向客户展示。 ");
      } else {
        setError(loadError instanceof Error ? loadError.message : "方案确认状态读取失败。");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [actor, delivery.workflow, householdId, roleAllowed]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function confirm() {
    if (!workflow) return;
    setBusy(true);
    setError(null);
    try {
      const next = await transitionWorkflow(workflow.workflow_id, actor, {
        action: "customer_confirm",
        expected_version: workflow.current.version_number,
        reason: "客户逐项确认风险、Mock 与非保本边界",
        customer_name: customerName,
        acknowledgements: [
          ...(riskRead ? ["risk_read" as const] : []),
          ...(mockUnderstood ? ["mock_understood" as const] : []),
          ...(notGuaranteed ? ["not_guaranteed" as const] : []),
        ],
      });
      setWorkflow(next);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "客户确认失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="client-confirmation" aria-labelledby="client-confirmation-heading">
      <header className="section-header-row">
        <div><p className="section-index">三端闭环</p><h3 id="client-confirmation-heading">方案审核与客户确认</h3></div>
        {workflow ? <StatusBadge tone={workflowTone(workflow.current.state)}>{workflowStateLabels[workflow.current.state]} · V{workflow.current.version_number}</StatusBadge> : <StatusBadge tone="info">等待可见版本</StatusBadge>}
      </header>
      {loading ? <p className="workflow-loading" role="status">正在核对客户可见版本…</p> : null}
      {!roleAllowed ? <div className="workflow-inline-permission" role="alert"><p>{waitingReason}</p><Button type="button" variant="secondary" onClick={() => setActorRole("client")}>切换为客户演示账号</Button></div> : null}
      {roleAllowed && waitingReason ? <p className="workflow-waiting" role="status">{waitingReason}</p> : null}
      {error ? <p className="workflow-error" role="alert">{error}</p> : null}
      {workflow ? <WorkflowStateRail workflow={workflow} /> : null}
      {workflow?.current.state === "compliance_reviewed" ? (
        <form className="client-confirmation-form" onSubmit={(event) => { event.preventDefault(); void confirm(); }}>
          <p>合规已通过当前规划版本。确认只表示您已阅读并理解，不构成真实银行签约或自动交易。</p>
          <fieldset>
            <legend>逐项确认</legend>
            <label><input type="checkbox" checked={riskRead} onChange={(event) => setRiskRead(event.target.checked)} /><span><strong>我已阅读风险、流动性与适当性限制</strong><small>压力结果不是预测，历史或假设表现不代表未来。</small></span></label>
            <label><input type="checkbox" checked={mockUnderstood} onChange={(event) => setMockUnderstood(event.target.checked)} /><span><strong>我理解全部银行接口与产品均为合成 Mock</strong><small>系统未连接真实银行，也不是中国工商银行官方产品。</small></span></label>
            <label><input type="checkbox" checked={notGuaranteed} onChange={(event) => setNotGuaranteed(event.target.checked)} /><span><strong>我理解方案不承诺保本或收益</strong><small>银行理财、信托、基金和保险按各自属性区分。</small></span></label>
          </fieldset>
          <div className="client-confirmation-name">
            <label htmlFor="client-demo-signature">演示签署姓名</label>
            <input id="client-demo-signature" value={customerName} onChange={(event) => setCustomerName(event.target.value)} autoComplete="name" aria-describedby="client-demo-signature-help" />
            <small id="client-demo-signature-help">服务端只保存姓名哈希和脱敏提示；这不是法律电子签名。</small>
          </div>
          <Button type="submit" loading={busy} disabled={!riskRead || !mockUnderstood || !notGuaranteed || customerName.trim().length < 2}>确认当前方案版本</Button>
        </form>
      ) : null}
      {workflow?.current.state === "customer_confirmed" ? <p className="workflow-waiting" role="status">客户已逐项确认，等待客户经理激活。演示签署不触发任何交易。</p> : null}
      {workflow?.current.state === "active" ? <p className="workflow-active-note" role="status">当前规划版本已生效。家庭数据、目标或授权变化时会创建新版本，不覆盖历史。</p> : null}
    </section>
  );
}
