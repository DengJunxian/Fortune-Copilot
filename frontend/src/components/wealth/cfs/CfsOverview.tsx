import type { CFSSolutionResponse } from "../../../api/cfs";
import { formatDomainLabel } from "../../../utils/format";
import { CfsComponentCard } from "./CfsComponentCard";

export function CfsOverview({ householdName, solution }: { householdName: string; solution: CFSSolutionResponse }) {
  return (
    <section className="cfs-overview" aria-labelledby="cfs-overview-title" data-no-action={solution.solution.summary.no_action_required ?? false}>
      <header><div><span>方案 #{solution.solution.solution_version}</span><h2 id="cfs-overview-title">{solution.solution.summary.headline ?? "家庭综合财务方案"}</h2></div><dl><div><dt>家庭</dt><dd>{householdName}</dd></div><div><dt>状态</dt><dd>{formatDomainLabel(solution.solution.status)}</dd></div><div><dt>来源</dt><dd>确定性工具</dd></div><div><dt>校验码</dt><dd>{solution.solution.decision_hash.slice(0, 10)}</dd></div></dl></header>
      <div className="cfs-overview-components">{solution.components.slice(0, 4).map((component) => <CfsComponentCard key={component.id} component={component} />)}</div>
    </section>
  );
}
