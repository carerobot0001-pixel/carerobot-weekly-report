"""스마트돌봄스페이스 외부 구글시트 연동 (FAQ 수집 / 스페이스 관리대장).

두 시트는 이 앱 소유가 아니라 팀원이 운영하는 공유 시트:
  - "스마트돌봄스페이스 FAQ" (백정은) — 사용매뉴얼 FAQ 항목 수집
  - "스마트돌봄스페이스 관련 문제 및 돌봄로봇 관리" (한벼리) — 스페이스 관리대장

레포가 공개라서 시트 ID는 코드에 두지 않고 secrets의 [smart_space] 섹션에서 읽는다:

  [smart_space]
  faq_sheet_id = "..."      # FAQ 시트 문서 ID
  space_sheet_id = "..."    # 관리대장 시트 문서 ID

각 시트에 서비스 계정(client_email)이 '편집자'로 공유되어 있어야 한다.
컬럼 구조(HEADER)가 바뀌면 아래 상수만 맞춰 수정하면 된다.
"""
import gspread
import streamlit as st

from sheets_store import _get_client

# 원본 시트의 1행 헤더와 동일한 순서 (번호 컬럼 포함)
FAQ_HEADER = ["번호", "공간 구분", "돌봄분야", "기기/서비스",
              "예상 질문(FAQ)", "답변", "문의 유형", "작성자", "비고"]
SPACE_LOG_HEADER = ["번호", "위치", "문제", "발견자", "조치방안", "발견 일자",
                    "진행상황", "조치일자", "관리유형", "조치자", "비고"]

SPACE_LOG_WS_TITLE = "스페이스 관리대장"  # 관리대장 시트 안의 워크시트(탭) 이름


class SheetNotConfigured(Exception):
    """secrets [smart_space]에 해당 시트 ID가 등록되지 않음."""


class RowMismatch(Exception):
    """캐시된 행 위치와 실제 시트 내용이 불일치 (그 사이 시트가 수정됨)."""


def _sheet_id(key: str) -> str:
    sid = st.secrets.get("smart_space", {}).get(key, "")
    if not sid:
        raise SheetNotConfigured(key)
    return sid


def sheet_url(key: str) -> str:
    """구글시트 바로가기 URL. 미설정이면 빈 문자열."""
    try:
        return f"https://docs.google.com/spreadsheets/d/{_sheet_id(key)}/edit"
    except SheetNotConfigured:
        return ""


@st.cache_resource
def _faq_ws():
    ss = _get_client().open_by_key(_sheet_id("faq_sheet_id"))
    try:
        return ss.worksheet("시트1")
    except gspread.WorksheetNotFound:
        return ss.get_worksheet(0)


@st.cache_resource
def _space_log_ws():
    ss = _get_client().open_by_key(_sheet_id("space_sheet_id"))
    try:
        return ss.worksheet(SPACE_LOG_WS_TITLE)
    except gspread.WorksheetNotFound:
        return ss.get_worksheet(0)  # 단톡 공유 링크가 gid=0 (첫 탭)


def _filter_data(vals: list, header: list) -> list:
    """헤더 제외, 값이 하나라도 있는 행만. 각 행을 헤더 길이에 맞춰 패딩."""
    out = []
    for r in vals[1:]:
        if not any(c.strip() for c in r):
            continue
        out.append((list(r) + [""] * len(header))[:len(header)])
    return out


def _data_rows(ws, header: list) -> list:
    return _filter_data(ws.get_all_values(), header)


def _write_row(ws, row_idx: int, row: list, ncols: int):
    """row_idx 행(마지막 데이터 행 바로 아래)에 한 줄 기록.

    append_row(테이블 자동 감지)는 필터가 시트 끝까지 걸린 시트(관리대장)에서
    새 행을 그리드 맨 끝(994행)에 떨어뜨려 운영자가 못 보고 지나치게 된다.
    그래서 마지막 값이 있는 행을 직접 찾아 그 다음 행에 쓴다.
    """
    if row_idx > ws.row_count:  # 그리드가 꽉 찬 경우에만 append로 확장
        ws.append_row(row, value_input_option="USER_ENTERED", table_range="A1")
        return
    end_col = chr(ord('A') + ncols - 1)
    ws.update(values=[row], range_name=f"A{row_idx}:{end_col}{row_idx}", raw=False)


def _next_no(rows: list) -> int:
    """첫 컬럼(번호)의 최댓값 + 1. 비거나 숫자가 아닌 행은 무시."""
    mx = 0
    for r in rows:
        try:
            mx = max(mx, int(float(r[0])))
        except (ValueError, IndexError):
            continue
    return mx + 1


@st.cache_data(ttl=60)
def faq_rows() -> list:
    return _data_rows(_faq_ws(), FAQ_HEADER)


def add_faq(space: str, domain: str, device: str, question: str,
            answer: str, qtype: str, writer: str, note: str) -> int:
    ws = _faq_ws()
    vals = ws.get_all_values()
    no = _next_no(_filter_data(vals, FAQ_HEADER))
    _write_row(ws, len(vals) + 1,
               [no, space, domain, device, question, answer, qtype, writer, note],
               len(FAQ_HEADER))
    faq_rows.clear()
    return no


@st.cache_data(ttl=60)
def space_log_rows() -> list:
    """(시트 행 번호, 패딩된 행) 튜플 목록 — 행 번호는 완료 처리 시 위치 지정용."""
    vals = _space_log_ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        out.append((i, (list(r) + [""] * len(SPACE_LOG_HEADER))[:len(SPACE_LOG_HEADER)]))
    return out


def add_space_log(location: str, problem: str, finder: str, action: str,
                  found_date: str, status: str, note: str) -> int:
    ws = _space_log_ws()
    vals = ws.get_all_values()
    no = _next_no(_filter_data(vals, SPACE_LOG_HEADER))
    # 접수 시점에 이미 처리완료면 조치일자/조치자도 함께 기록
    fixed_date = found_date if status == "처리완료" else ""
    fixer = finder if status == "처리완료" else ""
    _write_row(ws, len(vals) + 1,
               [no, location, problem, finder, action, found_date,
                status, fixed_date, "", fixer, note],
               len(SPACE_LOG_HEADER))
    space_log_rows.clear()
    return no


def resolve_space_log(row_idx: int, expected_problem: str, fixer: str,
                      fixed_date: str, action: str = "") -> None:
    """미해결 문제를 처리완료로 변경 — 해당 행의 G(진행상황)/H(조치일자)/J(조치자),
    조치 내용이 입력된 경우에만 E(조치방안) 칸을 수정한다.

    쓰기 직전에 그 행의 '문제' 텍스트를 다시 읽어 선택 시점과 같은지 확인한다
    (목록 캐시 60초 사이에 시트에서 행이 추가/삭제되면 위치가 밀릴 수 있음).
    """
    ws = _space_log_ws()
    current = ws.row_values(row_idx)
    cur_problem = current[2].strip() if len(current) > 2 else ""
    if cur_problem != expected_problem.strip():
        raise RowMismatch(f"{row_idx}행: '{cur_problem}' != '{expected_problem}'")
    data = [
        {"range": f"G{row_idx}", "values": [["처리완료"]]},
        {"range": f"H{row_idx}", "values": [[fixed_date]]},
        {"range": f"J{row_idx}", "values": [[fixer]]},
    ]
    if action.strip():
        data.append({"range": f"E{row_idx}", "values": [[action.strip()]]})
    ws.batch_update(data, value_input_option="USER_ENTERED")
    space_log_rows.clear()
