"""개인 할 일 — 제출함 스프레드시트 '개인할일' 탭. 로그인 계정(아이디)별 개인 메모.

캘린더에 안 넣고 본인에게만 보이는 간단 to-do. 앱은 로그인한 uid로 필터해서
본인 것만 보여줌. 컬럼이 바뀌면 TODO_HEADER만 수정(_ws가 헤더 자동 보정).
"""
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

TODO_WS = "개인할일"
TODO_HEADER = ["아이디", "내용", "등록일시"]


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(TODO_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=TODO_WS, rows=200, cols=len(TODO_HEADER))
        ws.append_row(TODO_HEADER)
        return ws
    if ws.col_count < len(TODO_HEADER):
        ws.add_cols(len(TODO_HEADER) - ws.col_count)
    if ws.row_values(1) != TODO_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(TODO_HEADER))
        ws.update(values=[TODO_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=10)
def _rows():
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(TODO_HEADER))[:len(TODO_HEADER)]
        d = dict(zip(TODO_HEADER, r))
        d["_row"] = i
        out.append(d)
    return out


def list_todos(uid):
    """로그인한 본인(uid)의 개인 할 일만."""
    uid = (uid or "").strip()
    if not uid:
        return []
    return [d for d in _rows() if d["아이디"].strip() == uid]


def add_todo(uid, text):
    uid = (uid or "").strip()
    text = (text or "").strip()
    if not uid or not text:
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    _ws().append_row([uid, text, now], value_input_option="RAW")
    _rows.clear()


def delete_todo(uid, row, text):
    """완료 처리(행 삭제). 최신 시트에서 (아이디+내용) 재확인 후 삭제 — 행밀림 방지."""
    uid = (uid or "").strip()
    text = (text or "").strip()
    if not uid or not row:
        return
    ws = _ws()
    vals = ws.get_all_values()
    if 1 <= row - 1 < len(vals):
        r = vals[row - 1]
        if r and r[0].strip() == uid \
                and (len(r) < 2 or r[1].strip() == text):
            ws.delete_rows(row)
            _rows.clear()
