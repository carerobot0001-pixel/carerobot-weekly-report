"""제출함 구글시트 전체(모든 탭)를 엑셀 한 파일로 NAS 백업 폴더에 저장한다.

매주 월요일 09:00 에 이 PC 의 작업 스케줄러("DolbomStudio NAS 백업")가 실행한다.

⚠️ NAS 에서는 **백업 폴더 하나(`DolbomStudio_백업`)만** 만들고 그 안에만 쓴다.
   다른 폴더는 만들지도 고치지도 않고, 옛 백업도 지우지 않는다(사용자 지시 2026-10-16).
⚠️ NAS 위치는 `backup_config.json` 의 `nas_parent`(git 제외 — 내부망 주소라서).
   이 PC 가 NAS 에 로그인(자격 증명 저장)돼 있어야 쓸 수 있다.

결과는 `backup_log.txt`(이 폴더, git 제외)와 팀 시트(`_team` / `nas_backup`)에 남는다.
앱 홈의 🗄️ 전체 데이터 백업 칸에 '마지막 NAS 백업'으로 보인다 — 조용히 실패하지 않게.

수동 실행:  python backup_to_nas.py            (설정된 NAS 로)
            python backup_to_nas.py <폴더>     (시험용 — 그 폴더 아래에 백업 폴더를 만든다)
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


def main(argv) -> int:
    os.chdir(APP)                     # st.secrets 가 app/.streamlit/secrets.toml 을 읽는다
    sys.path.insert(0, str(APP))
    if len(argv) > 1:
        parent, test = argv[1], True
    else:
        cfg = json.loads(CFG.read_text("utf-8")) if CFG.exists() else {}
        parent, test = (cfg.get("nas_parent") or "").strip(), False
    if not parent:
        _log("실패: NAS 위치가 설정되지 않음 (backup_config.json 의 nas_parent)")
        _record("실패 — NAS 위치 미설정")
        return 2
    base = Path(parent)
    if not base.is_dir():             # 없는 경로를 새로 만들지 않는다
        _log(f"실패: NAS 위치에 접근할 수 없음 — {parent} (이 PC가 NAS에 로그인돼 있는지 확인)")
        _record("실패 — NAS에 접근할 수 없음(PC 꺼짐·NAS 로그인 확인)")
        return 3
    try:
        from sheets_store import build_full_backup_xlsx
        data = build_full_backup_xlsx()
        dest = base / FOLDER
        dest.mkdir(exist_ok=True)     # 이 폴더 하나만 만든다
        out = dest / f"돌봄로봇_전체백업_{datetime.now():%Y%m%d_%H%M}.xlsx"
        out.write_bytes(data)
    except Exception as e:
        _log(f"실패: {type(e).__name__}: {e}")
        if not test:
            _record(f"실패 — {type(e).__name__}")
        return 1
    _log(f"성공: {out} ({len(data) // 1024}KB)")
    if not test:
        _record(f"성공 — {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
