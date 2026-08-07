"""기기 자료 — 제조사가 직접 올리는 매뉴얼·설치안내·문의처. 시트 '기기자료' 탭.

**왜 필요한가**: 서비스모델 논문의 AS-IS 문제 4 — "기기는 들어오기만 하고,
문제가 생겨도 공급자에게 돌아갈 길이 없다". 현장에서 기기를 만지는 사람이
매뉴얼과 문의처를 못 찾는다. 그 길을 만든다.

**파일을 받지 않고 링크만 받는다.** 제조사가 500곳 규모로 늘어나면 파일 보관은
버전 관리(개정본이 나와도 우리 것은 옛날 판)·저작권·삭제 요청이 전부 우리 일이
된다. 링크면 제조사가 자기 사이트에서 갱신하는 순간 최신이 된다.
(문서 협업이 링크 방식인 것과 같은 이유 — `collab_store` 참고)

**흐름**: 제조사가 로그인 없이 제출(`?maker=` 페이지) → `대기` 로 쌓임
→ 팀원이 확인 후 `공개` 로 전환 → 자료실·장비 대장에 나타남.
제출은 무인이라 24시간 열려 있고, 공개만 사람이 판단한다.
"""
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

MK_WS = "기기자료"
MK_HEADER = ["등록일시", "제조사", "기기명", "모델", "자료종류", "제목", "링크",
             "설명", "담당자", "연락처", "상태", "검토자", "검토일시"]

KINDS = ["사용설명서", "설치·설정 안내", "문제해결(FAQ)", "교육 영상",
         "A/S·문의처", "기타"]
ST_WAIT, ST_OPEN, ST_HOLD = "대기", "공개", "보류"
STATUSES = [ST_WAIT, ST_OPEN, ST_HOLD]


class RowMismatch(Exception):
    """행이 밀린 뒤에 수정하려 한 경우 — 엉뚱한 제조사 자료를 건드리지 않게."""


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(MK_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=MK_WS, rows=500, cols=len(MK_HEADER))
        ws.append_row(MK_HEADER)
        return ws
    _ensure_cols(ws)
    return ws


def _ensure_cols(ws):
    """컬럼을 늘려도 시트가 안 따라오는 경우를 막는다(`todo_store`와 같은 이유 —
    `_ws()`는 캐시라 프로세스가 사는 동안 한 번만 도는데, 재배포로 프로세스가
    안 죽으면 새 칸이 영영 안 생기고 저장이 조용히 실패한다)."""
    if ws.col_count < len(MK_HEADER):
        ws.add_cols(len(MK_HEADER) - ws.col_count)
    if ws.row_values(1) != MK_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(MK_HEADER))
        ws.update(values=[MK_HEADER], range_name=f"A1:{end}")


@st.cache_data(ttl=20)
def _rows():
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(MK_HEADER))[:len(MK_HEADER)]
        d = dict(zip(MK_HEADER, r))
        d["_row"] = i
        out.append(d)
    return out


def list_items(status=None):
    """상태별 목록(최신 등록순). status 미지정이면 전체."""
    out = [d for d in _rows()
           if status is None or (d.get("상태", "") or ST_WAIT).strip() == status]
    return sorted(out, key=lambda d: d.get("등록일시", ""), reverse=True)


def search(keyword, status=ST_OPEN):
    """제조사·기기명·모델·제목에서 찾는다. 기본은 공개된 것만."""
    kw = (keyword or "").strip().lower()
    rows = list_items(status)
    if not kw:
        return rows
    return [d for d in rows
            if any(kw in (d.get(f, "") or "").lower()
                   for f in ("제조사", "기기명", "모델", "제목"))]


def for_device(device_name, status=ST_OPEN):
    """장비 대장의 기기명으로 매칭 — 이름이 정확히 같지 않아도 서로 포함하면 잡는다.

    대장에는 '광주서구 1 거실 P2'처럼 설치 위치가 붙은 이름도 있어서 완전일치로는
    거의 안 걸린다. 그래서 양방향 부분일치로 느슨하게 본다.
    """
    n = (device_name or "").strip().lower()
    if not n:
        return []
    out = []
    for d in list_items(status):
        dev = (d.get("기기명", "") or "").strip().lower()
        mdl = (d.get("모델", "") or "").strip().lower()
        if not dev:
            continue
        if dev in n or n in dev or (mdl and (mdl in n or n in mdl)):
            out.append(d)
    return out


def add_item(maker, device, model, kind, title, link, desc,
             person="", contact=""):
    """제조사가 제출. 항상 '대기' 로 들어간다 — 검토 없이 바로 뜨지 않게."""
    maker, device = (maker or "").strip(), (device or "").strip()
    title, link = (title or "").strip(), (link or "").strip()
    if not (maker and device and title and link):
        raise ValueError("제조사·기기명·제목·링크는 필수입니다.")
    if not link.lower().startswith(("http://", "https://")):
        raise ValueError("링크는 http:// 또는 https:// 로 시작해야 합니다.")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    ws = _ws()
    _ensure_cols(ws)
    ws.append_row([now, maker, device, (model or "").strip(),
                   (kind or "").strip(), title, link, (desc or "").strip(),
                   (person or "").strip(), (contact or "").strip(),
                   ST_WAIT, "", ""], value_input_option="RAW")
    _rows.clear()


def _check(ws, row, device):
    """쓰기 직전에 그 행의 기기명을 재확인 — 행이 밀렸으면 멈춘다."""
    vals = ws.get_all_values()
    di = MK_HEADER.index("기기명")
    if not (1 <= row - 1 < len(vals)):
        raise RowMismatch("행을 찾을 수 없습니다. 새로고침 후 다시 시도하세요.")
    r = vals[row - 1]
    if not (len(r) > di and r[di].strip() == (device or "").strip()):
        raise RowMismatch("목록이 바뀌었습니다. 새로고침 후 다시 시도하세요.")


def set_status(row, device, status, reviewer=""):
    """공개/보류 전환. 누가 언제 판단했는지 함께 남긴다."""
    if status not in STATUSES:
        return
    ws = _ws()
    _ensure_cols(ws)
    _check(ws, row, device)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    si = MK_HEADER.index("상태") + 1
    ws.batch_update([
        {"range": gspread.utils.rowcol_to_a1(row, si), "values": [[status]]},
        {"range": gspread.utils.rowcol_to_a1(row, si + 1),
         "values": [[(reviewer or "").strip()]]},
        {"range": gspread.utils.rowcol_to_a1(row, si + 2), "values": [[now]]},
    ], value_input_option="RAW")
    _rows.clear()


def delete_item(row, device):
    ws = _ws()
    _check(ws, row, device)
    ws.delete_rows(row)
    _rows.clear()
