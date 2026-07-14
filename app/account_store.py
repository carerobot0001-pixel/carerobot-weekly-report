"""개인 계정 — 구글시트 '계정' 탭. 회원가입(관리자 승인) + 로그인.

비밀번호는 절대 평문 저장 안 함(pbkdf2-sha256 해시). 새로고침 로그인 유지는
비번해시 기반 토큰(?uid=&tok=)으로 — DB 없이는 계산 불가라 위조 불가.
컬럼이 바뀌면 ACC_HEADER만 맞추면 됨(_ws가 헤더 자동 보정).
"""
import os
import hashlib
import binascii
from datetime import datetime

import gspread
import streamlit as st

from sheets_store import _get_client, KST

ACC_WS = "계정"
ACC_HEADER = ["아이디", "비번", "이름", "직함", "이메일_korea", "이메일_gmail",
              "상태", "가입일시", "승인일시"]
_COL_STATUS = ACC_HEADER.index("상태") + 1        # 상태 열(1-indexed)
_COL_APPROVED = ACC_HEADER.index("승인일시") + 1  # 승인일시 열
ST_PENDING, ST_OK, ST_REJECT = "대기", "승인", "거부"


@st.cache_resource
def _ws():
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(ACC_WS)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=ACC_WS, rows=200, cols=len(ACC_HEADER))
        ws.append_row(ACC_HEADER)
        return ws
    if ws.col_count < len(ACC_HEADER):
        ws.add_cols(len(ACC_HEADER) - ws.col_count)
    if ws.row_values(1) != ACC_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(ACC_HEADER))
        ws.update(values=[ACC_HEADER], range_name=f"A1:{end}")
    return ws


def _hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 100_000)
    return ("pbkdf2$100000$" + binascii.hexlify(salt).decode()
            + "$" + binascii.hexlify(dk).decode())


def _verify_pw(pw: str, stored: str) -> bool:
    try:
        _algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"),
                                 binascii.unhexlify(salt_hex), int(iters))
        return binascii.hexlify(dk).decode() == hash_hex
    except Exception:
        return False


def token_for(acc: dict) -> str:
    """새로고침 로그인 유지용 토큰(비번해시 기반). 시트 접근 없이는 계산 불가."""
    raw = (acc.get("아이디", "") + "|" + acc.get("비번", "")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


@st.cache_data(ttl=15)
def _rows():
    vals = _ws().get_all_values()
    out = []
    for i, r in enumerate(vals[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (list(r) + [""] * len(ACC_HEADER))[:len(ACC_HEADER)]
        d = dict(zip(ACC_HEADER, r))
        d["_row"] = i
        out.append(d)
    return out


def get_account(uid: str):
    uid = (uid or "").strip()
    if not uid:
        return None
    for a in _rows():
        if a["아이디"].strip() == uid:
            return a
    return None


def register(uid, pw, name, title, email_korea, email_gmail, admin_ids) -> str:
    """회원가입 신청. 아이디가 admin_ids면 자동 승인. 반환: 상태(대기/승인)."""
    uid = (uid or "").strip()
    if not uid or not pw or not (name or "").strip():
        raise ValueError("아이디·비밀번호·이름은 필수입니다.")
    if get_account(uid):
        raise ValueError("이미 사용 중인 아이디입니다.")
    status = ST_OK if uid in admin_ids else ST_PENDING
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    _ws().append_row(
        [uid, _hash_pw(pw), name.strip(), (title or "").strip(),
         (email_korea or "").strip(), (email_gmail or "").strip(),
         status, now, now if status == ST_OK else ""],
        value_input_option="RAW")
    _rows.clear()
    return status


def login(uid, pw):
    """(계정dict, "") 또는 (None, 사유)."""
    a = get_account(uid)
    if not a or not _verify_pw(pw or "", a["비번"]):
        return None, "아이디 또는 비밀번호가 올바르지 않습니다."
    stt = a["상태"].strip()
    if stt != ST_OK:
        return None, ("관리자 승인 대기 중입니다." if stt == ST_PENDING
                      else "가입이 거부된 계정입니다. 관리자에게 문의하세요.")
    return a, ""


def find_by_identity(name: str, email: str):
    """이름 + (가입 이메일 korea/gmail 중 하나) 일치하는 계정 반환(아이디 찾기용)."""
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name or not email:
        return None
    for a in _rows():
        if a["이름"].strip() == name and email in (
                a["이메일_korea"].strip().lower(),
                a["이메일_gmail"].strip().lower()):
            return a
    return None


def reset_password(uid: str, new_pw: str) -> bool:
    """비밀번호 재설정(새 해시로 덮어씀). 최신 시트에서 아이디로 행 찾음(행밀림 방지)."""
    uid = (uid or "").strip()
    if not uid or not new_pw:
        raise ValueError("아이디와 새 비밀번호가 필요합니다.")
    ws = _ws()
    for i, r in enumerate(ws.get_all_values()[1:], start=2):
        if r and r[0].strip() == uid:
            ws.update_cell(i, ACC_HEADER.index("비번") + 1, _hash_pw(new_pw))
            _rows.clear()
            return True
    return False


def pending():
    return [a for a in _rows() if a["상태"].strip() == ST_PENDING]


def all_accounts():
    return list(_rows())


def set_status(uid: str, status: str) -> None:
    """상태 변경(승인/대기/거부). 캐시 아닌 최신 시트에서 아이디로 행을 찾아 씀(행밀림 방지)."""
    uid = (uid or "").strip()
    if not uid:
        return
    ws = _ws()
    row_idx = None
    for i, r in enumerate(ws.get_all_values()[1:], start=2):
        if r and r[0].strip() == uid:
            row_idx = i
            break
    if row_idx is None:
        return
    ws.update_cell(row_idx, _COL_STATUS, status)
    if status == ST_OK:
        ws.update_cell(row_idx, _COL_APPROVED,
                       datetime.now(KST).strftime("%Y-%m-%d %H:%M"))
    _rows.clear()
