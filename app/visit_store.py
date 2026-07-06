"""실증 방문 일지 — 제출함 스프레드시트의 '방문일지' 탭.

현장(가정·복지관·병원) 방문 기록을 실증(연구)별로 축적. 등록/조회/필터/삭제.
컬럼이 바뀌면 VISIT_HEADER만 수정. _ws()가 헤더 자동 보정.
"""
import gspread
import streamlit as st
from datetime import datetime

from sheets_store import _get_client, KST

VISIT_WS_TITLE = "방문일지"
VISIT_HEADER = ["방문일", "실증", "방문자", "방문내용", "이슈·특이사항", "등록일시"]


class RowMismatch(Exception):
    """삭제 대상 행이 그 사이 바뀜."""


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(VISIT_WS_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=VISIT_WS_TITLE, rows=500,
                              cols=len(VISIT_HEADER))
        ws.append_row(VISIT_HEADER)
        return ws
    if ws.col_count < len(VISIT_HEADER):
        ws.add_cols(len(VISIT_HEADER) - ws.col_count)
    if ws.row_values(1) != VISIT_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(VISIT_HEADER))
        ws.update(values=[VISIT_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=60)
def visit_rows() -> list:
    """(시트 행번호, 패딩된 행) 목록 — 행번호는 삭제 위치 지정용."""
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        out.append((i, (list(r) + [""] * len(VISIT_HEADER))[:len(VISIT_HEADER)]))
    return out


def add_visit(visit_date: str, site: str, visitor: str, content: str,
              issue: str) -> None:
    ws = _ws()
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([visit_date, site, visitor, content, issue, ts],
                  value_input_option="USER_ENTERED")
    visit_rows.clear()


def delete_visit(row_idx: int, expected_ts: str) -> None:
    """등록일시(F열)를 재확인해 밀림 방지 후 해당 행 삭제."""
    ws = _ws()
    cur = ws.row_values(row_idx)
    cur_ts = cur[5].strip() if len(cur) > 5 else ""
    if cur_ts != expected_ts.strip():
        raise RowMismatch(f"{row_idx}행 등록일시 불일치")
    ws.delete_rows(row_idx)
    visit_rows.clear()
