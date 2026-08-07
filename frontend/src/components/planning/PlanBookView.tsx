import {
  ArrowLeftIcon,
  CheckCircleIcon,
  FileTextIcon,
  PrinterIcon,
} from "@phosphor-icons/react";
import { useMemo, useRef, useState } from "react";
import type { FinancialAnalysis, MetricResult } from "../../api/financial";
import type { PlanningResponse } from "../../api/planning";
import type {
  KycProfile,
  PlanNarrative,
  PlanningGoalDraft,
  RatioExplanationItem,
} from "../../api/wealthPlanning";
import {
  formatDomainLabel,
  formatMetricValue,
  formatMoney,
  formatRatio,
} from "../../utils/format";
import type { MajorExpenseDraft } from "./planningDraft";
import { FundAdvisoryWorkspace } from "../portfolio/FundAdvisoryWorkspace";

interface PlanBookViewProps {
  analysis: FinancialAnalysis;
  explanations: RatioExplanationItem[];
  goals: PlanningGoalDraft[];
  majorExpenses: MajorExpenseDraft[];
  kyc: KycProfile;
  planning: PlanningResponse;
  narrative: PlanNarrative;
  reportMessage: string | null;
  onBack: () => void;
  onStartNew: () => void;
}

const chapters = [
  "家庭基础情况",
  "理财目标",
  "大额支出计划",
  "理财假设",
  "家庭财务报表",
  "家庭财务比率分析",
  "投资规划建议",
  "免责声明",
] as const;

const ratioOrder = [
  "liquidity_reserve_months",
  "debt_to_asset_ratio",
  "savings_ratio",
  "debt_service_burden_ratio",
  "investable_assets_to_net_worth",
  "property_to_assets_ratio",
];

const goalTypeLabels: Record<string, string> = {
  emergency_fund: "应急储备",
  education: "子女教育",
  home: "购房或改善住房",
  retirement: "退休养老",
  medical: "医疗保障",
  travel: "旅行",
  debt_repayment: "提前还债",
  family_support: "家庭支持",
  wealth_transfer: "财富传承",
  other: "其他目标",
};

const statusLabels: Record<string, string> = {
  strong: "较好",
  healthy: "合理",
  attention: "需关注",
  warning: "偏离参考",
  critical: "优先处理",
  review: "结合情况判断",
  not_applicable: "资料不足",
};

const riskPreferenceLabels: Record<KycProfile["risk_preference"], string> = {
  conservative: "稳健为先",
  balanced: "均衡配置",
  growth: "追求长期增长",
};

const experienceLabels: Record<KycProfile["investment_experience"], string> = {
  none: "暂无投资经验",
  basic: "了解常见产品",
  experienced: "有较丰富经验",
};

const lossToleranceLabels: Record<KycProfile["loss_tolerance"], string> = {
  low: "难以接受本金波动",
  medium: "可承受一定波动",
  high: "可承受较大波动",
};

const pensionLabels: Record<KycProfile["personal_pension_status"], string> = {
  opened: "已开立个人养老金账户",
  not_opened: "尚未开立个人养老金账户",
  not_sure: "需要进一步了解个人养老金",
};

function asNumber(value: string | number): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function progressPercent(current: string | number, target: string | number): number {
  const denominator = asNumber(target);
  if (denominator <= 0) return 0;
  return Math.max(0, Math.min(100, (asNumber(current) / denominator) * 100));
}

function ratioText(value: string | null): string {
  return value === null ? "暂不适用" : formatRatio(value);
}

export function PlanBookView({
  analysis,
  explanations,
  goals,
  majorExpenses,
  kyc,
  planning,
  narrative,
  reportMessage,
  onBack,
  onStartNew,
}: PlanBookViewProps) {
  const [activeChapter, setActiveChapter] = useState(1);
  const chapterPaperRef = useRef<HTMLElement>(null);
  const metricMap = useMemo(
    () => new Map(analysis.metrics.map((metric) => [metric.metric_id, metric])),
    [analysis],
  );
  const explanationMap = useMemo(
    () => new Map(explanations.map((item) => [item.metric_id, item])),
    [explanations],
  );
  const keyMetrics = ratioOrder
    .map((id) => metricMap.get(id))
    .filter((metric): metric is MetricResult => Boolean(metric));
  const validGoals = goals.filter((goal) => goal.name.trim() && Number(goal.target_amount) > 0);
  const validExpenses = majorExpenses.filter(
    (expense) => expense.name.trim() && Number(expense.target_amount) > 0,
  );
  const sharedProps = { analysis, kyc, planning, narrative };
  const selectChapter = (chapter: number) => {
    setActiveChapter(Math.max(1, Math.min(8, chapter)));
    window.requestAnimationFrame(() => {
      chapterPaperRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  return (
    <section className="plan-book" aria-labelledby="plan-book-heading">
      <header className="plan-book-hero">
        <div className="plan-book-status"><CheckCircleIcon size={20} weight="fill" aria-hidden="true" /> 规划书已生成</div>
        <div>
          <span>智运财富，普慧金融</span>
          <h1 id="plan-book-heading">{analysis.profile.name}</h1>
          <p>依据家庭资料、财务报表、目标计划和投资适当性信息形成。</p>
        </div>
        <FileTextIcon size={54} weight="duotone" aria-hidden="true" />
      </header>

      <div className="plan-book-toolbar">
        <div>
          <span>规划日期</span><strong>{analysis.meta.analysis_date}</strong>
          <span>金额单位</span><strong>人民币元</strong>
        </div>
        <div className="plan-book-downloads">
          <button className="primary-action" type="button" onClick={() => window.print()}>
            <PrinterIcon size={18} aria-hidden="true" /> 打印或保存 PDF
          </button>
        </div>
      </div>
      {reportMessage ? <p className="plan-book-message" role="status">{reportMessage}</p> : null}

      <div className="plan-book-layout">
        <nav className="chapter-nav" aria-label="规划书目录">
          <strong>目录</strong>
          <ol>
            {chapters.map((title, index) => (
              <li key={title}>
                <button
                  type="button"
                  aria-current={activeChapter === index + 1 ? "page" : undefined}
                  onClick={() => selectChapter(index + 1)}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>{title}
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <article className="chapter-paper" ref={chapterPaperRef}>
          <header>
            <span>第 {activeChapter} 章</span>
            <h2>{chapters[activeChapter - 1]}</h2>
          </header>
          {activeChapter === 1 ? <ChapterOne {...sharedProps} /> : null}
          {activeChapter === 2 ? <ChapterTwo goals={validGoals} narrative={narrative} /> : null}
          {activeChapter === 3 ? <ChapterThree expenses={validExpenses} narrative={narrative} /> : null}
          {activeChapter === 4 ? <ChapterFour {...sharedProps} /> : null}
          {activeChapter === 5 ? <ChapterFive analysis={analysis} narrative={narrative} /> : null}
          {activeChapter === 6 ? <ChapterSix metrics={keyMetrics} explanationMap={explanationMap} narrative={narrative} /> : null}
          {activeChapter === 7 ? <ChapterSeven planning={planning} kyc={kyc} narrative={narrative} householdId={analysis.meta.household_id} showFundAdvisory /> : null}
          {activeChapter === 8 ? <ChapterEight /> : null}
          <footer className="chapter-pagination">
            <button type="button" disabled={activeChapter === 1} onClick={() => selectChapter(activeChapter - 1)}>上一章</button>
            <span>{activeChapter} / 8</span>
            <button type="button" disabled={activeChapter === 8} onClick={() => selectChapter(activeChapter + 1)}>下一章</button>
          </footer>
        </article>
      </div>

      <div className="print-book-all" aria-hidden="true">
        <header className="print-book-cover">
          <span>智运财富，普慧金融</span>
          <h1>{analysis.profile.name}个人／家庭理财规划书</h1>
          <p>规划日期：{analysis.meta.analysis_date}，金额单位：人民币元</p>
        </header>
        <section className="print-book-chapter"><h2>第一章 · 家庭基础情况</h2><ChapterOne {...sharedProps} /></section>
        <section className="print-book-chapter"><h2>第二章 · 理财目标</h2><ChapterTwo goals={validGoals} narrative={narrative} /></section>
        <section className="print-book-chapter"><h2>第三章 · 大额支出计划</h2><ChapterThree expenses={validExpenses} narrative={narrative} /></section>
        <section className="print-book-chapter"><h2>第四章 · 理财假设</h2><ChapterFour {...sharedProps} /></section>
        <section className="print-book-chapter"><h2>第五章 · 家庭财务报表</h2><ChapterFive analysis={analysis} narrative={narrative} /></section>
        <section className="print-book-chapter"><h2>第六章 · 家庭财务比率分析</h2><ChapterSix metrics={keyMetrics} explanationMap={explanationMap} narrative={narrative} /></section>
        <section className="print-book-chapter"><h2>第七章 · 投资规划建议</h2><ChapterSeven planning={planning} kyc={kyc} narrative={narrative} householdId={analysis.meta.household_id} /></section>
        <section className="print-book-chapter"><h2>第八章 · 免责声明</h2><ChapterEight /></section>
      </div>

      <footer className="planning-step-actions plan-book-actions">
        <button className="secondary-action" type="button" onClick={onBack}><ArrowLeftIcon size={18} aria-hidden="true" /> 返回修改目标</button>
        <button className="text-action" type="button" onClick={onStartNew}>新建一份规划</button>
      </footer>
    </section>
  );
}

function ChapterOne({
  analysis,
  kyc,
  narrative,
}: {
  analysis: FinancialAnalysis;
  kyc: KycProfile;
  planning: PlanningResponse;
  narrative: PlanNarrative;
}) {
  return (
    <div className="chapter-content">
      <p className="chapter-lead">{narrative.family_analysis}</p>
      <dl className="chapter-facts">
        <div><dt>家庭名称</dt><dd>{analysis.profile.name}</dd></div>
        <div><dt>常住地区</dt><dd>{analysis.profile.region}</dd></div>
        <div><dt>家庭阶段</dt><dd>{formatDomainLabel(analysis.profile.lifecycle_stage)}</dd></div>
        <div><dt>共同规划人数</dt><dd>{analysis.profile.members.length} 人</dd></div>
      </dl>
      <ReportTable
        title="家庭成员情况"
        columns={["姓名", "关系", "年龄", "职业／身份", "收入稳定性"]}
        rows={analysis.profile.members.map((member) => [
          member.display_name,
          formatDomainLabel(member.relationship),
          `${member.age} 岁`,
          member.occupation || (member.age < 18 ? "学生／学龄前" : "未填写"),
          member.age < 18 ? "不适用" : formatDomainLabel(member.employment_stability),
        ])}
      />
      <section className="kyc-report-card">
        <header><span>投资适当性摘要</span><strong>已按本次填写信息评估</strong></header>
        <dl>
          <div><dt>投资经验</dt><dd>{experienceLabels[kyc.investment_experience]}</dd></div>
          <div><dt>风险取向</dt><dd>{riskPreferenceLabels[kyc.risk_preference]}</dd></div>
          <div><dt>波动承受</dt><dd>{lossToleranceLabels[kyc.loss_tolerance]}</dd></div>
          <div><dt>计划持有期</dt><dd>{kyc.investment_horizon_years} 年</dd></div>
        </dl>
        <p>{pensionLabels[kyc.personal_pension_status]}</p>
      </section>
    </div>
  );
}

function ChapterTwo({ goals, narrative }: { goals: PlanningGoalDraft[]; narrative: PlanNarrative }) {
  return (
    <div className="chapter-content">
      <p className="chapter-lead">{narrative.goal_analysis}</p>
      {goals.length ? (
        <div className="goal-progress-list">
          {goals.map((goal) => {
            const progress = progressPercent(goal.prepared_amount, goal.target_amount);
            return (
              <article key={`${goal.name}-${goal.target_date}`}>
                <header><div><span>{goalTypeLabels[goal.goal_type] ?? "其他目标"}</span><h3>{goal.name}</h3></div><strong>{goal.target_date}</strong></header>
                <div className="goal-progress-track" aria-label={`${goal.name}已准备 ${progress.toFixed(0)}%`}><span style={{ width: `${progress}%` }} /></div>
                <footer><span>已准备 {formatMoney(goal.prepared_amount)}</span><strong>目标 {formatMoney(goal.target_amount)}</strong></footer>
              </article>
            );
          })}
        </div>
      ) : <p className="chapter-empty">本次未登记独立理财目标，建议补充目标金额和日期。</p>}
    </div>
  );
}

function ChapterThree({
  expenses,
  narrative,
}: {
  expenses: MajorExpenseDraft[];
  narrative: PlanNarrative;
}) {
  return (
    <div className="chapter-content">
      <p className="chapter-lead">{narrative.major_expense_analysis}</p>
      {expenses.length ? (
        <ol className="expense-timeline">
          {expenses
            .slice()
            .sort((left, right) => left.target_date.localeCompare(right.target_date))
            .map((expense) => (
              <li key={`${expense.name}-${expense.target_date}`}>
                <time>{expense.target_date}</time>
                <div><h3>{expense.name}</h3><p>{expense.planned_source || "资金来源待确定"}</p></div>
                <strong>{formatMoney(expense.target_amount)}</strong>
                <span>已准备 {formatMoney(expense.prepared_amount)}</span>
              </li>
            ))}
        </ol>
      ) : <p className="chapter-empty">本次未登记大额支出计划。</p>}
    </div>
  );
}

function ChapterFour({
  analysis,
  kyc,
  planning,
}: {
  analysis: FinancialAnalysis;
  kyc: KycProfile;
  planning: PlanningResponse;
  narrative: PlanNarrative;
}) {
  return (
    <div className="chapter-content">
      <p className="chapter-lead">规划结果会随家庭事实、政策环境和市场条件变化，应按实际情况定期更新。</p>
      <ReportTable
        title="本次规划采用的主要假设"
        columns={["项目", "本次口径", "说明"]}
        rows={[
          ["规划时点", analysis.meta.analysis_date, "资产、负债和收支均以本次填写及该时点为准"],
          ["金额口径", "人民币元", "收入和支出采用年度税后、实际发生口径"],
          ["长期资金启动线", formatMoney(kyc.growth_entry_threshold), "按所在地区、工作稳定性和家庭情况选择，可在30万至100万元间调整"],
          ["购买力观察门槛", formatRatio(planning.growth_benchmark.benchmark_rate), "综合消费价格、家庭目标成本和最低工资变化观察；最低工资不等同于 CPI，也不是收益保证"],
          [
            "市场环境口径",
            planning.accounts.find((account) => account.reference_band)?.reference_band?.market_regime_label ?? "待发布",
            "按本次规划日期统一采用。家庭目标、债务、保障和流动性安排优先于市场判断",
          ],
          ["产品收益", "不作保证", "存款以外的银行理财、基金、信托、保险等产品应逐项核对本金风险、期限和流动性"],
          ["配置方法", "按家庭条件动态计算", "结合家庭责任、目标期限、收入稳定性和风险承受情况逐项安排，不采用固定比例"],
        ]}
      />
    </div>
  );
}

function ChapterFive({ analysis, narrative }: { analysis: FinancialAnalysis; narrative: PlanNarrative }) {
  const balance = analysis.statements.balance_sheet;
  const cashflow = analysis.statements.cash_flow;
  const assetMax = Math.max(...balance.assets.map((item) => asNumber(item.market_value)), 1);
  return (
    <div className="chapter-content chapter-statements">
      <p className="chapter-lead">{narrative.statement_analysis}</p>
      <div className="chapter-balance-summary">
        <div><span>总资产</span><strong>{formatMoney(balance.total_assets)}</strong></div>
        <div><span>总负债</span><strong>{formatMoney(balance.total_liabilities)}</strong></div>
        <div><span>净资产</span><strong>{formatMoney(balance.net_worth)}</strong></div>
        <div><span>年度结余</span><strong>{formatMoney(cashflow.annual_surplus)}</strong></div>
      </div>
      <section className="asset-visual-list">
        <h3>资产分布</h3>
        {balance.assets.map((item) => (
          <div key={`${item.name}-${item.asset_group}`}>
            <header><span>{item.name}</span><strong>{formatMoney(item.market_value)}</strong></header>
            <div><span style={{ width: `${Math.max(2, (asNumber(item.market_value) / assetMax) * 100)}%` }} /></div>
            <small>{formatDomainLabel(item.asset_group)}</small>
          </div>
        ))}
      </section>
      <ReportTable title="家庭资产表" columns={["项目", "类别", "金额"]} rows={balance.assets.map((item) => [item.name, formatDomainLabel(item.asset_group), formatMoney(item.market_value)])} />
      <ReportTable title="家庭负债表" columns={["项目", "类别", "余额", "月还款"]} rows={balance.liabilities.map((item) => [item.name, formatDomainLabel(item.category), formatMoney(item.outstanding_balance), formatMoney(item.monthly_payment)])} />
      <div className="chapter-two-tables">
        <ReportTable title="年度收入" columns={["项目", "类别", "金额"]} rows={cashflow.income_lines.map((item) => [item.name, formatDomainLabel(item.category), formatMoney(item.annual_amount)])} />
        <ReportTable title="年度支出" columns={["项目", "类别", "金额"]} rows={cashflow.expense_lines.map((item) => [item.name, formatDomainLabel(item.category), formatMoney(item.annual_amount)])} />
      </div>
    </div>
  );
}

function ChapterSix({
  metrics,
  explanationMap,
  narrative,
}: {
  metrics: MetricResult[];
  explanationMap: Map<string, RatioExplanationItem>;
  narrative: PlanNarrative;
}) {
  return (
    <div className="chapter-content chapter-ratios">
      <p className="chapter-lead">{narrative.ratio_analysis_summary}</p>
      <aside className="chapter-method-note">全部比率均由已填写的财务报表直接计算。常用范围用于辅助判断，不是对所有家庭都适用的硬性标准。</aside>
      {metrics.map((metric) => {
        const explanation = explanationMap.get(metric.metric_id);
        return (
          <section key={metric.metric_id} className="chapter-ratio-item">
            <header><h3>{metric.name}</h3><strong>{formatMetricValue(metric)}</strong><span>{statusLabels[metric.status] ?? "待判断"}</span></header>
            <p><b>计算方式：</b>{metric.formula}</p>
            <p><b>本次代入：</b>{metric.substitution}</p>
            <p><b>常用参考：</b>{metric.reference.reference_range}</p>
            <p>{explanation?.interpretation ?? metric.explanation}</p>
            <p><b>下一步：</b>{explanation?.next_step ?? metric.actions[0]}</p>
          </section>
        );
      })}
    </div>
  );
}

function ChapterSeven({
  planning,
  kyc,
  narrative,
  householdId,
  showFundAdvisory = false,
}: {
  planning: PlanningResponse;
  kyc: KycProfile;
  narrative: PlanNarrative;
  householdId: string;
  showFundAdvisory?: boolean;
}) {
  const netFinancialAssets = asNumber(planning.denominators.net_financial_assets_after_debt);
  const threshold = asNumber(planning.denominators.growth_entry_threshold);
  const thresholdProgress = threshold > 0 ? Math.max(0, Math.min(100, (netFinancialAssets / threshold) * 100)) : 0;
  const capitalReady = netFinancialAssets >= threshold;
  const learning = planning.investment_learning;
  const accountMax = Math.max(...planning.accounts.map((account) => asNumber(account.recommended_amount)), 1);
  const personalPensionNote = kyc.personal_pension_status === "opened"
    ? "已开立个人养老金账户，可结合当年缴费和税收安排纳入保本的钱，具体产品仍需逐项评估。"
    : "可了解个人养老金制度及每年1.2万元税前扣除额度；是否参与应结合纳税情况、期限和产品风险决定。";
  return (
    <div className="chapter-content account-plan-chapter">
      <section className="investor-guidance" aria-label="给投资者的说明">
        <span>给您的投资说明</span>
        <div>
          {narrative.four_account_analysis
            .split(/\n{2,}/)
            .filter(Boolean)
            .map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
        </div>
      </section>

      <section className="growth-entry-card" data-ready={capitalReady ? "true" : "false"}>
        <header>
          <div>
            <span>长期投资准备情况</span>
            <h3>
              {capitalReady
                ? "已达到本次长期配置起点"
                : learning.eligible
                  ? "还未到正式起点，可以先小额学习"
                  : "当前先不新增长期投资"}
            </h3>
          </div>
          <strong>{formatMoney(String(netFinancialAssets))} <small>/ {formatMoney(String(threshold))}</small></strong>
        </header>
        <div className="growth-entry-track"><span style={{ width: `${thresholdProgress}%` }} /></div>
        <p>这里的金融净值由可投资金融资产扣除全部负债得到。信用卡额度不计入资产；长期配置起点由您在30万至100万元之间选择。</p>
      </section>

      {learning.applicable ? (
        <section className="investment-learning-card" data-eligible={learning.eligible ? "true" : "false"}>
          <header>
            <div><span>小额投资学习</span><h3>{learning.eligible ? "从宽基指数基金开始认识市场" : "本次先不安排学习资金"}</h3></div>
            <strong>{formatMoney(learning.recommended_amount)}</strong>
          </header>
          <dl>
            <div><dt>本次比例</dt><dd>{learning.recommended_ratio ? formatRatio(learning.recommended_ratio) : "暂不适用"}</dd></div>
            <div><dt>最高上限</dt><dd>{formatRatio(learning.cap_ratio)}</dd></div>
            <div><dt>多余长期资金</dt><dd>{formatMoney(learning.denominator_value)}</dd></div>
          </dl>
          <p>{learning.explanation}</p>
          <small>这个比例只针对{learning.denominator_name}，不是家庭总资产。10%是上限，不需要用满。</small>
          {!learning.eligible && learning.failed_conditions.length > 0 ? (
            <ul>{learning.failed_conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>
          ) : null}
        </section>
      ) : null}

      <section className="four-account-ledger">
        <header><div><span>资金用途</span><strong>当前金额</strong><strong>本次建议</strong></div></header>
        {planning.accounts.map((account) => (
          <article key={account.bucket} data-account={account.bucket}>
            <div className="account-ledger-title"><span>{String(account.sequence).padStart(2, "0")}</span><div><h3>{account.name}</h3><p>{accountClientSummary(account.bucket)}</p></div></div>
            <strong>{formatMoney(account.current_amount)}</strong>
            <div className="account-recommendation">
              <strong>{formatMoney(account.recommended_amount)}</strong>
              <div><span style={{ width: `${Math.max(2, (asNumber(account.recommended_amount) / accountMax) * 100)}%` }} /></div>
              {account.reference_band ? <small>{account.reference_band.market_regime_label}参考范围 {formatRatio(account.reference_band.minimum_ratio)} 至 {formatRatio(account.reference_band.maximum_ratio)}，中间参考点 {formatRatio(account.reference_band.target_ratio)}</small> : null}
            </div>
            <details className="account-education-disclosure">
              <summary>了解这笔钱的用途和风险</summary>
              <p>{account.rationale}</p>
              <ul>{account.product_education.slice(0, 2).map((item) => <li key={item}>{item}</li>)}</ul>
            </details>
          </article>
        ))}
      </section>

      <div className="account-boundary-grid">
        <section>
          <span>长期资金占比说明</span>
          <h3>{planning.growth_70.eligible ? ratioText(planning.growth_70.actual_ratio) : learning.eligible ? "学习仓不适用" : "当前不适用"}</h3>
          <p>{growthRatioExplanation(planning, learning.eligible)}</p>
          <small>只针对{planning.growth_70.denominator_name}，不是家庭总资产。</small>
        </section>
        <section>
          <span>长期资金需要关注的购买力</span>
          <h3>{formatRatio(planning.growth_benchmark.benchmark_rate)}</h3>
          <p>长期投资需要关注家庭目标成本是否持续上涨，不能只看账户是否盈利。</p>
          <small>最低工资变化只作辅助观察，不等同于居民消费价格指数（CPI），也不构成收益保证。</small>
        </section>
      </div>

      <section className="planning-action-panel">
        <h3>建议按以下顺序处理</h3>
        <ol>
          {planning.actions.map((action) => (
            <li key={`${action.priority}-${action.action_code}`}><span>{String(action.priority).padStart(2, "0")}</span><div><strong>{action.title}</strong><p>{action.detail}</p></div>{asNumber(action.amount) > 0 ? <b>{formatMoney(action.amount)}</b> : null}</li>
          ))}
        </ol>
      </section>

      <aside className="personal-pension-note"><strong>个人养老金</strong><p>{personalPensionNote}</p></aside>
      {showFundAdvisory ? <FundAdvisoryWorkspace householdId={householdId} /> : null}
      <aside className="chapter-note">普通家庭不默认配置个股、杠杆或股指期货，也不默认新增投资性房产。选择具体产品前，还需要核对风险等级、持有期限、费用和赎回条件。</aside>
      <section className="review-trigger-panel"><h3>需要重新评估的情况</h3><ul>{narrative.review_triggers.map((trigger) => <li key={trigger}>{trigger}</li>)}</ul></section>
    </div>
  );
}

function accountClientSummary(bucket: string): string {
  const summaries: Record<string, string> = {
    daily_liquidity: "用于日常支付和短期周转，金额随家庭消费习惯调整。",
    risk_protection: "用于承担必要保费，避免重大风险直接冲击家庭现金流。",
    stable_goals: "用于应急储备、还款缓冲和五年内目标，重点看取用时间与本金风险。",
    long_term_growth: "只使用长期不用的资金，并把波动控制在家庭能够承受的范围内。",
  };
  return summaries[bucket] ?? "根据资金用途、使用日期和家庭承受能力安排。";
}

function growthRatioExplanation(planning: PlanningResponse, learningEligible: boolean): string {
  if (learningEligible) return "本次属于小额学习，不使用70%以上的正式长期配置判断。";
  if (!planning.growth_70.eligible) return "当前条件还不适合采用70%以上的正式长期配置判断，先完成排在前面的家庭安排。";
  return `本次长期增长资金占前置安排后剩余长期资金的${ratioText(planning.growth_70.actual_ratio)}。70%以上只用于这部分长期资金。`;
}

function ChapterEight() {
  return (
    <div className="chapter-content disclaimer-copy">
      <p>本规划书依据客户提供并确认的信息，以及生成当日可用的计算规则形成，仅用于家庭财务规划和沟通参考。</p>
      <p>规划书中的参考范围、分析意见和行动顺序不构成存款、理财、基金、信托、保险、证券或其他金融产品的销售、承诺或保证，也不替代法律、税务、会计和医疗等专业意见。</p>
      <p>金融产品可能存在本金损失、收益波动、流动性受限和费用变化。银行理财、信托、基金和保险不能统一描述为保本产品，具体权利义务以正式合同、产品说明书和风险揭示书为准。</p>
      <p>家庭收入、支出、资产价格、利率、政策和目标变化后，本规划书的结论可能不再适用。建议至少每半年复核一次，并在就业、婚育、购房、退休、重大疾病或大额支出发生后及时更新。</p>
    </div>
  );
}

function ReportTable({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return (
    <section className="report-table-section">
      <h3>{title}</h3>
      <div className="report-table-scroll">
        <table>
          <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody>
            {rows.length ? rows.map((row, rowIndex) => (
              <tr key={`${title}-${rowIndex}`}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}</tr>
            )) : <tr><td colSpan={columns.length}>暂无记录</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
