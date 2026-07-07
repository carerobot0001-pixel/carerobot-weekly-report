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
    return st.secrets.get("calendar", {}).get("id", "")


def calendar_enabled() -> bool:
    return bool(calendar_id())


def embed_url(mode: str = "MONTH") -> str:
    cid = calendar_id()
    if not cid:
        return ""
    # mode: MONTH / WEEK / AGENDA(일정목록). color=%23D50000 → 기존 캘린더와 같은 빨강
    mode = mode.upper() if mode.upper() in ("MONTH", "WEEK", "AGENDA") else "MONTH"
    return (f"https://calendar.google.com/calendar/embed?src={quote(cid)}"
            f"&ctz=Asia%2FSeoul&mode={mode}&color=%23D50000")


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


@st.cache_data(ttl=60)
def today_events() -> list:
    """오늘(00:00~24:00) 일정 목록 (시간순)."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    r = _sess().get(f"{CAL_API}/calendars/{_cid()}/events", params={
        "timeMin": start.isoformat(), "timeMax": end.isoformat(),
        "singleEvents": "true", "orderBy": "startTime", "maxResults": 30,
    })
    r.raise_for_status()
    return r.json().get("items", [])


@st.cache_data(ttl=60)
def upcoming_events(days: int = 45, maxn: int = 50) -> list:
    """지금부터 days일 내 일정(시간순). 각 항목: 원본 이벤트 dict."""
    now = datetime.now(KST)
    r = _sess().get(f"{CAL_API}/calendars/{_cid()}/events", params={
        "timeMin": now.isoformat(),
        "timeMax": (now + timedelta(days=days)).isoformat(),
        "singleEvents": "true", "orderBy": "startTime", "maxResults": maxn,
    })
    r.raise_for_status()
    return r.json().get("items", [])


def _body(summary, the_date, all_day, start_t, end_t, desc):
    if all_day:
        return {"summary": summary, "description": desc,
                "start": {"date": the_date},
                "end": {"date": (datetime.strptime(the_date, "%Y-%m-%d").date()
                                 + timedelta(days=1)).strftime("%Y-%m-%d")}}
    return {"summary": summary, "description": desc,
            "start": {"dateTime": f"{the_date}T{start_t}:00", "timeZone": "Asia/Seoul"},
            "end": {"dateTime": f"{the_date}T{end_t}:00", "timeZone": "Asia/Seoul"}}


def add_event(summary, the_date, all_day, start_t, end_t, desc="") -> str:
    r = _sess().post(f"{CAL_API}/calendars/{_cid()}/events",
                     json=_body(summary, the_date, all_day, start_t, end_t, desc))
    r.raise_for_status()
    upcoming_events.clear()
    return r.json().get("id", "")


def update_event(event_id, summary, the_date, all_day, start_t, end_t, desc="") -> None:
    r = _sess().put(f"{CAL_API}/calendars/{_cid()}/events/{event_id}",
                    json=_body(summary, the_date, all_day, start_t, end_t, desc))
    r.raise_for_status()
    upcoming_events.clear()


def delete_event(event_id) -> None:
    r = _sess().delete(f"{CAL_API}/calendars/{_cid()}/events/{event_id}")
    if r.status_code not in (200, 204):
        r.raise_for_status()
    upcoming_events.clear()


def event_view(e: dict) -> dict:
    """이벤트 dict → 표시용 (날짜/시간 문자열, 종일 여부)."""
    s, en = e.get("start", {}), e.get("end", {})
    if "date" in s:  # 종일
        return {"id": e.get("id"), "title": e.get("summary", "(제목 없음)"),
                "date": s["date"], "when": "종일", "all_day": True,
                "start_t": "09:00", "end_t": "10:00",
                "desc": e.get("description", "")}
    sd = s.get("dateTime", "")[:16]  # YYYY-MM-DDTHH:MM
    ed = en.get("dateTime", "")[:16]
    return {"id": e.get("id"), "title": e.get("summary", "(제목 없음)"),
            "date": sd[:10], "when": f"{sd[11:]}~{ed[11:]}", "all_day": False,
            "start_t": sd[11:] or "09:00", "end_t": ed[11:] or "10:00",
            "desc": e.get("description", "")}
