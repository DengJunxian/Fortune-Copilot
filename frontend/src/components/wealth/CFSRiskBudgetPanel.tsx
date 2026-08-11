import {
  CheckCircleIcon,
  ProhibitIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import type { HouseholdRiskBudget, RiskBudgetFactor } from "../../api/cfs";
import { formatDomainLabel, formatMoney, formatRatio } from "../../utils/format";

function factorValue(factor: RiskBudgetFactor, budget: HouseholdRiskBudget): string {
  if (factor.level) return formatDomainLabel(factor.level);
  if (factor.code === "time_horizon") {
    return budget.shortest_time_horizon_days === null
      ? "无明确近期日期"
      : `${budget.shortest_time_horizon_days} 天`;
  }
  if (factor.code === "existing_economic_exposure") return formatMoney(factor.amount, true);
  return Number(factor.amount) > 0 ? `缺口 ${formatMoney(factor.amount, true)}` : "无缺口";
}

export function CFSRiskBudgetPanel({ budget }: { budget: HouseholdRiskBudget }) {
  const DecisionIcon = budget.additional_risk_allowed ? CheckCircleIcon : ProhibitIcon;
  return (
    <section className="cfs-risk-section" aria-labelledby="cfs-risk-heading">
      <header className="section-heading">
        <div>
          <p className="page-kicker">Household economic risk capacity</p>
          <h2 id="cfs-risk-heading">家庭风险预算，不是一个 R1–R5 标签。</h2>
        </div>
        <p>能力、意愿、行为、现有经济暴露、流动性、刚性责任与期限一起决定是否还能承担新风险。</p>
      </header>

      <div className="cfs-risk-decision" data-open={budget.additional_risk_allowed}>
        <div>
          <span><DecisionIcon size={19} weight="duotone" aria-hidden="true" /> 当前决策</span>
          <strong>{formatDomainLabel(budget.decision)}</strong>
          <p>{budget.additional_risk_allowed ? "前置责任与适当性门已通过，可在剩余预算内谨慎安排。" : "当前不新增投资是正式建议，不会用 0 元组合伪装成产品方案。"}</p>
        </div>
        <dl>
          <div><dt>经济风险能力</dt><dd>{formatDomainLabel(budget.household_economic_risk_capacity)}</dd></div>
          <div><dt>风险上限</dt><dd>{formatMoney(budget.risk_ceiling_amount, true)} <small>{formatRatio(budget.risk_ceiling_ratio)}</small></dd></div>
          <div><dt>现有经济暴露</dt><dd>{formatMoney(budget.existing_economic_exposure, true)} <small>{formatRatio(budget.economic_exposure_ratio)}</small></dd></div>
          <div><dt>剩余风险容量</dt><dd>{formatMoney(budget.remaining_risk_capacity, true)}</dd></div>
        </dl>
      </div>

      <ol className="cfs-factor-ledger" aria-label="风险预算七项因子">
        {budget.factors.map((factor, index) => (
          <li key={factor.code}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div><strong>{factor.label}</strong><p>{factor.explanation}</p></div>
            <b>{factorValue(factor, budget)}</b>
          </li>
        ))}
      </ol>

      {budget.constraints.length > 0 ? (
        <aside className="cfs-constraint-note">
          <WarningCircleIcon size={22} weight="duotone" aria-hidden="true" />
          <div><strong>当前约束</strong><ul>{budget.constraints.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </aside>
      ) : null}
    </section>
  );
}
