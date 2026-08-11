import { CheckCircleIcon, ProhibitIcon, UsersThreeIcon } from "@phosphor-icons/react";
import type { CFSComponent } from "../../../api/cfs";
import { formatDomainLabel, formatMoney } from "../../../utils/format";

export function CfsComponentCard({ component }: { component: CFSComponent }) {
  const noAction = component.status === "no_action_required";
  const Icon = noAction ? ProhibitIcon : CheckCircleIcon;
  return (
    <article className="cfs-component-card" data-status={component.status}>
      <header><Icon size={20} weight="duotone" aria-hidden="true" /><span>{formatDomainLabel(component.component_type)}</span><strong>#{component.priority}</strong></header>
      <p>{component.recommended_action}</p>
      <dl><div><dt>目标</dt><dd>{formatMoney(component.target_amount, true)}</dd></div><div><dt>时间</dt><dd>{formatDomainLabel(component.time_horizon)}</dd></div></dl>
      {component.required_specialist ? <small><UsersThreeIcon size={15} aria-hidden="true" /> 专业承接：{formatDomainLabel(component.required_specialist)}</small> : null}
    </article>
  );
}
