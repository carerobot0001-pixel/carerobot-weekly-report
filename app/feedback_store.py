"""앱 개선 요청 — 제출함 스프레드시트의 '개선요청' 탭.

Dolbom Studio 자체에 대한 팀원 의견(오류 신고·개선 제안·문의)을 모으는 곳.
업무 데이터가 아니라 '앱을 고치기 위한' 기록이라 별도 탭으로 둔다.
컬럼이 바뀌면 FB_HEADER만 수정(_ws가 헤더/열수 자동 보정).
"""
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

FB_WS = "개선요청"
# '확인'은 **맨 뒤**에 붙였다(옛 행이 안 밀리게). 요청한 사람이 완료 알림을
# 홈에서 확인하면 이 칸에 이름이 들어가고, 그때부터 알림이 사라진다.
FB_HEADER = ["등록일시", "작성자", "분류", "내용", "상태", "처리메모",
             "처리일시", "처리자", "확인"]
_COL_STATUS = FB_HEADER.index("상태") + 1
_COL_MEMO = FB_HEADER.index("처리메모") + 1
_COL_AT = FB_HEADER.index("처리일시") + 1
_COL_BY = FB_HEADER.index("처리자") + 1

KINDS = ["🐞 오류·안 되는 것", "💡 개선 아이디어", "❓ 사용법 문의"]
ST_NEW, ST_DOING, ST_DONE, ST_HOLD = "접수", "진행중", "완료", "보류"
STATUSES = [ST_NEW, ST_DOING, ST_DONE, ST_HOLD]


class RowMismatch(Exception):
    """수정하려는 행이 그 사이 바뀜(행 밀림)."""


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(FB_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=FB_WS, rows=500, cols=len(FB_HEADER))
        ws.append_row(FB_HEADER)
        return ws
    if ws.col_count < len(FB_HEADER):
        ws.add_cols(len(FB_HEADER) - ws.col_count)
    if ws.row_values(1) != FB_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(FB_HEADER))
        ws.update(values=[FB_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=30)
def fb_rows():
    """등록 목록(최신순). 각 항목에 시트 행번호 `_row` 포함."""
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(FB_HEADER))[:len(FB_HEADER)]
        d = dict(zip(FB_HEADER, r))
        d["_row"] = i
        out.append(d)
    return list(reversed(out))


def add_feedback(writer, kind, text):
    writer, kind, text = ((writer or "").strip(), (kind or "").strip(),
                          (text or "").strip())
    if not writer or not text:
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    _ws().append_row([now, writer, kind, text, ST_NEW, "", "", ""],
                     value_input_option="RAW")
    fb_rows.clear()


def _check(ws, row, expected_ts):
    """행 밀림 방지 — 그 행의 등록일시가 기대값과 같은지 확인."""
    vals = ws.get_all_values()
    if not (1 <= row - 1 < len(vals)):
        raise RowMismatch("행을 찾을 수 없습니다.")
    if vals[row - 1][0].strip() != (expected_ts or "").strip():
        raise RowMismatch("목록이 바뀌었습니다. 새로고침 후 다시 시도하세요.")


def set_status(row, expected_ts, status, memo, who):
    """상태·처리메모 갱신(누구나). 상태가 완료/보류면 처리일시·처리자도 기록."""
    ws = _ws()
    _check(ws, row, expected_ts)
    ws.update_cell(row, _COL_STATUS, status)
    ws.update_cell(row, _COL_MEMO, (memo or "").strip())
    if status in (ST_DONE, ST_HOLD, ST_DOING):
        ws.update_cell(row, _COL_AT,
                       datetime.now(KST).strftime("%Y-%m-%d %H:%M"))
        ws.update_cell(row, _COL_BY, (who or "").strip())
    fb_rows.clear()


def mark_seen(row, expected_ts, who):
    """요청자가 완료 알림을 '확인'했다고 표시 — 홈에서 그 알림이 사라진다."""
    ws = _ws()
    _check(ws, row, expected_ts)
    ws.update_cell(row, FB_HEADER.index("확인") + 1,
                   (who or "").strip() or "확인")
    fb_rows.clear()


def new_for_admin():
    """아직 손대지 않은(접수) 개선요청 목록 — 관리자 홈 알림용."""
    return [r for r in fb_rows() if (r.get("상태", "") or "").strip() == ST_NEW]


def done_for(name, days=3):
    """`name`이 올린 것 중 **완료됐는데 아직 확인 안 한** 것 — 요청자 홈 알림용.

    처리한 지 `days`일이 지나면 확인을 안 눌러도 더 안 띄운다(계속 남아 거슬리지 않게).
    """
    name = (name or "").strip()
    if not name:
        return []
    today = datetime.now(KST).date()
    out = []
    for r in fb_rows():
        if (r.get("작성자", "") or "").strip() != name:
            continue
        if (r.get("상태", "") or "").strip() != ST_DONE:
            continue
        if (r.get("확인", "") or "").strip():
            continue
        at = (r.get("처리일시", "") or "")[:10]
        if at:
            try:
                d = datetime.strptime(at, "%Y-%m-%d").date()
                if (today - d).days > days:
                    continue
            except Exception:
                pass
        out.append(r)
    return out


def delete_feedback(row, expected_ts):
    ws = _ws()
    _check(ws, row, expected_ts)
    ws.delete_rows(row)
    fb_rows.clear()


def open_count():
    """미처리(접수·진행중) 건수 — 사이드바/홈 배지용."""
    try:
        return sum(1 for r in fb_rows()
                   if r["상태"].strip() in (ST_NEW, ST_DOING) or
                   not r["상태"].strip())
    except Exception:
        return 0
