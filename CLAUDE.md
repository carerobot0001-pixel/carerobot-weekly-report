# 돌봄로봇 주간 업무보고 웹앱 — 인수인계 문서

## 무엇을 하는 앱인가

- **목적**: 매주 팀원 10명이 주간 업무보고를 웹으로 입력 → 담당자가 HWPX 취합본을 다운로드해서 주간회의에서 띄움
- **사용자**: 10명 (팀원) + 1명 (담당자/관리자)
- **접속 URL**: https://carerobot-weekly-report.streamlit.app
- **비밀번호**: 팀원 `carerobot` / 담당자 `carerobot-admin` (`app/team_config.py`에서 변경 가능)

## 기술 스택 및 구조

```
┌──────────────────────────────────────────┐
│ Streamlit Cloud (streamlit.app)          │ ← 앱 호스팅
│   └─ GitHub(carerobot0001-pixel/          │
│         carerobot-weekly-report)에서 자동 │
├──────────────────────────────────────────┤
│ Google Sheets ("돌봄로봇_업무보고_제출함")  │ ← 입력 데이터 저장
│   └─ 서비스 계정(streamlit-bot@…)으로 접근 │
├──────────────────────────────────────────┤
│ HWPX 템플릿 (레포 루트의 *.hwpx 파일들)    │ ← 취합본 생성용
└──────────────────────────────────────────┘
```

## 파일 구조

```
돌봄로봇_업무보고_김건양/                    ← 레포 루트
├── CLAUDE.md                               ← 이 문서
├── .gitignore                              ← 비밀파일 차단 규칙
├── 돌봄로봇_업무보고(*.hwpx)                ← HWPX 템플릿들 (과거 주차들)
└── app/                                    ← Streamlit 앱
    ├── streamlit_app.py                    ← 메인 앱 (UI, 라우팅)
    ├── team_config.py                      ← 팀원 10명 + 셀 매핑 + 비밀번호
    ├── sheets_store.py                     ← 구글시트 읽기/쓰기 (업무보고 제출함)
    ├── space_store.py                      ← 스마트돌봄스페이스 외부 시트 연동 (FAQ/관리대장)
    ├── purchase_store.py                   ← 구매요청 시트 누적 + 엑셀 양식 생성
    ├── hwpx_exporter.py                    ← HWPX 취합본 생성
    ├── requirements.txt                    ← 파이썬 의존성
    ├── SETUP.md                            ← 초기 설치 가이드
    ├── .streamlit/
    │   ├── secrets.toml                    ← [비밀] 구글 서비스 계정 키 등
    │   └── secrets.toml.example            ← 예시 템플릿
    └── service_account.json                ← [비밀] 구글 서비스 계정 원본 JSON
```

## 핵심 개념: 셀 매핑 (`team_config.py`)

각 팀원이 HWPX 어느 셀에 내용이 들어갈지 `cells` 딕셔너리로 정의. 형식:

```python
"cells": {
    "필드명": (col, row),             # 기본 검정색, 첫 매치
    "필드명": (col, row, "blue"),      # 파란색
    "필드명": (col, row, "black", 1),  # nth번째 매치 (중복 주소 처리)
}
```

**필드 종류**: `acquired_data`(파란색), `research_done/plan`, `task_done/plan`, `smart_care_space`(백정은), `project_confirmation`(최혜민, Table 1), `research_meeting/director_meeting/mohw_weekly`(최혜민 회의자료).

## 자주 하는 작업

### 팀원 추가/삭제/순서 변경
`app/team_config.py`의 `TEAM_MEMBERS` 리스트 수정 → git push → Streamlit Cloud 자동 재배포.
**주의**: 셀 매핑(`col, row`)은 HWPX 템플릿 구조에 의존. 팀원 추가 시 먼저 템플릿에 행 추가 필요.

### HWPX 템플릿 구조 변경
1. 한글에서 템플릿 편집 → 새 `.hwpx` 파일로 저장 (레포 루트에)
2. 셀 구조 분석:
   ```bash
   cd app && python -c "
   import zipfile, re
   with zipfile.ZipFile('../새템플릿.hwpx') as z:
       xml = z.read('Contents/section0.xml').decode('utf-8')
   # 메인 테이블 셀들 나열
   for m in re.finditer(r'cellAddr colAddr=\"(\d+)\" rowAddr=\"(\d+)\"', xml):
       print(m.group())
   "
   ```
3. `team_config.py`의 `cells` 좌표 수정
4. 기존 HWPX로 테스트 후 push

### 비밀번호 변경
`app/team_config.py` 하단 `APP_PASSWORD`, `ADMIN_PASSWORD` 수정 → push.

### 지난주 데이터를 수동 임포트
`app/_import_0415.py`를 참고해서 `MAIN_BODY_MAPPING`과 `WEEK` 변수만 바꿔 실행. 1회용 스크립트.

### 매주 운영 (담당자)
1. 팀원들이 목~화 사이 웹에서 작성 (수요일 기준이라 수요일 회의 전까지)
2. 담당자: `carerobot-admin` 로그인 → 대시보드에서 제출 현황 확인 → 미제출자 독촉
3. 수요일 회의 전: 대시보드 하단 "HWPX 생성 및 다운로드" → 파일 받아 회의에서 띄움

## 스마트돌봄스페이스 페이지 (2026-06 추가)

사이드바 "🏠 스마트돌봄스페이스" 메뉴 — 팀원 누구나 사용. 탭 2개:

| 탭 | 대상 시트 (운영자) | 동작 |
|----|-------------------|------|
| 📖 사용매뉴얼 FAQ 수집 | "스마트돌봄스페이스 FAQ" (백정은) | FAQ 항목 등록 + 전체 목록 조회 |
| 🔧 관리대장 (문제 접수) | "스마트돌봄스페이스 관련 문제 및 돌봄로봇 관리" 중 `스페이스 관리대장` 탭 (한벼리) | 문제 접수 + 미해결 목록 조회 + **완료 처리** |

- 코드: `app/space_store.py` (시트 연동) + `streamlit_app.py`의 `space_page()`
- **시트 ID는 코드·이 문서에 없음** — secrets `[smart_space]` 섹션(`faq_sheet_id`, `space_sheet_id`)에만 둠.
  레포가 공개라서 ID가 노출되면 외부인이 시트에 접근할 수 있기 때문 (실제 값은 로컬
  `app/.streamlit/secrets.toml`과 Streamlit Cloud Secrets에 있음)
- **각 시트에 서비스 계정(`streamlit-bot@…`)이 '편집자'로 공유되어 있어야 함.** 안 되어 있으면
  앱 화면에 공유 안내가 뜸 (앱이 죽지는 않음)
- 시트 컬럼 구조가 바뀌면 `space_store.py`의 `FAQ_HEADER` / `SPACE_LOG_HEADER`만 맞춰 수정
- 앱이 하는 일: **행 추가 + 조회 + 관리대장 완료 처리**. 완료 처리는 해당 행의
  진행상황(G)/조치일자(H)/조치자(J), 조치 내용 입력 시 조치방안(E) 칸만 수정하며,
  쓰기 직전에 그 행의 '문제' 텍스트를 재확인해 행 밀림을 감지함(`RowMismatch`).
  그 외 수정·삭제는 구글시트에서 직접

## 구매요청서 페이지 (2026-06 추가)

사이드바 "🛒 구매요청서" 메뉴 — 팀원 누구나 사용. 장비·재료 구매요청용.

- 코드: `app/purchase_store.py` + `streamlit_app.py`의 `purchase_page()`
- **별도 시트를 안 만듦** — 업무보고 제출함과 **같은 스프레드시트**(secrets `[sheet] id`)에
  `구매요청` 탭(워크시트)을 자동 생성해 사용. 서비스 계정이 이미 편집자라 추가 공유·secrets 불필요.
- 입력: 요청자 + 구매사유 + **품목 표**(`st.data_editor`, 동적 행). 단가×수량=합계, 총액 자동 계산.
- 저장: **한 번의 요청 = 품목 여러 행**, 같은 `요청ID`(`YYYYMMDD-HHMMSS-이름`)로 묶음.
  `구글시트에 저장`은 행 append, `엑셀 양식 다운로드`는 첨부 구매요청서와 같은 xlsx 생성(openpyxl).
- 컬럼 구조가 바뀌면 `purchase_store.py`의 `PURCHASE_HEADER`(시트) / `XLSX_HEADER`(엑셀) 수정.
- 누적 목록은 요청ID별로 묶어 **처리 대기 / 구매완료**로 나눠 표시.
- **구매완료 처리**(진행상황·처리일자·처리자 기록)는 **담당자(admin)만** 가능 —
  요청 단위(같은 요청ID 전체 행)로 `resolve_purchase()`가 K/L/M 칸만 수정.
  팀원에게는 완료 처리 컨트롤이 안 보이고 대기/완료 목록 열람만 됨.
- 상태 컬럼(진행상황/처리일자/처리자)은 `PURCHASE_HEADER` 뒤에 추가됨. `_ws()`가
  기존 탭의 헤더/열수를 자동 보정하므로 상태 컬럼 없이 들어간 옛 행도 '대기'로 처리됨.
- 그 외 수정·삭제는 시트에서 직접.
- `requirements.txt`에 `openpyxl` 추가됨(엑셀 생성용).

## 배포 (Streamlit Cloud)

- main 브랜치에 push → 자동 재배포 (1~2분)
- 빌드 실패 시: share.streamlit.io → My apps → 앱 → "..." → Manage app → 로그 확인
- 패키지 추가: `app/requirements.txt`에 추가 후 push

## 비밀 파일 (절대 깃허브에 올리지 말 것)

- `app/.streamlit/secrets.toml` — 구글 서비스 계정 키 (Streamlit Cloud에도 같은 내용 등록되어 있음)
- `app/service_account.json` — 동일한 서비스 계정 키 (JSON 원본)

두 파일은 `.gitignore`에 등록되어 있어서 `git status` 에 잡히지 않음. 인계 시 **별도 안전한 경로**(USB, 암호화 메일, 1Password 등)로 전달.

## 외부 리소스 URL

| 항목 | URL |
|------|-----|
| 앱 (배포본) | https://carerobot-weekly-report.streamlit.app |
| GitHub 레포 | https://github.com/carerobot0001-pixel/carerobot-weekly-report |
| 구글시트 | https://docs.google.com/spreadsheets/d/1VX-t21tTlXyGPhxksgcoZ0t9js3ABPn_vpiWi_fJcRg/edit |
| FAQ·관리대장 시트 | URL 비공개 (위 "스마트돌봄스페이스 페이지" 참고 — secrets에 ID 저장) |
| Streamlit Cloud 대시보드 | https://share.streamlit.io |
| Google Cloud Console | https://console.cloud.google.com (프로젝트 ID: `molten-guide-469800-e0`) |

## 문제 해결

- **"Zzzz — This app has gone to sleep" 화면** → 무료 호스팅이라 한동안 방문자가 없으면 절전됨.
  파란 **"Yes, get this app back up!"** 버튼을 누르면 1~2분 뒤 정상 접속 (팀원 누구나 가능, 로그인 불필요).
  main에 push해서 재배포해도 깨어남
- **"You do not have access to this app"** → 레포가 비공개로 바뀌면 앱도 비공개. GitHub Settings → Public 유지
- **"템플릿 HWPX를 선택하거나 업로드해주세요"** → 레포 루트에 `돌봄로봇_업무보고*.hwpx` 파일이 있는지 확인
- **"서비스 계정 인증 실패"** → Streamlit Cloud Secrets에 `secrets.toml` 전체 내용 붙여넣었는지 확인
- **"시트를 열 수 없음"** → 구글시트의 공유 설정에 서비스 계정 이메일(`streamlit-bot@molten-guide-469800-e0.iam.gserviceaccount.com`)이 편집자로 있는지 확인
- **스마트돌봄스페이스 탭에 "시트에 접근할 수 없습니다"** → 해당 구글시트(FAQ 또는 관리대장)에 서비스 계정 이메일이 편집자로 공유됐는지 확인
- **스마트돌봄스페이스 탭에 "시트 ID가 아직 설정되지 않았습니다"** → Streamlit Cloud Secrets에 `[smart_space]` 섹션이 빠진 것. 로컬 `app/.streamlit/secrets.toml`의 같은 섹션을 복사해 붙여넣기
- **HWPX가 한글에서 "파일 손상" 에러로 안 열림** → `TROUBLESHOOTING.md` 의 "1. HWPX 생성본이 한글에서..." 섹션 참고. 탭 문자·자간·flag_bits 등 과거 범인 5종과 재발 시 체크리스트가 정리되어 있음
- **기타 과거 비자명 오류 기록** → `TROUBLESHOOTING.md` 전체

## 세팅 초기 이력

2026년 4월 ~ 김건양 연구원이 Claude Code로 설계·구현. 자세한 초기 설치 절차는 `app/SETUP.md` 참고.
