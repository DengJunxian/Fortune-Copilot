import { CalendarCheckIcon, UsersThreeIcon } from "@phosphor-icons/react";
import type { ProfessionalReferral } from "../../../api/cfs";
import { formatDate, formatDomainLabel } from "../../../utils/format";

export function ProfessionalReferralCard({ referrals }: { referrals: ProfessionalReferral[] }) {
  return (
    <section className="professional-referrals" aria-labelledby="professional-referrals-title">
      <header><div><p className="page-kicker">Professional referral</p><h2 id="professional-referrals-title">需要谁共同承接</h2></div><p>只有复杂度或专业边界被触发时才建立转介；客户经理仍负责整体沟通。</p></header>
      {referrals.length > 0 ? <div>{referrals.map((referral) => <article key={referral.id}><UsersThreeIcon size={25} weight="duotone" aria-hidden="true" /><div><strong>专业转介 · {formatDomainLabel(referral.specialist_type)}</strong><p>{referral.trigger_reason}</p><span>{formatDomainLabel(referral.urgency)} · {formatDomainLabel(referral.status)}</span></div>{referral.due_date ? <small><CalendarCheckIcon size={15} aria-hidden="true" /> {formatDate(referral.due_date)}</small> : null}</article>)}</div> : <p className="dashboard-unavailable">当前方案无需新增专业转介。</p>}
    </section>
  );
}
