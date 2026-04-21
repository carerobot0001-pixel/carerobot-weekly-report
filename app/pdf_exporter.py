"""10명 제출 내용을 원본 HWPX 양식과 동일한 구조의 PDF로 렌더링.

원본 04.24 HWPX 레이아웃 복제:
  Page 1: 사업단 공통확인사항 1 (정지수, 1칸)
  Page 2: 사업단 공통확인사항 2 (최혜민, 2칸 실적/계획)
  Page 3-12: 팀원 1명씩 1페이지 (6열 구조 + 획득데이터 병합행)
  Page 13: 스마트돌봄스페이스 + 회의자료 3종
"""
import io
import os
import html
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, blue, whitesmoke, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from team_config import TEAM_MEMBERS

FONT_NAME = "KoreanFont"
_BUNDLED_FONT = Path(__file__).parent / "fonts" / "NanumGothic-Regular.ttf"
_FONT_CANDIDATES = [
    str(_BUNDLED_FONT),
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:\\Windows\\Fonts\\malgun.ttf",
    "C:\\Windows\\Fonts\\NanumGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


def _register_font() -> str:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, path))
                return FONT_NAME
            except Exception:
                continue
    return "Helvetica"


def _escape(s: str) -> str:
    return html.escape(s or "")


def _vtext(text: str, style: ParagraphStyle) -> Paragraph:
    """한글을 한 글자씩 세로로 쌓아서 표시 (세로 레이블용)."""
    chars = [c for c in text if c.strip()]
    return Paragraph("<br/>".join(_escape(c) for c in chars), style)


def _body(text: str, style: ParagraphStyle,
          acquired_prefix: str = "") -> Paragraph:
    """본문 셀: 줄바꿈을 <br/>로, acquired_prefix 있으면 파란색 prefix."""
    lines = (text or "").split("\n")
    body_html = "<br/>".join(_escape(l) for l in lines)
    if acquired_prefix:
        pre_lines = acquired_prefix.split("\n")
        pre_html = "<br/>".join(_escape(l) for l in pre_lines)
        full_html = f'<font color="#0000FF"><b>{pre_html}</b></font>'
        if body_html.strip():
            full_html += f'<br/>{body_html}'
        return Paragraph(full_html, style)
    return Paragraph(body_html, style)


def build_pdf(submissions: dict, title_date: str,
              period_start: str, period_end: str,
              plan_start: str, plan_end: str) -> bytes:
    font = _register_font()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm,
        topMargin=12*mm, bottomMargin=10*mm,
        title=f"돌봄로봇 주간 업무보고 ({title_date})",
    )

    # 스타일
    title_style = ParagraphStyle(
        "title", fontName=font, fontSize=14, leading=18,
        alignment=1, spaceAfter=4, textColor=black,
    )
    vtext_style = ParagraphStyle(
        "vtext", fontName=font, fontSize=10, leading=12,
        alignment=1, textColor=black,
    )
    header_style = ParagraphStyle(
        "header", fontName=font, fontSize=10, leading=13,
        alignment=1, textColor=black,
    )
    body_style = ParagraphStyle(
        "body", fontName=font, fontSize=9, leading=12,
        alignment=0, textColor=black,
    )

    def page_title():
        return Paragraph(f"<u>과업별 업무 보고 ({title_date})</u>", title_style)

    period_header = f"업무 실적({period_start} ~ {period_end})"
    plan_header = f"업무 계획({plan_start} ~ {plan_end})"

    story = []

    # ─── Page 1: 사업단 공통확인사항 1 (정지수) ───────────
    story.append(page_title())
    jjs = submissions.get("정지수", {})
    pc1_rows = [[
        _vtext("사업단공통확인사항1", vtext_style),
        _body(jjs.get("project_confirmation_1", ""), body_style),
    ]]
    pc1_tbl = Table(pc1_rows, colWidths=[40*mm, 237*mm], rowHeights=[170*mm])
    pc1_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, black),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (1, 0), (1, 0), 8),
    ]))
    story.append(pc1_tbl)
    story.append(PageBreak())

    # ─── Page 2: 사업단 공통확인사항 2 (최혜민) ───────────
    story.append(page_title())
    chm = submissions.get("최혜민", {})
    pc2_rows = [
        [
            "",
            Paragraph(f"<b>{period_header}</b>", header_style),
            Paragraph(f"<b>{plan_header}</b>", header_style),
        ],
        [
            _vtext("사업단공통확인사항2", vtext_style),
            _body(chm.get("project_confirmation_2_done", ""), body_style),
            _body(chm.get("project_confirmation_2_plan", ""), body_style),
        ],
    ]
    pc2_tbl = Table(pc2_rows, colWidths=[40*mm, 118.5*mm, 118.5*mm],
                    rowHeights=[10*mm, 160*mm])
    pc2_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, black),
        ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (1, 0), (-1, 0), whitesmoke),
        ("VALIGN", (0, 0), (0, 1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (1, 1), (-1, 1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (1, 1), (-1, 1), 6),
    ]))
    story.append(pc2_tbl)
    story.append(PageBreak())

    # ─── Page 3-12: 팀원 1명씩 1페이지 ─────────────────
    col_widths = [12*mm, 14*mm, 14*mm, 12*mm, 115*mm, 110*mm]
    header_row = [
        Paragraph("<b>구분</b>", header_style), "", "", "",
        Paragraph(f"<b>{period_header}</b>", header_style),
        Paragraph(f"<b>{plan_header}</b>", header_style),
    ]

    for m in TEAM_MEMBERS:
        data = submissions.get(m["name"], {})
        story.append(_build_member_table(
            m, data, font, header_row, col_widths,
            vtext_style, header_style, body_style,
        ))
        story.append(PageBreak())

    # ─── 마지막 페이지: 스마트돌봄스페이스 + 회의자료 3종 ───
    bjs = submissions.get("백정은", {})
    chm = submissions.get("최혜민", {})
    bottom_rows = [
        header_row,
        [_vtext("스마트돌봄스페이스", vtext_style), "", "", "",
         _body(bjs.get("smart_care_space_done", ""), body_style),
         _body(bjs.get("smart_care_space_plan", ""), body_style)],
        [_vtext("1.연구소회의자료(소장주재회의)", vtext_style), "", "", "",
         _body(chm.get("research_meeting", ""), body_style), ""],
        [_vtext("2.원장+재활원주요간부회의자료(주간현안보고)", vtext_style),
         "", "", "",
         _body(chm.get("director_meeting", ""), body_style), ""],
        [_vtext("3.복지부본부주간일정_보산진보고(의료기기R&D주간일정)",
                vtext_style), "", "", "",
         _body(chm.get("mohw_weekly", ""), body_style), ""],
    ]
    bottom_col_widths = [32*mm, 0*mm, 0*mm, 0*mm, 120*mm, 125*mm]
    # col 1,2,3 폭 0으로 만들어서 실질 3열 레이아웃 (하지만 main과 스타일 일관성 위해 형식 유지)

    # 간편하게 새로 3열 테이블로
    bottom_rows_simple = [
        [Paragraph("<b>구분</b>", header_style),
         Paragraph(f"<b>{period_header}</b>", header_style),
         Paragraph(f"<b>{plan_header}</b>", header_style)],
        [_vtext("스마트돌봄스페이스", vtext_style),
         _body(bjs.get("smart_care_space_done", ""), body_style),
         _body(bjs.get("smart_care_space_plan", ""), body_style)],
        [_vtext("1.연구소회의자료(소장주재회의)", vtext_style),
         _body(chm.get("research_meeting", ""), body_style), ""],
        [_vtext("2.원장+재활원주요간부회의자료(주간현안보고)", vtext_style),
         _body(chm.get("director_meeting", ""), body_style), ""],
        [_vtext("3.복지부본부주간일정_보산진보고(의료기기R&D주간일정)", vtext_style),
         _body(chm.get("mohw_weekly", ""), body_style), ""],
    ]
    story.append(page_title())
    bottom_tbl = Table(bottom_rows_simple,
                       colWidths=[40*mm, 118.5*mm, 118.5*mm],
                       rowHeights=[10*mm, 32*mm, 32*mm, 32*mm, 50*mm])
    bottom_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, black),
        ("BACKGROUND", (0, 0), (-1, 0), whitesmoke),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("VALIGN", (0, 1), (0, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("VALIGN", (1, 1), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (1, 1), (-1, -1), 4),
    ]))
    story.append(bottom_tbl)

    doc.build(story)
    return buf.getvalue()


def _build_member_table(member, data, font, header_row, col_widths,
                        vtext_style, header_style, body_style) -> Table:
    """팀원 1명의 한 페이지짜리 테이블을 반환."""
    cat1 = member["category1"]
    cat2 = member["category2"]
    name = member["name"]

    if member["has_research"]:
        # 4행: [header][획득데이터][연구실적/계획][업무실적/계획]
        acquired = data.get("acquired_data", "")
        research_done_cell = _body(data.get("research_done", ""), body_style)
        research_plan_cell = _body(data.get("research_plan", ""), body_style)
        task_done_cell = _body(data.get("task_done", ""), body_style)
        task_plan_cell = _body(data.get("task_plan", ""), body_style)

        acquired_html = f'<font color="#0000FF"><b>획득 데이터:</b> {_escape(acquired)}</font>'
        acquired_cell = Paragraph(acquired_html, body_style)

        rows = [
            header_row,  # row 0
            # row 1: 획득 데이터 행 (c4~c5 병합)
            [_vtext(cat1, vtext_style), _vtext(cat2, vtext_style),
             _vtext(name, vtext_style), _vtext("연구", vtext_style),
             acquired_cell, ""],
            # row 2: 연구 실적/계획 행 (c0~c3 span 유지)
            ["", "", "", "", research_done_cell, research_plan_cell],
            # row 3: 업무 행 (c3만 새로, c0~c2 span 유지)
            ["", "", "", _vtext("업무", vtext_style),
             task_done_cell, task_plan_cell],
        ]
        spans = [
            ("SPAN", (0, 0), (3, 0)),      # "구분" 헤더
            ("SPAN", (0, 1), (0, 3)),      # 과제 3행
            ("SPAN", (1, 1), (1, 3)),      # 분야 3행
            ("SPAN", (2, 1), (2, 3)),      # 이름 3행
            ("SPAN", (3, 1), (3, 2)),      # 연구 2행 (획득+연구본문)
            ("SPAN", (4, 1), (5, 1)),      # 획득데이터 c4+c5
        ]
        row_heights = [10*mm, 18*mm, 72*mm, 85*mm]
    else:
        # 2행: [header][업무 행]
        task_done_cell = _body(data.get("task_done", ""), body_style)
        task_plan_cell = _body(data.get("task_plan", ""), body_style)
        rows = [
            header_row,
            [_vtext(cat1, vtext_style), _vtext(cat2, vtext_style),
             _vtext(name, vtext_style), _vtext("업무", vtext_style),
             task_done_cell, task_plan_cell],
        ]
        spans = [("SPAN", (0, 0), (3, 0))]
        row_heights = [10*mm, 170*mm]

    tbl = Table(rows, colWidths=col_widths, rowHeights=row_heights)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.5, black),
        ("BACKGROUND", (0, 0), (-1, 0), whitesmoke),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("VALIGN", (0, 1), (3, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (3, -1), "CENTER"),
        ("VALIGN", (4, 1), (5, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (4, 1), (5, -1), 4),
        *spans,
    ]))
    return tbl
