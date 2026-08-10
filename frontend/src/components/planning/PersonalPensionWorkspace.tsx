import type { PlanningResponse } from "../../api/planning";
import { formatMoney, formatRatio } from "../../utils/format";

export function PersonalPensionWorkspace({ plan }: { plan: PlanningResponse | null }) {
  if (!plan) {
    return <section className="client-inline-state"><h2>个人养老金规划暂不可用</h2><p>规划事实或政策快照未返回，系统不会补造资格、税惠或产品风险。</p></section>;
  }
  const pension = plan.methodology.personal_pension;
  return (
    <section className="personal-pension-workspace" aria-labelledby="personal-pension-heading">
      <header className="planning-header">
        <div><p className="section-index">制度账户 · Personal Pension Copilot</p><h2 id="personal-pension-heading">个人养老金不是低风险资产类别</h2><p>{pension.explanation}</p></div>
        <span className="methodology-version">{pension.policy.policy_version}</span>
      </header>

      <div className="planning-v4-grid">
        <article className="planning-v4-card"><span>账户余额</span><h3>{formatMoney(pension.account_balance)}</h3><small>锁定资金不计入日常、应急或近期目标流动性</small></article>
        <article className="planning-v4-card"><span>年度缴存进度</span><h3>{formatRatio(pension.contribution_progress_ratio)}</h3><small>{formatMoney(pension.annual_contribution_amount)} / {formatMoney(pension.contribution_limit)}</small></article>
        <article className="planning-v4-card"><span>剩余政策额度</span><h3>{formatMoney(pension.remaining_contribution_capacity)}</h3><small>限额来自版本化政策快照，不是 Python 常量</small></article>
        <article className="planning-v4-card"><span>估算当年税收利益</span><h3>{formatMoney(pension.estimated_current_year_tax_benefit)}</h3><small>按已确认边际税率 {formatRatio(pension.assumed_marginal_tax_rate)} 测算，办理前需复核</small></article>
      </div>

      <article className="planning-panel pension-risk-panel">
        <header><div><p className="section-index">账户内产品风险</p><h3>制度外壳与底层风险分开看</h3></div><span>{pension.eligibility_status === "needs_review" ? "资格待复核" : pension.eligibility_status}</span></header>
        {pension.product_risk_allocation.length ? <div className="pension-risk-list">{pension.product_risk_allocation.map((item) => <div key={item.asset_id}><strong>{item.asset_name}</strong><span>{formatMoney(item.market_value)}</span><small>{item.risk_level.toUpperCase()} · {item.principal_loss_possible ? "本金可能损失" : "按法律属性核对本金保证"} · 流动性 {item.liquidity_days} 天 · {item.lock_up ? "锁定" : "可领取状态待核对"}</small></div>)}</div> : <p>尚无已确认的账户内产品明细；不会将账户余额默认视为存款或低风险产品。</p>}
      </article>

      <aside className="portfolio-block-note"><strong>演示边界</strong><p>当前政策与账户数据是受控快照，不代表已经接入工商银行个人养老金、税务、社保或实时产品系统。</p></aside>
    </section>
  );
}
