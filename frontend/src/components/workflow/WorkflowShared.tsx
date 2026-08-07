import type { PlanWorkflow } from "../../api/reviewWorkflow";
import { formatDateTime } from "../../utils/format";
import { StatusBadge } from "../ui/StatusBadge";
import { workflowActionLabels, workflowStateLabels, workflowTone } from "./workflowLabels";

export function WorkflowStateRail({ workflow }: { workflow: PlanWorkflow }) {
  const currentIndex = workflow.state_order.indexOf(workflow.current.state);
  return (
    <section className="workflow-state-section" aria-labelledby="workflow-state-heading">
      <header className="section-header-row">
        <div>
          <p className="section-index">不可跳步状态机</p>
          <h3 id="workflow-state-heading">当前 {workflowStateLabels[workflow.current.state]} · V{workflow.current.version_number}</h3>
        </div>
        <StatusBadge tone={workflowTone(workflow.current.state)}>
          第 {currentIndex + 1}/8 个必要状态
        </StatusBadge>
      </header>
      <ol className="workflow-state-rail" aria-label="方案八状态">
        {workflow.state_order.map((state, index) => (
          <li
            key={state}
            data-state={index < currentIndex ? "complete" : index === currentIndex ? "current" : "pending"}
            aria-current={index === currentIndex ? "step" : undefined}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{workflowStateLabels[state]}</strong>
          </li>
        ))}
      </ol>
      <p className="workflow-state-note">退回会开启新的修订周期并回到草稿；同一状态内的编辑和提交也会生成新版本。</p>
    </section>
  );
}

export function WorkflowVersionLedger({ workflow }: { workflow: PlanWorkflow }) {
  return (
    <details className="workflow-version-ledger" open>
      <summary>版本链与修改留痕（{workflow.versions.length} 版）</summary>
      <div className="data-table-wrap" tabIndex={0} role="region" aria-label="方案版本链，可横向滚动">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">版本 / 周期</th>
              <th scope="col">状态与动作</th>
              <th scope="col">操作者</th>
              <th scope="col">时间</th>
              <th scope="col">理由</th>
              <th scope="col">哈希 / 请求</th>
            </tr>
          </thead>
          <tbody>
            {workflow.versions.map((version) => (
              <tr key={version.id} data-current={version.is_current || undefined}>
                <td><strong>V{version.version_number}</strong><small>周期 {version.cycle}</small></td>
                <td><span>{workflowStateLabels[version.state]}</span><small>{workflowActionLabels[version.action]}</small></td>
                <td><span>{version.actor_id}</span><small>{version.actor_role}</small></td>
                <td>{formatDateTime(version.created_at)}</td>
                <td>{version.reason}</td>
                <td><code>{version.after_hash.slice(0, 12)}</code><small>{version.request_id}</small></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function WorkflowBoundary() {
  return (
    <aside className="workflow-boundary" aria-label="方案闭环边界">
      <strong>人工与数据边界</strong>
      <p>AI 只生成可编辑解释草稿，不决定方案、不计算金额。所有候选金额、比率和配置读取确定性工具；高风险类型必须人工确认。</p>
    </aside>
  );
}
