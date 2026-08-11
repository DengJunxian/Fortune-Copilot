import {
  ArrowRightIcon,
  CheckCircleIcon,
  ProhibitIcon,
  UsersThreeIcon,
  WrenchIcon,
} from "@phosphor-icons/react";
import type {
  CFSComponent,
  CFSComponentType,
  CFSOrchestrationStep,
  CFSSolutionResponse,
  ProfessionalReferral,
} from "../../api/cfs";
import { formatDomainLabel, formatMoney } from "../../utils/format";

const toolLabels: Record<CFSOrchestrationStep["deterministic_tool"], string> = {
  financial_health: "家庭财务健康",
  liability_calendar: "责任流日历",
  protection_planner: "保障缺口测算",
  pension_planner: "养老规划",
  planning_waterfall: "资金瀑布",
  portfolio_optimizer: "组合优化器",
  family_enterprise: "家企财富孪生",
  professional_routing: "专业服务路由",
  no_action: "无新增行动",
};

const componentLabels: Record<CFSComponentType, string> = {
  liquidity: "流动性安排",
  debt: "债务安排",
  protection: "保障安排",
  housing: "住房安排",
  education: "教育安排",
  retirement: "养老安排",
  investment: "长期配置",
  enterprise_risk: "家企风险",
  cross_border: "跨境与币种",
  succession: "财富传承",
  trust: "信托审查",
  philanthropy: "公益安排",
  professional_service: "专业服务",
  no_action: "当前不新增投资",
};

function CFSDecisionRow({
  component,
  step,
  referral,
}: {
  component: CFSComponent;
  step: CFSOrchestrationStep;
  referral: ProfessionalReferral | undefined;
}) {
  const noAction = component.status === "no_action_required";
  const StatusIcon = noAction ? ProhibitIcon : CheckCircleIcon;
  return (
    <li data-status={component.status}>
      <span className="cfs-priority">{String(component.priority).padStart(2, "0")}</span>
      <article>
        <header>
          <div>
            <small>{formatDomainLabel(component.time_horizon)} · {formatDomainLabel(component.status)}</small>
            <h3>{componentLabels[component.component_type]}</h3>
          </div>
          <span className="cfs-status"><StatusIcon size={16} weight="duotone" aria-hidden="true" /> {noAction ? "NO_ACTION_REQUIRED" : formatDomainLabel(component.status)}</span>
        </header>
        <div className="cfs-decision-flow">
          <div><span>优先原因</span><p>{component.rationale}</p></div>
          <ArrowRightIcon size={17} aria-hidden="true" />
          <div><span>建议行动</span><p>{component.recommended_action}</p></div>
          <ArrowRightIcon size={17} aria-hidden="true" />
          <div className="cfs-amount"><span>目标金额</span><strong>{formatMoney(component.target_amount, true)}</strong><small>最低 {formatMoney(component.minimum_amount, true)}</small></div>
        </div>
        <footer>
          <span><WrenchIcon size={16} aria-hidden="true" /> {toolLabels[step.deterministic_tool]}</span>
          <span>允许风险：<strong>{formatDomainLabel(step.allowed_risk)}</strong></span>
          <span><UsersThreeIcon size={16} aria-hidden="true" /> {referral ? formatDomainLabel(referral.specialist_type) : "无需专业转介"}</span>
        </footer>
      </article>
    </li>
  );
}

export function CFSDecisionLedger({ solution }: { solution: CFSSolutionResponse }) {
  const steps = new Map(solution.orchestration.map((item) => [item.component_id, item]));
  const referrals = new Map(solution.referrals.map((item) => [item.component_id, item]));
  return (
    <section className="cfs-decision-section" aria-labelledby="cfs-decision-heading">
      <header className="section-heading">
        <div>
          <p className="page-kicker">Comprehensive financial solution</p>
          <h2 id="cfs-decision-heading">从需要开始，不从产品代码开始。</h2>
        </div>
        <p>每一行按同一顺序说明为什么做、做什么、用多少钱、允许多大风险，以及由哪个工具或专业人员承接。</p>
      </header>
      <ol className="cfs-decision-ledger">
        {solution.components.map((component) => {
          const step = steps.get(component.id);
          if (!step) return null;
          return <CFSDecisionRow key={component.id} component={component} step={step} referral={referrals.get(component.id)} />;
        })}
      </ol>
      <p className="cfs-product-boundary">{solution.solution.summary.boundary ?? "本阶段只确定目的、金额、风险预算、工具和专业路由；不生成基金代码或产品清单。"}</p>
    </section>
  );
}
