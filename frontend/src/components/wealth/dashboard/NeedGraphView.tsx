import { ArrowRightIcon, CheckCircleIcon, CircleDashedIcon } from "@phosphor-icons/react";
import type { WealthNeed, WealthNeedPriority } from "../../../api/clientProfile";
import { formatDomainLabel, formatMoney } from "../../../utils/format";

interface NeedGraphViewProps {
  needs: WealthNeed[];
  priorities: WealthNeedPriority[];
}

export function NeedGraphView({ needs, priorities }: NeedGraphViewProps) {
  const rankById = new Map(priorities.map((item) => [item.wealth_need_id, item]));
  const ordered = [...needs].sort((left, right) => {
    const leftRank = rankById.get(left.id)?.priority_rank ?? left.priority;
    const rightRank = rankById.get(right.id)?.priority_rank ?? right.priority;
    return leftRank - rightRank;
  }).slice(0, 4);

  if (ordered.length === 0) {
    return <p className="dashboard-unavailable">尚未形成可排序的家庭财富需要。</p>;
  }

  return (
    <ol className="need-graph" aria-label="财富需要优先顺序">
      {ordered.map((need, index) => {
        const priority = rankById.get(need.id);
        const prepared = need.status === "prepared";
        return (
          <li key={need.id} data-status={need.status}>
            <span className="need-graph-rank">{String(index + 1).padStart(2, "0")}</span>
            <span className="need-graph-marker" aria-hidden="true">
              {prepared
                ? <CheckCircleIcon size={22} weight="fill" />
                : <CircleDashedIcon size={22} weight="duotone" />}
            </span>
            <div>
              <strong>{formatDomainLabel(need.need_type)}</strong>
              <span>{formatDomainLabel(need.status)} · 目标 {formatMoney(need.target_amount, true)}</span>
              <small>{priority?.reason ?? (need.professional_review_required ? "需要专业复核" : "按家庭责任优先级排列")}</small>
            </div>
            {index < ordered.length - 1 ? <ArrowRightIcon className="need-graph-arrow" size={18} aria-hidden="true" /> : null}
          </li>
        );
      })}
    </ol>
  );
}
