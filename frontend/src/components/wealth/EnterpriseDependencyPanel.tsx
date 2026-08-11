import { ChartDonutIcon, WarningCircleIcon } from "@phosphor-icons/react";
import type { FamilyEnterpriseView } from "../../api/familyEnterprise";
import { formatMoney, formatRatio } from "../../utils/format";

export function EnterpriseDependencyPanel({ view }: { view: FamilyEnterpriseView }) {
  const capital = view.economic_capital;
  return (
    <section className="enterprise-dependency-section" aria-labelledby="enterprise-dependency-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Dependency + economic capital</p>
          <h2 id="enterprise-dependency-title">企业依赖不是标签，而是五项可核对的暴露</h2>
        </div>
        <p>评分只用于财富规划和风险预算，不替代授信、适当性或任何监管评级。</p>
      </header>
      <div className="enterprise-dependency-layout">
        <article className="enterprise-score-card" data-level={view.dependency.level}>
          <span><ChartDonutIcon size={20} weight="duotone" aria-hidden="true" /> Enterprise–Household Dependency</span>
          <strong>{view.dependency.label}</strong>
          <b>{formatRatio(view.dependency.score)}</b>
          <p>{view.dependency.disclaimer}</p>
        </article>
        <div className="enterprise-dependency-bars">
          {view.dependency.components.map((component) => (
            <article key={component.code}>
              <div><strong>{component.label}</strong><span>{formatRatio(component.ratio)}</span></div>
              <progress max={1} value={Number(component.ratio)} aria-label={`${component.label} ${formatRatio(component.ratio)}`} />
              <p>{component.explanation}</p>
            </article>
          ))}
        </div>
      </div>
      <div className="economic-capital-ledger">
        <article className="economic-capital-decision" data-allowed={String(capital.additional_equity_risk_allowed)}>
          <span>经济权益风险预算</span>
          <strong>{capital.additional_equity_risk_allowed ? "仍可评估新增权益风险" : "不建议新增权益风险"}</strong>
          <p>{capital.explanation}</p>
          {!capital.additional_equity_risk_allowed ? <WarningCircleIcon size={25} weight="duotone" aria-hidden="true" /> : null}
        </article>
        <dl>
          <div><dt>未上市企业股权</dt><dd>{formatMoney(capital.unlisted_company_equity)}</dd></div>
          <div><dt>上市雇主股票</dt><dd>{formatMoney(capital.listed_employer_stock)}</dd></div>
          <div><dt>股权激励</dt><dd>{formatMoney(capital.equity_incentives)}</dd></div>
          <div><dt>普通证券权益</dt><dd>{formatMoney(capital.liquid_securities_equity)}</dd></div>
          <div><dt>总经济权益暴露</dt><dd>{formatMoney(capital.total_economic_equity_exposure)}</dd></div>
          <div><dt>剩余新增容量</dt><dd>{formatMoney(capital.remaining_incremental_equity_capacity)}</dd></div>
        </dl>
      </div>
    </section>
  );
}
