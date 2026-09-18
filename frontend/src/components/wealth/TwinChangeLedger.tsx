import {
  ArrowsLeftRightIcon,
  CheckCircleIcon,
  MinusCircleIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import type { SnapshotComparison } from "../../api/persistentTwin";
import { formatDomainLabel, formatMoney } from "../../utils/format";

function moneyOrText(value: string | null): string {
  if (value === null) return "—";
  return Number.isFinite(Number(value)) ? formatMoney(value, true) : formatDomainLabel(value);
}

function needChangeSummary(item: SnapshotComparison["changed_needs"][number]): string {
  const parts: string[] = [];
  if (item.before_status !== item.after_status) {
    parts.push(
      `${item.before_status ? formatDomainLabel(item.before_status) : "无"} → ${item.after_status ? formatDomainLabel(item.after_status) : "无"}`,
    );
  }
  if (item.before_target_amount !== item.after_target_amount) {
    parts.push(`目标 ${moneyOrText(item.before_target_amount)} → ${moneyOrText(item.after_target_amount)}`);
  }
  return parts.join(" · ") || "需求内容已重算";
}

export function TwinChangeLedger({ comparison }: { comparison: SnapshotComparison }) {
  return (
    <section className="twin-change-section" aria-labelledby="twin-change-title">
      <header className="goals-section-header">
        <div>
          <p className="section-eyebrow">Change ledger</p>
          <h2 id="twin-change-title">这次变化影响了什么</h2>
        </div>
        <p>逐项比较前后快照；没有变化的模块也会明确说明，不用推测。</p>
      </header>
      <div className="twin-change-grid">
        <article>
          <h3>已变化事实</h3>
          {comparison.changed_facts.length > 0 ? (
            <ul className="twin-change-list">
              {comparison.changed_facts.map((item) => (
                <li key={item.code}>
                  <ArrowsLeftRightIcon size={18} aria-hidden="true" />
                  <div><strong>{item.label}</strong><span>{moneyOrText(item.before)} → {moneyOrText(item.after)}</span></div>
                </li>
              ))}
            </ul>
          ) : <EmptyChange text="当前为首个快照，尚无前后事实可比较。" />}
        </article>
        <article>
          <h3>需求变化</h3>
          {comparison.changed_needs.length > 0 ? (
            <ul className="twin-change-list">
              {comparison.changed_needs.map((item) => (
                <li key={`${item.need_type}-${item.change_type}`}>
                  <ArrowsLeftRightIcon size={18} aria-hidden="true" />
                  <div>
                    <strong>{formatDomainLabel(item.need_type)}</strong>
                    <span>{needChangeSummary(item)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : <EmptyChange text="本次事件没有改变需求种类、状态或目标金额。" />}
        </article>
        <article>
          <h3>风险预算变化</h3>
          <div className="twin-module-state" data-changed={comparison.changed_risk_budget.changed}>
            {comparison.changed_risk_budget.changed
              ? <WarningCircleIcon size={21} weight="fill" aria-hidden="true" />
              : <CheckCircleIcon size={21} weight="fill" aria-hidden="true" />}
            <div>
              <strong>{comparison.changed_risk_budget.changed ? "风险预算已重算" : "风险预算未发生变化"}</strong>
              <span>ELTC {formatMoney(comparison.changed_risk_budget.after.eligible_long_term_capital, true)} · {comparison.changed_risk_budget.after.formally_eligible ? "可进入正式评估" : "先修复前置责任"}</span>
            </div>
          </div>
        </article>
        <article>
          <h3>CFS 变化</h3>
          <div className="twin-module-state" data-changed="false">
            <MinusCircleIcon size={21} weight="fill" aria-hidden="true" />
            <div><strong>当前快照未绑定 CFS 版本</strong><span>{comparison.changed_cfs.after.explanation}</span></div>
          </div>
        </article>
      </div>
    </section>
  );
}

function EmptyChange({ text }: { text: string }) {
  return <p className="twin-empty-change"><MinusCircleIcon size={18} aria-hidden="true" />{text}</p>;
}
