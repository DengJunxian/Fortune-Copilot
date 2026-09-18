import { PiggyBankIcon, ShieldCheckIcon } from "@phosphor-icons/react";
import { fetchRetirementPlan } from "../api/specializedCfs";
import {
  ProfessionalRoutePanel,
  SpecializedBoundary,
  SpecializedError,
  SpecializedHero,
  SpecializedLoading,
} from "../components/wealth/SpecializedCFSFrame";
import { useSpecializedHouseholdView } from "../components/wealth/useSpecializedHouseholdView";
import { formatDate, formatDomainLabel, formatMoneyInWan } from "../utils/format";

export function RetirementPlanPage() {
  const state = useSpecializedHouseholdView(fetchRetirementPlan, "DEMO_C");
  const retry = () => state.householdId
    ? void state.loadView(state.householdId)
    : void state.loadHouseholds();

  return (
    <main className="page-shell specialized-page retirement-page" id="main-content">
      <SpecializedHero
        kicker="Specialized CFS · Retirement floor"
        title="养老不是一个目标金额，而是一条持续到晚年的收入底线。"
        description="把必要生活、医疗、长期照护与制度权益放在同一时间轴上，先看保障收入，再看缺口。"
        selectId="retirement-household-select"
        households={state.households}
        householdId={state.householdId}
        disabled={state.refreshing}
        onHouseholdChange={state.setHouseholdId}
        onRefresh={() => void state.loadView(state.householdId, { force: true })}
      />

      {state.loading ? <SpecializedLoading label="退休责任与制度权益" /> : null}
      {!state.loading && state.error ? (
        <SpecializedError message={state.error} onRetry={retry} />
      ) : null}
      {!state.loading && state.view ? (
        <>
          <section className="specialized-meta" aria-label="退休方案元数据">
            <div><span>家庭</span><strong>{state.selectedHousehold?.name ?? "当前家庭"}</strong></div>
            <div><span>分析日</span><strong>{formatDate(state.view.meta.analysis_date)}</strong></div>
            <div><span>规则版本</span><strong>{state.view.meta.rule_version}</strong></div>
            <div><span>输入校验</span><strong>{state.view.meta.input_hash.slice(0, 10)}</strong></div>
          </section>

          <section className="retirement-output" aria-labelledby="retirement-output-title">
            <article className="retirement-floor">
              <span>年度退休收入底线</span>
              <strong>{formatMoneyInWan(state.view.output.retirement_floor)}</strong>
              <p>按已确认的必要支出、医疗和长期照护责任计算。</p>
            </article>
            <div className="retirement-gap-ledger">
              <h2 id="retirement-output-title">收入与长寿缺口</h2>
              <dl>
                <div><dt>保障性年收入</dt><dd>{formatMoneyInWan(state.view.output.guaranteed_income)}</dd></div>
                <div><dt>年度收入缺口</dt><dd>{formatMoneyInWan(state.view.output.income_gap)}</dd></div>
                <div><dt>长寿资金缺口</dt><dd>{formatMoneyInWan(state.view.output.longevity_gap)}</dd></div>
                <div><dt>退休前流动性缺口</dt><dd>{formatMoneyInWan(state.view.output.liquidity_gap)}</dd></div>
              </dl>
            </div>
          </section>

          <section className="specialized-section retirement-liabilities">
            <header>
              <span>Liability decomposition</span>
              <h2>退休责任拆分</h2>
              <p>目标日期为{state.view.liabilities.retirement_start_date
                ? formatDate(state.view.liabilities.retirement_start_date)
                : "尚待确认"}，测算覆盖 {state.view.liabilities.retirement_years} 年。</p>
            </header>
            <dl className="liability-ledger">
              <div><dt>基本生活责任</dt><dd>{formatMoneyInWan(state.view.liabilities.basic_retirement_liability)}</dd></div>
              <div><dt>医疗责任</dt><dd>{formatMoneyInWan(state.view.liabilities.medical_liability)}</dd></div>
              <div><dt>长期照护责任</dt><dd>{formatMoneyInWan(state.view.liabilities.long_term_care_liability)}</dd></div>
              <div><dt>改进后养老目标</dt><dd>{formatMoneyInWan(state.view.liabilities.improved_retirement_goal)}</dd></div>
            </dl>
          </section>

          <section className="specialized-section">
            <header>
              <span>Institutional entitlements</span>
              <h2>制度权益与持续收入</h2>
              <p>社保、年金、养老金账户、租金与可提取金融资产分开记录，不混同保障程度。</p>
            </header>
            {state.view.entitlements.length === 0 ? (
              <div className="specialized-empty"><PiggyBankIcon size={28} weight="duotone" aria-hidden="true" /><div><h3>尚无制度权益记录</h3><p>需要补充社保、养老金、年金或退休收入资料。</p></div></div>
            ) : (
              <div className="specialized-table-wrap">
                <table className="specialized-table">
                  <thead><tr><th>权益类型</th><th>当前余额</th><th>预计年收入</th><th>开始</th><th>属性</th></tr></thead>
                  <tbody>
                    {state.view.entitlements.map((item) => (
                      <tr key={item.id}>
                        <td>{formatDomainLabel(item.entitlement_type)}</td>
                        <td>{formatMoneyInWan(item.balance)}</td>
                        <td>{formatMoneyInWan(item.expected_income)}</td>
                        <td>{item.start_age !== null ? `${item.start_age} 岁` : item.start_date ? formatDate(item.start_date) : "待确认"}</td>
                        <td>{item.guaranteed ? "保障性" : item.lock_up ? "锁定期" : "非保障性"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="specialized-assumptions">
            <ShieldCheckIcon size={25} weight="duotone" aria-hidden="true" />
            <div><h2>测算假设</h2><ul>{state.view.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </section>
          <ProfessionalRoutePanel route={state.view.route} />
          <SpecializedBoundary>{state.view.boundary}</SpecializedBoundary>
        </>
      ) : null}
    </main>
  );
}
