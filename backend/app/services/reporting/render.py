# ruff: noqa: E501
from __future__ import annotations

import hashlib
import os
from contextlib import suppress
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.formal_report import FormalReportDocument, ReportAdvice, ReportTable

HTML_RENDERER_VERSION = "formal-report-html-v1.0.0"
PDF_RENDERER_VERSION = "formal-report-pdf-v1.0.0"
INK = colors.HexColor("#16302B")
MUTED = colors.HexColor("#63706C")
TEAL = colors.HexColor("#0F766E")
MINT = colors.HexColor("#DDF3EC")
SAND = colors.HexColor("#F4EFE5")
LINE = colors.HexColor("#CCD8D3")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _citation_link(source_uri: str) -> str:
    parsed = urlsplit(source_uri)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return '<span class="source-local">本地受控快照</span>'
    return (
        f'<a href="{escape(source_uri, quote=True)}" target="_blank" '
        'rel="noopener noreferrer">来源入口</a>'
    )


def _html_table(table: ReportTable) -> str:
    headers = "".join(f'<th scope="col">{escape(item)}</th>' for item in table.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in table.rows
    )
    note = f'<p class="table-note">{escape(table.note)}</p>' if table.note else ""
    return (
        f"<figure><figcaption>{escape(table.title)}</figcaption>"
        f'<div class="table-scroll"><table><thead><tr>{headers}</tr></thead>'
        f"<tbody>{rows}</tbody></table></div>{note}"
        f"<small>计算来源：{escape(table.calculation_source)}</small></figure>"
    )


def _html_advice(item: ReportAdvice) -> str:
    due = item.due_date.isoformat() if item.due_date else "按条件触发"
    return (
        f'<article class="advice" data-status="{escape(item.status)}">'
        f"<header><span>优先级 {item.priority}</span><strong>{escape(item.title)}</strong>"
        f"<em>{escape(item.status)}</em></header>"
        f"<dl><div><dt>原因</dt><dd>{escape(item.reason)}</dd></div>"
        f"<div><dt>行动</dt><dd>{escape(item.action)}</dd></div>"
        f"<div><dt>完成标准</dt><dd>{escape(item.completion_criteria)}</dd></div>"
        f"<div><dt>复盘周期</dt><dd>{escape(item.review_cycle)}</dd></div>"
        f"<div><dt>日期</dt><dd>{escape(due)}</dd></div></dl></article>"
    )


def render_formal_html(document: FormalReportDocument) -> tuple[bytes, dict[str, object]]:
    toc = "".join(
        f'<li><a href="#chapter-{item.number}"><span>{item.number:02d}</span>'
        f"{escape(item.title)}</a></li>"
        for item in document.chapters
    )
    chapters = []
    for chapter in document.chapters:
        sections = []
        for section in chapter.sections:
            narratives = "".join(f"<p>{escape(item)}</p>" for item in section.narratives)
            tables = "".join(_html_table(item) for item in section.tables)
            advice = "".join(_html_advice(item) for item in section.advice)
            citation_note = (
                f'<p class="citation-note">引用：{escape("、".join(section.citation_ids))}</p>'
                if section.citation_ids
                else ""
            )
            sections.append(
                f"<section><h3><span>{escape(section.code)}</span>{escape(section.title)}</h3>"
                f"{narratives}{tables}{advice}{citation_note}</section>"
            )
        chapters.append(
            f'<article class="chapter" id="chapter-{chapter.number}">'
            f"<header><span>第 {chapter.number} 章</span><h2>{escape(chapter.title)}</h2>"
            f"<p>{escape(chapter.summary)}</p></header>{''.join(sections)}</article>"
        )
    appendices = []
    for appendix in document.appendices:
        narratives = "".join(f"<p>{escape(item)}</p>" for item in appendix.narratives)
        tables = "".join(_html_table(item) for item in appendix.tables)
        appendices.append(
            f'<section class="appendix"><h3>附录 {escape(appendix.code)} · '
            f"{escape(appendix.title)}</h3>{narratives}{tables}</section>"
        )
    citations = "".join(
        f'<li id="{escape(item.citation_id)}"><strong>{escape(item.title)}</strong>'
        f"<span>{escape(item.issuing_authority)} · {escape(item.document_version)} · "
        f"生效 {item.effective_date.isoformat()} · 核验 "
        f"{item.last_verified_date.isoformat() if item.last_verified_date else '待核验'}</span>"
        f"<small>{escape(item.paragraph_ref)} · {escape(item.content_hash)}</small>"
        f"{_citation_link(item.source_uri)}</li>"
        for item in document.citations
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(document.title)} · {escape(document.versions.report_version)}</title>
<style>
:root{{--ink:#16302b;--muted:#63706c;--teal:#0f766e;--mint:#ddf3ec;--sand:#f4efe5;--line:#ccd8d3;--paper:#fff;}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#edf2ef;color:var(--ink);font:15px/1.72 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
.watermark{{position:fixed;inset:45% auto auto 18%;z-index:0;transform:rotate(-24deg);font-size:56px;font-weight:800;color:rgba(15,118,110,.07);pointer-events:none}}
main{{position:relative;z-index:1;width:min(1180px,calc(100% - 32px));margin:24px auto 80px;background:var(--paper);box-shadow:0 20px 70px rgba(22,48,43,.12)}}
.cover{{min-height:620px;padding:72px;background:linear-gradient(145deg,#16302b,#205a50);color:white;display:grid;align-content:space-between}}
.cover .eyebrow,.chapter>header>span{{letter-spacing:.16em;text-transform:uppercase;font-size:12px}}.cover h1{{font-size:52px;line-height:1.1;margin:12px 0}}.cover p{{max-width:760px;color:#dce9e5}}
.cover dl{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.cover dl div{{border-top:1px solid rgba(255,255,255,.3);padding-top:10px}}dt{{color:var(--muted);font-size:12px}}.cover dt{{color:#a9c9c1}}dd{{margin:3px 0 0}}
.toc,.chapter,.appendices,.sources,.report-end{{padding:52px 64px}}.toc ol{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0;list-style:none}}.toc a{{display:flex;gap:16px;padding:14px;border-bottom:1px solid var(--line);color:inherit;text-decoration:none}}.toc a span{{color:var(--teal);font-variant-numeric:tabular-nums}}
.support-title{{font-size:30px;font-weight:760;line-height:1.2;margin:0 0 20px}}
.chapter{{border-top:12px solid var(--sand)}}.chapter>header{{margin-bottom:40px}}.chapter h2{{font-size:36px;margin:5px 0 10px}}.chapter section+section{{margin-top:38px}}h3{{font-size:22px;border-left:4px solid var(--teal);padding-left:12px}}h3 span{{font-size:12px;color:var(--teal);margin-right:10px}}
figure{{margin:24px 0}}figcaption{{font-weight:750;margin-bottom:8px}}.table-scroll{{overflow:auto;border:1px solid var(--line)}}table{{border-collapse:collapse;width:100%;font-size:12px}}th{{background:var(--ink);color:white;text-align:left}}th,td{{padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top}}tbody tr:nth-child(even){{background:#f7faf8}}figure>small,.table-note,.citation-note{{display:block;color:var(--muted);font-size:11px;margin-top:6px}}
.advice{{border:1px solid var(--line);border-left:4px solid var(--teal);padding:16px;margin:12px 0}}.advice header{{display:flex;gap:12px;align-items:center}}.advice header span,.advice header em{{font-size:11px;color:var(--muted)}}.advice header strong{{font-size:17px;flex:1}}.advice dl{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:0}}.advice dl div{{background:#f7faf8;padding:10px}}
.appendices{{border-top:12px solid var(--mint)}}.appendix+.appendix{{margin-top:42px}}.sources ol{{padding-left:20px}}.sources li{{margin:14px 0}}.sources span,.sources small,.sources a{{display:block}}.report-end{{background:var(--ink);color:white}}.report-end p{{color:#dce9e5}}
@media(max-width:760px){{.cover,.toc,.chapter,.appendices,.sources,.report-end{{padding:30px 22px}}.cover h1{{font-size:38px}}.cover dl,.toc ol,.advice dl{{grid-template-columns:1fr}}main{{width:100%;margin:0}}}}
@media print{{body{{background:white}}main{{width:100%;margin:0;box-shadow:none}}.chapter{{break-before:page}}.appendices{{break-before:page}}a{{color:inherit;text-decoration:none}}}}
</style>
</head>
<body><div class="watermark" aria-hidden="true">{escape(document.watermark)}</div><main>
<header class="cover"><div><p class="eyebrow">智运财富 · 普慧金融 · Fortune Copilot</p><h1>{escape(document.title)}</h1><p>{escape(document.subtitle)}</p></div>
<dl><div><dt>报告版本</dt><dd>{escape(document.versions.report_version)}</dd></div><div><dt>数据日</dt><dd>{document.data_as_of}</dd></div><div><dt>生成时间</dt><dd>{document.generated_at.isoformat()}</dd></div><div><dt>一致性</dt><dd>{escape(document.consistency_status)}</dd></div><div><dt>报告哈希</dt><dd>{escape(document.report_hash[:16])}</dd></div><div><dt>方案工作流</dt><dd>{escape(document.versions.workflow_version or "未关联")}</dd></div><div><dt>计算口径</dt><dd>已确认资料与版本化规则</dd></div><div><dt>报告状态</dt><dd>{escape(document.watermark)}</dd></div></dl></header>
<nav class="toc" aria-label="严格八章目录"><p class="support-title">目录</p><ol>{toc}</ol></nav>
{"".join(chapters)}
<section class="appendices"><p class="support-title">附录（不改变八章一级目录）</p>{"".join(appendices)}</section>
<section class="sources"><p class="support-title">受控引用索引</p><ol>{citations}</ol></section>
<footer class="report-end"><strong>报告结束 · 适用边界</strong><p>{escape(document.boundary_note)}</p><small>{escape(document.watermark)} · {escape(document.versions.report_version)} · {escape(document.report_hash)}</small></footer>
</main></body></html>"""
    payload = html.encode("utf-8")
    return payload, {
        "renderer_version": HTML_RENDERER_VERSION,
        "bytes": len(payload),
        "sha256": _hash(payload),
        "self_contained": True,
        "external_assets": 0,
    }


def _font_candidates() -> list[Path]:
    configured = os.getenv("REPORT_FONT_PATH")
    candidates = [
        Path(configured) if configured else None,
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
    ]
    return [item for item in candidates if item is not None and item.is_file()]


def _register_font() -> tuple[str, str]:
    font_name = "FortuneCopilotCJK"
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name, "already_registered_system_font"
    errors: list[str] = []
    for path in _font_candidates():
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(path), subfontIndex=0))
            return font_name, str(path)
        except Exception as exc:  # pragma: no cover - platform-specific font parser
            errors.append(f"{path.name}:{type(exc).__name__}")
    raise RuntimeError(
        "No usable system/open-license CJK font found; set REPORT_FONT_PATH. " + ",".join(errors)
    )


def _paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _pdf_table(
    table: ReportTable,
    body_style: ParagraphStyle,
    header_style: ParagraphStyle,
    available_width: float,
) -> Table:
    data = [
        [_paragraph(item, header_style) for item in table.columns],
        *[[_paragraph(item, body_style) for item in row] for row in table.rows],
    ]
    column_width = available_width / max(len(table.columns), 1)
    result = Table(
        data,
        colWidths=[column_width] * len(table.columns),
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SAND]),
            ]
        )
    )
    return result


def render_formal_pdf(document: FormalReportDocument) -> tuple[bytes, dict[str, object]]:
    font_name, font_path = _register_font()
    output = BytesIO()
    page_size = landscape(A4)
    margin = 16 * mm
    available_width = page_size[0] - (2 * margin)
    styles = getSampleStyleSheet()
    cover_style = ParagraphStyle(
        "CoverCJK",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=31,
        leading=40,
        textColor=colors.white,
        alignment=TA_LEFT,
        wordWrap="CJK",
        spaceAfter=15,
    )
    chapter_style = ParagraphStyle(
        "ChapterCJK",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=23,
        leading=30,
        textColor=INK,
        wordWrap="CJK",
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "SectionCJK",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        leading=20,
        textColor=TEAL,
        wordWrap="CJK",
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCJK",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8.6,
        leading=13,
        textColor=INK,
        wordWrap="CJK",
        spaceAfter=5,
    )
    table_style = ParagraphStyle(
        "TableCJK",
        parent=body_style,
        fontSize=6.4,
        leading=9,
        spaceAfter=0,
    )
    table_header_style = ParagraphStyle(
        "TableHeaderCJK",
        parent=table_style,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    small_style = ParagraphStyle(
        "SmallCJK",
        parent=body_style,
        fontSize=6.8,
        leading=10,
        textColor=MUTED,
    )
    cover_body_style = ParagraphStyle(
        "CoverBodyCJK",
        parent=body_style,
        fontSize=9,
        leading=14,
        textColor=colors.white,
    )
    cover_small_style = ParagraphStyle(
        "CoverSmallCJK",
        parent=small_style,
        textColor=colors.HexColor("#DCE9E5"),
    )

    def on_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 9 * mm, document.versions.report_version)
        footer = f"数据日 {document.data_as_of} · 第 {doc.page} 页 · {document.report_hash[:12]}"
        canvas.drawRightString(page_size[0] - margin, 9 * mm, footer)
        with suppress(AttributeError):
            canvas.setFillAlpha(0.055)
        canvas.setFillColor(TEAL)
        canvas.setFont(font_name, 27)
        canvas.translate(page_size[0] / 2, page_size[1] / 2)
        canvas.rotate(24)
        canvas.drawCentredString(0, 0, document.watermark)
        canvas.restoreState()

    frame = Frame(
        margin,
        15 * mm,
        available_width,
        page_size[1] - (30 * mm),
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = BaseDocTemplate(
        output,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=document.title,
        author="智运财富 · 普慧金融 · Fortune Copilot",
        subject="八章个人／家庭理财规划书",
    )
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=on_page)])
    story: list[Any] = []
    cover_box = Table(
        [
            [_paragraph("智运财富 · 普慧金融 · Fortune Copilot", cover_small_style)],
            [_paragraph(document.title, cover_style)],
            [_paragraph(document.subtitle, cover_body_style)],
            [
                _paragraph(
                    f"报告 {document.versions.report_version} · 数据日 {document.data_as_of} · "
                    f"生成 {document.generated_at.isoformat()} · {document.watermark}",
                    cover_body_style,
                )
            ],
            [_paragraph(f"报告哈希 {document.report_hash}", cover_small_style)],
        ],
        colWidths=[available_width],
    )
    cover_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), INK),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, 0), 22),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    story.extend([Spacer(1, 35 * mm), cover_box, PageBreak()])
    story.append(_paragraph("严格八章目录", chapter_style))
    for chapter in document.chapters:
        story.append(_paragraph(f"{chapter.number:02d}　{chapter.title}", section_style))
    story.extend(
        [
            Spacer(1, 8 * mm),
            _paragraph("附录不改变八章一级目录。", body_style),
            PageBreak(),
        ]
    )
    for chapter in document.chapters:
        story.append(_paragraph(f"第 {chapter.number} 章　{chapter.title}", chapter_style))
        story.append(_paragraph(chapter.summary, body_style))
        for section in chapter.sections:
            story.append(_paragraph(f"{section.code}　{section.title}", section_style))
            for narrative in section.narratives:
                story.append(_paragraph(narrative, body_style))
            for table in section.tables:
                story.append(_paragraph(table.title, body_style))
                story.append(_pdf_table(table, table_style, table_header_style, available_width))
                if table.note:
                    story.append(_paragraph(table.note, small_style))
                story.append(_paragraph(f"计算来源：{table.calculation_source}", small_style))
                story.append(Spacer(1, 3 * mm))
            for advice in section.advice:
                block: list[Flowable] = [
                    _paragraph(
                        f"优先级 {advice.priority} · {advice.title} · 状态 {advice.status}",
                        section_style,
                    ),
                    _paragraph(f"原因：{advice.reason}", body_style),
                    _paragraph(f"行动：{advice.action}", body_style),
                    _paragraph(f"完成标准：{advice.completion_criteria}", body_style),
                    _paragraph(
                        f"复盘：{advice.review_cycle} · "
                        f"{advice.due_date.isoformat() if advice.due_date else '按条件触发'}",
                        body_style,
                    ),
                ]
                story.append(KeepTogether(block))
            if section.citation_ids:
                story.append(
                    _paragraph(f"受控引用：{'、'.join(section.citation_ids)}", small_style)
                )
        story.append(PageBreak())
    story.append(_paragraph("附录（不改变八章一级目录）", chapter_style))
    for appendix in document.appendices:
        story.append(_paragraph(f"附录 {appendix.code}　{appendix.title}", section_style))
        for narrative in appendix.narratives:
            story.append(_paragraph(narrative, body_style))
        for table in appendix.tables:
            story.append(_paragraph(table.title, body_style))
            story.append(_pdf_table(table, table_style, table_header_style, available_width))
            if table.note:
                story.append(_paragraph(table.note, small_style))
            story.append(Spacer(1, 3 * mm))
    story.append(PageBreak())
    story.append(_paragraph("受控引用索引", chapter_style))
    for citation in document.citations:
        story.append(
            _paragraph(
                f"{citation.citation_id} · {citation.title} · {citation.issuing_authority} · "
                f"{citation.document_version} · 发布 {citation.publication_date} · "
                f"生效 {citation.effective_date} · 核验 "
                f"{citation.last_verified_date or '待核验'} · {citation.paragraph_ref}",
                body_style,
            )
        )
        story.append(_paragraph(citation.source_uri, small_style))
    story.extend(
        [
            Spacer(1, 8 * mm),
            _paragraph("报告结束 · 适用边界", chapter_style),
            _paragraph(document.boundary_note, body_style),
            _paragraph(
                f"{document.watermark} · {document.versions.report_version} · "
                f"{document.report_hash}",
                small_style,
            ),
        ]
    )
    doc.build(story)
    payload = output.getvalue()
    return payload, {
        "renderer_version": PDF_RENDERER_VERSION,
        "bytes": len(payload),
        "sha256": _hash(payload),
        "font_name": font_name,
        "font_source": Path(font_path).name,
        "font_bundled_in_repository": False,
        "page_size": "A4-landscape",
    }
