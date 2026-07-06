"""사업단 관련 뉴스 — 구글 뉴스 RSS + 기사 썸네일(og:image).

돌봄·돌봄로봇 우선, AI·신기술(LLM 등) 보조. API 키 불필요. 썸네일은 각 기사
페이지의 og:image를 병렬로 추출(1시간 캐시). 실패해도 빈 목록/무이미지로 폴백.
키워드가 바뀌면 NEWS_QUERIES만 수정.
"""
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests
import streamlit as st

# 앞쪽(돌봄) 우선 — 순서대로 채워서 돌봄 기사가 먼저 노출
NEWS_QUERIES = [
    "돌봄로봇",
    "돌봄 AI 로봇",
    "노인 돌봄 로봇",
    "보건복지부 돌봄",
    "AI LLM 신기술",
    "휴머노이드 로봇",
]
_UA = {"User-Agent": "Mozilla/5.0"}


@st.cache_data(ttl=3600)
def fetch_news(per_query: int = 2, cap: int = 9) -> list:
    """[{title, link, source}] — 돌봄 우선. (구글뉴스는 기사 사진을 제공 안 해
    이미지는 생략 — 제목·출처 위주)."""
    seen, out = set(), []
    for q in NEWS_QUERIES:
        try:
            url = (f"https://news.google.com/rss/search?q={quote(q)}"
                   "&hl=ko&gl=KR&ceid=KR:ko")
            r = requests.get(url, timeout=8, headers=_UA)
            root = ET.fromstring(r.content)
            cnt = 0
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                # 제목 끝의 " - 출처" 제거
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
