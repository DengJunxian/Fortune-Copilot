import { useEffect, useMemo, useState } from "react";
import {
  fetchDemoManifest,
  fetchFamilyComparison,
  fetchLatestExperiments,
  loadDemoData,
  preheatDemo,
  resetDemoData,
  retryMainDemo,
  runDemoExperiments,
  runMainDemo,
  type DemoControlResult,
  type DemoManifest,
  type DemoPreheatResult,
  type DemoRun,
  type ExperimentSuite,
  type FamilyComparison,
} from "../api/demo";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { AppLink } from "../router/Link";
import { formatDomainLabel, formatMoney, formatRatio } from "../utils/format";

type ActionName = "load" | "reset" | "preheat" | "run" | "retry" | "experiments";

const accountOrder = [
  "emergency_liquidity",
  "risk_protection",
  "stable_goals",
  "long_term_growth",
];

const accountShortNames: Record<string, string> = {
  emergency_liquidity: "日用与应急",
  risk_protection: "风险保障",
  stable_goals: "稳健目标",
  long_term_growth: "长期增长",
};

const experimentNames: Record<string, string> = {
  calculation_benchmark: "确定性计算与性能基准",
  suitability_adversarial: "适当性对抗测试",
  controlled_policy_qa: "政策问答可追溯性",
  prompt_injection: "提示注入防护",
  user_comprehension: "客户理解度调研协议",
  behavior_intervention_ab: "行为干预 A/B 协议",
  advisor_process_time: "顾问流程工时模拟",
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "操作未完成，请检查本地服务后重试。";
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : {};
}

function asString(value: unknown, fallback = "—"): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function moneyFromArtifact(value: unknown): string {
  const raw = asString(value, "");
  return raw && Number.isFinite(Number(raw)) ? formatMoney(raw, true) : "—";
}

function toneForStatus(status: string): "success" | "warning" | "info" | "danger" {
  if (status === "completed" || status === "passed" || status === "ready") return "success";
  if (status === "failed") return "danger";
  if (status === "protocol_ready") return "warning";
  return "info";
}

export function DemoPage() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [comparison, setComparison] = useState<FamilyComparison | null>(null);
  const [demoRun, setDemoRun] = useState<DemoRun | null>(null);
  const [experiments, setExperiments] = useState<ExperimentSuite | null>(null);
  const [controlResult, setControlResult] = useState<DemoControlResult | null>(null);
  const [preheatResult, setPreheatResult] = useState<DemoPreheatResult | null>(null);
  const [activeAction, setActiveAction] = useState<ActionName | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshOverview() {
    const [nextManifest, nextComparison, nextExperiments] = await Promise.allSettled([
      fetchDemoManifest(),
      fetchFamilyComparison(),
      fetchLatestExperiments(),
    ]);
    if (nextManifest.status === "fulfilled") setManifest(nextManifest.value);
    if (nextComparison.status === "fulfilled") setComparison(nextComparison.value);
    if (nextExperiments.status === "fulfilled") setExperiments(nextExperiments.value);
    if (nextManifest.status === "rejected" && nextComparison.status === "rejected") {
      throw nextManifest.reason;
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      fetchDemoManifest(controller.signal),
      fetchFamilyComparison(controller.signal),
      fetchLatestExperiments(controller.signal),
    ]).then(([nextManifest, nextComparison, nextExperiments]) => {
      if (controller.signal.aborted) return;
      if (nextManifest.status === "fulfilled") setManifest(nextManifest.value);
      if (nextComparison.status === "fulfilled") setComparison(nextComparison.value);
      if (nextExperiments.status === "fulfilled") setExperiments(nextExperiments.value);
      if (nextManifest.status === "rejected" && nextComparison.status === "rejected") {
        setError("本地后端尚未就绪。启动 Compose 后可在此运行完整业务演示；页面不会连接外网。" );
      }
    });
    return () => controller.abort();
  }, []);

  async function perform(action: ActionName, operation: () => Promise<void>) {
    setActiveAction(action);
    setError(null);
    try {
      await operation();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setActiveAction(null);
    }
  }

  const diagnosis = asRecord(demoRun?.artifacts.diagnosis);
  const planning = asRecord(demoRun?.artifacts.planning);
  const planningAccounts = asRecord(planning.accounts);
  const report = asRecord(demoRun?.artifacts.report);
  const review = asRecord(demoRun?.artifacts.review);
  const audit = asRecord(demoRun?.artifacts.audit);
  const targetResults = asRecord(demoRun?.metrics.target_results);
  const allTargetsPass = useMemo(
    () => Object.keys(targetResults).length > 0 && Object.values(targetResults).every(Boolean),
    [targetResults],
  );

  return (
    <main className="page-shell demo-release-page" id="main-content">
      <header className="demo-release-hero">
        <div>
          <p className="page-kicker">提示词 13 · 发布级完整演示</p>
          <h1>从一句家庭描述，到八章规划书与可追溯审核</h1>
          <p>
            主线使用 35 岁双收入育儿合成家庭。所有金额、比率、四账户配置与压力结果由确定性工具计算；
            语言模型不负责算数，Mock 模式不访问真实银行或外部网络。
          </p>
        </div>
        <dl className="demo-release-summary" aria-label="演示就绪状态">
          <div>
            <dt>数据集</dt>
            <dd>{manifest?.dataset_version ?? "等待本地服务"}</dd>
          </div>
          <div>
            <dt>合成家庭</dt>
            <dd>{manifest ? `${manifest.seeded_household_count} Personas` : "—"}</dd>
          </div>
          <div>
            <dt>外部网络</dt>
            <dd>0 次</dd>
          </div>
          <div>
            <dt>运行状态</dt>
            <dd>
              <StatusBadge tone={toneForStatus(demoRun?.status ?? (manifest?.ready ? "ready" : "idle"))}>
                {demoRun?.status === "completed" ? "已完成" : demoRun?.status === "failed" ? "可恢复" : manifest?.ready ? "已就绪" : "待连接"}
              </StatusBadge>
            </dd>
          </div>
        </dl>
      </header>

      <section className="demo-operation-rail" aria-labelledby="demo-control-heading">
        <div>
          <p className="section-index">CONTROL / 01</p>
          <h2 id="demo-control-heading">演示控制台</h2>
          <p>加载、重置和预热均只作用于本地合成数据。完整运行会自动加载、预热并执行十阶段主线。</p>
        </div>
        <div className="demo-operation-actions">
          <Button
            variant="secondary"
            loading={activeAction === "load"}
            disabled={activeAction !== null}
            onClick={() => perform("load", async () => {
              setControlResult(await loadDemoData());
              await refreshOverview();
            })}
          >
            加载 A-H Persona
          </Button>
          <Button
            variant="danger"
            loading={activeAction === "reset"}
            disabled={activeAction !== null}
            onClick={() => perform("reset", async () => {
              setDemoRun(null);
              setExperiments(null);
              setControlResult(await resetDemoData());
              await refreshOverview();
            })}
          >
            重置合成数据
          </Button>
          <Button
            variant="secondary"
            loading={activeAction === "preheat"}
            disabled={activeAction !== null}
            onClick={() => perform("preheat", async () => {
              setPreheatResult(await preheatDemo());
              await refreshOverview();
            })}
          >
            本地预热
          </Button>
          <Button
            loading={activeAction === "run"}
            disabled={activeAction !== null}
            onClick={() => perform("run", async () => {
              setControlResult(await loadDemoData());
              setPreheatResult(await preheatDemo());
              setDemoRun(await runMainDemo());
              await refreshOverview();
            })}
          >
            运行完整演示
          </Button>
          <Button
            variant="secondary"
            loading={activeAction === "experiments"}
            disabled={activeAction !== null}
            onClick={() => perform("experiments", async () => {
              setExperiments(await runDemoExperiments());
            })}
          >
            运行七项实验
          </Button>
        </div>
        <div className="demo-operation-feedback" role="status" aria-live="polite">
          {activeAction ? <span>正在执行本地任务：{activeAction}</span> : null}
          {controlResult ? <span>{controlResult.message}</span> : null}
          {preheatResult ? <span>预热完成：{preheatResult.warmed_components.length} 个组件，外部请求 {preheatResult.external_network_calls} 次。</span> : null}
          {error ? <strong>{error}</strong> : null}
          {demoRun?.status === "failed" ? (
            <Button
              variant="secondary"
              loading={activeAction === "retry"}
              disabled={activeAction !== null}
              onClick={() => perform("retry", async () => {
                setDemoRun(await retryMainDemo(demoRun.run_id));
              })}
            >
              从失败记录安全重试
            </Button>
          ) : null}
        </div>
      </section>

      <section className="demo-story-section" aria-labelledby="demo-story-heading">
        <header className="section-header-row">
          <div>
            <p className="section-index">STORY / 02</p>
            <h2 id="demo-story-heading">十阶段证据链</h2>
          </div>
          <p>{demoRun ? `运行 ${demoRun.run_id.slice(0, 8)} · ${demoRun.progress_percent}%` : "运行后逐阶段写入数据库与审计事件"}</p>
        </header>
        {demoRun ? (
          <ol className="demo-stage-timeline" aria-label="主 Demo 十阶段进度">
            {demoRun.stages.map((stage, index) => (
              <li key={`${stage.code}-${index}`} data-status={stage.status}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{stage.label}</h3>
                  <code>{stage.code}</code>
                </div>
                <strong>{stage.progress_percent}%</strong>
                <small>{stage.duration_ms} ms</small>
                <StatusBadge tone={toneForStatus(stage.status)}>
                  {stage.status === "completed" ? "完成" : "失败"}
                </StatusBadge>
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty-state">尚未运行。启动完整演示后，此处显示每一步的实际耗时、状态与持久化证据。</p>
        )}
      </section>

      {demoRun?.status === "completed" ? (
        <section className="demo-evidence-section" aria-labelledby="demo-evidence-heading">
          <header className="section-header-row">
            <div>
              <p className="section-index">EVIDENCE / 03</p>
              <h2 id="demo-evidence-heading">关键结果，不靠语言模型计算</h2>
            </div>
            <p>{allTargetsPass ? "本机四项性能门槛全部通过" : "性能结果以本次运行记录为准"}</p>
          </header>
          <div className="demo-evidence-ledger">
            <article>
              <span>家庭净资产</span>
              <strong>{moneyFromArtifact(diagnosis.net_worth)}</strong>
              <small>信用卡额度未计入资产</small>
            </article>
            <article>
              <span>房产集中度</span>
              <strong>{diagnosis.property_concentration ? formatRatio(asString(diagnosis.property_concentration)) : "—"}</strong>
              <small>由资产负债表确定性计算</small>
            </article>
            <article>
              <span>保障缺口</span>
              <strong>{moneyFromArtifact(diagnosis.protection_gap)}</strong>
              <small>不把保险描述为统一保本产品</small>
            </article>
            <article>
              <span>应急覆盖</span>
              <strong>{diagnosis.emergency_months ? `${Number(diagnosis.emergency_months).toFixed(1)} 个月` : "—"}</strong>
              <small>安全月数随家庭阶段动态变化</small>
            </article>
          </div>
          <div className="data-table-wrap">
            <table className="data-table demo-account-table">
              <caption>主家庭动态四账户结果；金额不是固定比例拆分</caption>
              <thead>
                <tr>
                  <th scope="col">顺序</th>
                  <th scope="col">账户</th>
                  <th scope="col">建议金额</th>
                  <th scope="col">缺口／余量</th>
                  <th scope="col">边界</th>
                </tr>
              </thead>
              <tbody>
                {accountOrder.map((bucket, index) => {
                  const account = asRecord(planningAccounts[bucket]);
                  return (
                    <tr key={bucket}>
                      <td className="numeric-cell">{String(index + 1).padStart(2, "0")}</td>
                      <th scope="row">{asString(account.name, accountShortNames[bucket])}</th>
                      <td className="numeric-cell">{moneyFromArtifact(account.recommended_amount)}</td>
                      <td className="numeric-cell">{moneyFromArtifact(account.gap_amount)}</td>
                      <td>{bucket === "long_term_growth" ? "70% 仅约束合格长期资金，不是家庭总资产" : "按安全约束与目标期限计算"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="demo-handoff-strip">
            <div>
              <span>八章规划书</span>
              <strong>{asString(report.chapter_count, "0")} / 8</strong>
              <small>{asString(report.action_count, "0")} 项行动</small>
            </div>
            <div>
              <span>审核状态</span>
              <strong>{asString(review.workflow_state)}</strong>
              <small>人工合规与客户确认不会被自动冒充</small>
            </div>
            <div>
              <span>九项智能服务终检</span>
              <strong>{asString(audit.agent_step_count, "0")} 步</strong>
              <small>金额仍只来自确定性账本</small>
            </div>
            <nav aria-label="演示结果转交">
              <AppLink to="/client">查看客户端规划书</AppLink>
              <AppLink to="/advisor">查看顾问底稿</AppLink>
              <AppLink to="/risk">查看风险与审计</AppLink>
            </nav>
          </div>
        </section>
      ) : null}

      <section className="demo-comparison-section" aria-labelledby="demo-comparison-heading">
        <header className="section-header-row">
          <div>
            <p className="section-index">COMPARISON / 04</p>
            <h2 id="demo-comparison-heading">A／B／C：同一规则，不同配置</h2>
          </div>
          <p>{comparison ? `${comparison.unique_configuration_count} 个唯一配置签名` : "等待 A／B／C 对照计算"}</p>
        </header>
        {comparison ? (
          <>
            <div className="data-table-wrap">
              <table className="data-table demo-comparison-table">
                <caption>{comparison.conclusion}</caption>
                <thead>
                  <tr>
                    <th scope="col">家庭</th>
                    <th scope="col">生命周期</th>
                    <th scope="col">净资产</th>
                    <th scope="col">动态安全月数</th>
                    {accountOrder.map((bucket) => <th scope="col" key={bucket}>{accountShortNames[bucket]}</th>)}
                    <th scope="col">配置签名</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.rows.map((row) => (
                    <tr key={row.household_id}>
                      <th scope="row"><strong>{row.code}</strong><small>{row.profile}</small></th>
                      <td>{formatDomainLabel(row.lifecycle_stage)}</td>
                      <td className="numeric-cell">{formatMoney(row.net_worth, true)}</td>
                      <td className="numeric-cell">{Number(row.dynamic_safety_months).toFixed(1)}</td>
                      {accountOrder.map((bucket) => {
                        const account = row.accounts.find((item) => item.bucket === bucket);
                        return <td className="numeric-cell" key={bucket}>{account ? formatMoney(account.recommended_amount, true) : "—"}</td>;
                      })}
                      <td><code>{row.configuration_signature}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="demo-boundary-note">{comparison.boundary_note}</p>
          </>
        ) : (
          <p className="empty-state">连接本地后端后显示 A-H 八类 Persona；其中 A／B／C 保留动态配置对照。</p>
        )}
      </section>

      <section className="demo-experiment-section" aria-labelledby="demo-experiment-heading">
        <header className="section-header-row">
          <div>
            <p className="section-index">EXPERIMENTS / 05</p>
            <h2 id="demo-experiment-heading">七项发布实验与边界</h2>
          </div>
          <p>{experiments ? `${experiments.cases.length} / 7 已记录` : "真实参与者实验仅提供协议，不伪造结果"}</p>
        </header>
        {experiments ? (
          <ol className="demo-experiment-ledger" aria-label="七项发布实验">
            {experiments.cases.map((item, index) => (
              <li key={item.code}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{experimentNames[item.code] ?? item.name}</h3>
                  <p>{item.boundary_note}</p>
                  <small>{item.evidence.join("；")}</small>
                </div>
                <StatusBadge tone={toneForStatus(item.status)}>
                  {item.status === "passed" ? "本地通过" : item.status === "protocol_ready" ? "协议就绪" : "失败"}
                </StatusBadge>
                <strong>{item.measured ? "已测量" : "未宣称实测"}</strong>
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty-state">运行实验后写入独立实验账本。客户理解度和顾问工时只记录可执行协议，不虚构工行实测数据。</p>
        )}
      </section>

      <section className="demo-release-assets" aria-labelledby="demo-release-heading">
        <header>
          <div>
            <p className="section-index">RELEASE / 06</p>
            <h2 id="demo-release-heading">离线发布清单</h2>
          </div>
          <StatusBadge tone={manifest && Object.values(manifest.release_assets).every(Boolean) ? "success" : "warning"}>
            {manifest && Object.values(manifest.release_assets).every(Boolean) ? "资产齐备" : "正在补齐"}
          </StatusBadge>
        </header>
        <ul>
          {Object.entries(manifest?.release_assets ?? {}).map(([name, ready]) => (
            <li key={name}>
              <code>{name}</code>
              <span>{ready ? "已提供" : "未提供"}</span>
            </li>
          ))}
        </ul>
        <p>该页面及主 Demo 不加载外部字体、图片、脚本或模型；服务不可用时保留诚实的降级说明。</p>
      </section>
    </main>
  );
}
