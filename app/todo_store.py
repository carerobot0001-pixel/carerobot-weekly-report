"""개인 할 일 — 제출함 스프레드시트 '개인할일' 탭. 로그인 계정(아이디)별 개인 메모.

캘린더에 안 넣고 본인에게만 보이는 간단 to-do. 앱은 로그인한 uid로 필터해서
본인 것만 보여줌. 컬럼이 바뀌면 TODO_HEADER만 수정(_ws가 헤더 자동 보정).
"""
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

TODO_WS = "개인할일"
# '구분'은 맨 뒤에 둠 — 옛 3열 행(구분 없음)은 기본 '할일'로 처리(데이터 안 밀림).
TODO_HEADER = ["아이디", "내용", "등록일시", "구분"]
KIND_TODO, KIND_CARE = "할일", "챙길것"      # 할일=업무, 챙길것=오늘 챙길 것
KIND_PERSONAL = "개인"                        # 개인 할 일(업무와 분리해서 표시)
KIND_DONE = "완료"                            # 완료 처리된 업무 할 일(업무보고 실적 반영용)
# 자동 가져오기 진행지점 기록용(화면엔 안 보임 — list_todos가 구분으로 걸러냄).
# 이걸 두는 이유: 이미 가져온 걸 또 넣지 않기 위해서. 특히 사용자가 ✓로 지운
# 항목이 자동 가져오기 때문에 되살아나는 것을 막는다.
KIND_SYNC = "_sync"


def get_sync(uid, key):
    """uid의 key 진행지점 값(없으면 '')."""
    uid = (uid or "").strip()
    pre = f"{key}="
    for d in _rows():
        if d["아이디"].strip() == uid and d.get("구분", "").strip() == KIND_SYNC:
            c = (d.get("내용", "") or "").strip()
            if c.startswith(pre):
                return c[len(pre):]
    return ""


def set_sync(uid, key, value):
    """uid의 key 진행지점 저장(있으면 갱신, 없으면 추가)."""
    uid = (uid or "").strip()
    if not uid:
        return
    ws = _ws()
    pre = f"{key}="
    vals = ws.get_all_values()
    for i, r in enumerate(vals[1:], start=2):
        r = (list(r) + [""] * len(TODO_HEADER))[:len(TODO_HEADER)]
        if r[0].strip() == uid and r[3].strip() == KIND_SYNC \
                and (r[1] or "").strip().startswith(pre):
            ws.update_cell(i, 2, f"{key}={value}")
            _rows.clear()
            return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    ws.append_row([uid, f"{key}={value}", now, KIND_SYNC],
                  value_input_option="RAW")
    _rows.clear()


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


def list_todos(uid, kind=KIND_TODO):
    """로그인한 본인(uid)의 개인 항목만(구분별). 구분 빈칸=옛 데이터=할일로 취급."""
    uid = (uid or "").strip()
    if not uid:
        return []
    out = []
    for d in _rows():
        if d["아이디"].strip() != uid:
            continue
        k = d.get("구분", "").strip() or KIND_TODO
        if k == kind:
            out.append(d)
    return out


def add_todo(uid, text, kind=KIND_TODO):
    uid = (uid or "").strip()
    text = (text or "").strip()
    if not uid or not text:
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    _ws().append_row([uid, text, now, kind], value_input_option="RAW")
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


def complete_todo(uid, row, text):
    """업무 할 일 '완료' — 완료 기록(구분=완료, 등록일시=완료시각)을 남기고 활성 행 삭제.
    나중에 업무보고 '업무실적'에 그 주기 완료분을 불러오기 위함. (개인/챙길것은 그냥
    delete_todo — 실적 반영 대상 아님.) 행밀림 방지로 (아이디+내용) 재확인 후 처리."""
    uid = (uid or "").strip()
    text = (text or "").strip()
    if not uid or not row:
        return
    ws = _ws()
    vals = ws.get_all_values()
    if not (1 <= row - 1 < len(vals)):
        return
    r = vals[row - 1]
    if not (r and r[0].strip() == uid and (len(r) < 2 or r[1].strip() == text)):
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    ws.append_row([uid, text, now, KIND_DONE], value_input_option="RAW")  # 끝에 기록
    ws.delete_rows(row)                                                   # 활성 행 제거
    _rows.clear()


def set_kind(uid, row, text, kind):
    """할 일의 구분 변경(업무 ↔ 개인). 행밀림 방지로 (아이디+내용) 재확인 후 수정.
    개인으로 옮긴 항목은 주간보고에 안 들어간다(보고는 KIND_TODO만 읽음)."""
    uid = (uid or "").strip()
    text = (text or "").strip()
    if not uid or not row or kind not in (KIND_TODO, KIND_PERSONAL, KIND_CARE):
        return
    ws = _ws()
    vals = ws.get_all_values()
    if not (1 <= row - 1 < len(vals)):
        return
    r = vals[row - 1]
    if r and r[0].strip() == uid and (len(r) < 2 or r[1].strip() == text):
        ws.update_cell(row, TODO_HEADER.index("구분") + 1, kind)
        _rows.clear()


def completed_todos(uid, since=None):
    """uid의 완료 기록 목록. since('YYYY-MM-DD') 지정 시 그 날짜 이후 완료분만.
    화면엔 안 뜨는 항목(list_todos는 KIND_DONE을 걸러냄) — 업무보고 작성용."""
    uid = (uid or "").strip()
    if not uid:
        return []
    out = []
    for d in _rows():
        if d["아이디"].strip() != uid:
            continue
        if d.get("구분", "").strip() != KIND_DONE:
            continue
        if since:
            ts = (d.get("등록일시", "") or "")[:10]
            if ts and ts < since:
                continue
        out.append(d)
    return out
