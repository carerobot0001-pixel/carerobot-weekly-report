"""구매요청 — 기존 제출함 스프레드시트의 '구매요청' 탭에 누적 + 엑셀 양식 생성.

별도 시트를 새로 만들지 않고, 업무보고 제출함과 같은 스프레드시트
(secrets [sheet] id)에 '구매요청' 워크시트(탭)를 추가해 쓴다.
그 스프레드시트엔 서비스 계정이 이미 편집자라 추가 공유·secrets가 필요 없다.

한 번의 '구매요청'은 품목 여러 개로 구성되며, 시트에는 품목 1개당 1행으로
저장하고 같은 요청ID로 묶는다. 컬럼 구조가 바뀌면 PURCHASE_HEADER만 맞춘다.
"""
import io
import gspread
import streamlit as st

from sheets_store import _get_client, KST
from datetime import datetime

PURCHASE_WS_TITLE = "구매요청"
PURCHASE_HEADER = ["요청ID", "요청일시", "요청자", "품명", "품목(상세)", "단가",
                   "수량", "합계", "구매사유", "비고(구매처)"]

# 엑셀 양식(첨부 구매요청서)과 동일한 컬럼 순서
XLSX_HEADER = ["연번", "품명", "품목", "단가", "수량", "합계", "구매사유", "비고(구매처)"]


@st.cache_resource
def _ws():
    """제출함 스프레드시트의 '구매요청' 탭 핸들 (없으면 생성)."""
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        return ss.worksheet(PURCHASE_WS_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=PURCHASE_WS_TITLE, rows=1000,
                              cols=len(PURCHASE_HEADER))
        ws.append_row(PURCHASE_HEADER)
        return ws


@st.cache_data(ttl=60)
def purchase_rows() -> list:
    """저장된 품목 행 목록(헤더 제외) — 헤더 길이에 맞춰 패딩."""
    vals = _ws().get_all_values()
    out = []
    for r in vals[1:]:
        if not any(c.strip() for c in r):
            continue
        out.append((list(r) + [""] * len(PURCHASE_HEADER))[:len(PURCHASE_HEADER)])
    return out


def add_purchase(requester: str, reason: str, items: list) -> tuple:
    """items = [{'품명','품목','단가','수량','비고'}...] 저장.

    반환: (요청ID, 저장된 품목 수, 총액)
    """
    ws = _ws()
    now = datetime.now(KST)
    req_id = now.strftime("%Y%m%d-%H%M%S-") + requester
    ts = now.strftime("%Y-%m-%d %H:%M")
    rows, total = [], 0
    for it in items:
        price = int(it.get("단가") or 0)
        qty = int(it.get("수량") or 0)
        subtotal = price * qty
        total += subtotal
        rows.append([req_id, ts, requester, it.get("품명", ""), it.get("품목", ""),
                     price, qty, subtotal, reason, it.get("비고", "")])
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        purchase_rows.clear()
    return req_id, len(rows), total


def build_purchase_xlsx(requester: str, reason: str, items: list) -> bytes:
    """첨부 구매요청서와 같은 양식의 엑셀 파일(bytes) 생성."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="D9E1F2")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center")

    wb = Workbook()
    ws = wb.active
    ws.title = "구매요청서"

    # 제목 + 요청자/일자
    ws.append([f"구매요청서 ({requester})"])
    ws.append([f"요청일자: {datetime.now(KST).strftime('%Y-%m-%d')}"])
    ws.append([])
    ws.append(XLSX_HEADER)
    head_row = ws.max_row
    for c in ws[head_row]:
        c.font = Font(bold=True)
        c.fill = head_fill
        c.alignment = center
        c.border = border

    total = 0
    for i, it in enumerate(items, 1):
        price = int(it.get("단가") or 0)
        qty = int(it.get("수량") or 0)
        subtotal = price * qty
        total += subtotal
        ws.append([i, it.get("품명", ""), it.get("품목", ""), price, qty,
                   subtotal, reason, it.get("비고", "")])
    ws.append(["합계", "", "", "", "", total, "", ""])

    # 본문 스타일 (헤더 다음 행부터 끝까지)
    for row in ws.iter_rows(min_row=head_row + 1, max_row=ws.max_row,
                            min_col=1, max_col=len(XLSX_HEADER)):
        for c in row:
            c.border = border
            if c.column_letter in ("D", "E", "F"):  # 단가/수량/합계
                c.alignment = right
                c.number_format = "#,##0"
            elif c.column_letter in ("C", "G", "H"):
                c.alignment = left
            else:
                c.alignment = center
    # 합계 행 강조
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    ws.cell(row=ws.max_row, column=1).alignment = center

    widths = {"A": 6, "B": 18, "C": 42, "D": 12, "E": 6, "F": 14, "G": 16, "H": 24}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
