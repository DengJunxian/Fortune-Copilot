import { GlobeHemisphereWestIcon } from "@phosphor-icons/react";
import { fetchCurrencyExposures } from "../api/specializedCfs";
import {
  ProfessionalRoutePanel,
  SpecializedBoundary,
  SpecializedError,
  SpecializedHero,
  SpecializedLoading,
} from "../components/wealth/SpecializedCFSFrame";
import { useSpecializedHouseholdView } from "../components/wealth/useSpecializedHouseholdView";
import { formatDomainLabel, formatMoneyInWanByCurrency } from "../utils/format";

export function GlobalExposurePage() {
  const state = useSpecializedHouseholdView(fetchCurrencyExposures, "DEMO_B");
  const retry = () => state.householdId
    ? void state.loadView(state.householdId)
    : void state.loadHouseholds();

  return (
    <main className="page-shell specialized-page global-page" id="main-content">
      <SpecializedHero
        kicker="Specialized CFS · Currency exposure"
        title="先看收入、资产与未来责任是否使用同一种货币。"
        description="本页识别币种暴露和责任错配，不做汇率预测，也不提供跨境法律、税务或交易建议。"
        selectId="global-household-select"
        households={state.households}
        householdId={state.householdId}
        disabled={state.refreshing}
        onHouseholdChange={state.setHouseholdId}
        onRefresh={() => void state.loadView(state.householdId, { force: true })}
      />

      {state.loading ? <SpecializedLoading label="币种敞口与未来责任" /> : null}
      {!state.loading && state.error ? <SpecializedError message={state.error} onRetry={retry} /> : null}
      {!state.loading && state.view ? (
        <>
          <section className="global-status" data-material={state.view.material_exposure_detected}>
            <GlobeHemisphereWestIcon size={34} weight="duotone" aria-hidden="true" />
            <div>
              <span>基准货币 · {state.view.base_currency}</span>
              <h2>{state.view.material_exposure_detected ? "识别到需要复核的币种暴露" : "暂未识别到重大外币暴露"}</h2>
              <p>{state.view.exposures.length > 0
                ? `共追溯 ${state.view.exposures.length} 条来源记录，按流入、流出和责任期限分开呈现。`
                : "当前已确认资料均使用家庭基准货币；后续如有海外教育、收入或负债，可再补充。"}</p>
            </div>
            <strong>{state.view.summaries.length} 种外币</strong>
          </section>

          {state.view.summaries.length > 0 ? (
            <section className="specialized-section">
              <header><span>Currency ledger</span><h2>按币种汇总</h2><p>金额保持原币种，不做隐含换汇或跨币种加总。</p></header>
              <div className="currency-summary-ledger">
                {state.view.summaries.map((item) => (
                  <article key={item.currency}>
                    <header><span>{item.currency}</span><small>{item.source_count} 条来源</small></header>
                    <dl>
                      <div><dt>流入</dt><dd>{formatMoneyInWanByCurrency(item.inflow, item.currency)}</dd></div>
                      <div><dt>流出／责任</dt><dd>{formatMoneyInWanByCurrency(item.outflow, item.currency)}</dd></div>
                      <div><dt>净暴露</dt><dd>{formatMoneyInWanByCurrency(item.net_exposure, item.currency)}</dd></div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {state.view.exposures.length > 0 ? (
            <section className="specialized-section">
              <header><span>Source trace</span><h2>暴露来源</h2><p>每条记录保留来源 ID，便于顾问回到原始家庭或企业事实核对。</p></header>
              <div className="specialized-table-wrap">
                <table className="specialized-table">
                  <thead><tr><th>来源类型</th><th>币种</th><th>方向</th><th>金额</th><th>期限</th><th>溯源</th></tr></thead>
                  <tbody>
                    {state.view.exposures.map((item) => (
                      <tr key={item.id}>
                        <td>{formatDomainLabel(item.exposure_type)}</td>
                        <td>{item.currency}</td>
                        <td>{formatDomainLabel(item.direction)}</td>
                        <td>{formatMoneyInWanByCurrency(item.amount, item.currency)}</td>
                        <td>{formatDomainLabel(item.horizon)}</td>
                        <td>{item.source_record_ids.length} 条</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          <ProfessionalRoutePanel route={state.view.route} />
          <SpecializedBoundary>{state.view.boundary}</SpecializedBoundary>
        </>
      ) : null}
    </main>
  );
}
