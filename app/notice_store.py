"""홈 팀 공지사항 — 제출함 스프레드시트의 '공지' 탭. 담당자가 등록/삭제, 전원 열람.

각 공지는 '표시 종료일(만료일)'을 선택적으로 가질 수 있고, 그 날이 지나면
화면에서 자동으로 숨겨지고 시트에서도 정리(자동삭제)된다. 만료일이 비어 있으면
수동 삭제 전까지 계속 표시된다.
컬럼이 바뀌면 NOTICE_HEADER만 맞추면 됨(_ws가 헤더/열수 자동 보정).
"""
import gspread
import streamlit as st
from datetime import datetime

from sheets_store import _get_client, KST

NOTICE_WS_TITLE = "공지"
# 확인자는 맨 뒤에 추가 — 옛 4열 행도 그대로 읽힘(데이터 안 밀림)
NOTICE_HEADER = ["등록일시", "작성자", "내용", "만료일", "확인자"]


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(NOTICE_WS_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=NOTICE_WS_TITLE, rows=200,
                              cols=len(NOTICE_HEADER))
        ws.append_row(NOTICE_HEADER)
        return ws
    # 옛 3열 탭 등 헤더/열수 자동 보정
    if ws.col_count < len(NOTICE_HEADER):
        ws.add_cols(len(NOTICE_HEADER) - ws.col_count)
    if ws.row_values(1) != NOTICE_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(NOTICE_HEADER))
        ws.update(values=[NOTICE_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=30)
def notices() -> list:
    """(행번호, [등록일시, 작성자, 내용, 만료일]) 목록 — 만료 여부 무관 전체."""
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        out.append((i, (list(r) + [""] * len(NOTICE_HEADER))[:len(NOTICE_HEADER)]))
    return out


def is_expired(row, today_str: str) -> bool:
    """만료일(YYYY-MM-DD)이 today_str 보다 이전이면 만료(표시 종료). 비어있으면 영구."""
    exp = (list(row) + [""] * len(NOTICE_HEADER))[3].strip()
    return bool(exp) and exp < today_str


def add_notice(author: str, text: str, expire: str = "") -> None:
    ws = _ws()
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    # RAW: 날짜/시각 문자열을 시트가 네이티브 날짜로 변환해 로케일별 표기로
    # 되돌리는 걸 막음(만료일 "YYYY-MM-DD" 문자열 비교와 행 재확인이 정확해짐).
    ws.append_row([ts, author, text, expire.strip(), ""],
                  value_input_option="RAW")
    notices.clear()


def delete_notice(row_idx: int, expected_ts: str) -> None:
    ws = _ws()
    cur = ws.row_values(row_idx)
    if (cur[0].strip() if cur else "") != expected_ts.strip():
        raise RuntimeError("공지 행이 바뀌었습니다.")
    ws.delete_rows(row_idx)
    notices.clear()


def sweep_expired(today_str: str) -> int:
    """만료일이 지난 공지를 시트에서 자동삭제. 삭제 건수 반환.

    시트를 새로 읽어 진짜 행번호를 얻고, 높은 행부터 삭제(인덱스 밀림 방지),
    삭제 직전 등록일시를 재확인(행 밀림 감지)한다. 만료일 기반이라
    외부 상태(문서협업 등)에 의존하지 않아 안전.
    """
    ws = _ws()
    vals = ws.get_all_values()
    stale = []  # (행번호, 등록일시)
    for i, r in enumerate(vals[1:], start=2):
        r4 = (list(r) + [""] * 4)[:4]
        if not r4[2].strip():          # 내용 없는 빈 행 무시
            continue
        if is_expired(r4, today_str):
            stale.append((i, r4[0]))
    if not stale:
        return 0
    for i, ts in sorted(stale, key=lambda x: x[0], reverse=True):
        cur = ws.row_values(i)
        if (cur[0].strip() if cur else "") == ts.strip():
            ws.delete_rows(i)
    notices.clear()
    return len(stale)


def readers(row) -> list:
    """그 공지를 확인(읽음)한 사람 목록."""
    v = (list(row) + [""] * len(NOTICE_HEADER))[4]
    return [n.strip() for n in (v or "").split(",") if n.strip()]


def mark_read(row_idx: int, expected_ts: str, name: str) -> list:
    """확인자에 name 추가(중복 방지). 쓰기 직전 등록일시 재확인 → 행 밀림 방지."""
    name = (name or "").strip()
    if not name:
        return []
    ws = _ws()
    cur = ws.row_values(row_idx)
    if (cur[0].strip() if cur else "") != expected_ts.strip():
        raise RuntimeError("공지 행이 바뀌었습니다. 새로고침 후 다시 시도해 주세요.")
    cur = (list(cur) + [""] * len(NOTICE_HEADER))[:len(NOTICE_HEADER)]
    names = [n.strip() for n in (cur[4] or "").split(",") if n.strip()]
    if name not in names:
        names.append(name)
        ws.update_cell(row_idx, 5, ", ".join(names))   # E열 = 확인자
        notices.clear()
    return names
