# 돌봄로봇 주간 업무보고 웹앱 - 설치/배포 가이드

## 전체 그림

```
팀원 10명 ──(비밀번호 carerobot로 접속)──> Streamlit 웹앱
                                              │
                                              ├── 구글시트에 저장
                                              │
담당자 ──(비밀번호 carerobot-admin)────────> 대시보드
                                              │
                                              └── HWPX 내보내기
```

## 1. 구글시트 + 서비스 계정 준비 (최초 1회, 약 10분)

### 1-1. 새 구글시트 생성
1. https://sheets.google.com 에서 빈 시트 생성
2. 이름: `돌봄로봇_업무보고_제출함` (원하는 대로)
3. URL에서 문서 ID 복사 — `https://docs.google.com/spreadsheets/d/[이 부분]/edit`

### 1-2. 서비스 계정 생성 (앱이 시트에 접근할 '로봇 계정')
1. https://console.cloud.google.com 접속
2. 상단에서 **프로젝트 만들기** → 이름: `carerobot-report` (아무거나)
3. 좌측 메뉴 **API 및 서비스 → 라이브러리**
   - `Google Sheets API` 검색 → **사용 설정**
   - `Google Drive API` 검색 → **사용 설정**
4. 좌측 메뉴 **API 및 서비스 → 사용자 인증 정보**
   - **사용자 인증 정보 만들기 → 서비스 계정**
   - 이름: `streamlit-bot` → **만들기 및 계속**
   - 역할은 건너뛰고 **완료**
5. 생성된 서비스 계정 클릭 → **키** 탭 → **키 추가 → 새 키 만들기 → JSON**
   - JSON 파일이 다운로드됨. 이 파일에 로그인 정보가 들어있음.

### 1-3. 시트에 서비스 계정 공유 권한 부여
1. JSON 파일 열어서 `client_email` 값 복사 (예: `streamlit-bot@carerobot-report.iam.gserviceaccount.com`)
2. 1-1에서 만든 구글시트로 돌아가 **공유** 버튼 클릭
3. 위 이메일 붙여넣고 **편집자** 권한으로 공유

## 2. 로컬 테스트 (선택 — 배포 전 확인용)

```bash
cd app
pip install -r requirements.txt
```

`.streamlit/secrets.toml` 파일 생성 (`.streamlit/secrets.toml.example` 참고):
- `[sheet]` 섹션의 `id`에 1-1의 문서 ID 붙여넣기
- `[gcp_service_account]` 섹션에 JSON 파일 내용 붙여넣기 (각 키를 toml 형식으로)

실행:
```bash
streamlit run streamlit_app.py
```

브라우저가 자동으로 열림 → `carerobot`(팀원용) 또는 `carerobot-admin`(담당자용) 로 로그인.

## 3. Streamlit Cloud 배포 (5분)

### 3-1. 깃허브 레포 생성
1. `app` 폴더를 깃허브 레포로 올림 (비공개 저장소 권장)
2. **`.streamlit/secrets.toml`은 `.gitignore`에 추가해서 올리지 말 것** (JSON 키 포함됨)

### 3-2. Streamlit Cloud에 연결
1. https://share.streamlit.io 접속 → 깃허브 로그인
2. **New app** 클릭
3. 레포지토리 선택, Main file path: `streamlit_app.py`
4. **Advanced settings → Secrets**에 로컬의 `secrets.toml` 내용 그대로 붙여넣기
5. **Deploy** 클릭

### 3-3. 템플릿 HWPX 업로드
Streamlit Cloud에는 HWPX 템플릿 파일이 필요합니다.
- **방법 A (간단)**: 담당자가 대시보드에서 매번 `파일 업로드`로 템플릿 직접 올림
- **방법 B**: 레포에 `templates/latest.hwpx`를 넣어두고 코드에서 경로 고정

## 4. 사용법

### 팀원
1. 담당자가 공유한 링크 접속 → `carerobot` 입력
2. 본인 이름 선택 → 4개 칸(연구실적·연구계획·업무실적·업무계획) 작성
3. **저장/제출** 클릭
4. 다시 들어오면 이전 내용 자동 로드 → 언제든 수정 가능

### 담당자
1. 링크 접속 → `carerobot-admin` 입력
2. 사이드바 **담당자 대시보드** 선택
3. 제출 현황 확인 (미제출자 이름 경고로 표시)
4. 내용 미리보기로 최종 확인
5. 템플릿 HWPX 업로드 → **HWPX 생성 및 다운로드** → 주간회의에서 띄움

## 5. 알아둘 것 — 현장실증팀 "획득 데이터" 섹션

현장실증팀 4명(백정은·한벼리·박재우·이윤환)의 연구 영역은 템플릿에 **"획득 데이터"** 가 병합된 헤더 행이 따로 존재합니다. 이 앱에서는 그 헤더 행은 건드리지 않고, 그 아래의 실제 실적/계획 셀만 업데이트합니다.

- **입력되는 범위**: 실적/계획 본문 (1., 2., 3.번 항목 등)
- **입력 안 되는 범위**: "획득 데이터:" 로 시작하는 최상단 블록

매주 획득 데이터 섹션을 갱신해야 한다면, 담당자가 최종 HWPX를 다운로드한 뒤 한글에서 직접 수정하거나, 필요시 `team_config.py`에 해당 헤더 셀 좌표(col 4, row 1/4/7/10)를 추가해서 확장할 수 있습니다.

## 6. 자주 발생하는 이슈

- **"서비스 계정 인증 실패"**: `secrets.toml`의 `private_key`는 반드시 양 끝에 `"..."` 따옴표로 감싸고, 개행은 `\n`으로 유지
- **"시트를 열 수 없음"**: 1-3 단계에서 시트에 서비스 계정 이메일을 **편집자**로 공유했는지 확인
- **HWPX 템플릿이 바뀌어서 깨짐**: `team_config.py`의 `research_row`/`task_row`를 새 템플릿 기준으로 수정
