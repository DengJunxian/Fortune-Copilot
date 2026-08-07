import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  behaviorExportUrl,
  completeBehaviorSession,
  exitBehaviorSession,
  fetchBehaviorABFramework,
  fetchBehaviorCatalog,
  fetchBehaviorOverview,
  startBehaviorSession,
  submitBehaviorResponse,
  updateBehaviorIntervention,
  type BehaviorABFramework,
  type BehaviorCatalog,
  type BehaviorIntervention,
  type BehaviorOverview,
  type BehaviorProfile,
  type BehaviorQuestionnaire,
  type BehaviorRiskLevel,
  type BehaviorSession,
  type BiasScore,
  type QuestionnaireDimension,
} from "../../api/behavior";
import { fetchHouseholds, type HouseholdSummary } from "../../api/financial";
import { formatDate, formatRatio } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

type BehaviorView = "client" | "advisor" | "risk";

const defaultQuestionnaire: BehaviorQuestionnaire = {
  risk_willingness: "0.70",
  loss_tolerance_claim: "0.80",
  investment_experience: "0.60",
  knowledge: "0.60",
  trading_frequency: "0.50",
  attention: "0.45",
  goal_discipline: "0.55",
};

const levelCopy: Record<BehaviorRiskLevel, string> = {
  low: "低风险上限",
  medium_low: "中低风险上限",
  medium: "中风险上限",
  medium_high: "中高风险上限",
  high: "高风险上限",
};

const severityCopy: Record<BiasScore["severity"], string> = {
  low: "低信号",
  watch: "需要关注",
  high: "高信号",
};

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    hour12: false,
  }).format(new Date(value));
}

function profileHeading(view: BehaviorView): string {
  if (view === "risk") return "从选择证据复核风险下调与干预状态";
  if (view === "advisor") return "把客户说法与真实选择放在同一张底稿上";
  return "先做选择，再看行为如何影响配置上限";
}

export function BehaviorWorkspace({ householdId, view = "client" }: { householdId: string; view?: BehaviorView }) {
  const [catalog, setCatalog] = useState<BehaviorCatalog | null>(null);
  const [overview, setOverview] = useState<BehaviorOverview | null>(null);
  const [abFramework, setAbFramework] = useState<BehaviorABFramework | null>(null);
  const [session, setSession] = useState<BehaviorSession | null>(null);
  const [profileOverride, setProfileOverride] = useState<BehaviorProfile | null>(null);
  const [questionnaire, setQuestionnaire] = useState<BehaviorQuestionnaire>(defaultQuestionnaire);
  const [choice, setChoice] = useState("");
  const [modificationCount, setModificationCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const questionStartedAt = useRef(performance.now());

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [nextCatalog, nextOverview] = await Promise.all([
        fetchBehaviorCatalog(signal),
        fetchBehaviorOverview(householdId, signal),
      ]);
      setCatalog(nextCatalog);
      setOverview(nextOverview);
      setSession(nextOverview.latest_session?.status === "active" ? nextOverview.latest_session : null);
      setProfileOverride(null);
      setLoading(false);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setLoading(false);
      setError("行为实验数据当前不可用；系统不会依据家庭财务数据猜测人格或偏差。");
    }
  }, [householdId]);

  useEffect(() => {
    const controller = new AbortController();
    setQuestionnaire(defaultQuestionnaire);
    setChoice("");
    setModificationCount(0);
    setStatusMessage(null);
    questionStartedAt.current = performance.now();
    void load(controller.signal);
    fetchBehaviorABFramework(controller.signal)
      .then(setAbFramework)
      .catch(() => setAbFramework(null));
    return () => controller.abort();
  }, [load]);

  const profile = profileOverride ?? session?.profile ?? overview?.profile ?? null;
  const currentExperiment = useMemo(() => {
    if (!catalog || !session || session.status !== "active") return null;
    const code = session.remaining_experiment_codes[0];
    return catalog.experiments.find((item) => item.code === code) ?? null;
  }, [catalog, session]);

  useEffect(() => {
    if (!currentExperiment) return;
    setChoice("");
    setModificationCount(0);
    questionStartedAt.current = performance.now();
  }, [currentExperiment]);

  async function beginExperiment() {
    setBusy(true);
    setError(null);
    setStatusMessage(null);
    try {
      const next = await startBehaviorSession(householdId, questionnaire);
      setSession(next);
      setProfileOverride(null);
      setStatusMessage(`已进入 ${next.assigned_variant_name}；可随时退出，不会因此生成画像。`);
      questionStartedAt.current = performance.now();
    } catch {
      setError("无法开始行为实验；请确认没有其他进行中的会话，并核对合成／授权数据范围。");
    } finally {
      setBusy(false);
    }
  }

  async function recordChoice() {
    if (!session || !currentExperiment || !choice) return;
    setBusy(true);
    setError(null);
    try {
      const elapsed = Math.max(100, Math.round(performance.now() - questionStartedAt.current));
      const next = await submitBehaviorResponse(
        householdId,
        session.session_id,
        currentExperiment.code,
        choice,
        elapsed,
        modificationCount,
      );
      setSession(next);
      setStatusMessage(`已记录第 ${next.answered_count}／${next.required_count} 项选择、反应时间和修改次数。`);
    } catch {
      setError("本项选择未能写入；当前进度未被前端假定为成功。");
    } finally {
      setBusy(false);
    }
  }

  async function finishExperiment() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await completeBehaviorSession(householdId, session.session_id);
      setSession(next);
      setProfileOverride(next.profile);
      setStatusMessage("双画像、十一项偏差证据和个性化干预已由确定性规则生成并进入审计链。");
      fetchBehaviorABFramework().then(setAbFramework).catch(() => undefined);
    } catch {
      setError("双画像生成失败；必须完成全部六项实验，系统不会补造缺失选择。");
    } finally {
      setBusy(false);
    }
  }

  async function leaveExperiment() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const result = await exitBehaviorSession(householdId, session.session_id);
      setStatusMessage(`${result.message} 审计 ${result.audit_event_id.slice(0, 12)}。`);
      setSession(null);
      await load();
      fetchBehaviorABFramework().then(setAbFramework).catch(() => undefined);
    } catch {
      setError("退出请求未被确认；请保留当前页面并重试。");
    } finally {
      setBusy(false);
    }
  }

  function changeChoice(nextChoice: string) {
    if (choice && choice !== nextChoice) setModificationCount((count) => count + 1);
    setChoice(nextChoice);
  }

  async function actOnIntervention(intervention: BehaviorIntervention, action: "complete" | "dismiss") {
    if (!profile || !intervention.intervention_id) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateBehaviorIntervention(
        householdId,
        intervention.intervention_id,
        action,
      );
      setProfileOverride({
        ...profile,
        interventions: profile.interventions.map((item) => (
          item.intervention_id === updated.intervention_id ? updated : item
        )),
      });
      setStatusMessage(action === "complete" ? "干预已完成并写入审计事件。" : "已记录暂不采用，不会暗中执行操作。");
    } catch {
      setError(
        intervention.cooling_period_hours
          ? "冷静期尚未结束，不能提前标记完成；开始时间和可操作时间保持可审计。"
          : "干预状态更新失败；页面没有假定操作成功。",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="behavior-workspace" data-view={view} aria-labelledby={`behavior-heading-${view}`}>
      <header className="behavior-header">
        <div>
          <p className="section-index">行为金融双画像 · 七维问卷 + 六项实验</p>
          <h2 id={`behavior-heading-${view}`}>{profileHeading(view)}</h2>
          <p>行为证据只能维持或下调客观风险能力；反应时间是辅助信号，不单独决定配置。</p>
        </div>
        <aside className="behavior-boundary">
          <strong>合成／授权测试数据</strong>
          <span>可退出 · 不承诺收益 · 不自动交易</span>
        </aside>
      </header>

      {loading ? <BehaviorLoading /> : null}
      {!loading && error ? <p className="behavior-error" role="alert">{error}</p> : null}
      {statusMessage ? <p className="behavior-status" role="status">{statusMessage}</p> : null}

      {!loading && catalog && overview ? (
        <>
          <ExperimentConsole
            catalog={catalog}
            overview={overview}
            session={session}
            questionnaire={questionnaire}
            currentExperiment={currentExperiment}
            choice={choice}
            modificationCount={modificationCount}
            busy={busy}
            onQuestionnaireChange={(code, value) => setQuestionnaire((current) => ({ ...current, [code]: value }))}
            onStart={() => void beginExperiment()}
            onChoiceChange={changeChoice}
            onRecord={() => void recordChoice()}
            onComplete={() => void finishExperiment()}
            onExit={() => void leaveExperiment()}
          />
          {profile ? (
            <BehaviorProfileView
              profile={profile}
              householdId={householdId}
              view={view}
              busy={busy}
              onInterventionAction={(item, action) => void actOnIntervention(item, action)}
            />
          ) : <BehaviorInsufficient overview={overview} />}
          {abFramework ? <ABFrameworkView framework={abFramework} open={view === "risk"} /> : null}
          <BehaviorEvidence catalog={catalog} profile={profile} view={view} />
        </>
      ) : null}
    </section>
  );
}

function BehaviorLoading() {
  return (
    <section className="behavior-loading" aria-live="polite">
      <span className="loading-mark" aria-hidden="true" />
      <div><strong>正在核对行为实验底稿</strong><p>读取规则版本、授权范围、六项选择和已有干预状态。</p></div>
    </section>
  );
}

interface ExperimentConsoleProps {
  catalog: BehaviorCatalog;
  overview: BehaviorOverview;
  session: BehaviorSession | null;
  questionnaire: BehaviorQuestionnaire;
  currentExperiment: BehaviorCatalog["experiments"][number] | null;
  choice: string;
  modificationCount: number;
  busy: boolean;
  onQuestionnaireChange: (code: keyof BehaviorQuestionnaire, value: string) => void;
  onStart: () => void;
  onChoiceChange: (choice: string) => void;
  onRecord: () => void;
  onComplete: () => void;
  onExit: () => void;
}

function ExperimentConsole({ catalog, overview, session, questionnaire, currentExperiment, choice, modificationCount, busy, onQuestionnaireChange, onStart, onChoiceChange, onRecord, onComplete, onExit }: ExperimentConsoleProps) {
  if (!session) {
    return (
      <section className="behavior-console" aria-labelledby="behavior-console-heading">
        <header>
          <div><p className="section-index">实验入口</p><h3 id="behavior-console-heading">用真实选择校验自述承受力</h3></div>
          <span>{overview.authorization_basis === "synthetic_data" ? "合成演示家庭" : "已授权测试数据"}</span>
        </header>
        <details className="behavior-questionnaire">
          <summary>调整七维问卷；当前采用主 Demo 起始值</summary>
          <div className="behavior-questionnaire-grid">
            {catalog.questionnaire_dimensions.map((dimension) => (
              <QuestionnaireControl
                key={dimension.code}
                dimension={dimension}
                value={questionnaire[dimension.code]}
                onChange={(value) => onQuestionnaireChange(dimension.code, value)}
              />
            ))}
          </div>
        </details>
        <div className="behavior-console-actions">
          <p>{catalog.required_experiment_count} 项实验会记录选择、反应时间、修改次数与一致性。开始后仍可随时退出。</p>
          <Button type="button" loading={busy} disabled={!overview.can_start_experiment} onClick={onStart}>开始行为实验</Button>
        </div>
      </section>
    );
  }

  if (session.status === "completed") {
    return (
      <section className="behavior-console behavior-console-completed" aria-labelledby="behavior-console-heading">
        <header>
          <div><p className="section-index">实验已完成 · {session.assigned_variant_name}</p><h3 id="behavior-console-heading">六项选择均已持久化</h3></div>
          <div className="behavior-progress-copy"><strong>{session.answered_count} / {session.required_count}</strong><span>已完成</span></div>
        </header>
        <progress max={session.required_count} value={session.answered_count}>{session.answered_count} / {session.required_count}</progress>
        <p>画像、冲突规则和干预均来自本次已记录选择；页面不会重复提交或自动执行交易。</p>
      </section>
    );
  }

  const completeReady = session.status === "active" && session.answered_count === session.required_count;
  return (
    <section className="behavior-console behavior-console-active" aria-labelledby="behavior-console-heading">
      <header>
        <div>
          <p className="section-index">实验进行中 · {session.assigned_variant_name}</p>
          <h3 id="behavior-console-heading">选择 {session.answered_count + (completeReady ? 0 : 1)}／{session.required_count}</h3>
        </div>
        <div className="behavior-progress-copy"><strong>{session.answered_count} / {session.required_count}</strong><span>已持久化</span></div>
      </header>
      <progress max={session.required_count} value={session.answered_count}>{session.answered_count} / {session.required_count}</progress>
      {currentExperiment ? (
        <fieldset className="behavior-choice-fieldset" disabled={busy}>
          <legend>{currentExperiment.name}</legend>
          <p>{currentExperiment.scenario}</p>
          <div>
            {currentExperiment.options.map((option) => (
              <label key={option.code} data-selected={choice === option.code}>
                <input type="radio" name={`behavior-${currentExperiment.code}`} value={option.code} checked={choice === option.code} onChange={() => onChoiceChange(option.code)} />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          <small>本项已修改 {modificationCount} 次；提交时同时记录本页反应时间。</small>
        </fieldset>
      ) : null}
      <div className="behavior-console-actions">
        <Button type="button" variant="secondary" disabled={busy} onClick={onExit}>退出实验</Button>
        {currentExperiment ? <Button type="button" loading={busy} disabled={!choice} onClick={onRecord}>记录选择并继续</Button> : null}
        {completeReady ? <Button type="button" loading={busy} onClick={onComplete}>生成双画像与干预</Button> : null}
      </div>
    </section>
  );
}

function QuestionnaireControl({ dimension, value, onChange }: { dimension: QuestionnaireDimension; value: string; onChange: (value: string) => void }) {
  return (
    <label className="behavior-question-control">
      <span><strong>{dimension.name}</strong><output>{formatRatio(value, 0)}</output></span>
      <small>{dimension.prompt}</small>
      <input aria-label={dimension.name} type="range" min="0" max="1" step="0.05" value={value} onChange={(event) => onChange(event.target.value)} />
      <span className="behavior-range-labels"><i>{dimension.low_label}</i><i>{dimension.high_label}</i></span>
    </label>
  );
}

function BehaviorInsufficient({ overview }: { overview: BehaviorOverview }) {
  return (
    <section className="behavior-insufficient">
      <p className="section-index">信息不足</p><h3>尚不能生成行为画像</h3>
      <p>{overview.information_message}</p>
      <p>系统不会用年龄、收入或资产规模猜测行为偏差，也不会据此提高风险等级。</p>
    </section>
  );
}

function BehaviorProfileView({ profile, householdId, view, busy, onInterventionAction }: { profile: BehaviorProfile; householdId: string; view: BehaviorView; busy: boolean; onInterventionAction: (intervention: BehaviorIntervention, action: "complete" | "dismiss") => void }) {
  const lossAversion = profile.biases.find((item) => item.code === "loss_aversion");
  const chasing = profile.biases.find((item) => item.code === "performance_chasing");
  const cooling = profile.interventions.find((item) => item.code === "cooling_period");
  return (
    <div className="behavior-results">
      <header className="behavior-result-header">
        <div>
          <p className="section-index">双画像结论 · {profile.meta.source === "completed_session" ? "已持久化" : "合成输入预览"}</p>
          <h3>{profile.dual_profile.risk_downshifted ? `行为证据将配置上限从${levelCopy[profile.dual_profile.objective_capacity_limit]}下调至${levelCopy[profile.dual_profile.effective_risk_limit]}` : `行为证据未提高${levelCopy[profile.dual_profile.objective_capacity_limit]}`}</h3>
          <p>{profile.dual_profile.explanation}</p>
          {lossAversion && chasing ? <p className="behavior-demo-callout">主 Demo 证据：损失厌恶 {formatRatio(lossAversion.score)}；追涨杀跌 {formatRatio(chasing.score)}；{cooling ? `${cooling.cooling_period_hours ?? 24} 小时冷静期已生成` : "当前未触发冷静期"}。</p> : null}
        </div>
        <a className="button export-link" data-variant="primary" href={behaviorExportUrl(householdId)} download>导出行为底稿</a>
      </header>
      <DualProfileLedger profile={profile} />
      <BiasLedger biases={profile.biases} />
      <InterventionLedger profile={profile} busy={busy} onAction={onInterventionAction} />
      <ResponseLedger profile={profile} />
      {view === "risk" ? <p className="behavior-risk-note">风险端复核：输入版本 <code>{profile.meta.input_version}</code>；客观能力记录 <code>{profile.dual_profile.capacity_source_record_id}</code>。</p> : null}
    </div>
  );
}

function DualProfileLedger({ profile }: { profile: BehaviorProfile }) {
  const rows = [
    { label: "客观风险能力", level: profile.dual_profile.objective_capacity_limit, score: profile.dual_profile.objective_capacity_score, note: "硬边界；行为不得上调" },
    { label: "问卷自述画像", level: profile.dual_profile.questionnaire_claim_limit, score: profile.dual_profile.questionnaire_score, note: "七维加权自述" },
    { label: "实验行为画像", level: profile.dual_profile.experiment_limit, score: profile.dual_profile.experiment_score, note: "六项选择 + 一致性" },
    { label: "最终配置上限", level: profile.dual_profile.effective_risk_limit, score: null, note: "三者审慎最低值" },
  ];
  return (
    <section className="dual-profile" aria-labelledby="dual-profile-heading">
      <header><div><p className="section-index">双画像对照</p><h3 id="dual-profile-heading">说法、选择与能力不做平均</h3></div><StatusBadge tone={profile.dual_profile.conflict_detected ? "warning" : "success"}>{profile.dual_profile.conflict_detected ? "发现冲突，已下调" : "未命中强制冲突"}</StatusBadge></header>
      <ol>
        {rows.map((row) => <li key={row.label} data-final={row.label === "最终配置上限"}><span><strong>{row.label}</strong><small>{row.note}</small></span><RiskLevelTrack level={row.level} /><b>{levelCopy[row.level]}{row.score === null ? "" : ` · ${formatRatio(row.score)}`}</b></li>)}
      </ol>
      {profile.dual_profile.conflict_codes.length ? <p>命中规则：<code>{profile.dual_profile.conflict_codes.join(" · ")}</code></p> : null}
    </section>
  );
}

function RiskLevelTrack({ level }: { level: BehaviorRiskLevel }) {
  const levels: BehaviorRiskLevel[] = ["low", "medium_low", "medium", "medium_high", "high"];
  return <span className="risk-level-track" aria-label={levelCopy[level]}>{levels.map((item) => <i key={item} data-active={item === level}>{item === level ? "●" : "—"}<span className="visually-hidden">{levelCopy[item]}</span></i>)}</span>;
}

function BiasLedger({ biases }: { biases: BiasScore[] }) {
  return (
    <section className="bias-ledger" aria-labelledby="bias-ledger-heading">
      <header><div><p className="section-index">十一项偏差证据</p><h3 id="bias-ledger-heading">分数旁必须能看到来源</h3></div><p>低信号不等于确认不存在；任何分数都不能提高风险等级。</p></header>
      <ol>
        {biases.map((bias) => (
          <li key={bias.code} data-severity={bias.severity}>
            <span><strong>{bias.name}</strong><code>{bias.code}</code></span>
            <progress max="1" value={bias.score}>{formatRatio(bias.score)}</progress>
            <b>{formatRatio(bias.score)}</b>
            <StatusBadge tone={bias.severity === "high" ? "danger" : bias.severity === "watch" ? "warning" : "info"}>{severityCopy[bias.severity]}</StatusBadge>
            <details open={bias.severity === "high"}>
              <summary>查看证据与解释</summary>
              <p>{bias.description}</p>
              <ul>{bias.evidence.map((item, index) => <li key={`${item.source}-${index}`}><strong>{item.source_label} · {formatRatio(item.contribution)}</strong><span>{item.observation}</span><code>{item.source}</code></li>)}</ul>
              <p>{bias.explanation}</p>
            </details>
          </li>
        ))}
      </ol>
    </section>
  );
}

function InterventionLedger({ profile, busy, onAction }: { profile: BehaviorProfile; busy: boolean; onAction: (intervention: BehaviorIntervention, action: "complete" | "dismiss") => void }) {
  return (
    <section className="intervention-ledger" aria-labelledby="intervention-heading">
      <header><div><p className="section-index">个性化干预记录</p><h3 id="intervention-heading">由偏差、目标和场景共同选择</h3></div><span>实验组：{profile.assigned_variant_name}</span></header>
      {profile.interventions.length === 0 ? <p className="behavior-insufficient">本次未命中需要主动干预的偏差信号。</p> : (
        <ol>
          {profile.interventions.map((item) => {
            const coolingActive = Boolean(item.eligible_at && new Date(item.eligible_at).getTime() > Date.now());
            return (
              <li key={item.code} data-cooling={item.code === "cooling_period"}>
                <div><span>{item.scenario_code}</span><h4>{item.name}</h4><p>{item.personalized_message}</p></div>
                <dl>
                  <div><dt>触发偏差</dt><dd>{item.trigger_biases.join("、")}</dd></div>
                  <div><dt>关联目标</dt><dd>{item.linked_goal_name ?? "本次无已记录目标"}</dd></div>
                  <div><dt>状态</dt><dd>{item.status === "active" ? "进行中" : item.status === "completed" ? "已完成" : "已忽略"}</dd></div>
                  {item.cooling_period_hours ? <div><dt>冷静期</dt><dd>{item.cooling_period_hours} 小时 · {item.eligible_at ? `至 ${formatDateTime(item.eligible_at)}` : "完成实验后开始"}</dd></div> : null}
                </dl>
                <p className="intervention-action-copy">{item.action_instruction}</p>
                <small>{item.audit_note}</small>
                {item.intervention_id && item.status === "active" ? <div className="intervention-actions"><Button type="button" variant="secondary" disabled={busy || coolingActive} onClick={() => onAction(item, "complete")}>{coolingActive ? "冷静期进行中" : "标记已完成"}</Button><button className="text-button" type="button" disabled={busy} onClick={() => onAction(item, "dismiss")}>暂不采用</button></div> : null}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function ResponseLedger({ profile }: { profile: BehaviorProfile }) {
  return (
    <section className="behavior-response-ledger" aria-labelledby="behavior-response-heading">
      <header><div><p className="section-index">原始实验记录</p><h3 id="behavior-response-heading">选择、反应时间、修改与一致性</h3></div><p>平均 {profile.average_response_time_ms.toLocaleString("zh-CN")} ms · 修改 {profile.total_modification_count} 次 · 一致性 {formatRatio(profile.overall_consistency_score)}</p></header>
      <div className="data-table-wrap" tabIndex={0} role="region" aria-label="六项行为实验记录，可横向滚动">
        <table className="data-table"><thead><tr><th>实验</th><th>选择</th><th>反应时间</th><th>修改</th><th>一致性</th><th>证据解释</th></tr></thead><tbody>{profile.responses.map((item) => <tr key={item.experiment_code}><td><code>{item.experiment_code}</code></td><td>{item.choice_label}<small>{item.choice_code}</small></td><td>{item.response_time_ms.toLocaleString("zh-CN")} ms</td><td>{item.modification_count} 次</td><td>{formatRatio(item.consistency_score)}</td><td>{item.evidence}</td></tr>)}</tbody></table>
      </div>
    </section>
  );
}

function ABFrameworkView({ framework, open }: { framework: BehaviorABFramework; open: boolean }) {
  return (
    <section className="behavior-ab" aria-labelledby="behavior-ab-heading">
      <details open={open}>
        <summary><span><p className="section-index">A/B 框架 · {framework.framework_version}</p><h3 id="behavior-ab-heading">四组配置与合成／授权指标</h3></span><span>查看配置和指标</span></summary>
        <p>{framework.eligible_data_policy}。{framework.privacy_note}</p>
        <div className="data-table-wrap" tabIndex={0} role="region" aria-label="行为干预 A/B 指标，可横向滚动">
          <table className="data-table"><thead><tr><th>实验组</th><th>分配</th><th>完成 / 退出</th><th>完成率</th><th>平均反应</th><th>风险下调</th><th>干预完成</th></tr></thead><tbody>{framework.metrics.map((item) => <tr key={item.variant_code}><td><strong>{item.variant_name}</strong><small>{item.variant_code}</small></td><td>{item.assigned_count}</td><td>{item.completed_count} / {item.exited_count}</td><td>{item.completion_rate === null ? "样本不足" : formatRatio(item.completion_rate)}</td><td>{item.average_response_time_ms === null ? "—" : `${item.average_response_time_ms.toLocaleString("zh-CN")} ms`}</td><td>{item.risk_downshift_count}</td><td>{item.intervention_completed_count}</td></tr>)}</tbody></table>
        </div>
        <dl className="behavior-ab-definitions">{Object.entries(framework.metric_definitions).map(([code, definition]) => <div key={code}><dt>{code}</dt><dd>{definition}</dd></div>)}</dl>
      </details>
    </section>
  );
}

function BehaviorEvidence({ catalog, profile, view }: { catalog: BehaviorCatalog; profile: BehaviorProfile | null; view: BehaviorView }) {
  return (
    <section className="behavior-evidence" aria-labelledby="behavior-evidence-heading">
      <header><div><p className="section-index">规则与边界</p><h3 id="behavior-evidence-heading">确定性评分，不让 LLM 决定风险上限</h3></div><StatusBadge tone="info">{catalog.source_type}</StatusBadge></header>
      <div className="behavior-version-rail"><span>规则 {catalog.rule_version}</span><span>公式 {catalog.formula_version}</span><span>实验 {catalog.experiment_version}</span><span>A/B {catalog.ab_framework_version}</span>{profile ? <span>数据日 {formatDate(profile.meta.data_as_of)}</span> : null}</div>
      <p>{catalog.source_summary}</p><p>{catalog.behavior_boundary}</p>
      <details open={view === "risk"}><summary>查看模型限制</summary><ul>{(profile?.limitations ?? ["行为信息不足时不生成偏差分数。", "仅使用合成或授权测试数据。"]).map((item) => <li key={item}>{item}</li>)}</ul></details>
    </section>
  );
}

export function BehaviorPortalWorkspace({ view }: { view: "advisor" | "risk" }) {
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
      .catch(() => setError("无法读取家庭列表；没有运行行为画像或实验。"));
    return () => controller.abort();
  }, []);
  return (
    <section className="behavior-portal-wrapper">
      <label className="portal-household-control"><span>行为画像复核家庭</span><select value={householdId} onChange={(event) => setHouseholdId(event.target.value)} disabled={households.length === 0}>{households.map((household) => <option key={household.id} value={household.id}>{household.name} · {household.code}</option>)}</select></label>
      {error ? <p role="alert">{error}</p> : null}
      {householdId ? <BehaviorWorkspace householdId={householdId} view={view} /> : null}
    </section>
  );
}
