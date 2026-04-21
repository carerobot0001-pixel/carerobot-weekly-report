"""10명 업무보고 데이터를 HWPX 템플릿에 일괄 삽입하는 모듈.

- 기본 본문 색상: charPr 15 (검정, 템플릿에 이미 존재)
- 파란색: 런타임에 charPr 15를 복제 + textColor를 #0000FF로 수정해서
          header.xml에 동적 추가한 뒤 그 id 사용
- 셀 위치가 여러 테이블에 중복으로 존재할 수 있음 → nth 인덱스 지원
"""
import zipfile
import re
import io
import html
from team_config import TEAM_MEMBERS

CHARPR_BLACK = "15"
COLOR_HEX = {"black": "#000000", "blue": "#0000FF"}


DEFAULT_P_ATTRS = (
    'id="0" paraPrIDRef="27" styleIDRef="0" '
    'pageBreak="0" columnBreak="0" merged="0"'
)
DEFAULT_LINESEG = (
    '<hp:linesegarray>'
    '<hp:lineseg textpos="0" vertpos="0" vertsize="1100" textheight="1100" '
    'baseline="935" spacing="164" horzpos="0" horzsize="31508" flags="393216"/>'
    '</hp:linesegarray>'
)


def make_paragraph_from_template(text, p_attrs, run_char_pr_id, lineseg_xml):
    """원본 셀 문단의 속성을 유지하면서 텍스트만 교체한 새 문단 생성."""
    escaped = html.escape(text)
    return (
        f'<hp:p {p_attrs}>'
        f'<hp:run charPrIDRef="{run_char_pr_id}"><hp:t>{escaped}</hp:t></hp:run>'
        f'{lineseg_xml}</hp:p>'
    )


def extract_cell_template(content_xml):
    """셀 내부 XML에서 첫 번째 <hp:p>의 속성·charPr·lineseg 추출.
    반환: (p_attrs_str, run_char_pr_id_or_None, lineseg_xml_str)"""
    p_m = re.search(r'<hp:p\s+([^>]*)>', content_xml)
    p_attrs = p_m.group(1) if p_m else DEFAULT_P_ATTRS
    # id는 0으로 통일 (원본이 0 또는 2147483648 다양)
    p_attrs = re.sub(r'id="\d+"', 'id="0"', p_attrs)

    run_m = re.search(r'<hp:run\s+charPrIDRef="(\d+)"', content_xml)
    run_char_pr_id = run_m.group(1) if run_m else None

    ls_m = re.search(r'<hp:linesegarray>.*?</hp:linesegarray>', content_xml, re.DOTALL)
    lineseg_xml = ls_m.group(0) if ls_m else DEFAULT_LINESEG

    return p_attrs, run_char_pr_id, lineseg_xml


def make_cell_content(text, cell_template, override_color_id=None):
    """cell_template = (p_attrs, orig_char_pr, lineseg). override_color_id 있으면 색상 덮어씀."""
    p_attrs, orig_char_pr, lineseg = cell_template
    # 원본 셀 charPr 우선, 없으면 검정 기본값. 파란색 필드만 override.
    run_id = override_color_id if override_color_id is not None else (orig_char_pr or CHARPR_BLACK)
    lines = (text or "").splitlines() or [""]
    return "".join(
        make_paragraph_from_template(line, p_attrs, run_id, lineseg)
        for line in lines
    )


def find_cell_sublist(xml, col, row, nth=0):
    """nth번째로 나타나는 cellAddr col=col row=row 셀의 subList 내부 영역 반환."""
    addr_str = f'cellAddr colAddr="{col}" rowAddr="{row}"'
    pos = 0
    for _ in range(nth + 1):
        pos = xml.find(addr_str, pos)
        if pos == -1:
            return None, None
        addr_pos = pos
        pos += len(addr_str)
    tc_start = xml.rfind('<hp:tc ', 0, addr_pos)
    if tc_start == -1:
        return None, None
    sublist_start = xml.find('<hp:subList', tc_start)
    if sublist_start == -1 or sublist_start > addr_pos:
        return None, None
    sublist_content_start = xml.find('>', sublist_start) + 1
    sublist_end = xml.find('</hp:subList>', sublist_start)
    if sublist_end == -1:
        return None, None
    return sublist_content_start, sublist_end


def replace_cell(xml, col, row, text, override_color_id=None, nth=0):
    """셀 내부를 text로 교체. 원본 셀 문단 속성(paraPr/charPr/lineseg)은 유지하고,
    override_color_id가 주어지면 run의 charPrIDRef만 그 값으로 강제."""
    start, end = find_cell_sublist(xml, col, row, nth=nth)
    if start is None:
        return xml
    old_content = xml[start:end]
    cell_template = extract_cell_template(old_content)
    new_content = make_cell_content(text, cell_template, override_color_id)
    return xml[:start] + new_content + xml[end:]


def ensure_blue_charpr(header_xml: str) -> tuple[str, str]:
    """header.xml에 파란색 charPr가 없으면 추가하고 해당 id 반환.
    이미 textColor=#0000FF인 charPr가 있으면 그걸 재사용."""
    existing = re.search(r'<hh:charPr\s+id="(\d+)"[^>]*textColor="#0000FF"', header_xml)
    if existing:
        return header_xml, existing.group(1)

    black_m = re.search(
        rf'<hh:charPr\s+id="{CHARPR_BLACK}"[^>]*?>.*?</hh:charPr>',
        header_xml, re.DOTALL)
    if not black_m:
        raise RuntimeError("템플릿에 기본 검정 charPr(15)가 없습니다.")
    black_xml = black_m.group(0)

    max_id = max(
        int(x) for x in re.findall(r'<hh:charPr\s+id="(\d+)"', header_xml)
    )
    new_id = str(max_id + 1)

    blue_xml = re.sub(
        r'id="\d+"', f'id="{new_id}"', black_xml, count=1
    )
    blue_xml = re.sub(
        r'textColor="#[0-9A-Fa-f]{6}"',
        'textColor="#0000FF"',
        blue_xml, count=1,
    )

    new_header = header_xml.replace(black_xml, black_xml + blue_xml)

    new_header = re.sub(
        r'(<hh:charProperties[^>]*itemCnt=")(\d+)(")',
        lambda m: f'{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}',
        new_header, count=1,
    )
    return new_header, new_id


def build_report(template_bytes: bytes, submissions: dict,
                 title_date: str,
                 period_start: str, period_end: str,
                 plan_start: str, plan_end: str) -> bytes:
    """submissions = {이름: {필드키: 텍스트, ...}}"""
    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as zin:
        xml = zin.read('Contents/section0.xml').decode('utf-8')
        header = zin.read('Contents/header.xml').decode('utf-8')
        all_files = {name: zin.read(name) for name in zin.namelist()}

    header, blue_id = ensure_blue_charpr(header)
    color_to_id = {"black": CHARPR_BLACK, "blue": blue_id}

    xml = re.sub(
        r'과업별 업무 보고 \(\d{2}\.\d{2}\.\d{2}\.\)',
        f'과업별 업무 보고 ({title_date})',
        xml,
    )
    xml = re.sub(
        r'업무 실적\(\d{4}\.\d{2}\.\d{2}\. ~ \d{4}\.\d{2}\.\d{2}\.\)',
        f'업무 실적({period_start} ~ {period_end})',
        xml,
    )
    xml = re.sub(
        r'업무 계획\(\d{4}\.\d{2}\.\d{2}\. ~ \d{4}\.\d{2}\.\d{2}\.\)',
        f'업무 계획({plan_start} ~ {plan_end})',
        xml,
    )

    for m in TEAM_MEMBERS:
        data = submissions.get(m["name"], {})
        for field, spec in m["cells"].items():
            if spec is None:
                continue  # HWPX 매핑 보류 필드 (시트 저장만 됨)
            if field in ("research_done", "research_plan") and not m["has_research"]:
                continue
            if len(spec) == 2:
                col, row = spec
                color, nth = "black", 0
            elif len(spec) == 3:
                col, row, color = spec
                nth = 0
            elif len(spec) == 4:
                col, row, color, nth = spec
            else:
                raise ValueError(f"잘못된 셀 명세: {spec}")
            text = data.get(field, "")
            # 파란색으로 명시된 필드만 override. 검정은 원본 셀 charPr 유지.
            override = color_to_id["blue"] if color == "blue" else None
            xml = replace_cell(xml, col, row, text,
                               override_color_id=override,
                               nth=nth)

    all_files['Contents/section0.xml'] = xml.encode('utf-8')
    all_files['Contents/header.xml'] = header.encode('utf-8')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in all_files.items():
            zout.writestr(name, data)
    return buf.getvalue()


def load_template(template_path: str) -> bytes:
    with open(template_path, 'rb') as f:
        return f.read()
