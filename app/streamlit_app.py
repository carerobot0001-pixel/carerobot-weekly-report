"""돌봄로봇 주간 업무보고 취합 웹앱."""
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta, time
import pandas as pd
from pathlib import Path

from team_config import (
    TEAM_MEMBERS, MEMBER_NAMES, USER_NAMES, FIELD_LABELS, NOTICE_AUTHORS,
    get_member, get_fields_for,
    APP_PASSWORD,
)
from sheets_store import (
    load_week, save_submission, submission_status, weeks_with_counts,
    build_full_backup_xlsx, FIELD_KEYS, KST,
)
from space_store import (
    FAQ_HEADER, SPACE_LOG_HEADER, SheetNotConfigured, RowMismatch, sheet_url,
    faq_rows, add_faq, space_log_rows, add_space_log, resolve_space_log,
)
from purchase_store import (
    PURCHASE_HEADER, STATUS_DONE, RequestNotFound,
    purchase_rows, add_purchase, build_purchase_xlsx, resolve_purchase,
    delete_purchase_request, clear_all_purchases, build_purchase_list_xlsx,
)
from collab_store import (
    COLLAB_HEADER, collab_rows, add_collab, mark_done, set_status, delete_collab,
    drive_enabled, create_drive_doc,
)
from equip_store import (
    EQUIP_HEADER, equip_rows, save_all_equipment, build_equip_xlsx,
)
from visit_store import (
    VISIT_HEADER, visit_rows, add_visit, delete_visit,
    RowMismatch as VisitRowMismatch,
)
from calendar_store import (
    calendar_enabled, embed_url, upcoming_events, today_events,
    add_event, update_event, delete_event, event_view,
)
from news_store import fetch_news, fetch_section, NEWS_SECTIONS
from notice_store import (notices, add_notice, delete_notice,
                          is_expired, sweep_expired)
from common_store import (
    KEYS as COMMON_KEYS, EXTRA_KEY, EXTRA_DONE_KEY, EXTRA_PLAN_KEY, YONG_MAX, ASSET_MAX,
    HWPX_YONG_MAX, HWPX_ASSET_MAX,
    load_common, save_common, build_common_hwpx, build_common_xlsx,
)
from hwpx_exporter import build_report

st.set_page_config(page_title="돌봄로봇 주간 업무보고", page_icon="📋", layout="wide")


def this_wednesday() -> str:
    today = datetime.now().date()
    days_until_wed = (2 - today.weekday()) % 7
    wednesday = today + timedelta(days=days_until_wed)
    return wednesday.strftime("%Y-%m-%d")


def wednesday_of_week(week_str: str) -> datetime:
    return datetime.strptime(week_str, "%Y-%m-%d")


def auth_gate():
    # URL 쿼리 파라미터로 로그인 유지 (새로고침 대응). 담당자/팀원 구분 없이 단일 비밀번호.
    qp = st.query_params
    if not st.session_state.get("authed") and qp.get("auth") == "team":
        st.session_state["authed"] = True

    if st.session_state.get("authed"):
        return True

    st.title("📋 돌봄로봇 주간 업무보고")
    pw = st.text_input("비밀번호", type="password", key="pw_input")
    if st.button("입장"):
        if pw == APP_PASSWORD:
            st.session_state["authed"] = True
            st.query_params["auth"] = "team"
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


def _goto(page):
    """홈의 바로가기 버튼용 — 사이드바 메뉴를 page로 바꾸고 재실행."""
    st.session_state["_nav_to"] = page
    st.rerun()


def _me_index(options, default=0):
    """전역 정체성 me(홈에서 1회 설정)의 options 내 위치. 이름 selectbox 기본값용.
    me가 없거나 목록에 없으면 default(기본 0=첫 항목, 기존 동작 유지)."""
    me = st.session_state.get("me")
    return options.index(me) if me in options else default


def home_page():
    """홈 대시보드 — 상단(나는 누구·공지·오늘 챙길 것·내 할 일) → 일정 달력 → 바로가기(작게) → 뉴스."""
    today = datetime.now(KST).date()
    now = datetime.now(KST)
    week = this_wednesday()
    st.caption(f"📊 팀 현황 · {today.strftime('%Y-%m-%d')} 기준")

    # 홈 전용 컴팩트 스타일(폰트·여백 축소). 다른 페이지엔 주입 안 됨(홈 렌더 시에만).
    st.markdown("""<style>
      [data-testid="stMetricValue"]{font-size:1.45rem;}
      [data-testid="stMetricLabel"] p{font-size:0.7rem;}
      div[data-testid="stVerticalBlock"]{gap:0.5rem;}
      div[data-testid="stHorizontalBlock"]{gap:0.55rem;}
      div[data-testid="stAlert"]{padding:0.4rem 0.65rem;}
      div[data-testid="stAlert"] p{font-size:0.85rem;margin:0;}
      div[data-testid="stAlert"] a{font-size:0.85rem;}
      hr{margin:0.45rem 0;}
      div.stButton>button{padding:0.25rem 0.5rem;}
      /* ⚡ 바로가기 타일(아이콘+라벨 한 버튼) — 작게, 한 줄. qbar 컨테이너 안 버튼만 */
      div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .qbar-mark)
        div.stButton>button{
        white-space:pre-line; min-height:40px; line-height:1.25; font-size:0.62rem;
        color:#555; border:1px solid #e9ecf1; border-radius:9px; background:#fff;
        padding:3px 1px; box-shadow:none;
      }
      div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .qbar-mark)
        div.stButton>button p{ white-space:pre-line; line-height:1.25; margin:0; }
      div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .qbar-mark)
        div.stButton>button::first-line,
      div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .qbar-mark)
        div.stButton>button p::first-line{ font-size:1.05rem; }
      div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .qbar-mark)
        div.stButton>button:hover{ border-color:#4C8BF5; background:#F5F9FF; }
    </style>""", unsafe_allow_html=True)

    today_str = today.strftime("%Y-%m-%d")

    def _pdate(d):
        try:
            return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except Exception:
            return None

    # ── 데이터 로드(컬럼 배치 전에 미리) ─────────────────────────────
    try:
        active_collab = [r for r in collab_rows()
                         if r[3].strip() and r[9].strip() != "완료"]
    except Exception:
        active_collab = []
    # 만료된 공지 자동정리(세션당 1회 — 만료일 기준이라 외부상태 의존 없이 안전)
    if not st.session_state.get("_notice_swept"):
        st.session_state["_notice_swept"] = True
        try:
            sweep_expired(today_str)
        except Exception:
            pass
    try:
        ntc = notices()
    except Exception:
        ntc = []
    status = submission_status(week)
    missing = [s["name"] for s in status if not s["submitted"]]

    # 공통확인은 '업무보고 작성·취합' 탭, 회의록은 사이드바 메뉴로 접근 → 바로가기에선 제외
    shortcuts = [
        ("📝", "주간보고", "📝 업무보고 작성·취합"),
        ("🛒", "구매요청", "🛒 구매요청서"),
        ("📋", "문서협업", "📋 문서 협업"),
        ("📍", "방문일지", "📍 실증 방문 일지"),
        ("🏠", "스페이스", "🏠 스마트돌봄스페이스"),
        ("🔧", "장비현황", "🔧 장비 사용현황"),
    ]

    # ── 상단: 🙋나는 누구(좌) + ⚡바로가기 작은 타일(우, 한 줄) ──
    # me는 main()에서 ?me=로 시드. 여기서 고르면 세션+URL 유지되고 전 페이지가 사용.
    # 두 컬럼 모두 '굵은 라벨 + 컨트롤' 동일 구조로 맞춰 높이·정렬 통일.
    top_l, top_r = st.columns([1.2, 5])
    with top_l:
        st.markdown("**🙋 나는 누구?**")
        _midx = (USER_NAMES.index(st.session_state["me"])
                 if st.session_state.get("me") in USER_NAMES else None)
        _me_sel = st.selectbox("나는", USER_NAMES, index=_midx,
                               placeholder="이름 선택", label_visibility="collapsed",
                               key="me_widget")
    st.session_state["me"] = _me_sel
    if _me_sel and st.query_params.get("me") != _me_sel:
        st.query_params["me"] = _me_sel
    with top_r:
        st.markdown("**⚡ 바로가기**")
        with st.container():
            st.markdown('<div class="qbar-mark"></div>', unsafe_allow_html=True)
            qcols = st.columns(len(shortcuts))
            for j, (col, (emoji, label, target)) in enumerate(
                    zip(qcols, shortcuts)):
                if col.button(f"{emoji}  \n{label}", key=f"qs_{j}_{target}",
                              use_container_width=True):
                    _goto(target)

    # 📌 공지사항 (나는 누구 바로 밑) — 표시 + 등록/관리 토글
    for _idx, r in sorted(ntc, key=lambda x: x[0], reverse=True):
        if is_expired(r, today_str):
            continue  # 만료일 지난 공지는 숨김(정리 전이어도)
        exp_md = f"　·　🗓️ ~{r[3]}까지" if r[3].strip() else ""
        st.info(f"📌 **{r[2]}**　—　{r[1]} · {r[0]}{exp_md}")
    # 문서협업 자동 공지 — 진행중 협업을 공지처럼(제출현황 체크), 완료·삭제 시 자동 소멸
    for r in active_collab:
        doners = [x.strip() for x in r[8].split(",") if x.strip()]
        assignees = [x.strip() for x in r[7].split(",")
                     if x.strip() and x.strip() != "전체"]
        if assignees:
            remain = [a for a in assignees if a not in doners]
            prog = f"{len(doners)}/{len(assignees)}명 제출"
            prog += (f" · 남은 사람: {', '.join(remain)}" if remain
                     else " · ✅ 전원 제출")
        else:
            prog = (f"제출 {len(doners)}명: {', '.join(doners)}"
                    if doners else "아직 제출자 없음")
        link = r[5].strip()
        linkmd = f"　·　[📄 문서 열기]({link})" if link else ""
        dl_md = f" · 마감 {r[6]}" if r[6].strip() else ""
        st.info(f"📋 **[문서협업] {r[3]}**{dl_md}　—　{prog}{linkmd}")

    # 📌 공지 등록/관리 (누구나, 기본 접힘) — 공지 바로 아래
    n_open = st.session_state.get("home_notice_open", False)
    if st.button("➖ 공지 관리 닫기" if n_open else "📌 공지 등록/관리",
                 key="home_notice_open_btn", use_container_width=True):
        st.session_state["home_notice_open"] = not n_open
        st.rerun()
    if st.session_state.get("home_notice_open"):
        with st.container(border=True):
            _notice_manage()

    # 🔔 오늘 챙길 것
    st.markdown("**🔔 오늘 챙길 것**")
    any_reminder = False
    if missing:
        wed_dt = datetime.strptime(week, "%Y-%m-%d").replace(tzinfo=KST)
        deadline = (wed_dt - timedelta(days=1)).replace(hour=17, minute=0)
        delta = deadline - now
        overdue = delta.total_seconds() < 0
        # 마감 임박(2일 이내)이거나 지난 경우만 '오늘 챙길 것'에 노출(그 전엔 '내 할 일'에만)
        if overdue or delta.days <= 2:
            if overdue:
                dtxt = "🔴 마감 지남 (화 17시)"
            elif delta.days == 0:
                dtxt = (f"⏰ 오늘 마감! (화 17시·"
                        f"{int(delta.total_seconds() // 3600)}시간 남음)")
            else:
                dtxt = f"⏳ 마감 D-{delta.days} (화 17시)"
            st.warning(f"📝 주간보고 {dtxt} · 미제출 {len(missing)}명 — "
                       f"{', '.join(missing)}")
            any_reminder = True
    for r in active_collab:
        dl = _pdate(r[6])
        if dl is None:
            continue
        if dl < today or (dl - today).days <= 3:
            tag = "🔴 마감 지남" if dl < today else f"🟡 D-{(dl - today).days}"
            st.warning(f"📋 문서협업 '{r[3]}' {tag} (마감 {r[6]})")
            any_reminder = True
    if not any_reminder:
        st.success("✅ 급히 챙길 건 없습니다.")

    # 🙋 내 할 일 (+ 7일 일정)
    my = st.session_state.get("me")
    st.markdown(f"**🙋 내 할 일**{f' — {my}' if my else ''}")
    if not my:
        st.caption("👆 위 '나는 누구?'에서 이름을 먼저 선택하세요.")
    else:
        todos = []
        if not next((s["submitted"] for s in status if s["name"] == my), False):
            todos.append("📝 이번주 주간보고 미제출 (화 17시 마감)")
        for r in active_collab:
            assignees = [x.strip() for x in r[7].split(",")
                         if x.strip() and x.strip() != "전체"]
            doners = [x.strip() for x in r[8].split(",")]
            if my in assignees and my not in doners:
                todos.append(f"📋 문서협업 '{r[3]}' — 내 부분 미완료")
        sched_items = []
        common_sched_items = []
        if calendar_enabled():
            try:
                for e in upcoming_events(days=7, maxn=20):
                    v = event_view(e)
                    d = _pdate(v["date"])
                    if d is None or not (today <= d <= today + timedelta(days=6)):
                        continue
                    haystack = " ".join([
                        str(e.get("summary", "") or ""),
                        str(e.get("description", "") or ""),
                        str(v.get("title", "") or ""),
                        str(v.get("desc", "") or ""),
                    ])
                    item_text = f"📅 {v['date']} {v['when']} - {v['title']}"
                    if my in haystack:
                        sched_items.append(item_text)
                        continue
                    if not any(name in haystack for name in USER_NAMES):
                        common_sched_items.append(item_text)
            except Exception:
                sched_items = []
                common_sched_items = []

        if sched_items:
            st.markdown("**7일 내 내 일정**")
            for item in sched_items:
                st.info(item)
        else:
            st.caption("7일 내 내 일정이 없습니다.")

        if common_sched_items:
            st.markdown("**7일 내 공통 일정**")
            for item in common_sched_items:
                st.info(item)

        if todos:
            for t in todos:
                st.warning(t)
        elif not sched_items and not common_sched_items:
            st.success(f"✅ {my} 님, 할 일 없어요!")
        else:
            st.caption(f"{my} 님의 업무성 할 일은 없고, 아래에 관련 일정만 표시했습니다.")

    # ── 📅 사업단 일정 (제목 옆 ➕로 일정 추가·수정·삭제 토글) ─────────────
    st.divider()
    with st.container(border=True):
        if calendar_enabled():
            # 제목 바로 옆 작은 ➕ 버튼 → 누르면 일정 관리 패널(달력 위)이 열림.
            try:
                ct1, ct2, _sp = st.columns([2, 0.6, 12],
                                           vertical_alignment="center")
            except TypeError:
                ct1, ct2, _sp = st.columns([2, 0.6, 12])
            ct1.markdown("**📅 사업단 일정**")
            cal_open = st.session_state.get("home_cal_open", False)
            if ct2.button("➖" if cal_open else "➕", key="home_cal_open_btn",
                          help="일정 추가·수정·삭제"):
                st.session_state["home_cal_open"] = not cal_open
                st.rerun()
            if st.session_state.get("home_cal_open"):
                _calendar_manage()
            # 달력은 구글 임베드(iframe). 주간/월간/일정 전환은 임베드 자체 버튼. 기본 월간.
            _iframe = getattr(st, "iframe", components.iframe)
            _iframe(embed_url("MONTH"), height=520)
        else:
            st.markdown("**📅 사업단 일정**")
            st.caption("⚙️ 캘린더 미설정 — Secrets에 [calendar] id 필요.")

    # ── 📰 관련 뉴스 (전체 폭) ────────────────────────────────
    st.markdown("**📰 관련 뉴스**")
    tabs = st.tabs([name for name, _ in NEWS_SECTIONS])
    for tab, (_name, queries) in zip(tabs, NEWS_SECTIONS):
        with tab:
            try:
                items = fetch_section(queries)
            except Exception:
                items = []
            if items:
                for it in items:
                    src = f" · {it['source']}" if it.get("source") else ""
                    st.markdown(f"- [{it['title']}]({it['link']}){src}")
            else:
                st.caption("불러오지 못했어요 (잠시 후 새로고침).")


def member_page():
    st.header("✍️ 업무보고 작성 · 취합")
    tab_write, tab_collect, tab_common = st.tabs(
        ["✍️ 내 보고 작성", "📊 제출현황 · 취합본 생성", "📑 사업단 공통확인사항"])
    with tab_write:
        _report_write()
    with tab_collect:
        _report_collect()
    with tab_common:
        common_page()


def _report_write():
    col1, col2 = st.columns([2, 2])
    with col1:
        name = st.selectbox("본인 이름", MEMBER_NAMES,
                            index=_me_index(MEMBER_NAMES), key="member_name")
    with col2:
        this_wed = datetime.strptime(this_wednesday(), "%Y-%m-%d").date()
        # 다음 주 1개 + 이번 주 + 지난 10주 (전부 수요일), 날짜 내림차순
        weds = [this_wed + timedelta(weeks=1)] + \
               [this_wed - timedelta(weeks=k) for k in range(11)]

        def _wlabel(d):
            diff = round((d.toordinal() - this_wed.toordinal()) / 7)
            tag = {0: "이번 주", 1: "다음 주", -1: "지난 주"}.get(
                diff, f"{-diff}주 전" if diff < 0 else f"{diff}주 후")
            return f"{d.strftime('%Y-%m-%d')} (수) · {tag}"

        picked = st.selectbox(
            "보고 주차 (매주 수요일 회의)",
            weds,
            index=weds.index(this_wed),
            format_func=_wlabel,
            help="보통 '이번 주'로 두면 됩니다. 놓친 주를 채우거나 미리 쓸 때만 바꾸세요.",
        )
        week = picked.strftime("%Y-%m-%d")

    member = get_member(name)
    fields = get_fields_for(member)

    current = load_week(week).get(name, {})

    # 지난주 제출 내용 조회 (이번주 초기값으로 사용)
    last_week = None
    last_week_data = {}
    try:
        this_wed = wednesday_of_week(week)
        last_week = (this_wed - timedelta(days=7)).strftime("%Y-%m-%d")
        last_week_data = load_week(last_week).get(name, {})
    except Exception:
        pass

    # prefill 우선순위: 이번주 기존 저장본 > 지난주 내용 > 빈값
    if current:
        existing = current
        st.info(f"📝 이번주({week}) 저장본을 불러왔습니다. (마지막 저장: {current.get('submitted_at','-')})")
    elif last_week_data:
        existing = last_week_data
        st.warning(f"🗂️ **지난주({last_week}) 내용을 그대로 불러왔습니다.** 내용을 확인하고 이번주에 맞게 수정해주세요.")
    else:
        existing = {}
        st.caption(f"ℹ️ 지난주({last_week or '-'}) 제출 기록도 없어 빈 칸으로 시작합니다.")

    values = {}
    with st.form("report_form", clear_on_submit=False):
        if "acquired_data" in fields:
            st.subheader("📊 획득 데이터")
            st.caption("입력한 내용은 최종 보고서에 **파란색**으로 출력됩니다.")
            values["acquired_data"] = st.text_area(
                FIELD_LABELS["acquired_data"],
                value=existing.get("acquired_data", ""),
                height=120,
                placeholder="예: Obi + 진동센서, 미니스위치 데이터(○○○ 가정실증)",
                label_visibility="collapsed",
            )

        if member["has_research"]:
            st.subheader("🔬 연구")
            rc1, rc2 = st.columns(2)
            with rc1:
                values["research_done"] = st.text_area(
                    FIELD_LABELS["research_done"],
                    value=existing.get("research_done", ""),
                    height=220, placeholder="한 줄에 한 항목씩 작성",
                )
            with rc2:
                values["research_plan"] = st.text_area(
                    FIELD_LABELS["research_plan"],
                    value=existing.get("research_plan", ""),
                    height=220, placeholder="한 줄에 한 항목씩 작성",
                )

        if "task_done" in fields:
            st.subheader("📝 업무")
            tc1, tc2 = st.columns(2)
            with tc1:
                values["task_done"] = st.text_area(
                    FIELD_LABELS["task_done"],
                    value=existing.get("task_done", ""),
                    height=220, placeholder="한 줄에 한 항목씩 작성",
                )
            with tc2:
                values["task_plan"] = st.text_area(
                    FIELD_LABELS["task_plan"],
                    value=existing.get("task_plan", ""),
                    height=220, placeholder="한 줄에 한 항목씩 작성",
                )

        extra_fields = [f for f in fields if f in (
            "smart_care_space_done", "smart_care_space_plan",
            "project_confirmation_1",
            "project_confirmation_2_done", "project_confirmation_2_plan",
            "research_meeting", "director_meeting", "mohw_weekly")]
        if extra_fields:
            st.subheader("📌 추가 작성 항목")
            for f in extra_fields:
                values[f] = st.text_area(
                    FIELD_LABELS[f],
                    value=existing.get(f, ""),
                    height=150,
                    key=f"extra_{f}",
                )

        submitted = st.form_submit_button("💾 저장 / 제출", use_container_width=True)

    if submitted:
        try:
            action = save_submission(name, week, values)
            st.success(f"저장 완료 ({'신규 제출' if action=='created' else '기존 내용 수정'})")
            # 개인 백업 텍스트 생성 → 다운로드 버튼 제공
            lines = [f"=== {name} / {week} ===\n"]
            for f in get_fields_for(member):
                v = values.get(f, "") or ""
                lines.append(f"\n[{FIELD_LABELS[f]}]\n{v}\n")
            backup_txt = "".join(lines).encode('utf-8')
            st.download_button(
                "📄 내 제출본 TXT 백업 다운로드 (권장: 매주 저장해두세요)",
                data=backup_txt,
                file_name=f"{name}_{week}.txt",
                mime="text/plain",
            )
        except Exception as e:
            st.error(f"저장 실패: {e}")


def history_page():
    """과거 주차 회의록(전체 팀원 업무보고) 읽기 전용 조회.

    류현경 요청(이슈 #1): "4.21 기준으로 4.15 / 4.8 / 4.1 ... 주간업무보고
    회의록 열람". 팀원·관리자 모두 접근 가능.
    """
    st.header("📚 과거 회의록 열람")
    st.caption("지난 주차들의 팀원 업무보고 내용을 조회합니다 (읽기 전용).")

    weeks = weeks_with_counts()
    if not weeks:
        st.info("📭 아직 저장된 회의록이 없습니다.")
        return

    WD = ["월", "화", "수", "목", "금", "토", "일"]

    def _week_label(item):
        wk, n = item
        try:
            wd = WD[datetime.strptime(wk, "%Y-%m-%d").weekday()]
        except ValueError:
            wd = "?"
        return f"{wk} ({wd}) — {n}명 제출"

    choice = st.selectbox(
        "조회할 주차 (매주 수요일 회의)",
        weeks,
        format_func=_week_label,
        help="회의록이 저장된 수요일만 최신순으로 표시됩니다.",
    )
    week = choice[0]

    data = load_week(week)
    if not data:
        st.info(f"📭 {week} 주차에 저장된 내용이 없습니다.")
        return

    done_names = [n for n in MEMBER_NAMES if n in data]
    missing_names = [n for n in MEMBER_NAMES if n not in data]
    st.success(
        f"✅ 제출자 {len(done_names)}/{len(MEMBER_NAMES)}명 — "
        + (", ".join(done_names) if done_names else "(없음)")
    )
    if missing_names:
        st.caption(f"⏳ 미제출: {', '.join(missing_names)}")

    st.divider()

    for name in MEMBER_NAMES:
        r = data.get(name)
        if not r:
            continue
        with st.expander(f"👤 {name}  _({r.get('submitted_at', '-')})_",
                         expanded=False):
            member = get_member(name)
            fields = get_fields_for(member)
            any_shown = False
            for f in fields:
                val = r.get(f, "")
                if not val:
                    continue  # 빈 필드는 숨김
                st.caption(FIELD_LABELS[f])
                st.text(val)
                any_shown = True
            if not any_shown:
                st.caption("_(빈 제출)_")


def _render_sheet_error(e: Exception, sheet_label: str, secrets_key: str):
    """외부 시트 접근 실패 시 원인별 안내 (설정 누락 / 공유 누락)."""
    if isinstance(e, SheetNotConfigured):
        st.warning(f"⚙️ **{sheet_label} 시트 ID가 아직 설정되지 않았습니다.**")
        st.markdown("Streamlit Cloud → 앱 → **Settings → Secrets** 에 아래 섹션을 추가해주세요. "
                    "(시트 ID는 구글시트 URL의 `/d/` 와 `/edit` 사이 문자열)")
        st.code(f'[smart_space]\n{secrets_key} = "구글시트_문서ID"', language="toml")
    else:
        sa_email = dict(st.secrets.get("gcp_service_account", {})).get(
            "client_email", "(서비스 계정 이메일)")
        st.error(f"🔒 **{sheet_label} 시트에 접근할 수 없습니다.** "
                 "시트 소유자가 아래 계정을 **편집자**로 공유해야 합니다.")
        st.markdown("구글시트 우상단 **공유** → 아래 이메일 추가 → 권한 **편집자** → 보내기")
        st.code(sa_email)
        with st.expander("오류 상세"):
            st.text(str(e))


def _flash(key: str):
    """직전 등록 성공 메시지를 rerun 후에 표시."""
    msg = st.session_state.pop(key, None)
    if msg:
        st.success(msg)


def faq_tab():
    st.caption("스페이스 **사용매뉴얼 FAQ** 항목을 수집합니다 — 직접 느낀 점, 방문자에게 "
               "전해 들은 질문 등을 자유롭게 등록해주세요. (백정은 연구원 취합)")
    _flash("faq_flash")

    try:
        rows = faq_rows()
    except Exception as e:
        _render_sheet_error(e, "FAQ", "faq_sheet_id")
        return

    SPACES = ["공통", "1차 스마트돌봄스페이스", "2차 스마트돌봄스페이스",
              "3차 스마트돌봄스페이스", "4차 스마트돌봄스페이스", "기타(직접 입력)"]
    DOMAINS = ["이승", "배설", "식사", "목욕", "욕창·자세변환",
               "모니터링", "IoT", "시설", "기타(직접 입력)"]

    c1, c2, c3 = st.columns(3)
    with c1:
        writer = st.selectbox("작성자", USER_NAMES,
                              index=_me_index(USER_NAMES), key="faq_writer")
    with c2:
        space = st.selectbox("공간 구분", SPACES, key="faq_space")
        if space == "기타(직접 입력)":
            space = st.text_input("공간 구분 직접 입력", key="faq_space_custom",
                                  placeholder="예: 3차/4차 스마트돌봄스페이스")
    with c3:
        domain = st.selectbox("돌봄분야", DOMAINS, key="faq_domain")
        if domain == "기타(직접 입력)":
            domain = st.text_input("돌봄분야 직접 입력", key="faq_domain_custom")

    c4, c5 = st.columns(2)
    with c4:
        device = st.text_input("기기/서비스", key="faq_device",
                               placeholder="예: LUNA, 샤워베드, IoT, emfit QS")
    with c5:
        qtype = st.selectbox("문의 유형", ["사용법", "오류", "기타"], key="faq_qtype")

    question = st.text_area("예상 질문(FAQ) — 필수", key="faq_question", height=90,
                            placeholder="예: 샤워베드 높이조절이 안돼요")
    answer = st.text_area("답변 — 아는 경우만 (비워두면 담당자가 채웁니다)",
                          key="faq_answer", height=90)
    note = st.text_input("비고", key="faq_note")

    if st.button("➕ FAQ 등록", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("질문을 입력해주세요.")
        else:
            try:
                no = add_faq(space=space, domain=domain, device=device,
                             question=question.strip(), answer=answer.strip(),
                             qtype=qtype, writer=writer, note=note.strip())
                st.session_state["faq_flash"] = f"✅ FAQ 등록 완료 (번호 {no}) — 감사합니다!"
                for k in ("faq_question", "faq_answer", "faq_note", "faq_device"):
                    st.session_state.pop(k, None)
                st.rerun()
            except Exception as e:
                st.error(f"등록 실패: {e}")

    st.divider()
    st.subheader(f"📋 수집된 FAQ — {len(rows)}건")
    if rows:
        df = pd.DataFrame(rows[::-1], columns=FAQ_HEADER)  # 최신이 위로
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("아직 등록된 항목이 없습니다.")
    url = sheet_url("faq_sheet_id")
    if url:
        st.markdown(f"🔗 [구글시트 원본에서 보기/수정]({url})")


def space_log_tab():
    st.caption("스페이스에서 발견한 **문제·조치사항**을 관리대장에 기록합니다. "
               "(한벼리 연구원 관리)")
    _flash("log_flash")
    warn = st.session_state.pop("log_flash_warn", None)
    if warn:
        st.warning(warn)

    try:
        indexed = space_log_rows()
    except Exception as e:
        _render_sheet_error(e, "스페이스 관리대장", "space_sheet_id")
        return
    rows = [r for _, r in indexed]

    c1, c2, c3 = st.columns(3)
    with c1:
        finder = st.selectbox("발견자", USER_NAMES, key="log_finder")
    with c2:
        locs = st.multiselect("위치 (복수 선택 가능)",
                              ["1차", "2차", "3차", "4차", "목욕", "공통"],
                              key="log_locs")
        loc_custom = st.text_input("위치 직접 입력 (선택지에 없을 때)",
                                   key="log_loc_custom")
        location = ", ".join(
            locs + ([loc_custom.strip()] if loc_custom.strip() else []))
    with c3:
        found_date = st.date_input("발견 일자", value=datetime.now(KST).date(),
                                   key="log_date")

    problem = st.text_area("문제 — 필수", key="log_problem", height=90,
                           placeholder="예: 로봇청소기 전선 씹힘")
    action = st.text_area("조치방안 (선택)", key="log_action", height=90,
                          placeholder="예: 전선 정리 및 로봇청소기 교체")
    c4, c5 = st.columns(2)
    with c4:
        status = st.selectbox("진행상황", ["시작 안함", "진행중", "처리완료"],
                              key="log_status")
    with c5:
        note = st.text_input("비고", key="log_note")

    if st.button("➕ 관리대장에 기록", type="primary", use_container_width=True):
        if not problem.strip():
            st.warning("문제 내용을 입력해주세요.")
        elif not location:
            st.warning("위치를 선택하거나 입력해주세요.")
        else:
            try:
                no = add_space_log(location=location, problem=problem.strip(),
                                   finder=finder, action=action.strip(),
                                   found_date=found_date.strftime("%Y-%m-%d"),
                                   status=status, note=note.strip())
                st.session_state["log_flash"] = f"✅ 관리대장 기록 완료 (번호 {no})"
                for k in ("log_problem", "log_action", "log_note"):
                    st.session_state.pop(k, None)
                st.rerun()
            except Exception as e:
                st.error(f"기록 실패: {e}")

    st.divider()
    open_items = [(i, r) for i, r in indexed
                  if r[2].strip() and r[6].strip() != "처리완료"]
    st.subheader(f"⏳ 미해결 문제 — {len(open_items)}건")
    if open_items:
        df_open = pd.DataFrame([r for _, r in open_items][::-1],
                               columns=SPACE_LOG_HEADER)
        st.dataframe(
            df_open[["번호", "위치", "문제", "발견자", "조치방안", "발견 일자", "진행상황"]],
            use_container_width=True, hide_index=True)

        st.markdown("**✅ 완료 처리** — 해결된 문제를 선택하면 시트에 바로 반영됩니다.")
        labels = {}
        for i, r in open_items:
            labels[f"{r[2][:45]} — {r[1] or '위치?'} · 발견 {r[3] or '-'} · 시트 {i}행"] = (i, r)
        sel = st.selectbox("완료 처리할 문제 선택", list(labels.keys()),
                           index=None, placeholder="문제를 선택하세요...",
                           key="resolve_sel")
        if sel:
            ri, rr = labels[sel]
            rc1, rc2 = st.columns(2)
            with rc1:
                fixer = st.selectbox("조치자 (본인 이름)", USER_NAMES,
                                     key="resolve_fixer")
            with rc2:
                fixed_date = st.date_input("조치일자",
                                           value=datetime.now(KST).date(),
                                           key="resolve_date")
            action_txt = st.text_input(
                "조치 내용 (선택 — 입력하면 '조치방안' 칸에 기록, 비우면 기존 내용 유지)",
                key="resolve_action",
                placeholder=f"기존 조치방안: {rr[4][:50] or '(비어있음)'}")
            if st.button("✅ 처리완료로 변경", type="primary",
                         use_container_width=True):
                try:
                    resolve_space_log(ri, rr[2], fixer,
                                      fixed_date.strftime("%Y-%m-%d"),
                                      action_txt.strip())
                    st.session_state["log_flash"] = (
                        f"✅ 처리완료로 변경됨 — \"{rr[2][:30]}\" (조치자: {fixer})")
                    for k in ("resolve_sel", "resolve_action"):
                        st.session_state.pop(k, None)
                    st.rerun()
                except RowMismatch:
                    space_log_rows.clear()
                    st.session_state["log_flash_warn"] = (
                        "그 사이 시트가 수정되어 행 위치가 바뀌었습니다. "
                        "목록을 새로 불러왔으니 다시 선택해주세요.")
                    st.session_state.pop("resolve_sel", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"완료 처리 실패: {e}")
    else:
        st.caption("미해결 문제가 없습니다 🎉")
    with st.expander(f"📚 전체 기록 보기 ({len(rows)}건)"):
        if rows:
            st.dataframe(pd.DataFrame(rows[::-1], columns=SPACE_LOG_HEADER),
                         use_container_width=True, hide_index=True)
    url = sheet_url("space_sheet_id")
    if url:
        st.markdown(f"🔗 [구글시트 원본에서 보기/수정]({url}) — "
                    "내용 수정·삭제는 시트에서 직접")


def space_page():
    """스마트돌봄스페이스: FAQ 수집(백정은) + 관리대장 문제 접수(한벼리)."""
    st.header("🏠 스마트돌봄스페이스")
    tab_faq, tab_log = st.tabs(["📖 사용매뉴얼 FAQ 수집", "🔧 관리대장 (문제 접수)"])
    with tab_faq:
        faq_tab()
    with tab_log:
        space_log_tab()


def purchase_page():
    """구매요청서 작성 — 품목 표 입력 → 구글시트 누적 + 엑셀 양식 다운로드."""
    st.header("🛒 구매요청서 작성")
    st.caption("장비·재료 구매요청 품목을 입력하면 구글시트에 누적되고, 첨부 양식과 같은 "
               "엑셀 파일로도 내려받을 수 있습니다.")
    _flash("purchase_flash")

    c1, c2 = st.columns([1, 2])
    with c1:
        requester = st.selectbox("요청자", USER_NAMES,
                                 index=_me_index(USER_NAMES), key="pur_requester")
    with c2:
        reason = st.text_input("구매사유", value="돌봄로봇 실증연구", key="pur_reason")

    st.markdown("**품목 입력** — 표에 한 줄씩 추가하세요. 단가·수량을 넣으면 합계가 자동 계산됩니다. "
                "(맨 아래 빈 줄에 입력하면 행이 늘어나고, 행 왼쪽 체크 후 휴지통으로 삭제)")
    blank = pd.DataFrame(
        [{"품명": "", "품목(상세)": "", "단가": 0, "수량": 1, "비고(구매처)": ""}
         for _ in range(3)])
    edited = st.data_editor(
        blank, num_rows="dynamic", use_container_width=True, key="pur_editor",
        column_config={
            "품명": st.column_config.TextColumn("품명", width="medium"),
            "품목(상세)": st.column_config.TextColumn("품목(상세)", width="large"),
            "단가": st.column_config.NumberColumn("단가(원)", min_value=0, step=100,
                                                format="%d"),
            "수량": st.column_config.NumberColumn("수량", min_value=0, step=1,
                                               format="%d"),
            "비고(구매처)": st.column_config.TextColumn("비고(구매처/링크)", width="medium"),
        },
    )

    v = edited[edited["품명"].astype(str).str.strip() != ""].copy()
    v["단가"] = pd.to_numeric(v["단가"], errors="coerce").fillna(0).astype(int)
    v["수량"] = pd.to_numeric(v["수량"], errors="coerce").fillna(0).astype(int)
    v["합계"] = v["단가"] * v["수량"]
    total = int(v["합계"].sum())

    if not v.empty:
        preview = v[["품명", "단가", "수량", "합계"]].copy()
        for col in ("단가", "합계"):
            preview[col] = preview[col].map("{:,}".format)
        st.dataframe(preview, hide_index=True, use_container_width=True)
    st.metric("총액", f"{total:,} 원")
    st.caption("⚠️ 합계·총액은 표 입력 후 자동 계산됩니다.")

    items = [{"품명": r["품명"], "품목": r["품목(상세)"], "단가": int(r["단가"]),
              "수량": int(r["수량"]), "비고": r["비고(구매처)"]}
             for _, r in v.iterrows()]

    b1, b2 = st.columns(2)
    with b1:
        if st.button("💾 구글시트에 저장", type="primary", use_container_width=True):
            if not items:
                st.warning("품명이 있는 품목을 1개 이상 입력해주세요.")
            else:
                try:
                    req_id, n, tot = add_purchase(requester, reason, items)
                    st.session_state["purchase_flash"] = (
                        f"✅ 저장 완료 — {n}개 품목, 총 {tot:,}원 (요청ID {req_id})")
                    st.session_state.pop("pur_editor", None)  # 표 초기화
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")
    with b2:
        if items:
            st.download_button(
                "📄 엑셀 양식 다운로드",
                data=build_purchase_xlsx(requester, reason, items),
                file_name=f"구매요청서_{requester}_"
                          f"{datetime.now(KST).strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet",
                use_container_width=True)
        else:
            st.button("📄 엑셀 양식 다운로드", disabled=True,
                      use_container_width=True,
                      help="품목을 입력하면 활성화됩니다.")

    st.divider()
    rows = purchase_rows()
    by_req = {}
    for r in rows:
        by_req.setdefault(r[0], []).append(r)

    def _req_status(grp):
        s = grp[0][10] if len(grp[0]) > 10 else ""
        return s.strip() or "요청"

    def _req_total(grp):
        return sum(int(x[7] or 0) for x in grp)

    def _show_items(grp):
        df = pd.DataFrame(grp, columns=PURCHASE_HEADER)
        st.dataframe(df[["품명", "품목(상세)", "단가", "수량", "합계",
                         "구매사유", "비고(구매처)", "요청자"]],
                     hide_index=True, use_container_width=True)

    pending = {k: v for k, v in by_req.items() if _req_status(v) != STATUS_DONE}
    done = {k: v for k, v in by_req.items() if _req_status(v) == STATUS_DONE}

    # 누적 리스트 관리 — 엑셀 다운로드 / 선택·전체 삭제
    st.subheader("📋 누적 리스트 관리")
    with st.container(border=True):
        mc1, mc2 = st.columns(2)
        with mc1:
            if rows:
                st.download_button(
                    "📥 누적 리스트 엑셀 다운로드",
                    data=build_purchase_list_xlsx(rows),
                    file_name=f"구매요청_누적_"
                              f"{datetime.now(KST).strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument."
                         "spreadsheetml.sheet",
                    use_container_width=True)
            else:
                st.button("📥 누적 리스트 엑셀 다운로드", disabled=True,
                          use_container_width=True)
        with mc2:
            clr = st.checkbox("⚠️ 전체삭제 확인", key="pur_clear_ok")
            if st.button("🗑️ 누적 전체 삭제", disabled=not (clr and rows),
                         use_container_width=True):
                n = clear_all_purchases()
                st.session_state["purchase_flash"] = f"🗑️ 누적 전체 삭제됨 ({n}행)"
                st.session_state.pop("pur_clear_ok", None)
                st.rerun()

        if by_req:
            def _dlabel(rid):
                g = by_req[rid]
                return (f"{g[0][1]} · {g[0][2]} — {len(g)}품목 · "
                        f"{_req_total(g):,}원 [{_req_status(g)}]")

            dsel = st.selectbox("🗑️ 선택 삭제할 요청", sorted(by_req, reverse=True),
                                index=None, format_func=_dlabel,
                                placeholder="요청을 선택하세요...", key="pur_del_sel")
            if dsel and st.checkbox("삭제 확인", key="pur_del_ok"):
                if st.button("🗑️ 선택한 요청 삭제", type="primary"):
                    try:
                        cnt = delete_purchase_request(dsel)
                        st.session_state["purchase_flash"] = (
                            f"🗑️ 요청 삭제됨 ({cnt}개 품목)")
                        for k in ("pur_del_sel", "pur_del_ok"):
                            st.session_state.pop(k, None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")

    # 구매완료 처리 (누구나)
    if pending:
        st.subheader("✅ 구매완료 처리")

        def _plabel(rid):
            g = pending[rid]
            return f"{g[0][1]} · {g[0][2]} — {len(g)}개 품목 · {_req_total(g):,}원"

        sel = st.selectbox("완료 처리할 요청 선택", sorted(pending, reverse=True),
                           index=None, format_func=_plabel,
                           placeholder="요청을 선택하세요...", key="pur_resolve_sel")
        if sel:
            rc1, rc2 = st.columns(2)
            with rc1:
                processor = st.selectbox("처리자", USER_NAMES, key="pur_processor")
            with rc2:
                done_date = st.date_input("처리일자",
                                          value=datetime.now(KST).date(),
                                          key="pur_done_date")
            with st.expander("처리할 품목 미리보기", expanded=True):
                _show_items(pending[sel])
            if st.button("✅ 구매완료로 변경", type="primary",
                         use_container_width=True):
                try:
                    cnt = resolve_purchase(sel, processor,
                                           done_date.strftime("%Y-%m-%d"))
                    st.session_state["purchase_flash"] = (
                        f"✅ 구매완료 처리됨 — {_plabel(sel)} (품목 {cnt}개)")
                    st.session_state.pop("pur_resolve_sel", None)
                    st.rerun()
                except RequestNotFound:
                    purchase_rows.clear()
                    st.warning("그 사이 목록이 바뀌었습니다. 다시 선택해주세요.")
                    st.session_state.pop("pur_resolve_sel", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"처리 실패: {e}")
        st.divider()

    st.subheader(f"🟡 처리 대기 — {len(pending)}건")
    if not pending:
        st.caption("처리 대기 중인 요청이 없습니다.")
    for rid in sorted(pending, reverse=True)[:30]:
        grp = pending[rid]
        with st.expander(f"🧾 {grp[0][1]} · {grp[0][2]} — {len(grp)}개 품목 · "
                         f"{_req_total(grp):,}원"):
            _show_items(grp)

    with st.expander(f"✅ 구매완료 — {len(done)}건"):
        if not done:
            st.caption("아직 구매완료된 요청이 없습니다.")
        for rid in sorted(done, reverse=True)[:50]:
            grp = done[rid]
            st.markdown(f"**{grp[0][1]} · {grp[0][2]}** — {len(grp)}개 · "
                        f"{_req_total(grp):,}원  _(처리: {grp[0][12] or '-'} / "
                        f"{grp[0][11] or '-'})_")
            _show_items(grp)


def collab_page():
    """문서 협업 보드 — 구글 문서 링크 + 요청 + 제출현황 (파일은 구글에 보관)."""
    st.header("📋 문서 협업")
    st.caption("엑셀·워드·PPT를 여럿이 나눠 작성할 때 — 팀원이 각자 자기 부분을 "
               "구글 문서에서 실시간으로 채웁니다.")
    _flash("collab_flash")

    my_name = st.selectbox("👤 내 이름 (요청자·완료체크에 사용)", USER_NAMES,
                           index=_me_index(USER_NAMES), key="collab_my_name")

    # 등록 폼: 펼침창 대신 토글 버튼 + 컨테이너 (작성 중 새로고침돼도 안 닫히게)
    open_form = st.session_state.get("collab_show_form", False)
    if st.button("➖ 등록 폼 닫기" if open_form else "➕ 새 협업 요청 등록",
                 use_container_width=True):
        st.session_state["collab_show_form"] = not open_form
        st.rerun()

    if st.session_state.get("collab_show_form"):
        with st.container(border=True):
            title = st.text_input("제목", key="collab_title",
                                  placeholder="예: 6월 결과보고서 분담 작성")
            up = None
            if drive_enabled():
                st.markdown("**문서 준비** — 엑셀·워드 파일을 올리면 앱이 구글 문서로 "
                            "만들어 링크를 자동 생성합니다.")
                up = st.file_uploader(
                    "파일 올리기 (엑셀·워드)",
                    type=["xlsx", "xls", "csv", "docx", "doc"],
                    key="collab_upload")
                st.caption("📌 **PPT는 여기에 올리지 마세요** — 구글 변환 시 서식이 깨집니다. "
                           "OneDrive/파워포인트 온라인에서 '편집 링크'를 만들어 아래 칸에 "
                           "붙여넣으세요.")
                link = st.text_input("또는 링크 붙여넣기 (구글 문서 / OneDrive PPT 등)",
                                     key="collab_link",
                                     placeholder="https://…  구글 시트·문서 또는 OneDrive PPT 링크")
            else:
                link = st.text_input("문서 링크 (구글 시트/문서/슬라이드 URL)",
                                     key="collab_link",
                                     placeholder="https://docs.google.com/...")
                st.caption("구글 드라이브에 올린 파일을 '연결 앱 → Google 스프레드시트/"
                           "슬라이드/문서'로 열고 [공유]→'링크가 있는 모든 사용자(편집자)'"
                           "→ 링크 복사해 붙여넣으세요.")

            request_text = st.text_area("요청사항 (누가 어느 부분을 작성할지 등)",
                                        key="collab_request", height=100)
            rc1, rc2 = st.columns(2)
            with rc1:
                deadline = st.date_input("마감일", value=datetime.now(KST).date(),
                                         key="collab_deadline")
            with rc2:
                assignees = st.multiselect("담당자 (선택 — 비우면 전체)", USER_NAMES,
                                           key="collab_assignees")
            st.caption(f"요청자: **{my_name}** (위 '내 이름'에서 변경)")
            if st.button("➕ 협업 요청 등록", type="primary",
                         use_container_width=True):
                final_link = link.strip()
                if not title.strip():
                    st.warning("제목을 입력해주세요.")
                elif up is None and not final_link:
                    st.warning("파일을 올리거나 문서 링크를 입력해주세요.")
                else:
                    try:
                        if up is not None:
                            with st.spinner("구글 문서로 변환하는 중..."):
                                final_link = create_drive_doc(up.getvalue(), up.name)
                        add_collab(my_name, title.strip(), request_text.strip(),
                                   final_link, deadline.strftime("%Y-%m-%d"),
                                   assignees)
                        st.session_state["collab_flash"] = f"✅ 등록 완료 — {title.strip()}"
                        for k in ("collab_title", "collab_link", "collab_request",
                                  "collab_assignees", "collab_upload"):
                            st.session_state.pop(k, None)
                        st.session_state["collab_show_form"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

    st.divider()
    rows = collab_rows()
    active = [r for r in rows if r[3].strip() and r[9].strip() != "완료"]
    closed = [r for r in rows if r[9].strip() == "완료"]

    st.subheader(f"🟢 진행중 — {len(active)}건")
    if not active:
        st.caption("진행중인 협업 요청이 없습니다.")
    for r in sorted(active, key=lambda x: x[0], reverse=True):
        req_id, ts, who, title, req_text, link, dl, assignees, doners, status = r
        done_list = [n.strip() for n in doners.split(",") if n.strip()]
        assigned = [n.strip() for n in assignees.split(",")
                    if n.strip() and n.strip() != "전체"]
        # 담당자 + (담당자가 아니어도 완료한 사람)까지 모두 표시
        roster = assigned + [n for n in done_list if n not in assigned]
        cnt = f" · ✅ {len(done_list)}명 완료" if done_list else ""
        with st.container(border=True):
            st.markdown(f"**📄 {title}** · {who}"
                        + (f" · 마감 {dl}" if dl.strip() else "") + cnt)
            if req_text.strip():
                st.caption(f"요청사항: {req_text}")
            if link.strip().startswith("http"):
                st.link_button("🔗 문서 열기 (작성하러 가기)", link,
                               use_container_width=True)
            elif link.strip():
                st.caption(f"링크: {link}")
            if roster:
                st.caption("제출현황 — " + "  ".join(
                    (f"✅{n}" if n in done_list else f"⏳{n}") for n in roster))
            else:
                st.caption("아직 완료 표시한 사람이 없습니다.")
            bc1, bc2 = st.columns(2)
            if bc1.button(f"✅ 내 부분 완료 ({my_name})",
                          key=f"collab_done_{req_id}", use_container_width=True):
                try:
                    mark_done(req_id, my_name)
                    st.session_state["collab_flash"] = f"✅ '{title}' — {my_name} 완료 표시"
                    st.rerun()
                except Exception as e:
                    st.error(f"실패: {e}")
            if bc2.button("🏁 마감", key=f"collab_close_{req_id}",
                          use_container_width=True):
                try:
                    set_status(req_id, "완료")
                    st.session_state["collab_flash"] = f"🏁 '{title}' 마감"
                    st.rerun()
                except Exception as e:
                    st.error(f"실패: {e}")
            dc1, dc2 = st.columns([1, 2])
            dok = dc1.checkbox("삭제 확인", key=f"collab_delok_{req_id}")
            if dc2.button("🗑️ 이 요청 삭제", key=f"collab_del_{req_id}",
                          disabled=not dok, use_container_width=True):
                try:
                    delete_collab(req_id)
                    st.session_state["collab_flash"] = (
                        f"🗑️ '{title}' 삭제됨 (구글 문서 원본은 드라이브에 남음)")
                    st.rerun()
                except Exception as e:
                    st.error(f"삭제 실패: {e}")

    with st.expander(f"✅ 완료된 요청 — {len(closed)}건"):
        if not closed:
            st.caption("아직 완료된 요청이 없습니다.")
        for r in sorted(closed, key=lambda x: x[0], reverse=True)[:30]:
            req_id, ts, who, title, req_text, link, dl, assignees, doners, status = r
            d_done = [n.strip() for n in doners.split(",") if n.strip()]
            st.markdown(f"**{title}** · {who} · {ts}"
                        + (f"  ·  [🔗 문서]({link})" if link.strip().startswith("http")
                           else ""))
            if d_done:
                st.caption("완료: " + ", ".join(d_done))
            cok = st.checkbox("삭제 확인", key=f"collab_delokc_{req_id}")
            ccol1, ccol2 = st.columns(2)
            if ccol1.button("↩️ 다시 진행중", key=f"collab_reopen_{req_id}"):
                set_status(req_id, "진행중")
                st.rerun()
            if ccol2.button("🗑️ 삭제", key=f"collab_delc_{req_id}", disabled=not cok):
                delete_collab(req_id)
                st.session_state["collab_flash"] = f"🗑️ '{title}' 삭제됨"
                st.rerun()
            st.divider()


def equip_page():
    """장비(기기) 사용현황 — 연구별 필터 조회 + 전체 목록 편집(등록·수정·삭제)."""
    st.header("🔧 장비 사용현황")
    st.caption("실증 장비(기기) 사용 현황 대장 — 연구(실증)별로 필터해 보고, 전체 목록을 "
               "편집할 수 있습니다. ※ 피험자명 등 개인정보 포함 — 팀 내부용입니다.")
    _flash("equip_flash")

    rows = equip_rows()
    researches = sorted({r[3] for r in rows if r[3].strip()})

    fc1, fc2 = st.columns([3, 1])
    with fc1:
        sel = st.selectbox("연구(실증) 필터", ["전체"] + researches, key="equip_filter")
    shown = rows if sel == "전체" else [r for r in rows if r[3] == sel]
    with fc2:
        st.metric("장비 수", f"{len(shown)} / {len(rows)}")

    if shown:
        st.dataframe(pd.DataFrame(shown, columns=EQUIP_HEADER),
                     use_container_width=True, hide_index=True)
        st.download_button(
            "📥 엑셀 다운로드 (현재 보기)",
            data=build_equip_xlsx(shown, sel),
            file_name=f"장비현황_{sel}_{datetime.now(KST).strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.caption("표시할 장비가 없습니다.")

    st.divider()
    ed = st.session_state.get("equip_edit", False)
    if st.button("✏️ 전체 목록 편집 닫기" if ed else "✏️ 등록·수정·삭제 (전체 목록 편집)",
                 use_container_width=True):
        st.session_state["equip_edit"] = not ed
        st.rerun()

    if st.session_state.get("equip_edit"):
        with st.container(border=True):
            st.markdown("표에서 **행 추가(맨 아래 빈 줄)·수정·삭제**(행 왼쪽 체크 후 휴지통) 후 "
                        "**저장**하세요. 연구·플랫폼명은 기존과 똑같이 적어야 필터가 깔끔합니다.")
            cur = (pd.DataFrame(rows, columns=EQUIP_HEADER) if rows
                   else pd.DataFrame([{h: "" for h in EQUIP_HEADER}]))
            edited = st.data_editor(cur, num_rows="dynamic", height=420,
                                    use_container_width=True, key="equip_editor")
            if st.button("💾 전체 저장", type="primary", use_container_width=True):
                new = edited.fillna("").astype(str)
                new = new[new["기기명"].str.strip() != ""]
                new_rows = new[EQUIP_HEADER].values.tolist()
                try:
                    n = save_all_equipment(new_rows)
                    st.session_state["equip_flash"] = f"💾 저장 완료 — 장비 {n}개"
                    st.session_state.pop("equip_editor", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")


def _cal_edit_form(v):
    eid = v["id"]
    st.markdown("**✏️ 일정 수정**")
    title = st.text_input("제목", value=v["title"], key=f"cal_et_title_{eid}")
    ec1, ec2 = st.columns([2, 1])
    try:
        dval = datetime.strptime(v["date"], "%Y-%m-%d").date()
    except Exception:
        dval = datetime.now(KST).date()
    edate = ec1.date_input("날짜", value=dval, key=f"cal_et_date_{eid}")
    eallday = ec2.checkbox("종일", value=v["all_day"], key=f"cal_et_allday_{eid}")

    def _pt(s, dflt):
        try:
            hh, mm = s.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return dflt

    if not eallday:
        tc1, tc2 = st.columns(2)
        est = tc1.time_input("시작", value=_pt(v["start_t"], time(9, 0)),
                             key=f"cal_et_st_{eid}")
        eet = tc2.time_input("종료", value=_pt(v["end_t"], time(10, 0)),
                             key=f"cal_et_et_{eid}")
    edesc = st.text_area("설명", value=v["desc"], key=f"cal_et_desc_{eid}", height=60)
    if st.button("💾 수정 저장", key=f"cal_et_save_{eid}", type="primary"):
        try:
            update_event(eid, title.strip(), edate.strftime("%Y-%m-%d"), eallday,
                         "09:00" if eallday else est.strftime("%H:%M"),
                         "10:00" if eallday else eet.strftime("%H:%M"), edesc.strip())
            st.session_state["cal_flash"] = f"✅ 수정됨 — {title.strip()}"
            st.session_state.pop(f"cal_edit_{eid}", None)
            st.rerun()
        except Exception as ex:
            st.error(f"수정 실패: {ex}")


def _calendar_manage():
    """일정 추가/수정/삭제 UI — 🏠 홈의 달력 아래에서 호출."""
    if not calendar_enabled():
        return
    _flash("cal_flash")

    open_f = st.session_state.get("cal_show_form", False)
    if st.button("➖ 등록 폼 닫기" if open_f else "➕ 일정 추가",
                 use_container_width=True):
        st.session_state["cal_show_form"] = not open_f
        st.rerun()
    if st.session_state.get("cal_show_form"):
        with st.container(border=True):
            title = st.text_input("제목", key="cal_add_title",
                                  placeholder="예: 사업단 정기회의")
            ac1, ac2 = st.columns([2, 1])
            adate = ac1.date_input("날짜", value=datetime.now(KST).date(),
                                   key="cal_add_date")
            allday = ac2.checkbox("종일", key="cal_add_allday")
            stime = etime = None
            if not allday:
                tc1, tc2 = st.columns(2)
                stime = tc1.time_input("시작", value=time(9, 0), key="cal_add_st")
                etime = tc2.time_input("종료", value=time(10, 0), key="cal_add_et")
            desc = st.text_area("설명 (선택)", key="cal_add_desc", height=70)
            if st.button("➕ 일정 등록", type="primary", use_container_width=True):
                if not title.strip():
                    st.warning("제목을 입력하세요.")
                else:
                    try:
                        add_event(title.strip(), adate.strftime("%Y-%m-%d"), allday,
                                  "09:00" if allday else stime.strftime("%H:%M"),
                                  "10:00" if allday else etime.strftime("%H:%M"),
                                  desc.strip())
                        st.session_state["cal_flash"] = f"✅ 일정 등록 — {title.strip()}"
                        for k in ("cal_add_title", "cal_add_desc"):
                            st.session_state.pop(k, None)
                        st.session_state["cal_show_form"] = False
                        st.rerun()
                    except Exception as ex:
                        st.error(f"등록 실패: {ex}")

    st.divider()
    st.subheader("✏️ 일정 수정 / 삭제")
    try:
        events = upcoming_events(days=60)
    except Exception as ex:
        st.error(f"일정을 불러오지 못했습니다: {ex}")
        return
    if not events:
        st.caption("다가오는 일정이 없습니다.")
        return
    labels = {}
    for e in events:
        v = event_view(e)
        labels[f"{v['date']} · {v['when']} · {v['title']}"] = v
    sel = st.selectbox("수정·삭제할 일정 선택", list(labels.keys()), index=None,
                       placeholder="일정을 선택하세요...", key="cal_manage_sel")
    if sel:
        v = labels[sel]
        with st.container(border=True):
            _cal_edit_form(v)
            st.markdown("---")
            delok = st.checkbox("삭제 확인", key=f"cal_delok_{v['id']}")
            if st.button("🗑️ 이 일정 삭제", key=f"cal_del_{v['id']}",
                         disabled=not delok, use_container_width=True):
                try:
                    delete_event(v["id"])
                    st.session_state["cal_flash"] = f"🗑️ 삭제 — {v['title']}"
                    st.session_state.pop("cal_manage_sel", None)
                    st.rerun()
                except Exception as ex:
                    st.error(f"삭제 실패: {ex}")


def common_page():
    """사업단 공통확인사항(최혜민) 입력 및 한글/엑셀 생성."""
    st.header("📑 사업단 공통확인사항")
    st.caption(
        "본부과제 용역·자산구매 실적/계획을 입력하면 한글(HWPX)과 엑셀 파일로 만들 수 있습니다."
    )
    _flash("common_flash")

    saved = load_common()

    def _editor(key, cols, label):
        st.caption(label)
        init = saved.get(key) or [[""] * len(cols)]
        init = [(list(row) + [""] * len(cols))[:len(cols)] for row in init]
        return st.data_editor(
            pd.DataFrame(init, columns=cols),
            num_rows="dynamic",
            use_container_width=True,
            key=f"ce_{key}",
        )

    st.markdown(f"#### 🔹 본부과제 용역 (최대 {YONG_MAX}행)")
    yc1, yc2 = st.columns(2)
    with yc1:
        y_done = _editor("용역_실적", ["분야", "발주금액", "비고"], "실적")
    with yc2:
        y_plan = _editor("용역_계획", ["분야", "발주금액", "비고"], "계획")

    st.markdown(f"#### 🔹 본부과제 자산구매 (최대 {ASSET_MAX}행)")
    ac1, ac2 = st.columns(2)
    with ac1:
        a_done = _editor("자산_실적", ["품명", "수량", "구매금액", "비고"], "실적")
    with ac2:
        a_plan = _editor("자산_계획", ["품명", "수량", "구매금액", "비고"], "계획")

    st.markdown("#### 🔹 기타내용")
    ec1, ec2 = st.columns(2)
    with ec1:
        extra_done_text = st.text_area(
            "실적 칸 기타내용",
            value=str(saved.get(EXTRA_DONE_KEY, saved.get(EXTRA_KEY, ""))),
            height=130,
            placeholder="실적 칸에 넣을 기타내용을 입력하세요.",
            key="ce_extra_done_text",
        )
    with ec2:
        extra_plan_text = st.text_area(
            "계획 칸 기타내용",
            value=str(saved.get(EXTRA_PLAN_KEY, saved.get(EXTRA_KEY, ""))),
            height=130,
            placeholder="계획 칸에 넣을 기타내용을 입력하세요.",
            key="ce_extra_plan_text",
        )
    st.caption("기타내용은 저장 및 엑셀 다운로드에 포함됩니다. 한글(HWPX)도 좌우 칸에 각각 반영됩니다.")

    def _rows(df, ncol):
        out = []
        for _, r in df.iterrows():
            vals = [str(r[c]).strip() for c in df.columns]
            if any(vals):
                out.append(vals[:ncol])
        return out

    tables = {
        "용역_실적": _rows(y_done, 3),
        "용역_계획": _rows(y_plan, 3),
        "자산_실적": _rows(a_done, 4),
        "자산_계획": _rows(a_plan, 4),
        EXTRA_DONE_KEY: extra_done_text,
        EXTRA_PLAN_KEY: extra_plan_text,
    }

    over = []
    if max(len(tables["용역_실적"]), len(tables["용역_계획"])) > YONG_MAX:
        over.append(f"용역 {YONG_MAX}행")
    if max(len(tables["자산_실적"]), len(tables["자산_계획"])) > ASSET_MAX:
        over.append(f"자산구매 {ASSET_MAX}행")
    if over:
        st.warning(
            f"현재 {', '.join(over)}를 넘는 항목은 한글 표에 모두 담기지 않을 수 있습니다. "
            "행 수를 줄이거나 엑셀 다운로드도 함께 사용해주세요."
        )

    hwpx_over = []
    if max(len(tables["용역_실적"]), len(tables["용역_계획"])) > HWPX_YONG_MAX:
        hwpx_over.append(f"용역 {HWPX_YONG_MAX}행 초과분")
    if max(len(tables["자산_실적"]), len(tables["자산_계획"])) > HWPX_ASSET_MAX:
        hwpx_over.append(f"자산구매 {HWPX_ASSET_MAX}행 초과분")
    if hwpx_over:
        st.info(
            f"업무망 호환을 위해 한글(HWPX)은 {', '.join(hwpx_over)}을 제외하고 생성합니다. "
            "전체 입력 내용은 엑셀 다운로드에 포함됩니다."
        )

    st.divider()
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("💾 저장", type="primary", use_container_width=True):
            try:
                save_common(tables)
                st.session_state["common_flash"] = "저장 완료"
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")

    fname = f"사업단_공통확인사항_{datetime.now(KST).strftime('%Y%m%d')}"
    with b2:
        try:
            st.download_button(
                "📄 한글(HWPX) 다운로드",
                data=build_common_hwpx(tables),
                file_name=f"{fname}.hwpx",
                mime="application/octet-stream",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"한글(HWPX) 생성 실패: {e}")
    with b3:
        st.download_button(
            "📊 엑셀 다운로드",
            data=build_common_xlsx(tables),
            file_name=f"{fname}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    st.caption("한글 파일을 열어서 표가 잘 나오는지 한 번 확인해주세요.")

def visit_page():
    """실증 방문 일지 — 현장 방문 기록 등록·조회(실증별 필터)·삭제."""
    st.header("📍 실증 방문 일지")
    st.caption("현장(가정·복지관·병원) 방문 기록을 실증별로 남깁니다.")
    _flash("visit_flash")

    SITES = ["WIM 장기실증", "광주서구 가정실증", "청양군 사회복지관",
             "안산시 부곡사회복지관", "병원실증", "서울대병원", "기타(직접 입력)"]

    open_f = st.session_state.get("visit_show_form", False)
    if st.button("➖ 등록 폼 닫기" if open_f else "➕ 방문 기록 추가",
                 use_container_width=True):
        st.session_state["visit_show_form"] = not open_f
        st.rerun()

    if st.session_state.get("visit_show_form"):
        with st.container(border=True):
            vc1, vc2, vc3 = st.columns(3)
            with vc1:
                vdate = st.date_input("방문일", value=datetime.now(KST).date(),
                                      key="visit_date")
            with vc2:
                site = st.selectbox("실증", SITES, key="visit_site")
                if site == "기타(직접 입력)":
                    site = st.text_input("실증 직접 입력", key="visit_site_custom")
            with vc3:
                visitor = st.selectbox("방문자", USER_NAMES,
                               index=_me_index(USER_NAMES), key="visit_visitor")
            content = st.text_area(
                "방문내용 (한 일)", key="visit_content", height=90,
                placeholder="예: 효돌 재설치, 센서 배터리 교체, 대상자 인터뷰")
            issue = st.text_area("이슈·특이사항 (선택)", key="visit_issue", height=70)
            if st.button("➕ 기록 저장", type="primary", use_container_width=True):
                if not (site and content.strip()):
                    st.warning("실증과 방문내용은 필수입니다.")
                else:
                    try:
                        add_visit(vdate.strftime("%Y-%m-%d"), site, visitor,
                                  content.strip(), issue.strip())
                        st.session_state["visit_flash"] = f"✅ 방문 기록 저장 — {site}"
                        for k in ("visit_content", "visit_issue"):
                            st.session_state.pop(k, None)
                        st.session_state["visit_show_form"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")

    st.divider()
    indexed = visit_rows()
    sites = sorted({r[1] for _, r in indexed if r[1].strip()})
    fsel = st.selectbox("실증 필터", ["전체"] + sites, key="visit_filter")
    shown = [(i, r) for i, r in indexed if fsel == "전체" or r[1] == fsel]
    shown.sort(key=lambda ir: (ir[1][0], ir[1][5]), reverse=True)  # 방문일 최신순
    st.subheader(f"📋 방문 기록 — {len(shown)}건")
    if not shown:
        st.caption("기록이 없습니다.")
    for i, r in shown[:50]:
        with st.container(border=True):
            st.markdown(f"**{r[0]}** · {r[1]} · {r[2]}")
            if r[3].strip():
                st.write(r[3])
            if r[4].strip():
                st.caption(f"⚠️ 이슈: {r[4]}")
            dc1, dc2 = st.columns([1, 3])
            dok = dc1.checkbox("삭제 확인", key=f"visit_delok_{i}")
            if dc2.button("🗑️ 삭제", key=f"visit_del_{i}", disabled=not dok):
                try:
                    delete_visit(i, r[5])
                    st.session_state["visit_flash"] = "🗑️ 방문 기록 삭제됨"
                    st.rerun()
                except VisitRowMismatch:
                    visit_rows.clear()
                    st.warning("그 사이 목록이 바뀌었습니다. 새로고침 후 다시 시도해주세요.")
                    st.rerun()
                except Exception as e:
                    st.error(f"삭제 실패: {e}")
    if len(shown) > 50:
        st.caption(f"…최근 50건만 표시 (전체 {len(shown)}건)")


def _notice_manage():
    """공지 등록/관리 — 홈 하단 토글에서 호출(누구나). 공지 표시는 홈 좌측 상단."""
    today = datetime.now(KST).date()
    try:
        ntc = notices()
    except Exception:
        ntc = []
    nauth = st.selectbox("작성자", NOTICE_AUTHORS + ["직접 입력"],
                         index=_me_index(NOTICE_AUTHORS + ["직접 입력"]),
                         key="adm_notice_author")
    if nauth == "직접 입력":
        nauth = (st.text_input("작성자 직접 입력",
                 key="adm_notice_author_custom").strip() or "담당자")
    ntext = st.text_input("새 공지 내용", key="adm_notice_text",
                          placeholder="예: 이번주 회의 목요일 15시로 변경")
    use_exp = st.checkbox("표시 종료일 지정 (그날 이후 자동삭제)", key="adm_notice_useexp")
    exp_str = ""
    if use_exp:
        d = st.date_input("이 날까지만 표시", value=today, key="adm_notice_exp")
        exp_str = d.strftime("%Y-%m-%d")
    if st.button("➕ 공지 등록", key="adm_notice_add"):
        if ntext.strip():
            add_notice(nauth, ntext.strip(), exp_str)
            st.session_state.pop("adm_notice_text", None)
            st.rerun()
    st.caption("📋 문서협업은 진행중이면 홈 공지에 자동으로 뜨고 완료·삭제 시 사라집니다"
               "(별도 등록 불필요).")
    if ntc:
        st.markdown("**현재 공지**")
    for _idx, r in sorted(ntc, key=lambda x: x[0], reverse=True):
        exp_tag = f"  ~{r[3]}" if r[3].strip() else ""
        dc1, dc2 = st.columns([5, 1])
        dc1.caption(f"• {r[2]}  ({r[1]} · {r[0]}{exp_tag})")
        if dc2.button("🗑️", key=f"adm_ndel_{_idx}"):
            try:
                delete_notice(_idx, r[0])
            except Exception:
                notices.clear()
            st.rerun()


def _backup_section():
    """전체 데이터 백업 — 홈에서 호출(누구나)."""
    st.markdown("**🗄️ 전체 데이터 백업** — 모든 탭(업무보고·구매요청·문서협업·"
                "장비현황·방문일지)을 엑셀 1개로 내려받아 오프라인 보관하세요.")
    if st.button("🔄 백업 파일 만들기", key="home_backup_make"):
        try:
            st.session_state["backup_xlsx"] = build_full_backup_xlsx()
        except Exception as e:
            st.error(f"백업 생성 실패: {e}")
    if st.session_state.get("backup_xlsx"):
        st.download_button(
            "📦 전체 데이터 백업 다운로드",
            data=st.session_state["backup_xlsx"],
            file_name=f"돌봄로봇_전체백업_{datetime.now(KST).strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    st.caption("※ 참고: 구글 시트는 자체 **버전 기록**이 있어, 실수로 지우거나 덮어써도 "
               "구글시트 '파일 → 버전 기록'에서 과거 상태로 되돌릴 수 있습니다.")


def _report_collect():
    """제출 현황 + 미리보기 + HWPX 취합본 생성 (구 담당자 대시보드에서 이동, 누구나)."""
    week = st.text_input("조회 주차", value=this_wednesday(), key="collect_week",
                         help="예: 2026-04-22 (해당 주 수요일)")

    status = submission_status(week)
    df = pd.DataFrame([
        {"이름": s["name"],
         "상태": "✅ 완료" if s["submitted"] else "⏳ 미제출",
         "제출시간": s["submitted_at"] or "-"}
        for s in status
    ])

    done_count = sum(1 for s in status if s["submitted"])
    st.metric("제출 현황", f"{done_count} / {len(status)}")
    st.dataframe(df, use_container_width=True, hide_index=True)

    missing = [s["name"] for s in status if not s["submitted"]]
    if missing:
        st.warning(f"미제출: {', '.join(missing)}")
    else:
        st.success("전원 제출 완료 🎉")

    with st.expander("🔍 제출 내용 미리보기"):
        data = load_week(week)
        for name in MEMBER_NAMES:
            r = data.get(name)
            if not r:
                continue
            st.markdown(f"**{name}**  _{r['submitted_at']}_")
            member = get_member(name)
            fields = get_fields_for(member)
            for f in fields:
                val = r.get(f, "") or "-"
                st.caption(FIELD_LABELS[f])
                st.text(val)
            st.divider()

    st.subheader("📤 내보내기")

    try:
        wed = wednesday_of_week(week)
    except ValueError:
        st.error("주차 형식이 잘못되었습니다 (YYYY-MM-DD).")
        return

    # 수요일 기준(보고일): 실적=지난주 수요일~이번주 화요일, 계획=이번주 수요일~다음주 화요일
    period_start = (wed - timedelta(days=7)).strftime("%Y.%m.%d.")  # 지난주 수요일
    period_end = (wed - timedelta(days=1)).strftime("%Y.%m.%d.")    # 이번주 화요일
    plan_start = wed.strftime("%Y.%m.%d.")                          # 이번주 수요일
    plan_end = (wed + timedelta(days=6)).strftime("%Y.%m.%d.")      # 다음주 화요일
    title_date = wed.strftime("%y.%m.%d.")

    c1, c2 = st.columns(2)
    with c1:
        period_start = st.text_input("실적 시작", period_start)
        period_end = st.text_input("실적 종료", period_end)
    with c2:
        plan_start = st.text_input("계획 시작", plan_start)
        plan_end = st.text_input("계획 종료", plan_end)

    title_date = st.text_input("제목 날짜", title_date)

    # 레포 루트 (streamlit_app.py의 부모의 부모)에서 HWPX 템플릿 찾기
    repo_root = Path(__file__).resolve().parent.parent
    template_files = sorted(repo_root.glob("돌봄로봇_업무보고*.hwpx"))
    template_path = st.selectbox(
        "템플릿 HWPX 파일",
        template_files,
        format_func=lambda p: p.name,
        index=len(template_files) - 1 if template_files else 0,
    ) if template_files else None

    uploaded = st.file_uploader("또는 템플릿 직접 업로드", type=["hwpx"])

    if st.button("📥 HWPX 생성 및 다운로드", type="primary", use_container_width=True):
        try:
            if uploaded is not None:
                template_bytes = uploaded.getvalue()
            elif template_path is not None:
                template_bytes = template_path.read_bytes()
            else:
                st.error("템플릿 HWPX를 선택하거나 업로드해주세요.")
                return

            submissions = load_week(week)

            # 미제출자는 지난주 내용 fallback (완전 미제출인 사람만)
            last_week_str = (wed - timedelta(days=7)).strftime("%Y-%m-%d")
            last_week_subs = load_week(last_week_str)
            fallback_used = []
            for name in MEMBER_NAMES:
                if name not in submissions and name in last_week_subs:
                    submissions[name] = last_week_subs[name]
                    fallback_used.append(name)
            if fallback_used:
                st.info(f"🔄 이번주 미제출 {len(fallback_used)}명은 지난주 내용으로 대체: "
                        f"{', '.join(fallback_used)}")

            result = build_report(
                template_bytes, submissions,
                title_date=title_date,
                period_start=period_start, period_end=period_end,
                plan_start=plan_start, plan_end=plan_end,
            )
            filename = f"돌봄로봇_업무보고({wed.strftime('%m.%d')})_취합본.hwpx"
            st.download_button(
                "💾 HWPX 다운로드",
                data=result,
                file_name=filename,
                mime="application/octet-stream",
                use_container_width=True,
            )
            st.success("생성 완료. 위 버튼으로 다운로드하세요.")
        except Exception as e:
            st.error(f"생성 실패: {e}")

    # 🗄️ 전체 데이터 백업 (홈에서 이동, 기본 접힘 — 누구나)
    st.divider()
    b_open = st.session_state.get("collect_backup_open", False)
    if st.button("➖ 백업 닫기" if b_open else "🗄️ 전체 데이터 백업",
                 key="collect_backup_open_btn", use_container_width=True):
        st.session_state["collect_backup_open"] = not b_open
        st.rerun()
    if st.session_state.get("collect_backup_open"):
        with st.container(border=True):
            _backup_section()


def main():
    if not auth_gate():
        return

    # 전역 정체성 me: ?me=로 새로고침에도 복원 → 어느 페이지에서 접속해도 이름 기본값으로 사용
    if "me" not in st.session_state:
        _q = st.query_params.get("me")
        st.session_state["me"] = _q if _q in USER_NAMES else None

    # 전체 페이지 여백 축소 — layout=wide 기본 상단·좌우 패딩이 커서 화면이 비어 보임
    st.markdown("""<style>
      .block-container,
      [data-testid="stMainBlockContainer"]{
        padding-top:2.2rem;padding-bottom:2rem;
        padding-left:2.4rem;padding-right:2.4rem;}
    </style>""", unsafe_allow_html=True)

    with st.sidebar:
        mode_options = ["🏠 홈", "📝 업무보고 작성·취합",
                        "🏠 스마트돌봄스페이스", "🛒 구매요청서", "📋 문서 협업",
                        "🔧 장비 사용현황", "📍 실증 방문 일지", "📚 과거 회의록 열람"]
        # 홈의 바로가기 버튼(_nav_to)이 있으면 그 메뉴로 이동
        nav = st.session_state.pop("_nav_to", None)
        if nav and nav in mode_options:
            st.session_state["main_menu"] = nav
        mode = st.radio("메뉴", mode_options, key="main_menu")
        st.divider()
        if st.button("로그아웃"):
            st.session_state.pop("authed", None)
            st.query_params.clear()
            st.rerun()

    if mode == "🏠 홈":
        home_page()
    elif mode == "📝 업무보고 작성·취합":
        member_page()
    elif mode == "🏠 스마트돌봄스페이스":
        space_page()
    elif mode == "📍 실증 방문 일지":
        visit_page()
    elif mode == "🛒 구매요청서":
        purchase_page()
    elif mode == "📋 문서 협업":
        collab_page()
    elif mode == "🔧 장비 사용현황":
        equip_page()
    else:
        history_page()


if __name__ == "__main__":
    main()
