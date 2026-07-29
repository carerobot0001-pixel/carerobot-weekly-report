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
# '링크'는 맨 뒤에 둠 — 옛 7열 행(링크 없음)도 그대로 읽힘(데이터 안 밀림).
REQ_HEADER = ["요청ID", "요청자", "대상", "내용", "등록일시", "상태", "완료일시",
              "링크", "회신", "확인"]
_COL_STATUS = REQ_HEADER.index("상태") + 1        # 상태 열(1-indexed)
_COL_DONE_AT = REQ_HEADER.index("완료일시") + 1   # 완료일시 열
_COL_REPLY = REQ_HEADER.index("회신") + 1         # 대상자가 남긴 한 줄 답
_COL_ACK = REQ_HEADER.index("확인") + 1           # 요청자가 결과를 확인한 시각
_COL_TEXT = REQ_HEADER.index("내용") + 1
_COL_LINK = REQ_HEADER.index("링크") + 1
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


def add_request(requester, target, text, link=""):
    """requester(이름)가 target(이름) 한 명에게 요청. 여러 명은 add_requests 사용."""
    add_requests(requester, [target], text, link)


def add_requests(requester, targets, text, link=""):
    """여러 명에게 같은 요청을 보냄 — 사람마다 한 행(각자 따로 완료·회신하므로).
    요청ID에 대상 이름을 넣어 같은 초에 만들어도 겹치지 않게 한다."""
    requester = (requester or "").strip()
    text = (text or "").strip()
    link = (link or "").strip()
    targets = [t.strip() for t in (targets or []) if (t or "").strip()]
    if not requester or not targets or not text:
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    stamp = datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    rows = [[f"{stamp}-{requester}-{t}", requester, t, text, now, ST_OPEN,
             "", link, "", ""] for t in targets]
    _ws().append_rows(rows, value_input_option="RAW")
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
            ws.update_cell(i, _COL_STATUS, ST_DONE)
            ws.update_cell(i, _COL_DONE_AT, now)
            _rows.clear()
            return


def _find_row(ws, req_id):
    """요청ID로 시트의 실제 행 번호 찾기(캐시 아닌 최신 값 — 행밀림 방지)."""
    for i, r in enumerate(ws.get_all_values()[1:], start=2):
        if r and r[0].strip() == req_id:
            return i
    return None


def set_reply(req_id, text):
    """대상자가 남기는 한 줄 회신. 요청자가 아직 확인 안 한 상태로 되돌린다
    (회신을 새로 달면 요청자 홈에 다시 알림이 뜨게)."""
    req_id = (req_id or "").strip()
    text = (text or "").strip()
    if not req_id:
        return
    ws = _ws()
    i = _find_row(ws, req_id)
    if i:
        ws.update_cell(i, _COL_REPLY, text)
        ws.update_cell(i, _COL_ACK, "")
        _rows.clear()


def ack_request(req_id, requester):
    """요청자가 결과(완료/회신)를 확인 — 홈 알림에서 사라짐."""
    req_id = (req_id or "").strip()
    requester = (requester or "").strip()
    if not req_id:
        return
    ws = _ws()
    for i, r in enumerate(ws.get_all_values()[1:], start=2):
        r = (list(r) + [""] * len(REQ_HEADER))[:len(REQ_HEADER)]
        if r[0].strip() == req_id and r[1].strip() == requester:
            ws.update_cell(i, _COL_ACK,
                           datetime.now(KST).strftime("%Y-%m-%d %H:%M"))
            _rows.clear()
            return


def updates_for(requester):
    """내가 보낸 요청 중 '결과가 왔는데 아직 확인 안 한' 것들(홈 알림용).
    = 완료됐거나 회신이 달렸는데 '확인' 칸이 비어 있는 요청."""
    requester = (requester or "").strip()
    if not requester:
        return []
    out = []
    for d in _rows():
        if d["요청자"].strip() != requester:
            continue
        if d.get("확인", "").strip():
            continue
        if d["상태"].strip() == ST_DONE or d.get("회신", "").strip():
            out.append(d)
    return out


def update_request(req_id, requester, text, link=""):
    """보낸 요청의 내용·링크 수정(잘못 보냈을 때). 요청자 본인 것만.
    완료·회신 기록은 그대로 둔다(누가 무엇을 했는지 흔적을 지우지 않기 위해)."""
    req_id = (req_id or "").strip()
    requester = (requester or "").strip()
    text = (text or "").strip()
    if not req_id or not text:
        return
    ws = _ws()
    for i, r in enumerate(ws.get_all_values()[1:], start=2):
        r = (list(r) + [""] * len(REQ_HEADER))[:len(REQ_HEADER)]
        if r[0].strip() == req_id and r[1].strip() == requester:
            ws.update_cell(i, _COL_TEXT, text)
            ws.update_cell(i, _COL_LINK, (link or "").strip())
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
