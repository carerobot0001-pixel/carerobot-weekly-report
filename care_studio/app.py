"""요양시설 스튜디오 — 주간보호센터·소형 요양원용 돌봄 업무 앱 (1단계).

Dolbom Studio(우리 팀 업무 공간)를 **돌봄 현장 쪽으로** 옮긴 것.
1단계는 논문(도우누리 주간보호센터 워크숍)에서 확인된 AS-IS 문제 3
— "기록이 일과 끝에 몰린다" — 하나만 정면으로 푼다.

  현장에서 말한다 → 초안이 채워진다 → 사람이 확인하고 저장한다 → 일지가 나온다

**안 하는 것(1단계)**: 상시 녹음, 자동 확정 저장, 의료 판단, 공단 청구.
저장은 항상 사람이 승인한 뒤에만 일어난다.
"""
import streamlit as st

import store
import voice

st.set_page_config(page_title="요양시설 스튜디오", page_icon="🏥",
                   layout="wide")

ORANGE = "#C4622D"
st.markdown(f"""<style>
  h1,h2,h3 {{ color:#8A3F12; }}
  [data-testid="stMetricValue"] {{ font-size:1.4rem; }}
  .cs-card {{ border:1px solid #E4DCD2; border-radius:10px; padding:.7rem .9rem;
             margin-bottom:.5rem; background:#fff; }}
  .cs-warn {{ color:{ORANGE}; font-weight:700; }}
</style>""", unsafe_allow_html=True)


def _me():
    return st.session_state.get("me", "")


# ── 사이드바 ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 요양시설 스튜디오")
    st.caption("주간보호센터 · 소형 요양원")
    st.session_state["me"] = st.text_input("기록자(내 이름)", value=_me(),
                                           placeholder="예: 박OO")
    menu = st.radio("메뉴", ["오늘", "이용자", "일지"], label_visibility="collapsed")
    st.divider()
    st.caption("⚠️ 시연·시험 단계입니다. 이용자는 **가명이나 코드**로 등록하세요. "
               "음성인식은 브라우저(구글) 서버를 거칩니다.")

users = store.users()
names = [u["이름"] for u in users]


# ── 오늘 ──────────────────────────────────────────────────────────────
def page_today():
    st.header("오늘")
    st.caption(f"{store.today()} · 이용자 {len(users)}명")
    if not users:
        st.info("먼저 **이용자** 메뉴에서 이용자를 등록하세요.")
        return

    done = store.done_map()
    cols = st.columns(4)
    for i, (key, label, hhmm) in enumerate(store.CARE_ITEMS):
        n = len(done.get(key, set()))
        with cols[i % 4]:
            st.metric(f"{hhmm} {label}", f"{n} / {len(users)}")

    st.divider()
    st.subheader("🎤 말해서 기록")
    st.caption("예: \"김OO 님 배설 완료, 시간이 좀 걸렸어요\" — "
               "말하면 아래에 초안이 뜨고, **확인 후 저장**합니다.")

    heard = voice.listen_box("today")
    if heard:
        st.session_state["draft_text"] = heard

    typed = st.text_input("말이 안 되는 상황이면 여기에 적어도 됩니다",
                          key="typed_in",
                          placeholder="김OO 님 점심 다 드셨어요")
    if st.button("초안 만들기", key="mk_draft") and typed.strip():
        st.session_state["draft_text"] = typed.strip()

    raw = st.session_state.get("draft_text", "")
    if raw:
        _draft_form(raw)

    st.divider()
    _today_records()


def _draft_form(raw):
    """말한 문장에서 뽑은 초안을 보여주고, 고쳐서 저장하게 한다."""
    d = store.parse(raw, names)
    st.markdown(f"<div class='cs-card'>들린 말 — <b>{raw}</b></div>",
                unsafe_allow_html=True)
    if not d["이용자"]:
        st.warning("이용자를 알아내지 못했습니다. 아래에서 골라 주세요.")
    if not d["항목"]:
        st.warning("항목을 알아내지 못했습니다. 아래에서 골라 주세요.")

    c1, c2, c3 = st.columns([2, 2, 1])
    u = c1.selectbox("이용자", names,
                     index=names.index(d["이용자"]) if d["이용자"] in names else 0,
                     key="d_user")
    it = c2.selectbox(
        "항목", store.ITEM_KEYS,
        index=store.ITEM_KEYS.index(d["항목"]) if d["항목"] in store.ITEM_KEYS else 0,
        format_func=lambda k: store.ITEM_LABEL[k], key="d_item")
    stt = c3.selectbox("상태", ["완료", "일부", "거부"],
                       index=["완료", "일부", "거부"].index(d["상태"])
                       if d["상태"] in ("완료", "일부", "거부") else 0,
                       key="d_stat")
    note = st.text_input("특이사항", value=d["특이사항"], key="d_note")

    b1, b2 = st.columns(2)
    if b1.button("✅ 확인하고 저장", type="primary", use_container_width=True):
        if not _me():
            st.warning("왼쪽에 기록자 이름을 먼저 넣어 주세요.")
        else:
            store.add_record(u, it, stt, note, _me(),
                             "음성" if st.session_state.get("_cs_last") else "화면")
            st.session_state.pop("draft_text", None)
            st.success(f"저장 — {u} · {store.ITEM_LABEL[it]} · {stt}")
            st.rerun()
    if b2.button("버리기", use_container_width=True):
        st.session_state.pop("draft_text", None)
        st.rerun()


def _today_records():
    rs = sorted(store.records(), key=lambda r: r["시각"], reverse=True)
    st.subheader(f"오늘 기록 — {len(rs)}건")
    if not rs:
        st.caption("아직 기록이 없습니다.")
        return
    for r in rs:
        c1, c2 = st.columns([9, 1])
        line = (f"**{r['시각']}**  {r['이용자']} · "
                f"{store.ITEM_LABEL.get(r['항목'], r['항목'])} · {r['상태']}")
        if r["특이사항"]:
            line += f" — {r['특이사항']}"
        line += (f"  <span style='opacity:.5;font-size:.78rem'>"
                 f"{r['기록자']} · {r['입력']}</span>")
        c1.markdown(line, unsafe_allow_html=True)
        if c2.button("✕", key=f"del_{r['시각']}_{r['이용자']}_{r['항목']}",
                     help="삭제"):
            store.delete_record(r["날짜"], r["시각"], r["이용자"], r["항목"])
            st.rerun()


# ── 이용자 ────────────────────────────────────────────────────────────
def page_users():
    st.header("이용자")
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
                st.success(f"등록 — {nm}")
                st.rerun()
            except ValueError as e:
                st.warning(str(e))

    if not users:
        st.caption("등록된 이용자가 없습니다.")
        return
    done = store.done_map()
    for u in users:
        with st.container(border=True):
            c1, c2 = st.columns([8, 1])
            head = f"### {u['이름']}"
            if u.get("자리"):
                head += f"  <span style='opacity:.6;font-size:.9rem'>{u['자리']}</span>"
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


# ── 일지 ──────────────────────────────────────────────────────────────
def page_log():
    st.header("일지")
    st.caption("오늘 기록을 이용자별로 모아 보여줍니다. "
               "일과가 끝난 뒤 처음부터 쓰지 않아도 됩니다.")
    if not users:
        st.info("이용자를 먼저 등록하세요.")
        return
    day = st.text_input("날짜", value=store.today(), key="log_day")
    whole = []
    for u in users:
        body = store.daily_log(u["이름"], day)
        with st.container(border=True):
            st.markdown(f"**{u['이름']}**")
            if body:
                st.text(body)
                whole.append(f"[{u['이름']}]\n{body}")
            else:
                st.caption("기록 없음")
    if whole:
        st.download_button("📥 전체 일지 내려받기 (txt)",
                           data=("\n\n".join(whole)).encode("utf-8"),
                           file_name=f"일지_{day}.txt", mime="text/plain")
    st.caption("※ 급여제공기록지 서식(복지부 고시) 요건은 아직 확인하지 못했습니다. "
               "확인 후 이 화면을 그 서식에 맞춥니다.")


{"오늘": page_today, "이용자": page_users, "일지": page_log}[menu]()
