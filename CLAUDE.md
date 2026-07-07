# 돌봄로봇 주간 업무보고 웹앱 — 인수인계 문서

## 무엇을 하는 앱인가

- **목적**: 매주 팀원 10명이 주간 업무보고를 웹으로 입력 → 누구나 HWPX 취합본을 다운로드해서 주간회의에서 띄움
- **사용자**: 팀원 10명 (담당자/관리자 구분 없음 — 2026-07 단일화)
- **접속 URL**: https://carerobot-weekly-report.streamlit.app
- **비밀번호**: `carerobot` 하나(전원 공용, `app/team_config.py`의 `APP_PASSWORD`에서 변경).
  **담당자/팀원 구분·`is_admin`·`ADMIN_PASSWORD`는 제거됨** — 모든 기능(공지·백업·취합본 생성·구매 완료처리)을 전원 사용.

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
    ├── collab_store.py                     ← 문서 협업 보드 (구글문서 링크+요청+현황)
    ├── equip_store.py                      ← 장비 사용현황 대장 (연구별 필터+편집)
    ├── visit_store.py                      ← 실증 방문 일지 (등록/필터/삭제)
    ├── calendar_store.py                   ← 사업단 구글캘린더 연동 (조회/추가/수정/삭제)
    ├── news_store.py                       ← 홈 뉴스피드 (구글뉴스 RSS)
    ├── notice_store.py                     ← 홈 팀 공지사항 (누구나 등록/삭제)
    ├── common_store.py                     ← 사업단 공통확인사항(최혜민) 표→한글/엑셀
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
`app/team_config.py`의 `APP_PASSWORD`(단일 비밀번호) 수정 → push. (담당자용 비밀번호는 없어짐)

### 지난주 데이터를 수동 임포트
`app/_import_0415.py`를 참고해서 `MAIN_BODY_MAPPING`과 `WEEK` 변수만 바꿔 실행. 1회용 스크립트.

### 매주 운영 (누구나 — 담당자 구분 없음)
1. 팀원들이 목~화 사이 웹에서 작성 (수요일 기준이라 수요일 회의 전까지)
2. **📝 업무보고 작성·취합** 메뉴 → **📊 제출현황·취합본 생성** 탭에서 제출 현황 확인 → 미제출자 독촉
3. 수요일 회의 전: 같은 탭 하단 "📥 HWPX 생성 및 다운로드" → 파일 받아 회의에서 띄움
   (구 "담당자 대시보드"는 없어지고 제출현황·취합·미리보기가 이 탭으로, 공지·백업은 홈 하단 토글로 분산됨)

### 담당자 개념 제거 · 기능 분산 (2026-07)
담당자(관리자)가 따로 없어져서 **단일 비밀번호 + `is_admin`/`admin_page` 완전 제거**. 구 담당자 대시보드 기능 분산:
- `member_page()`는 이제 **탭 2개**: `_report_write()`(내 보고 작성) + `_report_collect()`(제출현황·미리보기·HWPX 취합본 생성).
  st.tabs는 **두 탭 본문을 매 실행마다 모두 렌더**하므로 두 함수의 위젯 라벨/키가 겹치면 안 됨(현재 안 겹침, 취합 주차는 `key="collect_week"`).
- 공지 등록/관리(`_notice_manage`)·전체 백업(`_backup_section`)은 **홈 하단 토글**(누구나).
- 구매 완료처리·전체삭제도 **전원 개방**(전체삭제는 ⚠️확인 체크 유지).
- 메뉴 `업무보고 작성` → `📝 업무보고 작성·취합`으로 개명(사이드바·dispatch·홈 바로가기 target 3곳 동기화).

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
- **구매완료 처리**(진행상황·처리일자·처리자 기록)는 **누구나** 가능(2026-07 담당자 구분 제거) —
  요청 단위(같은 요청ID 전체 행)로 `resolve_purchase()`가 K/L/M 칸만 수정.
- 상태 컬럼(진행상황/처리일자/처리자)은 `PURCHASE_HEADER` 뒤에 추가됨. `_ws()`가
  기존 탭의 헤더/열수를 자동 보정하므로 상태 컬럼 없이 들어간 옛 행도 '대기'로 처리됨.
- **누적 리스트 관리**(2026-06 보완): 📥 누적 전체 **엑셀 다운로드**(`build_purchase_list_xlsx`,
  요청자 열을 비고 옆에 배치), 🗑️ **선택 삭제**(요청ID 단위) / **전체 삭제**(누구나,
  ⚠️확인 체크 필수). 함수: `delete_purchase_request`, `clear_all_purchases`.
- 모든 요청자는 하나의 `구매요청` 탭에 누적(요청자 무관) — 별도 분리 없음.
- 그 외 수정은 시트에서 직접.
- `requirements.txt`에 `openpyxl` 추가됨(엑셀 생성용).

## 문서 협업 보드 페이지 (2026-06 추가)

사이드바 "📋 문서 협업" 메뉴 — 팀원 누구나. 엑셀·워드·PPT를 여럿이 나눠 작성할 때 쓰는 보드.

- 코드: `app/collab_store.py` + `streamlit_app.py`의 `collab_page()`
- **앱은 파일을 저장하지 않음.** 실제 문서는 요청자가 만든 **구글 시트/문서/슬라이드**에 있고,
  앱은 그 **링크 + 요청사항 + 제출현황(완료자)** 만 제출함 스프레드시트의 `문서협업` 탭에 텍스트로 관리.
- **왜 링크 방식인가 (중요·인계 포인트)**: 서비스 계정은 **구글 드라이브에 파일을 저장 못 함**
  (`Service Accounts do not have storage quota` — 공유 드라이브=유료 Workspace 필요). 그래서
  "앱이 업로드 파일을 보관"하는 길이 막혀, 요청자가 직접 만든 구글 문서 **링크만** 받는 구조.
  앱이 파일을 *만들어 즉시 다운로드*(HWPX 취합본 등)하는 건 저장이 0이라 됨 — '만들기'와 '보관'은 다름.
- 흐름: 요청자가 구글 문서 만들어 링크 등록(+요청·마감·담당) → 팀원이 보드에서 링크 클릭해 실시간
  편집 → "✅ 내 부분 완료" 체크 → 요청자/누구나 "🏁 마감". 진행중/완료로 목록 분리.
- 한글(HWP)은 구글이 못 열어 제외. **PPT도 '파일 올리기'에서 제외** — 구글 슬라이드 변환 시
  서식이 깨져서. PPT는 **OneDrive/파워포인트 온라인 편집 링크**를 '링크 붙여넣기'로 등록(안 깨짐).
  즉 자동 구글변환 업로드는 **엑셀·워드만**, PPT·기타는 링크 방식.
- 컬럼이 바뀌면 `collab_store.py`의 `COLLAB_HEADER`만 수정. `_ws()`가 헤더 자동 보정.

### OAuth 파일 자동업로드 (2026-06 추가)

요청자가 **파일만 올리면 앱이 구글 문서로 자동 변환·공유·링크생성**까지 함. (링크 직접 붙여넣기도 여전히 가능)

- secrets `[google_oauth]`(client_id/client_secret/refresh_token)가 있으면 활성 — `collab_store.drive_enabled()`.
  없으면 자동으로 '링크 직접 붙여넣기'로 폴백(앱 안 죽음).
- **왜 OAuth인가**: 서비스 계정은 드라이브 저장 불가(quota 0 — 용량플랜과 무관한 구글 규칙).
  그래서 **본인(carerobot0001) 구글계정**을 OAuth로 연결해 그 드라이브에 파일을 만든다(구글원 5TB
  사용 중이라 용량 여유 충분). 범위는 `drive.file`(앱이 만든 파일만 접근, 비민감 범위).
- **토큰 발급(1회)**: 레포 루트 `get_oauth_token.py` 실행 → 브라우저 인증 → `oauth_secrets_block.txt` 생성
  → 그 내용을 로컬 `secrets.toml` + Streamlit Cloud Secrets에 `[google_oauth]`로 붙여넣기.
  (Google Cloud Console에서 OAuth 동의화면 구성 + 데스크톱 OAuth 클라이언트 생성이 선행. 프로젝트는
  `molten-guide-469800-e0`. `drive.file`은 비민감이라 '앱 게시'해도 구글 심사 불필요 → 토큰 무기한)
- `create_drive_doc(file_bytes, filename)`: 확장자로 변환 대상 결정(xlsx→시트, docx→문서, pptx→슬라이드),
  '링크가 있는 사용자 편집' 공유 후 편집링크 반환. 만든 문서는 본인 드라이브에 **영구 보관**(앱이 안 지움).
- 비밀파일: `client_secret*.json`, `oauth_secrets_block.txt`, `get_oauth_token.py`는 `.gitignore` 처리됨.

## 장비 사용현황 페이지 (2026-06 추가)

사이드바 "🔧 장비 사용현황" 메뉴 — 팀원 누구나. 실증 장비(기기) 사용 대장.

- 코드: `app/equip_store.py` + `streamlit_app.py`의 `equip_page()`
- 출처: `장비 사용 현황_자동화.xlsx`의 마스터 시트("기기 사용현황"). 엑셀의 **연구별 시트
  자동분류(수식)** 는 앱에서 **연구 필터 드롭다운**으로 대체 — 마스터 1개만 관리.
- 데이터: 제출함 스프레드시트의 `장비현황` 탭. `EQUIP_HEADER`(기기명/S/N/자산번호/연구/
  플랫폼/관련앱계정/피험자명/기간/비고). 초기 32행은 엑셀에서 임포트해둠.
- **조회**: 연구(실증)별 필터 + 현재 보기 엑셀 다운로드(`build_equip_xlsx`).
- **편집**: "전체 목록 편집"(토글) → `st.data_editor`(행 추가/수정/삭제) → `save_all_equipment`
  가 데이터영역을 **통째로 덮어쓰기**(동시편집 시 마지막 저장 우선 — 소규모 운영 적합). 누구나 가능.
- ⚠️ 피험자명·계정 등 **개인정보 포함** — 팀 로그인 뒤에서만 노출(외부 공개 없음).
- 컬럼이 바뀌면 `EQUIP_HEADER`만 수정. `_ws()`가 헤더 자동 보정.

## 홈 대시보드 / 실증 방문 일지 (2026-07 추가)

- **🏠 홈** (사이드바 첫 메뉴, 로그인 후 기본 화면): `home_page()`. 구성(위→아래):
  - **상단 전체폭 📅사업단 일정 임베드 달력**(라디오 주간/월간/일정목록, 기본 주간, `embed_url(mode)`).
  - 그 아래 **2단** `st.columns([1.7, 1])`:
    - **좌(넓음)**: 📌공지사항(**표시만**) → ⚡**바로가기 타일**(네이버 아이콘식 8개, 4개×2줄,
      **아이콘+라벨을 한 버튼에** `f"{emoji}  \\n{label}"`로 넣어 겹침 방지; `.qbar-mark` 컨테이너에
      스코프된 CSS로 타일화, `::first-line`으로 아이콘만 크게) → 🔔오늘 챙길 것(주간보고 **화 17시 마감
      카운트다운**·문서협업 마감) → 🙋내 할 일(이름 선택→미제출·협업 담당).
    - **우**: 📰**뉴스 섹션 탭**(오른쪽엔 뉴스만).
  - **홈 하단 전체폭 토글(누구나)**: ➕일정 추가·수정·삭제(`_calendar_manage`) · 📌공지 등록/관리
    (`_notice_manage`) · 🗄️전체 데이터 백업(`_backup_section`). 셋 다 기본 접힘(세션키 home_*_open).
  - 전역 여백: `main()`에서 `.block-container` 패딩 축소(layout=wide 기본 상단·좌우 패딩이 큼).
  - 좌 컬럼 안의 바로가기·삭제행은 **컬럼 중첩 1단**(Streamlit 허용 한계) — 더 깊게 넣지 말 것.
    지표/일정 읽기는 try/except로 감싸 하나 실패해도 뜸. 홈 렌더 시에만 주입되는 **컴팩트 CSS**로 압축.
    버튼 네비게이션은 사이드바 radio `key="main_menu"` + `_nav_to`(_goto)로 구현.
  - **공지사항**(`notice_store`, `NOTICE_HEADER=[등록일시,작성자,내용,만료일]`): 누구나 등록/삭제(홈 하단 토글).
    등록 시 **작성자 선택**(`team_config.NOTICE_AUTHORS`=송원경 과장·임명준 연구관·이정아 연구사
    +연구원10명+직접입력). **만료일(표시 종료일)** 지정 시 그날 지나면 화면에서 숨김 +
    `sweep_expired`(세션당 1회, 만료일 기준·높은행부터·등록일시 재확인)로 시트 자동정리.
    미지정이면 영구. **`add_notice`는 `value_input_option="RAW"`** — USER_ENTERED면 "YYYY-MM-DD"를
    시트가 네이티브 날짜로 바꿔 로케일 표기로 되돌려 문자열 비교(`is_expired`)가 깨짐(리뷰 확인 버그).
  - **문서협업 자동 공지**: 진행중 문서협업(`collab_rows`, 상태≠완료)을 공지 영역에 **가상 렌더**
    (시트 저장·삭제 없음) — 제목·마감·`N/M명 제출·남은 사람`(완료자=제출 체크) 표시, 협업 완료·삭제
    시 자동 소멸. `add_collab`을 건드리지 않아 안전.
  - **뉴스 섹션 탭**(`news_store.NEWS_SECTIONS`): 돌봄로봇/돌봄·복지/AI·신기술/로봇·휴머노이드 4탭,
    탭마다 다른 키워드로 `fetch_section(queries)` 조회(각 ttl 1h). 구글뉴스 RSS라 사진 없이 제목·출처.
- **📍 실증 방문 일지**: `app/visit_store.py` + `visit_page()`. 제출함 스프레드시트의
  `방문일지` 탭. `VISIT_HEADER`(방문일/실증/방문자/방문내용/이슈/등록일시). 등록 + 실증별
  필터 조회 + 삭제(등록일시 재확인으로 행 밀림 방지). 누구나.
- 사이드바 메뉴가 8개가 됨 → `streamlit_app.py`가 1000줄 넘음. **페이지 파일 분리 리팩토링**
  하기 좋은 시점(기능 동작엔 문제없음, 유지보수 편의 목적). [[weekly-report-app-roadmap]]

## 사업단 일정 (구글 캘린더 연동, 2026-07 추가)

**별도 사이드바 메뉴가 아니라 🏠 홈 안에 임베드됨**(우측 컬럼 달력 + 하단 전체폭 관리 토글).
`calendar_page()`는 없고, 홈이 `embed_url()`로 임베드 + `_calendar_manage()`로 추가/수정/삭제한다.

- 코드: `app/calendar_store.py` + `streamlit_app.py`의 `home_page()` / `_calendar_manage()`
- **서비스 계정으로 양방향 연동** — 드라이브 파일과 달리 캘린더 이벤트는 서비스 계정이
  저장/수정 가능(용량 이슈 없음). Calendar API 사용설정 + 대상 캘린더를 서비스 계정에
  **'일정 변경' 권한으로 공유**해야 함.
- 캘린더 ID는 secrets `[calendar] id`(공개 레포 대비). 현재 캘린더 = **돌봄로봇중개연구사업단**
  (`pi7uilph8s...@group.calendar.google.com`). 없으면 홈에 설정 안내가 뜸.
- 임베드: `embed_url(mode)` — `mode`는 `WEEK`(홈 기본)/`MONTH`/`AGENDA`(일정목록). 홈 우측에서
  라디오로 전환. `st.iframe`(신)/`components.iframe`(구) 버전 호환 처리. 임베드는 구글 로그인·권한
  있는 사람에게만 보이므로, 필요 시 `AGENDA`(일정목록)로 텍스트 목록처럼 볼 수 있음.
- CRUD: `upcoming_events`(ttl 60s)/`add_event`/`update_event`/`delete_event`. 종일/시간 지정 지원.

## 사업단 공통확인사항(최혜민) 페이지 (2026-07 추가, 1단계)

사이드바 "📑 사업단 공통확인사항" — 최혜민 연구원의 표(본부과제 용역·자산구매 × 실적/계획)를
앱에서 입력 → **한글(HWPX)/엑셀 생성**. 다른 분들 줄글과 달리 표라서 별도 처리.

- 코드: `app/common_store.py` + `streamlit_app.py`의 `common_page()`
- 저장: 제출함 스프레드시트 `공통확인사항` 탭(종류/구분/내용1~4). `st.data_editor` 4개.
- **한글 생성 방식(중요)**: 취합본의 **리프 표**(중첩 없는 `<hp:tbl>`)를 찾아 — 용역 표(발주금액,
  최대 5행)·자산 표(구매금액, 최대 10행), 각 실적(1번째)/계획(2번째) — 검증된 `replace_cell`로
  셀을 채움(합계 자동). 동적 행 삽입은 위험해서 **고정 행수**만. 행 초과 시 UI 경고.
- **템플릿**: `사업단_공통확인사항_템플릿.hwpx`(레포 루트). 06.24 취합본을 **빈 표로 변환**
  (모든 데이터·피험자명 제거, 헤더만 남김) 후 커밋 — 데이터 든 원본은 **커밋 금지**(공개 레포).
  표 구조가 바뀌면 이 템플릿을 새로 만들어야 함(위 blanking 스크립트 참고).
- 엑셀도 제공(`build_common_xlsx`) — 한글이 안 맞으면 대체용.
- ⚠️ HWPX는 예민해 로컬에서 '한글 열림'을 검증 못 함 → 최혜민 님이 실제 열어 확인 필요.
- **2단계(보류)**: 이 표를 메인 취합본 한 파일에 합치기 = 다른 10명 셀 인덱스가 밀려 재매핑
  필요 + 깨짐 위험 큼. 1단계(별도 한글) 안정화 후 검토.

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
