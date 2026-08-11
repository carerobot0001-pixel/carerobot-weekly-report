"""요양시설 스튜디오 — 주간보호센터·소형 요양원용 돌봄 업무 앱.

Dolbom Studio(우리 팀 업무 공간)와 **같은 구조**로 만든다 — 사이드바 메뉴,
홈 대시보드, 공지, 기록. 쓰는 사람만 연구원에서 요양보호사로 바뀐다.

1단계 범위: 출결 · 케어 기록 · 인계 · 일지 · 공지.
음성 기록은 그 다음 단계에서 이 위에 얹는다(`voice.py`는 이미 있음).

**저장은 항상 사람이 누른 뒤에만** 일어난다. 자동 확정 없음.
"""
from html import escape as html_escape

import streamlit as st

import store
import voice

st.set_page_config(page_title="요양시설 스튜디오", page_icon="🏥", layout="wide")

# 다크 모드 — 계정별로 기억한다.
# ⚠️ 다크에서 **순백 글씨(18.7:1)는 눈부시다**(돌봄스튜디오에서 세 번 헤맴).
#    그렇다고 낮추면 시력 저하자가 못 읽는다 → 본문 #DAD7D2 (13:1) 로 잡았다.
_who = st.session_state.get("who") or st.session_state.get("me") or "_"
if "dark" not in st.session_state:
    st.session_state["dark"] = store.get_pref(_who, "dark", "") == "Y"
DARK = st.session_state["dark"]

# 인스타그램 웹 화면 + **시력 저하자 배려**.
#
# 인스타 원색을 그대로 쓰면 안 된다 — 흰 배경 대비를 계산해보면 셋 다 미달이다:
#   회색 #8E8E8E 3.28:1 · 파랑 #0095F6 3.17:1 · 빨강 #ED4956 3.69:1  (본문 기준 4.5)
# 그래서 진한 쪽으로 바꿨다:
#   본문 #1A1A1A 17.4 · 보조 #595959 7.0 · 파랑 #0B5FCC 6.0 · 경고 #C62828 5.6
# 인스타 원색은 **면적이 큰 배경**(그라디언트 링·버튼 바탕)에만 남긴다.
#
# 그 외 시력 배려: 기본 글씨 18px, 줄높이 1.65, 버튼 높이 48px 이상,
# 입력칸 글씨 17px. 돌봄스튜디오에서 배운 대로 **여백·정렬 CSS 는 stMain 으로 한정**
# 한다(전역으로 두면 사이드바 간격이 무너진다).
st.markdown("""<style>
  :root{
    --ig-ink:#1A1A1A; --ig-sub:#595959; --ig-line:#C7C7C7;
    --ig-blue:#0B5FCC; --ig-warn:#C62828;
    --ig-grad:linear-gradient(45deg,#F58529,#DD2A7B,#8134AF,#515BD4);
  }
  html, body, section[data-testid="stMain"]{ font-size:18px; }
  section[data-testid="stMain"]{ background:#FFFFFF; }
  section[data-testid="stMain"] .block-container{
    padding-top:2rem; max-width:900px; margin-left:auto; margin-right:auto; }
  /* 사이드바 항목 — 폭·들여쓰기를 하나로 맞춘다(들쭉날쭉해 보이던 것) */
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{
    gap:.2rem; }
  /* 버튼 칸을 전체 폭으로 — 안 그러면 현재 메뉴(색 채운 것)만 좁게 보인다 */
  section[data-testid="stSidebar"] [data-testid="stElementContainer"],
  section[data-testid="stSidebar"] .stButton{
    width:100% !important; display:block !important; }
  section[data-testid="stSidebar"] .stButton>button{ width:100% !important; }
  section[data-testid="stMain"] p,
  section[data-testid="stMain"] li,
  section[data-testid="stMain"] label,
  section[data-testid="stMain"] div[data-testid="stMarkdownContainer"]{
    font-size:1.02rem; line-height:1.65; color:var(--ig-ink); }
  h1,h2,h3,h4{ color:var(--ig-ink) !important; font-weight:800;
               letter-spacing:-.01em; }
  h1{ font-size:2rem; } h2{ font-size:1.5rem; } h3{ font-size:1.25rem; }
  a,a:visited{ color:var(--ig-blue); text-decoration:underline; }

  /* 사이드바 — 돌봄스튜디오와 같은 짜임: 어두운 바탕 · 밝은 글씨 ·
     왼쪽 정렬 · 현재 메뉴는 색을 채워 표시. 색만 인스타 계열로 바꿨다. */
  section[data-testid="stSidebar"]{
    background:#241B2F; border-right:none; }
  section[data-testid="stSidebar"] *{ color:#F3EAF7 !important; }
  section[data-testid="stSidebar"] .stButton>button{
    background:transparent; border:none; text-align:center !important;
    justify-content:center !important; font-size:1.05rem; font-weight:600;
    padding:10px 12px; border-radius:10px; margin:2px 0; width:100%;
    min-height:46px; }
  section[data-testid="stSidebar"] .stButton>button p{
    text-align:center !important; width:100%; margin:0; }
  section[data-testid="stSidebar"] .stButton>button:hover{ background:#362A45; }
  section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
    background:linear-gradient(90deg,#DD2A7B,#8134AF);
    color:#FFFFFF !important; font-weight:800; box-shadow:none; }
  /* 테마 전환 버튼은 메뉴와 구분되게 테두리 있는 칩으로 */
  section[data-testid="stSidebar"] .st-key-theme_btn button{
    background:#33263F !important; border:1px solid #5B4A6B !important;
    text-align:center !important; justify-content:center !important;
    font-size:.95rem !important; font-weight:700; min-height:42px; }
  section[data-testid="stSidebar"] .st-key-theme_btn button p{
    text-align:center !important; }
  /* 카테고리 소제목 */
  /* 카테고리 소제목 — 자기 줄을 확실히 차지하게 한다.
     margin 만 주면 버튼과 겹쳐 보였다(간격 CSS 를 좁혀둔 탓). */
  section[data-testid="stSidebar"] .navcat{
    display:block; color:#C0A8D6 !important; font-size:.78rem;
    font-weight:800; letter-spacing:2px; text-align:center;
    line-height:1.2; padding:14px 0 6px; margin:0; }
  /* 입력칸(이름 고르기)도 어두운 바탕에 맞춘다 */
  section[data-testid="stSidebar"] [data-baseweb="select"] > div,
  section[data-testid="stSidebar"] input{
    background:#33263F !important; border-color:#5B4A6B !important; }

  /* 버튼 — 손가락으로 누를 크기 */
  div.stButton>button, div.stFormSubmitButton>button{
    min-height:48px; font-size:1.02rem; font-weight:700; border-radius:10px; }
  div.stButton>button[kind="primary"], div.stFormSubmitButton>button{
    background:var(--ig-blue); border:1px solid var(--ig-blue); color:#fff; }
  div.stButton>button[kind="primary"]:hover,
  div.stFormSubmitButton>button:hover{ background:#0A4EA8; border-color:#0A4EA8; }
  div.stButton>button{
    border:2px solid var(--ig-line); color:var(--ig-ink); background:#fff; }
  div.stButton>button:hover{ background:#F5F5F5; border-color:#8E8E8E; }

  /* 입력칸도 크게 */
  section[data-testid="stMain"] input,
  section[data-testid="stMain"] textarea,
  section[data-testid="stMain"] div[data-baseweb="select"] *{
    font-size:1.02rem !important; color:var(--ig-ink) !important; }
  section[data-testid="stMain"] input, section[data-testid="stMain"] textarea{
    min-height:46px; }
  section[data-testid="stMain"] input::placeholder,
  section[data-testid="stMain"] textarea::placeholder{
    color:#6E6E6E !important; opacity:1 !important; }

  div[data-testid="stVerticalBlockBorderWrapper"]{
    border:1px solid var(--ig-line) !important; border-radius:12px;
    background:#fff; }
  [data-testid="stMetric"]{ border:none; padding:0; }
  [data-testid="stMetricValue"]{
    color:var(--ig-ink); font-size:1.6rem; font-weight:800; }
  [data-testid="stMetricLabel"] *{ color:var(--ig-sub); font-size:.95rem; }

  [data-testid="stAlert"]{
    border:2px solid var(--ig-line); border-radius:12px; background:#FAFAFA; }
  [data-testid="stAlert"] *{ color:var(--ig-ink) !important; font-size:1rem; }

  section[data-testid="stMain"] [data-testid="stRadio"] label,
  section[data-testid="stMain"] [data-testid="stCheckbox"] label{
    font-size:1rem; }
  section[data-testid="stMain"] [data-testid="stTabs"] button p{
    font-size:1.05rem; font-weight:700; }

  .ig-brand{
    font-weight:900; background:var(--ig-grad); -webkit-background-clip:text;
    background-clip:text; color:transparent; }
  .ig-cap{ color:var(--ig-sub); font-size:.92rem; }
  .cs-warn{ color:var(--ig-warn); font-weight:800; }
  .cs-dim{ color:var(--ig-sub); font-size:.92rem; }
</style>""", unsafe_allow_html=True)

if DARK:
    # 색면을 바꾸는 규칙만 전역, 여백·정렬은 건드리지 않는다.
    st.markdown("""<style>
      :root{
        --ig-ink:#DAD7D2; --ig-sub:#A8A49E; --ig-line:#3A3A38;
        --ig-blue:#6BAAF5; --ig-warn:#FF7A70; }
      html, body, section[data-testid="stMain"],
      [data-testid="stAppViewContainer"]{ background:#121212 !important; }
      section[data-testid="stMain"] *, section[data-testid="stSidebar"] *{
        color:#DAD7D2 !important; }
      h1,h2,h3,h4{ color:#E8E5E1 !important; }
      section[data-testid="stSidebar"]{
        background:#0D0D0D !important; border-right:1px solid #3A3A38; }
      section[data-testid="stSidebar"] .stButton>button:hover{
        background:#242422 !important; }
      section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
        background:#242422 !important; box-shadow:inset 4px 0 0 0 #DD2A7B; }
      div[data-testid="stVerticalBlockBorderWrapper"],
      [data-testid="stAlert"]{
        background:#1B1B1A !important; border-color:#3A3A38 !important; }
      div.stButton>button{
        background:#1B1B1A !important; border-color:#4A4A47 !important; }
      div.stButton>button:hover{ background:#242422 !important; }
      div.stButton>button[kind="primary"], div.stFormSubmitButton>button{
        background:#2F6FD0 !important; border-color:#2F6FD0 !important;
        color:#FFFFFF !important; }
      section[data-testid="stMain"] input,
      section[data-testid="stMain"] textarea,
      section[data-testid="stMain"] [data-baseweb="select"] > div{
        background:#1B1B1A !important; border-color:#4A4A47 !important; }
      section[data-testid="stMain"] input::placeholder,
      section[data-testid="stMain"] textarea::placeholder{
        color:#8E8B86 !important; opacity:1 !important; }
      /* 드롭다운·달력은 body 포털이라 앱 밖에 그려진다 — 따로 덮는다 */
      div[data-baseweb="popover"] *, div[data-baseweb="menu"] *{
        background:#1B1B1A !important; color:#DAD7D2 !important; }
      .ig-cap, .cs-dim{ color:#A8A49E !important; }
      .cs-warn{ color:#FF7A70 !important; }
    </style>""", unsafe_allow_html=True)

MENUS = [("현장", ["🏠 홈", "✅ 케어 기록", "🔄 인계"]),
         ("기록", ["📄 일지", "📝 사정·상담", "📋 급여제공계획서",
                   "📚 대장·점검", "🧑‍🦳 이용자"]),
         ("기기", ["🤖 기기 대장"]),
         ("운영", ["🗓 근무표", "🛒 구매요청", "📌 공지", "💡 건의",
                   "⚙️ 직원·설정"])]
ALL = [m for _, ms in MENUS for m in ms]

if "menu" not in st.session_state:
    st.session_state["menu"] = ALL[0]


def _go(m):
    st.session_state["menu"] = m
    st.rerun()


def _login_gate():
    """PIN 로그인. 아무도 PIN 을 안 걸었으면 잠그지 않는다(첫 설치 편의).

    ⚠️ 시설 안에서 쓰는 **최소 잠금**이다. 인터넷에 공개할 거면 부족하다.
    """
    if st.session_state.get("who"):
        return True
    if not store.any_pin():
        return True                      # 아직 PIN 을 아무도 설정하지 않음
    st.markdown("### 🏥 요양시설 스튜디오")
    st.caption("이용자 정보가 있어 로그인이 필요합니다.")
    ss = [x["이름"] for x in store.staff()]
    with st.form("login"):
        who = st.selectbox("이름", ss)
        pin = st.text_input("PIN", type="password", max_chars=8)
        if st.form_submit_button("들어가기", type="primary",
                                 use_container_width=True):
            if not store.has_pin(who):
                st.warning(f"{who} 님은 PIN 이 설정돼 있지 않습니다. "
                           "PIN 을 설정한 다른 직원으로 들어와 "
                           "⚙️ 직원·설정에서 발급하세요.")
            elif store.check_pin(who, pin):
                st.session_state["who"] = who
                st.session_state["me"] = who
                st.rerun()
            else:
                st.error("PIN 이 맞지 않습니다.")
    st.caption("PIN 을 잊었으면 센터장(또는 PIN 을 아는 직원)이 "
               "⚙️ 직원·설정에서 다시 발급할 수 있습니다.")
    return False


if not _login_gate():
    st.stop()

with st.sidebar:
    st.markdown("<div style='text-align:center;padding:.2rem 0 .1rem'>"
                "<span class='ig-brand' style='font-size:1.25rem'>"
                "요양시설 스튜디오</span></div>"
                "<div class='ig-cap' style='text-align:center;"
                "margin-bottom:.7rem'>주간보호센터 · 소형 요양원</div>",
                unsafe_allow_html=True)
    if st.button("🌙 어두운 화면으로" if not DARK else "☀️ 밝은 화면으로",
                 key="theme_btn", use_container_width=True):
        st.session_state["dark"] = not DARK
        store.set_pref(_who, "dark", "" if DARK else "Y")
        st.rerun()
    _names = [s["이름"] for s in store.staff()]
    if st.session_state.get("who"):
        st.markdown(f"**{st.session_state['who']}** 님")
        st.session_state["me"] = st.session_state["who"]
        if st.button("나가기", key="logout"):
            for k in ("who", "me"):
                st.session_state.pop(k, None)
            st.rerun()
    elif _names:
        st.session_state["me"] = st.selectbox(
            "나", _names,
            index=_names.index(st.session_state["me"])
            if st.session_state.get("me") in _names else 0)
    else:
        st.session_state["me"] = st.text_input(
            "나(이름)", value=st.session_state.get("me", ""))
        st.caption("⚙️ 직원·설정에서 직원을 등록하면 목록에서 고를 수 있습니다.")
    st.divider()
    for cat, ms in MENUS:
        st.markdown(f"<div class='navcat'>{cat}</div>",
                    unsafe_allow_html=True)
        for m in ms:
            if st.button(m, key=f"nav_{m}",
                         type="primary" if st.session_state["menu"] == m else "secondary"):
                _go(m)
    st.divider()
    if not store.any_pin():
        st.caption("🔓 잠금 없음 — ⚙️ 직원·설정에서 PIN 을 걸면 로그인 화면이 생깁니다.")
    st.caption("⚠️ 시연·시험 단계. 이용자는 **가명·코드**로 등록하세요.")

me = st.session_state.get("me", "")
users = store.users()
names = [u["이름"] for u in users]


def _need_users():
    if not users:
        st.info("먼저 **🧑‍🦳 이용자** 에서 이용자를 등록하세요.")
        return True
    return False


# ── 홈 (인스타그램식) ─────────────────────────────────────────────────
# 인스타 앱 화면을 따른다:
#   상단 앱바(로고) → 스토리 줄(원형·그라디언트 링) → 피드 카드
# 스토리 자리에는 **오늘 등원한 이용자**를 놓는다. 주의사항이 있으면 링이 빨갛다.
def page_home():
    _appbar()
    if _need_users():
        return
    att = store.attendance()
    here = [u for u, s in att.items() if s == "등원"]
    unknown = [u for u, s in att.items() if s == "미확인"]
    done = store.done_map()

    _stories(here, att)
    _stats(here, att, done)
    _shortcuts()

    # 피드 — 중요한 것부터 카드로
    for n in store.notices()[:2]:
        _card("공지", n["내용"], f"{n['작성자']} · {n['등록']}", icon="📌")

    if unknown:
        _card("출결 미확인", ", ".join(unknown[:12]),
              "케어 기록에서 등원·결석을 찍어 주세요", warn=True, icon="🙋")

    od = store.overdue_logs()
    if od:
        _card("기한이 지난 기록",
              " · ".join(f"{stt['이름']}({stt['주기']})" for _k, stt in od[:6]),
              f"모두 {len(od)}건 — 대장·점검에서 처리", warn=True, icon="⏰")

    cd = store.care_due()
    if cd:
        _card("수급자별 기한",
              " · ".join(f"{n} {lab}" for n, lab, _g in cd[:6]),
              f"모두 {len(cd)}건 — 사정·상담에서 처리", warn=True, icon="🗓")

    bad = store.broken_devices()
    if bad:
        _card("손봐야 할 기기",
              " · ".join(f"{d['기기명']}({d['상태']})" for d in bad),
              "기기 대장에서 상태를 관리합니다", warn=True, icon="🤖")

    warn = [u for u in users if u["이름"] in here and (u.get("주의사항") or "").strip()]
    if warn:
        _card("오늘 주의",
              "  ·  ".join(f"{u['이름']} {u['주의사항']}" for u in warn), "", icon="⚠")

    rows = []
    for key in store.FIELD_KEYS:
        miss = [u for u in here if u not in done.get(key, set())]
        if miss:
            rows.append(f"{store.FIELDS[key][1]} — {len(miss)}명")
    if here:
        _card("아직 안 채운 칸",
              " · ".join(rows[:8]) if rows else "서식이 모두 채워졌습니다.",
              f"모두 {len(rows)}개 항목" if rows else "", icon="✅")

    pr = store.today_programs()
    _card("오늘 프로그램",
          " · ".join(f"{r['값'].get('프로그램명', '')}({r.get('유형', '')})"
                     for r in pr) if pr else "아직 기록이 없습니다.",
          "신체·인지기능 주 3회 이상 · 사회적응 월 1회 이상", icon="🎵")

    hs = store.handovers()
    if hs:
        _card("오늘 인계",
              "  ·  ".join(f"{h['이용자']} {h['내용']}" for h in hs[:4]),
              f"모두 {len(hs)}건", icon="🔄")


def _appbar():
    """앱바 — 제목과 정보를 **두 줄**로 나눈다.
    한 줄에 몰면 좁은 화면에서 제목이 '요양시설 스튜디 / 오' 처럼 끊긴다."""
    duty = store.on_duty()
    st.markdown(
        "<div style='border-bottom:2px solid #C7C7C7;padding-bottom:.6rem;"
        "margin-bottom:1.1rem'>"
        "<div class='ig-brand' style='font-size:1.7rem;line-height:1.25;"
        "white-space:nowrap'>요양시설 스튜디오</div>"
        f"<div class='ig-cap' style='margin-top:.15rem'>{store.today()}"
        + (f" · 근무 {', '.join(duty)}" if duty else " · 근무표 비어 있음")
        + f" · {me or '이름 선택'}</div></div>", unsafe_allow_html=True)


def _stories(here, att):
    """스토리 줄 — 등원한 이용자를 동그라미로. 주의사항이 있으면 링이 빨갛다."""
    if not here:
        st.markdown("<div class='ig-cap' style='margin:.2rem 0 1rem'>"
                    "등원한 이용자가 없습니다. 케어 기록에서 출결을 찍으세요."
                    "</div>", unsafe_allow_html=True)
        return
    warn = {u["이름"] for u in users if (u.get("주의사항") or "").strip()}
    done = store.done_map()
    cells = []
    for n in here:
        left = sum(1 for k in store.FIELD_KEYS if n not in done.get(k, set()))
        ring = ("linear-gradient(45deg,#C62828,#F58529)" if n in warn
                else "linear-gradient(45deg,#F58529,#DD2A7B,#8134AF,#515BD4)"
                if left else "#C7C7C7")
        cells.append(
            "<div style='text-align:center;width:96px;flex:none'>"
            f"<div style='width:82px;height:82px;border-radius:50%;padding:4px;"
            f"margin:0 auto;background:{ring}'>"
            "<div style='width:100%;height:100%;border-radius:50%;background:#fff;"
            "display:flex;align-items:center;justify-content:center;"
            "font-size:1.35rem;font-weight:800;color:#1A1A1A'>"
            f"{html_escape(n[:2])}</div></div>"
            f"<div style='font-size:.95rem;margin-top:6px;font-weight:600;color:#1A1A1A'>"
            f"{html_escape(n)}</div>"
            f"<div style='font-size:.88rem;color:#595959'>"
            + (f"{left}칸" if left else "완료") + "</div></div>")
    st.markdown(
        "<div style='display:flex;gap:10px;overflow-x:auto;padding:.4rem 0 1.1rem;"
        "border-bottom:1px solid #C7C7C7;margin-bottom:1rem'>"
        + "".join(cells) + "</div>", unsafe_allow_html=True)


def _stats(here, att, done):
    """인스타 프로필식 숫자 줄 — 박스 없이 숫자 위, 라벨 아래."""
    absent = sum(1 for v in att.values() if v == "결석")
    left = sum(1 for k in store.FIELD_KEYS for u in here
               if u not in done.get(k, set()))
    items = [(f"{len(here)}/{len(users)}", "등원"), (str(absent), "결석"),
             (str(sum(1 for v in att.values() if v == "미확인")), "미확인"),
             (str(left), "빈 칸")]
    st.markdown(
        "<div style='display:flex;gap:2.6rem;padding:.3rem 0 1.2rem;border-bottom:1px solid #C7C7C7;margin-bottom:1rem'>"
        + "".join(
            f"<div style='text-align:center'>"
            f"<div style='font-size:1.9rem;font-weight:800;color:#1A1A1A;line-height:1.1'>{v}</div>"
            f"<div style='font-size:1rem;color:#595959;margin-top:2px'>{k}</div></div>"
            for v, k in items)
        + "</div>", unsafe_allow_html=True)


def _card(title, body, foot="", warn=False, icon="●"):
    """피드 카드 — 인스타 게시물 모양.

    머리(동그란 아바타 + 제목 + 작은 회색 부제) / 본문 / 아래 회색 한 줄.
    """
    ring = ("linear-gradient(45deg,#C62828,#F58529)" if warn
            else "linear-gradient(45deg,#F58529,#DD2A7B,#8134AF,#515BD4)")
    color = "#C62828" if warn else "#1A1A1A"
    st.markdown(
        "<div style='border:1px solid #C7C7C7;border-radius:14px;"
        "margin-bottom:1rem;background:#fff;overflow:hidden'>"
        # 머리
        "<div style='display:flex;align-items:center;gap:.6rem;"
        "padding:.85rem 1.1rem;border-bottom:1px solid #E4E4E4'>"
        f"<div style='width:42px;height:42px;border-radius:50%;padding:3px;"
        f"background:{ring};flex:none'>"
        "<div style='width:100%;height:100%;border-radius:50%;background:#fff;"
        "display:flex;align-items:center;justify-content:center;font-size:1.05rem'>"
        f"{icon}</div></div>"
        f"<div><div style='font-weight:800;font-size:1.12rem;color:{color};line-height:1.25'>"
        f"{html_escape(title)}</div>"
        + (f"<div style='font-size:.92rem;color:#595959'>{html_escape(foot)}</div>"
           if foot else "")
        + "</div></div>"
        # 본문
        f"<div style='padding:.95rem 1.1rem;color:#1A1A1A;font-size:1.05rem;line-height:1.65'>"
        f"{html_escape(body)}</div></div>", unsafe_allow_html=True)


def _shortcuts():
    tiles = ["✅ 케어 기록", "🔄 인계", "📝 사정·상담", "📚 대장·점검"]
    cols = st.columns(len(tiles))
    for c, t in zip(cols, tiles):
        if c.button(t, key=f"sc_{t}", use_container_width=True):
            _go(t)


# ── 케어 기록(급여제공기록지) ─────────────────────────────────────────
def page_care():
    st.header("✅ 케어 기록")
    st.caption("노인장기요양보험법 시행규칙 **별지 제15호서식** "
               "장기요양급여제공기록지(주·야간보호) 항목입니다.")
    if _need_users():
        return
    att = store.attendance()

    st.subheader("출결")
    cols = st.columns(min(4, len(users)))
    for i, u in enumerate(users):
        with cols[i % len(cols)]:
            cur = att[u["이름"]]
            pick = st.radio(u["이름"], store.ATT, index=store.ATT.index(cur),
                            key=f"att_{u['이름']}", horizontal=True)
            if pick != cur:
                store.set_attendance(u["이름"], pick)
                st.rerun()

    here = [u for u, s in att.items() if s == "등원"]
    if not here:
        st.info("등원으로 표시된 이용자가 없습니다.")
        return

    st.divider()
    _voice_block(here)

    st.divider()
    who = st.selectbox("이용자", here, key="care_user")
    sh = store.sheet(who)
    _session_row(who, sh)
    st.divider()
    _form(who, sh)


def _session_row(who, sh):
    """서식 앞쪽 머리 — 시작/종료시각, 총시간(자동), 이동서비스(차량번호)."""
    se = sh.get("세션", {})
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.4])
    a = c1.text_input("시작시간", value=se.get("시작", ""), key=f"s_{who}",
                      placeholder="09:10")
    b = c2.text_input("종료시간", value=se.get("종료", ""), key=f"e_{who}",
                      placeholder="17:30")
    ride = c3.checkbox("이동서비스", value=se.get("이동", False), key=f"r_{who}")
    car = c4.text_input("차량번호", value=se.get("차량", ""), key=f"c_{who}",
                        disabled=not ride)
    if c5.button("급여시간 저장", use_container_width=True):
        store.set_session(who, a, b, ride, car)
        st.rerun()
    mins = store.total_minutes(who)
    st.caption(f"총시간 {mins}분" if mins is not None
               else "총시간 — 시작·종료시각을 넣으면 자동 계산됩니다.")


def _form(who, sh):
    """서식 본문. 구역별로 항목을 그리고, 구역마다 특이사항·작성자를 받는다."""
    vals = sh["필드"]
    for sec, items in store.SECTIONS:
        st.markdown(f"#### {sec}")
        for k, label, typ in items:
            cur = vals.get(k)
            c1, c2 = st.columns([3, 4])
            c1.markdown(("✅ " if k in vals else "") + label)
            with c2:
                _field_widget(who, k, typ, cur)
        note = st.text_input(
            f"특이사항 ({sec})", value=sh["특이"].get(sec, ""),
            key=f"note_{who}_{sec}",
            placeholder="예: 설사를 해서 엉덩이 짓물러 파우더 바름")
        cA, cB = st.columns([1, 4])
        if cA.button("특이사항 저장", key=f"nb_{who}_{sec}",
                     use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.set_section_note(who, sec, note, me)
                st.rerun()
        if sh["작성자"].get(sec):
            cB.caption(f"작성자 {sh['작성자'][sec]}")
        st.divider()


def _field_widget(who, k, typ, cur):
    """항목 유형별 입력칸. 저장은 각 칸의 버튼을 눌러야 일어난다."""
    if typ == "check":
        b1, b2 = st.columns(2)
        if b1.button("제공함", key=f"f_{who}_{k}", use_container_width=True,
                     disabled=bool(cur)):
            _set(who, k, True)
        if b2.button("지우기", key=f"x_{who}_{k}", use_container_width=True,
                     disabled=not cur):
            _set(who, k, None)
    elif typ == "count":
        c1, c2 = st.columns([2, 1])
        n = c1.number_input("횟수", 0, 30, int(cur or 0), key=f"f_{who}_{k}",
                            label_visibility="collapsed")
        if c2.button("저장", key=f"b_{who}_{k}", use_container_width=True):
            _set(who, k, int(n))
    elif typ == "bath":
        v = cur or {}
        c1, c2, c3 = st.columns([1, 1.4, 1])
        m = c1.number_input("분", 0, 240, int(v.get("분", 0)),
                            key=f"f_{who}_{k}", label_visibility="collapsed")
        w = c2.selectbox("방법", store.BATH_WAYS,
                         index=store.BATH_WAYS.index(v["방법"])
                         if v.get("방법") in store.BATH_WAYS else 0,
                         key=f"w_{who}_{k}", label_visibility="collapsed")
        if c3.button("저장", key=f"b_{who}_{k}", use_container_width=True):
            _set(who, k, {"분": int(m), "방법": w})
    elif typ == "meal":
        v = cur or {}
        c1, c2, c3 = st.columns([1.3, 1.3, 1])
        kind = c1.selectbox("종류", store.MEAL_KINDS,
                            index=store.MEAL_KINDS.index(v["종류"])
                            if v.get("종류") in store.MEAL_KINDS else 0,
                            key=f"k_{who}_{k}", label_visibility="collapsed")
        amt = c2.selectbox("섭취량", store.MEAL_AMOUNTS,
                           index=store.MEAL_AMOUNTS.index(v["섭취량"])
                           if v.get("섭취량") in store.MEAL_AMOUNTS else 0,
                           key=f"a_{who}_{k}", label_visibility="collapsed")
        if c3.button("저장", key=f"b_{who}_{k}", use_container_width=True):
            _set(who, k, {"종류": kind, "섭취량": amt})
    elif typ == "vitals":
        v = cur or {}
        c1, c2, c3 = st.columns([1.3, 1.3, 1])
        bp = c1.text_input("혈압", value=v.get("혈압", ""), key=f"p_{who}_{k}",
                           label_visibility="collapsed", placeholder="130/80")
        tp = c2.text_input("체온", value=v.get("체온", ""), key=f"t_{who}_{k}",
                           label_visibility="collapsed", placeholder="36.7")
        if c3.button("저장", key=f"b_{who}_{k}", use_container_width=True):
            _set(who, k, {"혈압": bp, "체온": tp})
    else:                                   # program — 프로그램명을 적는다
        c1, c2 = st.columns([3, 1])
        nm = c1.text_input("프로그램명", value=cur or "", key=f"f_{who}_{k}",
                           label_visibility="collapsed",
                           placeholder="예: 회상훈련, 음악활동")
        if c2.button("저장", key=f"b_{who}_{k}", use_container_width=True):
            _set(who, k, nm.strip())


def _set(who, k, v, src="화면"):
    if not me:
        st.warning("왼쪽에서 이름을 먼저 고르세요.")
        return
    store.set_field(who, k, v, me, src=src)
    st.rerun()


# ── 음성 기록 ─────────────────────────────────────────────────────────
def _voice_block(here):
    """말로 서식을 채운다. **말한 것을 바로 저장하지 않는다** —
    초안을 띄우고 사람이 고쳐 저장한다. 잘못 들은 기록은 되돌릴 수 없다."""
    st.subheader("말해서 기록")
    st.caption("예: \"김OO 님 기저귀 세 번 갈았어요\"  ·  "
               "\"이OO 님 목욕 25분 샤워식\"  ·  \"김OO 혈압 130에 80\"")
    heard = voice.listen_box("care")
    if heard:
        st.session_state["draft"] = heard
    with st.expander("말이 안 되는 상황이면 적어서 넣기", expanded=False):
        typed = st.text_input("문장", key="typed", label_visibility="collapsed",
                              placeholder="김OO 님 점심 죽으로 절반 넘게 드셨어요")
        if st.button("초안 만들기", key="mk_draft") and typed.strip():
            st.session_state["draft"] = typed.strip()

    raw = st.session_state.get("draft", "")
    if not raw:
        return
    d = store.parse(raw, names)
    with st.container(border=True):
        st.markdown(f"들린 말 — **{raw}**")
        if not d["이용자"]:
            st.warning("이용자를 못 알아들었습니다. 골라 주세요.")
        elif d["이용자"] not in here:
            st.warning(f"{d['이용자']} 님은 오늘 등원으로 표시돼 있지 않습니다.")
        if not d["항목"]:
            st.warning("서식 항목을 못 알아들었습니다. 골라 주세요. "
                       "서식에 없는 내용이면 아래 **인계로 넘기기**를 쓰세요.")

        c1, c2 = st.columns(2)
        u = c1.selectbox("이용자", names,
                         index=names.index(d["이용자"]) if d["이용자"] in names else 0,
                         key="v_user")
        keys = store.FIELD_KEYS
        it = c2.selectbox("서식 항목", keys,
                          index=keys.index(d["항목"]) if d["항목"] in keys else 0,
                          format_func=lambda k: store.FIELDS[k][1], key="v_item")
        typ = store.FIELDS[it][2]
        val = _draft_value(it, typ, d)
        note = st.text_input("특이사항(해당 구역에 기록)", value=d["특이사항"],
                             key="v_note")
        b1, b2, b3 = st.columns(3)
        if b1.button("확인하고 저장", type="primary", use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.set_field(u, it, val, me, src="음성")
                if note.strip():
                    store.set_section_note(u, store.FIELDS[it][0], note, me)
                st.session_state.pop("draft", None)
                st.rerun()
        # 서식에 없는 말("기분이 안 좋으세요")이 자주 온다 → 인계로 보낸다
        if b2.button("인계로 넘기기", use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.add_handover(u, "기타", note or raw, me)
                st.session_state.pop("draft", None)
                st.rerun()
        if b3.button("버리기", use_container_width=True):
            st.session_state.pop("draft", None)
            st.rerun()


def _draft_value(key, typ, d):
    """말에서 못 뽑는 세부값(분·방법·섭취량 등)은 여기서 사람이 채운다."""
    if typ == "check":
        st.caption("'제공함'으로 기록됩니다.")
        return True
    if typ == "count":
        return int(st.number_input("횟수", 0, 30, int(d.get("숫자") or 0),
                                   key="v_cnt"))
    if typ == "bath":
        c1, c2 = st.columns(2)
        m = c1.number_input("소요시간(분)", 0, 240, int(d.get("숫자") or 0),
                            key="v_min")
        w = c2.selectbox("방법", store.BATH_WAYS, key="v_way")
        return {"분": int(m), "방법": w}
    if typ == "meal":
        c1, c2 = st.columns(2)
        return {"종류": c1.selectbox("종류", store.MEAL_KINDS, key="v_kind"),
                "섭취량": c2.selectbox("섭취량", store.MEAL_AMOUNTS, key="v_amt")}
    if typ == "vitals":
        c1, c2 = st.columns(2)
        return {"혈압": c1.text_input("혈압", value=d.get("혈압", ""), key="v_bp"),
                "체온": c2.text_input("체온", value=d.get("체온", ""), key="v_tp")}
    return st.text_input("프로그램명", value=d.get("특이사항", ""), key="v_prog")


# ── 인계 ──────────────────────────────────────────────────────────────
def page_handover():
    st.header("🔄 인계")
    st.caption("다음 교대가 알아야 할 것. 기억에 의존하지 않게 남깁니다.")
    if _need_users():
        return
    with st.container(border=True):
        c1, c2 = st.columns([2, 2])
        u = c1.selectbox("이용자", names, key="h_user")
        k = c2.selectbox("종류", store.HANDOVER_KINDS, key="h_kind")
        t = st.text_input("내용", key="h_text",
                          placeholder="예: 오후에 기침 잦음. 물 자주 권할 것")
        if st.button("남기기", type="primary"):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            elif t.strip():
                store.add_handover(u, k, t, me)
                st.rerun()

    hs = store.handovers()
    st.subheader(f"오늘 인계 — {len(hs)}건")
    if not hs:
        st.caption("아직 없습니다.")
    for h in hs:
        with st.container(border=True):
            c1, c2, c3 = st.columns([7, 1.4, 1])
            c1.markdown(f"**{h['이용자']}** · {h['종류']}  \n{h['내용']}  \n"
                        f"<span class='cs-dim'>{h['시각']} {h['작성자']}"
                        + (f" · 확인 {h['확인']}" if h["확인"] else "") + "</span>",
                        unsafe_allow_html=True)
            if not h["확인"] and c2.button("확인함", key=f"ack_{h['시각']}_{h['이용자']}",
                                         use_container_width=True):
                if me:
                    store.ack_handover(h["날짜"], h["시각"], h["이용자"], me)
                    st.rerun()
                else:
                    st.warning("이름을 먼저 고르세요.")
            if c3.button("✕", key=f"hd_{h['시각']}_{h['이용자']}"):
                store.delete_handover(h["날짜"], h["시각"], h["이용자"])
                st.rerun()


# ── 일지 ──────────────────────────────────────────────────────────────
def page_log():
    st.header("📄 일지")
    st.caption("오늘 기록을 이용자별로 모읍니다. 일과 끝에 처음부터 쓰지 않아도 됩니다.")
    if _need_users():
        return
    day = st.text_input("날짜", value=store.today(), key="log_day")
    att = store.attendance(day)
    whole = []
    for u in users:
        body = store.daily_log(u["이름"], day)
        hs = [h for h in store.handovers(day) if h["이용자"] == u["이름"]]
        with st.container(border=True):
            st.markdown(f"**{u['이름']}**  "
                        f"<span class='cs-dim'>{att.get(u['이름'], '미확인')}</span>",
                        unsafe_allow_html=True)
            if body:
                st.text(body)
            else:
                st.caption("기록 없음")
            for h in hs:
                st.markdown(f"<span class='cs-dim'>인계 · {h['종류']} — "
                            f"{h['내용']}</span>", unsafe_allow_html=True)
            if body or hs:
                part = f"[{u['이름']}] {att.get(u['이름'], '')}\n{body}"
                for h in hs:
                    part += f"\n(인계 {h['종류']}) {h['내용']}"
                whole.append(part)
    if whole:
        st.download_button("📥 전체 일지 내려받기 (txt)",
                           data=("\n\n".join(whole)).encode("utf-8"),
                           file_name=f"일지_{day}.txt", mime="text/plain")
    st.divider()
    st.subheader("보호자 알림장")
    st.caption("오늘 적은 기록에서 문장을 만들어 줍니다. **읽어 보고** 문자·카톡으로 "
               "보내세요. 앱이 대신 보내지는 않습니다.")
    gwho = st.selectbox("이용자", names, key="gn_user")
    gtxt = store.guardian_note(gwho, day)
    if gtxt:
        st.text_area("알림장", gtxt, height=200, key="gn_txt")
        st.download_button("📥 텍스트로 받기", data=gtxt.encode("utf-8"),
                           file_name=f"알림장_{gwho}_{day}.txt",
                           mime="text/plain", use_container_width=True)
    else:
        st.caption("오늘 기록이 없어 만들 내용이 없습니다.")

    st.divider()
    st.subheader("월간 내보내기")
    st.caption("공단 대응·감사 때 한 달치를 한 번에 뽑습니다. "
               "엑셀에서 바로 열립니다.")
    ym = st.text_input("월(YYYY-MM)", value=store.today()[:7], key="ex_ym")
    nday = len(store.month_days(ym))
    if nday:
        st.download_button(f"📥 급여제공기록지 {ym} 내려받기 (CSV, {nday}일치)",
                           data=store.export_month_csv(ym),
                           file_name=f"급여제공기록지_{ym}.csv",
                           mime="text/csv", use_container_width=True)
    else:
        st.caption(f"{ym} 에 기록이 없습니다.")


# ── 사정·상담·결과평가 ────────────────────────────────────────────────
def page_assess():
    st.header("📝 사정·상담")
    st.caption("평가지표 30(욕구사정 연 1회) · 25(상담 분기 1회) · "
               "44(결과평가 반기, 30일 이내 계획 재작성)")
    if _need_users():
        return
    due = store.care_due()
    if due:
        st.error("기한 지남 — " + " · ".join(
            f"{n} {lab}" + (f"({g}일)" if g else "(없음)")
            for n, lab, g in due[:8])
            + (f" 외 {len(due) - 8}건" if len(due) > 8 else ""))

    who = st.selectbox("수급자", names, key="as_user")
    t1, t2, t3 = st.tabs(["욕구사정", "상담", "결과평가"])

    with t1:
        st.info("**단순 체크는 인정되지 않습니다.** 항목마다 판단 근거를 "
                "서술하세요. 예: 옷 벗고 입기 '부분도움' 만 체크 → 불인정 / "
                "\"왼쪽 편마비로 옷 갈아입을 때 일부 도움 필요\" → 인정")
        vals = {}
        for k, hint in store.ASSESS_ITEMS:
            # ⚠️ 매뉴얼은 "9개 항목"이라면서 1~8만 열거한다. 9번은 추정이다.
            _lab = f"{k}  ({hint})" + (
                "   ※ 9번 항목은 확인 필요" if k == "구강상태" else "")
            vals[k] = st.text_input(_lab, key=f"as_{k}")
        summ = st.text_area("총평 (종합소견, 서술형)", key="as_sum", height=90)
        if st.button("욕구사정 저장", type="primary", key="as_save",
                     use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.save_assessment(who, vals, summ, me)
                st.rerun()
        for x in store.assessments(who)[:3]:
            with st.container(border=True):
                st.markdown(f"**{x['작성']}** · {x['작성자']}")
                for k, v in x["항목"].items():
                    if str(v).strip():
                        st.markdown(f"- **{k}** {v}")
                if x.get("총평"):
                    st.markdown(f"총평 — {x['총평']}")

    with t2:
        st.caption("필수 기재: 상담일자 · 수급자명 · 상담직원명 · "
                   "상담대상자명(관계) · 상담내용. 내방·방문·전화 모두 인정됩니다"
                   "(일방향 소통은 제외).")
        c1, c2, c3 = st.columns(3)
        cdate = c1.text_input("상담일자", value=store.today(), key="cs_d")
        ctgt = c2.text_input("상담대상자", key="cs_t", placeholder="예: 김AA")
        crel = c3.text_input("관계", key="cs_r", placeholder="예: 자녀 / 본인")
        cbody = st.text_area("상담내용 (상태·욕구·건의사항)", key="cs_b",
                             height=90)
        if st.button("상담 저장", type="primary", key="cs_save",
                     use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.save_counsel(who, cdate, ctgt, crel, cbody, me)
                st.rerun()
        for x in store.counsels(who)[:5]:
            st.markdown(f"**{x['상담일자']}** {x.get('상담대상자', '')}"
                        f"({x.get('관계', '')}) — {x['상담내용']}<br>"
                        f"<span class='cs-dim'>상담직원 {x['상담직원']}</span>",
                        unsafe_allow_html=True)

    with t3:
        st.caption("결과평가는 **반기별**입니다. 결과를 반영해 급여제공계획서를 "
                   "**30일 이내에 재작성**해야 합니다.")
        per = st.text_input("평가기간", key="rs_p",
                            placeholder="2026-01-01 ~ 2026-06-30")
        ach = st.text_area("목표 달성 정도", key="rs_a", height=70)
        chg = st.text_area("수급자 상태 변화", key="rs_c", height=70)
        nxt = st.text_area("계획 반영 사항", key="rs_n", height=70)
        if st.button("결과평가 저장", type="primary", key="rs_save",
                     use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.save_result(who, per, ach, chg, nxt, me)
                st.rerun()
        for x in store.results(who)[:3]:
            with st.container(border=True):
                st.markdown(f"**{x['작성']}** · {x.get('평가기간', '')} · "
                            f"{x['작성자']}")
                for k in ("목표달성", "상태변화", "계획반영"):
                    if str(x.get(k, "")).strip():
                        st.markdown(f"- **{k}** {x[k]}")


# ── 구매요청 ──────────────────────────────────────────────────────────
def page_buy():
    st.header("🛒 구매요청")
    st.caption("위생용품·프로그램 재료처럼 현장에서 떨어지는 것을 적어 둡니다.")
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 1])
        it = c1.text_input("품목", key="by_it", placeholder="예: 성인용 기저귀 L")
        kd = c2.selectbox("분류", store.BUY_KINDS, key="by_kd")
        qt = c3.text_input("수량", key="by_qt", placeholder="2박스")
        wy = st.text_input("사유(선택)", key="by_wy",
                           placeholder="예: 이번 주 소진 예정")
        if st.button("요청 등록", type="primary", key="by_add",
                     use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                try:
                    store.add_buy(it, kd, qt, wy, me)
                    st.rerun()
                except ValueError as e:
                    st.warning(str(e))

    rows = store.buys()
    wait = [x for x in rows if x["상태"] in ("요청", "구매중")]
    done = [x for x in rows if x["상태"] not in ("요청", "구매중")]
    st.subheader(f"처리 대기 — {len(wait)}건")
    for x in wait:
        _buy_row(x)
    if done:
        st.subheader(f"완료·보류 — {len(done)}건")
        for x in done[:20]:
            _buy_row(x)


def _buy_row(x):
    with st.container(border=True):
        c1, c2, c3 = st.columns([6, 2, 1])
        c1.markdown(f"**{x['품목']}** {x.get('수량', '')}<br>"
                    f"<span class='cs-dim'>{x['분류']} · {x['요청자']} · "
                    f"{x['등록']}" + (f" · {x['사유']}" if x.get("사유") else "")
                    + "</span>", unsafe_allow_html=True)
        cur = x.get("상태", "요청")
        pick = c2.selectbox("상태", store.BUY_STATES,
                            index=store.BUY_STATES.index(cur)
                            if cur in store.BUY_STATES else 0,
                            key=f"bys_{x['등록']}", label_visibility="collapsed")
        if pick != cur:
            store.set_buy(x["등록"], pick)
            st.rerun()
        if c3.button("✕", key=f"byx_{x['등록']}"):
            store.delete_buy(x["등록"])
            st.rerun()


# ── 급여제공계획서 ────────────────────────────────────────────────────
def page_plan():
    st.header("📋 급여제공계획서")
    st.caption("노인장기요양보험법 시행규칙 **별지 제11호의4서식** "
               "(시설급여·주야간보호·단기보호). 개정 2021. 6. 30.")
    st.info("서식 작성방법: 개인별장기요양이용계획서의 급여종류 범위 안에서 "
            "기능상태·욕구를 고려해 **급여 개시 전에** 작성하고, 수급자 또는 "
            "가족에게 충분히 설명한 뒤 **동의를 받아** 공단에 통보합니다.")
    if _need_users():
        return

    miss = store.plan_missing()
    if miss:
        st.warning("계획서가 없는 이용자 — " + ", ".join(miss)
                   + "  (평가지표 22: 연 1회 이상 수립)")

    who = st.selectbox("수급자", names, key="pl_user")
    last = store.latest_plan(who)
    if last:
        with st.container(border=True):
            st.markdown(f"**최근 계획서** {last['작성']} · 작성자 "
                        f"{last.get('작성자', '')}")
            st.markdown(f"목표 — {last.get('목표', '')}")
            for r in last.get("내용", []):
                line = " · ".join(f"{k} {r.get(k, '')}" for k in store.PLAN_ROW
                                  if str(r.get(k, "")).strip())
                if line:
                    st.markdown(f"- {line}")
            ag = last.get("동의자", {})
            if ag.get("성명"):
                st.caption(f"동의자 {ag['성명']}({ag.get('관계', '')}) · "
                           f"동의일 {ag.get('동의일', '')}")
            else:
                st.markdown("<span class='cs-warn'>동의 정보 없음 — 서식상 "
                            "동의 없이 공단 통보를 할 수 없습니다.</span>",
                            unsafe_allow_html=True)
            if st.button("이 계획서 삭제", key=f"plx_{last['작성']}"):
                store.delete_plan(who, last["작성"])
                st.rerun()
    else:
        st.caption("등록된 계획서가 없습니다.")

    st.divider()
    st.subheader("새 계획서 작성")
    head = {}
    cols = st.columns(3)
    for i, k in enumerate(store.PLAN_HEAD):
        with cols[i % 3]:
            head[k] = st.text_input(k, key=f"plh_{k}")
    goal = st.text_area("목표 (급여 제공으로 얻고자 하는 종합적 효과)",
                        key="pl_goal", height=70)

    st.markdown("**급여제공계획 내용**")
    st.caption("한 줄이 '무엇을 얼마나 자주' 하나입니다. "
               "예: 세부 제공내용 = 옷 갈아입기 도움 → 옷 준비와 상의 단추 채우기 도움")
    nrow = st.number_input("줄 수", 1, 10, 3, key="pl_n")
    rows = []
    for i in range(int(nrow)):
        c = st.columns(6)
        row = {}
        for j, k in enumerate(store.PLAN_ROW):
            row[k] = c[j].text_input(f"{k} {i + 1}", key=f"plr_{i}_{k}",
                                     label_visibility="collapsed"
                                     if i else "visible")
        rows.append(row)

    opinion = st.text_area("종합의견", key="pl_op", height=70,
                           placeholder="서비스 제공자·가족과 공유할 사항, "
                                       "이용계획서와 다르게 제공하는 경우 그 사유")
    c1, c2 = st.columns(2)
    writer = c1.text_input("작성자 (직종·성명)", value=me, key="pl_w")
    manager = c2.text_input("총괄 확인자 (직종·성명)", key="pl_m")
    st.markdown("**동의자**")
    a1, a2, a3 = st.columns(3)
    an = a1.text_input("성명", key="pl_an")
    ar = a2.text_input("수급자와의 관계", key="pl_ar")
    ad = a3.text_input("동의일", key="pl_ad", placeholder="2026-08-11")

    if st.button("계획서 저장", type="primary", key="pl_save",
                 use_container_width=True):
        if not me:
            st.warning("왼쪽에서 이름을 먼저 고르세요.")
        else:
            store.save_plan(who, head, goal,
                            [r for r in rows if any(str(v).strip()
                                                    for v in r.values())],
                            opinion, writer, manager, an, ar, ad)
            st.success("저장했습니다.")
            st.rerun()


# ── 대장·점검 ─────────────────────────────────────────────────────────
def page_logs():
    st.header("📚 대장·점검")
    st.caption("2026년 장기요양기관 재가급여(주야간보호) **평가지표**가 요구하는 "
               "주기별 기록입니다. 마지막 기록일로부터 며칠 지났는지 세어 줍니다.")

    st.subheader("주기 현황")
    for k in store.LOG_KEYS:
        stt = store.log_status(k)
        c1, c2, c3 = st.columns([3, 2, 5])
        c1.markdown(f"**{stt['이름']}**")
        c2.markdown(f"<span class='cs-dim'>{stt['주기']}</span>",
                    unsafe_allow_html=True)
        if stt["마지막"] is None:
            c3.markdown("<span class='cs-warn'>기록 없음</span>",
                        unsafe_allow_html=True)
        elif stt["늦음"]:
            c3.markdown(f"<span class='cs-warn'>기한 지남 — 마지막 "
                        f"{stt['마지막']} ({stt['경과']}일 전)</span>",
                        unsafe_allow_html=True)
        else:
            c3.markdown(f"마지막 {stt['마지막']} "
                        f"<span class='cs-dim'>({stt['경과']}일 전)</span>",
                        unsafe_allow_html=True)

    st.divider()
    key = st.selectbox("대장 고르기", store.LOG_KEYS,
                       format_func=lambda k: store.LOG_SPEC[k][0], key="lg_pick")
    name, cycle, basis, fields = store.LOG_SPEC[key]
    st.markdown(f"### {name}")
    st.caption(f"주기 {cycle} · 근거: {basis}")

    with st.container(border=True):
        day = st.text_input("날짜", value=store.today(), key=f"lgd_{key}")
        vals = {}
        cols = st.columns(2)
        for i, (fname, ftype) in enumerate(fields):
            with cols[i % 2]:
                vals[fname] = _log_field(key, fname, ftype)
        if st.button("기록 추가", type="primary", key=f"lga_{key}",
                     use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.add_log(key, vals, me, day)
                st.rerun()

    rs = store.logs(key, 30)
    st.subheader(f"기록 — {len(rs)}건")
    if not rs:
        st.caption("아직 기록이 없습니다.")
    for r in rs:
        c1, c2 = st.columns([9, 1])
        body = " · ".join(f"{k} {v}" for k, v in r["값"].items()
                          if str(v).strip())
        c1.markdown(f"**{r['날짜']}** {body}<br>"
                    f"<span class='cs-dim'>{r['작성자']} {r.get('등록', '')}</span>",
                    unsafe_allow_html=True)
        if c2.button("✕", key=f"lgx_{key}_{r['날짜']}_{r.get('등록', '')}"):
            store.delete_log(key, r["날짜"], r.get("등록", ""))
            st.rerun()


def _log_field(key, fname, ftype):
    """대장 항목 한 칸. staff/user 는 등록된 명단에서 고른다."""
    wk = f"lg_{key}_{fname}"
    if ftype == "num":
        return int(st.number_input(fname, 0, 999, 0, key=wk))
    if ftype == "staff":
        opts = [s["이름"] for s in store.staff()] or [me or "-"]
        return st.selectbox(fname, opts, key=wk)
    if ftype == "user":
        return st.selectbox(fname, names or ["-"], key=wk)
    if isinstance(ftype, list):
        return st.selectbox(fname, ftype, key=wk)
    return st.text_input(fname, key=wk)


# ── 기기 대장 ─────────────────────────────────────────────────────────
def page_devices():
    st.header("🤖 기기 대장")
    st.caption("시설에 들어온 돌봄로봇·센서와 그 **매뉴얼·문의처**. "
               "조사한 요양 SW 6종에는 없는 칸입니다.")
    ds = store.devices()

    with st.expander("➕ 기기 등록", expanded=not ds):
        c1, c2, c3 = st.columns(3)
        nm = c1.text_input("기기명", key="dv_nm", placeholder="예: 효돌")
        mk = c2.text_input("제조사", key="dv_mk")
        md = c3.text_input("모델", key="dv_md")
        c4, c5 = st.columns(2)
        pl = c4.text_input("위치", key="dv_pl", placeholder="예: 프로그램실")
        sc = c5.text_input("도입일", key="dv_sc", placeholder="2026-03-02")
        nt = st.text_input("비고", key="dv_nt")
        if st.button("등록", type="primary", key="dv_add"):
            try:
                store.add_device(nm, mk, md, pl, "사용중", sc, nt)
                st.rerun()
            except ValueError as e:
                st.warning(str(e))

    if not ds:
        st.caption("등록된 기기가 없습니다.")
    for d in ds:
        with st.container(border=True):
            c1, c2, c3 = st.columns([6, 2, 1])
            head = f"### {d['기기명']}"
            sub = " · ".join(x for x in (d.get("제조사"), d.get("모델"),
                                         d.get("위치")) if x)
            c1.markdown(head + (f"<br><span class='cs-dim'>{sub}</span>"
                                if sub else ""), unsafe_allow_html=True)
            cur = d.get("상태", "사용중")
            pick = c2.selectbox("상태", store.DEVICE_STATES,
                                index=store.DEVICE_STATES.index(cur)
                                if cur in store.DEVICE_STATES else 0,
                                key=f"dvs_{d['기기명']}",
                                label_visibility="collapsed")
            if pick != cur:
                store.set_device_state(d["기기명"], pick)
                st.rerun()
            if c3.button("✕", key=f"dvx_{d['기기명']}"):
                store.delete_device(d["기기명"])
                st.rerun()
            docs = store.device_docs(d["기기명"])
            if docs:
                for doc in docs:
                    line = f"- {doc['종류']} — [{doc['제목']}]({doc['링크']})"
                    if doc.get("문의처"):
                        line += f"  <span class='cs-dim'>문의 {doc['문의처']}</span>"
                    st.markdown(line, unsafe_allow_html=True)
            else:
                st.caption("등록된 자료가 없습니다. 아래에서 매뉴얼 링크를 넣으세요.")

    st.divider()
    st.subheader("기기 자료 등록")
    st.caption("**파일이 아니라 링크**를 받습니다. 제조사가 매뉴얼을 개정하면 "
               "링크는 저절로 최신본이 됩니다.")
    c1, c2 = st.columns(2)
    dn = c1.text_input("기기명", key="dc_nm",
                       placeholder="대장의 기기명과 같게")
    dk = c2.selectbox("종류", store.DOC_KINDS, key="dc_kd")
    ti = st.text_input("제목", key="dc_ti", placeholder="예: 효돌 사용설명서 v2")
    lk = st.text_input("링크", key="dc_lk", placeholder="https://...")
    ct = st.text_input("문의처(선택)", key="dc_ct", placeholder="전화·이메일")
    if st.button("자료 등록", type="primary", key="dc_add"):
        try:
            store.add_device_doc(dn, dk, ti, lk, ct)
            st.rerun()
        except ValueError as e:
            st.warning(str(e))
    for doc in store.device_docs():
        c1, c2 = st.columns([9, 1])
        c1.markdown(f"**{doc['기기명']}** · {doc['종류']} — "
                    f"[{doc['제목']}]({doc['링크']})", unsafe_allow_html=True)
        if c2.button("✕", key=f"dcx_{doc['제목']}_{doc['링크'][:20]}"):
            store.delete_device_doc(doc["제목"], doc["링크"])
            st.rerun()


# ── 근무표 ────────────────────────────────────────────────────────────
def page_shift():
    st.header("🗓 근무표")
    st.caption("인력 배치는 평가지표 3(인력기준)·4(추가배치)에 걸립니다. "
               "누가 언제 근무했는지 기록으로 남깁니다.")
    ss = store.staff()
    if not ss:
        st.info("먼저 **⚙️ 직원·설정** 에서 직원을 등록하세요.")
        return
    day = st.text_input("날짜", value=store.today(), key="sh_day")
    cur = store.shifts(day)
    opts = [""] + store.SHIFTS
    for s_ in ss:
        c1, c2 = st.columns([2, 6])
        c1.markdown(f"**{s_['이름']}** <span class='cs-dim'>{s_['직무']}</span>",
                    unsafe_allow_html=True)
        now = cur.get(s_["이름"], "")
        pick = c2.radio(s_["이름"], opts,
                        index=opts.index(now) if now in opts else 0,
                        key=f"sh_{day}_{s_['이름']}", horizontal=True,
                        label_visibility="collapsed")
        if pick != now:
            store.set_shift(s_["이름"], pick, day)
            st.rerun()
    duty = store.on_duty(day)
    st.success(f"근무 {len(duty)}명 — {', '.join(duty)}" if duty
               else "근무로 표시된 직원이 없습니다.")


# ── 건의 ──────────────────────────────────────────────────────────────
def page_suggest():
    st.header("💡 건의")
    st.caption("현장에서 불편한 것·고쳤으면 하는 것을 남깁니다.")
    c1, c2 = st.columns([1, 4])
    kind = c1.selectbox("분류", ["개선", "오류", "문의", "기기 이상"],
                        key="sg_kind")
    txt = c2.text_input("내용", key="sg_text")
    if st.button("등록", type="primary", key="sg_add"):
        if not me:
            st.warning("왼쪽에서 이름을 먼저 고르세요.")
        elif txt.strip():
            store.add_suggestion(txt, me, kind)
            st.rerun()
    for x in store.suggestions():
        with st.container(border=True):
            c1, c2, c3 = st.columns([6, 2, 1])
            c1.markdown(f"[{x['분류']}] {x['내용']}<br>"
                        f"<span class='cs-dim'>{x['작성자']} · {x['등록']}"
                        + (f" · {x['처리']}" if x.get("처리") else "")
                        + "</span>", unsafe_allow_html=True)
            nowst = x.get("상태", "접수")
            pick = c2.selectbox("상태", store.SUG_STATES,
                                index=store.SUG_STATES.index(nowst)
                                if nowst in store.SUG_STATES else 0,
                                key=f"sgs_{x['등록']}",
                                label_visibility="collapsed")
            if pick != nowst:
                store.set_suggestion(x["등록"], pick, x.get("처리", ""))
                st.rerun()
            if c3.button("✕", key=f"sgx_{x['등록']}"):
                store.delete_suggestion(x["등록"])
                st.rerun()


# ── 이용자 ────────────────────────────────────────────────────────────
def page_users():
    st.header("🧑‍🦳 이용자")
    with st.expander("➕ 이용자 등록", expanded=not users):
        c1, c2, c3 = st.columns(3)
        nm = c1.text_input("이름(가명·코드 권장)", key="u_name")
        br = c2.text_input("생년(선택)", key="u_birth", placeholder="1943")
        rm = c3.text_input("자리·호실(선택)", key="u_room")
        ca = st.text_input("주의사항", key="u_caution",
                           placeholder="예: 낙상 위험 / 삼킴 곤란 / 당뇨")
        nt = st.text_area("메모(선택)", key="u_note", height=60)
        if st.button("등록", type="primary"):
            try:
                store.add_user(nm, br, rm, nt, ca)
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
    if not users:
        st.caption("등록된 이용자가 없습니다.")
        return
    done = store.done_map()
    att = store.attendance()
    for u in users:
        with st.container(border=True):
            c1, c2 = st.columns([8, 1])
            head = f"### {u['이름']}"
            if u.get("자리"):
                head += f"  <span class='cs-dim'>{u['자리']}</span>"
            head += f"  <span class='cs-dim'>· {att.get(u['이름'], '미확인')}</span>"
            c1.markdown(head, unsafe_allow_html=True)
            if u.get("주의사항"):
                c1.markdown(f"<span class='cs-warn'>⚠ {u['주의사항']}</span>",
                            unsafe_allow_html=True)
            todo = [store.FIELDS[k][1] for k in store.FIELD_KEYS
                    if u["이름"] not in done.get(k, set())]
            c1.caption("서식에서 안 채운 칸: "
                       + (", ".join(todo) if todo else "없음"))
            if u.get("메모"):
                c1.caption(u["메모"])
            if c2.button("삭제", key=f"du_{u['이름']}"):
                store.delete_user(u["이름"])
                st.rerun()


# ── 공지 ──────────────────────────────────────────────────────────────
def page_notice():
    st.header("📌 공지")
    t = st.text_area("공지 내용", key="n_text", height=80)
    if st.button("등록", type="primary"):
        if not me:
            st.warning("왼쪽에서 이름을 먼저 고르세요.")
        elif t.strip():
            store.add_notice(t, me)
            st.rerun()
    for n in store.notices():
        c1, c2 = st.columns([9, 1])
        c1.markdown(f"{n['내용']}  \n<span class='cs-dim'>{n['작성자']} · "
                    f"{n['등록']}</span>", unsafe_allow_html=True)
        if c2.button("✕", key=f"dn_{n['등록']}"):
            store.delete_notice(n["등록"])
            st.rerun()


# ── 직원·설정 ─────────────────────────────────────────────────────────
def page_staff():
    st.header("⚙️ 직원·설정")
    c1, c2, c3 = st.columns([2, 2, 1])
    nm = c1.text_input("직원 이름", key="s_name")
    ro = c2.selectbox("직무", ["요양보호사", "사회복지사", "간호(조무)사",
                              "물리·작업치료사", "센터장", "운전원"], key="s_role")
    if c3.button("추가", use_container_width=True):
        try:
            store.add_staff(nm, ro)
            st.rerun()
        except ValueError as e:
            st.warning(str(e))
    for s in store.staff():
        c1, c2 = st.columns([9, 1])
        c1.markdown(f"**{s['이름']}** <span class='cs-dim'>{s['직무']}</span>",
                    unsafe_allow_html=True)
        if c2.button("✕", key=f"ds_{s['이름']}"):
            store.delete_staff(s["이름"])
            st.rerun()
    st.divider()
    st.subheader("PIN (로그인)")
    st.caption("PIN 을 하나라도 걸면 로그인 화면이 생깁니다. 숫자 4~8자리. "
               "저장은 해시로만 되어 사람이 되읽을 수 없습니다(재발급만 가능).")
    for s_ in store.staff():
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        c1.markdown(f"**{s_['이름']}**")
        c2.markdown("설정됨" if store.has_pin(s_["이름"]) else
                    "<span class='cs-dim'>없음</span>", unsafe_allow_html=True)
        newpin = c3.text_input("PIN", key=f"pin_{s_['이름']}", type="password",
                               max_chars=8, label_visibility="collapsed",
                               placeholder="숫자 4~8")
        if c4.button("발급", key=f"pinb_{s_['이름']}",
                     use_container_width=True):
            try:
                store.set_pin(s_["이름"], newpin)
                st.success(f"{s_['이름']} PIN 설정됨")
                st.rerun()
            except ValueError as e:
                st.warning(str(e))

    st.divider()
    st.subheader("케어 항목")
    st.caption("지금 항목은 논문(주간보호센터 워크숍)의 하루 일과 기준입니다. "
               "급여제공기록지 서식 확인 후 `store.CARE_ITEMS` 를 그것에 맞춥니다.")
    for k, label, hhmm in store.CARE_ITEMS:
        st.markdown(f"- {hhmm}  **{label}**  <span class='cs-dim'>{k}</span>",
                    unsafe_allow_html=True)
    st.divider()
    st.subheader("백업")
    st.caption("데이터는 이 PC의 `care_studio/data/` 에만 있습니다. "
               "**날리면 복구가 안 됩니다.** 주기적으로 내려받아 두세요.")
    st.download_button("🗄 전체 데이터 백업 (zip)", data=store.backup_zip(),
                       file_name=f"요양시설스튜디오_백업_{store.today()}.zip",
                       mime="application/zip", use_container_width=True)


{"🏠 홈": page_home, "✅ 케어 기록": page_care, "🔄 인계": page_handover,
 "📄 일지": page_log, "📝 사정·상담": page_assess,
 "📋 급여제공계획서": page_plan,
 "📚 대장·점검": page_logs, "🧑‍🦳 이용자": page_users,
 "🤖 기기 대장": page_devices, "🗓 근무표": page_shift, "🛒 구매요청": page_buy, "💡 건의": page_suggest,
 "📌 공지": page_notice,
 "⚙️ 직원·설정": page_staff}[st.session_state["menu"]]()
