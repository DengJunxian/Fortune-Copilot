import { useCallback, useEffect, useState } from "react";
import {
  fetchSecurityDashboard,
  runSecurityEvaluation,
  type SecurityDashboard,
} from "../../api/security";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

const metricLabels = {
  calculation_correctness_pct: "核心计算正确率",
  citation_coverage_pct: "引用覆盖率",
  unsupported_fact_rate_pct: "无依据事实率",
  suitability_block_rate_pct: "不适当建议阻断率",
  prompt_injection_block_rate_pct: "提示注入阻断率",
  report_consistency_pct: "报告数值一致率",
} as const;

export function SecurityQualityWorkspace() {
  const [dashboard, setDashboard] = useState<SecurityDashboard | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const next = await fetchSecurityDashboard(signal);
    setDashboard(next);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal).catch(() => setMessage("安全评测台账暂不可用；核心业务仍按 Mock 模式降级运行。"));
    return () => controller.abort();
  }, [refresh]);

  async function runEvaluation() {
    setRunning(true);
    setMessage(null);
    try {
      const evaluation = await runSecurityEvaluation();
      setDashboard((current) => current ? { ...current, latest_evaluation: evaluation } : current);
      if (!dashboard) await refresh();
      setMessage(`八类对抗用例通过 ${evaluation.metrics.adversarial_passed}/${evaluation.metrics.adversarial_total}。`);
    } catch {
      setMessage("评测未完成；未把失败请求包装成通过结果。");
    } finally {
      setRunning(false);
    }
  }

  const evaluation = dashboard?.latest_evaluation ?? null;
  return (
    <section className="security-quality" aria-labelledby="security-quality-heading">
      <header>
        <div>
          <p className="page-kicker">Security · Privacy · Model Risk</p>
          <h2 id="security-quality-heading">测试环境安全与模型风险质量门禁</h2>
          <p>指标来自确定性夹具和本地对抗套件，不代表生产安全水平或真实客户效果。</p>
        </div>
        <div className="security-quality-actions">
          <StatusBadge tone="warning">仅测试环境</StatusBadge>
          <Button type="button" loading={running} onClick={() => void runEvaluation()}>运行八类对抗评测</Button>
        </div>
      </header>

      {evaluation ? (
        <>
          <dl className="security-metric-grid">
            {Object.entries(metricLabels).map(([code, label]) => (
              <div key={code}><dt>{label}</dt><dd>{evaluation.metrics[code as keyof typeof metricLabels]}%</dd><small>test fixture</small></div>
            ))}
          </dl>
          <ol className="security-case-list" aria-label="八类对抗用例">
            {evaluation.cases.map((item) => (
              <li key={item.code}>
                <span>{item.code}</span>
                <div><strong>{item.title}</strong><small>期望 {item.expected} · 实际 {item.observed}</small></div>
                <StatusBadge tone={item.passed ? "success" : "danger"}>{item.passed ? "通过" : "阻断发布"}</StatusBadge>
              </li>
            ))}
          </ol>
        </>
      ) : <p className="empty-state">尚无评测运行；点击按钮生成可追溯测试记录。</p>}

      {dashboard ? (
        <footer>
          <span>模型运行台账 {Object.values(dashboard.model_run_counts).reduce((sum, value) => sum + value, 0)} 条</span>
          <span>质量门禁通过 {dashboard.quality_gate_counts.passed ?? 0} / 阻断 {dashboard.quality_gate_counts.blocked ?? 0}</span>
          <span>已启用控制 {dashboard.controls.filter((item) => item.implemented).length} 项</span>
        </footer>
      ) : null}
      <p className="privacy-boundary">{dashboard?.boundary_note ?? "该面板不读取或展示 API Key、完整提示词和直接身份字段。"}</p>
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
