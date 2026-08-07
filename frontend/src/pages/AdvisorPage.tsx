import { usePortalContext } from "../contexts/PortalContext";
import { StatusBadge } from "../components/ui/StatusBadge";
import { PortfolioPortalWorkspace } from "../components/portfolio/PortfolioWorkspace";
import { TwinPortalWorkspace } from "../components/twin/TwinWorkspace";
import { BehaviorPortalWorkspace } from "../components/behavior/BehaviorWorkspace";
import { TrustPortalWorkspace } from "../components/trust/TrustWorkspace";
import { AdvisorWorkflowWorkspace } from "../components/workflow/AdvisorWorkflowWorkspace";

export function AdvisorPage() {
  const { capabilities } = usePortalContext();
  const statusLabel = (status: "available" | "planned" | "blocked") => {
    if (status === "available") return "可用";
    if (status === "blocked") return "当前不可用";
    return "计划中";
  };
  return (
    <main className="page-shell" id="main-content">
      <header className="page-intro">
        <p className="page-kicker">顾问端</p>
        <h1>客户经理工作台</h1>
        <p>以共享方案版本组织客户队列、面谈准备、三方案、沟通稿、合规提交、客户确认与月度复盘。</p>
      </header>

      <AdvisorWorkflowWorkspace />

      <details className="technical-evidence-drawer">
        <summary>查看底层能力与专项证据工作区</summary>
      <section aria-labelledby="capability-heading">
        <h2 className="section-heading" id="capability-heading">
          工程能力清单
        </h2>
        <div className="data-table-wrap" tabIndex={0} role="region" aria-label="可横向滚动的能力表">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">能力</th>
                <th scope="col">状态</th>
                <th scope="col">实现类型</th>
                <th scope="col">说明</th>
              </tr>
            </thead>
            <tbody>
              {capabilities.capabilities.map((capability) => (
                <tr key={capability.id}>
                  <td>{capability.id}</td>
                  <td>
                    <StatusBadge tone={capability.status === "available" ? "success" : "warning"}>
                      {statusLabel(capability.status)}
                    </StatusBadge>
                  </td>
                  <td>{capability.implementation}</td>
                  <td>{capability.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <PortfolioPortalWorkspace view="advisor" />
      <TwinPortalWorkspace view="advisor" />
      <BehaviorPortalWorkspace view="advisor" />
      <TrustPortalWorkspace view="advisor" />
      </details>
    </main>
  );
}
