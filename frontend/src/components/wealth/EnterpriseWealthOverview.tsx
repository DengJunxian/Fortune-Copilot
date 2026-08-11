import { BriefcaseIcon, HouseLineIcon, WalletIcon } from "@phosphor-icons/react";
import type { FamilyEnterpriseView } from "../../api/familyEnterprise";
import { formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";

export function EnterpriseWealthOverview({ view }: { view: FamilyEnterpriseView }) {
  return (
    <section className="enterprise-wealth-section" aria-labelledby="enterprise-wealth-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Household + enterprise wealth</p>
          <h2 id="enterprise-wealth-title">家庭资产与企业资产，合在一张底稿里看</h2>
        </div>
        <p>企业股权计入经济财富，但不会被误当作随时可卖出的金融资产。</p>
      </header>
      <div className="enterprise-wealth-ledger">
        <article className="enterprise-wealth-total">
          <span><WalletIcon size={18} weight="duotone" aria-hidden="true" /> 家庭经济财富</span>
          <strong>{formatMoney(view.wealth.economic_household_wealth)}</strong>
          <small>家庭账面资产与关联企业权益合并口径</small>
        </article>
        <article>
          <span><HouseLineIcon size={18} weight="duotone" aria-hidden="true" /> 家庭财富</span>
          <strong>{formatMoney(view.wealth.household_wealth)}</strong>
          <small>金融资产 {formatMoney(view.wealth.financial_assets)} · 房产 {formatMoney(view.wealth.property_assets)}</small>
        </article>
        <article className="enterprise-wealth-emphasis">
          <span><BriefcaseIcon size={18} weight="duotone" aria-hidden="true" /> 企业财富</span>
          <strong>{formatMoney(view.wealth.enterprise_wealth)}</strong>
          <small>占经济财富 {formatRatio(view.wealth.enterprise_wealth_ratio)}</small>
        </article>
      </div>
      <div className="enterprise-entity-ledger" aria-label="关联企业明细">
        {view.enterprises.map((enterprise) => (
          <article key={enterprise.profile.id}>
            <div>
              <span>{formatDomainLabel(enterprise.profile.listed_status)} · {formatDomainLabel(enterprise.profile.stage)}</span>
              <h3>{enterprise.profile.name}</h3>
              <p>{enterprise.profile.industry} · {enterprise.profile.jurisdiction}</p>
            </div>
            <dl>
              <div><dt>家庭持有价值</dt><dd>{formatMoney(enterprise.household_owned_value)}</dd></div>
              <div><dt>最新企业估值</dt><dd>{enterprise.latest_valuation ? formatMoney(enterprise.latest_valuation.equity_value) : "待补录"}</dd></div>
              <div><dt>所有权记录</dt><dd>{enterprise.ownerships.length} 项</dd></div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
