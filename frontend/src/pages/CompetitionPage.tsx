import {
  ArrowRightIcon,
  BankIcon,
  ChartLineUpIcon,
  CheckCircleIcon,
  CirclesFourIcon,
  ClockCountdownIcon,
  FingerprintIcon,
  HandshakeIcon,
  ShieldCheckIcon,
  TargetIcon,
  UserFocusIcon,
  WarningDiamondIcon,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";
import { fetchCompetitionDemo, type CompetitionDemoResponse } from "../api/competition";
import { usePortalContext } from "../contexts/PortalContext";
import { formatMoney } from "../utils/format";
import "./CompetitionPage.css";

const journey = [
  "家庭建档",
  "CHFH 安全诊断",
  "目标与责任",
  "资金分层",
  "ELTC",
  "GRB 风险预算",
  "资产配置",
  "产品候选",
  "持续监控",
  "顾问与合规",
];

const methodLabels: Record<string, string> = {
  mean_variance: "Mean–Variance",
  risk_parity: "Risk Parity",
  cvar: "CVaR",
  black_litterman: "Black–Litterman",
};

const biasLabels: Record<string, string> = {
  loss_aversion: "损失厌恶",
  disposition_effect: "处置效应",
  herding: "羊群效应",
  overconfidence: "过度自信",
  recency_bias: "近因偏差",
  performance_chasing: "追逐业绩",
};

function percent(value: string, digits = 1): string {
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function CompetitionPage() {
  const { actor } = usePortalContext();
  const [data, setData] = useState<CompetitionDemoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchCompetitionDemo(actor, controller.signal)
      .then((payload) => {
        setData(payload);
        setError(false);
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") return;
        setError(true);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [actor]);

  if (loading) return <CompetitionLoading />;
  if (error || !data) return <CompetitionError />;
  return <CompetitionStory data={data} />;
}

function CompetitionStory({ data }: { data: CompetitionDemoResponse }) {
  const selectedQuant = data.quant.methods.find((item) => item.method === data.quant.selected_method);
  const eligibleLongTermCapital = data.wealth_accounts.find((item) => item.code === "growth")?.target_amount ?? "0";
  const annualIncome = Number(data.cash_flow.annual_income);
  const assetShare = (Number(data.balance_sheet.total_assets) / Math.max(annualIncome, 1)).toFixed(1);
  const goalResourceUse = useMemo(
    () => data.goals.reduce((sum, item) => sum + Number(item.allocated_monthly_saving), 0),
    [data.goals],
  );

  return (
    <main className="competition-page" id="main-content">
      <section className="competition-hero" aria-labelledby="competition-title">
        <div className="competition-hero-copy">
          <p className="competition-eyebrow">Fortune Copilot · 工行杯财富管理服务方向</p>
          <h1 id="competition-title">每个家庭，都有自己的财富答案。</h1>
          <p>先判断家庭是否安全、哪些钱真正可以长期投资，再结合目标、风险与真实行为决定怎么配置，并在家庭变化后持续重算。</p>
          <div className="competition-boundaries" aria-label="演示边界">
            <span><FingerprintIcon size={17} aria-hidden="true" /> 合成 Demo</span>
            <span><ShieldCheckIcon size={17} aria-hidden="true" /> 确定性算法可回放</span>
            <span><BankIcon size={17} aria-hidden="true" /> 未连接工行生产系统</span>
          </div>
        </div>
        <aside className="competition-case-file" aria-label="比赛演示家庭">
          <div><span>比赛主案例</span><strong>上海 · 38 岁</strong></div>
          <p>{data.client.personal_profile.occupation}，已婚，一个孩子；家庭年收入约 65 万元，金融资产 180 万元，存在房贷。</p>
          <dl>
            <div><dt>家庭成员</dt><dd>{data.client.family_profile.members.length} 人</dd></div>
            <div><dt>房贷余额</dt><dd>{formatMoney(data.balance_sheet.total_liabilities, true)}</dd></div>
            <div><dt>数据状态</dt><dd>合成 · 可复现</dd></div>
          </dl>
        </aside>
      </section>

      <ol className="competition-journey" aria-label="全生命周期财富管理闭环">
        {journey.map((item, index) => <li key={item}><span>{String(index + 1).padStart(2, "0")}</span>{item}</li>)}
      </ol>

      <section className="competition-ledger" aria-label="家庭财富核心数字">
        <article><span>净资产</span><strong>{formatMoney(data.balance_sheet.net_worth, true)}</strong><small>{data.balance_sheet.accounting_identity}</small></article>
        <article><span>长期可投资资本 ELTC</span><strong>{formatMoney(eligibleLongTermCapital, true)}</strong><small>金融资产 {formatMoney(data.balance_sheet.financial_assets, true)} 不等于全部可投资</small></article>
        <article><span>月度净现金流</span><strong>{formatMoney(data.balance_sheet.monthly_cash_flow, true)}</strong><small>目标月投入协调后使用 {formatMoney(String(goalResourceUse), true)} · 总资产/收入 {assetShare} 倍</small></article>
        <article><span>有效风险预算</span><strong>R{data.risk_budget.risk_level} · {percent(data.risk_budget.effective_risk_budget)}</strong><small>{data.risk_budget.binding_dimension === "tolerance" ? "风险意愿为约束项" : "风险能力为约束项"}</small></article>
      </section>

      <section className="competition-section competition-balance" aria-labelledby="balance-heading">
        <header><p>01 · Family balance sheet</p><h2 id="balance-heading">先看家庭是否稳，再谈怎么投。</h2></header>
        <div className="competition-balance-grid">
          <div className="balance-visual">
            <div className="balance-assets"><span>总资产</span><strong>{formatMoney(data.balance_sheet.total_assets, true)}</strong></div>
            <div className="balance-minus" aria-hidden="true">−</div>
            <div className="balance-liabilities"><span>总负债</span><strong>{formatMoney(data.balance_sheet.total_liabilities, true)}</strong></div>
            <div className="balance-equals" aria-hidden="true">=</div>
            <div className="balance-net"><span>家庭净资产</span><strong>{formatMoney(data.balance_sheet.net_worth, true)}</strong></div>
          </div>
          <div className="health-ratio-list">
            <div data-alert={Number(data.balance_sheet.emergency_fund_months) < 6}><span>紧急备用金</span><strong>{Number(data.balance_sheet.emergency_fund_months).toFixed(1)} 个月</strong><small>动态目标高于当前 4 个月</small></div>
            <div><span>债务收入比</span><strong>{percent(data.balance_sheet.debt_to_income_ratio)}</strong><small>按月度偿债 / 月收入</small></div>
            <div data-alert={Number(data.balance_sheet.asset_concentration) > 0.6}><span>资产集中度</span><strong>{percent(data.balance_sheet.asset_concentration)}</strong><small>自住房占比较高</small></div>
            <div data-alert><span>保障缺口</span><strong>{formatMoney(data.balance_sheet.insurance_protection_gap, true)}</strong><small>需由持牌人员复核口径</small></div>
          </div>
        </div>
      </section>

      <section className="competition-section" aria-labelledby="accounts-heading">
        <header><p>02 · Capital eligibility</p><h2 id="accounts-heading">先分清每笔钱的责任，再得到长期可投资资本 ELTC。</h2></header>
        <div className="wealth-account-stack">
          {data.wealth_accounts.map((account, index) => (
            <article key={account.code} style={{ "--account-share": `${Math.max(8, Number(account.share_of_financial_assets) * 100)}%` } as React.CSSProperties}>
              <div><span>0{index + 1}</span><h3>{account.chinese_name}</h3><strong>{formatMoney(account.target_amount, true)}</strong></div>
              <div className="account-bar" role="img" aria-label={`${account.chinese_name}占金融资产${percent(account.share_of_financial_assets)}`}><i /></div>
              <p>{account.explanation}</p>
              <ul>{account.drivers.map((driver) => <li key={driver}>{driver}</li>)}</ul>
            </article>
          ))}
        </div>
      </section>

      <section className="competition-section" aria-labelledby="goals-heading">
        <header><p>03 · Goal-based planning</p><h2 id="goals-heading">同一份月结余，先按优先级协调，再计算每个目标概率。</h2></header>
        <div className="goal-table-wrap">
          <table className="competition-table goal-table">
            <thead><tr><th>目标</th><th>未来所需</th><th>每月应投</th><th>本次分配</th><th>成功概率</th><th>资源状态</th></tr></thead>
            <tbody>{data.goals.map((goal) => (
              <tr key={goal.goal_id}>
                <th scope="row">{goal.name}</th>
                <td>{formatMoney(goal.future_value, true)}</td>
                <td>{formatMoney(goal.required_monthly_saving, true)}</td>
                <td>{formatMoney(goal.allocated_monthly_saving, true)}</td>
                <td><span className="goal-probability"><i style={{ width: percent(goal.success_probability) }} />{percent(goal.success_probability, 0)}</span></td>
                <td><span className={`competition-status ${goal.coordination_status}`}>{goal.coordination_status === "resource_constrained" ? "资金受限" : goal.coordination_status === "on_track" ? "在轨" : "已覆盖"}</span></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>

      <section className="competition-section risk-quant-section" aria-labelledby="quant-heading">
        <header><p>04 · Goal + Risk + Behavior</p><h2 id="quant-heading">先确认 ELTC、家庭目标与风险预算，再比较资产方向。</h2></header>
        <div className="risk-budget-strip">
          <div><span>Risk Capacity</span><strong>{percent(data.risk_budget.risk_capacity)}</strong></div>
          <div><span>Risk Tolerance</span><strong>{percent(data.risk_budget.risk_tolerance)}</strong></div>
          <div><span>Risk Requirement</span><strong>{percent(data.risk_budget.risk_requirement)}</strong></div>
          <p><ShieldCheckIcon size={20} aria-hidden="true" /> 有效预算取 Capacity 与 Tolerance 的审慎较低值；Requirement 只揭示目标冲突，不能抬高上限。</p>
        </div>
        <div className="quant-comparison">
          <table className="competition-table">
            <thead><tr><th>方法</th><th>预期收益</th><th>波动率</th><th>Sharpe</th><th>CVaR</th><th>最大回撤</th><th>状态</th></tr></thead>
            <tbody>{data.quant.methods.map((method) => (
              <tr key={method.method} data-selected={method.method === data.quant.selected_method}>
                <th scope="row">{methodLabels[method.method]}{method.method === data.quant.selected_method ? <span>已选</span> : null}</th>
                <td>{percent(method.metrics.expected_return)}</td><td>{percent(method.metrics.volatility)}</td><td>{Number(method.metrics.sharpe_ratio).toFixed(2)}</td><td>{percent(method.metrics.cvar_loss)}</td><td>{percent(method.metrics.max_drawdown)}</td><td>{method.evaluated_candidates} 个可行解</td>
              </tr>
            ))}</tbody>
          </table>
          {selectedQuant ? <div className="selected-allocation"><header><ChartLineUpIcon size={22} aria-hidden="true" /><div><span>本次选择 · {methodLabels[selectedQuant.method]}</span><p>{data.quant.selection_reason}</p></div></header><div>{Object.entries(selectedQuant.weights).map(([name, weight]) => <span key={name}><i style={{ width: percent(weight) }} />{name}<strong>{percent(weight, 0)}</strong></span>)}</div></div> : null}
        </div>
      </section>

      <section className="competition-section" aria-labelledby="products-heading">
        <header><p>05 · Explainable product candidates</p><h2 id="products-heading">展示当前家庭约束下的候选，也说明为什么排除其他产品。</h2></header>
        <div className="pipeline-rail" aria-label="产品方案流程">{data.product_pipeline.stages.map((stage, index) => <span key={stage}>{stage}{index < data.product_pipeline.stages.length - 1 ? <ArrowRightIcon size={14} aria-hidden="true" /> : null}</span>)}</div>
        <div className="product-ledger">
          <div className="approved-products">
            <header><CheckCircleIcon size={21} weight="fill" aria-hidden="true" /><h3>通过合规终检</h3><strong>违规率 {percent(data.product_pipeline.suitability_violation_rate)}</strong></header>
            {data.product_pipeline.recommendations.map((item) => <article key={item.product.product_id}><div><span>Demo · {item.product.asset_class}</span><h4>{item.product.product_name}</h4></div><strong>{formatMoney(item.target_amount, true)} · {percent(item.target_weight, 0)}</strong><small>R{item.product.risk_level} · 费用 {percent(item.product.fees)} · 7 类规则已检查</small></article>)}
          </div>
          <aside className="rejected-products"><header><WarningDiamondIcon size={21} aria-hidden="true" /><h3>被拒绝候选</h3></header>{data.product_pipeline.rejected_products.map((item) => <div key={`${item.product_id}-${item.violations.join("-")}`}><strong>{item.product_id}</strong><span>{item.violations.join(" · ")}</span></div>)}<p>拒绝记录同样进入审计链，不用“无结果”掩盖冲突。</p></aside>
        </div>
      </section>

      <section className="competition-section" aria-labelledby="behavior-heading">
        <header><p>06 · Behavioral evidence</p><h2 id="behavior-heading">真实行为提供约束证据，只能维持或下调风险预算。</h2></header>
        <div className="behavior-grid">{data.behavior_findings.map((finding, index) => <article key={finding.bias}><span>0{index + 1}</span><h3>{biasLabels[finding.bias] ?? finding.bias}</h3><blockquote>{finding.evidence[0]}</blockquote><p>{finding.risk}</p><strong>{finding.intervention}</strong></article>)}</div>
      </section>

      <section className="competition-section advisor-rm-grid" aria-labelledby="advisor-heading">
        <article className="advisor-brief"><header><CirclesFourIcon size={24} aria-hidden="true" /><div><p>Advisor Why Now</p><h2 id="advisor-heading">今天为什么需要联系这个家庭？</h2></div></header><ol>{data.advisor_summary.map((item) => <li key={item}>{item}</li>)}</ol><div className="citation-strip">{data.citations.map((citation) => <a key={citation.citation_id} href={citation.source_uri.startsWith("http") ? citation.source_uri : undefined} title={citation.excerpt}><span>[{citation.citation_id}]</span>{citation.title}</a>)}</div></article>
        <article className="rm-brief"><header><UserFocusIcon size={24} aria-hidden="true" /><div><p>RM Copilot · Human escalation</p><h2>复杂事项交给客户经理。</h2></div></header><div className="rm-next-action"><ClockCountdownIcon size={24} aria-hidden="true" /><div><span>Next Best Action</span><strong>{data.rm_copilot.next_best_action}</strong></div></div><ul>{data.rm_copilot.human_review_items.map((item) => <li key={item}>{item}</li>)}</ul><div className="rm-opportunities">{data.rm_copilot.service_opportunities.map((item) => <span key={item}>{item}</span>)}</div></article>
      </section>

      <section className="competition-section three-portals" aria-labelledby="portals-heading">
        <header><p>07 · ICBC-ready target architecture</p><h2 id="portals-heading">三端共享一条决策证据链。</h2></header>
        <div><article><TargetIcon size={25} aria-hidden="true" /><span>客户端</span><h3>可嵌入手机银行</h3><p>财富总览、目标、CFS方案、行为教育与待确认行动。</p></article><article><HandshakeIcon size={25} aria-hidden="true" /><span>客户经理端</span><h3>AI Wealth Copilot</h3><p>客户360、服务机会、沟通建议与人工介入事项。</p></article><article><ShieldCheckIcon size={25} aria-hidden="true" /><span>管理端</span><h3>运营与合规驾驶舱</h3><p>适当性、模型版本、Citation、再平衡与审计回放。</p></article></div>
        <footer><BankIcon size={20} aria-hidden="true" /><p><strong>部署边界：</strong>当前仅为竞赛原型与模拟数据。IAM、客户数据、产品、交易、CRM、投研与审计系统均只设计 Port/Adapter，不声称已与中国工商银行真实系统连接。</p><code>{data.audit.engine_version} · {data.audit.output_hash.slice(0, 12)}</code></footer>
      </section>
    </main>
  );
}

function CompetitionLoading() {
  return <main className="competition-page" id="main-content"><div className="competition-loading" role="status"><i /><div><p>正在重放合成家庭决策链</p><h1>确定性引擎正在计算资产负债、目标、风险预算与量化对比。</h1></div></div></main>;
}

function CompetitionError() {
  return <main className="competition-page" id="main-content"><div className="competition-error" role="alert"><WarningDiamondIcon size={30} aria-hidden="true" /><div><h1>比赛主案例暂时无法读取</h1><p>页面不会用静态数字冒充实时计算。请启动后端后刷新。</p></div></div></main>;
}
