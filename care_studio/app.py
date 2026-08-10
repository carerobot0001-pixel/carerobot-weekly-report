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
         ("기록", ["📄 일지", "🧑‍🦳 이용자"]),
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
    _left = sum(1 for k in store.ITEM_KEYS for u in here
                if u not in done.get(k, set()))
    c4.metric("남은 케어", _left)

    if unknown:
        st.warning("출결 미확인 — " + ", ".join(unknown[:10])
                   + ("…" if len(unknown) > 10 else ""))

    left, right = st.columns([1.5, 1])
    with left:
        st.subheader("오늘 남은 케어")
        if not here:
            st.caption("등원한 이용자가 없습니다. **✅ 케어 기록**에서 출결을 먼저 찍으세요.")
        else:
            rows = []
            for key in store.ITEM_KEYS:
                miss = [u for u in here if u not in done.get(key, set())]
                if miss:
                    rows.append((store.ITEM_TIME[key], store.ITEM_LABEL[key], miss))
            if not rows:
                st.success("오늘 케어가 모두 기록됐습니다.")
            for hhmm, label, miss in sorted(rows):
                st.markdown(f"**{hhmm} {label}** — {len(miss)}명 남음  \n"
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


# ── 케어 기록 ─────────────────────────────────────────────────────────
def page_care():
    st.header("✅ 케어 기록")
    if _need_users():
        return
    att = store.attendance()

    st.subheader("출결")
    cols = st.columns(min(4, len(users)))
    for i, u in enumerate(users):
        with cols[i % len(cols)]:
            cur = att[u["이름"]]
            pick = st.radio(u["이름"], store.ATT,
                            index=store.ATT.index(cur),
                            key=f"att_{u['이름']}", horizontal=True)
            if pick != cur:
                store.set_attendance(u["이름"], pick)
                st.rerun()

    st.divider()
    here = [u for u, s in att.items() if s == "등원"]
    if not here:
        st.info("등원으로 표시된 이용자가 없습니다.")
        return

    _voice_block(here)

    st.divider()
    st.subheader("케어 체크")
    st.caption("한 것만 누르면 됩니다. 특이사항이 있으면 그 줄에 적으세요.")
    done = store.done_map()
    item = st.selectbox("항목", store.ITEM_KEYS,
                        format_func=lambda k: f"{store.ITEM_TIME[k]} "
                                              f"{store.ITEM_LABEL[k]}")
    for u in here:
        c1, c2, c3 = st.columns([2, 5, 2])
        already = u in done.get(item, set())
        c1.markdown(("✅ " if already else "") + f"**{u}**")
        note = c2.text_input("특이사항", key=f"n_{item}_{u}",
                             label_visibility="collapsed",
                             placeholder="특이사항(선택)")
        if already:
            c3.caption("기록됨")
        else:
            b1, b2 = c3.columns(2)
            if b1.button("완료", key=f"ok_{item}_{u}", use_container_width=True):
                if not me:
                    st.warning("왼쪽에서 이름을 먼저 고르세요.")
                else:
                    store.add_record(u, item, "완료", note, me, "화면")
                    st.rerun()
            if b2.button("거부", key=f"no_{item}_{u}", use_container_width=True):
                if not me:
                    st.warning("왼쪽에서 이름을 먼저 고르세요.")
                else:
                    store.add_record(u, item, "거부", note, me, "화면")
                    st.rerun()

    st.divider()
    rs = sorted(store.records(), key=lambda r: r["시각"], reverse=True)
    st.subheader(f"오늘 기록 — {len(rs)}건")
    for r in rs[:30]:
        c1, c2 = st.columns([9, 1])
        line = (f"**{r['시각']}** {r['이용자']} · "
                f"{store.ITEM_LABEL.get(r['항목'], r['항목'])} · {r['상태']}")
        if r["특이사항"]:
            line += f" — {r['특이사항']}"
        line += f"  <span class='cs-dim'>{r['기록자']}</span>"
        c1.markdown(line, unsafe_allow_html=True)
        if c2.button("✕", key=f"d_{r['시각']}_{r['이용자']}_{r['항목']}"):
            store.delete_record(r["날짜"], r["시각"], r["이용자"], r["항목"])
            st.rerun()


# ── 음성 기록 ─────────────────────────────────────────────────────────
def _voice_block(here):
    """말로 케어를 기록한다. **말한 것을 바로 저장하지 않는다** —
    초안을 띄우고 사람이 고쳐 저장한다. 잘못 들은 기록은 되돌릴 수 없다."""
    st.subheader("🎤 말해서 기록")
    st.caption("예: \"김OO 님 배설 완료, 시간이 좀 걸렸어요\"  ·  "
               "말하면 아래에 초안이 뜹니다. 확인 후 저장하세요.")
    heard = voice.listen_box("care")
    if heard:
        st.session_state["draft"] = heard

    with st.expander("말이 안 되는 상황이면 적어서 넣기", expanded=False):
        typed = st.text_input("문장", key="typed",
                              label_visibility="collapsed",
                              placeholder="김OO 님 점심 다 드셨어요")
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
            st.warning("항목을 못 알아들었습니다. 골라 주세요.")

        c1, c2, c3 = st.columns([2, 2, 1])
        u = c1.selectbox("이용자", names,
                         index=names.index(d["이용자"]) if d["이용자"] in names else 0,
                         key="v_user")
        it = c2.selectbox(
            "항목", store.ITEM_KEYS,
            index=(store.ITEM_KEYS.index(d["항목"])
                   if d["항목"] in store.ITEM_KEYS else 0),
            format_func=lambda k: store.ITEM_LABEL[k], key="v_item")
        sts = ["완료", "일부", "거부"]
        stt = c3.selectbox("상태", sts,
                           index=sts.index(d["상태"]) if d["상태"] in sts else 0,
                           key="v_stat")
        note = st.text_input("특이사항", value=d["특이사항"], key="v_note")
        b1, b2, b3 = st.columns(3)
        if b1.button("✅ 확인하고 저장", type="primary", use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.add_record(u, it, stt, note, me, "음성")
                st.session_state.pop("draft", None)
                st.rerun()
        # 인계로 보내기 — "기분이 안 좋으세요" 처럼 케어 항목이 아닌 말이 자주 온다
        if b2.button("🔄 인계로 넘기기", use_container_width=True):
            if not me:
                st.warning("왼쪽에서 이름을 먼저 고르세요.")
            else:
                store.add_handover(u, "기타", note or raw, me)
                st.session_state.pop("draft", None)
                st.rerun()
        if b3.button("버리기", use_container_width=True):
            st.session_state.pop("draft", None)
            st.rerun()


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
            todo = [store.ITEM_LABEL[k] for k in store.ITEM_KEYS
                    if u["이름"] not in done.get(k, set())]
            c1.caption("오늘 남은 것: " + (", ".join(todo) if todo else "없음"))
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
 "📄 일지": page_log, "🧑‍🦳 이용자": page_users, "📌 공지": page_notice,
 "⚙️ 직원·설정": page_staff}[st.session_state["menu"]]()
