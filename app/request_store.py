"""팀 할 일 '요청' — 제출함 스프레드시트 '팀요청' 탭.

한 사람이 다른 팀원에게 일을 요청하면, 대상자의 홈 '내 할 일'에 '받은 요청'으로
뜨고, 대상자가 완료하면 상태가 바뀌어 요청자가 '보낸 요청'에서 확인한다.
(메일 대신 앱 안에서 확인 — 발송 인프라 불필요.)

대상·요청자는 로그인 계정이 아니라 '이름'으로 다룬다(팀원 명단과 일치). 컬럼이
바뀌면 REQ_HEADER만 수정(_ws가 헤더/열수 자동 보정).
"""
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

REQ_WS = "팀요청"
REQ_HEADER = ["요청ID", "요청자", "대상", "내용", "등록일시", "상태", "완료일시"]
ST_OPEN, ST_DONE = "대기", "완료"


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(REQ_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=REQ_WS, rows=300, cols=len(REQ_HEADER))
        ws.append_row(REQ_HEADER)
        return ws
    if ws.col_count < len(REQ_HEADER):
        ws.add_cols(len(REQ_HEADER) - ws.col_count)
    if ws.row_values(1) != REQ_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(REQ_HEADER))
        ws.update(values=[REQ_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=10)
def _rows():
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(REQ_HEADER))[:len(REQ_HEADER)]
        d = dict(zip(REQ_HEADER, r))
        d["_row"] = i
        out.append(d)
    return out


def add_request(requester, target, text):
    """requester(이름)가 target(이름)에게 text 요청. 요청ID로 행 식별."""
    requester = (requester or "").strip()
    target = (target or "").strip()
    text = (text or "").strip()
    if not requester or not target or not text:
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    req_id = datetime.now(KST).strftime("%Y%m%d-%H%M%S-") + requester
    _ws().append_row([req_id, requester, target, text, now, ST_OPEN, ""],
                     value_input_option="RAW")
    _rows.clear()


def open_for(target):
    """target(이름)에게 온 '대기' 요청들 (오래된 것부터)."""
    target = (target or "").strip()
    if not target:
        return []
    return [d for d in _rows()
            if d["대상"].strip() == target and d["상태"].strip() != ST_DONE]


def sent_by(requester):
    """requester(이름)가 보낸 요청 전체 (최신부터)."""
    requester = (requester or "").strip()
    if not requester:
        return []
    out = [d for d in _rows() if d["요청자"].strip() == requester]
    return list(reversed(out))


def complete_request(req_id, target, text):
    """대상자가 완료 처리 — 상태=완료, 완료일시 기록. 행밀림 방지로 요청ID 재확인."""
    req_id = (req_id or "").strip()
    if not req_id:
        return
    ws = _ws()
    vals = ws.get_all_values()
    for i, r in enumerate(vals[1:], start=2):
        r = (list(r) + [""] * len(REQ_HEADER))[:len(REQ_HEADER)]
        if r[0].strip() == req_id:
            now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
            ws.update_cell(i, 6, ST_DONE)   # 상태
            ws.update_cell(i, 7, now)       # 완료일시
            _rows.clear()
            return


def delete_request(req_id, requester):
    """요청자가 자기 요청 삭제 (요청ID+요청자 재확인)."""
    req_id = (req_id or "").strip()
    requester = (requester or "").strip()
    if not req_id:
        return
    ws = _ws()
    vals = ws.get_all_values()
    for i, r in enumerate(vals[1:], start=2):
        r = (list(r) + [""] * len(REQ_HEADER))[:len(REQ_HEADER)]
        if r[0].strip() == req_id and r[1].strip() == requester:
            ws.delete_rows(i)
            _rows.clear()
            return
