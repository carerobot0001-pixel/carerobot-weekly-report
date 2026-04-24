# 인수인계 체크리스트

**넘기는 사람**: 김건양 연구원 (`carerobot0001@gmail.com` / GitHub `carerobot0001-pixel`)
**받는 사람**: (신규 관리자)

아래 8가지를 순서대로 진행하면 됩니다. 관리자 Claude Code에게 `CLAUDE.md`를 읽혀놓으면 각 단계에서 막힐 때 도움 받을 수 있습니다.

## ☐ 1. 로컬 폴더 전달 (10분)

넘기는 사람:
```
C:\Users\carer\Desktop\돌봄로봇_업무보고_김건양\  폴더 전체
```
를 압축해서 관리자에게 전달 (USB, 드라이브, 암호화 메일 등).

**포함 내용**:
- `app/` 전체 (`.streamlit/secrets.toml`, `service_account.json` 포함)
- HWPX 템플릿들
- `CLAUDE.md`, `HANDOVER.md`

받는 사람: 자기 PC의 적당한 경로에 압축 풀기 (예: `D:\carerobot-report\`).

## ☐ 2. 파이썬 환경 세팅 (관리자 PC에서)

```bash
cd <폴더>/app
pip install -r requirements.txt
```

## ☐ 3. 로컬 테스트

```bash
cd <폴더>/app
streamlit run streamlit_app.py
```
- 브라우저에서 `http://localhost:8501` 접속
- `carerobot` 로 로그인 → 팀원 화면 정상 표시되면 OK
- `carerobot-admin` 로 로그인 → 담당자 대시보드에서 HWPX 생성되면 OK

## ☐ 4. GitHub 레포 권한 이전

**방법 A — 소유권 완전 이전 (추천)**:
1. 김건양이 `github.com/carerobot0001-pixel/carerobot-weekly-report/settings` 접속
2. **Danger Zone → Transfer ownership**
3. 관리자 GitHub 아이디 입력 → 확인
4. 관리자 수락 후 완료

**방법 B — 협업자로 추가 (김건양도 계속 접근)**:
1. `Settings → Collaborators → Add people`
2. 관리자 GitHub 아이디 입력

## ☐ 5. Streamlit Cloud 앱 권한 이전

**방법 A — 앱 삭제 후 관리자가 재배포 (가장 깔끔, URL 바뀜)**:
1. 김건양이 share.streamlit.io → My apps → 앱 → Delete
2. 관리자가 자기 GitHub로 Streamlit Cloud 로그인 → Create app → 같은 레포·파일 선택 → Secrets 붙여넣기 → Deploy
3. 새 URL이 생성됨 (예: `carerobot-report-admin.streamlit.app`). 팀원들에게 재공지.

**방법 B — 관리자에게 앱 편집 권한만 부여 (URL 그대로 유지)**:
- Streamlit Cloud는 앱당 편집자 추가 가능. 앱 설정 → Sharing → 관리자 이메일 입력.
- 단 소유자는 그대로 김건양. 완전 이전 아님.

## ☐ 6. 구글시트 소유권 이전

1. 김건양이 구글시트 열기 (URL은 `CLAUDE.md` 참고)
2. 우측 상단 **공유** → 관리자 이메일을 **편집자**로 추가
3. 관리자가 수락 후, 김건양이 공유 메뉴에서 관리자를 **소유자로 변경**
4. 완료되면 김건양은 편집자 또는 제거 가능

## ☐ 7. Google Cloud 프로젝트 접근 권한

서비스 계정은 레포/Streamlit Cloud에 키가 이미 등록되어 있으므로 **키 자체는 건드릴 필요 없음**. 다만 향후 IAM 관리·키 재발급·API 추가 등을 관리자가 하려면 관리자 구글 계정을 프로젝트에 Owner로 초대해야 함:

1. 김건양이 https://console.cloud.google.com 접속 (프로젝트 ID: `molten-guide-469800-e0`)
2. **IAM 및 관리자 → IAM → 액세스 권한 부여**
3. 관리자 이메일 입력 → 역할 **소유자(Owner)** 선택 → 저장

## ☐ 8. 최종 동작 확인

관리자가:
1. 배포된 앱 URL에 접속 → 팀원 로그인 및 저장 테스트
2. 담당자 모드로 로그인 → HWPX 생성 → 한글에서 열어 정상 확인
3. 구글시트에 데이터가 제대로 쌓이는지 확인
4. 김건양이 자기 컴퓨터에서 `git push` 해봐서 관리자 레포에 반영되지 않는지 확인 (소유권 이전 확실히 됐는지 체크)

## 인계 완료 후 김건양이 할 일

- 로컬 폴더 `C:\Users\carer\Desktop\돌봄로봇_업무보고_김건양\` 는 계속 보관 or 삭제 (관리자 확인 후)
- `secrets.toml`, `service_account.json` 은 로컬에서도 더 이상 필요 없으면 삭제 가능
- Streamlit Cloud 계정(rlaxo1235@gmail.com)도 더 이상 쓸 일 없으면 그대로 두거나 탈퇴

---

## 관리자의 Claude Code에게 — 빠른 적응 프롬프트

관리자가 Claude Code를 이 폴더에서 처음 켜면 이렇게 질문하세요:

> "CLAUDE.md와 HANDOVER.md 읽고, 내가 이 프로젝트를 막 인계받은 상태라는 걸 인지해줘. 로컬에서 streamlit run으로 돌려서 정상 동작하는지 먼저 확인하고 싶어."

그러면 Claude Code가 문서를 참고하면서 환경 설정 안내합니다.
