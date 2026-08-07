import { usePortalContext } from "../contexts/PortalContext";
import { StatusBadge } from "../components/ui/StatusBadge";
import { PortfolioPortalWorkspace } from "../components/portfolio/PortfolioWorkspace";
import { TwinPortalWorkspace } from "../components/twin/TwinWorkspace";
import { BehaviorPortalWorkspace } from "../components/behavior/BehaviorWorkspace";
import { TrustPortalWorkspace } from "../components/trust/TrustWorkspace";
import { RiskWorkflowWorkspace } from "../components/workflow/RiskWorkflowWorkspace";
import { SecurityQualityWorkspace } from "../components/security/SecurityQualityWorkspace";

const guardrailCopy: Record<string, { title: string; detail: string }> = {
  credit_limit_is_not_asset: {
    title: "信用卡额度不是资产",
    detail: "备用授信只能单独展示，信用卡未付计入负债。",
  },
  no_fixed_four_account_ratio: {
    title: "禁止固定四账户比例",
    detail: "先执行流动性、偿债、保障、期限和适当性约束。",
  },
  no_principal_or_return_guarantee: {
    title: "禁止保本保收益承诺",
    detail: "存款、银行理财、基金、信托和保险按各自属性建模。",
  },
  llm_must_not_calculate_key_numbers: {
    title: "LLM 不计算关键数字",
    detail: "金额、比率和配置只能读取确定性工具输出。",
  },
  growth_70_percent_requires_long_term_funds_and_safety_gates: {
    title: "70% 必须有分母和闸门",
    detail: "只适用于通过安全闸门后的长期资金或新增长期结余。",
  },
  minimum_wage_is_not_cpi: {
    title: "最低工资不等于 CPI",
    detail: "最低工资仅作为民生收入追赶辅助信号。",
  },
  no_default_stock_leverage_or_futures_recommendation: {
    title: "普通家庭默认禁入高风险捷径",
    detail: "不默认推荐个股、杠杆、场外配资或股指期货。",
  },
};

export function RiskPage() {
  const { capabilities } = usePortalContext();
  return (
    <main className="page-shell" id="main-content">
      <header className="page-intro">
        <p className="page-kicker">风险端</p>
        <h1>风险与审计控制台</h1>
        <p>从同一方案版本复核三道闸门、禁止性表述、数字、来源、授权、模型治理与审计哈希。</p>
      </header>

      <RiskWorkflowWorkspace />
      <SecurityQualityWorkspace />

      <details className="technical-evidence-drawer">
        <summary>查看基础禁令与专项对抗证据</summary>
      <section aria-labelledby="guardrail-heading">
        <h2 className="section-heading" id="guardrail-heading">
          基础治理规则
        </h2>
        <ul className="guardrail-list">
          {capabilities.guardrails.map((guardrail) => {
            const copy = guardrailCopy[guardrail] ?? {
              title: guardrail,
              detail: "规则已由能力接口声明。",
            };
            return (
              <li className="guardrail-item" key={guardrail}>
                <strong>{copy.title}</strong>
                <span>{copy.detail}</span>
                <StatusBadge tone="success">底座已固化</StatusBadge>
              </li>
            );
          })}
        </ul>
      </section>
      <PortfolioPortalWorkspace view="risk" />
      <TwinPortalWorkspace view="risk" />
      <BehaviorPortalWorkspace view="risk" />
      <TrustPortalWorkspace view="risk" />
      </details>
    </main>
  );
}
