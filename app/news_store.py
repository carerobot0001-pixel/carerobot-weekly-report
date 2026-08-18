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
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests
import streamlit as st

# 구글뉴스 로케일 — 이걸 안 바꾸면 무슨 키워드를 넣어도 그 나라 기사만 나온다
KO = "hl=ko&gl=KR&ceid=KR:ko"
EN = "hl=en-US&gl=US&ceid=US:en"
JA = "hl=ja&gl=JP&ceid=JP:ja"

# (탭 이름, ((키워드, 로케일), ...)) — 탭을 누르면 섹션별로 다른 기사가 나옴
# 탭 이름에 이모지를 안 쓴다 — 국기(🇰🇷)는 윈도우에서 'KR' 글자로 나오고,
# 이모지마다 폭이 달라 탭 줄이 들쭉날쭉해진다.
#
# 섹션 구성은 **매일 받는 뉴스 브리핑의 편집 지침**을 따라 나눴다(2026-08):
#   · 돌봄 = '사람 돌봄(정책·인력·제도)' 과 '돌봄로봇·보조기술' 두 축
#   · AI  = '기술 동향' 과 '실전 활용법(프롬프트·RAG)' 두 축
# ⚠️ 다만 키워드 검색은 지침의 **판단**까지 못 한다 — "투자 유치 헤드라인 말고 실질",
#    "정말로 새로운 기법인가", "왜 중요한가"는 사람이나 모델이 읽어야 가려진다.
#    여기서 맞출 수 있는 건 *어떤 주제를 긁어오는가* 까지다.
# 각 키워드는 실제 조회해 수확이 좋은 것만 남겼다(2026-08 확인).
# **2026-08: 앞쪽 탭을 복지부 11개 과제 그대로로 바꿨다.** 예전 주제별 5탭
# (돌봄로봇·돌봄정책·AI·LLM·AI 활용법·로봇휴머노이드)은 과제와 대응이 안 맞아
# "이 기사가 어느 과제 것이냐"를 사람이 다시 갈라야 했다.
#
# 키워드 출처: `과제별_자료조사_키워드_프롬프트_양식.xlsx` — 각 과제 담당자가 직접 적은 것.
# ⚠️ **엑셀 키워드를 그대로 다 넣지는 못한다.** 두 가지 이유:
#   · 논문 검색용 불리언(9번 식사는 `("식사보조로봇" OR …) AND (…) AND (…)`)은
#     구글뉴스 RSS가 못 삼킨다 → 핵심 명사만 뽑았다.
#   · 학술 용어(CycleGAN·Domain Adaptation·근전도)는 뉴스가 거의 안 잡힌다.
# 그래서 **뉴스로 수확되는 것만** 골랐다. 원본 키워드 전체는 위 엑셀에 있다.
# 담당자가 키워드를 고치면 이 목록도 같이 고칠 것.
#
# 2·3번(목욕·배설)은 엑셀이 아직 비어 있다 → **탭만 만들고 비워 둔다.**
# 11번 AI 챗봇도 엑셀은 비었으나, 기존 'AI 활용법' 키워드를 이리로 옮겼다(지시).
NEWS_SECTIONS = [
    # 1 이동 — 100mm 단차극복 (남재엽)
    ("1 이동", (("노인 이동 보조 로봇", KO), ("보행 보조 로봇", KO),
                ("전동휠체어 문턱", KO), ("낙상 예방", KO),
                ("gait assistance robot", EN),
                ("indoor mobility assistance elderly", EN))),
    # 2 목욕 — 이동가능·가변형. 엑셀 키워드 미작성
    ("2 목욕", ()),
    # 3 배설 — 배설 양상 관리·배설유도. 엑셀 키워드 미작성
    ("3 배설", ()),
    # 4 유연착용형 — 의복·속옷형태, 하이브리드 (한벼리)
    # ⚠️ '외골격 로봇'은 0건이다(붙여 쓰면 안 잡힌다). '착용형 로봇'·'엑소슈트'로 쓸 것
    ("4 유연착용형", (("웨어러블 로봇", KO), ("착용형 로봇", KO),
                      ("엑소슈트", KO), ("소프트 외골격", KO),
                      ("wearable robot exosuit", EN),
                      ("soft exoskeleton", EN),
                      ("装着型 ロボット 介護", JA))),
    # 5 인체영향성 — 근력보조 신체영향성 (한벼리). 4번과 키워드가 같아
    #   임상·대사·재활 쪽 용어로 갈랐다(같은 엑셀 행에서 뽑음)
    ("5 인체영향성", (("외골격 임상시험", KO), ("보행 재활 로봇", KO),
                      ("뇌졸중 재활 로봇", KO),
                      ("exoskeleton clinical trial", EN),
                      ("exoskeleton metabolic cost", EN),
                      ("gait rehabilitation robot stroke", EN))),
    # 6 모니터링 — 요양시설중심·정보통합형 (류현경). 일본이 見守り 중심지라 JA 포함
    # ⚠️ '비접촉 모니터링 센서'·'생체정보 모니터링'은 **논문 용어**라 기사 제목에 안 쓴다
    #    (24시간 0건). 기사에 실제로 쓰는 말로 바꿨다.
    ("6 모니터링", (("낙상 감지", KO), ("스마트 돌봄 센서", KO),
                    ("AI 돌봄 모니터링", KO),
                    ("contactless vital sign monitoring", EN),
                    ("remote patient monitoring elderly", EN),
                    ("見守り センサー 介護", JA))),
    # 7 이승 — 협소공간 사용·리포지셔닝 (남재엽)
    ("7 이승", (("이승 보조 로봇", KO), ("환자 이송 보조", KO),
                ("리포지셔닝 침대", KO),
                ("patient transfer robot", EN),
                ("bed to wheelchair transfer device", EN),
                ("移乗 支援 ロボット", JA))),
    # 8 욕창 — 초저소음·호환성 (이경진)
    # ⚠️ '스마트베드' 단독은 쓰지 말 것 — 24시간 10건이 전부 수면가구(모션베드) 기사다
    ("8 욕창", (("욕창", KO), ("욕창 예방 매트리스", KO),
                ("체위변환 침대", KO), ("스마트베드 욕창", KO),
                ("pressure injury prevention device", EN),
                ("smart mattress pressure ulcer", EN),
                ("alternating pressure mattress", EN))),
    # 9 식사 — 휴대성·융합형 (이윤환). 엑셀은 긴 불리언 → 핵심 명사만
    ("9 식사", (("식사보조로봇", KO), ("식사 지원 로봇", KO),
                ("식사보조기기", KO),
                ("feeding assistance robot", EN),
                ("robot-assisted feeding", EN),
                ("食事 支援 ロボット", JA))),
    # 10 커뮤니케이션 — 가정/병원 중심·현장소통 (김건양)
    # ⚠️ '고독사 예방'을 뺐다 — 뉴스에서는 **지자체 복지행정**만 물어와서(하루 7건)
    #    로봇 기사가 통째로 묻혔다. 과제는 커뮤니케이션 로봇이다.
    ("10 커뮤니케이션", (("소셜로봇", KO), ("반려로봇 노인", KO),
                        ("독거노인 돌봄 로봇", KO), ("말벗 로봇", KO),
                        ("socially assistive robot", EN),
                        ("companion robot loneliness", EN))),
    # 11 AI 챗봇 — 비대면·시니어 헬스케어. 엑셀 칸은 비었지만,
    #   `11. AI챗봇/AI챗봇_유사서비스_자료조사_202608.xlsx`(자체 조사)의 조사 축을 옮겼다:
    #   AI 안부전화(클로바 케어콜·NUGU·KT AI케어) / AI 생활지원사 / 디지털휴먼·AI 아바타 /
    #   시니어 특화 STT / 식단 이미지 영양분석.
    #   ※ 예전에 여기 넣었던 'AI 활용법'(프롬프트·RAG·업무자동화)은 뺐다 — 과제와 무관.
    ("11 AI 챗봇", (("시니어 AI 챗봇", KO), ("AI 안부전화", KO),
                    ("AI 돌봄 콜", KO), ("디지털 휴먼 아바타", KO),
                    ("시니어 헬스케어 AI", KO),
                    ("senior care chatbot", EN),
                    ("conversational agent older adults", EN),
                    ("digital human avatar healthcare", EN))),
    # 과제에 안 걸리는 가로축 하나 — 제도·인력·치매·재가.
    # 과제 키워드는 전부 '기기' 쪽이라 제도·수가·인력 소식은 어느 탭에도 안 걸린다.
    # (AI·LLM / 로봇·휴머노이드 탭은 11개 과제로 바꾸며 없앴다)
    ("돌봄·정책", (("장기요양보험 제도", KO), ("요양보호사 처우", KO),
                    ("치매 돌봄 정책", KO), ("재가 돌봄 서비스", KO),
                    ("long-term care workforce policy", EN))),
    # ── 아래 4개는 업무 밖 일반 뉴스(세계·한국·경제·축구).
    #    매일 받는 뉴스 브리핑 PPT의 섹션 구성을 그대로 가져왔다.
    #    일반 분야는 키워드 검색보다 **구글뉴스 토픽 피드**가 훨씬 낫다 —
    #    편집된 헤드라인이 와서 잡음이 적다. `topic:` 접두어로 쓴다.
    # 과제가 아니라 **일하는 방법** — 프롬프트·RAG·업무 자동화.
    # 11 AI 챗봇에 잠깐 넣었다가 뺐다: 과제(시니어 챗봇) 기사가 활용법 기사에 묻혔다.
    ("AI 활용법", (("프롬프트 엔지니어링", KO), ("AI 업무 자동화 사례", KO),
                  ("AI 도구 활용법", KO),
                  ("prompt engineering technique", EN),
                  ("RAG retrieval technique", EN),
                  ("AI workflow productivity guide", EN))),
    # 일반 뉴스는 경제·시장 하나만 남겼다(세계·한국·축구는 뺌). 맨 뒤가 제자리다
    ("경제·시장", (("topic:BUSINESS", KO), ("코스피 환율", KO),
                  ("Federal Reserve rate decision", EN))),
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
    """`_translate` 의 캐시판(외부 호출용)."""
    return _translate(text, src)


def _translate(text: str, src: str) -> str:
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
        out = "".join(part[0] for part in r.json()[0]).strip()
        for wrong, right in _GLOSSARY.items():
            out = out.replace(wrong, right)
        return out
    except Exception:
        return ""


# 기계번역이 기술 용어를 통째로 잘못 옮기는 것만 바로잡는다.
# (뜻을 바꾸는 '의역'은 하지 않는다 — 틀린 게 확인된 것만 넣을 것)
# 'prompt engineering' 의 prompt 를 '신속한'으로 옮기는 게 대표적이다.
_GLOSSARY = {
    "신속한 엔지니어링": "프롬프트 엔지니어링",
    "신속한 주입": "프롬프트 주입",
}


def _age_hours(item) -> float:
    """기사가 나온 지 몇 시간 됐나. pubDate가 없거나 깨지면 아주 큰 값(=버림)."""
    raw = (item.findtext("pubDate") or "").strip()
    if not raw:
        return 1e9
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 1e9


# 검색어 토큰에서 뺄 말 — 아무 기사에나 있어서 걸러내는 힘이 없다
# 검색어 토큰에서 뺄 말 — 아무 기사에나 있어서 걸러내는 힘이 없다.
# 국문의 '예방·지원·사업'을 뺀 이유: `낙상 예방` 으로 검색했더니 '부정수급 예방 교육'이
# 통과했다(제목에 '예방'만 있어도 한 낱말 규칙을 만족). 남는 낱말(낙상)로만 판정한다.
_STOP = {"older", "adults", "elderly", "device", "technique", "guide",
         "system", "care", "robot", "ai", "the", "for", "with", "and",
         "예방", "지원", "사업", "교육", "확대", "관리", "서비스", "기기",
         # 일본어도 같은 이유 — `食事 支援 ロボット` 인데 '手術支援ロボット'(수술)이
         # 支援+ロボット 두 낱말로 통과했다. 판정은 남는 낱말(食事)로만 한다.
         "支援", "ロボット"}


def _relevant(title: str, q: str) -> bool:
    """제목에 검색어의 낱말이 하나라도 들어 있나.

    **왜 필요한가**: 구글뉴스는 낱말을 느슨하게 맞춰서, `노인 이동 보조 로봇` 으로
    검색하면 '피매치 AI 약물안전 투자유치' 같은 기사도 딸려 온다. 예전에는 섹션당
    6건만 담아 눈에 잘 안 띄었는데, 개수 제한을 없애니 이런 게 그대로 쌓였다.
    → 제목에 낱말이 실제로 나오는 것만 남긴다. **억지로 끼워넣지 않는다**(지시).
    **국문은 한 낱말, 영문은 두 낱말**을 요구한다. 국문 제목은 낱말 하나가 이미
    구체적이라(`욕창`) 한 개면 충분한데, 영문은 `mattress` 하나로 침구 쇼핑 기사가
    딸려 왔다(`alternating pressure mattress` → "The 11 Best Cooling Mattresses").
    다 맞추라고 하면 멀쩡한 기사까지 떨어지므로 두 개까지만 요구한다.
    """
    t = title.lower()
    # ⚠️ 일본어(移乗 支援 ロボット)를 낱말로 안 쪼개면 토큰이 0개가 되어
    #    **아무거나 통과**했다 — 그래서 '이승' 탭에 LOVOT 기사가, '식사' 탭에
    #    수술로봇 시장 리포트가 들어왔다. 가나·한자도 낱말 글자로 넣는다.
    _WORD = r"[^0-9A-Za-z가-힣぀-ヿ一-鿿]+"
    toks = [w for w in re.split(_WORD, q.lower()) if w]
    cjk = bool(re.search(r"[가-힣぀-ヿ一-鿿]", q))
    toks = [w for w in toks
            if w not in _STOP
            and (len(w) >= 2 if re.search(
                r"[가-힣぀-ヿ一-鿿]", w) else len(w) >= 4)]
    if not toks:                       # 전부 흔한 낱말이면 거르지 않는다
        return True
    need = 1 if cjk else min(2, len(toks))
    return sum(1 for w in toks if w in t) >= need


def _key_tokens(title: str) -> set:
    """제목을 낱말 뭉치로. 같은 사건을 다르게 쓴 제목을 알아보려고 쓴다."""
    return {w for w in re.split(
        r"[^0-9A-Za-z가-힣぀-ヿ一-鿿]+", title.lower())
        if len(w) >= 2}


def _near_dup(toks: set, kept: list) -> bool:
    """이미 담은 것과 사실상 같은 기사인가(낱말 절반 이상 겹침).

    **왜**: 같은 사건을 여러 매체가 조금씩 다르게 쓴다 —
    '엔젤로보틱스, 베트남 재활로봇 심포지엄 개최' 와
    '엔젤로보틱스, 베트남서 국제 로봇 재활 심포지엄 개최…아세안 시장 공략'.
    제목 완전일치로만 걸러서 한 탭에 같은 소식이 두세 줄씩 쌓였다.
    """
    if not toks:
        return False
    for k in kept:
        if not k:
            continue
        inter = len(toks & k)
        if inter / min(len(toks), len(k)) >= 0.6:
            return True
    return False


def _fetch_specs(specs, max_age_h: int = 24, cap: int = 0) -> list:
    """[{title, link, source, region, hours}] — 최근 24시간 기사 전부, 최신순.

    **개수 제한이 없다**(2026-08 지시). 예전엔 섹션당 6건으로 자르고 키워드를
    번갈아 담았는데(라운드로빈), 그러면 *없는 뉴스를 억지로 채우지는 않는 대신*
    **있는 뉴스가 잘려 나갔다**. 지금은 걸리는 만큼 다 보여주고, 없으면 안 보여준다.

    **하루 지난 기사는 버린다** — 매일 새 것만 나오게. 두 겹으로 막는다:
      ① 검색어에 구글뉴스의 `when:1d` 를 붙여 애초에 최근 것만 받는다
      ② 그래도 오래된 게 섞여 오므로 `pubDate` 로 다시 거른다(토픽 피드는 ①이 안 먹는다)
    """
    seen, kept, out = set(), [], []
    for q, loc in specs:
        try:
            # `topic:BUSINESS` 처럼 오면 검색이 아니라 구글뉴스 **토픽 피드**를 쓴다
            # (경제 같은 넓은 분야는 편집된 헤드라인이 훨씬 깨끗하다).
            # ⚠️ 토픽 피드에는 `when:` 을 못 붙인다 — pubDate 로만 거른다.
            if q.startswith("topic:"):
                url = ("https://news.google.com/rss/headlines/section/topic/"
                       f"{quote(q[len('topic:'):])}?{loc}")
            else:
                url = (f"https://news.google.com/rss/search?"
                       f"q={quote(q + ' when:1d')}&{loc}")
            r = requests.get(url, timeout=8, headers=_UA)
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                age = _age_hours(item)
                if age > max_age_h:
                    continue
                title = (item.findtext("title") or "").strip()
                title = title.rsplit(" - ", 1)[0] if " - " in title else title
                link = (item.findtext("link") or "").strip()
                src_el = item.find("{*}source")
                source = src_el.text if src_el is not None else ""
                if not title or not link or title in seen:
                    continue
                _tk = _key_tokens(title)
                if _near_dup(_tk, kept):      # 같은 사건을 다르게 쓴 제목
                    continue
                # 토픽 피드(경제 등)는 키워드가 없으니 걸러내지 않는다
                if not q.startswith("topic:") and not _relevant(title, q):
                    continue
                seen.add(title)
                kept.append(_tk)
                out.append({"title": title, "link": link, "source": source,
                            "region": _region(loc), "lang": _src_lang(loc),
                            "hours": age})
        except Exception:
            pass

    out.sort(key=lambda it: it["hours"])          # 최신순
    if cap:                                       # 자를 거면 **번역 전에** 자른다
        out = out[:cap]
    return _with_ko(out)


def _with_ko(items):
    """해외 기사에 한국어 제목(`title_ko`)을 붙인다.

    ⚠️ 개수 제한을 없애면서 해외 기사가 수십 건이 됐다. 하나씩 번역하면 제목 하나에
    0.3~1초라 **그날 처음 연 사람이 몇십 초를 기다린다** → 8개씩 동시에 부른다.
    (`st.cache_data` 를 붙인 `translate` 대신 맨 함수를 쓴다 — 워커 스레드에는
    스크립트 컨텍스트가 없어 캐시가 경고를 낸다. 결과는 `fetch_section` 캐시에 남는다.)
    """
    todo = [it for it in items if it.get("region") == "해외"]
    if not todo:
        return items
    with ThreadPoolExecutor(max_workers=8) as ex:
        for it, ko in zip(todo, ex.map(
                lambda x: _translate(x["title"], x.get("lang", "en")), todo)):
            it["title_ko"] = ko
    return items


def today_key() -> str:
    """오늘 날짜(KST) — 캐시 키로 쓴다. 날짜가 바뀌면 자동으로 새로 수집된다."""
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


# ⚠️ `day` 는 안 쓰는 인자처럼 보이지만 **캐시 키**다. 날짜가 바뀔 때만 다시 수집하고
#    같은 날에는 처음 연 사람이 가져온 목록을 하루 종일 모두가 같이 본다.
#    (예약 실행 장치 없이 '하루 1회 수집 · 매일 교체'를 만드는 방법)
#    ttl은 이틀 — 자정 직후에도 어제 것이 남아 있지 않게 날짜 키가 먼저 갈린다.
# 섹션별 개수 상한 — 여기 없는 탭은 **제한 없음**(걸리는 대로 다).
# 경제·시장만 자른다: 토픽 피드라 관련성 필터가 안 걸려 하루 100건씩 쌓인다.
SECTION_CAP = {"경제·시장": 10}


@st.cache_data(ttl=172800, show_spinner=False)
def fetch_section(specs: tuple, day: str, max_age_h: int = 24,
                  cap: int = 0) -> list:
    """한 섹션의 최근 24시간 기사(국내·해외 섞임, 최신순). day = today_key().

    `cap=0`이면 개수 제한 없음 — 걸리는 대로 다 준다. 해당 과제에 그날 뉴스가 없으면
    **빈 목록**이다(억지로 채우지 않는다). 화면에는 '오늘은 새 뉴스가 없습니다'.
    """
    return _fetch_specs(list(specs), max_age_h=max_age_h, cap=cap)


@st.cache_data(ttl=172800, show_spinner=False)
def fetch_news(day: str, max_age_h: int = 24) -> list:
    """전체 합본(돌봄 우선). 섹션 탭을 쓰지 않는 곳의 호환용."""
    return _fetch_specs(list(_ALL_SPECS), max_age_h=max_age_h)
