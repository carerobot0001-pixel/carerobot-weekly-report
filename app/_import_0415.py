"""04.15 템플릿 파일에서 10명의 실제 제출 내용을 추출해
구글시트에 week=2026-04-15로 저장. 1회용 임포트 스크립트.

04.15 파일은 여러 개의 부가 테이블(예산표, 물품표 등)이 있어서
(col, row) 주소가 중복됨. 메인 본문 테이블만 대상으로 추출.
"""
import re
import html
import sys
import zipfile
import toml
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from sheets_store import HEADER, FIELD_KEYS

sys.stdout.reconfigure(encoding='utf-8')

TEMPLATE_PATH = "../돌봄로봇_업무보고(04.15)_취합완료-2.hwpx"
WEEK = "2026-04-15"

# 04.15 메인 본문 셀 매핑 (로봇기술팀은 2행, 획득데이터 없음)
MAIN_BODY_MAPPING = {
    "백정은": {"acquired_data": (4, 1), "research_done": (4, 2),
               "research_plan": (5, 2), "task_done": (4, 3),
               "task_plan": (5, 3), "smart_care_space": (4, 23)},
    "한벼리": {"acquired_data": (4, 4), "research_done": (4, 5),
               "research_plan": (5, 5), "task_done": (4, 6),
               "task_plan": (5, 6)},
    "박재우": {"acquired_data": (4, 7), "research_done": (4, 8),
               "research_plan": (5, 8), "task_done": (4, 9),
               "task_plan": (5, 9)},
    "이윤환": {"acquired_data": (4, 10), "research_done": (4, 11),
               "research_plan": (5, 11), "task_done": (4, 12),
               "task_plan": (5, 12)},
    "김건양": {"research_done": (4, 13), "research_plan": (5, 13),
               "task_done": (4, 14), "task_plan": (5, 14)},
    "류현경": {"research_done": (4, 15), "research_plan": (5, 15),
               "task_done": (4, 16), "task_plan": (5, 16)},
    "남재엽": {"research_done": (4, 17), "research_plan": (5, 17),
               "task_done": (4, 18), "task_plan": (5, 18)},
    "이경진": {"research_done": (4, 19), "research_plan": (5, 19),
               "task_done": (4, 20), "task_plan": (5, 20)},
    "최혜민": {"task_done": (4, 21), "task_plan": (5, 21),
               "research_meeting": (4, 24),
               "director_meeting": (4, 25),
               "mohw_weekly": (4, 26)},
    "정지수": {"task_done": (4, 22), "task_plan": (5, 22)},
}

# project_confirmation은 별도 테이블(Table 1)에서
PROJECT_CONFIRMATION_ASSIGNEE = "최혜민"


def find_table_body(xml, *markers):
    """주어진 모든 marker 텍스트가 포함된 첫 테이블의 바디 XML 반환."""
    tbl_pattern = re.compile(r'<hp:tbl\b[^>]*>(.*?)</hp:tbl>', re.DOTALL)
    for m in tbl_pattern.finditer(xml):
        body = m.group(1)
        if all(marker in body for marker in markers):
            return body
    return None


def extract_cell_text(body, col, row):
    """body XML(하나의 테이블 내부)에서 (col, row) 셀의 텍스트 추출.
    셀 내부의 모든 <hp:p> 문단을 \n으로 결합해 반환."""
    addr_str = f'cellAddr colAddr="{col}" rowAddr="{row}"'
    pos = body.find(addr_str)
    if pos == -1:
        return ""
    tc_start = body.rfind('<hp:tc ', 0, pos)
    if tc_start == -1:
        return ""
    sublist_start = body.find('<hp:subList', tc_start)
    if sublist_start == -1 or sublist_start > pos:
        return ""
    sublist_end = body.find('</hp:subList>', sublist_start)
    if sublist_end == -1:
        return ""
    content_start = body.find('>', sublist_start) + 1
    content = body[content_start:sublist_end]

    paragraphs = re.findall(r'<hp:p\b[^>]*?>(.*?)</hp:p>', content, re.DOTALL)
    lines = []
    for p in paragraphs:
        texts = re.findall(r'<hp:t>([^<]*)</hp:t>', p)
        lines.append(html.unescape(''.join(texts)).strip())
    return '\n'.join(lines).strip()


def main():
    with zipfile.ZipFile(TEMPLATE_PATH, 'r') as z:
        xml = z.read('Contents/section0.xml').decode('utf-8')

    # 메인 본문 테이블: 10명 이름 중 몇 개가 같이 등장하는 테이블
    main_body = find_table_body(xml, "백정은", "한벼리", "최혜민", "정지수")
    if main_body is None:
        print("ERROR: 메인 본문 테이블을 찾지 못했습니다.")
        return

    # 사업단 공통확인사항 테이블
    pc_body = find_table_body(xml, "사업단", "실증 데이터 센서 활용 강화")

    cfg = toml.load('.streamlit/secrets.toml')
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(
        dict(cfg['gcp_service_account']), scopes=SCOPES)
    client = gspread.authorize(creds)
    ss = client.open_by_key(cfg['sheet']['id'])
    ws = ss.worksheet('submissions')

    all_rows = ws.get_all_values()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 사업단 공통확인사항 추출 (최혜민에게 할당)
    pc_text = ""
    if pc_body is not None:
        pc_text = extract_cell_text(pc_body, 1, 0)
    else:
        print("WARN: 사업단 공통확인사항 테이블 없음")

    for name, cells in MAIN_BODY_MAPPING.items():
        values = {}
        for field, (col, row) in cells.items():
            values[field] = extract_cell_text(main_body, col, row)

        if name == PROJECT_CONFIRMATION_ASSIGNEE:
            values["project_confirmation"] = pc_text

        field_values = [values.get(k, "") for k in FIELD_KEYS]
        new_row = [name, WEEK] + field_values + [now]

        updated = False
        for i, r in enumerate(all_rows[1:], start=2):
            if len(r) >= 2 and r[0] == name and r[1] == WEEK:
                end_col = chr(ord('A') + len(HEADER) - 1)
                ws.update(f"A{i}:{end_col}{i}", [new_row])
                updated = True
                break
        if not updated:
            ws.append_row(new_row)

        filled_count = sum(1 for v in values.values() if v)
        total = len(values)
        # 주요 필드 길이 요약
        sample = []
        for key in ("acquired_data", "research_done", "task_done"):
            if key in values:
                sample.append(f"{key[:3]}={len(values[key])}")
        print(f'  {name}: {filled_count}/{total} 필드 | {" ".join(sample)}')

    print(f'\n[OK] {WEEK} 주차로 10명 데이터 임포트 완료')


if __name__ == "__main__":
    main()
