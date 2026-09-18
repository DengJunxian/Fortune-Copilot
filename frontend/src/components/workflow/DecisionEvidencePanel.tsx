import { useState } from "react";
import {
  replayDecision,
  type DecisionEvidenceSection,
  type DecisionEvidenceV2,
  type DecisionReplayV2,
} from "../../api/reviewWorkflow";
import type { DemoActor } from "../../api/actor";
import { formatDateTime } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

const sections: Array<[keyof DecisionEvidenceV2, string]> = [
  ["household_input", "家庭输入"],
  ["financial_graph", "财务图谱"],
  ["client_profile", "客户画像"],
  ["wealth_needs", "财富需求"],
  ["liability", "负债责任"],
  ["ELTC", "长期可投资资金"],
  ["risk_budget", "家庭风险预算"],
  ["enterprise", "家企风险"],
  ["CFS", "综合财务方案"],
  ["product_snapshot", "产品快照"],
  ["suitability", "适当性"],
  ["calibration", "校准"],
  ["advisor", "客户经理"],
  ["client_confirmation", "客户确认"],
];

const statusLabels = {
  bound: "已冻结",
  not_available: "尚无记录",
  not_applicable: "本阶段不适用",
};

function asSection(value: DecisionEvidenceV2[keyof DecisionEvidenceV2]): DecisionEvidenceSection {
  return value as DecisionEvidenceSection;
}

function productCount(evidence: DecisionEvidenceV2): number {
  const snapshots = evidence.product_snapshot.decision_inputs.snapshots;
  return Array.isArray(snapshots) ? snapshots.length : 0;
}

export function DecisionEvidencePanel({
  actor,
  evidence,
  onError,
}: {
  actor: DemoActor;
  evidence: DecisionEvidenceV2;
  onError: (message: string) => void;
}) {
  const [replay, setReplay] = useState<DecisionReplayV2 | null>(null);
  const [busy, setBusy] = useState(false);
  const boundCount = sections.filter(([key]) => asSection(evidence[key]).status === "bound").length;
  const cfsId = evidence.CFS.decision_inputs.solution_id;

  async function runReplay() {
    setBusy(true);
    setReplay(null);
    try {
      setReplay(await replayDecision(evidence.decision_id, actor));
    } catch (error) {
      onError(error instanceof Error ? error.message : "冻结快照回放失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="decision-evidence-panel" aria-labelledby="decision-evidence-heading">
      <header className="decision-evidence-heading">
        <div>
          <p className="section-index">Decision Evidence V2</p>
          <h3 id="decision-evidence-heading">这次决定，当时依据了什么</h3>
          <p>证据包冻结决策时使用的输入和版本；回放不会换成今天的产品资料。</p>
        </div>
        <StatusBadge tone="success">{boundCount}/14 个域已绑定</StatusBadge>
      </header>

      <div className="decision-evidence-summary">
        <article>
          <span>决策校验码</span>
          <strong><code>{evidence.decision_hash.slice(0, 16)}</code></strong>
          <small>{evidence.evidence_version}</small>
        </article>
        <article>
          <span>CFS 方案</span>
          <strong>{typeof cfsId === "string" ? cfsId.slice(0, 8) : "未绑定"}</strong>
          <small>{evidence.CFS.version}</small>
        </article>
        <article>
          <span>产品证据</span>
          <strong>{productCount(evidence)} 份快照</strong>
          <small>费用、流动性、条款与来源一并冻结</small>
        </article>
      </div>

      <div className="decision-evidence-ledger" role="list" aria-label="决策证据域与冻结版本">
        {sections.map(([key, label], index) => {
          const section = asSection(evidence[key]);
          return (
            <article key={key} role="listitem" data-status={section.status}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div><strong>{label}</strong><code title={section.version}>{section.version}</code></div>
              <small>{statusLabels[section.status]} · {section.source_record_ids.length} 条来源</small>
            </article>
          );
        })}
      </div>

      <footer className="decision-replay-footer">
        <div>
          <strong>历史快照回放</strong>
          <p>重新计算规范化哈希，不访问最新产品表，也不覆盖原证据。</p>
        </div>
        <Button type="button" variant="secondary" loading={busy} onClick={() => void runReplay()}>
          使用冻结快照回放
        </Button>
      </footer>
      {replay ? (
        <div className="decision-replay-result" data-identical={String(replay.hash_identical)} role="status">
          <StatusBadge tone={replay.hash_identical ? "success" : "danger"}>
            {replay.hash_identical ? "哈希一致" : "完整性异常"}
          </StatusBadge>
          <p>{replay.latest_product_data_used ? "使用了最新产品资料" : "未读取最新产品资料"} · {formatDateTime(replay.replayed_at)}</p>
          <code>{replay.replay_decision_hash}</code>
        </div>
      ) : null}
    </section>
  );
}
