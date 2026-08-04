"""돌봄로봇 주간 업무보고 취합 웹앱."""
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta, time
from urllib.parse import quote
from html import escape as html_escape
import json
import base64
import re
import pandas as pd
from pathlib import Path

from team_config import (
    TEAM_MEMBERS, MEMBER_NAMES, USER_NAMES, FIELD_LABELS, NOTICE_AUTHORS,
    get_member, get_fields_for,
    APP_PASSWORD, ADMIN_IDS,
)
import account_store
import todo_store
import request_store
import feedback_store
import resource_store
import mail_store
from sheets_store import (
    load_week, save_submission, submission_status, weeks_with_counts,
    build_full_backup_xlsx, latest_submission, FIELD_KEYS, KST,
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
    EQUIP_HEADER, equip_rows, save_all_equipment, build_equip_xlsx, sheet_link,
)
from visit_store import (
    VISIT_HEADER, visit_rows, add_visit, delete_visit,
    RowMismatch as VisitRowMismatch,
)
from calendar_store import (
    calendar_enabled, embed_url, upcoming_events, today_events, month_events,
    add_event, update_event, delete_event, event_view,
)
from news_store import fetch_news, fetch_section, NEWS_SECTIONS
from notice_store import (notices, add_notice, delete_notice,
                          is_expired, sweep_expired,
                          readers as notice_readers,
                          mark_read as mark_notice_read)
from common_store import (
    KEYS as COMMON_KEYS, EXTRA_KEY, EXTRA_DONE_KEY, EXTRA_PLAN_KEY, YONG_MAX, ASSET_MAX,
    HWPX_YONG_MAX, HWPX_ASSET_MAX,
    load_common, save_common, build_common_hwpx, build_common_xlsx,
)
from hwpx_exporter import build_report

_ICON = Path(__file__).resolve().parent / "assets" / "dolbom_favicon.png"
st.set_page_config(page_title="dolbom studio",
                   page_icon=str(_ICON) if _ICON.exists() else "🧡",
                   layout="wide", initial_sidebar_state="collapsed")


# 줌 바로가기 타일 아이콘(파란 라운드 사각 + 흰 카메라) — 외부 이미지 로드 없이 인라인.
_ZOOM_SVG = (
    '<svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">'
    '<rect x="2" y="2" width="44" height="44" rx="13" fill="#2D8CFF"/>'
    '<path d="M12 17.5h14.5c1.7 0 3 1.3 3 3v10c0 1.7-1.3 3-3 3H12c-1.7 0-3-1.3-3-3'
    'v-10c0-1.7 1.3-3 3-3z" fill="#fff"/>'
    '<path d="M31.5 23.6l6.2-4.3c.8-.6 1.8 0 1.8.9v10.6c0 .9-1 1.5-1.8.9l-6.2-4.3z"'
    ' fill="#fff"/></svg>')


def zoom_links():
    """팀 공용 줌 링크 목록 [(이름, 주소), ...]. 주간회의·세미나처럼 고정 링크가
    여러 개라 이름을 붙여 저장한다(JSON). 옛 단일 링크('zoom')도 함께 인식."""
    out = []
    try:
        raw = todo_store.get_sync("_team", "zoom_links")
        if raw:
            out = [(str(d.get("name", "")).strip(), str(d.get("url", "")).strip())
                   for d in json.loads(raw)]
            out = [t for t in out if t[0] and t[1]]
    except Exception:
        out = []
    if not out:                      # 예전 방식(단일 링크)에서 넘어오는 경우
        try:
            old = todo_store.get_sync("_team", "zoom")
        except Exception:
            old = ""
        if old:
            out = [("주간회의", old)]
    return out


def save_zoom_links(items):
    """[(이름, 주소), ...] 저장. 빈 줄은 버림."""
    data = [{"name": n.strip(), "url": u.strip()} for n, u in items
            if n.strip() and u.strip()]
    todo_store.set_sync("_team", "zoom_links",
                        json.dumps(data, ensure_ascii=False))


def _brand(where="home"):
    """DS 주황 배지 + 'dolbom studio' 브랜드 블록 HTML."""
    if where == "sidebar":
        name_c, sub_c, size, badge = "#F3E9DC", "#B9A892", 19, 34
        # 사이드바는 바로 아래에 다크모드 토글이 붙어서 여백을 넉넉히(겹침 방지)
        return (
            f'<div style="display:flex;align-items:center;gap:12px;'
            f'margin:2px 0 16px;">'
            f'<div style="flex:0 0 auto;width:{badge}px;height:{badge}px;'
            f'border-radius:{int(badge*0.28)}px;'
            f'background:#C4622D;color:#fff;font-weight:800;font-size:{int(badge*0.44)}px;'
            f'display:flex;align-items:center;justify-content:center;letter-spacing:1px;'
            f'font-family:Arial,sans-serif;box-shadow:0 2px 7px rgba(196,98,45,.35);">DS</div>'
            f'<div style="line-height:1.15;">'
            f'<div style="font-size:{size}px;font-weight:800;color:{name_c};">'
            f'dolbom studio</div>'
            f'<div style="font-size:{max(10,int(size*0.5))}px;color:{sub_c};">'
            f'돌봄로봇 사업단 · 업무·협업 공간</div>'
            f'</div></div>')
    else:  # home / login
        name_c, sub_c, size, badge = "#C4622D", "#8A7A6B", (34 if where == "login" else 26), (54 if where == "login" else 46)
    return (
        f'<div style="display:flex;align-items:center;gap:12px;margin:2px 0 8px;">'
        f'<div style="width:{badge}px;height:{badge}px;border-radius:{int(badge*0.28)}px;'
        f'background:#C4622D;color:#fff;font-weight:800;font-size:{int(badge*0.44)}px;'
        f'display:flex;align-items:center;justify-content:center;letter-spacing:1px;'
        f'font-family:Arial,sans-serif;box-shadow:0 2px 7px rgba(196,98,45,.35);">DS</div>'
        f'<div style="line-height:1.15;">'
        f'<div style="font-size:{size}px;font-weight:800;color:{name_c};">dolbom studio</div>'
        f'<div style="font-size:{max(10,int(size*0.5))}px;color:{sub_c};">돌봄로봇 사업단 · 업무·협업 공간</div>'
        f'</div></div>'
    )


def this_wednesday() -> str:
    today = datetime.now().date()
    days_until_wed = (2 - today.weekday()) % 7
    wednesday = today + timedelta(days=days_until_wed)
    return wednesday.strftime("%Y-%m-%d")


def wednesday_of_week(week_str: str) -> datetime:
    return datetime.strptime(week_str, "%Y-%m-%d")


def _set_session(a: dict):
    """로그인 성공 시 세션 세팅. me=이름, is_admin=관리자 아이디 여부."""
    st.session_state["authed"] = True
    st.session_state["uid"] = a["아이디"]
    st.session_state["me"] = a["이름"]
    st.session_state["title"] = a.get("직함", "")
    st.session_state["tok"] = account_store.token_for(a)
    st.session_state["is_admin"] = a["아이디"] in ADMIN_IDS


def _try_login_token(uid, tok):
    """uid+tok가 유효하면 세션 로그인 + URL 토큰 세팅. 성공 시 True."""
    if not (uid and tok):
        return False
    try:
        a = account_store.get_account(uid)
    except Exception:
        a = None
    if a and a["상태"].strip() == account_store.ST_OK \
            and account_store.token_for(a) == tok:
        _set_session(a)
        st.query_params["uid"] = a["아이디"]
        st.query_params["tok"] = account_store.token_for(a)
        return True
    return False


def auth_gate():
    """개인 계정 로그인 + 회원가입(관리자 승인). 공용 비밀번호는 폐지."""
    qp = st.query_params
    # 1) URL 토큰(?uid=&tok=)으로 복원 — 새로고침·주소공유용(토큰 위조 불가)
    if not st.session_state.get("authed"):
        _try_login_token(qp.get("uid"), qp.get("tok"))
    if st.session_state.get("authed"):
        return True

    # 2) 브라우저 저장(localStorage)으로 복원 — 다음 방문 자동 로그인.
    #    streamlit-js-eval은 값 없으면 None만 반환(대기 루프 없음 → 앱 멈춤 불가).
    #    로그인 화면일 때만 컴포넌트 렌더(로그인된 페이지엔 안 뜸).
    try:
        from streamlit_js_eval import get_local_storage, remove_local_storage
        if st.session_state.get("_ls_clear"):        # 로그아웃 직후 저장정보 삭제
            remove_local_storage("ds_auth", component_key="ls_del")
            st.session_state.pop("_ls_clear", None)
        else:
            raw = get_local_storage("ds_auth", component_key="ls_get")
            if raw and "|" in raw:
                _u, _t = raw.split("|", 1)
                if _try_login_token(_u, _t):
                    st.rerun()
    except Exception:
        pass

    st.markdown(_brand("login"), unsafe_allow_html=True)
    st.caption("개인 계정으로 로그인하세요. 계정이 없으면 회원가입 후 관리자 승인을 받으면 됩니다. "
               "💡 '이 기기에 로그인 정보 저장'을 켜두면 다음부터 이 기기에서 자동 로그인됩니다.")
    tab_login, tab_join, tab_find = st.tabs(
        ["🔑 로그인", "📝 회원가입", "🔎 아이디·비번 찾기"])
    with tab_login:
        lid = st.text_input("아이디", key="login_id")
        lpw = st.text_input("비밀번호", type="password", key="login_pw")
        lrem = st.checkbox("이 기기에 로그인 정보 저장(자동 로그인)", value=True,
                           key="login_remember")
        if st.button("로그인", type="primary"):
            try:
                a, err = account_store.login(lid, lpw)
            except Exception as e:
                a, err = None, f"로그인 오류: {e}"
            if a:
                _set_session(a)
                st.query_params["uid"] = a["아이디"]
                st.query_params["tok"] = account_store.token_for(a)
                if lrem:   # 저장은 main()의 정상 렌더에서(로그인 직후 rerun에 안 잘리게)
                    st.session_state["_ls_save"] = \
                        a["아이디"] + "|" + account_store.token_for(a)
                st.rerun()
            else:
                st.error(err)
    with tab_join:
        st.caption("이름·직함·아이디·비밀번호·이메일(korea·gmail)을 입력하고 신청하면, "
                   "관리자 승인 후 로그인됩니다.")
        jname = st.text_input("이름", key="join_name")
        jtitle = st.text_input("직함", key="join_title", placeholder="예: 연구원 / 과장")
        jid = st.text_input("아이디", key="join_id")
        jpw = st.text_input("비밀번호", type="password", key="join_pw")
        jpw2 = st.text_input("비밀번호 확인", type="password", key="join_pw2")
        jek = st.text_input("이메일 (korea)", key="join_email_k",
                            placeholder="예: hong@korea.ac.kr")
        jeg = st.text_input("이메일 (gmail)", key="join_email_g",
                            placeholder="예: hong@gmail.com")
        if st.button("회원가입 신청"):
            if (jpw or "") != (jpw2 or ""):
                st.warning("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
            elif len(jpw or "") < 4:
                st.warning("비밀번호는 4자 이상으로 해주세요.")
            else:
                try:
                    stt = account_store.register(jid, jpw, jname, jtitle,
                                                 jek, jeg, ADMIN_IDS)
                    if stt == account_store.ST_OK:
                        # 자동 승인(관리자) → 가입 즉시 자동 로그인해서 바로 입장
                        a = account_store.get_account(jid)
                        if a:
                            _set_session(a)
                            st.query_params["uid"] = a["아이디"]
                            st.query_params["tok"] = account_store.token_for(a)
                            st.rerun()
                        else:
                            st.success("등록 완료! 위 '🔑 로그인' 탭에서 로그인하세요.")
                    else:
                        st.success("가입 신청 완료! 관리자 승인 후 "
                                   "위 '🔑 로그인' 탭에서 로그인하세요.")
                except ValueError as e:
                    st.warning(str(e))
                except Exception as e:
                    st.error(f"가입 오류: {e}")
    with tab_find:
        st.caption("이름과 **가입 때 등록한 이메일**(korea·gmail 중 하나)을 입력하면, "
                   "아이디를 알려주고 비밀번호를 새로 정할 수 있습니다.")
        fn = st.text_input("이름", key="find_name")
        fe = st.text_input("이메일 (korea 또는 gmail)", key="find_email")
        if st.button("🔎 계정 찾기", key="find_btn"):
            try:
                fa = account_store.find_by_identity(fn, fe)
            except Exception as e:
                fa = None
                st.error(f"조회 오류: {e}")
            if fa:
                st.session_state["_recover_uid"] = fa["아이디"]
            else:
                st.session_state.pop("_recover_uid", None)
                st.warning("일치하는 계정이 없습니다. 이름·이메일을 확인하세요.")
        _ruid = st.session_state.get("_recover_uid")
        if _ruid:
            st.success(f"✅ 아이디: **{_ruid}**")
            np1 = st.text_input("새 비밀번호 (👁 눈 아이콘으로 확인)",
                                type="password", key="find_np1")
            if st.button("🔑 비밀번호 재설정", type="primary", key="find_reset"):
                if len((np1 or "").strip()) < 4:
                    st.warning("비밀번호는 4자 이상으로 해주세요.")
                else:
                    try:
                        account_store.reset_password(_ruid, np1.strip())
                        st.session_state.pop("_recover_uid", None)
                        st.session_state.pop("find_np1", None)
                        st.success("비밀번호를 변경했습니다. 위 '🔑 로그인' 탭에서 "
                                   "새 비밀번호로 로그인하세요.")
                    except Exception as e:
                        st.error(f"재설정 실패: {e}")
    return False


def _me_index(options, default=0):
    """전역 정체성 me(홈에서 1회 설정)의 options 내 위치. 이름 selectbox 기본값용.
    me가 없거나 목록에 없으면 default(기본 0=첫 항목, 기존 동작 유지)."""
    me = st.session_state.get("me")
    return options.index(me) if me in options else default


def _auto_import(uid, name):
    """주간보고 계획(번호 붙은 줄) + 내 CC 메일을 '내 할 일'에 자동 추가.

    이미 가져온 지점(todo_store의 _sync)을 기록해 **새 것만** 넣는다.
    → 사용자가 ✓로 지운 항목이 다시 살아나지 않는다. 세션당 1회만 실행.
    """
    if not uid or st.session_state.get("_auto_imp_done"):
        return
    st.session_state["_auto_imp_done"] = True
    try:
        existing = {r["내용"].strip() for r in todo_store.list_todos(uid)}
    except Exception:
        return
    added = 0

    # ① 주간보고 계획 — '1.' '2)' 처럼 번호로 시작하는 줄만, 새 주차일 때만
    try:
        last_wk = todo_store.get_sync(uid, "report")
        latest = latest_submission(name)
        if latest:
            wk, data = latest
            if wk and wk != last_wk:
                for fk in ("research_plan", "task_plan"):
                    for ln in (data.get(fk, "") or "").replace("\r", "").split("\n"):
                        s = ln.strip()
                        if not re.match(r"^\d+\s*[.)]\s*\S", s):
                            continue
                        item = f"📄 {s}"
                        if item in existing:
                            continue
                        todo_store.add_todo(uid, item)
                        existing.add(item)
                        added += 1
                todo_store.set_sync(uid, "report", wk)
    except Exception:
        pass

    # ② 메일 — 내 등록 이메일로 보낸 것만(mails_for), 마지막 수집시각 이후만
    try:
        acc = account_store.get_account(uid) or {}
        emails = [acc.get("이메일_korea", ""), acc.get("이메일_gmail", "")]
        last_dt = todo_store.get_sync(uid, "mail")
        newest = last_dt
        for m in mail_store.mails_for(emails):
            dt = (m.get("날짜", "") or "").strip()
            if last_dt and dt <= last_dt:
                continue
            tag, _pri = mail_store.classify(m.get("제목", ""), m.get("본문", ""))
            item = f"📧 {tag} · {m.get('제목', '(제목 없음)')}"
            if item not in existing:
                todo_store.add_todo(uid, item)
                existing.add(item)
                added += 1
            if dt > newest:
                newest = dt
        if newest and newest != last_dt:
            todo_store.set_sync(uid, "mail", newest)
    except Exception:
        pass

    if added:
        st.toast(f"📥 새 항목 {added}건을 '내 할 일'에 자동 추가했습니다.")


# ── 개인 할 일: 브라우저(내 기기)에만 저장 ────────────────────────────────
#   구글시트는 팀 공용이라 시트를 열 수 있는 사람에게 개인 메모가 노출된다.
#   그래서 개인 할 일은 서버에 보내지 않고 브라우저 localStorage 에만 둔다.
#   ⚠️ 기기별로 따로 저장된다(폰과 PC가 공유되지 않음). 브라우저 데이터를
#      지우면 함께 사라진다 — 중요한 건 '업무'로 두는 편이 안전.
def _per_key(uid):
    return f"ds_per_{(uid or '').strip()}"


def personal_todos(uid):
    """브라우저에 저장된 개인 할 일 [{'t':내용,'ts':등록시각}, ...] (세션당 1회 읽음)."""
    if not uid:
        return []
    if not st.session_state.get("_per_loaded"):
        try:
            from streamlit_js_eval import get_local_storage
            raw = get_local_storage(_per_key(uid), component_key="ls_per_get")
        except Exception:
            raw = None
        if raw is not None:                    # None = 아직 응답 전(다음 실행에 옴)
            try:
                st.session_state["_per"] = json.loads(raw) if raw else []
            except Exception:
                st.session_state["_per"] = []
            st.session_state["_per_loaded"] = True
    return st.session_state.get("_per", [])


def save_personal(uid, items):
    """개인 할 일 저장 — 실제 쓰기는 main() 끝에서(컴포넌트 렌더 타이밍 때문)."""
    st.session_state["_per"] = items
    st.session_state["_per_loaded"] = True
    st.session_state["_ls_per_save"] = (_per_key(uid),
                                        json.dumps(items, ensure_ascii=False))


def _todo_badges(item, today):
    """할 일 옆에 붙는 배지 — 마감(D-day)과 등록 후 경과일.
    오래 묵은 일과 임박한 일이 눈에 띄게 색을 달리한다."""
    out = []
    due = (item.get("마감일", "") or "").strip()
    if due:
        try:
            d = (datetime.strptime(due, "%Y-%m-%d").date() - today).days
            if d < 0:
                txt, col = f"D+{-d}", "#e05252"
            elif d == 0:
                txt, col = "D-0", "#e05252"
            elif d <= 3:
                txt, col = f"D-{d}", "#e08a3c"
            else:
                txt, col = f"D-{d}", "#8a8781"
            out.append((txt, col))
        except Exception:
            pass
    ts = (item.get("등록일시", "") or "")[:10]
    if ts:
        try:
            age = (today - datetime.strptime(ts, "%Y-%m-%d").date()).days
            # 7일 미만은 표시하지 않는다 — 배지가 많으면 줄이 넘어가 정렬이 깨진다
            if age >= 14:
                out.append((f"{age}일", "#e05252"))
            elif age >= 7:
                out.append((f"{age}일", "#e08a3c"))
        except Exception:
            pass
    # white-space:nowrap — 없으면 '22일 / 째'처럼 배지 가운데서 줄이 바뀐다
    return "".join(
        f"<span style='margin-left:5px;font-size:.72em;color:{c};"
        f"border:1px solid {c}55;border-radius:4px;padding:0 4px;"
        f"white-space:nowrap;display:inline-block;'>{t}</span>"
        for t, c in out)


def _todo_sort_key(item, today):
    """사용자가 드래그로 정한 순서가 있으면 그것을 따르고(맨 위가 1번),
    없으면 예전 방식(중요 → 마감 임박 → 오래된 순)으로 정렬한다."""
    o = (item.get("순서", "") or "").strip()
    if o:
        try:
            return (0, int(o), "")
        except ValueError:
            pass
    star = 0 if (item.get("중요", "") or "").strip() else 1
    due = (item.get("마감일", "") or "").strip()
    try:
        dd = (datetime.strptime(due, "%Y-%m-%d").date() - today).days
    except Exception:
        dd = 9999                      # 마감 없는 건 뒤로
    return (1, star * 10000 + min(dd, 9999), item.get("등록일시", ""))


def _req_peers(rq, me):
    """같은 요청을 받은 다른 사람들의 완료·회신 요약(받은 사람 화면용).
    누가 이미 했는지 보이면 중복 작업·눈치보기가 줄어든다."""
    try:
        grp = request_store.group_rows(rq["요청자"], rq["내용"], rq["등록일시"])
    except Exception:
        return ""
    others = [g for g in grp if g["대상"].strip() != (me or "").strip()]
    if not others:
        return ""
    done, rep, lines = 0, 0, []
    for g in others:
        _rp = (g.get("회신", "") or "").strip()
        if g["상태"].strip() == request_store.ST_DONE:
            done += 1
            lines.append(f"✅ {g['대상']} {_hm(g['완료일시'])}"
                         + (f" · 💬 {_rp}" if _rp else ""))
        elif _rp:
            rep += 1
            lines.append(f"💬 {g['대상']}: {_rp}")
    if not lines:
        return (f"<br>다른 {len(others)}명은 아직 응답 없음")
    return ("<br>다른 사람 — 완료 " + str(done) + "명 · 회신 " + str(rep)
            + f"명 · 대기 {len(others) - done - rep}명<br>"
            + "<br>".join(lines))


def _drag_available() -> bool:
    """드래그 정렬 컴포넌트가 설치돼 있는지(없으면 기존 목록만 보여준다)."""
    try:
        import streamlit_sortables  # noqa: F401
        return True
    except Exception:
        return False


def _drag_sort(by_area, uid, today):
    """🔬 연구 / 🏢 업무 두 칸 사이로 끌어 옮기고 순서를 정하는 화면.

    컴포넌트가 '글자'만 주고받으므로 앞에 번호를 붙여 고유하게 만든 뒤,
    돌아온 순서대로 (행번호, 영역, 순번)을 계산해 한 번에 저장한다.
    """
    import streamlit_sortables as sortables

    labels, back = {}, {}
    for area in (todo_store.AREA_RESEARCH, todo_store.AREA_WORK):
        items = sorted(by_area.get(area, []),
                       key=lambda x: _todo_sort_key(x, today))
        labels[area] = []
        for i, p in enumerate(items, start=1):
            # 컴포넌트는 '글자'로 항목을 구분하므로 고유해야 한다. 행번호를 앞에
            # 붙이면 화면에 그대로 보이므로, 보이지 않는 문자(U+200B)를 개수만큼
            # 덧붙여 눈에는 안 띄면서 서로 다른 값이 되게 한다.
            tag = p["내용"] + "​" * (len(back) + 1)
            labels[area].append(tag)
            back[tag] = p
    st.caption("끌어서 순서를 바꾸고, 🔬연구 ↔ 🏢업무 사이로 옮길 수 있습니다. "
               "맨 위가 1번입니다.")
    res = sortables.sort_items(
        [{"header": f"🔬 {todo_store.AREA_RESEARCH}",
          "items": labels[todo_store.AREA_RESEARCH]},
         {"header": f"🏢 {todo_store.AREA_WORK}",
          "items": labels[todo_store.AREA_WORK]}],
        multi_containers=True, direction="vertical", key="todo_drag")

    if st.button("💾 순서 저장", key="todo_drag_save", type="primary"):
        ordered = []
        for cont in res:
            area = (todo_store.AREA_RESEARCH
                    if todo_store.AREA_RESEARCH in cont["header"]
                    else todo_store.AREA_WORK)
            for idx, tag in enumerate(cont["items"], start=1):
                p = back.get(tag)
                if p:
                    ordered.append((p["_row"], area, idx))
        try:
            todo_store.reorder(uid, ordered)
            st.session_state["todo_sort_mode"] = False
            st.toast("↕ 순서를 저장했습니다.")
        except Exception as e:
            st.error(f"저장 실패: {e}")
        st.rerun()


def _todo_row(p, uid, today, no=None):
    """업무 할 일 한 줄 — 번호·내용·배지 + ☆(중요) + ✓(완료). 두 목록 공용."""
    star = bool((p.get("중요", "") or "").strip())
    c1, cs, c3 = st.columns([9, 1, 1])
    _head = f"{no}." if no else "-"
    c1.markdown(f"{_head} {'⭐' if star else '📝'} {p['내용']}"
                + _todo_badges(p, today), unsafe_allow_html=True)
    if cs.button("☆" if not star else "★", key=f"todo_star_{p['_row']}",
                 help="중요 표시(맨 위로)"):
        try:
            todo_store.set_star(uid, p["_row"], p["내용"], not star)
        except Exception as e:
            st.error(f"저장 실패: {e}")
        st.rerun()
    if c3.button("✓", key=f"todo_done_{p['_row']}",
                 help="완료 — 주간보고 실적에 넣을 수 있게 기록됨"):
        try:
            todo_store.complete_todo(uid, p["_row"], p["내용"])
        except Exception as e:
            st.error(f"완료 처리 실패: {e}")
        st.rerun()


def _hm(ts: str) -> str:
    """'2026-07-30 09:12' → '7/30 09:12' (오늘이면 '09:12'). 빈 값은 그대로."""
    ts = (ts or "").strip()
    if len(ts) < 16:
        return ts
    d, t = ts[:10], ts[11:16]
    try:
        if d == datetime.now(KST).strftime("%Y-%m-%d"):
            return t
    except Exception:
        pass
    return f"{int(d[5:7])}/{int(d[8:10])} {t}"


def home_page():
    """홈 대시보드 — 상단(나는 누구·공지·오늘 챙길 것·내 할 일) → 일정 달력 → 바로가기(작게) → 뉴스."""
    today = datetime.now(KST).date()
    now = datetime.now(KST)
    week = this_wednesday()
    # 다크에선 글자색을 낮추고 그림자(번짐)를 없앰 — 어두운 배경에서 발광해 보임
    _dk = bool(st.session_state.get("dark"))
    _ttl_c = "#c3bfb7" if _dk else "#C4622D"
    _ttl_sh = "none" if _dk else "0 2px 6px rgba(196,98,45,.20)"
    st.markdown(
        "<style>@import url('https://fonts.googleapis.com/css2?"
        "family=Dancing+Script:wght@700&display=swap');</style>"
        "<div style='text-align:center;margin:2px 0 12px;'>"
        "<span style=\"font-family:'Dancing Script','Brush Script MT',cursive;"
        f"font-weight:700;font-size:clamp(2.3rem,8vw,3.9rem);color:{_ttl_c};"
        f"line-height:1.05;text-shadow:{_ttl_sh};\">"
        "Dolbom Studio</span></div>",
        unsafe_allow_html=True)

    # 홈 전용 컴팩트 스타일(폰트·여백 축소). 다른 페이지엔 주입 안 됨(홈 렌더 시에만).
    # ⚠ 본문(stMain)으로 한정 — 전역으로 두면 사이드바 간격까지 줄어 브랜드와
    #    다크모드 토글이 겹친다.
    st.markdown("""<style>
      section[data-testid="stMain"] [data-testid="stMetricValue"]{font-size:1.45rem;}
      section[data-testid="stMain"] [data-testid="stMetricLabel"] p{font-size:0.7rem;}
      section[data-testid="stMain"] div[data-testid="stVerticalBlock"]{gap:0.3rem;}
      /* 목록·안내문 여백 — 너무 붙지도, 벌어지지도 않게 */
      section[data-testid="stMain"] [data-testid="stMarkdownContainer"] ul{
        margin:0; padding-left:1.1rem; }
      section[data-testid="stMain"] [data-testid="stMarkdownContainer"] li{
        margin:0 0 7px; }
      /* ✓ 버튼이 있는 줄(st.columns)은 버튼 높이 때문에 조금 더 벌어진다.
         버튼 없는 줄(달력·시스템 할 일)의 여백을 맞춰 목록 전체를 고르게. */
      section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]{
        margin-bottom:1px; }
      section[data-testid="stMain"] [data-testid="stCaptionContainer"]{
        margin:0 0 2px; }
      /* ＋(추가) 버튼을 확장패널 제목줄 오른쪽에 올린다.
         st.expander 헤더에는 위젯을 못 넣고, 컬럼으로 나누면 그 안의 목록
         행 컬럼이 3단 중첩이 되어 Streamlit 예외가 난다 → 겹쳐 배치. */
      section[data-testid="stMain"] [data-testid="stExpander"]{ position:relative; }
      section[data-testid="stMain"] [class*="st-key-todo_add_btn"],
      section[data-testid="stMain"] [class*="st-key-care_add_btn"],
      section[data-testid="stMain"] [class*="st-key-per_add_btn"]{
        /* 머리글 높이 ~40px, 버튼 22px → 위아래 가운데는 9px */
        position:absolute; top:9px; width:auto !important; z-index:5; }
      /* 제목 길이가 달라 섹션마다 왼쪽 위치를 따로 준다(제목에서 약 10px 뒤) */
      section[data-testid="stMain"] [class*="st-key-care_add_btn"]{ left:129px; }
      section[data-testid="stMain"] [class*="st-key-todo_add_btn"]{ left:111px; }
      section[data-testid="stMain"] [class*="st-key-per_add_btn"]{ left:104px; }
      section[data-testid="stMain"] [class*="st-key-todo_sort_btn"]{
        position:absolute; top:9px; left:135px; width:auto !important; z-index:5; }
      /* 테두리·배경 없는 아이콘으로(사업단 일정의 ＋와 같은 모양) */
      section[data-testid="stMain"] [class*="st-key-todo_add_btn"] button,
      section[data-testid="stMain"] [class*="st-key-care_add_btn"] button,
      section[data-testid="stMain"] [class*="st-key-per_add_btn"] button,
      section[data-testid="stMain"] [class*="st-key-todo_sort_btn"] button{
        min-height:0 !important; height:22px; padding:0 0.25rem !important;
        font-size:1.15rem; line-height:1; font-weight:700;
        background:transparent !important; border:none !important;
        box-shadow:none !important; color:#C4622D !important; }
      section[data-testid="stMain"] [class*="st-key-todo_add_btn"] button:hover,
      section[data-testid="stMain"] [class*="st-key-care_add_btn"] button:hover,
      section[data-testid="stMain"] [class*="st-key-per_add_btn"] button:hover,
      section[data-testid="stMain"] [class*="st-key-todo_sort_btn"] button:hover{
        background:transparent !important; border:none !important;
        color:#A8501A !important; }
      /* 항목 옆 작은 아이콘 버튼(✓·🙋·🏢·✎·✕): 기본 높이(38px)가 커서 줄간격이
         벌어짐 → 낮춰서 글자 줄과 비슷하게 맞춤. 기호는 이모지가 아닌 글자라
         CSS 색이 먹는다(이모지는 폰트가 그림을 그려 흰 박스로 보였음). */
      [class*="st-key-todo_done_"] button, [class*="st-key-per_done_"] button,
      [class*="st-key-care_done_"] button, [class*="st-key-req_done_"] button,
      [class*="st-key-req_del_"] button, [class*="st-key-req_edit_btn_"] button,
      [class*="st-key-req_reply_"] button, [class*="st-key-todo_star_"] button{
        min-height:0 !important; height:26px; padding:0 0.45rem !important;
        line-height:1; }
      /* ☆/★ 는 글자 기호라 크기·굵기를 맞춰야 ✓ 버튼과 나란해 보인다 */
      [class*="st-key-todo_star_"] button p{
        font-size:1.05rem !important; line-height:1 !important; margin:0; }
      section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]{gap:0.55rem;}
      section[data-testid="stMain"] div[data-testid="stAlert"]{padding:0.4rem 0.65rem;}
      section[data-testid="stMain"] div[data-testid="stAlert"] p{font-size:0.85rem;margin:0;}
      section[data-testid="stMain"] div[data-testid="stAlert"] a{font-size:0.85rem;}
      /* 구분선 아래는 넉넉히 — 바로 밑에 오는 테두리 상자(확장패널)가
         선에 걸쳐 보이지 않게. 양쪽 컬럼에 공통으로 적용됨. */
      section[data-testid="stMain"] hr{margin:0.45rem 0 1rem;}
      section[data-testid="stMain"] div.stButton>button{padding:0.25rem 0.5rem;}
      /* ⚡ 바로가기 — 순수 HTML 타일 그리드(네이버식): 이모지 크게·박스 작게·라벨 밑·간격 촘촘 */
      .dsbar{ display:flex; flex-wrap:wrap; gap:9px 18px; align-items:flex-start;
              justify-content:center; margin-bottom:12px; }
      .dsbar .dstile{ width:56px; text-decoration:none; text-align:center; }
      .dsbar .dstile .ic{ display:flex; align-items:center; justify-content:center;
        width:52px; height:44px; margin:0 auto; font-size:1.95rem; line-height:1;
        border:1px solid #E3C6A6; border-radius:13px; background:#FCF3EA; }
      .dsbar .dstile:hover .ic{ border-color:#C4622D; background:#FCEEE1; }
      .dsbar .dstile .ic svg{ display:block; width:30px; height:30px; }
      .dsbar .dstile .lb{ display:block; margin-top:5px; font-size:0.72rem;
        color:#8A5A2B !important; line-height:1.15; }
      /* '나는 누구' 선택박스: 타일+라벨 높이(62px)·이름 세로/가로 중앙·적당한 크기 */
      .st-key-me_widget div[data-baseweb="select"]>div{
        min-height:62px; display:flex; align-items:center; justify-content:center; }
      .st-key-me_widget div[data-baseweb="select"] div[value],
      .st-key-me_widget div[data-baseweb="select"] input{
        font-size:1.1rem; text-align:center; }
      /* 사업단 일정 제목 옆 ➕ 버튼: 테두리·배경 없는 주황 아이콘 */
      .st-key-home_cal_open_btn button{ min-height:0; padding:0 0.35rem;
        border:none !important; background:transparent !important; box-shadow:none;
        color:#C4622D !important; font-size:1.25rem; line-height:1; }
      .st-key-home_cal_open_btn button:hover{ color:#A8501A !important;
        background:transparent !important; border:none !important; }
    </style>""", unsafe_allow_html=True)

    # 다크모드일 때 바로가기 라벨(진갈색 #8A5A2B)이 배경에 묻혀 안 보임 → 밝은 톤으로.
    # 이 홈 CSS가 전역 다크 CSS보다 나중에 주입돼 덮어써지지 않으므로 여기서 처리.
    if st.session_state.get("dark"):
        # 크림색 타일(#FCF3EA)이 어두운 배경에서 8개나 빛나 눈이 부심 → 어둡게
        # 어두운 배경에선 '밝은 사각형 10개 + 채도 높은 이모지'가 가장 눈부시다.
        # → 타일 면을 없애고(테두리만) 이모지 채도·밝기를 낮춘다.
        st.markdown("""<style>
          .dsbar .dstile .lb{ color:#f0eee9 !important; }
          .dsbar .dstile .ic{ background:transparent !important;
            border-color:#333331 !important;
            filter:saturate(.95) brightness(1.02); }
          .dsbar .dstile:hover .ic{ background:#1d1d1c !important;
            border-color:#5c5c57 !important; filter:none; }
          .dsbar .dstile:hover .lb{ color:#ffffff !important; }
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
        ("🖥️", "주간취합", "🖥️ 주간취합"),
        ("📝", "주간보고", "📝 업무보고 작성·취합"),
        ("🛒", "구매요청", "🛒 구매요청서"),
        ("📋", "문서협업", "📋 문서 협업"),
        ("📍", "방문일지", "📍 실증 방문 일지"),
        ("🏠", "스페이스", "🏠 스마트돌봄스페이스"),
        ("🔧", "장비현황", "🔧 장비 사용현황"),
        ("💡", "개선요청", "💡 개선 요청"),
    ]

    # ── ⚡ 바로가기 (전폭 중앙정렬). 로그인한 계정 유지용 uid·tok을 링크에 담음 ──
    _uid = st.session_state.get("uid", "")
    _tok = st.session_state.get("tok", "")
    _base = f"uid={quote(_uid)}&tok={quote(_tok)}"
    _tiles = [("📌", "공지등록", "notice")] + list(shortcuts)
    # (아이콘HTML, 라벨, 링크, target) — 내부 이동은 _self, 외부(줌)는 새 탭
    _items = [(_e, _l, f"?{_base}&go={quote(_key)}", "_self")
              for _e, _l, _key in _tiles]
    # 🎥 줌 회의 — 회의 진행 모드에 저장해 둔 팀 공용 링크로 바로 접속.
    #   링크가 저장돼 있을 때만 타일이 보인다(빈 링크 클릭 방지). 위치는 회의진행 옆.
    _at = next((i for i, _it in enumerate(_items) if _it[1] == "주간취합"),
               len(_items) - 1)
    for _zn, _zu in reversed(zoom_links()):      # 주간취합 바로 뒤에 순서대로
        _items.insert(_at + 1, (_ZOOM_SVG, _zn,
                                html_escape(_zu, quote=True), "_blank"))
    _html = '<div class="dsbar">'
    for _ic, _l, _href, _tgt in _items:
        _rel = ' rel="noopener"' if _tgt == "_blank" else ""
        _html += (f'<a class="dstile" href="{_href}" target="{_tgt}"{_rel}>'
                  f'<span class="ic">{_ic}</span>'
                  f'<span class="lb">{_l}</span></a>')
    _html += "</div>"
    st.markdown(_html, unsafe_allow_html=True)

    # 📌 공지사항 — 표시 + 등록/관리 토글(바로가기 첫 타일)
    for _idx, r in sorted(ntc, key=lambda x: x[0], reverse=True):
        if is_expired(r, today_str):
            continue  # 만료일 지난 공지는 숨김(정리 전이어도)
        exp_md = f"　·　🗓️ ~{r[3]}까지" if r[3].strip() else ""
        _rd = notice_readers(r)
        _cnt = f"　·　✅ 확인 {len(_rd)}명" if _rd else ""
        st.info(f"📌 **{r[2]}**　—　{r[1]} · {r[0]}{exp_md}{_cnt}")
        # 확인(읽음) 체크 — 본인이 아직 확인 안 했으면 버튼, 했으면 표시
        if my:
            _c1, _c2 = st.columns([1, 5])
            if my in _rd:
                _c1.caption("✅ 확인함")
            elif _c1.button("✅ 확인", key=f"ntc_read_{_idx}",
                            help="이 공지를 확인했다고 표시합니다"):
                try:
                    mark_notice_read(_idx, r[0], my)
                except Exception as e:
                    st.warning(str(e))
                st.rerun()
            if _rd:
                _miss = [n for n in MEMBER_NAMES if n not in _rd]
                _c2.caption("확인: " + ", ".join(_rd)
                            + (f"　|　미확인: {', '.join(_miss)}" if _miss else "　|　전원 확인 🎉"))
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

    # 📌 공지 등록/관리 패널 (열기=바로가기 📌공지등록 타일 / 닫기=아래 ✖ 버튼)
    if st.session_state.get("home_notice_open"):
        with st.container(border=True):
            _nh1, _nh2 = st.columns([6, 1])
            _nh1.markdown("**📌 공지 등록 / 관리**")
            if _nh2.button("✖ 닫기", key="notice_close"):
                st.session_state["home_notice_open"] = False
                st.rerun()
            _notice_manage()

    # 데이터 계산: 오늘 챙길 것(my 무관) + 할일·일정(my 필요)
    my = st.session_state.get("me")
    todos, sched_items, common_sched_items = [], [], []
    today_mine = []          # 오늘(D-0) 내 일정 — '오늘 챙길 것'에 올림
    if my:
        # 주간보고 미제출은 '오늘 챙길 것'에서 마감일(화)에만 알린다 — 할 일
        # 목록에 상시로 두면 매일 보이는 잔소리가 된다.
        for r in active_collab:
            assignees = [x.strip() for x in r[7].split(",")
                         if x.strip() and x.strip() != "전체"]
            doners = [x.strip() for x in r[8].split(",")]
            if my in assignees and my not in doners:
                todos.append(f"📋 문서협업 '{r[3]}' — 내 부분 미완료")
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
                    # 오른쪽 칸이 좁아 줄이 접히므로 최대한 짧게:
                    #   0 안 붙인 날짜, 종일이면 '종일' 표기 생략(제목만)
                    md = f"{int(v['date'][5:7])}/{int(v['date'][8:10])}"
                    tm = "" if v["when"] == "종일" else v["when"].split("~")[0]
                    line = f"{md} {tm} · {v['title']}" if tm                         else f"{md} · {v['title']}"
                    if my in haystack:
                        sched_items.append(line)
                        # 오늘 것은 '오늘 챙길 것'에도 올린다(조퇴·출장 등을 놓치지 않게)
                        if v["date"] == today_str:
                            today_mine.append(
                                f"{tm} · {v['title']}"
                                + (f" ({v['location']})"
                                   if (v.get("location") or "").strip() else ""))
                    else:   # 내 것 외에는 이름 구분 없이 전부 '그 외 일정'으로
                        common_sched_items.append(line)
            except Exception:
                sched_items, common_sched_items, today_mine = [], [], []

    st.divider()
    # ── 좌: 오늘 챙길 것 + 내 할 일(7일) / 우: 그 외 일정(7일) ─────────────
    left, right = st.columns([1.45, 1])  # 왼쪽 글이 길어 조금 더 넓게
    with left:
        uid = st.session_state.get("uid", "")
        _auto_import(uid, my)   # 보고(번호줄)·내 메일을 새 것만 자동 추가(세션당 1회)
        # 오른쪽 컬럼과 같은 st.expander 로 통일(내용이 상자 안에 들어가고
        # 새로고침 없이 즉시 접힘). ＋ 는 상자 안 첫 줄 버튼으로 옮김.
        any_reminder = False
        _mycare = []
        with st.expander("🔔 오늘 챙길 것", expanded=True):
            if uid and st.button(
                    "－" if st.session_state.get("care_add_open") else "＋",
                    key="care_add_btn",
                    help="닫기" if st.session_state.get("care_add_open")
                    else "오늘 챙길 것 추가(나만 보임)"):
                st.session_state["care_add_open"] =                     not st.session_state.get("care_add_open", False)
                st.rerun()
            if st.session_state.get("care_add_open") and uid:
                with st.form("care_add_form", clear_on_submit=True):
                    _ct = st.text_input("오늘 챙길 것 (나만 보임)", key="care_text",
                                        placeholder="예: 회의 자료 인쇄")
                    if st.form_submit_button("추가") and _ct.strip():
                        try:
                            todo_store.add_todo(uid, _ct, todo_store.KIND_CARE)
                            st.session_state["care_add_open"] = False
                        except Exception as e:
                            st.error(f"저장 실패: {e}")
                        st.rerun()
            # 📅 오늘 내 일정(연가·조퇴·출장·회의 등) — 오늘 챙길 것의 첫 항목
            for _tmine in today_mine:
                st.info(f"📅 오늘 · {_tmine}")
                any_reminder = True
            if missing:
                wed_dt = datetime.strptime(week, "%Y-%m-%d").replace(tzinfo=KST)
                deadline = (wed_dt - timedelta(days=1)).replace(hour=17, minute=0)
                delta = deadline - now
                overdue = delta.total_seconds() < 0
                # 마감일(화요일)에만 알린다 — 매일 띄우면 무뎌진다
                if today.weekday() == 1:
                    if overdue:
                        dtxt = "🔴 마감 지남 (화 17시)"
                    else:
                        dtxt = (f"⏰ 오늘 마감! (화 17시·"
                                f"{max(0, int(delta.total_seconds() // 3600))}"
                                "시간 남음)")
                    st.warning(f"📝 주간보고 {dtxt} · 미제출 {len(missing)}명 — "
                               f"{', '.join(missing)}")
                    any_reminder = True
            for r in active_collab:
                dl = _pdate(r[6])
                if dl is None:
                    continue
                if dl < today or (dl - today).days <= 1:   # 마감 지남 + D-0·D-1만
                    tag = "🔴 마감 지남" if dl < today else f"🟡 D-{(dl - today).days}"
                    st.warning(f"📋 문서협업 '{r[3]}' {tag} (마감 {r[6]})")
                    any_reminder = True
            # 📨 내가 보낸 요청의 결과(완료·회신) 알림 — 확인 누르면 사라짐
            try:
                _upd = request_store.updates_for(my) if my else []
            except Exception:
                _upd = []
            for _u in _upd:
                _urp = (_u.get("회신", "") or "").strip()
                _udone = _u["상태"].strip() == request_store.ST_DONE
                _uwhen = _hm(_u["완료일시"] if _udone else _u.get("회신일시", ""))
                _umsg = (f"✅ **{_u['대상']}** 님이 완료: {_u['내용']}"
                         if _udone else f"💬 **{_u['대상']}** 님 회신: {_urp}")
                if _uwhen:
                    _umsg += f"  ({_uwhen})"
                if _udone and _urp:
                    _umsg += f"  \n💬 {_urp}"
                _uc1, _uc2 = st.columns([8, 1])
                # ⚠ 삼항식으로 쓰면 Streamlit '매직'이 그 반환값(DeltaGenerator)을
                #   화면에 덤프한다 → 반드시 if/else 문으로 호출할 것.
                if _udone:
                    _uc1.success(_umsg)
                else:
                    _uc1.info(_umsg)
                if _uc2.button("확인", key=f"req_ack_{_u['_row']}",
                               help="확인했습니다(알림 지우기)"):
                    try:
                        request_store.ack_request(_u["요청ID"], my)
                    except Exception as e:
                        st.error(f"확인 실패: {e}")
                    st.rerun()
                any_reminder = True

            # ⚠️ 취합본을 만든 뒤에 보고를 고친 사람 — 받아둔 파일이 옛 것이 되므로 알림.
            #   제출시간·생성시각 모두 'YYYY-MM-DD HH:MM'이라 문자열 비교로 시간순 판정.
            try:
                _exp_at = todo_store.get_sync("_team", f"export_{week}")
                _stale = ([s["name"] for s in status
                           if (s["submitted_at"] or "") > _exp_at] if _exp_at else [])
            except Exception:
                _exp_at, _stale = "", []
            if _stale:
                st.warning(
                    f"🗂️ 취합본({_exp_at}) 생성 후 수정: {', '.join(_stale)} — "
                    "회의 전 **다시 생성**하세요 (📝 업무보고 작성·취합)")
                any_reminder = True
            # 개인 '오늘 챙길 것'(본인만) — 각 항목 옆 완료(삭제) 버튼
            try:
                _mycare = todo_store.list_todos(uid, todo_store.KIND_CARE)
            except Exception:
                _mycare = []
            for _c in _mycare:
                _cc1, _cc2 = st.columns([8, 1])
                _cc1.markdown(f"📌 {_c['내용']}")
                if _cc2.button("✓", key=f"care_done_{_c['_row']}", help="완료(삭제)"):
                    try:
                        todo_store.delete_todo(uid, _c["_row"], _c["내용"])
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")
                    st.rerun()
            if not any_reminder and not _mycare:
                st.caption("✅ 급히 챙길 건 없습니다.")

        # 내 할 일(7일): 주간보고·문서협업 + 내 이름 붙은 7일 내 일정 + 개인 메모(+)
        # 제목('내 할 일 — 이름')은 없앰 — 업무/개인 머리글만으로 충분.
        # ＋(추가)는 아래 '🏢 업무' 머리글 옆으로 이동.
        _todo_open = st.session_state.get("todo_add_open", False)
        if not my:
            st.caption("로그인 계정에 이름이 없습니다. 관리자에게 문의하세요.")
        else:
            todo_lines = list(todos) + [f"📅 {s}" for s in sched_items]
            try:
                _mytodos = todo_store.list_todos(uid)                      # 업무
            except Exception:
                _mytodos = []
            _myper = personal_todos(uid)        # 개인 = 브라우저에만 저장
            # 예전에 시트에 저장된 개인 할 일이 남아 있으면 옮길 수 있게 안내
            try:
                _old_per = todo_store.list_todos(uid, todo_store.KIND_PERSONAL)
            except Exception:
                _old_per = []
            # 🔀 옮기기 모드 — 평소엔 ✓만 보이고, 켤 때만 업무↔개인 이동 버튼 노출
            # 오른쪽 컬럼과 같은 st.expander. 추가는 ＋ 버튼 하나로.
            # (마감일은 추가할 때 함께 입력 — 목록에서 고치는 '편집 모드'는 없앴다)
            with st.expander(f"🏢 업무 ({len(todo_lines) + len(_mytodos)})",
                             expanded=True):
                if uid and st.button("－" if _todo_open else "＋",
                                     key="todo_add_btn",
                                     help="닫기" if _todo_open
                                     else "할 일 추가(마감일도 함께 입력)"):
                    st.session_state["todo_add_open"] = not _todo_open
                    st.rerun()
                if _todo_open:
                    with st.form("todo_add_form", clear_on_submit=True):
                        _tt = st.text_input("할 일 (나만 보임)", key="todo_text",
                                            placeholder="예: 백정은 님께 자료 요청")
                        _tarea = st.radio(
                            "영역", [todo_store.AREA_RESEARCH,
                                     todo_store.AREA_WORK],
                            index=1, horizontal=True, key="todo_area_new",
                            help="주간보고의 연구/업무와 같은 구분입니다.")
                        _tdue = st.date_input("마감일 (선택)", value=None,
                                              key="todo_due_new",
                                              format="YYYY-MM-DD")
                        # 구분 선택은 없앰 — 개인은 아래 '🙋 개인'에서 따로 추가한다
                        st.caption("팀 시트에 저장됩니다. 남에게 안 보일 메모는 "
                                   "아래 **🙋 개인**에서 추가하세요.")
                        if st.form_submit_button("추가") and _tt.strip():
                            try:
                                todo_store.add_todo(
                                    uid, _tt, todo_store.KIND_TODO,
                                    due=_tdue.strftime("%Y-%m-%d") if _tdue else "",
                                    area=_tarea)
                                st.session_state["todo_add_open"] = False  # 추가 후 닫기
                            except Exception as e:
                                st.error(f"저장 실패: {e}")
                            st.rerun()
                # 시스템 할 일(주간보고·협업·일정)은 업무 쪽에 둔다
                if todo_lines:
                    st.markdown("\n".join(f"- {t}" for t in todo_lines))
                # 주간보고와 같은 구분으로 나눠 보여준다(영역 빈칸 = 옛 데이터 = 업무)
                _by_area = {todo_store.AREA_RESEARCH: [],
                            todo_store.AREA_WORK: []}
                for _p in _mytodos:
                    _a = (_p.get("영역", "") or "").strip()
                    _by_area.setdefault(
                        _a if _a in _by_area else todo_store.AREA_WORK,
                        []).append(_p)
                # ↕ 정렬(드래그) 모드 — 켜면 두 칸 사이로 끌어 옮기고 순서도 바꾼다
                _sortable = _drag_available()
                if _mytodos and _sortable and st.button(
                        "✓" if st.session_state.get("todo_sort_mode") else "↕",
                        key="todo_sort_btn",
                        help="정렬 끝내기"
                        if st.session_state.get("todo_sort_mode")
                        else "순서 바꾸기(끌어서 이동)"):
                    st.session_state["todo_sort_mode"] = \
                        not st.session_state.get("todo_sort_mode", False)
                    st.rerun()
                if _mytodos and _sortable and st.session_state.get(
                        "todo_sort_mode"):
                    _drag_sort(_by_area, uid, today)
                else:
                    for _label, _icon in ((todo_store.AREA_RESEARCH, "🔬"),
                                          (todo_store.AREA_WORK, "🏢")):
                        _items = _by_area.get(_label, [])
                        if not _items and not (
                                _label == todo_store.AREA_WORK and todo_lines):
                            continue
                        st.markdown(f"**{_icon} {_label}**")
                        # 시스템이 만든 알림(주간보고 미제출·협업 마감·내 일정)은
                        # 업무 성격이라 업무 머리글 아래에 붙인다.
                        if _label == todo_store.AREA_WORK and todo_lines:
                            st.markdown("\n".join(f"- {t}" for t in todo_lines))
                        for _i, _p in enumerate(
                                sorted(_items,
                                       key=lambda x: _todo_sort_key(x, today)),
                                start=1):
                            _todo_row(_p, uid, today, no=_i)
            # 🙋 개인: 업무와 분리해서 표시. 비어 있어도 열어둔다(여기서 바로 추가).
            if uid:
                # 옮기기 모드는 위 '🏢 업무' 머리글의 🔀로 켠다(항상 보임).
                with st.expander(f"🙋 개인 ({len(_myper)})", expanded=True):
                    if st.button(
                            "－" if st.session_state.get("per_add_open")
                            else "＋", key="per_add_btn",
                            help="닫기" if st.session_state.get("per_add_open")
                            else "개인 할 일 추가(내 기기에만 저장)"):
                        st.session_state["per_add_open"] = \
                            not st.session_state.get("per_add_open", False)
                        st.rerun()
                    if st.session_state.get("per_add_open"):
                        with st.form("per_add_form", clear_on_submit=True):
                            _pt = st.text_input("개인 할 일 (나만 보임)",
                                                key="per_text",
                                                placeholder="예: 병원 예약 확인")
                            if st.form_submit_button("추가") and _pt.strip():
                                save_personal(uid, _myper + [{
                                    "t": _pt.strip(),
                                    "ts": datetime.now(KST).strftime(
                                        "%Y-%m-%d %H:%M")}])
                                st.session_state["per_add_open"] = False
                                st.rerun()
                    st.caption("🔒 이 목록은 **내 기기(브라우저)에만** 저장됩니다 — "
                               "팀 시트로 나가지 않습니다. (기기마다 따로 저장)")
                    for _i, _p in enumerate(_myper):
                        _pc1, _pc3 = st.columns([10, 1])
                        _pc1.markdown(f"- 🏠 {_p.get('t', '')}")
                        if _pc3.button("✓", key=f"per_done_{_i}",
                                       help="완료(삭제) — 기록에 남지 않음"):
                            save_personal(uid, [q for j, q in enumerate(_myper)
                                                if j != _i])
                            st.rerun()
            # 옛 개인 할 일이 팀 시트에 남아 있으면 내 기기로 옮길 수 있게 안내.
            # (자동으로 지우지 않는다 — 삭제는 되돌릴 수 없으므로 직접 누르게)
            if _old_per:
                st.warning(f"🔒 예전에 저장한 개인 할 일 {len(_old_per)}건이 "
                           "**팀 시트에 남아 있습니다**(시트를 열 수 있는 사람에게 보임).")
                if st.button("내 기기로 옮기고 시트에서 지우기", key="per_migrate"):
                    try:
                        _now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
                        save_personal(uid, _myper + [
                            {"t": r["내용"], "ts": r.get("등록일시") or _now}
                            for r in _old_per])
                        for r in _old_per:
                            todo_store.delete_todo(uid, r["_row"], r["내용"])
                        st.toast("🔒 개인 할 일을 내 기기로 옮겼습니다.")
                    except Exception as e:
                        st.error(f"옮기기 실패: {e}")
                    st.rerun()
            if not todo_lines and not _mytodos and not _myper:
                st.caption(f"✅ {my} 님, 7일 내 할 일이 없습니다.")
            # 📨 받은 요청 — 다른 팀원이 나(my)에게 요청한 일
            try:
                _reqs = request_store.open_for(my)
            except Exception:
                _reqs = []
            if _reqs:
                with st.expander(f"📨 받은 요청 ({len(_reqs)})", expanded=True):
                    for _rq in _reqs:
                        _rc1, _rc2, _rc3 = st.columns([8, 1, 1])
                        _rlk = (_rq.get("링크", "") or "").strip()
                        _rrp = (_rq.get("회신", "") or "").strip()
                        _rc1.markdown(
                            f"- 📨 {_rq['내용']}"
                            + (f" [🔗 열기]({_rlk})" if _rlk else "")
                            + f"  \n  <span style='opacity:.85;font-size:.88em'>"
                              f"— {_rq['요청자']} 요청 ({_hm(_rq['등록일시'])})"
                            + (f" · 내 회신: {_rrp}"
                               + (f" ({_hm(_rq.get('회신일시', ''))})"
                                  if (_rq.get('회신일시') or '').strip() else "")
                               if _rrp else "")
                            # 같은 요청을 받은 다른 사람들의 응답도 함께 보여준다
                            # (지금까지는 요청자만 볼 수 있었음)
                            + _req_peers(_rq, my) + "</span>",
                            unsafe_allow_html=True)
                        # 💬 한 줄 회신 — 완료 말고 상황만 알릴 때(예: "8/5까지 드릴게요")
                        _rkey = f"reply_open_{_rq['_row']}"
                        if _rc2.button("💬", key=f"req_reply_{_rq['_row']}",
                                       help="한 줄 회신 보내기"):
                            st.session_state[_rkey] = not st.session_state.get(_rkey)
                            st.rerun()
                        if _rc3.button("✓", key=f"req_done_{_rq['_row']}",
                                       help="완료 처리(요청자에게 표시됨)"):
                            try:
                                request_store.complete_request(
                                    _rq["요청ID"], my, _rq["내용"])
                            except Exception as e:
                                st.error(f"완료 처리 실패: {e}")
                            st.rerun()
                        if st.session_state.get(_rkey):
                            _rt = st.text_input(
                                "회신", value=_rrp, key=f"reply_txt_{_rq['_row']}",
                                placeholder="예: 8/5까지 드릴게요",
                                label_visibility="collapsed")
                            if st.button("보내기", key=f"reply_send_{_rq['_row']}"):
                                try:
                                    request_store.set_reply(_rq["요청ID"], _rt)
                                    st.session_state[_rkey] = False
                                except Exception as e:
                                    st.error(f"회신 실패: {e}")
                                st.rerun()
            # (요청 보내기 폼은 오른쪽 컬럼 '정보 미입력 일정' 아래에 있음 — 좌우 균형)
    with right:
        # (이전엔 왼쪽이 글자 제목이라 오른쪽만 9px 내렸는데, 지금은 양쪽 다
        #  확장패널로 시작하므로 보정이 필요 없다 — 넣으면 왼쪽이 위로 올라가 보임)
        if common_sched_items:
            with st.expander(f"🗓️ 그 외 일정 (7일) — {len(common_sched_items)}건",
                             expanded=False):
                st.markdown("\n".join(f"- {s}" for s in common_sched_items))
        else:
            st.markdown("**🗓️ 그 외 일정 (7일)**")
            st.caption("7일 내 다른 일정이 없습니다.")

        # 📍 정보 미입력 일정: 14일 내 일정 중 장소·시간이 빈 것 (사업단 일정 ＋에서 보완)
        #   연가·조퇴 등 근태는 장소·시간이 필요 없어 제외.
        _SKIP_WORDS = ("연가", "조퇴", "반차", "반가", "휴가", "외출", "월차", "연차")
        try:
            _miss = []
            for _e in upcoming_events(days=14, maxn=50):
                _vv = event_view(_e)
                _dd = _pdate(_vv["date"])
                if _dd is None or _dd < today:
                    continue
                if any(_w in _vv["title"] for _w in _SKIP_WORDS):
                    continue
                _m = []
                if not (_vv.get("location") or "").strip():
                    _m.append("장소")
                if _vv["all_day"]:
                    _m.append("시간")
                if _m:
                    _miss.append((_vv, _m))
        except Exception:
            _miss = []
        if _miss:
            with st.expander(f"📍 정보 미입력 일정 ({len(_miss)})", expanded=False):
                for _vv, _m in _miss:
                    st.markdown(
                        f"- {_vv['date'][5:].replace('-', '/')} · {_vv['title']} "
                        f"— {'·'.join(_m)} 없음")
                st.caption("‘📅 사업단 일정 ＋’에서 해당 일정을 열어 채워주세요.")

        # 📨 팀원에게 요청하기 + 내가 보낸 요청 현황
        #   (받은 요청은 왼쪽 '내 할 일'에 — 내가 할 일이므로. 여기엔 보내는 쪽만)
        if my:
            # 제목의 (N) = 내가 보낸 요청 건수(같은 내용·시각으로 묶은 단위).
            # 다른 확장패널처럼 개수를 보여주려 미리 세어 둔다.
            try:
                _sent_pre = request_store.sent_by(my)
            except Exception:
                _sent_pre = []
            _nsent = len({(r["내용"], r["등록일시"]) for r in _sent_pre})
            with st.expander(f"📨 팀원에게 요청하기 ({_nsent})", expanded=False):
                # 고르는 명단엔 간부(과장·연구관·연구사)도 포함, 없는 사람은 직접 입력
                _others = [n for n in USER_NAMES if n != my]
                _researchers = [n for n in MEMBER_NAMES if n != my]
                with st.form("req_add_form", clear_on_submit=True):
                    # 여러 명 선택 가능 — 사람마다 따로 완료·회신이 오간다
                    _rtargets = st.multiselect(
                        "요청 대상 (여러 명 선택 가능)", _others, key="req_target",
                        placeholder="이름을 고르세요")
                    _rall = st.checkbox("연구원 전체에게 보내기", key="req_all",
                                        help=f"연구원 {len(_researchers)}명(나 제외)")
                    _rmanual = st.text_input(
                        "직접 입력 (선택)", key="req_manual",
                        placeholder="명단에 없는 사람 · 여러 명은 쉼표로",
                        help="예: 홍길동, 김철수")
                    _rtext = st.text_input(
                        "요청 내용", key="req_text",
                        placeholder="예: 센서 데이터 공유해주세요")
                    _rlink = st.text_input(
                        "관련 링크 (선택)", key="req_link",
                        placeholder="예: 구글문서·시트 주소 (문서 작성 요청 시)",
                        help="여러 명이 나눠 쓰는 문서는 '📋 문서 협업'을 쓰세요.")
                    if st.form_submit_button("보내기"):
                        # 연구원전체 + 고른 사람 + 직접 입력 → 중복 제거(순서 유지)
                        _tg, _seen = [], set()
                        for _n in ((_researchers if _rall else []) + _rtargets
                                   + [x.strip() for x in
                                      (_rmanual or "").replace("·", ",").split(",")]):
                            _n = (_n or "").strip()
                            if _n and _n != my and _n not in _seen:
                                _seen.add(_n)
                                _tg.append(_n)
                        if not _rtext.strip():
                            st.warning("요청 내용을 적어주세요.")
                        elif not _tg:
                            st.warning("받을 사람을 고르거나 직접 입력해 주세요.")
                        else:
                            try:
                                request_store.add_requests(my, _tg, _rtext, _rlink)
                                st.toast(f"📨 {len(_tg)}명에게 요청을 보냈습니다.")
                            except Exception as e:
                                st.error(f"요청 실패: {e}")
                            st.rerun()
                _sent = _sent_pre          # 위에서 개수 세느라 이미 읽음(재조회 불필요)
                if _sent:
                    st.caption("내가 보낸 요청")
                    # 여러 명에게 보낸 건 사람마다 한 행 → (내용+보낸시각)으로 묶어
                    # 한 줄에 진행률로 표시(10명에게 보내도 목록이 길어지지 않게)
                    _groups = {}
                    for _sq in _sent:
                        _groups.setdefault((_sq["내용"], _sq["등록일시"]),
                                           []).append(_sq)
                    for (_gtext, _gtime), _grp in _groups.items():
                        _dones = [g for g in _grp
                                  if g["상태"].strip() == request_store.ST_DONE]
                        _all_done = len(_dones) == len(_grp)
                        _mark = "✅" if _all_done else "⏳"
                        _slk = (_grp[0].get("링크", "") or "").strip()
                        # 회신만 온 사람도 세어 준다 — '0명 완료'만 보이면
                        # 답이 온 걸 놓치기 쉬움(회신 ≠ 완료)
                        _reps = [g for g in _grp
                                 if (g.get("회신", "") or "").strip()
                                 and g["상태"].strip() != request_store.ST_DONE]
                        # '완료 0명, 회신 1명'처럼 0을 같이 쓰면 모순처럼 읽힌다.
                        # → 완료·회신·대기로 나눠 0인 항목은 빼고, 합이 인원과 맞게.
                        if len(_grp) == 1:
                            _who = _grp[0]["대상"]
                        elif _all_done:
                            _who = f"{len(_grp)}명 전원 완료"
                        else:
                            _wait_n = len(_grp) - len(_dones) - len(_reps)
                            _parts = []
                            if _dones:
                                _parts.append(f"완료 {len(_dones)}명")
                            if _reps:
                                _parts.append(f"회신 {len(_reps)}명")
                            if _wait_n:
                                _parts.append(f"대기 {_wait_n}명")
                            # 항목이 하나뿐이면 '대기 12명 (총 12명)'처럼 중복돼 총계 생략
                            _who = " · ".join(_parts) + (
                                f" (총 {len(_grp)}명)" if len(_parts) > 1 else "")
                        # 사람별 상태 — '대기'를 12번 늘어놓으면 읽기 어렵고 회신이
                        # 누구 것인지도 묻힌다. → 응답한 사람만 쓰고 나머지는 숫자로.
                        # 완료 먼저, 그다음 회신 — 시트 순서대로면 뒤죽박죽 보인다.
                        # 대기 인원은 위 요약에 이미 있으므로 여기서 반복하지 않는다.
                        _done_ln, _rep_ln = [], []
                        for g in _grp:
                            _rp = (g.get("회신", "") or "").strip()
                            _rpt = (g.get("회신일시", "") or "").strip()
                            _gd = g["상태"].strip() == request_store.ST_DONE
                            if _gd:
                                # 완료·회신 모두 '이름 · 내용' 형태로 통일
                                _done_ln.append(
                                    f"✅ {g['대상']} 완료 {_hm(g['완료일시'])}"
                                    + (f" · 💬 {_rp}" if _rp else ""))
                            elif _rp:
                                _rep_ln.append(
                                    f"💬 {g['대상']} 회신"
                                    + (f" {_hm(_rpt)}" if _rpt else "")
                                    + f" · {_rp}")
                        _lines = _done_ln + _rep_ln
                        # 가운데 점으로 다 이어 붙이면 문장이 끊긴 것처럼 보여
                        # 항목마다 줄을 나눈다(보낸 시각 → 응답 → 대기).
                        _detail = "<br>".join(
                            [f"보낸 시각 {_hm(_gtime)}"] + _lines)
                        _sc1, _sc2, _sc3 = st.columns([7, 1, 1])
                        _sc1.markdown(
                            f"- {_mark} {_who}: {_gtext}"
                            + (f" [🔗]({_slk})" if _slk else "")
                            + "  \n  <span style='opacity:.85;font-size:.88em'>"
                            + _detail + "</span>",
                            unsafe_allow_html=True)
                        # ✏️ 수정 — 잘못 보냈을 때 내용·링크를 고침(받은 사람 화면에 즉시 반영)
                        _ekey = f"req_edit_{_grp[0]['_row']}"
                        if _sc2.button("✎", key=f"req_edit_btn_{_grp[0]['_row']}",
                                       help="내용 수정(받은 사람 전원에게 반영)"):
                            st.session_state[_ekey] = not st.session_state.get(_ekey)
                            st.rerun()
                        # 🗑 회수 — 받은 사람 목록에서도 사라짐
                        if _sc3.button("✕", key=f"req_del_{_grp[0]['_row']}",
                                       help="회수 — 받은 사람 전원에게서 삭제"):
                            try:
                                for g in _grp:
                                    request_store.delete_request(g["요청ID"], my)
                            except Exception as e:
                                st.error(f"회수 실패: {e}")
                            st.rerun()
                        if st.session_state.get(_ekey):
                            _et = st.text_input(
                                "요청 내용 수정", value=_gtext,
                                key=f"req_et_{_grp[0]['_row']}")
                            _el = st.text_input(
                                "관련 링크", value=_slk,
                                key=f"req_el_{_grp[0]['_row']}")
                            _ec1, _ec2 = st.columns(2)
                            if _ec1.button("저장", key=f"req_esave_{_grp[0]['_row']}"):
                                if not _et.strip():
                                    st.warning("내용을 비울 수 없습니다.")
                                else:
                                    try:
                                        for g in _grp:
                                            request_store.update_request(
                                                g["요청ID"], my, _et, _el)
                                        st.session_state[_ekey] = False
                                        st.toast("✏️ 요청을 수정했습니다.")
                                    except Exception as e:
                                        st.error(f"수정 실패: {e}")
                                    st.rerun()
                            if _ec2.button("취소", key=f"req_ecancel_{_grp[0]['_row']}"):
                                st.session_state[_ekey] = False
                                st.rerun()

    # ── 📅 사업단 일정 (제목 옆 ➕로 일정 추가·수정·삭제 토글) ─────────────
    st.divider()
    if calendar_enabled():
        # 제목 + ＋를 한 HTML 줄에(컬럼 폭 문제 없이 딱 붙음). ＋는 ?go=cal 링크로 토글.
        _cuid = st.session_state.get("uid", "")
        _ctok = st.session_state.get("tok", "")
        _cb = f"uid={quote(_cuid)}&tok={quote(_ctok)}"
        _copen = st.session_state.get("home_cal_open", False)
        _sym = "－" if _copen else "＋"
        # 바로 아래가 달력 임베드라 여백이 좁으면 붙어 보인다 → 아래 여백 확보.
        # 색도 다크 대응(진한 주황 #A8501A는 어두운 배경에서 묻힘).
        _cdk = bool(st.session_state.get("dark"))
        st.markdown(
            "<div style='display:flex;align-items:center;gap:9px;"
            "margin:2px 0 14px;'>"
            f"<span style='font-weight:700;font-size:1.05rem;"
            f"color:{'#fbfaf7' if _cdk else '#A8501A'};'>"
            "📅 사업단 일정</span>"
            f"<a href='?{_cb}&go=cal' target='_self' title='일정 추가·수정·삭제' "
            f"style='text-decoration:none;font-size:1.4rem;"
            f"color:{'#e08a63' if _cdk else '#C4622D'};"
            f"line-height:1;font-weight:700;'>{_sym}</a></div>",
            unsafe_allow_html=True)
        if _copen:
            _calendar_manage()
        # 임베드 달력(기본 월간). 팀원 폰에서 로그인 벽 없이 보이려면 이 구글 캘린더를
        # '공개(모든 일정 세부정보 보기)'로 설정해야 함 → AGENTS.md 참고.
        _iframe = getattr(st, "iframe", components.iframe)
        _iframe(embed_url("MONTH"), height=520)
    else:
        st.markdown("**📅 사업단 일정**")
        st.caption("⚙️ 캘린더 미설정 — Secrets에 [calendar] id 필요.")

    # ── 📰 관련 뉴스 (전체 폭, 달력 아래) ────────────────────────────────
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

    # 📌 미처리 할 일 → 업무계획으로 넘기기 (form 안에서는 st.button 사용 불가 → 폼 밖에 배치)
    _uid_w = st.session_state.get("uid", "")
    if _uid_w:
        with st.expander("📌 미처리 할 일을 업무계획에 넣기", expanded=False):
            try:
                _undone = todo_store.list_todos(_uid_w)      # 남아 있는 업무 할 일
            except Exception:
                _undone = []
            if not _undone:
                st.caption("남은 업무 할 일이 없습니다. (완료한 항목은 ✓로 지워집니다)")
            else:
                st.caption("체크 후 버튼을 누르면 아래 '업무계획' 칸에 채워집니다.")
                _picks = [t["내용"] for t in _undone
                          if st.checkbox(t["내용"], key=f"carry_{t['_row']}")]
                if st.button("⬇️ 업무계획에 넣기", key="carry_btn"):
                    if _picks:
                        _base = existing.get("task_plan", "")
                        st.session_state["_task_plan_val"] = (
                            (_base + "\n" + "\n".join(_picks)).strip("\n"))
                        st.rerun()
                    else:
                        st.warning("먼저 넣을 항목을 체크해 주세요.")

        # ✅ 완료한 할 일 → 업무실적으로 넣기 (홈에서 ✓로 완료하면 여기에 모임)
        if _uid_w and "task_done" in fields:
            try:
                _since = (wednesday_of_week(week)
                          - timedelta(days=7)).strftime("%Y-%m-%d")
            except Exception:
                _since = None
            with st.expander("✅ 완료한 할 일을 실적에 넣기", expanded=False):
                try:
                    _done = todo_store.completed_todos(_uid_w, since=_since)
                except Exception:
                    _done = []
                if not _done:
                    st.caption("이번 주기에 완료 처리한 할 일이 없습니다. "
                               "(홈 '내 할 일'에서 ✓로 완료하면 여기에 모입니다)")
                else:
                    # 홈에서 나눈 연구/업무 그대로 각 실적 칸에 넣는다
                    st.caption("체크 후 버튼을 누르면 해당 실적 칸에 채워집니다.")
                    _dsel = {todo_store.AREA_RESEARCH: [],
                             todo_store.AREA_WORK: []}
                    for _t in _done:
                        _a = (_t.get("영역", "") or "").strip()
                        _a = _a if _a in _dsel else todo_store.AREA_WORK
                        if st.checkbox(f"[{_a}] {_t['내용']}",
                                       key=f"done_{_t['_row']}"):
                            _dsel[_a].append(_t["내용"])
                    _bc1, _bc2 = st.columns(2)
                    if "research_done" in fields and _bc1.button(
                            "⬇️ 연구실적에 넣기", key="done_res_btn",
                            use_container_width=True):
                        if _dsel[todo_store.AREA_RESEARCH]:
                            _rbase = existing.get("research_done", "")
                            st.session_state["_research_done_val"] = (
                                (_rbase + "\n"
                                 + "\n".join(_dsel[todo_store.AREA_RESEARCH]))
                                .strip("\n"))
                            st.rerun()
                        else:
                            st.warning("연구로 표시된 항목을 체크해 주세요.")
                    if _bc2.button("⬇️ 업무실적에 넣기", key="done_btn",
                                   use_container_width=True):
                        if _dsel[todo_store.AREA_WORK]:
                            _dbase = existing.get("task_done", "")
                            st.session_state["_task_done_val"] = (
                                (_dbase + "\n"
                                 + "\n".join(_dsel[todo_store.AREA_WORK]))
                                .strip("\n"))
                            st.rerun()
                        else:
                            st.warning("업무로 표시된 항목을 체크해 주세요.")

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
                    value=st.session_state.get(
                        "_research_done_val",
                        existing.get("research_done", "")),
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
            _tp_val = st.session_state.get("_task_plan_val",
                                           existing.get("task_plan", ""))
            _td_val = st.session_state.get("_task_done_val",
                                           existing.get("task_done", ""))
            tc1, tc2 = st.columns(2)
            with tc1:
                values["task_done"] = st.text_area(
                    FIELD_LABELS["task_done"],
                    value=_td_val,
                    height=220, placeholder="한 줄에 한 항목씩 작성",
                )
            with tc2:
                values["task_plan"] = st.text_area(
                    FIELD_LABELS["task_plan"], value=_tp_val,
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
            st.session_state.pop("_task_plan_val", None)   # 넘겨넣기 임시값 정리
            st.session_state.pop("_task_done_val", None)   # 실적 넣기 임시값 정리
            st.session_state.pop("_research_done_val", None)
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
                    # 완료 문서를 자료실에 자동 축적(유효 링크 + 중복 제외)
                    _lk = link.strip()
                    _archived = False
                    if _lk.startswith("http"):
                        try:
                            _exist = {x["링크"].strip()
                                      for x in resource_store.list_resources()}
                            if _lk not in _exist:
                                resource_store.add_resource(
                                    who, "협업문서", title, _lk, "문서협업 완료본")
                                _archived = True
                        except Exception:
                            pass
                    st.session_state["collab_flash"] = (
                        f"🏁 '{title}' 마감"
                        + (" · 📁 자료실에 등록됨" if _archived else ""))
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


def resource_page():
    """자료실 — 팀 공용 참고자료·양식 링크 보드(파일이 아니라 링크만 관리)."""
    st.header("📁 자료실")
    st.caption("팀 공용 참고자료·양식·매뉴얼 **링크** 모음. (파일이 아니라 구글문서/드라이브/URL 링크를 등록)")
    _flash("res_flash")
    me = st.session_state.get("me", "")

    with st.expander("➕ 자료 등록", expanded=False):
        c1, c2 = st.columns([1, 2])
        cat = c1.selectbox("분류", resource_store.CATEGORIES, key="res_cat")
        title = c2.text_input("제목", key="res_title")
        link = st.text_input("링크(URL)", key="res_link", placeholder="https://...")
        author = st.text_input("등록자", value=me, key="res_author")
        desc = st.text_area("설명(선택)", key="res_desc", height=60)
        if st.button("등록", type="primary", key="res_add"):
            try:
                resource_store.add_resource(author, cat, title, link, desc)
                st.session_state["res_flash"] = f"✅ 등록 — {title.strip()}"
                for k in ("res_title", "res_link", "res_desc"):
                    st.session_state.pop(k, None)
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
            except Exception as e:
                st.error(f"등록 실패: {e}")

    try:
        rows = resource_store.list_resources()
    except Exception as e:
        st.error(f"자료실을 불러오지 못했습니다: {e}")
        return
    q = st.text_input("🔎 검색 (제목·설명)", key="res_search").strip()
    if q:
        rows = [r for r in rows
                if q.lower() in (r["제목"] + " " + r["설명"]).lower()]
    if not rows:
        st.caption("표시할 자료가 없습니다." if q else "아직 등록된 자료가 없습니다.")
        return
    # 분류별 그룹(정의된 순서 → 그 외)
    order = resource_store.CATEGORIES
    cats = [c for c in order if any((r["분류"] or "") == c for r in rows)]
    cats += sorted({(r["분류"] or "기타") for r in rows if (r["분류"] or "") not in order})
    for cat in dict.fromkeys(cats):
        group = [r for r in rows if (r["분류"] or "기타") == cat]
        if not group:
            continue
        st.markdown(f"**📂 {cat}** ({len(group)})")
        for r in group:
            c1, c2 = st.columns([9, 1])
            meta = " · ".join(x for x in (r["등록자"], r["등록일시"]) if x)
            body = f"🔗 [{r['제목']}]({r['링크']})"
            if r["설명"]:
                body += f" — {r['설명']}"
            c1.markdown(body + (f"  \n<span style='color:#999;font-size:0.8rem;'>"
                                f"{meta}</span>" if meta else ""),
                        unsafe_allow_html=True)
            if c2.button("🗑️", key=f"res_del_{r['_row']}", help="삭제"):
                try:
                    resource_store.delete_resource(r["_row"], r["제목"])
                except Exception as e:
                    st.error(f"삭제 실패: {e}")
                st.rerun()
        st.divider()


def equip_page():
    """장비(기기) 사용현황 — 연구별 필터 조회 + 전체 목록 편집(등록·수정·삭제)."""
    st.header("🔧 장비 사용현황")
    st.caption("실증 장비(기기) 사용 현황 대장 — 연구(실증)별로 필터해 보고, 전체 목록을 "
               "편집할 수 있습니다. ※ 피험자명 등 개인정보 포함 — 팀 내부용입니다.")
    _link = sheet_link()
    if _link:
        st.markdown(f"🔗 [원본 구글시트(장비현황)에서 직접 편집하기]({_link}) "
                    "— 양이 많거나 세밀한 편집은 시트에서 하는 게 편합니다.")
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
    eloc = st.text_input("장소", value=v.get("location", ""),
                         key=f"cal_et_loc_{eid}")
    edesc = st.text_area("설명", value=v["desc"], key=f"cal_et_desc_{eid}", height=60)
    if st.button("💾 수정 저장", key=f"cal_et_save_{eid}", type="primary"):
        try:
            update_event(eid, title.strip(), edate.strftime("%Y-%m-%d"), eallday,
                         "09:00" if eallday else est.strftime("%H:%M"),
                         "10:00" if eallday else eet.strftime("%H:%M"),
                         edesc.strip(), eloc.strip())
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
            loc = st.text_input("장소", key="cal_add_loc",
                                placeholder="예: 의학세미나실 / 스마트돌봄스페이스")
            desc = st.text_area("설명 (선택)", key="cal_add_desc", height=70)
            if st.button("➕ 일정 등록", type="primary", use_container_width=True):
                if not title.strip():
                    st.warning("제목을 입력하세요.")
                else:
                    try:
                        add_event(title.strip(), adate.strftime("%Y-%m-%d"), allday,
                                  "09:00" if allday else stime.strftime("%H:%M"),
                                  "10:00" if allday else etime.strftime("%H:%M"),
                                  desc.strip(), loc.strip())
                        st.session_state["cal_flash"] = f"✅ 일정 등록 — {title.strip()}"
                        for k in ("cal_add_title", "cal_add_desc", "cal_add_loc"):
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

def feedback_page():
    """앱 개선 요청 — 팀원이 오류·개선 의견을 남기고 처리 상태를 공유."""
    st.header("💡 개선 요청")
    st.caption("Dolbom Studio를 쓰다가 **안 되는 것·불편한 것·있으면 좋겠는 것**을 "
               "남겨주세요. 업무 내용이 아니라 **앱 자체**에 대한 의견입니다.")
    _flash("fb_flash")

    # 🆕 최근 수정 내용 — 레포 루트 CHANGELOG.md 를 그대로 보여준다.
    #   (커밋 로그를 그대로 쓰면 미세 조정까지 섞여 팀원이 읽기 번잡함)
    try:
        _ch = (Path(__file__).parent.parent / "CHANGELOG.md").read_text(
            encoding="utf-8")
    except Exception:
        _ch = ""
    if _ch:
        with st.expander("🆕 최근 수정 내용", expanded=False):
            st.markdown(_ch.split("\n", 1)[1] if _ch.startswith("#") else _ch)

    with st.form("fb_add", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        _writer = c1.selectbox("작성자", USER_NAMES,
                               index=_me_index(USER_NAMES), key="fb_writer")
        _kind = c2.selectbox("분류", feedback_store.KINDS, key="fb_kind")
        _text = st.text_area(
            "내용", key="fb_text", height=110,
            placeholder="예: 휴대폰에서 달력 글씨가 잘려요 / 할 일에 반복 기능이 있으면 좋겠어요")
        if st.form_submit_button("등록", use_container_width=True):
            if not _text.strip():
                st.warning("내용을 적어주세요.")
            else:
                try:
                    feedback_store.add_feedback(_writer, _kind, _text)
                    st.session_state["fb_flash"] = "✅ 등록했습니다. 고맙습니다!"
                except Exception as e:
                    st.error(f"등록 실패: {e}")
                st.rerun()

    try:
        rows = feedback_store.fb_rows()
    except Exception as e:
        st.error(f"목록을 불러오지 못했습니다: {e}")
        return

    _open = [r for r in rows
             if r["상태"].strip() not in (feedback_store.ST_DONE,)]
    _closed = [r for r in rows if r["상태"].strip() == feedback_store.ST_DONE]
    st.markdown(f"### 처리 중 ({len(_open)})")
    if not _open:
        st.caption("처리할 요청이 없습니다.")
    for r in _open:
        _fb_item(r)
    # 완료 목록은 바깥 expander로 감싸면 항목 expander와 2단 중첩이 되어 앱이 죽는다
    # → 제목만 두고 최근 것부터 펼침 없이 나열.
    if _closed:
        st.markdown(f"### ✅ 처리 완료 ({len(_closed)})")
        for r in _closed[:10]:
            _fb_item(r)
        if len(_closed) > 10:
            st.caption(f"이하 {len(_closed) - 10}건은 구글시트에서 확인하세요.")


def _fb_item(r):
    """개선 요청 한 건 — 내용 + 상태 변경 + 삭제."""
    _st = r["상태"].strip() or feedback_store.ST_NEW
    _mark = {"접수": "🆕", "진행중": "🔧", "완료": "✅", "보류": "⏸️"}.get(_st, "🆕")
    with st.expander(f"{_mark} [{_st}] {r['분류']} · {r['내용'][:40]}"
                     + ("…" if len(r["내용"]) > 40 else ""),
                     expanded=False):
        st.text(r["내용"])
        st.caption(f"{r['작성자']} · {r['등록일시']}"
                   + (f" · 처리 {r['처리자']} {r['처리일시']}"
                      if r["처리일시"].strip() else ""))
        with st.form(f"fb_edit_{r['_row']}"):
            c1, c2 = st.columns([1, 3])
            _ns = c1.selectbox("상태", feedback_store.STATUSES,
                               index=feedback_store.STATUSES.index(_st)
                               if _st in feedback_store.STATUSES else 0,
                               key=f"fb_st_{r['_row']}")
            _memo = c2.text_input("처리 메모", value=r["처리메모"],
                                  key=f"fb_memo_{r['_row']}",
                                  placeholder="예: 다음 배포에 반영")
            b1, b2 = st.columns(2)
            if b1.form_submit_button("저장", use_container_width=True):
                try:
                    feedback_store.set_status(
                        r["_row"], r["등록일시"], _ns, _memo,
                        st.session_state.get("me", ""))
                    st.session_state["fb_flash"] = "✅ 저장했습니다."
                except feedback_store.RowMismatch as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"저장 실패: {e}")
                st.rerun()
            if b2.form_submit_button("삭제", use_container_width=True):
                try:
                    feedback_store.delete_feedback(r["_row"], r["등록일시"])
                    st.session_state["fb_flash"] = "🗑️ 삭제했습니다."
                except feedback_store.RowMismatch as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"삭제 실패: {e}")
                st.rerun()
        if r["처리메모"].strip():
            st.info(f"📝 {r['처리메모']}")


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


def meeting_page():
    """주간 회의용 회의 진행 모드 — 전용 페이지(사이드바 홈 바로 밑)."""
    st.header("🖥️ 주간취합")
    st.caption("주간 회의용 — 연구원별 실적/계획을 취합본 형식으로. 한 명씩 한 화면.")
    _wd = st.date_input(
        "조회 주차", key="meet_week",
        value=datetime.strptime(this_wednesday(), "%Y-%m-%d").date(),
        help="달력에서 아무 날짜나 고르면 그 주(수요일 기준)로 조회됩니다.")
    week = (_wd + timedelta(days=(2 - _wd.weekday()))).strftime("%Y-%m-%d")
    st.caption(f"📅 조회 주차: **{week} (수)**")

    # 🔗 줌 링크 — 팀 공용. 주간회의·세미나처럼 고정 링크가 여러 개라 이름별로 저장.
    _zl = zoom_links()
    _zcols = st.columns(max(len(_zl), 1) + 1)
    for _i, (_zn, _zu) in enumerate(_zl):
        _zcols[_i].link_button(f"🎥 {_zn}", _zu, use_container_width=True)
    if not _zl:
        _zcols[0].caption("🎥 줌 링크가 아직 없습니다. 오른쪽에서 등록하세요.")
    if _zcols[-1].button("⚙️ 링크 설정", key="zoom_set_btn",
                         use_container_width=True):
        st.session_state["zoom_edit"] = not st.session_state.get("zoom_edit", False)
        st.rerun()
    if st.session_state.get("zoom_edit"):
        with st.form("zoom_form"):
            st.caption("이름과 주소를 적어 저장하세요. 이름을 지우면 그 줄은 삭제됩니다. "
                       "(예: 주간회의 / 세미나)")
            _rows_in = []
            for _i, (_zn, _zu) in enumerate(_zl + [("", "")]):   # 마지막은 새 줄
                _c1, _c2 = st.columns([1, 3])
                _rows_in.append((
                    _c1.text_input("이름", value=_zn, key=f"zn_{_i}",
                                   placeholder="주간회의"),
                    _c2.text_input("주소", value=_zu, key=f"zu_{_i}",
                                   placeholder="https://zoom.us/j/…")))
            if st.form_submit_button("저장"):
                try:
                    save_zoom_links(_rows_in)
                    st.session_state["zoom_edit"] = False
                except Exception as e:
                    st.error(f"저장 실패: {e}")
                st.rerun()

    # 섹션(st.markdown)들 사이 흰 여백 제거 — Streamlit 기본 블록 간격 축소.
    # ⚠ 반드시 본문(stMain)으로 한정 — 전역이면 사이드바 메뉴 간격까지 무너져
    #   카테고리 소제목이 버튼에 겹쳐 보인다.
    st.markdown("<style>section[data-testid='stMain'] "
                "[data-testid='stVerticalBlock']{gap:0.1rem !important;}</style>",
                unsafe_allow_html=True)
    with st.expander("📋 회의 자료 전체 (펼치기/접기)", expanded=True):
        mdata = load_week(week)
        submitted = [n for n in MEMBER_NAMES if mdata.get(n)]
        if not submitted:
            st.caption("제출된 보고가 없습니다.")
        else:
            st.caption(f"제출 {len(submitted)}명 — 취합본과 같은 '실적 | 계획' 표. 아래로 스크롤하며 진행.")
            # 테두리 있는 HTML 표(칸 또렷·여백 최소, 차분한 톤). 실적/계획은 정확히 반반.
            # 다크모드면 표도 어두운 팔레트로(전체 다크). 밝을 땐 기존 색 그대로.
            _dark = bool(st.session_state.get("dark"))
            _BD = "#333331" if _dark else "#efe2d2"
            _TXT = "#f0eee9" if _dark else "#000"
            _HDBG = "#1d1d1c" if _dark else "#fdf5ec"
            _ADBG = "#2b3140" if _dark else "#ffffff"
            _ADFG = "#8ab4f8" if _dark else "#1a56db"
            _TD = (f"border:1px solid {_BD};padding:5px 9px;vertical-align:top;"
                   "text-align:left;word-break:break-word;overflow-wrap:anywhere;"
                   f"overflow:hidden;color:{_TXT};")
            _LBL = _TD + f"font-weight:700;background:{_HDBG};color:{_TXT};"
            # height:1px → 이 행들은 내용 높이만 차지(안 늘어남). 남는 높이는 내용 행이 흡수.
            _TH = _TD + (f"height:1px;background:{_HDBG};color:{_TXT};"
                         "font-weight:700;text-align:center;")
            _ADS = _TD + f"height:1px;background:{_ADBG};color:{_ADFG};font-weight:700;"

            def _esc(s):
                s = (s or "").strip()
                s = (s.replace("&", "&amp;").replace("<", "&lt;")
                     .replace(">", "&gt;").replace("\n", "<br>"))
                return s or "-"

            def _tbl(inner, fill=False, lblw="56px"):
                # table-layout:fixed + colgroup → 구분칸 고정, 실적/계획 50:50(정중앙)
                # fill=True → 표가 한 화면(84vh) 이상 → 내용 없어도 셀이 커져 화면 가득 참
                # lblw → 구분칸 너비(회의자료처럼 라벨 긴 표는 넓게)
                h = "height:84vh;" if fill else ""
                return (f"<table style='width:100%;{h}border-collapse:collapse;"
                        "table-layout:fixed;font-size:1.05rem;line-height:1.32;'>"
                        f"<colgroup><col style='width:{lblw}'><col><col></colgroup>"
                        + inner + "</table>")

            # 헤더 날짜 범위: 실적=지난주 수요일~이번주 화요일, 계획=이번주 수요일~다음주 화요일
            _w = wednesday_of_week(week)
            _dr = ("실적(" + (_w - timedelta(days=7)).strftime("%Y.%m.%d.")
                   + " ~ " + (_w - timedelta(days=1)).strftime("%Y.%m.%d.") + ")")
            _pr = ("계획(" + _w.strftime("%Y.%m.%d.")
                   + " ~ " + (_w + timedelta(days=6)).strftime("%Y.%m.%d.") + ")")

            def _hdr():
                return (f"<tr><th style='{_LBL}'>구분</th>"
                        f"<th style='{_TH}'>{_dr}</th>"
                        f"<th style='{_TH}'>{_pr}</th></tr>")

            def _row(lb, dv, pv):
                return (f"<tr><td style='{_LBL}'>{lb}</td>"
                        f"<td style='{_TD}'>{_esc(dv)}</td>"
                        f"<td style='{_TD}'>{_esc(pv)}</td></tr>")

            def _full(lb, v):
                return (f"<tr><td style='{_LBL}'>{lb}</td>"
                        f"<td style='{_TD}' colspan='2'>{_esc(v)}</td></tr>")

            _BARFG = "#fbfaf7" if _dark else "#000"

            def _barhtml(bg, txt, right=""):
                if _dark:
                    bg = "#4a3527" if bg == "#fbe6d3" else "#3c2a1e"
                return (f"<div style='background:{bg};color:{_BARFG};padding:6px 12px;"
                        f"border-radius:7px 7px 0 0;font-weight:700;font-size:1.08rem;'>"
                        f"{txt}<span style='float:right;font-size:0.72rem;font-weight:400;"
                        f"opacity:.75;color:{_BARFG};'>{right}</span></div>")

            def _bar(bg, txt, right=""):
                st.markdown(_barhtml(bg, txt, right), unsafe_allow_html=True)

            # 상단: 사업단 공통확인사항 (취합본 1~2쪽) — 확인사항 리스트 + 용역/자산 실적·계획 표
            conf1 = ""
            for n in submitted:
                v = (mdata[n].get("project_confirmation_1", "") or "").strip()
                if v:
                    conf1 = v
                    break
            try:
                ct = load_common()
            except Exception:
                ct = {}

            def _num(s):
                return int("".join(ch for ch in str(s) if ch.isdigit()) or "0")

            def _mini(headers, items, ncols, midx):
                data = [it for it in items
                        if any((str(c) or "").strip() for c in it[:ncols])]
                if not data:
                    return "<div style='color:#999;font-size:0.78rem;padding:2px;'>(없음)</div>"
                # 행 간격(세로 여백) 최소화 → 공통확인 2가 한 화면에 들어오게(글씨는 유지)
                tdm = (f"border:1px solid {_BD};padding:2px 6px;vertical-align:top;"
                       "overflow-wrap:anywhere;line-height:1.28;color:#000;")
                thm = tdm + "background:#fdf5ec;font-weight:700;text-align:center;"
                # 고정 레이아웃 + 열너비 → 긴 글씨도 셀 안에서 줄바꿈(튀어나감 방지)
                if ncols == 3:      # 용역: 순번/분야/발주금액/비고(금액 좁게)
                    cols = "<col style='width:6%'><col style='width:48%'><col style='width:14%'><col style='width:32%'>"
                else:               # 자산: 순번/품명/수량/구매금액/비고(금액 좁게)
                    cols = "<col style='width:6%'><col style='width:33%'><col style='width:8%'><col style='width:15%'><col style='width:38%'>"
                out = ("<table style='width:100%;border-collapse:collapse;"
                       "table-layout:fixed;font-size:0.88rem;'><colgroup>" + cols
                       + "</colgroup><tr>"
                       + "".join(f"<th style='{thm}'>{h}</th>" for h in headers) + "</tr>")
                tot = 0
                for i, it in enumerate(data, 1):
                    cs = f"<td style='{tdm}'>{i}</td>"
                    for j in range(ncols):
                        cs += f"<td style='{tdm}'>{_esc(str(it[j]) if j < len(it) else '')}</td>"
                    out += f"<tr>{cs}</tr>"
                    tot += _num(it[midx]) if midx < len(it) else 0
                sc = ""
                for j in range(ncols + 1):
                    if j == 1:
                        sc += f"<td style='{tdm}'><b>합계</b></td>"
                    elif j == midx + 1:
                        sc += f"<td style='{tdm}'><b>{tot:,}</b></td>"
                    else:
                        sc += f"<td style='{tdm}'></td>"
                return out + f"<tr>{sc}</tr></table>"

            def _side(yk, ak, ek):
                h = ("<div style='font-weight:700;color:#8A4A1E;margin:1px 0 3px;'>"
                     "&lt;본부과제 용역&gt;</div>")
                h += _mini(["순번", "분야", "발주금액", "비고"], ct.get(yk, []), 3, 1)
                h += ("<div style='font-weight:700;color:#8A4A1E;margin:7px 0 3px;'>"
                      "&lt;본부과제 자산구매&gt;</div>")
                h += _mini(["순번", "품명", "수량", "구매금액", "비고"], ct.get(ak, []), 4, 2)
                ex = (ct.get(ek, "") or "").strip()
                if ex:
                    h += f"<div style='margin-top:6px;'>{_esc(ex)}</div>"
                return h

            has_tables = any(any((str(c) or "").strip() for it in ct.get(k, []) for c in it)
                             for k in ("용역_실적", "용역_계획", "자산_실적", "자산_계획")) \
                or (ct.get("기타_실적", "") or "").strip() \
                or (ct.get("기타_계획", "") or "").strip()

            # 모든 섹션을 하나의 HTML로 합쳐 마지막에 한 번에 렌더 → 섹션 간 겹침/흰띠 없음
            _SEC = ("<div style='border-bottom:2px dashed #e6be97;"
                    "margin-bottom:10px;padding-bottom:6px;'>")
            HTML = ""
            # 사업단 공통확인사항 1(확인사항 리스트) — 한 화면 고정
            if conf1:
                p1 = (_barhtml("#f8e0c9", "📋 사업단 공통확인사항 1")
                      + _tbl(_full("확인사항", conf1), fill=True, lblw="96px"))
                HTML += _SEC + p1 + "</div>"
            # 사업단 공통확인사항 2(용역/자산 실적·계획) — 한 화면 고정
            if has_tables:
                outer = (_hdr()
                         + f"<tr><td style='{_LBL}'>공통</td>"
                         + f"<td style='{_TD}'>{_side('용역_실적', '자산_실적', '기타_실적')}</td>"
                         + f"<td style='{_TD}'>{_side('용역_계획', '자산_계획', '기타_계획')}</td></tr>")
                p2 = (_barhtml("#f8e0c9", "📋 사업단 공통확인사항 2")
                      + _tbl(outer, fill=True))
                HTML += _SEC + p2 + "</div>"

            PAIRS = [("research_done", "research_plan", "연구"),
                     ("task_done", "task_plan", "업무")]
            paired = {k for a, b, _ in PAIRS for k in (a, b)}
            # 스페이스·공통확인·회의자료는 카드에서 빼고 별도/마지막 섹션으로
            skip = paired | {"acquired_data", "project_confirmation_1",
                             "project_confirmation_2_done", "project_confirmation_2_plan",
                             "research_meeting", "director_meeting", "mohw_weekly",
                             "smart_care_space_done", "smart_care_space_plan"}

            # 본부과제 하위 분야별 그룹(취합본 좌측 계층)
            GROUPS = [("현장실증", ["백정은", "한벼리", "박재우", "이윤환"]),
                      ("로봇기술", ["김건양", "류현경", "남재엽", "이경진"]),
                      ("운영과제", ["최혜민", "정지수"])]
            grouped = {n for _g, ns in GROUPS for n in ns}
            plan = [(g, [n for n in ns if n in submitted]) for g, ns in GROUPS]
            _others = [n for n in submitted if n not in grouped]
            if _others:
                plan.append(("기타", _others))

            for gname, gmembers in plan:
                if not gmembers:
                    continue
                HTML += (f"<div style='color:{_BARFG};font-weight:700;font-size:0.98rem;"
                         f"margin:12px 0 4px;border-left:5px solid #C4622D;"
                         f"padding-left:8px;'>🏛️ 본부과제 · {gname}</div>")
                for name in gmembers:
                    r = mdata[name]
                    fields = get_fields_for(get_member(name))
                    inner = ""
                    ad = (r.get("acquired_data", "") or "").strip()
                    for pre in ("획득 데이터:", "획득데이터:", "획득 데이터 :"):
                        if ad.startswith(pre):
                            ad = ad[len(pre):].strip()
                    if "acquired_data" in fields and ad:
                        inner += (f"<tr><td colspan='3' style='{_ADS}'>"
                                  f"획득 데이터: {_esc(ad)}</td></tr>")
                    pairs = [(lb, r.get(d, ""), r.get(p, "")) for d, p, lb in PAIRS
                             if (d in fields or p in fields)
                             and ((r.get(d, "") or "").strip()
                                  or (r.get(p, "") or "").strip())]
                    if pairs:
                        inner += _hdr()
                        for lb, dv, pv in pairs:
                            inner += _row(lb, dv, pv)
                    for f in fields:
                        if f in skip:
                            continue
                        v = (r.get(f, "") or "").strip()
                        if not v:
                            continue
                        inner += _full(FIELD_LABELS[f], v)
                    # 한 사람 = 한 화면(표 84vh) → 내용 없어도 셀이 커져 화면 가득, 2명 안 겹침.
                    tbl = _tbl(inner, fill=True) if inner else ""
                    bar = _barhtml("#fbe6d3", f"🙋 {name}", r.get("submitted_at", ""))
                    HTML += _SEC + bar + tbl + "</div>"

            # 회의자료(최혜민) — 취합본 뒷부분(정지수 다음). 비어 있어도 항상 표시.
            MEET = [("research_meeting", "1. 연구소 회의자료 (소장주재회의)"),
                    ("director_meeting", "2. 원장+재활원 주요간부회의자료 (주간현안보고)"),
                    ("mohw_weekly",
                     "3. 복지부 본부 주간일정·보산진 보고 (의료기기 R&D 주간일정)")]
            mvals = {}
            for k, _lb in MEET:
                for n in submitted:
                    v = (mdata[n].get(k, "") or "").strip()
                    if v:
                        mvals[k] = v
                        break
            # 스마트돌봄스페이스(백정은 등) — 마지막에 회의자료와 함께
            scd = scp = ""
            for n in submitted:
                if not scd:
                    scd = (mdata[n].get("smart_care_space_done", "") or "").strip()
                if not scp:
                    scp = (mdata[n].get("smart_care_space_plan", "") or "").strip()
            minner = _hdr()
            minner += _row("스마트돌봄스페이스", scd, scp)
            for k, lb in MEET:
                minner += _full(lb, mvals.get(k, ""))
            HTML += (_SEC + _barhtml("#f8e0c9", "🏠 스마트돌봄스페이스 · 📑 회의자료")
                     + _tbl(minner, fill=True, lblw="230px") + "</div>")

            # 합친 HTML을 한 번에 렌더(섹션 사이 Streamlit 간격 없음 → 겹침/흰띠 해결)
            st.markdown(HTML, unsafe_allow_html=True)

            # 월간 캘린더(취합본 마지막) — 스마트돌봄스페이스 및 돌봄사업 일정
            if calendar_enabled():
                _bar("#f8e0c9", "🗓️ 스마트돌봄스페이스 및 돌봄사업 일정")
                try:
                    _ifr = getattr(st, "iframe", components.iframe)
                    _ifr(embed_url("MONTH"), height=560)
                except Exception:
                    st.caption("캘린더를 불러오지 못했습니다.")



def _report_collect():
    """제출 현황 + 미리보기 + HWPX 취합본 생성 (구 담당자 대시보드에서 이동, 누구나)."""
    _wd = st.date_input(
        "조회 주차", key="collect_week",
        value=datetime.strptime(this_wednesday(), "%Y-%m-%d").date(),
        help="달력에서 아무 날짜나 고르면 그 주(수요일 기준)로 조회됩니다.")
    week = (_wd + timedelta(days=(2 - _wd.weekday()))).strftime("%Y-%m-%d")
    st.caption(f"📅 조회 주차: **{week} (수)**")

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
        # 카톡 등에 붙여넣어 독촉할 수 있게 명단 복사용 텍스트 제공
        st.code(" ".join(f"@{n}" for n in missing) + " 주간보고 부탁드립니다 🙏",
                language=None)
    else:
        st.success("🎉 전원 제출 완료 — 취합본 생성/발송 가능합니다 (담당: 정지수 연구원)")

    # ⚠️ 취합본을 만든 뒤에 보고를 고친 사람 표시 — 옛 파일을 회의에 띄우지 않도록.
    #   제출시간·생성시각 모두 'YYYY-MM-DD HH:MM' 이라 문자열 비교로 시간순 판정 가능.
    try:
        _exported_at = todo_store.get_sync("_team", f"export_{week}")
    except Exception:
        _exported_at = ""
    if _exported_at:
        _late = [s["name"] for s in status
                 if (s["submitted_at"] or "") > _exported_at]
        if _late:
            st.warning(
                f"⚠️ **취합본 생성({_exported_at}) 후 수정한 사람: "
                f"{', '.join(_late)}** — 아래에서 다시 생성하세요. "
                "(받아둔 파일에는 이 수정이 빠져 있습니다)")
        else:
            st.caption(f"🗂️ 이번 주차 취합본 마지막 생성: {_exported_at} — "
                       "이후 수정 없음(최신)")

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

    st.checkbox(
        "📐 줄바꿈 재계산 (권장) — 글자가 칸 밖으로 넘치지 않게",
        value=True, key="hwpx_relayout",
        help="템플릿에 남은 옛 줄바꿈 정보를 지워 한글이 다시 계산하게 합니다. "
             "끄면 예전 방식(긴 문장이 칸 밖으로 넘칠 수 있음).",
    )
    st.checkbox(
        "🔎 내용 많은 칸만 1pt 작게 (권장) — 다음 장으로 밀리지 않게",
        value=True, key="hwpx_shrink",
        help="칸 분량을 넘치는 칸만 글자를 1pt 줄입니다(9pt→8pt). "
             "1pt까지만 줄이며, 그래도 넘치면 그대로 둡니다.",
    )

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

            # 마지막 장 월간 달력을 이번 주차의 달로 새로 그려 교체(템플릿 옛 달력 방지)
            cal_bmp = None
            try:
                if calendar_enabled():
                    import calendar_image   # 지연 임포트(PIL 없어도 앱은 정상)
                    if not calendar_image.has_korean_font():
                        st.caption("※ 한글 폰트가 없어 달력 갱신을 건너뜁니다"
                                   "(템플릿 달력 그대로). 나머지는 정상 생성됩니다.")
                    else:
                        _evs = month_events(wed.year, wed.month)
                        cal_bmp = calendar_image.build_calendar_bmp(
                            wed.year, wed.month, _evs)
            except Exception as _e:
                st.caption(f"※ 달력 이미지 갱신을 건너뜁니다({_e}). 나머지는 정상 생성됩니다.")
            _shrunk = []
            result = build_report(
                template_bytes, submissions,
                title_date=title_date,
                period_start=period_start, period_end=period_end,
                plan_start=plan_start, plan_end=plan_end,
                calendar_bmp=cal_bmp,
                relayout=st.session_state.get("hwpx_relayout", True),
                calendar_ym=(wed.year, wed.month),
                shrink_overflow=st.session_state.get("hwpx_shrink", True),
                shrunk_out=_shrunk,
            )
            if _shrunk:
                st.caption("🔎 내용이 많아 **1pt 작게** 넣은 칸: "
                           + ", ".join(_shrunk)
                           + " — 그래도 넘치면 내용을 조금 줄여주세요.")
            filename = f"돌봄로봇_업무보고({wed.strftime('%m.%d')})_취합본.hwpx"
            st.download_button(
                "💾 HWPX 다운로드",
                data=result,
                file_name=filename,
                mime="application/octet-stream",
                use_container_width=True,
            )
            # 생성 시각 기록(팀 공용) — 이후 누가 보고를 고치면 '취합 후 수정'으로
            # 제출현황에 표시돼, 옛 파일을 회의에 띄우는 일을 막는다.
            try:
                todo_store.set_sync(
                    "_team", f"export_{week}",
                    datetime.now(KST).strftime("%Y-%m-%d %H:%M"))
            except Exception:
                pass
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


def _member_admin():
    """👤 회원 관리 (관리자 전용 메뉴) — 가입 승인 + 전체 상태 변경."""
    st.header("👤 회원 관리")
    if not st.session_state.get("is_admin"):
        st.warning("관리자만 사용할 수 있습니다.")
        return
    try:
        accts = account_store.all_accounts()
    except Exception as e:
        st.error(f"계정을 불러오지 못했습니다: {e}")
        return
    npend = sum(1 for a in accts if a["상태"].strip() == account_store.ST_PENDING)
    st.caption(f"대기 {npend}명 / 전체 {len(accts)}명 — 승인해야 로그인할 수 있습니다.")
    if not accts:
        st.info("아직 가입한 계정이 없습니다.")
        return
    order = {"대기": 0, "승인": 1, "거부": 2}
    for a in sorted(accts, key=lambda x: order.get(x["상태"].strip(), 3)):
        stt = a["상태"].strip()
        cc = st.columns([5, 1, 1, 1])
        emails = " / ".join(e for e in (a.get('이메일_korea', ''),
                                        a.get('이메일_gmail', '')) if e.strip())
        cc[0].markdown(f"**{a['이름']}** {a.get('직함', '')} · `{a['아이디']}`"
                       + (f" · {emails}" if emails else "")
                       + f" — **[{stt or '?'}]**")
        aid = a["아이디"]
        if stt != "승인" and cc[1].button("승인", key=f"ma_ok_{aid}"):
            account_store.set_status(aid, account_store.ST_OK)
            st.rerun()
        if stt != "대기" and cc[2].button("대기", key=f"ma_pd_{aid}"):
            account_store.set_status(aid, account_store.ST_PENDING)
            st.rerun()
        if stt != "거부" and cc[3].button("거부", key=f"ma_rj_{aid}"):
            account_store.set_status(aid, account_store.ST_REJECT)
            st.rerun()
    st.caption("거부 취소·권한 회수는 상태를 '대기'/'승인'으로 바꾸면 됩니다.")


@st.cache_data
def _pwa_icon_b64():
    try:
        p = Path(__file__).resolve().parent / "assets" / "dolbom_favicon.png"
        return base64.b64encode(p.read_bytes()).decode()
    except Exception:
        return ""


def _inject_pwa():
    """홈 화면 추가 시 아이콘·이름·전체화면(PWA) — 문서 head에 manifest/아이콘 주입.
    실패해도 무해(try/catch), 세션당 1회. iOS Safari는 iframe 제약으로 일부만 적용될 수 있음."""
    if st.session_state.get("_pwa_done"):
        return
    b64 = _pwa_icon_b64()
    if not b64:
        return
    icon = f"data:image/png;base64,{b64}"
    manifest = {
        "name": "Dolbom Studio", "short_name": "Dolbom",
        "start_url": ".", "display": "standalone",
        "background_color": "#2B2018", "theme_color": "#C4622D",
        "icons": [{"src": icon, "sizes": "512x512", "type": "image/png"},
                  {"src": icon, "sizes": "192x192", "type": "image/png"}],
    }
    js = ("<script>try{var p=window.parent.document;"
          "if(!p.getElementById('ds-pwa')){var h=p.head;"
          "function m(n,c){var e=p.createElement('meta');e.name=n;e.content=c;h.appendChild(e);}"
          "var mk=p.createElement('meta');mk.id='ds-pwa';mk.name='ds-pwa';mk.content='1';h.appendChild(mk);"
          "m('apple-mobile-web-app-capable','yes');"
          "m('apple-mobile-web-app-status-bar-style','default');"
          "m('apple-mobile-web-app-title','Dolbom Studio');m('theme-color','#C4622D');"
          "var ic=p.createElement('link');ic.rel='apple-touch-icon';ic.href=" + json.dumps(icon) + ";h.appendChild(ic);"
          "var b=new Blob([" + json.dumps(json.dumps(manifest)) + "],{type:'application/json'});"
          "var ml=p.createElement('link');ml.rel='manifest';ml.href=URL.createObjectURL(b);h.appendChild(ml);"
          "}}catch(e){}</script>")
    components.html(js, height=0)
    st.session_state["_pwa_done"] = True


def main():
    if not auth_gate():
        return
    _inject_pwa()
    # me·is_admin은 로그인 시 _set_session()에서 세팅됨(개인 계정).
    # 로그인 유지: ?uid=&tok= URL 토큰 + 브라우저 localStorage(다음 방문 자동 로그인).
    # 저장은 여기(정상 렌더)에서 1회 — 로그인 직후 rerun에 컴포넌트 쓰기가 잘리지 않게.
    _save = st.session_state.pop("_ls_save", None)
    if _save:
        try:
            from streamlit_js_eval import set_local_storage
            set_local_storage("ds_auth", _save, component_key="ls_set")
        except Exception:
            pass
    # 개인 할 일도 같은 방식으로 브라우저에만 기록(서버·시트로 안 나감)
    _psave = st.session_state.pop("_ls_per_save", None)
    if _psave:
        try:
            from streamlit_js_eval import set_local_storage
            set_local_storage(_psave[0], _psave[1], component_key="ls_per_set")
        except Exception:
            pass

    # 전체 페이지 여백 축소 + dolbom studio 주황/갈색 톤(전 페이지 적용)
    st.markdown("""<style>
      .block-container,
      [data-testid="stMainBlockContainer"]{
        padding-top:3.6rem;padding-bottom:2rem;
        padding-left:1.6rem;padding-right:1.6rem;}
      /* 헤더·섹션 라벨(굵은글씨)·링크를 주황갈색으로 (알림박스 안 굵은글씨는 제외) */
      h1,h2,h3,h4,h5,h6{ color:#8A3F12; }
      [data-testid="stMarkdownContainer"] strong{ color:#A8501A; }
      [data-testid="stAlert"] strong{ color:inherit; }
      a,a:visited{ color:#C4622D; }
      /* 다크 사이드바(CRLM식) — 텍스트 밝게 강제해 가독성 보장 */
      section[data-testid="stSidebar"]{ background:#2B2018; }
      section[data-testid="stSidebar"] *{ color:#EFE5D8 !important; }
      /* 네비게이션 버튼: 큰 글씨·왼쪽 정렬·현재 메뉴 강조 */
      section[data-testid="stSidebar"] .stButton>button{
        background:transparent; border:none; text-align:left !important;
        justify-content:flex-start !important; font-size:1.05rem; font-weight:600;
        padding:7px 14px; border-radius:8px; margin:1px 0; }
      section[data-testid="stSidebar"] .stButton>button p,
      section[data-testid="stSidebar"] .stButton>button div{
        text-align:left !important; width:100%; margin:0; }
      section[data-testid="stSidebar"] .stButton>button:hover{ background:#3c2d22; }
      section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
        background:#C4622D; color:#fff !important; font-weight:700; }
      section[data-testid="stSidebar"] .stButton>button[kind="primary"]:hover{ background:#A8501A; }
      /* 테마 전환 버튼: 메뉴와 구분되게 테두리 있는 작은 칩 */
      section[data-testid="stSidebar"] .st-key-theme_btn button{
        background:#3a2c22 !important; border:1px solid #6a5544 !important;
        font-size:0.85rem !important; font-weight:600; padding:5px 12px !important;
        text-align:center !important; justify-content:center !important;
        margin:0 0 10px !important; }
      section[data-testid="stSidebar"] .st-key-theme_btn button:hover{
        background:#4a3a2c !important; border-color:#C4622D !important; }
      section[data-testid="stSidebar"] .st-key-theme_btn button p{
        text-align:center !important; }
      /* 카테고리 소제목 */
      section[data-testid="stSidebar"] .navcat{
        color:#b79370 !important; font-size:0.7rem; font-weight:700;
        letter-spacing:1.5px; margin:12px 6px 2px; }
      /* 일반 버튼 주황 톤(바로가기 타일은 더 구체적 규칙이라 그대로 유지) */
      div.stButton>button{ border-color:#E6C9AC; color:#8A4A1E; }
      div.stButton>button:hover{ border-color:#C4622D; color:#C4622D; }
      div.stButton>button[kind="primary"]{ background:#C4622D; border-color:#C4622D; color:#FFFFFF; }
      div.stButton>button[kind="primary"]:hover{ background:#A8501A; border-color:#A8501A; color:#FFFFFF; }
      /* 📱 모바일(좁은 화면): 2단 컬럼 세로로 쌓고 여백 축소 → 폰에서 안 잘림 */
      @media (max-width: 700px){
        .block-container, [data-testid="stMainBlockContainer"]{
          padding-left:0.8rem; padding-right:0.8rem; padding-top:2.6rem; }
        /* 본문만 — 사이드바 안의 좌우 배치까지 세로로 쌓이면 메뉴가 망가짐 */
        section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]{
          flex-direction:column; gap:0.4rem; }
        section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]
          > div[data-testid="column"]{
          width:100% !important; flex:1 1 100% !important; }
      }
    </style>""", unsafe_allow_html=True)

    # 🌙 다크모드(계정별 선택). 세션에 없으면 저장된 설정에서 1회 불러옴.
    if "dark" not in st.session_state:
        try:
            st.session_state["dark"] = (
                todo_store.get_sync(st.session_state.get("uid", ""), "theme")
                == "dark")
        except Exception:
            st.session_state["dark"] = False
    if st.session_state.get("dark"):
        st.markdown("""<style>
      /* 팔레트 — 톤 조정은 여기 5줄만 바꾸면 전체 반영 */
      /* ⚠ 눈부심은 '배경 밝기'가 아니라 '글씨와의 대비'에서 온다.
         검정 배경에 순백 글씨(15:1)면 옛날 화면처럼 쨍하게 빛난다.
         → 배경은 검정으로 두고 흰색의 채도·밝기를 낮춰 9:1 안팎으로 맞춘다. */
      :root{ --ds-bg:#141413; --ds-surface:#1d1d1c; --ds-surface2:#282826;
             --ds-border:#333331; --ds-text:#f0eee9; --ds-text2:#b3b0a9;
             --ds-accent:#b05a35; }
      /* 다크모드 — Claude 데스크탑 방식: 중성 회색 배경 + 흰 글씨.
         눈부심의 원인은 글씨 밝기가 아니라 '채도 높은 주황이 곳곳에 있는 것'이라,
         주황은 포인트(버튼·아이콘)에만 남기고 글씨·제목은 흰색으로 통일한다. */
      .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"]{
        background:var(--ds-bg) !important; }
      /* 상단 바 — 흰색으로 남아 사이드바 열기(») 버튼이 묻혔음.
         Fork/앱메뉴/배포 버튼과 사이드바 상단 영역도 같이 흰 박스로 남는다. */
      [data-testid="stHeader"], [data-testid="stToolbar"],
      [data-testid="stDecoration"], [data-testid="stStatusWidget"],
      [data-testid="stToolbarActions"], [data-testid="stActionButton"],
      [data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
      [data-testid="stSidebarHeader"], [data-testid="stSidebarNavItems"],
      [data-testid="stSidebarCollapseButton"]{
        background:var(--ds-bg) !important; color:var(--ds-text) !important; }
      [data-testid="stSidebarHeader"]{ background:var(--ds-bg) !important; }
      [data-testid="stToolbarActions"] *, [data-testid="stActionButton"] *,
      [data-testid="stStatusWidget"] *, [data-testid="stMainMenu"] *{
        background:transparent !important; color:var(--ds-text) !important; }
      [data-testid="stSidebarCollapsedControl"] button,
      [data-testid="stExpandSidebarButton"] button,
      [data-testid="stBaseButton-headerNoPadding"],
      [data-testid="stBaseButton-header"]{
        background:var(--ds-surface) !important; border:1px solid var(--ds-border) !important;
        color:var(--ds-text) !important; }
      [data-testid="stSidebarCollapsedControl"] svg,
      [data-testid="stExpandSidebarButton"] svg,
      [data-testid="stHeader"] svg, [data-testid="stToolbar"] svg{
        fill:var(--ds-text) !important; color:var(--ds-text) !important; }
      [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] *,
      p, li, span, label{ color:var(--ds-text) !important; }
      h1,h2,h3,h4,h5,h6,
      [data-testid="stMarkdownContainer"] strong{ color:#fbfaf7 !important; }
      /* 보조 설명은 한 단계 낮춰 위계를 만든다(흐릿해서 안 보이면 안 됨) */
      .stCaption, [data-testid="stCaptionContainer"],
      [data-testid="stCaptionContainer"] *{ color:var(--ds-text2) !important; }
      a, a:visited{ color:#e08a63 !important; }
      /* 알림/카드/펼치기 — 배경보다 살짝 밝은 한 단계 위 면(surface) */
      [data-testid="stAlert"]{ background:var(--ds-surface) !important;
        border:1px solid var(--ds-border) !important; }
      [data-testid="stAlert"] *{ color:var(--ds-text) !important; }
      [data-testid="stExpander"], [data-testid="stExpander"] details{
        background:var(--ds-surface) !important; border-color:var(--ds-border) !important; }
      /* 펼침 헤더(summary) — 기본/hover/focus 가 밝은 값으로 남아 흰 띠로 보였음 */
      [data-testid="stExpander"] summary,
      [data-testid="stExpander"] details[open] > summary,
      [data-testid="stExpander"] summary:hover,
      [data-testid="stExpander"] summary:focus,
      [data-testid="stExpander"] summary:active{
        background:var(--ds-surface) !important; color:var(--ds-text) !important; }
      [data-testid="stExpander"] summary:hover{ background:var(--ds-surface2) !important; }
      [data-testid="stExpander"] summary *,
      [data-testid="stExpander"] summary svg{
        color:var(--ds-text) !important; fill:var(--ds-text) !important; }
      div[data-testid="stVerticalBlockBorderWrapper"]{
        background:var(--ds-surface) !important; border-color:var(--ds-border) !important; }
      /* 입력 요소 */
      input, textarea, [data-baseweb="select"]>div, [data-baseweb="input"]>div{
        background:var(--ds-surface) !important; color:var(--ds-text) !important;
        border-color:var(--ds-border) !important; }
      /* 입력칸 안내문구(placeholder) — 배경이 어두워지며 거의 안 보이게 됨.
         브라우저가 기본 opacity를 걸어둬서 opacity:1 도 같이 줘야 한다. */
      input::placeholder, textarea::placeholder,
      input::-webkit-input-placeholder, textarea::-webkit-input-placeholder{
        color:#a09d96 !important; opacity:1 !important; }
      [data-baseweb="select"] [class*="placeholder"],
      [data-baseweb="select"] [class*="Placeholder"]{
        color:#a09d96 !important; }
      /* 표(st.dataframe / st.data_editor) — 캔버스로 그려서 CSS 변수로만 바뀜 */
      [data-testid="stDataFrame"], [data-testid="stTable"],
      [data-testid="stDataFrameResizable"]{
        background:var(--ds-surface) !important;
        --gdg-bg-cell:var(--ds-surface); --gdg-bg-cell-medium:var(--ds-surface2);
        --gdg-bg-header:var(--ds-surface2); --gdg-bg-header-hovered:var(--ds-surface2);
        --gdg-bg-header-has-focus:var(--ds-surface2);
        --gdg-text-dark:var(--ds-text); --gdg-text-medium:var(--ds-text);
        --gdg-text-light:var(--ds-text2); --gdg-text-header:var(--ds-text);
        --gdg-border-color:var(--ds-border); --gdg-horizontal-border-color:var(--ds-border);
        --gdg-accent-color:var(--ds-accent); --gdg-accent-light:#3a322c;
        --gdg-bg-bubble:var(--ds-surface2); --gdg-bg-search-result:#4a3a2c; }
      [data-testid="stTable"] th, [data-testid="stTable"] td{
        background:var(--ds-surface) !important; color:var(--ds-text) !important;
        border-color:var(--ds-border) !important; }
      /* 탭(주간취합·업무보고 등) */
      [data-baseweb="tab-list"]{ background:transparent !important;
        border-bottom-color:var(--ds-border) !important; }
      [data-baseweb="tab"]{ background:transparent !important;
        color:var(--ds-text2) !important; }
      [data-baseweb="tab"][aria-selected="true"]{ color:var(--ds-text) !important; }
      [data-baseweb="tab-highlight"]{ background:var(--ds-accent) !important; }
      /* 파일 업로더(문서 협업) — 기본 드롭존이 흰색 */
      [data-testid="stFileUploader"] section,
      [data-testid="stFileUploaderDropzone"]{
        background:var(--ds-surface) !important; border-color:var(--ds-border) !important; }
      [data-testid="stFileUploader"] *{ color:var(--ds-text) !important; }
      /* 지표·토스트·라디오 */
      [data-testid="stMetric"]{ background:transparent !important; }
      [data-testid="stMetricValue"], [data-testid="stMetricLabel"] *{
        color:var(--ds-text) !important; }
      [data-testid="stToast"]{ background:var(--ds-surface2) !important;
        color:var(--ds-text) !important; border:1px solid var(--ds-border) !important; }
      [data-testid="stToast"] *{ color:var(--ds-text) !important; }
      [data-testid="stDialog"] > div, [role="dialog"]{
        background:var(--ds-surface) !important; color:var(--ds-text) !important; }
      /* 버튼 — 폼 안의 버튼은 stButton이 아니라 stFormSubmitButton이라 좁게 잡으면
         '보내기'만 흰 박스로 남는다. 다운로드·링크 버튼까지 한 번에 잡는다. */
      div.stButton>button, div[data-testid="stButton"] button,
      div[data-testid="stFormSubmitButton"] button,
      div[data-testid="stDownloadButton"] button,
      div[data-testid="stLinkButton"] a, button[data-testid^="stBaseButton"]{
        background:var(--ds-surface) !important; border-color:var(--ds-border) !important;
        color:var(--ds-text) !important; }
      div.stButton>button:hover, div[data-testid="stFormSubmitButton"] button:hover,
      div[data-testid="stDownloadButton"] button:hover,
      div[data-testid="stLinkButton"] a:hover{
        border-color:#d97757 !important; color:#fff !important; }
      div.stButton>button[kind="primary"],
      div[data-testid="stFormSubmitButton"] button[kind="primary"],
      button[data-testid="stBaseButton-primary"],
      button[data-testid="stBaseButton-primaryFormSubmit"]{
        background:var(--ds-accent) !important; border-color:var(--ds-accent) !important;
        color:#fff !important; }
      /* 항목 옆 작은 기호 버튼(✎ 수정 · ✕ 회수)은 또렷하게 */
      [class*="st-key-req_edit_btn_"] button, [class*="st-key-req_del_"] button,
      [class*="st-key-todo_star_"] button{
        color:var(--ds-text) !important; font-size:1rem !important; }
      /* 머리글 옆 ＋ 는 다크에서도 테두리·배경 없이(위 버튼 규칙보다 뒤에 와야 함) */
      [class*="st-key-todo_add_btn"] button, [class*="st-key-care_add_btn"] button,
      [class*="st-key-per_add_btn"] button, [class*="st-key-todo_sort_btn"] button{
        background:transparent !important; border:none !important;
        box-shadow:none !important; color:#e08a63 !important; }
      [class*="st-key-req_del_"] button:hover{ color:#ff8a72 !important;
        border-color:#ff8a72 !important; }
      hr{ border-color:var(--ds-border) !important; }
      /* 드롭다운·달력 팝업 — 앱 밖(body 포털)에 그려져서 따로 지정해야 함.
         내부 구조(헤더·주차행·빈칸)가 여러 겹이라 하나씩 잡으면 계속 흰 칸이
         남는다 → 팝업 하위 전체를 같은 색으로 덮고, 강조(선택·hover)만 되살린다. */
      [data-baseweb="popover"], [data-baseweb="popover"] *,
      [data-baseweb="calendar"], [data-baseweb="calendar"] *,
      [data-baseweb="datepicker"], [data-baseweb="datepicker"] *,
      [data-baseweb="tooltip"], [data-baseweb="tooltip"] *,
      [data-baseweb="menu"], [data-baseweb="menu"] *{
        background-color:var(--ds-surface) !important; color:var(--ds-text) !important;
        border-color:var(--ds-border) !important; }
      /* 선택된 날짜/항목은 주황으로 되살림(위 일괄 규칙에 묻히지 않게) */
      [data-baseweb="calendar"] [aria-selected="true"],
      [data-baseweb="popover"] li[aria-selected="true"],
      [data-baseweb="calendar"] div[aria-label*="선택"]{
        background-color:var(--ds-accent) !important; color:#fff !important; }
      [data-baseweb="popover"] li[role="option"]:hover,
      [data-baseweb="calendar"] [role="gridcell"]:hover{
        background-color:var(--ds-surface2) !important; }
      /* 이번 달이 아닌 날짜·비활성 항목은 흐리게 */
      [data-baseweb="calendar"] [aria-disabled="true"],
      [data-baseweb="calendar"] [data-outside-month="true"]{
        color:#8f8c85 !important; }
      /* 선택된 항목 칩(멀티셀렉트) */
      [data-baseweb="tag"]{ background:var(--ds-surface2) !important; color:var(--ds-text) !important; }
      [data-baseweb="tag"] *{ color:var(--ds-text) !important; }
      /* 도움말 툴팁(? 아이콘·버튼 help) — BaseWeb 툴팁과 별개 요소라 따로 지정해야
         흰 박스에 흰 글씨로 남는다. role=tooltip 까지 함께 덮어 새는 곳을 막는다. */
      [data-testid="stTooltipContent"], [data-testid="stTooltipContent"] *,
      [data-testid="stTooltipHoverTarget"] + div,
      [role="tooltip"], [role="tooltip"] *{
        background:var(--ds-surface2) !important; color:var(--ds-text) !important;
        border-color:var(--ds-border) !important; }
      /* 코드 표시(`아이디` 같은 백틱·st.code) — 밝은 배경이 남아 글씨가 묻힘 */
      code, kbd, pre, [data-testid="stCode"], [data-testid="stCode"] pre,
      [data-testid="stCodeBlock"], [data-testid="stCodeBlock"] pre{
        background:var(--ds-surface) !important; border-color:var(--ds-border) !important; }
      code, code span, pre, pre span, kbd,
      [data-testid="stCode"] *, [data-testid="stCodeBlock"] *{
        color:var(--ds-text) !important; }
      /* 완료 체크박스 — 밝은 흰 박스가 튀지 않게 */
      [data-testid="stCheckbox"] [data-baseweb="checkbox"] div[role="presentation"]{
        background:var(--ds-surface) !important; border-color:#5c5c57 !important; }
      [data-testid="stCheckbox"] input:checked + div div[role="presentation"],
      [data-testid="stCheckbox"] [aria-checked="true"] div[role="presentation"]{
        background:var(--ds-accent) !important; border-color:var(--ds-accent) !important; }
      /* 사이드바도 같은 계열로(갈색 → 중성) */
      /* 사이드바는 본문보다 한 톤 더 어둡게 — 면이 구분돼야 메뉴가 떠 보임 */
      section[data-testid="stSidebar"]{ background:#0e0e0d !important; }
      section[data-testid="stSidebar"] *{ color:var(--ds-text) !important; }
      section[data-testid="stSidebar"] .navcat{ color:#a8a59e !important; }
      section[data-testid="stSidebar"] .stButton>button:hover{
        background:var(--ds-surface2) !important; }
      section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
        background:var(--ds-accent) !important; color:#fff !important; }
      section[data-testid="stSidebar"] .st-key-theme_btn button{
        background:var(--ds-surface2) !important; border-color:var(--ds-border) !important; }
      /* 스크롤바도 다크 */
      ::-webkit-scrollbar{ width:12px; height:12px; }
      ::-webkit-scrollbar-track{ background:var(--ds-bg); }
      ::-webkit-scrollbar-thumb{ background:var(--ds-surface2); border-radius:6px; }
      ::-webkit-scrollbar-thumb:hover{ background:#5c5c57; }
      *{ scrollbar-color:var(--ds-surface2) var(--ds-bg); }
    </style>""", unsafe_allow_html=True)

    mode_options = ["🏠 홈", "🖥️ 주간취합", "📝 업무보고 작성·취합",
                    "🏠 스마트돌봄스페이스", "🛒 구매요청서", "📋 문서 협업",
                    "📁 자료실", "🔧 장비 사용현황", "📍 실증 방문 일지",
                    "📚 과거 회의록 열람", "💡 개선 요청"]
    if st.session_state.get("is_admin"):
        mode_options.append("👤 회원 관리")
    # 홈 바로가기(HTML 타일)의 ?go= 처리 — 메뉴 이동 또는 공지 토글 (radio 생성 전에)
    _go = st.query_params.get("go")
    if _go is not None:
        try:
            del st.query_params["go"]
        except Exception:
            pass
        if _go == "notice":
            st.session_state["home_notice_open"] = \
                not st.session_state.get("home_notice_open", False)
            st.session_state["main_menu"] = "🏠 홈"
        elif _go == "cal":
            st.session_state["home_cal_open"] = \
                not st.session_state.get("home_cal_open", False)
            st.session_state["main_menu"] = "🏠 홈"
        elif _go in ("care_open", "care_close", "todo_open", "todo_close"):
            _nm, _act = _go.rsplit("_", 1)   # 명시적 열기/닫기(토글 아님)
            st.session_state[f"{_nm}_add_open"] = (_act == "open")
            st.session_state["main_menu"] = "🏠 홈"
        elif _go in mode_options:
            st.session_state["main_menu"] = _go

    with st.sidebar:
        st.markdown(_brand("sidebar"), unsafe_allow_html=True)
        # 🌙/☀️ 테마 전환 — 버튼(토글 스위치는 어두운 사이드바에서 켜짐/꺼짐이
        # 구분되지 않아 글씨로 상태가 보이는 버튼으로 대체). 선택은 계정별 저장.
        _is_dark = bool(st.session_state.get("dark"))
        if st.button("☀️ 라이트 모드로" if _is_dark else "🌙 다크 모드로",
                     key="theme_btn", use_container_width=True,
                     help="화면 밝기 테마를 바꿉니다(다음 접속에도 유지)"):
            st.session_state["dark"] = not _is_dark
            try:
                todo_store.set_sync(st.session_state.get("uid", ""), "theme",
                                    "light" if _is_dark else "dark")
            except Exception:
                pass
            st.rerun()
        # 홈의 바로가기 버튼(_nav_to)이 있으면 그 메뉴로 이동
        nav = st.session_state.pop("_nav_to", None)
        if nav and nav in mode_options:
            st.session_state["main_menu"] = nav
        mode = st.session_state.get("main_menu", "🏠 홈")
        if mode not in mode_options:
            mode = "🏠 홈"
        # 카테고리별 정리 + 큰 글씨 버튼 네비게이션
        _cats = [("", ["🏠 홈", "🖥️ 주간취합"]),
                 ("업무", ["📝 업무보고 작성·취합", "🛒 구매요청서", "📋 문서 협업"]),
                 ("자료·장비", ["📁 자료실", "🔧 장비 사용현황",
                              "📍 실증 방문 일지", "📚 과거 회의록 열람"]),
                 ("스페이스", ["🏠 스마트돌봄스페이스"]),
                 ("앱", ["💡 개선 요청"])]
        if st.session_state.get("is_admin"):
            _cats.append(("관리자", ["👤 회원 관리"]))
        for _cat, _items in _cats:
            if _cat:
                st.markdown(f"<div class='navcat'>{_cat}</div>",
                            unsafe_allow_html=True)
            for _opt in _items:
                if _opt not in mode_options:
                    continue
                if st.button(_opt, key=f"nav_{_opt}", use_container_width=True,
                             type="primary" if _opt == mode else "secondary"):
                    st.session_state["main_menu"] = _opt
                    st.rerun()
        st.divider()
        _who = st.session_state.get("me", "")
        _wt = st.session_state.get("title", "")
        st.caption(f"👤 {_who}" + (f" · {_wt}" if _wt else "")
                   + (" · 관리자" if st.session_state.get("is_admin") else ""))
        if st.session_state.get("is_admin"):
            try:
                _np = sum(1 for a in account_store.all_accounts()
                          if a["상태"].strip() == account_store.ST_PENDING)
            except Exception:
                _np = 0
            if _np:
                st.caption(f"🔔 가입 승인 대기 {_np}명 → '👤 회원 관리'")
        if st.button("로그아웃"):
            for _k in ("authed", "uid", "me", "title", "tok", "is_admin"):
                st.session_state.pop(_k, None)
            st.session_state["_ls_clear"] = True   # 저장된 자동로그인 정보 삭제
            st.query_params.clear()
            st.rerun()

    if mode == "🏠 홈":
        home_page()
    elif mode == "🖥️ 주간취합":
        meeting_page()
    elif mode == "📝 업무보고 작성·취합":
        member_page()
    elif mode == "🏠 스마트돌봄스페이스":
        space_page()
    elif mode == "💡 개선 요청":
        feedback_page()
    elif mode == "📍 실증 방문 일지":
        visit_page()
    elif mode == "🛒 구매요청서":
        purchase_page()
    elif mode == "📋 문서 협업":
        collab_page()
    elif mode == "📁 자료실":
        resource_page()
    elif mode == "🔧 장비 사용현황":
        equip_page()
    elif mode == "👤 회원 관리":
        _member_admin()
    else:
        history_page()


if __name__ == "__main__":
    main()
