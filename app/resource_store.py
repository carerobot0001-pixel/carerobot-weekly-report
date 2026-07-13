"""자료실 — 팀 공용 참고자료·양식 링크 보드. 제출함 스프레드시트 '자료실' 탭.

앱은 파일을 저장하지 않고 **링크만** 관리(구글문서/드라이브/외부 URL 등).
컬럼이 바뀌면 RES_HEADER만 맞추면 됨(_ws가 헤더 자동 보정).
"""
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

RES_WS = "자료실"
RES_HEADER = ["등록일시", "등록자", "분류", "제목", "링크", "설명"]
CATEGORIES = ["양식", "참고자료", "매뉴얼/가이드", "규정/공문", "기타"]


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(RES_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=RES_WS, rows=300, cols=len(RES_HEADER))
        ws.append_row(RES_HEADER)
        return ws
    if ws.col_count < len(RES_HEADER):
        ws.add_cols(len(RES_HEADER) - ws.col_count)
    if ws.row_values(1) != RES_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(RES_HEADER))
        ws.update(values=[RES_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=15)
def _rows():
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(RES_HEADER))[:len(RES_HEADER)]
        d = dict(zip(RES_HEADER, r))
        d["_row"] = i
        out.append(d)
    return out


def list_resources():
    return _rows()


def add_resource(user, category, title, link, desc):
    title = (title or "").strip()
    link = (link or "").strip()
    if not title or not link:
        raise ValueError("제목과 링크는 필수입니다.")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    _ws().append_row(
        [now, (user or "").strip(), (category or "").strip(), title, link,
         (desc or "").strip()],
        value_input_option="RAW")
    _rows.clear()


def delete_resource(row, title):
    """행 삭제. 최신 시트에서 (행·제목) 재확인 후 삭제 — 행밀림 방지."""
    if not row:
        return
    ws = _ws()
    vals = ws.get_all_values()
    ti = RES_HEADER.index("제목")
    if 1 <= row - 1 < len(vals):
        r = vals[row - 1]
        if len(r) > ti and r[ti].strip() == (title or "").strip():
            ws.delete_rows(row)
            _rows.clear()
