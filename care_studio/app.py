"""요양시설 스튜디오 — 주간보호센터·소형 요양원용 돌봄 업무 앱.

Dolbom Studio(우리 팀 업무 공간)와 **같은 구조**로 만든다 — 사이드바 메뉴,
홈 대시보드, 공지, 기록. 쓰는 사람만 연구원에서 요양보호사로 바뀐다.

1단계 범위: 출결 · 케어 기록 · 인계 · 일지 · 공지.
음성 기록은 그 다음 단계에서 이 위에 얹는다(`voice.py`는 이미 있음).

**저장은 항상 사람이 누른 뒤에만** 일어난다. 자동 확정 없음.
"""
import streamlit as st

import store
import voice

st.set_page_config(page_title="요양시설 스튜디오", page_icon="🏥", layout="wide")

st.markdown("""<style>
  section[data-testid="stMain"] .block-container{ padding-top:2.6rem; }
  h1,h2,h3{ color:#8A3F12; }
  section[data-testid="stSidebar"]{ background:#2B2018; }
  section[data-testid="stSidebar"] *{ color:#EFE5D8 !important; }
  section[data-testid="stSidebar"] .stButton>button{
    background:transparent; border:none; text-align:left !important;
    justify-content:flex-start !important; font-size:1.02rem; font-weight:600;
    padding:6px 12px; border-radius:8px; margin:1px 0; width:100%; }
  section[data-testid="stSidebar"] .stButton>button:hover{ background:#3c2d22; }
  section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
    background:#C4622D; color:#fff !important; }
  .cs-warn{ color:#C4622D; font-weight:700; }
  .cs-dim{ opacity:.55; font-size:.8rem; }
</style>""", unsafe_allow_html=True)

MENUS = [("현장", ["🏠 홈", "✅ 케어 기록", "🔄 인계"]),
         ("기록", ["📄 일지", "📚 대장·점검", "🧑‍🦳 이용자"]),
         ("운영", ["📌 공지", "⚙️ 직원·설정"])]
ALL = [m for _, ms in MENUS for m in ms]

if "menu" not in st.session_state:
    st.session_state["menu"] = ALL[0]


def _go(m):
    st.session_state["menu"] = m
    st.rerun()


with st.sidebar:
    st.markdown("### 🏥 요양시설 스튜디오")
    st.caption("주간보호센터 · 소형 요양원")
    _names = [s["이름"] for s in store.staff()]
    if _names:
        st.session_state["me"] = st.selectbox(
            "나", _names,
            index=_names.index(st.session_state["me"])
            if st.session_state.get("me") in _names else 0)
    else:
        st.session_state["me"] = st.text_input("나(이름)",
                                               value=st.session_state.get("me", ""))
        st.caption("⚙️ 직원·설정에서 직원을 등록하면 목록에서 고를 수 있습니다.")
    st.divider()
    for cat, ms in MENUS:
        st.markdown(f"<div class='cs-dim' style='margin:10px 6px 2px;"
                    f"letter-spacing:1px'>{cat}</div>", unsafe_allow_html=True)
        for m in ms:
            if st.button(m, key=f"nav_{m}",
                         type="primary" if st.session_state["menu"] == m else "secondary"):
                _go(m)
    st.divider()
    st.caption("⚠️ 시연·시험 단계. 이용자는 **가명·코드**로 등록하세요.")

me = st.session_state.get("me", "")
users = store.users()
names = [u["이름"] for u in users]


def _need_users():
    if not users:
        st.info("먼저 **🧑‍🦳 이용자** 에서 이용자를 등록하세요.")
        return True
    return False


# ── 홈 ────────────────────────────────────────────────────────────────
def page_home():
    st.header("🏠 홈")
    st.caption(f"{store.today()} · {me or '이름을 먼저 고르세요'}")

    ns = store.notices()
    if ns:
        st.markdown("**📌 공지**")
        for n in ns[:3]:
            # st.info 는 HTML 을 그리지 않는다 — 태그가 글자로 보였다. 마크다운만.
            st.info(f"{n['내용']}  \n*{n['작성자']} · {n['등록']}*", icon="📌")
    if _need_users():
        return

    att = store.attendance()
    here = [u for u, s in att.items() if s == "등원"]
    absent = [u for u, s in att.items() if s == "결석"]
    unknown = [u for u, s in att.items() if s == "미확인"]
    done = store.done_map()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("등원", f"{len(here)} / {len(users)}")
    c2.metric("결석", len(absent))
    c3.metric("출결 미확인", len(unknown))
    _left = sum(1 for k in store.FIELD_KEYS for u in here
                if u not in done.get(k, set()))
    c4.metric("빈 칸", _left)

    if unknown:
        st.warning("출결 미확인 — " + ", ".join(unknown[:10])
                   + ("…" if len(unknown) > 10 else ""))

    # 평가지표는 주기가 정해져 있다. 넘긴 것을 홈에서 먼저 보여준다.
    od = store.overdue_logs()
    if od:
        st.error("기한이 지난 기록 — " + " · ".join(
            f"{stt['이름']}({stt['주기']})" for _k, stt in od[:6])
            + (f" 외 {len(od) - 6}건" if len(od) > 6 else ""))

    left, right = st.columns([1.5, 1])
    with left:
        st.subheader("아직 안 채운 칸")
        if not here:
            st.caption("등원한 이용자가 없습니다. **✅ 케어 기록**에서 출결을 먼저 찍으세요.")
        else:
            rows = []
            for key in store.FIELD_KEYS:
                miss = [u for u in here if u not in done.get(key, set())]
                if miss:
                    rows.append((store.FIELDS[key][0], store.FIELDS[key][1], miss))
            if not rows:
                st.success("서식이 모두 채워졌습니다.")
            for sec, label, miss in rows:
                st.markdown(f"**{label}** <span class='cs-dim'>{sec}</span> — "
                            f"{len(miss)}명 남음  \n"
                            f"<span class='cs-dim'>{', '.join(miss)}</span>",
                            unsafe_allow_html=True)
    with right:
        st.subheader("🔄 오늘 인계")
        hs = store.handovers()
        if not hs:
            st.caption("인계 내용이 없습니다.")
        for h in hs[:6]:
            mark = "✔" if h["확인"] else "•"
            st.markdown(f"{mark} **{h['이용자']}** ({h['종류']}) {h['내용']}  \n"
                        f"<span class='cs-dim'>{h['시각']} {h['작성자']}</span>",
                        unsafe_allow_html=True)


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
    st.caption("※ 급여제공기록지 서식(복지부 고시)은 아직 확인하지 못했습니다. "
               "확인 후 항목명과 이 양식을 그 서식에 맞춥니다.")


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
    st.subheader("케어 항목")
    st.caption("지금 항목은 논문(주간보호센터 워크숍)의 하루 일과 기준입니다. "
               "급여제공기록지 서식 확인 후 `store.CARE_ITEMS` 를 그것에 맞춥니다.")
    for k, label, hhmm in store.CARE_ITEMS:
        st.markdown(f"- {hhmm}  **{label}**  <span class='cs-dim'>{k}</span>",
                    unsafe_allow_html=True)
    st.divider()
    st.caption("데이터는 이 PC의 `care_studio/data/` 에만 저장됩니다.")


{"🏠 홈": page_home, "✅ 케어 기록": page_care, "🔄 인계": page_handover,
 "📄 일지": page_log, "📚 대장·점검": page_logs, "🧑‍🦳 이용자": page_users,
 "📌 공지": page_notice,
 "⚙️ 직원·설정": page_staff}[st.session_state["menu"]]()
