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

# ── 급여제공기록지(주·야간보호) — 노인장기요양보험법 시행규칙 별지 제15호서식
#    <개정 2019. 9. 27.> 원문에서 옮긴 항목이다. 임의로 만든 것이 아니다.
#    출처: 국가법령정보센터 별지 제15호서식 PDF (2026-08 확인)
#
# 유형
#   check   제공 여부 체크
#   bath    목욕 — 소요시간(분) + 방법(전신입욕/샤워식)
#   meal    식사 — 종류(일반식/죽/유동식(미음)) + 섭취량(1 / 1/2이상 / 1/2미만)
#   count   횟수 (화장실 이용 = 급여제공시간 동안 소변·대변 총 횟수, 기저귀는 교환 횟수)
#   vitals  혈압 / 체온
#   program 제공한 프로그램명을 적는다(서식 유의사항 5)
SECTIONS = [
    ("신체활동지원", [
        ("세면등", "세면·구강·머리감기·몸단장·옷 갈아입히기", "check"),
        ("목욕", "목욕", "bath"),
        ("식사", "식사", "meal"),
        ("화장실", "화장실 이용하기(기저귀 교환)", "count"),
        ("이동도움", "이동도움 및 신체기능 유지·증진", "check"),
    ]),
    ("간호 및 처치", [
        ("활력징후", "혈압 / 체온", "vitals"),
        ("욕창관리", "욕창관리", "check"),
        ("투약관리", "투약관리", "check"),
    ]),
    ("기능회복훈련", [
        ("프로그램", "신체·인지기능 향상 프로그램", "program"),
        ("신체기능훈련", "신체기능·기본동작·일상생활동작 훈련", "check"),
        ("인지훈련", "인지·정신기능 훈련", "check"),
        ("물리작업치료", "물리(작업)치료", "check"),
    ]),
]
SECTION_NAMES = [s for s, _ in SECTIONS]
FIELDS = {k: (sec, label, typ)
          for sec, items in SECTIONS for k, label, typ in items}
FIELD_KEYS = list(FIELDS)
BATH_WAYS = ["전신입욕", "샤워식"]
MEAL_KINDS = ["일반식", "죽", "유동식(미음)"]
MEAL_AMOUNTS = ["1", "1/2이상", "1/2미만"]

# 옛 이름(임시로 쓰던 8항목)을 새 서식 항목으로 옮기는 표.
# 음성 인식 말뭉치와 기존 데이터가 이 이름을 쓰고 있었다.
LEGACY = {"배설": "화장실", "식사": "식사", "목욕": "목욕",
          "프로그램": "프로그램", "투약": "투약관리",
          "활력징후": "활력징후", "등원": "이동도움", "하원": "이동도움"}

# 말에서 항목을 알아내는 말뭉치. 요양보호사가 실제로 쓰는 말을 넣는다.
ITEM_WORDS = {
    "화장실": ["화장실", "기저귀", "배설", "소변", "대변", "패드", "배뇨", "배변"],
    "식사": ["식사", "점심", "밥", "드셨", "간식", "섭취"],
    "목욕": ["목욕", "샤워", "입욕"],
    "세면등": ["세면", "양치", "구강", "머리감", "몸단장", "면도", "옷 갈아"],
    "이동도움": ["이동", "부축", "휠체어", "보행", "산책", "차량", "등원", "하원"],
    "활력징후": ["활력", "혈압", "체온", "맥박", "열", "재고"],
    "욕창관리": ["욕창", "짓물", "드레싱", "연고"],
    "투약관리": ["투약", "약", "복용", "좌약"],
    "프로그램": ["프로그램", "체조", "회상", "음악", "원예", "종이접기", "나들이"],
    "인지훈련": ["인지", "기억", "회상훈련", "판단"],
    "신체기능훈련": ["근력", "관절", "일어나", "균형", "보장구", "일상생활동작"],
    "물리작업치료": ["물리치료", "작업치료", "온열", "전기치료"],
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


# ── 급여제공기록지 (이용자 1명 × 하루 1장) ────────────────────────────
# 서식이 '수급자별 일자별 1장'이라 데이터도 그렇게 잡는다.
# 화면 체크든 음성이든 결국 이 한 장을 채운다.
#   sheets = {날짜: {이용자: {"필드": {키: 값}, "특이": {구역: 글},
#                            "작성자": {구역: 이름}, "세션": {...}}}}
# 값 모양: check → True / bath → {"분":int,"방법":str} / meal → {"종류":,"섭취량":}
#          count → int / vitals → {"혈압":str,"체온":str} / program → "프로그램명"


def _sheets():
    return _load("sheets", {})


def sheet(user, day=None):
    day = day or today()
    d = _sheets().get(day, {}).get(user, {})
    return {"필드": d.get("필드", {}), "특이": d.get("특이", {}),
            "작성자": d.get("작성자", {}), "세션": d.get("세션", {})}


def set_field(user, key, value, by="", day=None, src="화면"):
    """서식 한 칸 채우기. 값이 None 이면 지운다."""
    if key not in FIELDS:
        raise ValueError(f"서식에 없는 항목: {key}")
    day = day or today()
    all_ = _sheets()
    cell = all_.setdefault(day, {}).setdefault(user, {})
    f = cell.setdefault("필드", {})
    if value is None:
        f.pop(key, None)
    else:
        f[key] = value
    sec = FIELDS[key][0]
    cell.setdefault("작성자", {})[sec] = by          # 서식 유의사항 7 — 구역별 서명
    _save("sheets", all_)
    _log(day, user, key, value, by, src)


def set_section_note(user, section, text, by="", day=None):
    """구역별 특이사항. 서식 유의사항 6 — 상태변화와 조치를 적는 칸이다."""
    day = day or today()
    all_ = _sheets()
    cell = all_.setdefault(day, {}).setdefault(user, {})
    cell.setdefault("특이", {})[section] = (text or "").strip()
    if by:
        cell.setdefault("작성자", {})[section] = by
    _save("sheets", all_)


def set_session(user, start="", end="", ride=False, car="", day=None):
    """급여 시작·종료시각과 이동서비스(차량번호). 서식 앞쪽 머리 부분."""
    day = day or today()
    all_ = _sheets()
    cell = all_.setdefault(day, {}).setdefault(user, {})
    cell["세션"] = {"시작": start, "종료": end, "이동": bool(ride), "차량": car}
    _save("sheets", all_)


def total_minutes(user, day=None):
    """총시간 — 시작·종료가 다 있을 때만 계산한다. 없으면 None."""
    se = sheet(user, day).get("세션", {})
    a, b = (se.get("시작") or "").strip(), (se.get("종료") or "").strip()
    try:
        h1, m1 = map(int, a.split(":"))
        h2, m2 = map(int, b.split(":"))
        return max(0, (h2 * 60 + m2) - (h1 * 60 + m1))
    except Exception:
        return None


def filled(user, day=None):
    """채워진 항목 키 집합."""
    return set(sheet(user, day)["필드"].keys())


def done_map(day=None):
    """{항목키: {이용자,...}} — 홈에서 '몇 명 남았나' 세는 데 쓴다."""
    out = {k: set() for k in FIELD_KEYS}
    day = day or today()
    for user, cell in _sheets().get(day, {}).items():
        for k in cell.get("필드", {}):
            out.setdefault(k, set()).add(user)
    return out


# ── 입력 기록(감사용) ─────────────────────────────────────────────────
# 서식 자체는 '최종 상태'만 담는다. 누가 언제 무엇을 어떤 방법으로 넣었는지는
# 따로 남긴다 — 음성 인식이 틀렸을 때 되짚으려면 이게 있어야 한다.
def _log(day, user, key, value, by, src):
    rs = _load("records", [])
    rs.append({"날짜": day, "시각": now_hm(), "이용자": user, "항목": key,
               "값": value, "기록자": by, "입력": src})
    _save("records", rs)


def records(day=None):
    day = day or today()
    return [r for r in _load("records", []) if r["날짜"] == day]


def value_text(key, value):
    """서식 값 한 칸을 사람이 읽는 문장으로."""
    typ = FIELDS[key][2]
    if value is None:
        return ""
    if typ == "check":
        return "제공" if value else ""
    if typ == "count":
        return f"{value}회"
    if typ == "bath":
        v = value or {}
        return f"{v.get('분', '')}분 · {v.get('방법', '')}".strip(" ·")
    if typ == "meal":
        v = value or {}
        return f"{v.get('종류', '')} · 섭취량 {v.get('섭취량', '')}".strip(" ·")
    if typ == "vitals":
        v = value or {}
        return f"혈압 {v.get('혈압', '-')} / 체온 {v.get('체온', '-')}"
    return str(value)


# ── 출결 ──────────────────────────────────────────────────────────────
# 주간보호센터는 출퇴근형이라 '오늘 누가 왔나'가 하루의 출발점이다.
ATT = ["등원", "결석", "미확인"]


def attendance(day=None):
    """{이용자: 상태}. 기록이 없으면 '미확인'."""
    day = day or today()
    saved = _load("attend", {}).get(day, {})
    return {u["이름"]: saved.get(u["이름"], "미확인") for u in users()}


def set_attendance(user, state, day=None):
    if state not in ATT:
        return
    day = day or today()
    all_ = _load("attend", {})
    all_.setdefault(day, {})[user] = state
    _save("attend", all_)


# ── 직원 ──────────────────────────────────────────────────────────────
def staff():
    return _load("staff", [])


def add_staff(name, role="요양보호사"):
    name = (name or "").strip()
    if not name:
        raise ValueError("이름은 필수입니다.")
    ss = staff()
    if any(s["이름"] == name for s in ss):
        raise ValueError(f"이미 있는 직원 — {name}")
    ss.append({"이름": name, "직무": role})
    _save("staff", ss)


def delete_staff(name):
    _save("staff", [s for s in staff() if s["이름"] != name])


# ── 공지 ──────────────────────────────────────────────────────────────
def notices():
    return sorted(_load("notices", []), key=lambda n: n["등록"], reverse=True)


def add_notice(text, by=""):
    text = (text or "").strip()
    if not text:
        return
    ns = _load("notices", [])
    ns.append({"내용": text, "작성자": by,
               "등록": datetime.now(KST).strftime("%Y-%m-%d %H:%M")})
    _save("notices", ns)


def delete_notice(stamp):
    _save("notices", [n for n in _load("notices", []) if n["등록"] != stamp])


# ── 인계 ──────────────────────────────────────────────────────────────
# 논문 AS-IS 문제 2(정서·인지 부담)에서 나온 것 — 다음 교대가 알아야 할 것이
# 사람 머릿속에만 있다. 이용자와 연결해 남긴다.
HANDOVER_KINDS = ["건강", "정서·행동", "가족 연락", "기기·환경", "기타"]


def handovers(day=None):
    day = day or today()
    return [h for h in _load("handover", []) if h["날짜"] == day]


def add_handover(user, kind, text, by=""):
    text = (text or "").strip()
    if not text:
        return
    hs = _load("handover", [])
    hs.append({"날짜": today(), "시각": now_hm(), "이용자": user,
               "종류": kind, "내용": text, "작성자": by, "확인": ""})
    _save("handover", hs)


def ack_handover(day, time_hm, user, who):
    """다음 교대가 '봤다'고 표시. 누가 언제 봤는지 남긴다."""
    hs = _load("handover", [])
    for h in hs:
        if h["날짜"] == day and h["시각"] == time_hm and h["이용자"] == user:
            h["확인"] = f"{who} {now_hm()}"
    _save("handover", hs)


def delete_handover(day, time_hm, user):
    keep = [h for h in _load("handover", [])
            if not (h["날짜"] == day and h["시각"] == time_hm
                    and h["이용자"] == user)]
    _save("handover", keep)


# ── 말 → 기록 초안 ────────────────────────────────────────────────────
def parse(text, known_users=None):
    """말한 문장에서 (이용자, 서식 항목, 상태, 숫자, 혈압/체온, 특이사항)을 뽑는다.

    **자동 확정하지 않는다.** 화면에서 사람이 고친 뒤 저장한다 — 잘못 들은 것을
    그대로 기록으로 남기면 되돌릴 수 없다.
    """
    import re
    t = " ".join((text or "").split())
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
    for st_, words in STATUS_WORDS.items():
        if any(w in t for w in words):
            status = st_
            break

    # 숫자 — "세 번", "3회", "25분" 처럼 말한다
    han = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6,
           "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
    num = None
    m = re.search(r"(\d+)\s*(회|번|분)", t)
    if m:
        num = int(m.group(1))
    else:
        for w, v in han.items():
            if f"{w} 번" in t or f"{w}번" in t:
                num = v
                break

    # 혈압 — "130에 80" / "130/80", 체온 — "36.7"
    bp = ""
    m = re.search(r"(\d{2,3})\s*(?:/|에)\s*(\d{2,3})", t)
    if m:
        bp = f"{m.group(1)}/{m.group(2)}"
    tp = ""
    m = re.search(r"(3[5-9]\.\d|4[0-2]\.\d)", t)
    if m:
        tp = m.group(1)

    # 특이사항은 원문을 살린다. 이름과 뒤따르는 '님'만 뗀다.
    note = t.replace(f"{user} 님", " ").replace(f"{user}님", " ") if user else t
    if user:
        note = note.replace(user, " ")
    note = " ".join(note.split()).strip(" ,.")
    return {"이용자": user, "항목": item, "상태": status, "숫자": num,
            "혈압": bp, "체온": tp, "특이사항": note, "원문": t}


# ── 일지(급여제공기록지 출력) ─────────────────────────────────────────
def daily_log(user, day=None):
    """이용자 한 명의 하루 기록을 서식 순서대로 글로. 일과 끝 일지 작성을 대신한다."""
    day = day or today()
    sh = sheet(user, day)
    if not sh["필드"] and not sh["특이"] and not sh["세션"]:
        return ""
    out = []
    se = sh["세션"]
    if se:
        mins = total_minutes(user, day)
        head = f"급여시간 {se.get('시작', '')}~{se.get('종료', '')}"
        if mins is not None:
            head += f" (총 {mins}분)"
        if se.get("이동"):
            head += f" · 이동서비스 {se.get('차량', '')}".rstrip()
        out.append(head.strip())
    for sec, items in SECTIONS:
        lines = []
        for k, label, _typ in items:
            if k in sh["필드"]:
                txt = value_text(k, sh["필드"][k])
                lines.append(f"  - {label}: {txt}" if txt else f"  - {label}")
        note = sh["특이"].get(sec, "")
        who = sh["작성자"].get(sec, "")
        if lines or note:
            out.append(f"[{sec}]")
            out += lines
            if note:
                out.append(f"  · 특이사항: {note}")
            if who:
                out.append(f"  · 작성자: {who}")
    return chr(10).join(out)

# ── 대장·점검표 (평가지표 대응) ────────────────────────────────────────
# 근거: 2026년 장기요양기관 재가급여(주야간보호) 평가매뉴얼의 평가지표.
# 지표마다 **주기가 정해져 있다** — 앱이 그 주기를 세어 주면 평가 대응이 된다.
# (지표 번호·주기는 매뉴얼에서 확인해 옮긴 것이다. 배점·세부 평가기준은 안 담는다)
#
# 주기: 매일 / 주3회 / 매월 / 분기 / 반기 / 매년
LOGBOOKS = [
    ("프로그램", "프로그램 운영일지", "주3회", "지표 24·25 신체·인지기능 프로그램 주 3회 이상",
     [("프로그램명", "text"), ("유형", ["신체기능", "인지기능", "사회적응", "기타"]),
      ("참여인원", "num"), ("진행자", "staff"), ("내용·특이사항", "text")]),
    ("차량", "차량운행일지", "매일", "지표 28 이동서비스 — 차량운행표 제공",
     [("차량번호", "text"), ("운행구간", "text"), ("운전원", "staff"),
      ("탑승인원", "num"), ("출발", "text"), ("도착", "text"), ("특이사항", "text")]),
    ("환기", "실내환기 일일 점검표", "매일", "지표 9-② 환기수칙에 따라 환기, 일일 점검표 비치",
     [("점검시간", "text"), ("환기방법", ["창문 개방", "환기장치", "둘 다"]),
      ("점검자", "staff"), ("특이사항", "text")]),
    ("소독", "소독·감염관리 점검", "분기", "지표 16-② 분기별 1회 이상 실내·외 전문소독",
     [("범위", "text"), ("업체·담당", "text"), ("점검자", "staff"), ("결과", "text")]),
    ("교육", "종사자 교육기록", "매년", "지표 6 운영규정·급여제공지침 교육 연 1회 이상",
     [("교육명", "text"),
      ("종류", ["운영규정", "급여제공지침", "인권보호", "감염관리", "안전·재난", "기타"]),
      ("강사", "text"), ("참석자", "text"), ("시간(분)", "num")]),
    ("소방", "소방설비 점검", "매월", "지표 13-① 소화설비·경보설비 매월 점검",
     [("점검항목", "text"), ("점검자", "staff"), ("결과", "text")]),
    ("재난훈련", "재난대응 훈련", "반기", "지표 11 재난상황 대응훈련 반기별 1회 이상",
     [("훈련내용", "text"), ("참석자", "text"), ("진행자", "staff")]),
    ("건강검진", "직원 건강검진", "매년", "지표 15 결핵검진 포함 건강검진 매년",
     [("대상자", "text"), ("검진기관", "text"), ("결과", "text")]),
    ("사례관리", "사례관리 회의", "반기", "지표 29 사례관리 회의 반기별 1회 이상",
     [("대상 수급자", "text"), ("참석자", "text"), ("논의·결정", "text")]),
    ("위험도평가", "낙상·욕창·인지 위험도 평가", "반기",
     "지표 20·21 낙상·욕창 위험도, 인지기능 평가 반기별 1회 이상",
     [("수급자", "user"), ("종류", ["낙상", "욕창", "인지기능"]),
      ("결과", "text"), ("평가자", "staff")]),
]
LOG_KEYS = [k for k, _, _, _, _ in LOGBOOKS]
LOG_SPEC = {k: (name, cycle, basis, fields)
            for k, name, cycle, basis, fields in LOGBOOKS}
CYCLE_DAYS = {"매일": 1, "주3회": 3, "매월": 31, "분기": 92, "반기": 183, "매년": 366}


def logs(key, limit=None):
    """대장 항목(최신순)."""
    rs = [r for r in _load("logs", []) if r["대장"] == key]
    rs.sort(key=lambda r: (r["날짜"], r.get("등록", "")), reverse=True)
    return rs[:limit] if limit else rs


def add_log(key, values, by="", day=None):
    if key not in LOG_SPEC:
        raise ValueError(f"모르는 대장: {key}")
    rs = _load("logs", [])
    rs.append({"대장": key, "날짜": day or today(), "값": values,
               "작성자": by, "등록": now_hm()})
    _save("logs", rs)


def delete_log(key, day, stamp):
    keep = [r for r in _load("logs", [])
            if not (r["대장"] == key and r["날짜"] == day
                    and r.get("등록") == stamp)]
    _save("logs", keep)


def log_status(key):
    """마지막 기록일과 경과일. 주기를 넘겼으면 늦음으로 표시한다.

    반환 {마지막, 경과, 늦음, 남음}. 기록이 없으면 마지막=None.
    """
    rs = logs(key, 1)
    name, cycle, basis, _ = LOG_SPEC[key]
    span = CYCLE_DAYS[cycle]
    if not rs:
        return {"마지막": None, "경과": None, "늦음": True, "남음": None,
                "이름": name, "주기": cycle, "근거": basis}
    last = rs[0]["날짜"]
    try:
        d0 = datetime.strptime(last, "%Y-%m-%d").date()
        gap = (datetime.now(KST).date() - d0).days
    except Exception:
        return {"마지막": last, "경과": None, "늦음": False, "남음": None,
                "이름": name, "주기": cycle, "근거": basis}
    return {"마지막": last, "경과": gap, "늦음": gap > span,
            "남음": span - gap, "이름": name, "주기": cycle, "근거": basis}


def overdue_logs():
    """주기를 넘긴 대장 목록 — 홈에 띄운다."""
    out = []
    for k in LOG_KEYS:
        stt = log_status(k)
        if stt["늦음"]:
            out.append((k, stt))
    return out

# ── 기기 대장 · 기기 자료 ──────────────────────────────────────────────
# **우리 차별점.** 조사한 요양 SW 6종(이지케어·케어포·이스마트케어·요양시스·
# 엔젤시스템·메디로) 어디에도 돌봄로봇·센서를 다루는 칸이 없다.
# 시설에 들어온 기기를 대장에 올리고, 매뉴얼·문의처를 붙여 현장에서 바로 찾게 한다.
DEVICE_STATES = ["사용중", "점검중", "고장", "보관", "반납"]


def devices():
    return _load("devices", [])


def add_device(name, maker="", model="", place="", state="사용중",
               since="", note=""):
    name = (name or "").strip()
    if not name:
        raise ValueError("기기명은 필수입니다.")
    ds = devices()
    ds.append({"기기명": name, "제조사": maker.strip(), "모델": model.strip(),
               "위치": place.strip(), "상태": state, "도입일": since.strip(),
               "비고": note.strip(), "등록일": today()})
    _save("devices", ds)


def set_device_state(name, state):
    if state not in DEVICE_STATES:
        return
    ds = devices()
    for d in ds:
        if d["기기명"] == name:
            d["상태"] = state
    _save("devices", ds)


def delete_device(name):
    _save("devices", [d for d in devices() if d["기기명"] != name])


DOC_KINDS = ["사용설명서", "설치·설정", "문제해결(FAQ)", "교육 영상", "A/S·문의처"]


def device_docs(name=None):
    ds = _load("device_docs", [])
    if name is None:
        return ds
    n = (name or "").strip().lower()
    return [d for d in ds
            if d["기기명"].strip().lower() in n or n in d["기기명"].strip().lower()]


def add_device_doc(name, kind, title, link, contact=""):
    name, title, link = name.strip(), title.strip(), link.strip()
    if not (name and title and link):
        raise ValueError("기기명·제목·링크는 필수입니다.")
    if not link.lower().startswith(("http://", "https://")):
        raise ValueError("링크는 http:// 또는 https:// 로 시작해야 합니다.")
    ds = _load("device_docs", [])
    ds.append({"기기명": name, "종류": kind, "제목": title, "링크": link,
               "문의처": contact.strip(), "등록일": today()})
    _save("device_docs", ds)


def delete_device_doc(title, link):
    _save("device_docs", [d for d in _load("device_docs", [])
                          if not (d["제목"] == title and d["링크"] == link)])


# ── 근무표 ────────────────────────────────────────────────────────────
# 인력 배치는 평가지표 3(인력기준)·4(추가배치)에 걸린다. 누가 언제 근무했는지가
# 기록으로 남아야 한다.
SHIFTS = ["주간", "오전", "오후", "야간", "휴무", "연차", "교육"]


def shifts(day=None):
    day = day or today()
    saved = _load("shifts", {}).get(day, {})
    return {s["이름"]: saved.get(s["이름"], "") for s in staff()}


def set_shift(name, kind, day=None):
    day = day or today()
    all_ = _load("shifts", {})
    if kind:
        all_.setdefault(day, {})[name] = kind
    else:
        all_.get(day, {}).pop(name, None)
    _save("shifts", all_)


def on_duty(day=None):
    """오늘 근무 중인 직원(휴무·연차 제외)."""
    return [n for n, k in shifts(day).items() if k and k not in ("휴무", "연차")]


# ── 건의·개선 요청 ────────────────────────────────────────────────────
SUG_STATES = ["접수", "진행중", "완료", "보류"]


def suggestions():
    return sorted(_load("suggest", []), key=lambda x: x["등록"], reverse=True)


def add_suggestion(text, by="", kind="개선"):
    text = (text or "").strip()
    if not text:
        return
    ss = _load("suggest", [])
    ss.append({"등록": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
               "작성자": by, "분류": kind, "내용": text, "상태": "접수",
               "처리": ""})
    _save("suggest", ss)


def set_suggestion(stamp, state, memo=""):
    ss = _load("suggest", [])
    for x in ss:
        if x["등록"] == stamp:
            x["상태"] = state
            x["처리"] = memo
    _save("suggest", ss)


def delete_suggestion(stamp):
    _save("suggest", [x for x in _load("suggest", []) if x["등록"] != stamp])


# ── 월간 내보내기 ─────────────────────────────────────────────────────
def month_days(ym):
    """그 달에 기록이 있는 날짜들."""
    return sorted(d for d in _sheets() if d.startswith(ym))


def export_month_csv(ym):
    """급여제공기록지 한 달치를 CSV 로. 공단 대응·감사 때 뽑는 용도.

    엑셀에서 한글이 안 깨지게 BOM 을 붙인다.
    """
    head = ["날짜", "수급자", "시작", "종료", "총시간(분)", "이동서비스", "차량번호"]
    head += [FIELDS[k][1] for k in FIELD_KEYS]
    head += [f"특이사항({sec})" for sec in SECTION_NAMES]
    head += [f"작성자({sec})" for sec in SECTION_NAMES]
    rows = [head]
    for day in month_days(ym):
        for user in sorted(_sheets().get(day, {})):
            sh = sheet(user, day)
            se = sh["세션"]
            mins = total_minutes(user, day)
            row = [day, user, se.get("시작", ""), se.get("종료", ""),
                   "" if mins is None else str(mins),
                   "Y" if se.get("이동") else "", se.get("차량", "")]
            row += [value_text(k, sh["필드"].get(k)) if k in sh["필드"] else ""
                    for k in FIELD_KEYS]
            row += [sh["특이"].get(sec, "") for sec in SECTION_NAMES]
            row += [sh["작성자"].get(sec, "") for sec in SECTION_NAMES]
            rows.append(row)
    out = []
    for r in rows:
        out.append(",".join('"' + str(c).replace('"', '""') + '"' for c in r))
    return ("﻿" + chr(10).join(out)).encode("utf-8")


def backup_zip():
    """데이터 전부를 zip 으로. 로컬 파일뿐이라 날리면 복구가 안 된다."""
    import io as _io
    import zipfile
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(DATA)):
            if fn.endswith(".json"):
                z.write(os.path.join(DATA, fn), fn)
    return buf.getvalue()

# ── 로그인 ────────────────────────────────────────────────────────────
# 이용자 건강정보를 다루므로 아무나 열려 있으면 안 된다.
# 직원별 **PIN(4~8자리 숫자)** 을 pbkdf2-sha256 으로 해시해 저장한다.
#
# ⚠️ 한계를 분명히 해둔다: 이건 *시설 안에서 쓰는 최소 잠금*이다.
#    PIN 은 비밀번호보다 약하고, 브라우저 세션 단위로만 유지된다.
#    인터넷에 공개할 거면 이 방식으로는 부족하다(계정·2단계 인증 필요).
_PIN_ITER = 120000


def _hash_pin(pin, salt):
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt),
                               _PIN_ITER).hex()


def has_pin(name):
    return bool(_load("pins", {}).get(name))


def any_pin():
    """PIN 이 하나라도 설정돼 있으면 로그인 화면을 띄운다."""
    return bool(_load("pins", {}))


def set_pin(name, pin):
    import os as _os
    pin = (pin or "").strip()
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        raise ValueError("PIN 은 숫자 4~8자리여야 합니다.")
    salt = _os.urandom(16).hex()
    ps = _load("pins", {})
    ps[name] = {"salt": salt, "hash": _hash_pin(pin, salt),
                "설정일": today()}
    _save("pins", ps)


def clear_pin(name):
    ps = _load("pins", {})
    ps.pop(name, None)
    _save("pins", ps)


def check_pin(name, pin):
    rec = _load("pins", {}).get(name)
    if not rec:
        return False
    import hmac
    return hmac.compare_digest(rec["hash"],
                               _hash_pin((pin or "").strip(), rec["salt"]))


def today_programs():
    """오늘 진행한 프로그램(대장에서). 홈에 띄운다."""
    return [r for r in logs("프로그램") if r["날짜"] == today()]


def broken_devices():
    """손봐야 할 기기 — 고장·점검중."""
    return [d for d in devices() if d.get("상태") in ("고장", "점검중")]

# ── 급여제공계획서 (별지 제11호의4서식) ────────────────────────────────
# 노인장기요양보험법 시행규칙 [별지 제11호의4서식] <개정 2021. 6. 30.>
# 장기요양급여제공계획서(시설급여, 주·야간보호, 단기보호). 원문에서 옮긴 항목.
#
# 작성방법(뒤쪽)에 명시된 것:
#   · 개인별장기요양이용계획서의 급여종류 범위 안에서, 기능상태·욕구를 고려해
#     **급여 개시 전에** 작성한다.
#   · 수급자 또는 가족에게 충분히 설명한 뒤 **동의를 받아** 공단에 통보한다.
#   · 급여종류별 또는 기관별로 각각 작성한다.
# 평가지표 22 — 연 1회 이상 수립, 확인서명, 급여제공 시작일까지 공단 통보.
PLAN_HEAD = ["장기요양등급", "장기요양인정번호", "인정유효기간",
             "개인별장기요양이용계획서 번호", "급여종류", "급여계약일",
             "계약기간", "적용기간", "작성일", "통보일"]
# 급여제공계획 내용 — 한 줄이 '무엇을 얼마나 자주' 하나를 나타낸다
PLAN_ROW = ["장기요양 필요영역", "장기요양 세부목표", "장기요양 필요내용",
            "세부 제공내용", "횟수", "시간"]


def plans(user=None):
    ps = _load("plans", [])
    return [p for p in ps if user is None or p["수급자"] == user]


def latest_plan(user):
    ps = sorted(plans(user), key=lambda p: p.get("작성", ""), reverse=True)
    return ps[0] if ps else None


def save_plan(user, head, goal, rows, opinion, writer, manager,
              agree_name="", agree_rel="", agree_date=""):
    """계획서 한 장 저장. 동의 정보가 비어 있어도 저장은 되지만 화면에서 경고한다
    (서식상 동의 없이 공단 통보를 할 수 없다)."""
    ps = _load("plans", [])
    ps.append({"수급자": user, "머리": head, "목표": (goal or "").strip(),
               "내용": rows, "종합의견": (opinion or "").strip(),
               "작성자": writer, "총괄확인자": manager,
               "동의자": {"성명": agree_name, "관계": agree_rel,
                        "동의일": agree_date},
               "작성": datetime.now(KST).strftime("%Y-%m-%d %H:%M")})
    _save("plans", ps)


def delete_plan(user, stamp):
    _save("plans", [p for p in _load("plans", [])
                    if not (p["수급자"] == user and p.get("작성") == stamp)])


def plan_missing():
    """계획서가 없는 이용자 — 평가지표 22는 '연 1회 이상 수립'을 요구한다."""
    return [u["이름"] for u in users() if not latest_plan(u["이름"])]

# ── 욕구사정 · 상담 · 결과평가 ─────────────────────────────────────────
# 근거: 2026년 재가급여(주야간보호) 평가매뉴얼
#   · 지표 30 욕구사정 — 모든 수급자 **연 1회 이상**, 대면 원칙, 해당급여직원이 작성
#     매뉴얼 114쪽의 '욕구사정 세부내용' 을 그대로 옮겼다.
#     ⚠️ 매뉴얼은 "세부내용 9개 항목"이라고 하면서 번호는 1~8까지만 열거한다.
#        본문 다른 곳에 '구강상태' 항목이 언급돼 9번으로 넣었다.
#        [[확인필요: 9번 항목이 구강상태가 맞는지]]
#   · 지표 25 상담관리 — 모든 수급자(보호자)와 **분기별 1회 이상**
#     필수사항: 상담일자, 수급자명, 상담직원명, 상담대상자명(관계), 상담내용
#   · 지표 44 결과평가 — **반기별**, 결과를 반영해 급여제공계획을 **30일 이내 재작성**
#
# ⚠️ 매뉴얼이 못박은 것: 단순 체크만 하면 인정 안 된다. **판단 근거를 서술**해야 한다.
#    (예: 옷 벗고 입기 '부분도움' 체크만 → 불인정 /
#         "왼쪽 편마비로 옷 갈아입을 때 일부 도움 필요" 로 근거 서술 → 인정)
ASSESS_ITEMS = [
    ("신체상태", "일상생활동작 수행능력 등"),
    ("질병상태", "과거병력, 현 진단명 등"),
    ("인지상태", "인지기능 등"),
    ("의사소통", "청취능력, 발음능력 등"),
    ("영양상태", "음식섭취 패턴, 치아상태, 배설 양상 등"),
    ("가족 및 환경상태", "가족상황, 거주환경, 수발부담 등"),
    ("주관적 욕구", "수급자 또는 보호자가 호소하는 개별 욕구"),
    ("자원이용", "의료기관, 사회복지기관, 그 외 서비스 기관 등"),
    ("구강상태", "치아·틀니·기피식품 파악 등"),
]


def assessments(user=None):
    xs = sorted(_load("assess", []), key=lambda x: x["작성"], reverse=True)
    return [x for x in xs if user is None or x["수급자"] == user]


def save_assessment(user, items, summary, by):
    _push("assess", {"수급자": user, "항목": items, "총평": (summary or "").strip(),
                     "작성자": by, "작성": today()})


def counsels(user=None):
    xs = sorted(_load("counsel", []), key=lambda x: x["상담일자"], reverse=True)
    return [x for x in xs if user is None or x["수급자"] == user]


def save_counsel(user, date, target, rel, content, by):
    """상담 기록. 매뉴얼이 요구하는 5개 필수사항을 그대로 칸으로 둔다."""
    _push("counsel", {"수급자": user, "상담일자": date or today(),
                      "상담대상자": target, "관계": rel,
                      "상담내용": (content or "").strip(), "상담직원": by})


def results(user=None):
    xs = sorted(_load("result", []), key=lambda x: x["작성"], reverse=True)
    return [x for x in xs if user is None or x["수급자"] == user]


def save_result(user, period, achieved, change, next_plan, by):
    _push("result", {"수급자": user, "평가기간": period,
                     "목표달성": achieved, "상태변화": change,
                     "계획반영": next_plan, "작성자": by, "작성": today()})


def _push(name, row):
    xs = _load(name, [])
    xs.append(row)
    _save(name, xs)


def _days_since(datestr):
    try:
        d0 = datetime.strptime(datestr[:10], "%Y-%m-%d").date()
        return (datetime.now(KST).date() - d0).days
    except Exception:
        return None


def care_due():
    """수급자별로 기한이 지난 것을 모아 준다.

    욕구사정 연1회(366일) · 상담 분기(92일) · 결과평가 반기(183일) · 계획서 연1회.
    """
    out = []
    for u in users():
        n = u["이름"]
        for label, rows, span, keyf in (
                ("욕구사정", assessments(n), 366, lambda r: r["작성"]),
                ("상담", counsels(n), 92, lambda r: r["상담일자"]),
                ("결과평가", results(n), 183, lambda r: r["작성"]),
                ("급여제공계획서", plans(n), 366, lambda r: r.get("작성", ""))):
            if not rows:
                out.append((n, label, None))
                continue
            gap = _days_since(keyf(rows[0]))
            if gap is not None and gap > span:
                out.append((n, label, gap))
    return out



# ── 화면 설정(테마) ───────────────────────────────────────────────────
def get_pref(name, key, default=""):
    return _load("prefs", {}).get(name, {}).get(key, default)


def set_pref(name, key, value):
    ps = _load("prefs", {})
    ps.setdefault(name or "_", {})[key] = value
    _save("prefs", ps)
