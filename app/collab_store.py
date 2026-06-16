"""문서 협업 보드 — 구글 문서 링크 + 요청사항 + 제출현황을 시트에 누적.

파일을 앱이 저장하지 않는다(서비스 계정은 드라이브 저장 불가). 실제 문서는
요청자가 만든 구글 시트/문서/슬라이드에 있고, 앱은 그 '링크 + 요청 + 현황'만
기존 제출함 스프레드시트의 '문서협업' 탭에 텍스트로 관리한다.
컬럼이 바뀌면 COLLAB_HEADER만 맞추면 된다.
"""
import gspread
import streamlit as st
from datetime import datetime

from sheets_store import _get_client, KST

COLLAB_WS_TITLE = "문서협업"
COLLAB_HEADER = ["요청ID", "등록일시", "요청자", "제목", "요청사항", "문서링크",
                 "마감일", "담당자", "완료자", "상태"]

STATUS_OPEN = "진행중"
STATUS_CLOSED = "완료"


class RequestNotFound(Exception):
    """해당 요청ID의 행을 시트에서 찾지 못함."""


@st.cache_resource
def _ws():
    """제출함 스프레드시트의 '문서협업' 탭 (없으면 생성, 헤더 자동 보정)."""
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(COLLAB_WS_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=COLLAB_WS_TITLE, rows=1000,
                              cols=len(COLLAB_HEADER))
        ws.append_row(COLLAB_HEADER)
        return ws
    if ws.col_count < len(COLLAB_HEADER):
        ws.add_cols(len(COLLAB_HEADER) - ws.col_count)
    if ws.row_values(1) != COLLAB_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(COLLAB_HEADER))
        ws.update(values=[COLLAB_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=60)
def collab_rows() -> list:
    vals = _ws().get_all_values()
    out = []
    for r in vals[1:]:
        if not any(c.strip() for c in r):
            continue
        out.append((list(r) + [""] * len(COLLAB_HEADER))[:len(COLLAB_HEADER)])
    return out


def add_collab(requester: str, title: str, request_text: str, link: str,
               deadline: str, assignees: list) -> str:
    ws = _ws()
    now = datetime.now(KST)
    req_id = now.strftime("%Y%m%d-%H%M%S-") + requester
    row = [req_id, now.strftime("%Y-%m-%d %H:%M"), requester, title, request_text,
           link, deadline, ", ".join(assignees) if assignees else "전체",
           "", STATUS_OPEN]
    ws.append_row(row, value_input_option="USER_ENTERED")
    collab_rows.clear()
    return req_id


def _find_row(ws, req_id: str):
    for i, r in enumerate(ws.get_all_values(), start=1):
        if i > 1 and r and r[0] == req_id:
            return i, r
    raise RequestNotFound(req_id)


def mark_done(req_id: str, member: str) -> list:
    """'완료자'(I열)에 member 추가 (중복 방지). 반환: 완료자 목록."""
    ws = _ws()
    i, r = _find_row(ws, req_id)
    cur = (r[8] if len(r) > 8 else "").strip()
    names = [n.strip() for n in cur.split(",") if n.strip()]
    if member not in names:
        names.append(member)
    ws.update_cell(i, 9, ", ".join(names))  # I열 = 완료자
    collab_rows.clear()
    return names


def set_status(req_id: str, status: str) -> None:
    """상태(J열)를 진행중/완료로 변경."""
    ws = _ws()
    i, _ = _find_row(ws, req_id)
    ws.update_cell(i, 10, status)  # J열 = 상태
    collab_rows.clear()
