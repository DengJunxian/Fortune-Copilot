import {
  CheckCircleIcon,
  InfoIcon,
  ProhibitIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import type { EligibleCapitalResponse } from "../../api/liability";
import type { CalibrationMode, CalibrationStatus } from "../../api/liability";
import { formatMoney, formatRatio } from "../../utils/format";

export function EligibleCapitalBridge({ result }: { result: EligibleCapitalResponse }) {
  const { calculation } = result;
  const [explanationMode, setExplanationMode] = useState<"simple" | "standard" | "professional">("standard");
  const dispatchable = Number(calculation.dispatchable_financial_resources);
  const width = (value: string) => dispatchable > 0
    ? `${Math.max(1.5, Number(value) / dispatchable * 100)}%`
    : "1.5%";
  const reservedCapital = Math.max(0, dispatchable - Number(calculation.eligible_long_term_capital));
  const simpleExplanation = `并非全部金融资源都适合承担长期市场波动。当前先保留 ${formatMoney(String(reservedCapital))} 用于家庭周转、责任和安全垫。`;
  const standardExplanation = `当前家庭拥有 ${formatMoney(calculation.dispatchable_financial_resources)} 可调度金融资源；逐项覆盖日常周转、应急、债务、保障、近期责任、已承诺目标与锁定资金后，${formatMoney(calculation.eligible_long_term_capital)} 可以进入长期配置评估。`;
  const professionalExplanation = `ELTC = ${formatMoney(calculation.dispatchable_financial_resources)} − ${formatMoney(String(reservedCapital))} = ${formatMoney(calculation.eligible_long_term_capital)}。公式版本 ${result.meta.formula_version}，输入哈希 ${result.meta.input_hash.slice(0, 12)}…；资格仍须通过全部安全闸门。`;
  const explanation = explanationMode === "simple"
    ? simpleExplanation
    : explanationMode === "professional"
      ? professionalExplanation
      : standardExplanation;
  return (
    <section className="eligible-capital-section" aria-labelledby="eligible-capital-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Eligible Long-Term Capital</p>
          <h2 id="eligible-capital-title">长期可投资资本 ELTC</h2>
        </div>
        <p>每一步均保留扣减前、扣减额、扣减后、来源和原因，可回溯而不可跳步。</p>
      </header>
      <div className="eltc-outcome" data-decision={calculation.decision}>
        <div>
          <span>{calculation.formally_eligible ? "可进入正式配置评估" : "当前应先修复前置责任"}</span>
          <strong>{formatMoney(calculation.eligible_long_term_capital)}</strong>
          <small>只有这部分资金才可以正式进入长期资产配置</small>
        </div>
        <aside>
          <InfoIcon size={19} weight="fill" aria-hidden="true" />
          <div>
            <strong>为什么不是全部金融资产？</strong>
            <p>{explanation}</p>
            <div className="eltc-explanation-modes" aria-label="ELTC 解释详细程度">
              {(["simple", "standard", "professional"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={explanationMode === mode}
                  onClick={() => setExplanationMode(mode)}
                >
                  {{ simple: "简洁", standard: "标准", professional: "专业" }[mode]}
                </button>
              ))}
            </div>
          </div>
        </aside>
      </div>
      <section className="capital-eligibility-view" aria-labelledby="capital-eligibility-title">
        <header>
          <div>
            <p className="section-eyebrow">Investment eligibility</p>
            <h3 id="capital-eligibility-title">哪些钱可以投资？</h3>
          </div>
          <p>资金用途先于产品选择；被家庭责任占用的资金不进入长期组合。</p>
        </header>
        <ul>
          {calculation.bridge.map((step) => (
            <li key={step.code} data-eligible="false">
              <ProhibitIcon size={20} weight="fill" aria-hidden="true" />
              <div><strong>{step.label}</strong><small>{step.reason}</small></div>
              <b>{formatMoney(step.deduction)}</b>
              <span>{Number(step.deduction) > 0 ? "不参与长期配置" : "当前无需预留"}</span>
            </li>
          ))}
          <li data-eligible={calculation.formally_eligible}>
            {calculation.formally_eligible
              ? <CheckCircleIcon size={20} weight="fill" aria-hidden="true" />
              : <WarningCircleIcon size={20} weight="fill" aria-hidden="true" />}
            <div><strong>长期可投资资本 ELTC</strong><small>通过责任扣减后，仍须满足安全与适当性闸门。</small></div>
            <b>{formatMoney(calculation.eligible_long_term_capital)}</b>
            <span>{calculation.formally_eligible ? "可进入长期投资" : "暂不进入长期投资"}</span>
          </li>
        </ul>
      </section>
      <ol className="eltc-waterfall">
        <li className="eltc-waterfall-origin">
          <span>起始</span><strong>{formatMoney(calculation.dispatchable_financial_resources)}</strong>
          <small>可调度金融资源（扣减前）</small>
        </li>
        {calculation.bridge.map((step, index) => (
          <li key={step.code}>
            <div className="eltc-step-head">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div><strong>{step.label}</strong><small>{step.source}</small></div>
              <b>− {formatMoney(step.deduction)}</b>
            </div>
            <div className="eltc-step-track" aria-hidden="true">
              <span style={{ width: width(step.before) }} />
              <i style={{ width: width(step.after) }} />
            </div>
            <div className="eltc-step-foot">
              <p>{step.reason}</p>
              <dl>
                <div><dt>扣减前</dt><dd>{formatMoney(step.before, true)}</dd></div>
                <div><dt>扣减后</dt><dd>{formatMoney(step.after, true)}</dd></div>
                {Number(step.unfunded) > 0
                  ? <div data-tone="warning"><dt>未覆盖</dt><dd>{formatMoney(step.unfunded, true)}</dd></div>
                  : null}
              </dl>
            </div>
          </li>
        ))}
      </ol>
      <div className="eltc-support-grid">
        <section aria-labelledby="eligibility-gates-title">
          <h3 id="eligibility-gates-title">资格与安全闸门</h3>
          <ul className="eligibility-gates">
            {calculation.eligibility_gates.map((gate) => (
              <li key={gate.code} data-passed={gate.passed}>
                {gate.passed
                  ? <CheckCircleIcon size={20} weight="fill" aria-hidden="true" />
                  : <WarningCircleIcon size={20} weight="fill" aria-hidden="true" />}
                <div><strong>{gate.label}</strong><span>{gate.reason}</span></div>
              </li>
            ))}
          </ul>
        </section>
        <PurchasingPower result={result} />
      </div>
    </section>
  );
}

function PurchasingPower({ result }: { result: EligibleCapitalResponse }) {
  const power = result.calculation.purchasing_power;
  const goalRate = power.goal_cost_inflation.length > 0
    ? power.goal_cost_inflation.reduce((highest, item) =>
      Number(item.annual_rate) > Number(highest.annual_rate) ? item : highest)
    : null;
  return (
    <section className="purchasing-power-v2" aria-labelledby="purchasing-power-v2-title">
      <header className="purchasing-power-heading">
        <div>
          <h3 id="purchasing-power-v2-title">购买力 V2</h3>
          <small>{power.calibration_registry_version}</small>
        </div>
        <CalibrationBadge status={power.calibration_status} modes={power.calibration_modes} />
      </header>
      <div className="purchasing-power-metrics">
        <div>
          <span>HCI</span><strong>{formatRatio(power.household_cost_inflation.annual_rate)}</strong>
          <small>家庭成本通胀</small>
          <CalibrationBadge
            status={power.household_cost_inflation.calibration_status}
            modes={power.household_cost_inflation.calibration_modes}
          />
        </div>
        <div>
          <span>GCI</span><strong>{goalRate ? formatRatio(goalRate.annual_rate) : "暂无"}</strong>
          <small>{goalRate ? `最高：${goalRate.stream_name}` : "目标成本增长"}</small>
          {goalRate
            ? <CalibrationBadge status={goalRate.calibration_status} modes={goalRate.calibration_modes} />
            : null}
        </div>
        <div>
          <span>IAI</span><strong>{Number(power.income_adequacy.ratio).toFixed(2)}×</strong>
          <small>收入充足度 · {power.income_adequacy.status}</small>
          <CalibrationBadge
            status={power.income_adequacy.calibration_status}
            modes={power.income_adequacy.calibration_modes}
          />
        </div>
      </div>
      <p>
        最低工资趋势只进入 IAI，不是 CPI，也不是投资收益门槛。
        {power.requires_human_review ? " 当前包含降级或待复核参数，不可作为银行授权结论。" : ""}
      </p>
    </section>
  );
}

const calibrationModeLabels: Record<CalibrationMode, string> = {
  controlled_demo: "受控演示",
  empirically_calibrated: "经验校准",
  bank_authorized: "银行授权",
};

const calibrationStatusLabels: Record<CalibrationStatus, string> = {
  available: "可用",
  degraded: "降级",
  needs_review: "待复核",
};

function CalibrationBadge({
  status,
  modes,
}: {
  status: CalibrationStatus;
  modes: CalibrationMode[];
}) {
  const modeLabel = modes.length > 0
    ? modes.map((mode) => calibrationModeLabels[mode]).join(" + ")
    : "未校准";
  return (
    <span className="calibration-badge" data-status={status}>
      {modeLabel} · {calibrationStatusLabels[status]}
    </span>
  );
}
