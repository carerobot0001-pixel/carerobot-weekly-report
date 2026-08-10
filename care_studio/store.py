"""요양시설 스튜디오 — 데이터 저장(로컬 JSON).

**왜 구글시트가 아니라 로컬 파일인가**: 이건 우리 팀 도구(Dolbom Studio)가 아니라
**시설에 들어갈 제품**이다. 이용자 이름·건강 상태가 들어가므로 시연·시험 단계에서
외부로 나가지 않게 이 PC 안에만 둔다. 실제 도입 시 시설 내 서버나 원내 PC로 옮긴다.

파일: care_studio/data/*.json (기기 한 대 기준. 여러 대 동시 편집은 1단계 범위 밖)
"""
import json
import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DATA = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA, exist_ok=True)

# 급여제공기록지 서식 요건(복지부 고시)은 아직 확인하지 못했다.
# 그래서 1단계 항목은 논문(도우누리 워크숍)에서 확인된 하루 일과를 따른다.
# [[확인필요: 급여제공기록지 고시 서식과 항목명]]
CARE_ITEMS = [
    ("등원", "등원 · 차량", "08:00"),
    ("프로그램", "인지·재활 프로그램", "10:00"),
    ("배설", "배설 지원", "11:00"),
    ("식사", "점심 · 식사 지원", "12:00"),
    ("목욕", "목욕 · 위생", "14:00"),
    ("투약", "투약", "13:00"),
    ("활력징후", "활력징후 확인", "09:00"),
    ("하원", "하원 · 차량", "17:00"),
]
ITEM_KEYS = [k for k, _, _ in CARE_ITEMS]
ITEM_LABEL = {k: la for k, la, _ in CARE_ITEMS}
ITEM_TIME = {k: t for k, _, t in CARE_ITEMS}

# 말에서 항목을 알아내는 말뭉치. 요양보호사가 실제로 쓰는 말을 넣는다.
ITEM_WORDS = {
    "배설": ["배설", "기저귀", "화장실", "소변", "대변", "패드"],
    "식사": ["식사", "점심", "밥", "드셨", "식사보조", "간식"],
    "목욕": ["목욕", "샤워", "세면", "위생", "머리감", "손발"],
    "프로그램": ["프로그램", "인지", "체조", "미술", "음악", "작업치료"],
    "투약": ["투약", "약", "복용", "혈압약", "당뇨약"],
    "활력징후": ["활력", "혈압", "체온", "맥박", "혈당", "산소포화도"],
    "등원": ["등원", "도착", "모시고 왔", "차량 승차"],
    "하원": ["하원", "귀가", "모셔다", "차량 하차"],
}
STATUS_WORDS = {
    "완료": ["완료", "했습니다", "마쳤", "끝났", "드렸", "했어요", "함"],
    "거부": ["거부", "안 하시", "싫다", "거절", "안하심"],
    "일부": ["일부", "조금", "절반", "부분"],
}


def _path(name):
    return os.path.join(DATA, f"{name}.json")


def _load(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(name, obj):
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def today():
    return datetime.now(KST).strftime("%Y-%m-%d")


def now_hm():
    return datetime.now(KST).strftime("%H:%M")


# ── 이용자 ────────────────────────────────────────────────────────────
def users():
    return _load("users", [])


def add_user(name, birth="", room="", note="", cautions=""):
    """이용자 등록. `주의사항`은 인계에서 가장 자주 놓치는 것이라 칸을 따로 둔다."""
    name = (name or "").strip()
    if not name:
        raise ValueError("이름은 필수입니다.")
    us = users()
    if any(u["이름"] == name for u in us):
        raise ValueError(f"이미 등록된 이용자입니다 — {name}")
    us.append({"이름": name, "생년": birth.strip(), "자리": room.strip(),
               "메모": note.strip(), "주의사항": cautions.strip(),
               "등록일": today()})
    _save("users", us)
    return us


def delete_user(name):
    _save("users", [u for u in users() if u["이름"] != name])


# ── 케어 기록 ─────────────────────────────────────────────────────────
def records(day=None):
    day = day or today()
    return [r for r in _load("records", []) if r["날짜"] == day]


def add_record(user, item, status="완료", note="", by="", src="화면"):
    """케어 한 건 기록. src='음성'이면 말로 넣은 것(사후 검증용으로 남긴다)."""
    if item not in ITEM_KEYS:
        raise ValueError(f"모르는 항목: {item}")
    rs = _load("records", [])
    rs.append({"날짜": today(), "시각": now_hm(), "이용자": user, "항목": item,
               "상태": status, "특이사항": (note or "").strip(),
               "기록자": by, "입력": src})
    _save("records", rs)


def delete_record(day, time_hm, user, item):
    rs = _load("records", [])
    keep = [r for r in rs
            if not (r["날짜"] == day and r["시각"] == time_hm
                    and r["이용자"] == user and r["항목"] == item)]
    _save("records", keep)


def done_map(day=None):
    """{항목: {이용자, ...}} — 오늘 화면에서 '몇 명 했나'를 세는 데 쓴다."""
    out = {k: set() for k in ITEM_KEYS}
    for r in records(day):
        out.setdefault(r["항목"], set()).add(r["이용자"])
    return out


# ── 말 → 기록 초안 ────────────────────────────────────────────────────
def parse(text, known_users=None):
    """말한 문장에서 (이용자, 항목, 상태, 특이사항) 초안을 뽑는다.

    **자동 확정하지 않는다.** 화면에서 사람이 고친 뒤 저장한다 — 잘못 들은 것을
    그대로 기록으로 남기면 되돌릴 수 없다.
    """
    t = " ".join((text or "").split())
    low = t.lower()
    known = known_users if known_users is not None else [u["이름"] for u in users()]

    user = ""
    for n in sorted(known, key=len, reverse=True):
        if n and n in t:
            user = n
            break

    item = ""
    for key, words in ITEM_WORDS.items():
        if any(w in t for w in words):
            item = key
            break

    status = "완료"
    for st, words in STATUS_WORDS.items():
        if any(w in t for w in words):
            status = st
            break

    # 특이사항은 **원문을 살린다**. 항목 단어까지 지웠더니 "다 드셨어요"가
    # "다 어요"로 깨졌다. 이름과 뒤따르는 '님'만 떼고 나머지는 그대로 둔다.
    note = t.replace(f"{user} 님", " ").replace(f"{user}님", " ") if user else t
    if user:
        note = note.replace(user, " ")
    note = " ".join(note.split()).strip(" ,.")
    return {"이용자": user, "항목": item, "상태": status, "특이사항": note,
            "원문": t}


# ── 일지 ──────────────────────────────────────────────────────────────
def daily_log(user, day=None):
    """이용자 한 명의 하루 기록을 시간순 텍스트로. 일과 끝 일지 작성을 대신한다."""
    day = day or today()
    rs = sorted([r for r in records(day) if r["이용자"] == user],
                key=lambda r: r["시각"])
    if not rs:
        return ""
    lines = []
    for r in rs:
        s = f"{r['시각']}  {ITEM_LABEL.get(r['항목'], r['항목'])} · {r['상태']}"
        if r["특이사항"]:
            s += f" — {r['특이사항']}"
        lines.append(s)
    return "\n".join(lines)
