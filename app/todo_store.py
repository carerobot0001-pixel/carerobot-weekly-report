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
# '중요'·'마감일'도 맨 뒤 — 옛 4열 행이 밀리지 않게.
TODO_HEADER = ["아이디", "내용", "등록일시", "구분", "중요", "마감일",
               "영역", "순서", "진행일", "진행", "묶음"]
# '묶음' = 여러 할 일이 이어지는 **하나의 프로젝트 이름**.
# 큰 일 하나가 작은 일로 계속 갈라지는데, ✓(완료)를 누르면 그 갈래가 사라져
# 무엇의 일부였는지 안 남는다. 묶음을 적어두면 완료 기록에도 함께 남아
# 주간보고에서 "○○ 프로젝트 — 이번 주 완료분"으로 묶어 볼 수 있다.
# '진행' = 지금 어디까지 왔는지 본인이 직접 적는 한 줄("메일 회신 기다리는 중" 등).
# '진행일' = 그 메모를 적은 날짜 — 며칠째 그 상태인지 세기 위해.
# 완료(✓)로 넘기면 실적 기록이 되어버리는데 아직 끝난 게 아니고, 그냥 두면
# 손도 안 댄 일처럼 보인다. 그 사이를 메우고, 주간보고 실적에도 함께 넣는다.
AREA_RESEARCH, AREA_WORK = "연구", "업무"   # 주간보고의 연구/업무와 같은 구분
_COL_STAR = TODO_HEADER.index("중요") + 1
_COL_DUE = TODO_HEADER.index("마감일") + 1
_COL_AREA = TODO_HEADER.index("영역") + 1
_COL_ORDER = TODO_HEADER.index("순서") + 1
_COL_NOTED = TODO_HEADER.index("진행일") + 1
_COL_NOTE = TODO_HEADER.index("진행") + 1
_COL_GROUP = TODO_HEADER.index("묶음") + 1
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
    ws.append_row([uid, f"{key}={value}", now, KIND_SYNC, "", "", "", "", "", "", ""],
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


def _ensure_cols(ws):
    """컬럼을 늘린 코드가 배포돼도 시트가 그대로인 경우를 메운다.

    `_ws()`는 `@st.cache_resource`라 **프로세스가 살아 있는 동안 한 번만** 헤더를
    확인한다. Streamlit Cloud가 재배포에서 프로세스를 안 죽이면 새 컬럼이 영영
    안 생기고, 그 칸에 쓰는 저장이 조용히 실패한다(실제로 '진행' 칸에서 발생).
    그래서 쓰기 직전에 한 번 더 확인한다.
    """
    if ws.col_count < len(TODO_HEADER):
        ws.add_cols(len(TODO_HEADER) - ws.col_count)
        end = gspread.utils.rowcol_to_a1(1, len(TODO_HEADER))
        ws.update(values=[TODO_HEADER], range_name=f"A1:{end}")


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


def add_todo(uid, text, kind=KIND_TODO, due="", area=AREA_WORK,
             star=False, group=""):
    uid = (uid or "").strip()
    text = (text or "").strip()
    if not uid or not text:
        return
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    ws = _ws()
    _ensure_cols(ws)
    ws.append_row([uid, text, now, kind, "Y" if star else "",
                      (due or "").strip(), (area or AREA_WORK), "", "", "", (group or "").strip()],
                     value_input_option="RAW")
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
    _area = (r[TODO_HEADER.index("영역")].strip()
             if len(r) > TODO_HEADER.index("영역") else "") or AREA_WORK
    _gi = TODO_HEADER.index("묶음")
    _group = r[_gi].strip() if len(r) > _gi else ""
    ws.append_row([uid, text, now, KIND_DONE, "", "", _area, "", "", "", _group],
                  value_input_option="RAW")   # 끝에 기록(영역 보존)
    ws.delete_rows(row)                                                   # 활성 행 제거
    _rows.clear()


def _update(uid, row, text, col, value):
    """행밀림 방지로 (아이디+내용) 재확인 후 한 칸만 수정."""
    uid, text = (uid or "").strip(), (text or "").strip()
    if not uid or not row:
        return
    ws = _ws()
    _ensure_cols(ws)
    vals = ws.get_all_values()
    if not (1 <= row - 1 < len(vals)):
        return
    r = vals[row - 1]
    if r and r[0].strip() == uid and (len(r) < 2 or r[1].strip() == text):
        ws.update_cell(row, col, value)
        _rows.clear()


def set_star(uid, row, text, on: bool):
    """⭐ 중요 표시 켜기/끄기."""
    _update(uid, row, text, _COL_STAR, "Y" if on else "")


def set_area(uid, row, text, area: str):
    """연구/업무 영역 변경."""
    if area in (AREA_RESEARCH, AREA_WORK):
        _update(uid, row, text, _COL_AREA, area)


def set_note(uid, row, text, note: str):
    """진행 메모 저장(빈 문자열이면 해제). 날짜도 같이 남겨 '며칠째'를 셀 수 있게 한다.

    칸이 둘이라 _update를 두 번 부른다(호출 2회) — 항목 하나를 손볼 때만 쓰므로
    reorder처럼 batch로 묶을 만큼 잦지 않다.
    """
    note = " ".join((note or "").split())
    _update(uid, row, text, _COL_NOTE, note)
    _update(uid, row, text, _COL_NOTED,
            datetime.now(KST).strftime("%Y-%m-%d") if note else "")


def set_due(uid, row, text, due: str):
    """마감일 설정('YYYY-MM-DD', 빈 문자열이면 해제)."""
    _update(uid, row, text, _COL_DUE, (due or "").strip())


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


def reorder(uid, ordered):
    """드래그로 정한 순서·영역을 한 번에 저장. ordered = [(row, 영역, 순번), ...]
    행마다 update_cell 두 번이면 호출이 많아지므로 batch_update 로 한 번에 쓴다."""
    uid = (uid or "").strip()
    if not uid or not ordered:
        return
    ws = _ws()
    reqs = []
    for row, area, idx in ordered:
        reqs.append({"range": gspread.utils.rowcol_to_a1(row, _COL_AREA),
                     "values": [[area]]})
        reqs.append({"range": gspread.utils.rowcol_to_a1(row, _COL_ORDER),
                     "values": [[str(idx)]]})
    ws.batch_update(reqs, value_input_option="RAW")
    _rows.clear()


def order_key(d):
    """정렬용 — 사용자가 정한 순서가 있으면 그 값, 없으면 맨 뒤(등록순)."""
    v = (d.get("순서", "") or "").strip()
    try:
        return (0, int(v))
    except ValueError:
        return (1, d.get("등록일시", ""))


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


def set_group(uid, row, text, group):
    """묶음(프로젝트) 이름 지정. 빈 문자열이면 해제."""
    _update(uid, row, text, _COL_GROUP, (group or "").strip())


def groups(uid):
    """내가 쓰고 있는 묶음 이름들(활성 + 완료 기록에서)."""
    uid = (uid or "").strip()
    out = []
    for d in _rows():
        if d["아이디"].strip() != uid:
            continue
        g = (d.get("묶음", "") or "").strip()
        if g and g not in out:
            out.append(g)
    return out
