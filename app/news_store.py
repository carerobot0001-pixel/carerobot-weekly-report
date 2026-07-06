"""사업단 관련 뉴스 — 구글 뉴스 RSS로 돌봄로봇·보건복지·AI 기사 수집.

API 키 불필요(공개 RSS). 1시간 캐시. 실패해도 빈 목록 반환(홈 안 죽음).
키워드가 바뀌면 NEWS_QUERIES만 수정.
"""
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests
import streamlit as st

NEWS_QUERIES = [
    "돌봄로봇",
    "보건복지부 AI 돌봄",
    "휴머노이드 로봇",
    "돌봄 AI 로봇",
]


@st.cache_data(ttl=3600)
def fetch_news(per_query: int = 2, cap: int = 8) -> list:
    """각 키워드별 최신 기사 몇 개씩 모아 반환 — [{title, link, source}]."""
    seen, out = set(), []
    for q in NEWS_QUERIES:
        try:
            url = (f"https://news.google.com/rss/search?q={quote(q)}"
                   "&hl=ko&gl=KR&ceid=KR:ko")
            r = requests.get(url, timeout=8,
                             headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            cnt = 0
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
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
    return out[:cap]
