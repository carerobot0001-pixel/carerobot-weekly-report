"""사업단 관련 뉴스 — 구글 뉴스 RSS. 섹션(카테고리)별로 다른 기사를 보여준다.

돌봄·돌봄로봇 우선, AI·신기술(LLM 등)·로봇 보조. API 키 불필요.
구글뉴스는 기사 사진을 제공하지 않아 제목·출처만 노출.
섹션/키워드가 바뀌면 NEWS_SECTIONS만 수정.
"""
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests
import streamlit as st

# (탭 이름, 검색 키워드들) — 탭을 누르면 섹션별로 다른 기사가 나옴(네이버 뉴스스탠드식)
NEWS_SECTIONS = [
    ("🤖 돌봄로봇", ("돌봄로봇", "돌봄 로봇 서비스")),
    ("🧑‍🦳 돌봄·복지", ("노인 돌봄 로봇", "보건복지부 돌봄")),
    ("✨ AI·신기술", ("AI LLM 신기술", "생성형 AI")),
    ("🦿 로봇·휴머노이드", ("휴머노이드 로봇", "서비스 로봇")),
]
# 전체 합본용(구버전 홈 호환)
_ALL_QUERIES = tuple(q for _, qs in NEWS_SECTIONS for q in qs)
_UA = {"User-Agent": "Mozilla/5.0"}


def _fetch_queries(queries, per_query: int = 3, cap: int = 6) -> list:
    """[{title, link, source}] — 주어진 키워드들에서 중복 제거 후 최대 cap개."""
    seen, out = set(), []
    for q in queries:
        try:
            url = (f"https://news.google.com/rss/search?q={quote(q)}"
                   "&hl=ko&gl=KR&ceid=KR:ko")
            r = requests.get(url, timeout=8, headers=_UA)
            root = ET.fromstring(r.content)
            cnt = 0
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                title = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = (item.findtext("link") or "").strip()
                src_el = item.find("{*}source")
                source = src_el.text if src_el is not None else ""
                if not title or not link or title in seen:
                    continue
                seen.add(title)
                out.append({"title": title, "link": link, "source": source})
                cnt += 1
                if cnt >= per_query:
                    break
        except Exception:
            continue
        if len(out) >= cap:
            break
    return out[:cap]


@st.cache_data(ttl=3600)
def fetch_section(queries: tuple, cap: int = 5) -> list:
    """한 섹션(키워드 튜플)의 기사 목록. 섹션 탭용."""
    return _fetch_queries(list(queries), per_query=3, cap=cap)


@st.cache_data(ttl=3600)
def fetch_news(per_query: int = 2, cap: int = 9) -> list:
    """전체 합본(돌봄 우선). 섹션 탭을 쓰지 않는 곳의 호환용."""
    return _fetch_queries(list(_ALL_QUERIES), per_query=per_query, cap=cap)
