"""문서 협업 보드 — 구글 문서 링크 + 요청사항 + 제출현황을 시트에 누적.

파일을 앱이 저장하지 않는다(서비스 계정은 드라이브 저장 불가). 실제 문서는
요청자가 만든 구글 시트/문서/슬라이드에 있고, 앱은 그 '링크 + 요청 + 현황'만
기존 제출함 스프레드시트의 '문서협업' 탭에 텍스트로 관리한다.
컬럼이 바뀌면 COLLAB_HEADER만 맞추면 된다.
"""
import json
import re
import gspread
import streamlit as st
from datetime import datetime

from sheets_store import _get_client, KST

COLLAB_WS_TITLE = "문서협업"
COLLAB_HEADER = ["요청ID", "등록일시", "요청자", "제목", "요청사항", "문서링크",
                 "마감일", "담당자", "완료자", "상태"]

STATUS_OPEN = "진행중"
STATUS_CLOSED = "완료"


class RequestNotFound(Exception):
    """해당 요청ID의 행을 시트에서 찾지 못함."""


class OAuthNotConfigured(Exception):
    """secrets에 [google_oauth] 가 없음 — 파일 자동 업로드 비활성."""


# 업로드 확장자 → (원본 MIME, 변환될 구글 문서 MIME)
_CONVERT = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "application/vnd.google-apps.spreadsheet"),
    "xls": ("application/vnd.ms-excel", "application/vnd.google-apps.spreadsheet"),
    "csv": ("text/csv", "application/vnd.google-apps.spreadsheet"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "application/vnd.google-apps.document"),
    "doc": ("application/msword", "application/vnd.google-apps.document"),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation",
             "application/vnd.google-apps.presentation"),
    "ppt": ("application/vnd.ms-powerpoint", "application/vnd.google-apps.presentation"),
}
DRIVE_EXTS = list(_CONVERT.keys())


def drive_enabled() -> bool:
    """[google_oauth] secrets가 있으면 파일 업로드→구글문서 자동변환 가능."""
    try:
        return "google_oauth" in st.secrets
    except Exception:
        return False


def _oauth_session():
    if not drive_enabled():
        raise OAuthNotConfigured()
    # 지연 임포트: 이 모듈들(requests 의존)이 없는 환경에서도 앱 로딩은 되게
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request, AuthorizedSession
    o = st.secrets["google_oauth"]
    creds = Credentials(None, refresh_token=o["refresh_token"],
                        client_id=o["client_id"], client_secret=o["client_secret"],
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/drive.file"])
    creds.refresh(Request())
    return AuthorizedSession(creds)


_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
_MULTIPART_MAX = 4 * 1024 * 1024      # 여유를 둔 값(구글 실제 한도 5MB)


def drive_upload(sess, meta: dict, data: bytes, mime: str) -> dict:
    """드라이브에 파일을 올리고 {id, webViewLink} 를 돌려준다.

    ⚠️ **`uploadType=multipart` 는 5MB 한도다.** 152MB 엑셀을 올렸다가
       `413 Client Error: Request Entity Too Large` 를 받았다(2026-08 확인).
       그래서 큰 파일은 **resumable**(업로드 세션을 먼저 열고 본문을 PUT)로 보낸다.
    청크로 쪼개지는 않는다 — 끊겼을 때 이어붙이는 처리가 따로 필요해서,
    1단계에서는 한 번에 PUT 한다.
    """
    if len(data) <= _MULTIPART_MAX:
        b = "carebotdocboundary"
        head = ("--" + b + chr(13) + chr(10)
                + "Content-Type: application/json; charset=UTF-8"
                + chr(13) + chr(10) + chr(13) + chr(10)
                + json.dumps(meta) + chr(13) + chr(10)
                + "--" + b + chr(13) + chr(10)
                + "Content-Type: " + mime
                + chr(13) + chr(10) + chr(13) + chr(10))
        tail = chr(13) + chr(10) + "--" + b + "--"
        body = head.encode("utf-8") + data + tail.encode("utf-8")
        r = sess.post(_UPLOAD_URL + "?uploadType=multipart"
                      "&fields=id,webViewLink", data=body,
                      headers={"Content-Type":
                               "multipart/related; boundary=" + b})
        r.raise_for_status()
        return r.json()

    r = sess.post(_UPLOAD_URL + "?uploadType=resumable&fields=id,webViewLink",
                  json=meta,
                  headers={"X-Upload-Content-Type": mime,
                           "X-Upload-Content-Length": str(len(data))})
    r.raise_for_status()
    loc = r.headers.get("Location")
    if not loc:
        raise RuntimeError("업로드 세션을 열지 못했습니다(Location 헤더 없음).")
    r2 = sess.put(loc, data=data,
                  headers={"Content-Type": mime,
                           "Content-Length": str(len(data))})
    r2.raise_for_status()
    return r2.json()


def create_drive_doc(file_bytes: bytes, filename: str) -> str:
    """업로드 파일(엑셀/워드/PPT)을 구글 문서로 변환·생성하고 '링크가 있는 사용자
    편집' 공유를 건 뒤 편집 링크를 반환. (소유자=연결된 본인 계정, 본인 드라이브에 보관)"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _CONVERT:
        raise ValueError(f"지원하지 않는 형식(.{ext}) — 엑셀·워드·PPT만 됩니다.")
    src_mime, dst_mime = _CONVERT[ext]
    name = filename.rsplit(".", 1)[0]
    sess = _oauth_session()
    info = drive_upload(sess, {"name": name, "mimeType": dst_mime},
                        file_bytes, src_mime)
    fid = info["id"]
    # 팀원이 편집할 수 있게 '링크가 있는 사용자 편집' 공유
    sess.post(f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
              json={"role": "writer", "type": "anyone"})
    return info.get("webViewLink") or f"https://drive.google.com/open?id={fid}"


@st.cache_resource
def _ws():
    """제출함 스프레드시트의 '문서협업' 탭 (없으면 생성, 헤더 자동 보정)."""
    ss = _get_client().open_by_key(st.secrets["sheet"]["id"])
    try:
        ws = ss.worksheet(COLLAB_WS_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=COLLAB_WS_TITLE, rows=1000,
                              cols=len(COLLAB_HEADER))
        ws.append_row(COLLAB_HEADER)
        return ws
    if ws.col_count < len(COLLAB_HEADER):
        ws.add_cols(len(COLLAB_HEADER) - ws.col_count)
    if ws.row_values(1) != COLLAB_HEADER:
        end = gspread.utils.rowcol_to_a1(1, len(COLLAB_HEADER))
        ws.update(values=[COLLAB_HEADER], range_name=f"A1:{end}")
    return ws


@st.cache_data(ttl=60)
def collab_rows() -> list:
    vals = _ws().get_all_values()
    out = []
    for r in vals[1:]:
        if not any(c.strip() for c in r):
            continue
        out.append((list(r) + [""] * len(COLLAB_HEADER))[:len(COLLAB_HEADER)])
    return out


def add_collab(requester: str, title: str, request_text: str, link: str,
               deadline: str, assignees: list) -> str:
    ws = _ws()
    now = datetime.now(KST)
    req_id = now.strftime("%Y%m%d-%H%M%S-") + requester
    row = [req_id, now.strftime("%Y-%m-%d %H:%M"), requester, title, request_text,
           link, deadline, ", ".join(assignees) if assignees else "전체",
           "", STATUS_OPEN]
    ws.append_row(row, value_input_option="USER_ENTERED")
    collab_rows.clear()
    return req_id


def _find_row(ws, req_id: str):
    for i, r in enumerate(ws.get_all_values(), start=1):
        if i > 1 and r and r[0] == req_id:
            return i, r
    raise RequestNotFound(req_id)


def mark_done(req_id: str, member: str) -> list:
    """'완료자'(I열)에 member 추가 (중복 방지). 반환: 완료자 목록."""
    ws = _ws()
    i, r = _find_row(ws, req_id)
    cur = (r[8] if len(r) > 8 else "").strip()
    names = [n.strip() for n in cur.split(",") if n.strip()]
    if member not in names:
        names.append(member)
    ws.update_cell(i, 9, ", ".join(names))  # I열 = 완료자
    collab_rows.clear()
    return names


def set_status(req_id: str, status: str) -> None:
    """상태(J열)를 진행중/완료로 변경."""
    ws = _ws()
    i, _ = _find_row(ws, req_id)
    ws.update_cell(i, 10, status)  # J열 = 상태
    collab_rows.clear()


def delete_collab(req_id: str) -> None:
    """협업 요청을 보드(시트)에서 삭제. 구글 드라이브의 실제 문서는 건드리지 않음."""
    ws = _ws()
    i, _ = _find_row(ws, req_id)
    ws.delete_rows(i)
    collab_rows.clear()

_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]{20,})|[?&]id=([A-Za-z0-9_-]{20,})")


def file_id(link: str) -> str:
    """구글 문서 링크에서 파일 ID만 뽑는다(못 뽑으면 빈 문자열)."""
    m = _ID_RE.search(link or "")
    return (m.group(1) or m.group(2)) if m else ""


@st.cache_data(ttl=300, show_spinner=False)
def doc_activity(link: str) -> dict:
    """문서가 실제로 고쳐졌는지 — {modified, count, named, anon}.

    ⚠️ **누가 고쳤는지는 대개 알 수 없다**(2026-08 실측). 실제 협업 시트의 편집
       이력 9건 중 7건에 사용자 정보가 없었다 — '링크가 있는 사람 편집'으로 연
       사람이 구글에 로그인돼 있지 않으면 구글이 이름을 안 남긴다.
       그래서 이름은 **잡히는 것만** 주고(`named`), 나머지는 수만 센다(`anon`).
    ⚠️ 이것은 '편집 흔적'이지 '완료'가 아니다. 한 글자만 고쳐도 잡힌다.
    ⚠️ 우리 앱이 만든 문서만 조회된다(OAuth 범위 `drive.file`). 남이 만든 문서·
       OneDrive 링크는 권한이 없어 빈 값이 온다(오류 아님).
    """
    empty = {"modified": "", "count": 0, "named": [], "anon": 0}
    fid = file_id(link)
    if not fid or not drive_enabled():
        return empty
    try:
        sess = _oauth_session()
        r = sess.get(
            f"https://www.googleapis.com/drive/v3/files/{fid}/revisions",
            params={"fields": "revisions(modifiedTime,lastModifyingUser(displayName,emailAddress))", "pageSize": 1000})
        if r.status_code != 200:
            return empty
        revs = r.json().get("revisions", [])
        named, anon = {}, 0
        for rev in revs:
            u = rev.get("lastModifyingUser") or {}
            em = (u.get("emailAddress") or "").strip().lower()
            nm = (u.get("displayName") or "").strip()
            t = (rev.get("modifiedTime") or "")[:10]
            if not (em or nm):
                anon += 1
                continue
            named[em or nm] = {"name": nm, "email": em, "time": t}
        return {"modified": max((x.get("modifiedTime", "") for x in revs),
                                default="")[:10],
                "count": len(revs), "anon": anon,
                "named": sorted(named.values(),
                                key=lambda x: x["time"], reverse=True)}
    except Exception:
        return empty
