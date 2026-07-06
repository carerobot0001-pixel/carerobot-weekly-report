"""사업단 관련 뉴스 — 구글 뉴스 RSS + 기사 썸네일(og:image).

돌봄·돌봄로봇 우선, AI·신기술(LLM 등) 보조. API 키 불필요. 썸네일은 각 기사
페이지의 og:image를 병렬로 추출(1시간 캐시). 실패해도 빈 목록/무이미지로 폴백.
키워드가 바뀌면 NEWS_QUERIES만 수정.
"""
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
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


def _og_image(link: str) -> str:
    try:
        a = requests.get(link, timeout=6, headers=_UA)
        m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', a.text)
        return m.group(1) if m else ""
    except Exception:
        return ""


@st.cache_data(ttl=3600)
def fetch_news(per_query: int = 2, cap: int = 9) -> list:
    """[{title, link, source, image}] — 돌봄 우선, 썸네일 포함."""
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
    out = out[:cap]
    # 썸네일 병렬 수집
    try:
        with ThreadPoolExecutor(max_workers=6) as ex:
            imgs = list(ex.map(_og_image, [it["link"] for it in out]))
        for it, img in zip(out, imgs):
            it["image"] = img
    except Exception:
        for it in out:
            it["image"] = ""
    return out
