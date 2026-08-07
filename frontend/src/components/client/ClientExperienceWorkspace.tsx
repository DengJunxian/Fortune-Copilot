import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import {
  fetchClientExperience,
  type ClientExperience,
  type ClientView,
} from "../../api/clientExperience";
import type { FinancialAnalysis, MetricResult } from "../../api/financial";
import { fetchPlanning, type PlanningResponse } from "../../api/planning";
import { useDisplayPreferences } from "../../contexts/displayPreferences";
import {
  formatDate,
  formatDomainLabel,
  formatMetricValue,
  formatMoney,
  formatPercentagePoint,
  formatRatio,
} from "../../utils/format";
import { BehaviorWorkspace } from "../behavior/BehaviorWorkspace";
import {
  BalanceOverviewChart,
  CashFlowWaterfallChart,
  GoalTimelineChart,
} from "../charts/FinancialCharts";
import { HealthRadar } from "../financial/HealthRadar";
import { MetricInspector } from "../financial/MetricInspector";
import { StatementWorkspace } from "../financial/StatementWorkspace";
import { PlanningWorkspace } from "../planning/PlanningWorkspace";
import { PortfolioWorkspace } from "../portfolio/PortfolioWorkspace";
import { TrustWorkspace } from "../trust/TrustWorkspace";
import { TwinWorkspace } from "../twin/TwinWorkspace";
import { Button } from "../ui/Button";
import { FinancialTerm } from "../ui/FinancialValue";
import { StatusBadge } from "../ui/StatusBadge";
import { ActionCalendar } from "./ActionCalendar";
import { ClientPreferences } from "./ClientPreferences";
import { ClientStatePreview } from "./ClientStatePreview";
import { PlanningReportWorkspace } from "./PlanningReportWorkspace";
import { PrivacyCenter } from "./PrivacyCenter";
import { ClientPlanConfirmation } from "../workflow/ClientPlanConfirmation";

const taskViews: Array<{ code: ClientView; label: string; short: string }> = [
  { code: "family", label: "家庭画像", short: "家庭" },
  { code: "balance", label: "资产负债", short: "资产" },
  { code: "cashflow", label: "家庭现金流", short: "现金流" },
  { code: "health", label: "财务健康", short: "健康" },
  { code: "accounts", label: "四账户", short: "账户" },
  { code: "goals", label: "目标时间轴", short: "目标" },
  { code: "twin", label: "数字孪生", short: "孪生" },
  { code: "behavior", label: "行为实验", short: "行为" },
  { code: "report", label: "家庭规划书", short: "规划书" },
  { code: "actions", label: "行动日历", short: "行动" },
  { code: "privacy", label: "隐私中心", short: "隐私" },
];

const overviewMetricIds = [
  "net_worth",
  "liquidity_reserve_months",
  "debt_to_asset_ratio",
  "savings_ratio",
];

const statusCopy: Record<MetricResult["status"], string> = {
  strong: "表现较强",
  healthy: "区间内",
  attention: "需要关注",
  warning: "建议处理",
  critical: "优先处理",
  review: "需要复核",
  not_applicable: "不适用",
};

function statusTone(status: MetricResult["status"]): "success" | "warning" | "info" | "danger" {
  if (status === "strong" || status === "healthy") return "success";
  if (status === "critical") return "danger";
  if (status === "attention" || status === "warning") return "warning";
  return "info";
}

export function ClientExperienceWorkspace({
  analysis,
  initialView = "family",
}: {
  analysis: FinancialAnalysis;
  initialView?: ClientView;
}) {
  const householdId = analysis.meta.household_id;
  const { maskAmounts, valueView } = useDisplayPreferences();
  const [activeView, setActiveView] = useState<ClientView>(initialView);
  const [experience, setExperience] = useState<ClientExperience | null>(null);
  const [plan, setPlan] = useState<PlanningResponse | null>(null);
  const [experienceLoading, setExperienceLoading] = useState(true);
  const [experienceError, setExperienceError] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<MetricResult | null>(null);

  const refreshExperience = useCallback(async (signal?: AbortSignal) => {
    setExperienceLoading(true);
    setExperienceError(null);
    try {
      const [experienceResult, planResult] = await Promise.allSettled([
        fetchClientExperience(householdId, signal),
        fetchPlanning(householdId, signal),
      ]);
      if (signal?.aborted) return;
      if (experienceResult.status === "fulfilled") setExperience(experienceResult.value);
      else {
        setExperience(null);
        setExperienceError("客户旅程元数据暂不可用；财务底表与确定性计算仍可继续查看。");
      }
      setPlan(planResult.status === "fulfilled" ? planResult.value : null);
    } finally {
      if (!signal?.aborted) setExperienceLoading(false);
    }
  }, [householdId]);

  useEffect(() => {
    const controller = new AbortController();
    setActiveView(initialView);
    setSelectedMetric(null);
    void refreshExperience(controller.signal);
    return () => controller.abort();
  }, [initialView, refreshExperience]);

  useEffect(() => {
    if (activeView !== "accounts" || window.location.hash !== "#fund-advisory") return;
    const scrollToAdvisory = () => {
      const target = document.getElementById("fund-advisory");
      if (!target) return false;
      target.scrollIntoView?.({ block: "start" });
      return true;
    };
    if (scrollToAdvisory()) return;
    const observer = new MutationObserver(() => {
      if (scrollToAdvisory()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const timeout = window.setTimeout(() => observer.disconnect(), 10_000);
    return () => {
      observer.disconnect();
      window.clearTimeout(timeout);
    };
  }, [activeView, householdId]);

  const activeDefinition = taskViews.find((item) => item.code === activeView) ?? taskViews[0]!;
  const completedJourney = experience?.journey.filter((step) => step.status === "completed").length ?? 0;

  function navigate(view: ClientView, focusHeading = true) {
    setActiveView(view);
    if (focusHeading) {
      window.requestAnimationFrame(() => {
        document.querySelector<HTMLElement>("#client-view-heading")?.focus();
      });
    }
  }

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? taskViews.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + taskViews.length) % taskViews.length;
    const next = taskViews[nextIndex];
    if (!next) return;
    navigate(next.code, false);
    document.querySelector<HTMLButtonElement>(`#client-task-${next.code}`)?.focus();
  }

  return (
    <section className="client-experience" aria-label="客户端完整旅程">
      <div className="client-journey-bar">
        <nav aria-label="当前位置" className="client-breadcrumb">
          <ol><li>客户端</li><li aria-current="page">{activeDefinition.label}</li></ol>
        </nav>
        <div className="client-journey-actions">
          <span>{experienceLoading ? "正在核对旅程" : `旅程 ${completedJourney}/${experience?.journey.length ?? 13}`}</span>
          <Button type="button" variant="secondary" onClick={() => navigate("health")}>3 分钟快速体检</Button>
          <Button type="button" onClick={() => navigate((experience?.privacy.active_consent_count ?? 0) > 0 ? "accounts" : "privacy")}>进入深度规划</Button>
        </div>
      </div>

      {experienceError ? <p className="client-degraded-state" role="status"><strong>解释层降级</strong>{experienceError}</p> : null}
      <ClientPreferences />

      <nav className="client-task-nav" aria-label="客户任务工作区">
        <div role="tablist" aria-label="十一项客户任务">
          {taskViews.map((item, index) => (
            <button
              key={item.code}
              id={`client-task-${item.code}`}
              type="button"
              role="tab"
              aria-label={item.label}
              aria-selected={activeView === item.code}
              aria-controls="client-task-panel"
              tabIndex={activeView === item.code ? 0 : -1}
              onClick={() => navigate(item.code)}
              onKeyDown={(event) => handleTabKey(event, index)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item.label}</strong>
              <small>{item.short}</small>
            </button>
          ))}
        </div>
      </nav>

      <div id="client-task-panel" className="client-task-panel" role="tabpanel" aria-labelledby={`client-task-${activeView}`}>
        {activeView === "family" ? <FamilyView analysis={analysis} experience={experience} masked={maskAmounts} onNavigate={navigate} /> : null}
        {activeView === "balance" ? (
          <TaskSection kicker="家庭资产负债表" title="每一笔资产与负债都能回到底稿" description="信用卡额度从不进入资产；待还款余额只在负债中核算。">
            <SensitiveRegion masked={maskAmounts} label="资产负债金额">
              <BalanceOverviewChart analysis={analysis} />
              <StatementWorkspace statements={analysis.statements} initialTab="balance" showTabs={false} />
            </SensitiveRegion>
          </TaskSection>
        ) : null}
        {activeView === "cashflow" ? (
          <TaskSection kicker="家庭现金流" title="先看钱从哪里来，再看被什么占用" description="收入、必要支出、还贷、保险、教育赡养、弹性消费与结余按互斥口径展开。">
            <SensitiveRegion masked={maskAmounts} label="家庭现金流金额">
              <CashFlowWaterfallChart analysis={analysis} />
              <StatementWorkspace statements={analysis.statements} initialTab="cashflow" showTabs={false} />
            </SensitiveRegion>
          </TaskSection>
        ) : null}
        {activeView === "health" ? <HealthView analysis={analysis} masked={maskAmounts} onSelectMetric={setSelectedMetric} /> : null}
        {activeView === "accounts" ? (
          <TaskSection kicker="动态四账户" title="账户用途由目标和安全闸门决定" description="四账户不是固定比例模板；每次建议都保留分母、区间、条件与约束证据。">
            <SensitiveRegion masked={maskAmounts} label="四账户金额与配置">
              <PlanningWorkspace householdId={householdId} focus="accounts" preferredValueView={valueView} />
              <PortfolioWorkspace householdId={householdId} />
            </SensitiveRegion>
          </TaskSection>
        ) : null}
        {activeView === "goals" ? (
          <TaskSection kicker="目标与方案比较" title="把期限、准备率和冲突放在同一条时间轴" description="准备率不冒充成功概率；方案调整由同一版本确定性规则重新计算。">
            <SensitiveRegion masked={maskAmounts} label="目标金额与方案比较">
              {plan ? <GoalTimelineChart plan={plan} /> : <InlineState title="目标图表暂不可用" detail="规划 API 未返回数据；下方工作区可独立重试。" />}
              <PlanningWorkspace householdId={householdId} focus="goals" preferredValueView={valueView} />
            </SensitiveRegion>
          </TaskSection>
        ) : null}
        {activeView === "twin" ? (
          <TaskSection kicker="家庭财富数字孪生" title="用区间观察路径，不把中位线说成承诺" description="所有随机假设、种子、路径数量与压力事件均可核验。">
            <SensitiveRegion masked={maskAmounts} label="数字孪生金额与路径"><TwinWorkspace householdId={householdId} /></SensitiveRegion>
          </TaskSection>
        ) : null}
        {activeView === "behavior" ? (
          <TaskSection kicker="行为实验" title="先验证表达，再决定是否扩大使用" description="实验只改变表达或流程，不改变确定性金额和适当性边界。">
            <SensitiveRegion masked={maskAmounts} label="行为实验中的家庭金额"><BehaviorWorkspace householdId={householdId} /></SensitiveRegion>
          </TaskSection>
        ) : null}
        {activeView === "report" ? experienceLoading ? <InlineState title="正在编排八章规划书" detail="章节只会在计算与引用完整后展示。" /> : experience ? (
          <SensitiveRegion masked={maskAmounts} label="家庭规划书金额与方案确认">
            <PlanningReportWorkspace experience={experience} onNavigate={navigate} />
            <ClientPlanConfirmation householdId={householdId} delivery={experience.delivery} />
          </SensitiveRegion>
        ) : <InlineState title="规划书生成失败" detail="客户体验聚合服务不可用；系统没有生成缺章或补造数字的报告。" /> : null}
        {activeView === "actions" ? experienceLoading ? <InlineState title="正在生成行动日历" detail="核对行动来源、金额和期限。" /> : experience ? (
          <SensitiveRegion masked={maskAmounts} label="行动金额"><ActionCalendar householdId={householdId} groups={experience.action_calendar} delivery={experience.delivery} /></SensitiveRegion>
        ) : <InlineState title="行动日历暂不可用" detail="保存确定性规划草案后重试。" /> : null}
        {activeView === "privacy" ? experienceLoading ? <InlineState title="正在读取授权账本" detail="隐私操作需要最新记录版本。" /> : experience ? (
          <PrivacyCenter experience={experience} onRefresh={() => refreshExperience()} />
        ) : <InlineState title="隐私中心暂不可用" detail="当前未读取到授权版本；系统不会接受未经核对的撤回或删除请求。" /> : null}
      </div>

      {experience?.journey ? <JourneyLedger experience={experience} onNavigate={navigate} /> : null}
      <ClientStatePreview />
      <MetricInspector metric={selectedMetric} onClose={() => setSelectedMetric(null)} />
    </section>
  );
}

function TaskSection({ kicker, title, description, children }: { kicker: string; title: string; description: string; children: ReactNode }) {
  return (
    <section className="client-view">
      <header className="client-view-header">
        <div><p className="page-kicker">{kicker}</p><h2 id="client-view-heading" tabIndex={-1}>{title}</h2><p>{description}</p></div>
      </header>
      {children}
    </section>
  );
}

function SensitiveRegion({ masked, label, children }: { masked: boolean; label: string; children: ReactNode }) {
  if (masked) {
    return (
      <section className="sensitive-region-masked" aria-label={`${label}已隐藏`}>
        <span aria-hidden="true">••••</span><h3>金额已隐藏</h3><p>{label}不会出现在屏幕或辅助技术可读树中。关闭“隐藏金额”后再查看。</p>
      </section>
    );
  }
  return <>{children}</>;
}

function FamilyView({ analysis, experience, masked, onNavigate }: { analysis: FinancialAnalysis; experience: ClientExperience | null; masked: boolean; onNavigate: (view: ClientView) => void }) {
  return (
    <section className="client-view family-view">
      <header className="client-view-header">
        <div><p className="page-kicker">家庭画像与责任关系</p><h2 id="client-view-heading" tabIndex={-1}>{analysis.profile.name}</h2><p>先确认家庭成员、生命周期和数据授权，再进入任何配置或情景推演。</p></div>
        <dl className="family-facts">
          <div><dt>生命周期</dt><dd>{formatDomainLabel(analysis.profile.lifecycle_stage)}</dd></div>
          <div><dt>地区</dt><dd>{analysis.profile.region}</dd></div>
          <div><dt>数据状态</dt><dd>{analysis.profile.is_user_confirmed ? "家庭已确认" : "待家庭确认"}</dd></div>
        </dl>
      </header>
      <div className="family-tree" role="list" aria-label="家庭成员关系">
        {analysis.profile.members.map((member, index) => (
          <article key={member.id} role="listitem" data-primary={index === 0}>
            <span aria-hidden="true">{member.display_name.slice(0, 1)}</span>
            <div><strong>{member.display_name}</strong><small>{formatDomainLabel(member.relationship)} · {member.age} 岁</small></div>
            <dl><div><dt>职业</dt><dd>{member.occupation ?? "待补"}</dd></div><div><dt>就业稳定性</dt><dd>{formatDomainLabel(member.employment_stability)}</dd></div><div><dt>健康风险</dt><dd>{formatDomainLabel(member.health_risk_level)}</dd></div></dl>
          </article>
        ))}
      </div>
      <div className="family-next-actions">
        <button type="button" onClick={() => onNavigate("privacy")}><span>01</span><strong>核对授权范围</strong><small>{experience ? `${experience.privacy.active_consent_count} 项有效授权` : "等待授权账本"}</small></button>
        <button type="button" onClick={() => onNavigate("health")}><span>02</span><strong>查看财务体检</strong><small>{analysis.metrics.length} 项确定性指标</small></button>
        <button type="button" onClick={() => onNavigate("accounts")}><span>03</span><strong>进入动态规划</strong><small>先安全、后增长</small></button>
      </div>
      <SensitiveRegion masked={masked} label="家庭画像中的敏感金额">
        <TrustWorkspace householdId={analysis.meta.household_id} />
      </SensitiveRegion>
    </section>
  );
}

function HealthView({ analysis, masked, onSelectMetric }: { analysis: FinancialAnalysis; masked: boolean; onSelectMetric: (metric: MetricResult) => void }) {
  const overviewMetrics = useMemo(
    () => overviewMetricIds.map((id) => analysis.metrics.find((metric) => metric.metric_id === id)).filter((metric): metric is MetricResult => Boolean(metric)),
    [analysis.metrics],
  );
  return (
    <section className="client-view health-view">
      <header className="client-view-header"><div><p className="page-kicker">财务健康体检</p><h2 id="client-view-heading" tabIndex={-1}>结论、依据与行动在同一页核对</h2><p>雷达图只定位薄弱维度；任何判断都能回到公式、代入、阈值与数据日。</p></div></header>
      <div className="overview-layout">
        <SensitiveRegion masked={masked} label="财务健康指标金额">
          <div className="metric-ledger">
            {overviewMetrics.map((metric) => <MetricSummaryButton key={metric.metric_id} metric={metric} onSelect={onSelectMetric} />)}
          </div>
        </SensitiveRegion>
        <HealthRadar dimensions={analysis.health_dimensions} dataAsOf={formatDate(analysis.meta.data_as_of)} ruleVersion={analysis.meta.rule_version} />
      </div>
      <SensitiveRegion masked={masked} label="完整财务健康指标与保障缺口">
        <section className="metrics-section" aria-labelledby="metrics-heading">
          <header className="section-header-row"><div><p className="section-index">指标账本</p><h3 id="metrics-heading">全量财务健康指标</h3></div><p>{analysis.metrics.length} 项纯函数结果；分母缺失时显示“不适用”。</p></header>
          <div className="data-table-wrap" role="region" tabIndex={0} aria-label="财务健康指标表">
            <table className="data-table metric-table"><thead><tr><th>指标</th><th>当前值</th><th>实际代入</th><th>参考条件</th><th>判断</th><th><span className="visually-hidden">操作</span></th></tr></thead><tbody>
              {analysis.metrics.map((metric) => <tr key={metric.metric_id}><td><strong><FinancialTerm term={metric.name} /></strong><small>{metric.metric_id}</small></td><td className="numeric-cell">{formatMetricValue(metric)}</td><td><code>{metric.substitution}</code></td><td>{metric.reference.reference_range}<small>{metric.reference.source_type}</small></td><td><StatusBadge tone={statusTone(metric.status)}>{statusCopy[metric.status]}</StatusBadge></td><td><button className="text-button" type="button" onClick={() => onSelectMetric(metric)}>审计详情</button></td></tr>)}
            </tbody></table>
          </div>
        </section>
        <RiskAndPurchasingPower analysis={analysis} />
      </SensitiveRegion>
      <Diagnostics analysis={analysis} />
    </section>
  );
}

function MetricSummaryButton({ metric, onSelect }: { metric: MetricResult; onSelect: (metric: MetricResult) => void }) {
  return <button className="metric-summary" type="button" aria-label={`查看${metric.name}详情`} onClick={() => onSelect(metric)}><span><b><FinancialTerm term={metric.name} /></b><code>{metric.metric_id}</code></span><strong>{formatMetricValue(metric, true)}</strong><span><StatusBadge tone={statusTone(metric.status)}>{statusCopy[metric.status]}</StatusBadge><small>{metric.reference.reference_range}</small></span></button>;
}

function RiskAndPurchasingPower({ analysis }: { analysis: FinancialAnalysis }) {
  const significantRisk = analysis.protection.risks.find((risk) => risk.risk_code === analysis.protection.most_significant_risk);
  return (
    <section className="two-column-analysis" aria-label="保障与购买力分析">
      <article className="analysis-panel"><p className="section-index">家庭责任</p><h3>四类保障缺口</h3><p>{analysis.protection.counting_note}</p><ul className="risk-ledger">{analysis.protection.risks.map((risk) => <li key={risk.risk_code}><span><strong>{risk.name}</strong><small>{risk.basis}</small></span><span>缺口 <b>{formatMoney(risk.gap)}</b><small>覆盖率 {risk.coverage_ratio === null ? "不适用" : formatRatio(risk.coverage_ratio)}</small></span></li>)}</ul><p className="panel-conclusion">优先风险：{significantRisk?.name ?? analysis.protection.most_significant_risk}。这是需求测算，不构成具体产品推荐。</p></article>
      <article className="analysis-panel"><p className="section-index">购买力</p><h3>把不同口径分开看</h3><dl className="purchasing-list"><div><dt>{analysis.purchasing_power.official_cpi.name}</dt><dd>{formatRatio(analysis.purchasing_power.official_cpi.rate)}<small>{analysis.purchasing_power.official_cpi.source_type}</small></dd></div><div><dt>{analysis.purchasing_power.family_weighted_inflation.name}</dt><dd>{formatRatio(analysis.purchasing_power.family_weighted_inflation.rate)}<small>按家庭支出权重</small></dd></div><div><dt>{analysis.purchasing_power.minimum_wage_catch_up.name}</dt><dd>{formatRatio(analysis.purchasing_power.minimum_wage_catch_up.rate)}<small>不是 CPI，也不是收益保证</small></dd></div></dl><p className="panel-conclusion">目标成本增速逐项保存；最低工资追赶参数与 CPI、投资回报假设严格分离。</p></article>
    </section>
  );
}

function Diagnostics({ analysis }: { analysis: FinancialAnalysis }) {
  const diagnostics = analysis.diagnostics;
  return (
    <section className="diagnostics-section" aria-labelledby="diagnostics-heading"><header className="section-header-row"><div><p className="section-index">数据诊断</p><h3 id="diagnostics-heading">先修数据，再解释结果</h3></div><p>完整度 {formatPercentagePoint(diagnostics.completeness_score)} · 通过 {diagnostics.passed_checks} 项 · 发现 {diagnostics.issue_count} 项</p></header>{diagnostics.issues.length === 0 ? <p className="empty-state">未发现需处理的数据问题。</p> : <ol className="diagnostic-list">{diagnostics.issues.map((issue) => <li key={`${issue.code}-${issue.related_record_ids.join("-")}`} data-severity={issue.severity}><span>{issue.severity}</span><div><strong>{issue.title}</strong><p>{issue.detail}</p><small>下一步：{issue.action}</small></div></li>)}</ol>}</section>
  );
}

function JourneyLedger({ experience, onNavigate }: { experience: ClientExperience; onNavigate: (view: ClientView) => void }) {
  return (
    <details className="journey-ledger"><summary>查看完整客户旅程与阻塞原因</summary><ol>{experience.journey.map((step, index) => <li key={step.code} data-status={step.status}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{step.label}</strong><p>{step.reason}</p></div><button type="button" onClick={() => onNavigate(step.view)}>{step.action}</button></li>)}</ol></details>
  );
}

function InlineState({ title, detail }: { title: string; detail: string }) {
  return <section className="client-inline-state" role="status"><h2 id="client-view-heading" tabIndex={-1}>{title}</h2><p>{detail}</p></section>;
}
