"""돌봄로봇 주간 업무보고 취합 웹앱."""
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

from team_config import (
    TEAM_MEMBERS, MEMBER_NAMES, FIELD_LABELS,
    get_member, get_fields_for,
    APP_PASSWORD, ADMIN_PASSWORD,
)
from sheets_store import (
    load_week, save_submission, submission_status, weeks_with_counts,
    FIELD_KEYS, KST,
)
from space_store import (
    FAQ_HEADER, SPACE_LOG_HEADER, SheetNotConfigured, RowMismatch, sheet_url,
    faq_rows, add_faq, space_log_rows, add_space_log, resolve_space_log,
)
from purchase_store import (
    PURCHASE_HEADER, STATUS_DONE, RequestNotFound,
    purchase_rows, add_purchase, build_purchase_xlsx, resolve_purchase,
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
    # URL 쿼리 파라미터로 로그인 유지 (새로고침 대응)
    qp = st.query_params
    if not st.session_state.get("authed"):
        token = qp.get("auth")
        if token == "team":
            st.session_state["authed"] = True
            st.session_state["is_admin"] = False
        elif token == "admin":
            st.session_state["authed"] = True
            st.session_state["is_admin"] = True

    if st.session_state.get("authed"):
        return True

    st.title("📋 돌봄로봇 주간 업무보고")
    pw = st.text_input("비밀번호", type="password", key="pw_input")
    if st.button("입장"):
        if pw == APP_PASSWORD:
            st.session_state["authed"] = True
            st.session_state["is_admin"] = False
            st.query_params["auth"] = "team"
            st.rerun()
        elif pw == ADMIN_PASSWORD:
            st.session_state["authed"] = True
            st.session_state["is_admin"] = True
            st.query_params["auth"] = "admin"
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


def member_page():
    st.header("✍️ 업무보고 작성")

    col1, col2 = st.columns([2, 2])
    with col1:
        name = st.selectbox("본인 이름", MEMBER_NAMES, key="member_name")
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
        writer = st.selectbox("작성자", MEMBER_NAMES, key="faq_writer")
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
        finder = st.selectbox("발견자", MEMBER_NAMES, key="log_finder")
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
                fixer = st.selectbox("조치자 (본인 이름)", MEMBER_NAMES,
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
        requester = st.selectbox("요청자", MEMBER_NAMES, key="pur_requester")
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
                         "구매사유", "비고(구매처)"]],
                     hide_index=True, use_container_width=True)

    pending = {k: v for k, v in by_req.items() if _req_status(v) != STATUS_DONE}
    done = {k: v for k, v in by_req.items() if _req_status(v) == STATUS_DONE}

    # 담당자 전용: 구매완료 처리
    if st.session_state.get("is_admin") and pending:
        st.subheader("✅ 구매완료 처리 (담당자)")

        def _plabel(rid):
            g = pending[rid]
            return f"{g[0][1]} · {g[0][2]} — {len(g)}개 품목 · {_req_total(g):,}원"

        sel = st.selectbox("완료 처리할 요청 선택", sorted(pending, reverse=True),
                           index=None, format_func=_plabel,
                           placeholder="요청을 선택하세요...", key="pur_resolve_sel")
        if sel:
            rc1, rc2 = st.columns(2)
            with rc1:
                processor = st.selectbox("처리자", MEMBER_NAMES, key="pur_processor")
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


def admin_page():
    st.header("📊 담당자 대시보드")

    week = st.text_input("조회 주차", value=this_wednesday(),
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


def main():
    if not auth_gate():
        return

    with st.sidebar:
        st.caption(f"접속 모드: {'관리자' if st.session_state.get('is_admin') else '팀원'}")
        mode_options = ["업무보고 작성", "🏠 스마트돌봄스페이스", "🛒 구매요청서",
                        "📚 과거 회의록 열람"]
        if st.session_state.get("is_admin"):
            mode_options.append("담당자 대시보드")
        mode = st.radio("메뉴", mode_options)
        st.divider()
        if st.button("로그아웃"):
            for k in ["authed", "is_admin"]:
                st.session_state.pop(k, None)
            st.query_params.clear()
            st.rerun()

    if mode == "업무보고 작성":
        member_page()
    elif mode == "🏠 스마트돌봄스페이스":
        space_page()
    elif mode == "🛒 구매요청서":
        purchase_page()
    elif mode == "📚 과거 회의록 열람":
        history_page()
    else:
        admin_page()


if __name__ == "__main__":
    main()
