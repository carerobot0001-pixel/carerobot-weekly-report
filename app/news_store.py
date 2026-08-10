"""사업단 관련 뉴스 — 구글 뉴스 RSS. 섹션(카테고리)별로 다른 기사를 보여준다.

돌봄·돌봄로봇 우선, AI·신기술(LLM 등)·로봇 보조. API 키 불필요.

**국내만 나오던 문제(2026-08 수정)**: 구글뉴스 RSS는 `hl/gl/ceid` 로 언어·지역이
정해진다. 예전엔 전부 `hl=ko&gl=KR` 이라 **한국어 기사만** 들어왔다. 지금은 섹션마다
한국어 + 영어 + 일본어 키워드를 함께 조회하고 `region`('국내'/'해외')을 붙인다.
일본은 개호로봇 정책·도입지원 사업이 우리 벤치마크 대상이라 따로 넣었다.

⚠️ RSS의 `description` 은 **기사 요약이 아니라 링크 HTML** 이다(확인함). 그래서
제목·출처만 쓴다. 요약을 붙이려면 기사 본문을 읽는 별도 수단이 필요하다.
섹션/키워드가 바뀌면 NEWS_SECTIONS만 수정.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests
import streamlit as st

# 구글뉴스 로케일 — 이걸 안 바꾸면 무슨 키워드를 넣어도 그 나라 기사만 나온다
KO = "hl=ko&gl=KR&ceid=KR:ko"
EN = "hl=en-US&gl=US&ceid=US:en"
JA = "hl=ja&gl=JP&ceid=JP:ja"

# (탭 이름, ((키워드, 로케일), ...)) — 탭을 누르면 섹션별로 다른 기사가 나옴
NEWS_SECTIONS = [
    ("🤖 돌봄로봇", (("돌봄로봇", KO), ("돌봄 로봇 서비스", KO),
                  ("care robot older adults", EN), ("介護ロボット", JA))),
    ("🧑‍🦳 돌봄·복지", (("노인 돌봄 로봇", KO), ("보건복지부 돌봄", KO),
                    ("eldercare technology policy", EN),
                    ("介護 テクノロジー 導入支援", JA))),
    ("✨ AI·신기술", (("생성형 AI 의료", KO), ("AI 돌봄 서비스", KO),
                   ("AI caregiving assistive", EN))),
    ("🦿 로봇·휴머노이드", (("휴머노이드 로봇", KO), ("서비스 로봇", KO),
                       ("humanoid service robot", EN))),
]
# 전체 합본용(구버전 홈 호환)
_ALL_SPECS = tuple(s for _, specs in NEWS_SECTIONS for s in specs)
_UA = {"User-Agent": "Mozilla/5.0"}


def _region(loc: str) -> str:
    return "국내" if loc == KO else "해외"


def _src_lang(loc: str) -> str:
    return "ja" if loc == JA else "en"


@st.cache_data(ttl=86400, show_spinner=False)
def translate(text: str, src: str) -> str:
    """해외 기사 제목을 한국어로. 실패하면 빈 문자열(원문만 보여준다).

    구글 번역의 키 없는 endpoint를 쓴다 — 무료·무설정이지만 **공식 API가 아니라
    막히거나 바뀔 수 있다.** 그래서 실패를 정상 경로로 취급하고 원문으로 돌아간다.
    ⚠️ 기계번역이라 틀린다. 실제로 `令和8年度`(2026년도)를 '2007년'으로 옮겼다.
    그래서 화면에는 **원문 제목을 함께** 보여주고, 인용할 때는 원문을 봐야 한다.
    """
    t = (text or "").strip()
    if not t:
        return ""
    try:
        url = ("https://translate.googleapis.com/translate_a/single?client=gtx"
               f"&sl={src}&tl=ko&dt=t&q={quote(t)}")
        r = requests.get(url, timeout=6, headers=_UA)
        if r.status_code != 200:
            return ""
        return "".join(part[0] for part in r.json()[0]).strip()
    except Exception:
        return ""


def _fetch_specs(specs, per_query: int = 3, cap: int = 6) -> list:
    """[{title, link, source, region}] — (키워드, 로케일) 목록에서 중복 제거 후 최대 cap개.

    국내만 채우고 끝나지 않도록 **키워드를 번갈아** 한 건씩 담는다(라운드로빈).
    한 키워드에서 몰아 담으면 뒤의 해외 키워드가 cap에 걸려 아예 안 나온다.
    """
    buckets = []
    for q, loc in specs:
        got = []
        try:
            url = f"https://news.google.com/rss/search?q={quote(q)}&{loc}"
            r = requests.get(url, timeout=8, headers=_UA)
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                title = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = (item.findtext("link") or "").strip()
                src_el = item.find("{*}source")
                source = src_el.text if src_el is not None else ""
                if not title or not link:
                    continue
                got.append({"title": title, "link": link, "source": source,
                            "region": _region(loc), "lang": _src_lang(loc)})
                if len(got) >= per_query:
                    break
        except Exception:
            pass
        buckets.append(got)

    seen, out = set(), []
    for i in range(per_query):
        for b in buckets:
            if i < len(b) and b[i]["title"] not in seen:
                seen.add(b[i]["title"])
                out.append(b[i])
                if len(out) >= cap:
                    return _with_ko(out)
    return _with_ko(out)


def _with_ko(items):
    """해외 기사에 한국어 제목(`title_ko`)을 붙인다. 담긴 것만 번역해 호출을 아낀다."""
    for it in items:
        if it.get("region") == "해외":
            it["title_ko"] = translate(it["title"], it.get("lang", "en"))
    return items


def today_key() -> str:
    """오늘 날짜(KST) — 캐시 키로 쓴다. 날짜가 바뀌면 자동으로 새로 수집된다."""
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


# ⚠️ `day` 는 안 쓰는 인자처럼 보이지만 **캐시 키**다. 날짜가 바뀔 때만 다시 수집하고
#    같은 날에는 처음 연 사람이 가져온 목록을 하루 종일 모두가 같이 본다.
#    (예약 실행 장치 없이 '하루 1회 수집 · 매일 교체'를 만드는 방법)
#    ttl은 이틀 — 자정 직후에도 어제 것이 남아 있지 않게 날짜 키가 먼저 갈린다.
@st.cache_data(ttl=172800, show_spinner=False)
def fetch_section(specs: tuple, day: str, cap: int = 8) -> list:
    """한 섹션의 기사 목록(국내·해외 섞임). 섹션 탭용. day = today_key()."""
    return _fetch_specs(list(specs), per_query=3, cap=cap)


@st.cache_data(ttl=172800, show_spinner=False)
def fetch_news(day: str, per_query: int = 2, cap: int = 9) -> list:
    """전체 합본(돌봄 우선). 섹션 탭을 쓰지 않는 곳의 호환용."""
    return _fetch_specs(list(_ALL_SPECS), per_query=per_query, cap=cap)
