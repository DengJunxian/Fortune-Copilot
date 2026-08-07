import { useCallback, useEffect, useState } from "react";
import {
  downloadFormalReport,
  fetchCurrentFormalReport,
  formalChapterTitles,
  generateFormalReport,
  recalculateFormalReport,
  type FormalReport,
  type ReportGenerationChain,
} from "../../api/formalReport";
import { usePortalContext } from "../../contexts/PortalContext";
import {
  evaluateReportQualityGate,
  publishReport,
  type QualityGate,
} from "../../api/security";
import { formatDate, formatDateTime } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

export function AdvisorFormalReportPanel({
  householdId,
  analysisDate,
}: {
  householdId: string;
  analysisDate: string;
}) {
  const { actor } = usePortalContext();
  const [report, setReport] = useState<FormalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setReport(await fetchCurrentFormalReport(householdId, actor, signal));
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setReport(null);
      setError("正式报告快照暂不可用；面谈底稿仍可继续核对。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [actor, householdId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function generate() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await generateFormalReport(householdId, actor, analysisDate);
      setReport(next);
      setMessage(`正式规划书 R${next.sequence} 已生成并关联当前可用方案版本；关键数字来自确定性工具。`);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "正式规划书生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function recalculate() {
    if (!report) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await recalculateFormalReport(householdId, actor, report, "major_event");
      setReport(next);
      setMessage(`已创建 R${next.sequence}；R${report.sequence} 保留在不可变历史链。`);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "报告重算失败。");
    } finally {
      setBusy(false);
    }
  }

  async function download(format: "html" | "pdf") {
    if (!report) return;
    setBusy(true);
    setError(null);
    try {
      await downloadFormalReport(report, format, actor);
      setMessage(`${format.toUpperCase()} 已由当前客户经理身份导出，审计事件已记录。`);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "报告导出失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="formal-report-portal-panel" aria-labelledby="advisor-report-heading">
      <header className="section-header-row">
        <div><p className="section-index">正式八章规划书</p><h3 id="advisor-report-heading">客户与顾问读取同一份报告快照</h3></div>
        {report ? <StatusBadge tone={report.consistency_status === "passed" ? "success" : "warning"}>R{report.sequence} · {report.consistency_status === "passed" ? "一致性通过" : "待复核"}</StatusBadge> : <StatusBadge tone="info">尚未生成</StatusBadge>}
      </header>
      {loading ? <p className="workflow-loading" role="status">正在核对八章结构、来源和版本…</p> : null}
      {message ? <p className="formal-report-state" data-tone="success" role="status">{message}</p> : null}
      {error ? <p className="formal-report-state" data-tone="warning" role="alert">{error}</p> : null}
      {report ? (
        <div className="formal-report-portal-body">
          <dl>
            <div><dt>数据日</dt><dd>{formatDate(report.data_as_of)}</dd></div>
            <div><dt>生成时间</dt><dd>{formatDateTime(report.generated_at)}</dd></div>
            <div><dt>报告版本</dt><dd>{report.versions.report_version}</dd></div>
            <div><dt>方案版本</dt><dd>{report.versions.workflow_version ?? "未关联"}</dd></div>
            <div><dt>行动进度</dt><dd>{report.execution_metrics.completed}/{report.execution_metrics.total}</dd></div>
            <div><dt>哈希</dt><dd>{report.report_hash.slice(0, 16)}</dd></div>
          </dl>
          <ol aria-label="正式规划书八章目录">{report.chapters.map((chapter) => <li key={chapter.number}><span>{String(chapter.number).padStart(2, "0")}</span><div><strong>{chapter.title}</strong><p>{chapter.summary}</p></div></li>)}</ol>
          <div className="workflow-action-row">
            <Button type="button" variant="secondary" loading={busy} onClick={() => void download("html")}>导出 HTML</Button>
            <Button type="button" variant="secondary" loading={busy} onClick={() => void download("pdf")}>导出 PDF</Button>
            <Button type="button" loading={busy} onClick={() => void recalculate()}>重大事件后新建快照</Button>
          </div>
        </div>
      ) : !loading ? (
        <div className="formal-report-empty-state">
          <ol aria-label="正式规划书八章目录">{formalChapterTitles.map((title, index) => <li key={title}><span>{String(index + 1).padStart(2, "0")}</span><strong>{title}</strong></li>)}</ol>
          <div><p>生成动作会完成确定性计算、受控事实引用、版本记录和 PDF 可导出校验；不会用语言模型计算金额或比率。</p><Button type="button" loading={busy} onClick={() => void generate()}>生成完整八章规划书</Button></div>
        </div>
      ) : null}
    </section>
  );
}

export function ReportGenerationChainPanel({
  chain,
  loading,
}: {
  chain: ReportGenerationChain | null;
  loading: boolean;
}) {
  const [humanReviewed, setHumanReviewed] = useState(false);
  const [gate, setGate] = useState<QualityGate | null>(null);
  const [gateBusy, setGateBusy] = useState(false);
  const [gateMessage, setGateMessage] = useState<string | null>(null);
  const current = chain?.items.find((item) => item.report_id === chain.current_report_id) ?? null;

  async function runGate() {
    if (!current || !humanReviewed) return;
    setGateBusy(true);
    setGateMessage(null);
    try {
      const result = await evaluateReportQualityGate(current.report_id);
      setGate(result);
      setGateMessage(result.passed ? "十项门禁全部通过，可执行二次确认发布。" : "存在阻断项，报告保持未发布。 ");
    } catch {
      setGateMessage("门禁运行失败；报告保持未发布。 ");
    } finally {
      setGateBusy(false);
    }
  }

  async function confirmPublish() {
    if (!current || !gate?.passed || !humanReviewed) return;
    setGateBusy(true);
    setGateMessage(null);
    try {
      const result = await publishReport(current.report_id, current.sequence);
      setGate(result.gate);
      setGateMessage(`报告已发布，水印：${result.watermark}。`);
    } catch {
      setGateMessage("发布被拒绝；请重新核对报告版本和全部门禁。 ");
    } finally {
      setGateBusy(false);
    }
  }

  return (
    <section className="report-generation-chain" aria-labelledby="report-chain-heading">
      <header className="section-header-row">
        <div><p className="section-index">正式报告生成链</p><h3 id="report-chain-heading">快照、版本、哈希与触发原因</h3></div>
        {chain ? <StatusBadge tone={chain.chain_verified ? "success" : "danger"}>{chain.chain_verified ? "哈希链已验证" : "哈希链异常"}</StatusBadge> : <StatusBadge tone="info">等待报告</StatusBadge>}
      </header>
      {loading ? <p className="workflow-loading" role="status">正在读取正式报告生成链…</p> : null}
      {!loading && (!chain || chain.items.length === 0) ? <p className="empty-state">当前家庭尚无正式报告快照。合规端只能读取生成链，不能代替客户或顾问生成、重算或修改行动。</p> : null}
      {chain && chain.items.length > 0 ? (
        <>
          <ol aria-label="正式报告不可变版本链">{chain.items.map((item) => (
            <li key={item.report_id} data-current={item.report_id === chain.current_report_id || undefined}>
              <span>R{item.sequence}</span>
              <div><strong>{item.report_version}</strong><p>{item.generation_trigger} · 数据日 {formatDate(item.data_as_of)} · {formatDateTime(item.generated_at)}</p></div>
              <dl><div><dt>报告哈希</dt><dd>{item.report_hash.slice(0, 16)}</dd></div><div><dt>父快照</dt><dd>{item.parent_report_id?.slice(0, 12) ?? "起点"}</dd></div><div><dt>方案版本</dt><dd>{item.workflow_version_id?.slice(0, 12) ?? "未关联"}</dd></div></dl>
            </li>
          ))}</ol>
          <footer><span>{chain.items.length} 个快照</span><span>{chain.audit_event_ids.length} 条关联审计事件</span><p>{chain.boundary_note}</p></footer>
          <section className="release-gate" aria-labelledby="release-gate-heading">
            <header><div><p className="section-index">发布控制</p><h4 id="release-gate-heading">十项质量门禁</h4></div>{gate ? <StatusBadge tone={gate.passed ? "success" : "danger"}>{gate.passed ? "全部通过" : "发布阻断"}</StatusBadge> : <StatusBadge tone="info">尚未运行</StatusBadge>}</header>
            <label><input type="checkbox" checked={humanReviewed} onChange={(event) => { setHumanReviewed(event.target.checked); setGate(null); }} />我已人工复核报告、授权、数字、来源及适当性证据</label>
            <div className="workflow-action-row"><Button type="button" variant="secondary" disabled={!humanReviewed || !current} loading={gateBusy} onClick={() => void runGate()}>运行十项发布门禁</Button><Button type="button" disabled={!gate?.passed || !humanReviewed} loading={gateBusy} onClick={() => void confirmPublish()}>二次确认并发布</Button></div>
            {gate ? <ol aria-label="报告发布十项门禁">{gate.gates.map((item) => <li key={item.code}><span>{item.label}</span><p>{item.explanation}</p><StatusBadge tone={item.status === "pass" ? "success" : "danger"}>{item.status === "pass" ? "通过" : "阻断"}</StatusBadge></li>)}</ol> : null}
            {gateMessage ? <p role="status">{gateMessage}</p> : null}
          </section>
        </>
      ) : null}
    </section>
  );
}
