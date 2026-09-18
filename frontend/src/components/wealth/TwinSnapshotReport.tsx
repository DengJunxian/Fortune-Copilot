import { FingerprintIcon, FileLockIcon } from "@phosphor-icons/react";
import type { CFSSolutionResponse } from "../../api/cfs";
import type { WealthTwinResponse } from "../../api/persistentTwin";
import { formatDate } from "../../utils/format";

export function TwinSnapshotReport({
  solution,
  twin,
}: {
  solution: CFSSolutionResponse | null;
  twin: WealthTwinResponse;
}) {
  const snapshot = twin.current;
  return (
    <section className="twin-snapshot-report" aria-labelledby="twin-snapshot-report-title">
      <header>
        <div><span><FileLockIcon size={20} weight="duotone" aria-hidden="true" /> Twin Snapshot Report</span><h2 id="twin-snapshot-report-title">这份规划引用了哪一版家庭状态</h2></div>
        <p>它是八章正式规划书的证据附件，不新增第九章。</p>
      </header>
      <dl>
        <div><dt>快照 ID</dt><dd>{snapshot.id}</dd></div>
        <div><dt>快照日期</dt><dd>{formatDate(snapshot.snapshot_date)}</dd></div>
        <div><dt>画像版本</dt><dd>{snapshot.profile_version === null ? "未绑定" : `P${snapshot.profile_version}`}</dd></div>
        <div><dt>责任版本</dt><dd>{snapshot.liability_version}</dd></div>
        <div><dt>CFS 版本</dt><dd>{solution ? `CFS ${solution.solution.solution_version}` : "当前会话未绑定"}</dd></div>
        <div><dt>决策哈希</dt><dd>{solution?.solution.decision_hash ?? "当前会话未绑定"}</dd></div>
      </dl>
      <p><FingerprintIcon size={18} aria-hidden="true" /> 快照校验 {snapshot.snapshot_hash} · 输入校验 {snapshot.input_hash}</p>
    </section>
  );
}
