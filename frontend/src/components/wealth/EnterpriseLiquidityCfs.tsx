import { CalendarCheckIcon, CompassIcon } from "@phosphor-icons/react";
import type { FamilyEnterpriseView } from "../../api/familyEnterprise";
import { formatDate, formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";

export function EnterpriseLiquidityCfs({ view }: { view: FamilyEnterpriseView }) {
  const enterpriseById = new Map(view.enterprises.map((enterprise) => [
    enterprise.profile.id,
    enterprise.profile.name,
  ]));
  return (
    <section className="enterprise-liquidity-section" aria-labelledby="enterprise-liquidity-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Liquidity events + CFS implications</p>
          <h2 id="enterprise-liquidity-title">流动性窗口是可能性，不是已经到账的现金</h2>
        </div>
        <p>融资、IPO、解禁与股权出售按日期、概率和锁定条件逐项留痕。</p>
      </header>
      <div className="enterprise-liquidity-layout">
        <ol className="enterprise-event-rail">
          {view.liquidity_events.map((event) => (
            <li key={event.id}>
              <span><CalendarCheckIcon size={18} weight="duotone" aria-hidden="true" /></span>
              <div><small>{formatDate(event.expected_date)} · {formatDomainLabel(event.status)}</small><strong>{enterpriseById.get(event.enterprise_id) ?? "关联企业"} · {formatDomainLabel(event.event_type)}</strong><p>估计价值 {formatMoney(event.estimated_value)} · 概率 {formatRatio(event.probability)}{event.lockup ? " · 存在锁定期" : ""}</p></div>
            </li>
          ))}
        </ol>
        <aside className="enterprise-cfs-note">
          <span><CompassIcon size={20} weight="duotone" aria-hidden="true" /> CFS implications</span>
          <h3>约束已准备，正式评分尚未启用</h3>
          <p>{view.cfs_implication.explanation}</p>
          <ul>{view.cfs_implication.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
        </aside>
      </div>
    </section>
  );
}
