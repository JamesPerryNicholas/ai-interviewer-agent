"""Generate downloadable Chinese PDF reports with ReportLab."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.evaluation import EvaluationReportResponse


PDF_FONT = "STSong-Light"


def generate_report_pdf(
    *,
    report: EvaluationReportResponse,
    username: str,
    position: str,
    created_at: datetime | None,
) -> bytes:
    """Render the complete report, including hidden per-answer analysis."""

    pdfmetrics.registerFont(UnicodeCIDFont(PDF_FONT))
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AI面试评分报告",
        author="AI Interview Agent",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName=PDF_FONT, fontSize=23, leading=31, alignment=TA_CENTER, textColor=colors.HexColor("#24213a"))
    subtitle = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontName=PDF_FONT, fontSize=10, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#777386"))
    heading = ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontName=PDF_FONT, fontSize=15, leading=22, spaceBefore=12, spaceAfter=8, textColor=colors.HexColor("#302b4a"))
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName=PDF_FONT, fontSize=10, leading=17, textColor=colors.HexColor("#565263"), spaceAfter=5)
    small = ParagraphStyle("ReportSmall", parent=body, fontSize=9, leading=15, textColor=colors.HexColor("#777386"))
    score = ParagraphStyle("ReportScore", parent=body, fontSize=17, leading=24, textColor=colors.HexColor("#6d5dfc"), alignment=TA_CENTER)

    created_text = (created_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    story = [
        Paragraph("AI面试评分报告", title),
        Spacer(1, 3 * mm),
        Paragraph(f"候选人：{escape(username)}　　面试岗位：{escape(position or '技术岗位')}", subtitle),
        Paragraph(f"生成时间：{created_text}", subtitle),
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#e3e0ed")),
        Spacer(1, 5 * mm),
    ]

    score_table = Table(
        [
            [Paragraph("综合评分", small), Paragraph("技术能力", small), Paragraph("沟通表达", small)],
            [Paragraph(f"{report.total_score} / 100", score), Paragraph(f"{report.technical_score} / 100", score), Paragraph(f"{report.communication_score} / 100", score)],
        ],
        colWidths=[55 * mm, 55 * mm, 55 * mm],
    )
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#faf9ff")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#e5e1f3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e1f3")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([score_table, Spacer(1, 5 * mm)])

    def add_list_section(title_text: str, items: list[str]) -> None:
        story.append(Paragraph(title_text, heading))
        if items:
            story.extend(Paragraph(f"- {escape(item)}", body) for item in items)
        else:
            story.append(Paragraph("暂无记录", body))

    add_list_section("面试表现优点", report.strengths)
    add_list_section("需要改进的方面", report.weaknesses)
    add_list_section("后续学习建议", report.suggestions)

    story.append(Paragraph("逐题回答分析", heading))
    if report.answers:
        for index, answer in enumerate(report.answers, start=1):
            story.append(Paragraph(f"第{index}题　得分：{answer.score if answer.score is not None else '待评估'} / 100", body))
            if answer.question:
                story.append(Paragraph(f"面试官问题：{escape(answer.question)}", small))
            story.append(Paragraph(f"候选人回答：{escape(answer.answer)}", small))
            if answer.analysis:
                story.append(Paragraph(f"AI分析：{escape(answer.analysis)}", small))
            story.extend([Spacer(1, 2 * mm), HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#eceaf2"))])
    else:
        story.append(Paragraph("暂无逐题分析", body))

    def draw_footer(canvas, doc) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setFont(PDF_FONT, 8)
        canvas.setFillColor(colors.HexColor("#9995a5"))
        canvas.drawString(18 * mm, 10 * mm, "AI Interview Agent")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()
