"""CC로 수신된 보고 메일 수집함 — 제출함 스프레드시트 '메일수신' 탭.

Gmail 자체는 앱이 읽지 않는다. carerobot0001 계정에서 도는 **Google Apps Script**가
CC 메일을 이 탭에 적재하고(무료·본인 계정 실행이라 OAuth 심사/토큰만료 없음),
앱은 이 탭을 **읽기만** 해서 팀원별로 보여준다(보낸이메일 ↔ 계정 이메일 매칭).
컬럼이 바뀌면 MAIL_HEADER만 맞추면 됨(_ws가 헤더 자동 보정).
"""
import gspread
import streamlit as st

from sheets_store import _get_client

MAIL_WS = "메일수신"
MAIL_HEADER = ["메일ID", "날짜", "보낸이름", "보낸이메일", "제목", "본문"]

# 키워드 기반 자동 분류 — 위에서부터 첫 매칭. AI·과금 없이 동작.
# (구 '돌봄사업단 대시보드' 프로젝트의 분류 규칙을 가져와 다듬음)
MAIL_RULES = [
    ("🔴 긴급", 5, ["긴급", "즉시", "IRB", "법정", "마감", "기한", "overdue",
                   "D-1", "D-2", "D-3", "★★★★★"]),
    ("🟠 결정필요", 4, ["검토 요청", "검토요청", "승인 여부", "결정", "선택",
                      "구매", "도입", "구독", "취소", "비교", "의견 요청"]),
    ("🖊️ 결재", 3, ["결재", "승인", "최종본", "영수증", "지출", "정산", "서명", "사인"]),
    ("💬 회의·논의", 2, ["회의", "면담", "논의", "협의", "대면", "미팅", "일정",
                       "세미나", "워크숍", "워크샵"]),
    ("📎 자료공유", 1, ["공유", "링크", "자료", "드라이브", "첨부", "송부", "전달"]),
]


def classify(subject, body=""):
    """제목+본문 키워드로 (태그, 우선순위) 판정. 매칭 없으면 일반(0)."""
    blob = f"{subject or ''} {body or ''}".lower()
    for tag, pri, keys in MAIL_RULES:
        if any(k.lower() in blob for k in keys):
            return tag, pri
    return "⚪ 일반", 0


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(MAIL_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=MAIL_WS, rows=1000, cols=len(MAIL_HEADER))
        ws.append_row(MAIL_HEADER)
        return ws
    if ws.col_count < len(MAIL_HEADER):
        ws.add_cols(len(MAIL_HEADER) - ws.col_count)
    if ws.row_values(1) != MAIL_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(MAIL_HEADER))
        ws.update(values=[MAIL_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=60)
def _rows():
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(MAIL_HEADER))[:len(MAIL_HEADER)]
        d = dict(zip(MAIL_HEADER, r))
        d["_row"] = i
        out.append(d)
    return out


def list_mails():
    """전체 메일(최신순)."""
    return sorted(_rows(), key=lambda d: d.get("날짜", ""), reverse=True)


def mails_for(emails):
    """내 이메일(들)로 보낸 메일만 — 팀원별 분리의 핵심."""
    keys = {(e or "").strip().lower() for e in emails if (e or "").strip()}
    if not keys:
        return []
    return [m for m in list_mails()
            if (m.get("보낸이메일", "") or "").strip().lower() in keys]


def unmatched(all_member_emails):
    """등록된 어떤 팀원 이메일과도 매칭 안 되는 메일(미분류)."""
    keys = {(e or "").strip().lower() for e in all_member_emails if (e or "").strip()}
    return [m for m in list_mails()
            if (m.get("보낸이메일", "") or "").strip().lower() not in keys]
