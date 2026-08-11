import { ReceiptIcon, ShieldCheckIcon } from "@phosphor-icons/react";
import type { FamilyEnterpriseView } from "../../api/familyEnterprise";
import { formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";

export function EnterpriseObligations({ view }: { view: FamilyEnterpriseView }) {
  const cashflows = view.enterprises.flatMap((enterprise) => enterprise.cashflows.map((cashflow) => ({
    ...cashflow,
    enterpriseName: enterprise.profile.name,
  })));
  const guarantees = view.enterprises.flatMap((enterprise) => enterprise.guarantees.map((guarantee) => ({
    ...guarantee,
    enterpriseName: enterprise.profile.name,
  })));
  return (
    <section className="enterprise-obligations-section" aria-labelledby="enterprise-obligations-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Income + guarantees</p>
          <h2 id="enterprise-obligations-title">收入来源和表外责任，决定家庭能承受多少波动</h2>
        </div>
        <p>收入、股权和担保若来自同一家企业，风险不会因为证券账户持股少而消失。</p>
      </header>
      <div className="enterprise-obligations-grid">
        <article>
          <header><ReceiptIcon size={22} weight="duotone" aria-hidden="true" /><div><span>收入依赖</span><strong>{formatRatio(view.income.dependency_ratio)}</strong></div></header>
          <p>企业年收入 {formatMoney(view.income.enterprise_annual_income)} / 家庭年收入 {formatMoney(view.income.household_annual_income)}</p>
          <ul>
            {cashflows.map((cashflow) => (
              <li key={cashflow.id}><span>{cashflow.enterpriseName} · {formatDomainLabel(cashflow.cashflow_type)}</span><strong>{formatMoney(cashflow.amount)} / {formatDomainLabel(cashflow.frequency)}</strong><small>{formatDomainLabel(cashflow.stability)}稳定性</small></li>
            ))}
          </ul>
        </article>
        <article>
          <header><ShieldCheckIcon size={22} weight="duotone" aria-hidden="true" /><div><span>担保暴露</span><strong>{formatMoney(view.guarantees.outstanding_exposure)}</strong></div></header>
          <p>{view.guarantees.active_count} 项有效责任 · 担保额度 {formatMoney(view.guarantees.guaranteed_amount)}</p>
          <ul>
            {guarantees.map((guarantee) => (
              <li key={guarantee.id}><span>{guarantee.enterpriseName} · {formatDomainLabel(guarantee.guarantee_type)}</span><strong>{formatMoney(guarantee.outstanding_exposure)}</strong><small>{guarantee.expiry_date ? `至 ${guarantee.expiry_date}` : "未设到期日"}</small></li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}
