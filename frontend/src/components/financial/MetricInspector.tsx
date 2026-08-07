import { useEffect, useRef } from "react";
import type { MetricResult } from "../../api/financial";
import { formatMetricValue } from "../../utils/format";
import { StatusBadge } from "../ui/StatusBadge";

interface MetricInspectorProps {
  metric: MetricResult | null;
  onClose: () => void;
}

const statusLabel: Record<MetricResult["status"], string> = {
  strong: "表现较强",
  healthy: "区间内",
  attention: "需要关注",
  warning: "建议处理",
  critical: "优先处理",
  review: "需要复核",
  not_applicable: "不适用",
};

function toneFor(status: MetricResult["status"]): "success" | "warning" | "info" | "danger" {
  if (status === "strong" || status === "healthy") return "success";
  if (status === "critical") return "danger";
  if (status === "attention" || status === "warning") return "warning";
  return "info";
}

export function MetricInspector({ metric, onClose }: MetricInspectorProps) {
  const inspectorRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!metric) return;
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        inspectorRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus.current?.focus();
    };
  }, [metric, onClose]);

  if (!metric) return null;

  return (
    <div className="inspector-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside
        ref={inspectorRef}
        className="metric-inspector"
        role="dialog"
        aria-modal="true"
        aria-labelledby="metric-inspector-title"
        aria-describedby="metric-inspector-description"
      >
        <header className="inspector-header">
          <div>
            <p className="eyebrow-code">{metric.metric_id}</p>
            <h2 id="metric-inspector-title">{metric.name}</h2>
          </div>
          <button ref={closeRef} type="button" className="icon-button" onClick={onClose} aria-label="关闭指标详情">
            ×
          </button>
        </header>

        <div className="inspector-result">
          <strong>{formatMetricValue(metric)}</strong>
          <StatusBadge tone={toneFor(metric.status)}>{statusLabel[metric.status]}</StatusBadge>
        </div>
        <p id="metric-inspector-description" className="inspector-explanation">{metric.explanation}</p>

        <section className="inspector-section" aria-labelledby="formula-heading">
          <h3 id="formula-heading">公式与实际代入</h3>
          <dl className="audit-definition-list">
            <div><dt>公式</dt><dd><code>{metric.formula}</code></dd></div>
            <div><dt>本次代入</dt><dd><code>{metric.substitution}</code></dd></div>
            <div><dt>分子</dt><dd>{metric.numerator ?? "不适用"}</dd></div>
            <div><dt>分母</dt><dd>{metric.denominator ?? "不适用"}</dd></div>
            <div><dt>单位</dt><dd>{metric.unit}</dd></div>
          </dl>
          <div className="data-table-wrap compact-table">
            <table className="data-table">
              <thead><tr><th>输入项</th><th>数值</th><th>来源记录</th></tr></thead>
              <tbody>
                {metric.inputs.map((input) => (
                  <tr key={input.key}>
                    <td>{input.label}<small>{input.key}</small></td>
                    <td className="numeric-cell">{input.value} {input.unit}</td>
                    <td>{input.source_record_ids.length > 0 ? input.source_record_ids.join("、") : "聚合值"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="inspector-section" aria-labelledby="reference-heading">
          <h3 id="reference-heading">参考条件与可追溯性</h3>
          <dl className="audit-definition-list">
            <div><dt>当前参考条件</dt><dd>{metric.reference.reference_range}</dd></div>
            <div><dt>阈值版本</dt><dd>{metric.threshold_version}</dd></div>
            <div><dt>参考来源类型</dt><dd>{metric.reference.source_type}</dd></div>
            <div><dt>参考说明</dt><dd>{metric.reference.source_reference}</dd></div>
            <div><dt>数据日期</dt><dd>{metric.data_as_of}</dd></div>
            <div><dt>计算来源</dt><dd>{metric.source_type}</dd></div>
            <div><dt>适用性</dt><dd>{metric.applicability.applicable ? "适用" : "不适用"}：{metric.applicability.reason}</dd></div>
            <div><dt>解释键</dt><dd><code>{metric.explanation_key}</code></dd></div>
          </dl>
        </section>

        <section className="inspector-section" aria-labelledby="action-heading">
          <h3 id="action-heading">建议下一步</h3>
          <ol className="action-list">
            {metric.actions.map((action) => <li key={action}>{action}</li>)}
          </ol>
        </section>
      </aside>
    </div>
  );
}
