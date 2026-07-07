"""홈 팀 공지사항 — 제출함 스프레드시트의 '공지' 탭. 담당자가 등록/삭제, 전원 열람."""
import gspread
import streamlit as st
from datetime import datetime

from sheets_store import _get_client, KST

NOTICE_WS_TITLE = "공지"
NOTICE_HEADER = ["등록일시", "작성자", "내용"]


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        return ss.worksheet(NOTICE_WS_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=NOTICE_WS_TITLE, rows=100,
                              cols=len(NOTICE_HEADER))
        ws.append_row(NOTICE_HEADER)
        return ws


@st.cache_data(ttl=30)
def notices() -> list:
    """(행번호, [등록일시, 작성자, 내용]) 목록."""
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        out.append((i, (list(r) + ["", "", ""])[:3]))
    return out


def add_notice(author: str, text: str) -> None:
    ws = _ws()
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    ws.append_row([ts, author, text], value_input_option="USER_ENTERED")
    notices.clear()


def delete_notice(row_idx: int, expected_ts: str) -> None:
    ws = _ws()
    cur = ws.row_values(row_idx)
    if (cur[0].strip() if cur else "") != expected_ts.strip():
        raise RuntimeError("공지 행이 바뀌었습니다.")
    ws.delete_rows(row_idx)
    notices.clear()
