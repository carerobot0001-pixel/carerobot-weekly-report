"""제출함 구글시트 전체(모든 탭)를 엑셀 한 파일로 만들어 NAS 와 구글 드라이브에 함께 저장한다.

매주 월요일 09:00 에 이 PC 의 작업 스케줄러("DolbomStudio NAS 백업")가 실행한다.

⚠️ NAS 에서는 **백업 폴더 하나(`DolbomStudio_백업`)만** 만들고 그 안에만 쓴다.
   다른 폴더는 만들지도 고치지도 않고, 옛 백업도 지우지 않는다(사용자 지시 2026-10-16).
⚠️ NAS 위치는 `backup_config.json` 의 `nas_parent`(git 제외 — 내부망 주소라서).
   이 PC 가 NAS 에 로그인(자격 증명 저장)돼 있어야 쓸 수 있다.
⚠️ 드라이브는 carerobot0001 계정(앱의 `[google_oauth]`)의 `DolbomStudio_백업` 폴더에
   **같은 xlsx 를 그대로** 올린다(2026-10-26 추가). **공유를 걸지 않는다** — 계정 탭
   (가입 이메일·비밀번호 해시)·피험자명이 들어 있어 소유자만 봐야 한다. 옛 백업도 안 지운다.
   NAS 와 드라이브는 **따로** 시도한다 — 한쪽이 실패해도 다른 쪽에는 남는다.

결과는 `backup_log.txt`(이 폴더, git 제외)와 팀 시트(`_team` / `nas_backup`)에 남는다.
앱 홈의 🗄️ 전체 데이터 백업 칸에 '마지막 자동 백업'으로 보인다 — 조용히 실패하지 않게.

수동 실행:  python backup_to_nas.py            (설정된 NAS + 드라이브로)
            python backup_to_nas.py <폴더>     (시험용 — 그 폴더 아래에 백업 폴더를 만든다.
                                                드라이브에는 안 올린다)
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
CFG = ROOT / "backup_config.json"
LOG = ROOT / "backup_log.txt"
FOLDER = "DolbomStudio_백업"

_FILES_URL = "https://www.googleapis.com/drive/v3/files"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{_now()} {msg}\n")


def _record(msg: str) -> None:
    """팀 시트에 결과 한 줄 — 앱 화면에서 보이게. 실패해도 백업 자체엔 영향 없음."""
    try:
        import todo_store
        todo_store.set_sync("_team", "nas_backup", f"{_now()} {msg}")
    except Exception as e:
        _log(f"(팀 시트 기록 실패: {e})")


def _to_nas(parent: str, name: str, data: bytes) -> str:
    """NAS 백업 폴더에 쓰고 결과 한마디를 돌려준다(화면용). 자세한 내용은 로그에."""
    if not parent:
        _log("실패: NAS 위치가 설정되지 않음 (backup_config.json 의 nas_parent)")
        return "NAS 실패(위치 미설정)"
    base = Path(parent)
    if not base.is_dir():             # 없는 경로를 새로 만들지 않는다
        _log(f"실패: NAS 위치에 접근할 수 없음 — {parent} (이 PC가 NAS에 로그인돼 있는지 확인)")
        return "NAS 실패(접근 불가 — PC 꺼짐·NAS 로그인 확인)"
    try:
        dest = base / FOLDER
        dest.mkdir(exist_ok=True)     # 이 폴더 하나만 만든다
        out = dest / name
        out.write_bytes(data)
    except Exception as e:
        _log(f"실패: NAS 저장 — {type(e).__name__}: {e}")
        return f"NAS 실패({type(e).__name__})"
    _log(f"성공: {out} ({len(data) // 1024}KB)")
    return "NAS 성공"


def _drive_folder(sess) -> str:
    """드라이브의 `DolbomStudio_백업` 폴더 id. 없으면 만든다(공유 없음).

    OAuth 범위가 `drive.file` 이라 **이 앱이 만든 파일만** 보인다 — 그래서 사람이 같은
    이름으로 만든 폴더를 잘못 집지 않는다. 폴더를 옮겨도 찾는다(부모 조건을 안 건다).
    """
    q = f"name = '{FOLDER}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
    r = sess.get(_FILES_URL, params={"q": q, "fields": "files(id)", "spaces": "drive"})
    r.raise_for_status()
    found = r.json().get("files", [])
    if found:
        return found[0]["id"]
    r = sess.post(_FILES_URL, params={"fields": "id"},
                  json={"name": FOLDER, "mimeType": _FOLDER_MIME})
    r.raise_for_status()
    return r.json()["id"]


def _to_drive(name: str, data: bytes) -> str:
    """같은 xlsx 를 드라이브에 원본 그대로 올린다(구글 시트로 변환하지 않음).

    ⚠️ `permissions` 를 부르지 않는다 — 공유 없이 소유자(carerobot0001)만 본다.
    """
    try:
        from collab_store import _oauth_session, drive_upload
        sess = _oauth_session()
        folder = _drive_folder(sess)
        info = drive_upload(sess, {"name": name, "parents": [folder]}, data, _XLSX_MIME)
    except Exception as e:
        _log(f"실패: 드라이브 업로드 — {type(e).__name__}: {e}")
        return f"드라이브 실패({type(e).__name__})"
    _log(f"성공: 드라이브 {FOLDER}/{name} (id={info.get('id')})")
    return "드라이브 성공"


def main(argv) -> int:
    os.chdir(APP)                     # st.secrets 가 app/.streamlit/secrets.toml 을 읽는다
    sys.path.insert(0, str(APP))
    if len(argv) > 1:
        parent, test = argv[1], True
    else:
        cfg = json.loads(CFG.read_text("utf-8")) if CFG.exists() else {}
        parent, test = (cfg.get("nas_parent") or "").strip(), False
    name = f"돌봄로봇_전체백업_{datetime.now():%Y%m%d_%H%M}.xlsx"
    try:
        from sheets_store import build_full_backup_xlsx
        data = build_full_backup_xlsx()
    except Exception as e:
        _log(f"실패: 백업 파일을 만들지 못함 — {type(e).__name__}: {e}")
        if not test:
            _record(f"실패 — 백업 파일 생성({type(e).__name__})")
        return 1
    results = [_to_nas(parent, name, data)]
    if not test:                      # 시험 실행은 드라이브에 쌓지 않는다
        results.append(_to_drive(name, data))
    ok = all(r.endswith("성공") for r in results)
    if not test:
        _record(f"{'성공' if ok else '실패 있음'} — {' · '.join(results)} · {name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
