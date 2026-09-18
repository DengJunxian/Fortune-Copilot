import {
  CheckCircleIcon,
  ProhibitIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import type { HouseholdRiskBudget, RiskBudgetFactor } from "../../api/cfs";
import type { RiskLevel } from "../../api/clientProfile";
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

const riskBand: Record<RiskLevel, string> = {
  low: "R1",
  medium_low: "R2",
  medium: "R3",
  medium_high: "R4",
  high: "R5",
};

function factorExplanation(budget: HouseholdRiskBudget, code: RiskBudgetFactor["code"]): string {
  return budget.factors.find((factor) => factor.code === code)?.explanation ?? "由当前已确认家庭事实计算。";
}

export function CFSRiskBudgetPanel({ budget }: { budget: HouseholdRiskBudget }) {
  const DecisionIcon = budget.additional_risk_allowed ? CheckCircleIcon : ProhibitIcon;
  return (
    <section className="cfs-risk-section" aria-labelledby="cfs-risk-heading">
      <header className="section-heading">
        <div>
          <p className="page-kicker">Goal + Risk + Behavior</p>
          <h2 id="cfs-risk-heading">Family Risk Profile</h2>
        </div>
        <p>能力、意愿与真实行为先形成基础上限，再由现有暴露、流动性、刚性责任与期限继续收紧家庭风险预算。</p>
      </header>

      <ol className="family-risk-profile" aria-label="家庭风险画像四层">
        <li>
          <span>01 · Risk Capacity</span>
          <div><small>风险承担能力</small><strong>{riskBand[budget.capacity]}</strong><b>{formatDomainLabel(budget.capacity)}</b></div>
          <p>{factorExplanation(budget, "capacity")}</p>
        </li>
        <li>
          <span>02 · Risk Willingness</span>
          <div><small>风险承受意愿</small><strong>{riskBand[budget.willingness]}</strong><b>{formatDomainLabel(budget.willingness)}</b></div>
          <p>{factorExplanation(budget, "willingness")}</p>
        </li>
        <li data-behavior="true">
          <span>03 · Behavior Risk</span>
          <div><small>真实行为约束</small><strong>{riskBand[budget.behavior]}</strong><b>{formatDomainLabel(budget.behavior)}</b></div>
          <p>{factorExplanation(budget, "behavior")} 行为证据只允许保持或下调预算，不能自动上调。</p>
        </li>
        <li data-final="true">
          <span>04 · Family Risk Budget</span>
          <div><small>最终家庭风险预算</small><strong>{riskBand[budget.household_economic_risk_capacity]}</strong><b>{formatDomainLabel(budget.household_economic_risk_capacity)}</b></div>
          <p>这是进入配置与产品适当性判断的风险上限，不以单次问卷作为唯一依据。</p>
        </li>
      </ol>

      <div className="cfs-risk-decision" data-open={budget.additional_risk_allowed}>
        <div>
          <span><DecisionIcon size={19} weight="duotone" aria-hidden="true" /> 当前决策</span>
          <strong>{formatDomainLabel(budget.decision)}</strong>
          <p>{budget.additional_risk_allowed ? "前置责任与适当性门已通过，可在剩余预算内谨慎安排。" : "当前不新增投资是正式建议，不会用 0 元组合伪装成产品方案。"}</p>
        </div>
        <dl>
          <div><dt>最终风险预算</dt><dd>{riskBand[budget.household_economic_risk_capacity]} <small>{formatDomainLabel(budget.household_economic_risk_capacity)}</small></dd></div>
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
