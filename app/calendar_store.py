"""사업단 구글 캘린더 연동 — 서비스 계정(writer 공유)으로 일정 조회·추가·수정·삭제.

캘린더 ID는 secrets [calendar] id 에 둔다(공개 레포 대비). 서비스 계정
(streamlit-bot@…)이 해당 캘린더에 '일정 변경' 권한으로 공유되어 있어야 한다.
드라이브와 달리 캘린더 이벤트는 서비스 계정이 저장/수정 가능(용량 이슈 없음).
"""
from urllib.parse import quote
from datetime import datetime, timedelta

import streamlit as st
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

from sheets_store import KST

CAL_API = "https://www.googleapis.com/calendar/v3"
_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarNotConfigured(Exception):
    """secrets [calendar] id 가 없음."""


def calendar_id() -> str:
    """일정을 '추가'할 기본 캘린더(사업단)."""
    return st.secrets.get("calendar", {}).get("id", "")


def calendar_ids() -> list:
    """조회에 쓸 캘린더 전체. secrets [calendar] 의 id 와 id2, id3 … 를 모은다.
    (여러 캘린더를 한 화면에 합쳐 보기 위함. 쓰기는 기본 캘린더에만 한다.)"""
    sec = st.secrets.get("calendar", {})
    out = [sec.get("id", "")]
    for k in sorted(k for k in sec.keys() if k.startswith("id") and k != "id"):
        out.append(sec.get(k, ""))
    return [c for c in out if c]


def calendar_enabled() -> bool:
    return bool(calendar_id())


def embed_url(mode: str = "MONTH") -> str:
    ids = calendar_ids()
    if not ids:
        return ""
    # mode: MONTH / WEEK / AGENDA(일정목록). src 를 여러 개 주면 함께 표시된다.
    mode = mode.upper() if mode.upper() in ("MONTH", "WEEK", "AGENDA") else "MONTH"
    src = "".join(f"&src={quote(c)}" for c in ids)
    return (f"https://calendar.google.com/calendar/embed?ctz=Asia%2FSeoul"
            f"&mode={mode}&color=%23D50000{src}")


@st.cache_resource
def _sess():
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return AuthorizedSession(creds)


def _cid():
    cid = calendar_id()
    if not cid:
        raise CalendarNotConfigured()
    return quote(cid)


def _fetch(start, end, maxn):
    """등록된 모든 캘린더에서 기간 내 일정을 모아 시간순으로 돌려준다.
    하나가 실패해도(권한 없음 등) 나머지는 보이게 한다."""
    items = []
    for cid in calendar_ids():
        try:
            r = _sess().get(f"{CAL_API}/calendars/{quote(cid)}/events", params={
                "timeMin": start.isoformat(), "timeMax": end.isoformat(),
                "singleEvents": "true", "orderBy": "startTime",
                "maxResults": maxn,
            })
            r.raise_for_status()
            for e in r.json().get("items", []):
                e["_cal"] = cid          # 수정·삭제 때 이 캘린더로 보내야 함
                items.append(e)
        except Exception:
            continue
    items.sort(key=lambda e: (e.get("start", {}).get("dateTime")
                              or e.get("start", {}).get("date") or ""))
    return items


@st.cache_data(ttl=60)
def today_events() -> list:
    """오늘(00:00~24:00) 일정 목록 (시간순)."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _fetch(start, start + timedelta(days=1), 30)


@st.cache_data(ttl=60)
def upcoming_events(days: int = 45, maxn: int = 50) -> list:
    """지금부터 days일 내 일정(시간순). 각 항목: 원본 이벤트 dict."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _fetch(start, start + timedelta(days=days), maxn)


@st.cache_data(ttl=300)
def month_events(year: int, month: int, maxn: int = 250) -> list:
    """해당 '월' 전체 일정(시간순). 취합본 달력 이미지 생성용."""
    start = datetime(year, month, 1, tzinfo=KST)
    end = (datetime(year + 1, 1, 1, tzinfo=KST) if month == 12
           else datetime(year, month + 1, 1, tzinfo=KST))
    return _fetch(start, end, maxn)


def _body(summary, the_date, all_day, start_t, end_t, desc, location=""):
    if all_day:
        b = {"summary": summary, "description": desc, "location": location,
             "start": {"date": the_date},
             "end": {"date": (datetime.strptime(the_date, "%Y-%m-%d").date()
                              + timedelta(days=1)).strftime("%Y-%m-%d")}}
    else:
        b = {"summary": summary, "description": desc, "location": location,
             "start": {"dateTime": f"{the_date}T{start_t}:00", "timeZone": "Asia/Seoul"},
             "end": {"dateTime": f"{the_date}T{end_t}:00", "timeZone": "Asia/Seoul"}}
    return b


def add_event(summary, the_date, all_day, start_t, end_t, desc="", location="",
              cal="") -> str:
    """일정 추가. cal 을 주면 그 캘린더에(개인 캘린더 등), 없으면 사업단 캘린더에.

    ⚠️ 개인 캘린더에 쓰려면 그 캘린더를 서비스 계정(`streamlit-bot@…`)에
    **'일정 변경' 권한으로 공유**해야 한다. 안 하면 403이 온다.
    """
    r = _sess().post(f"{CAL_API}/calendars/{quote(cal) if cal else _cid()}/events",
                     json=_body(summary, the_date, all_day, start_t, end_t, desc, location))
    r.raise_for_status()
    upcoming_events.clear()
    return r.json().get("id", "")


def update_event(event_id, summary, the_date, all_day, start_t, end_t,
                 desc="", location="", cal="") -> None:
    r = _sess().put(f"{CAL_API}/calendars/{quote(cal) if cal else _cid()}"
                    f"/events/{event_id}",
                    json=_body(summary, the_date, all_day, start_t, end_t, desc, location))
    r.raise_for_status()
    upcoming_events.clear()


def delete_event(event_id, cal="") -> None:
    r = _sess().delete(f"{CAL_API}/calendars/{quote(cal) if cal else _cid()}"
                       f"/events/{event_id}")
    if r.status_code not in (200, 204):
        r.raise_for_status()
    upcoming_events.clear()


def event_view(e: dict) -> dict:
    """이벤트 dict → 표시용 (날짜/시간 문자열, 종일 여부)."""
    s, en = e.get("start", {}), e.get("end", {})
    if "date" in s:  # 종일
        return {"id": e.get("id"), "cal": e.get("_cal", ""),
                "title": e.get("summary", "(제목 없음)"),
                "date": s["date"], "when": "종일", "all_day": True,
                "start_t": "09:00", "end_t": "10:00",
                "desc": e.get("description", ""), "location": e.get("location", "")}
    sd = s.get("dateTime", "")[:16]  # YYYY-MM-DDTHH:MM
    ed = en.get("dateTime", "")[:16]
    return {"id": e.get("id"), "cal": e.get("_cal", ""),
            "title": e.get("summary", "(제목 없음)"),
            "date": sd[:10], "when": f"{sd[11:]}~{ed[11:]}", "all_day": False,
            "start_t": sd[11:] or "09:00", "end_t": ed[11:] or "10:00",
            "desc": e.get("description", ""), "location": e.get("location", "")}
