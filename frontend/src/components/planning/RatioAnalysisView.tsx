import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CalculatorIcon,
  ChartDonutIcon,
  SparkleIcon,
} from "@phosphor-icons/react";
import type { FinancialAnalysis, MetricResult } from "../../api/financial";
import type { RatioExplanationItem } from "../../api/wealthPlanning";
import { BalanceOverviewChart, CashFlowWaterfallChart } from "../charts/FinancialCharts";
import { formatMetricValue, formatMoney } from "../../utils/format";

interface RatioAnalysisViewProps {
  analysis: FinancialAnalysis;
  explanations: RatioExplanationItem[];
  explanationLoading: boolean;
  explanationError: string | null;
  onBack: () => void;
  onContinue: () => void;
}

const ratioOrder = [
  "liquidity_reserve_months",
  "debt_to_asset_ratio",
  "savings_ratio",
  "debt_service_burden_ratio",
  "investable_assets_to_net_worth",
  "property_to_assets_ratio",
];

const metricMeaning: Record<string, string> = {
  liquidity_reserve_months: "可立即动用的金融资产，可以覆盖多少个月的基本生活支出。",
  debt_to_asset_ratio: "家庭总资产中有多少由负债形成，用于观察整体杠杆水平。",
  savings_ratio: "每年收入扣除全部支出后的结余占收入比例，反映持续积累能力。",
  debt_service_burden_ratio: "年度还本付息占税后收入的比例，反映还贷对现金流的占用。",
  investable_assets_to_net_worth: "净资产中可用于储蓄和投资安排的金融资产占比。",
  property_to_assets_ratio: "房产占家庭总资产的比例，用于观察资产集中和流动性。",
};

const referenceOverride: Record<string, string> = {
  investable_assets_to_net_worth: "积累期常见参考为 20%-50%。随年龄、住房、保障和目标期限调整，不设统一强制值。",
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

function statusTone(status: string): string {
  if (status === "strong" || status === "healthy") return "positive";
  if (status === "attention" || status === "review") return "attention";
  if (status === "not_applicable") return "neutral";
  return "warning";
}

export function RatioAnalysisView({
  analysis,
  explanations,
  explanationLoading,
  explanationError,
  onBack,
  onContinue,
}: RatioAnalysisViewProps) {
  const explanationMap = new Map<string, RatioExplanationItem>(
    explanations.map((item) => [item.metric_id, item]),
  );
  const metricMap = new Map(analysis.metrics.map((item) => [item.metric_id, item]));
  const metrics = ratioOrder
    .map((id) => metricMap.get(id))
    .filter((item): item is MetricResult => Boolean(item));
  const balance = analysis.statements.balance_sheet;
  const cashflow = analysis.statements.cash_flow;

  return (
    <section className="planning-step-panel ratio-analysis" aria-labelledby="ratio-step-heading">
      <header className="planning-step-header ratio-step-header">
        <div>
          <span>家庭财务分析</span>
          <h1 id="ratio-step-heading">先看全貌，再看六项关键比率</h1>
          <p>金额、公式、代入和参考区间均根据已填写的财务报表计算。文字解读帮助您理解结果，不会改动数字。</p>
        </div>
        <ChartDonutIcon size={44} weight="duotone" aria-hidden="true" />
      </header>

      <dl className="financial-summary-strip">
        <div><dt>家庭总资产</dt><dd>{formatMoney(balance.total_assets)}</dd></div>
        <div><dt>家庭总负债</dt><dd>{formatMoney(balance.total_liabilities)}</dd></div>
        <div><dt>家庭净资产</dt><dd>{formatMoney(balance.net_worth)}</dd></div>
        <div><dt>年度结余</dt><dd>{formatMoney(cashflow.annual_surplus)}</dd></div>
      </dl>

      <div className="planning-chart-grid">
        <BalanceOverviewChart analysis={analysis} />
        <CashFlowWaterfallChart analysis={analysis} />
      </div>

      <section className="ratio-ledger" aria-labelledby="ratio-ledger-heading">
        <header className="ratio-ledger-header">
          <div>
            <h2 id="ratio-ledger-heading">财务比率逐项分析</h2>
            <p>参考区间是中国家庭理财规划中的常用观察口径，不是监管强制标准。</p>
          </div>
          <CalculatorIcon size={30} weight="duotone" aria-hidden="true" />
        </header>
        <div className="ratio-card-list">
          {metrics.map((metric, index) => (
            <RatioCard
              key={metric.metric_id}
              metric={metric}
              index={index + 1}
              explanation={explanationMap.get(metric.metric_id)}
              loading={explanationLoading}
            />
          ))}
        </div>
        {explanationError ? (
          <p className="ratio-explanation-state" role="status">{explanationError} 当前先显示基础说明，比率结果不受影响。</p>
        ) : null}
      </section>

      <footer className="planning-step-actions">
        <button className="secondary-action" type="button" onClick={onBack}>
          <ArrowLeftIcon size={18} aria-hidden="true" /> 返回修改报表
        </button>
        <button className="primary-action" type="button" onClick={onContinue}>
          填写理财目标 <ArrowRightIcon size={18} aria-hidden="true" />
        </button>
      </footer>
    </section>
  );
}

function RatioCard({
  metric,
  index,
  explanation,
  loading,
}: {
  metric: MetricResult;
  index: number;
  explanation?: RatioExplanationItem;
  loading: boolean;
}) {
  return (
    <article className="ratio-card" data-tone={statusTone(metric.status)}>
      <header>
        <span>{String(index).padStart(2, "0")}</span>
        <div><h3>{metric.name.replace("／应急储备月数", "")}</h3><p>{metricMeaning[metric.metric_id]}</p></div>
        <strong>{formatMetricValue(metric)}</strong>
        <em>{statusLabels[metric.status] ?? "待判断"}</em>
      </header>
      <dl className="ratio-definition-grid">
        <div><dt>计算方式</dt><dd>{metric.formula}</dd></div>
        <div><dt>本次代入</dt><dd>{metric.substitution}</dd></div>
        <div><dt>常用参考</dt><dd>{referenceOverride[metric.metric_id] ?? metric.reference.reference_range}</dd></div>
      </dl>
      <section className="ratio-ai-reading" aria-label={`${metric.name}家庭解读`}>
        <h4><SparkleIcon size={18} weight="fill" aria-hidden="true" /> 结合家庭情况的解读</h4>
        {loading ? (
          <div className="ratio-reading-skeleton" role="status" aria-label="正在准备家庭解读"><span /><span /><span /></div>
        ) : explanation ? (
          <div className="ratio-reading-copy">
            <p>{explanation.interpretation}</p>
            <p><strong>关注点：</strong>{explanation.focus}</p>
            <p><strong>下一步：</strong>{explanation.next_step}</p>
          </div>
        ) : (
          <div className="ratio-reading-copy"><p>{metric.explanation}</p><p><strong>下一步：</strong>{metric.actions[0]}</p></div>
        )}
      </section>
    </article>
  );
}
