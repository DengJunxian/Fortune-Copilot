import { useCallback, useEffect, useMemo, useState } from "react";
import type { ClientExperience, ClientView } from "../../api/clientExperience";
import { clientExperienceExportUrl } from "../../api/clientExperience";
import {
  fetchCurrentFormalReport,
  formalChapterTitles,
  generateFormalReport,
  recalculateFormalReport,
  ReportApiError,
  reportExportUrl,
  type FormalReport,
  type FormalReportSection,
  type ReportAdvice,
} from "../../api/formalReport";
import { usePortalContext } from "../../contexts/PortalContext";
import { formatDate, formatDateTime, safeExternalUrl } from "../../utils/format";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";

function previewTone(status: string): "success" | "warning" | "info" {
  if (status === "ready") return "success";
  if (status === "pending_twin") return "warning";
  return "info";
}

const actionStatusLabels = {
  open: "待处理",
  completed: "已完成",
  deferred: "已延期",
  not_applicable: "不适用",
};

export function PlanningReportWorkspace({
  experience,
  onNavigate,
}: {
  experience: ClientExperience;
  onNavigate: (view: ClientView) => void;
}) {
  const { actor } = usePortalContext();
  const [formalReport, setFormalReport] = useState<FormalReport | null>(null);
  const [reportUnderReview, setReportUnderReview] = useState(false);
  const [loadingFormal, setLoadingFormal] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadFormal = useCallback(async (signal?: AbortSignal) => {
    setLoadingFormal(true);
    setError(null);
    setMessage(null);
    setReportUnderReview(false);
    if (experience.delivery.report === "under_review") {
      setFormalReport(null);
      setReportUnderReview(true);
      setMessage("正式报告正在顾问与合规审核；审核完成前仅展示确定性预览，不暴露内部草稿。");
      setLoadingFormal(false);
      return;
    }
    if (experience.delivery.report === "not_generated") {
      setFormalReport(null);
      setLoadingFormal(false);
      return;
    }
    try {
      const report = await fetchCurrentFormalReport(experience.household_id, actor, signal);
      if (signal?.aborted) return;
      if (report && report.chapters.map((item) => item.title).join("|") !== formalChapterTitles.join("|")) {
        throw new Error("正式报告一级目录未通过八章协议校验");
      }
      setFormalReport(report);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setFormalReport(null);
      if (loadError instanceof ReportApiError && loadError.code === "report_not_ready_for_client") {
        setReportUnderReview(true);
        setMessage("正式报告正在顾问与合规审核；审核完成前仅展示确定性预览，不暴露内部草稿。");
      } else {
        setError("正式报告服务暂不可用；下方只显示阶段九确定性预览，不冒充已生成文档。");
      }
    } finally {
      if (!signal?.aborted) setLoadingFormal(false);
    }
  }, [actor, experience.delivery.report, experience.household_id]);

  useEffect(() => {
    const controller = new AbortController();
    void loadFormal(controller.signal);
    return () => controller.abort();
  }, [loadFormal]);

  async function generate() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const report = await generateFormalReport(
        experience.household_id,
        actor,
        experience.analysis_date,
      );
      setFormalReport(report);
      setMessage(`完整八章正式规划书 R${report.sequence} 已生成；历史快照未覆盖。`);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "正式规划书生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function recalculate(trigger: "monthly_review" | "major_event") {
    if (!formalReport) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const report = await recalculateFormalReport(
        experience.household_id,
        actor,
        formalReport,
        trigger,
      );
      setFormalReport(report);
      setMessage(`已创建 R${report.sequence} 新快照；R${formalReport.sequence} 仍可追溯。`);
    } catch (recalculationError) {
      setError(recalculationError instanceof Error ? recalculationError.message : "报告重算失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="正式八章家庭财富规划书">
      <header className="formal-report-control">
        <div>
          <p className="page-kicker">正式报告 · 不可变快照</p>
          <h2>{formalReport ? `当前 R${formalReport.sequence}` : reportUnderReview ? "正式规划书审核中" : "生成完整八章规划书"}</h2>
          <p>财务、规划、组合、数字孪生与行动数字只来自确定性工具；政策事实只来自受控引用。</p>
        </div>
        <div className="formal-report-control-actions">
          {!formalReport && !reportUnderReview ? <Button type="button" loading={busy} disabled={loadingFormal} onClick={() => void generate()}>生成完整八章规划书</Button> : null}
          {formalReport ? <Button type="button" variant="secondary" loading={busy} onClick={() => void recalculate("monthly_review")}>月度复盘新快照</Button> : null}
          {formalReport ? <Button type="button" variant="secondary" loading={busy} onClick={() => void recalculate("major_event")}>重大事件后重算</Button> : null}
        </div>
      </header>
      {loadingFormal ? <p className="formal-report-state" role="status">正在核对当前报告快照与八章结构…</p> : null}
      {message ? <p className="formal-report-state" data-tone="success" role="status">{message}</p> : null}
      {error ? <p className="formal-report-state" data-tone="warning" role="status">{error}</p> : null}
      {formalReport ? (
        <FormalReportReader report={formalReport} />
      ) : (
        <PreviewReport experience={experience} onNavigate={onNavigate} />
      )}
    </section>
  );
}

function FormalReportReader({ report }: { report: FormalReport }) {
  const [chapterNumber, setChapterNumber] = useState(1);
  const chapter = report.chapters.find((item) => item.number === chapterNumber) ?? report.chapters[0];
  const citationMap = useMemo(
    () => new Map(report.citations.map((item) => [item.citation_id, item])),
    [report.citations],
  );
  if (!chapter) {
    return <section className="client-inline-state" role="alert"><h2>规划书生成失败</h2><p>正式报告没有通过八章结构校验。</p></section>;
  }
  const statusLabel = report.status === "client_ready"
    ? "已关联人工审核链"
    : report.status === "workflow_linked"
      ? "方案审核中"
      : "待人工复核";
  return (
    <section className="report-workspace formal-report-reader" aria-labelledby="client-view-heading">
      <header className="report-cover">
        <div>
          <p className="page-kicker">家庭规划书 · 正式八章 · R{report.sequence}</p>
          <h2 id="client-view-heading" tabIndex={-1}>{report.title}</h2>
          <p>{report.subtitle}</p>
          <StatusBadge tone={report.status === "client_ready" ? "success" : "warning"}>{statusLabel}</StatusBadge>
        </div>
        <dl>
          <div><dt>一级目录</dt><dd>{report.chapter_count} 章</dd></div>
          <div><dt>数据日</dt><dd>{formatDate(report.data_as_of)}</dd></div>
          <div><dt>生成时间</dt><dd>{formatDateTime(report.generated_at)}</dd></div>
          <div><dt>一致性</dt><dd>{report.consistency_status === "passed" ? "已通过" : "需复核"}</dd></div>
          <div><dt>报告版本</dt><dd>{report.versions.report_version}</dd></div>
          <div><dt>方案版本</dt><dd>{report.versions.workflow_version ?? "未关联"}</dd></div>
          <div><dt>执行进度</dt><dd>{report.execution_metrics.completed}/{report.execution_metrics.total} · {report.execution_metrics.completion_ratio}</dd></div>
          <div><dt>水印</dt><dd>{report.watermark}</dd></div>
        </dl>
        <div className="report-export-actions">
          <a className="button export-link" data-variant="secondary" href={reportExportUrl(report.report_id, "html")} download>下载 HTML</a>
          <a className="button export-link" data-variant="primary" href={reportExportUrl(report.report_id, "pdf")} download>下载 PDF</a>
        </div>
      </header>

      <div className="report-layout">
        <nav className="report-chapter-nav" aria-label="规划书八章">
          <ol>
            {report.chapters.map((item) => (
              <li key={item.number}>
                <button type="button" aria-current={item.number === chapterNumber ? "page" : undefined} onClick={() => setChapterNumber(item.number)}>
                  <span>{String(item.number).padStart(2, "0")}</span>
                  <strong>{item.title}</strong>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <article className="report-chapter formal-report-chapter" aria-live="polite">
          <header><span>第 {chapter.number} 章</span><h3>{chapter.title}</h3></header>
          <p className="report-summary">{chapter.summary}</p>
          {chapter.sections.map((section) => (
            <ReportSectionView key={section.code} section={section} citationMap={citationMap} />
          ))}
        </article>
      </div>
      <aside className="report-boundary-note report-ending">
        <strong>报告结束 · 适用边界</strong><p>{report.boundary_note}</p>
        <small>{report.versions.report_version} · {report.report_hash}</small>
      </aside>
    </section>
  );
}

function ReportSectionView({
  section,
  citationMap,
}: {
  section: FormalReportSection;
  citationMap: Map<string, FormalReport["citations"][number]>;
}) {
  const citations = section.citation_ids
    .map((id) => citationMap.get(id))
    .filter((item): item is FormalReport["citations"][number] => Boolean(item));
  return (
    <section className="formal-report-section">
      <h4><span>{section.code}</span>{section.title}</h4>
      {section.narratives.map((item, index) => <p key={`${section.code}-n-${index}`}>{item}</p>)}
      {section.tables.map((table) => (
        <figure key={`${section.code}-${table.title}`} className="formal-report-table">
          <figcaption>{table.title}</figcaption>
          <div className="data-table-wrap" tabIndex={0} role="region" aria-label={`${table.title}，可横向滚动`}>
            <table className="data-table"><thead><tr>{table.columns.map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>
              {table.rows.length === 0 ? <tr><td colSpan={table.columns.length}>当前没有适用记录；系统未补造数据。</td></tr> : table.rows.map((row, rowIndex) => <tr key={`${table.title}-${rowIndex}`}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}</tr>)}
            </tbody></table>
          </div>
          {table.note ? <p>{table.note}</p> : null}<small>计算来源：{table.calculation_source}</small>
        </figure>
      ))}
      {section.advice.length > 0 ? <div className="formal-advice-list">{section.advice.map((item) => <AdviceView key={item.code} item={item} />)}</div> : null}
      {citations.length > 0 ? <ol className="report-citations">{citations.map((citation) => (
        <li key={citation.citation_id}><strong>{citation.title}</strong><span>{citation.issuing_authority}，版本 {citation.document_version}</span><small>{citation.paragraph_ref} · {citation.citation_id}</small>{safeExternalUrl(citation.source_uri) ? <a href={safeExternalUrl(citation.source_uri) ?? undefined} target="_blank" rel="noopener noreferrer">打开来源入口</a> : <span>本地受控快照</span>}</li>
      ))}</ol> : null}
    </section>
  );
}

function AdviceView({ item }: { item: ReportAdvice }) {
  return (
    <article className="formal-advice" data-status={item.status}>
      <header><span>优先级 {item.priority}</span><strong>{item.title}</strong><StatusBadge tone={item.status === "completed" ? "success" : item.status === "open" ? "warning" : "info"}>{actionStatusLabels[item.status]}</StatusBadge></header>
      <dl><div><dt>原因</dt><dd>{item.reason}</dd></div><div><dt>行动</dt><dd>{item.action}</dd></div><div><dt>完成标准</dt><dd>{item.completion_criteria}</dd></div><div><dt>复盘</dt><dd>{item.review_cycle}{item.due_date ? ` · ${formatDate(item.due_date)}` : ""}</dd></div></dl>
    </article>
  );
}

function PreviewReport({
  experience,
  onNavigate,
}: {
  experience: ClientExperience;
  onNavigate: (view: ClientView) => void;
}) {
  const [chapterNumber, setChapterNumber] = useState(1);
  const chapter = experience.report.chapters.find((item) => item.number === chapterNumber) ?? experience.report.chapters[0];
  if (!chapter) return <section className="client-inline-state" role="alert"><h2>规划书预览失败</h2><p>八章预览结构不完整。</p></section>;
  const citations = experience.report.citations.filter((item) => chapter.citation_ids.includes(item.citation_id));
  return (
    <section className="report-workspace" aria-labelledby="client-view-heading">
      <header className="report-cover">
        <div><p className="page-kicker">家庭规划书 · 阶段九确定性预览</p><h2 id="client-view-heading" tabIndex={-1}>{experience.report.title}</h2><p>{experience.report.subtitle}</p></div>
        <dl><div><dt>一级目录</dt><dd>{experience.report.chapter_count} 章</dd></div><div><dt>数据日</dt><dd>{formatDate(experience.report.data_as_of)}</dd></div><div><dt>计算来源</dt><dd>确定性工具</dd></div><div><dt>版本</dt><dd>{experience.report.report_version}</dd></div></dl>
        <a className="button export-link" data-variant="secondary" href={clientExperienceExportUrl(experience.household_id)} download>下载预览数据包</a>
      </header>
      <div className="report-layout">
        <nav className="report-chapter-nav" aria-label="规划书八章"><ol>{experience.report.chapters.map((item) => <li key={item.number}><button type="button" aria-current={item.number === chapterNumber ? "page" : undefined} onClick={() => setChapterNumber(item.number)}><span>{String(item.number).padStart(2, "0")}</span><strong>{item.title}</strong><StatusBadge tone={previewTone(item.status)}>{item.status === "ready" ? "已生成" : item.status === "pending_twin" ? "待孪生结果" : "需复核"}</StatusBadge></button></li>)}</ol></nav>
        <article className="report-chapter" aria-live="polite"><header><span>第 {chapter.number} 章</span><h3>{chapter.title}</h3></header><p className="report-summary">{chapter.summary}</p><section><h4>计算依据</h4><ol>{chapter.calculation_basis.map((item, index) => <li key={`${chapter.number}-${index}`}>{item}</li>)}</ol></section><section><h4>受控引用</h4>{citations.length === 0 ? <p className="empty-state">本章只引用家庭事实与确定性公式。</p> : <ol className="report-citations">{citations.map((citation) => <li key={citation.citation_id}><strong>{citation.title}</strong><span>{citation.issuing_authority}，版本 {citation.document_version}</span><small>{citation.paragraph_ref} · {citation.citation_id}</small></li>)}</ol>}</section>{chapter.status === "pending_twin" ? <Button type="button" variant="secondary" onClick={() => onNavigate("twin")}>运行数字孪生</Button> : null}</article>
      </div>
      <aside className="report-boundary-note"><strong>预览边界</strong><p>{experience.report.boundary_note}</p></aside>
    </section>
  );
}
