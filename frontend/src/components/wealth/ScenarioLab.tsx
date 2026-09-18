import { BriefcaseIcon, GraduationCapIcon, HeartbeatIcon, PersonSimpleRunIcon, TrendDownIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { AppLink } from "../../router/Link";

const scenarios = [
  { code: "unemployment", label: "收入中断", description: "记录已经发生的工资变化，并生成新快照。", to: "#life-event-composer", icon: TrendDownIcon, available: true },
  { code: "medical", label: "医疗支出上升", description: "先核对保障缺口与医疗责任，不直接猜测支出金额。", to: "/wealth/goals", icon: HeartbeatIcon, available: false },
  { code: "enterprise", label: "企业估值变化", description: "进入家企财富底稿，按持股与担保关系重算经济暴露。", to: "/wealth/family-enterprise", icon: BriefcaseIcon, available: false },
  { code: "retirement", label: "提前退休", description: "核对制度权益、退休底线和长寿缺口。", to: "/wealth/retirement", icon: PersonSimpleRunIcon, available: false },
  { code: "education", label: "教育成本上升", description: "调整责任现金流后，再核对资金缺口和 ELTC。", to: "/wealth/goals", icon: GraduationCapIcon, available: false },
] as const;

export function ScenarioLab() {
  const [selectedCode, setSelectedCode] = useState<(typeof scenarios)[number]["code"]>("unemployment");
  const selected = scenarios.find((item) => item.code === selectedCode) ?? scenarios[0];
  return (
    <section className="scenario-lab" aria-labelledby="scenario-lab-title">
      <header><div><p className="section-eyebrow">Scenario Lab</p><h2 id="scenario-lab-title">如果家庭条件变化，先看哪一条链会被影响</h2></div><p>场景用于组织事实核对，不替代真实事件、人工确认或专业测算。</p></header>
      <fieldset><legend className="sr-only">选择家庭变化场景</legend>{scenarios.map((scenario) => { const Icon = scenario.icon; return <label key={scenario.code} data-selected={selectedCode === scenario.code}><input type="radio" name="scenario-lab" value={scenario.code} checked={selectedCode === scenario.code} onChange={() => setSelectedCode(scenario.code)} /><Icon size={23} weight="duotone" aria-hidden="true" /><span><strong>{scenario.label}</strong><small>{scenario.available ? "可写入已发生事件" : "进入对应规划模块"}</small></span></label>; })}</fieldset>
      <div className="scenario-lab-selection"><div><strong>{selected.label}</strong><p>{selected.description}</p></div>{selected.to.startsWith("#") ? <a href={selected.to}>填写已发生变化</a> : <AppLink to={selected.to}>进入对应模块</AppLink>}</div>
    </section>
  );
}
