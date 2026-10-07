"""10명 업무보고 데이터를 HWPX 템플릿에 일괄 삽입하는 모듈.

- 기본 본문 색상: 셀의 원래 글자모양(charPr)을 쓰되 글자색만 검정으로
- 파란색(획득 데이터): 셀의 원래 글자모양을 복제해 **파랑 + 굵게**로 바꾼 판을 추가
- 셀 위치가 여러 테이블에 중복으로 존재할 수 있음 → nth 인덱스 지원

⚠️ 한글은 charPrIDRef 를 id 속성이 아니라 **목록 안 순서(위치)**로 찾는다(2026-10
렌더링으로 확인). 새 charPr 를 목록 중간에 끼우면 그 뒤 번호가 한 칸씩 밀려
파란 굵은 글씨가 빨간 보통 글씨로 나왔다. 새 charPr 는 반드시 **맨 끝**에 붙인다.
"""
import zipfile
import re
import io
import html
from team_config import TEAM_MEMBERS

CHARPR_BLACK = "15"
COLOR_HEX = {"black": "#000000", "blue": "#0000FF"}


def _sanitize_for_hwpx(text: str) -> str:
    """한글 HWPX 파서가 싫어하는 문자 정리.
    - 백슬래시(\\): 이스케이프 오해. 제거
    - 탭(\\t): HWPX 내부 구조자 충돌 가능. 공백 4개로 치환
    - 그 외 제어문자 (\\n, \\r 제외): 제거
    """
    if not text:
        return ""
    text = text.replace("\\", "")
    text = text.replace("\t", "    ")
    # \n, \r 외의 제어문자 제거 (0x00-0x1F, 0x7F)
    text = "".join(c for c in text
                   if ord(c) >= 0x20 or c in ("\n", "\r"))
    return text


DEFAULT_LINESEG = (
    '<hp:linesegarray>'
    '<hp:lineseg textpos="0" vertpos="0" vertsize="1100" '
    'textheight="1100" baseline="935" spacing="164" horzpos="0" '
    'horzsize="31508" flags="393216"/>'
    '</hp:linesegarray>'
)


def make_paragraph_xml(text: str, char_pr_id: str = CHARPR_BLACK,
                       para_pr_id: str = "27",
                       style_id: str = "0",
                       is_first: bool = True,
                       lineseg_xml: str = DEFAULT_LINESEG) -> str:
    """단순 하드코딩된 <hp:p> 블록 생성. lineseg 는 셀별로 바꿀 수 있음."""
    escaped = html.escape(_sanitize_for_hwpx(text))
    pid = "2147483648" if is_first else "0"
    return (
        f'<hp:p id="{pid}" paraPrIDRef="{para_pr_id}" styleIDRef="{style_id}" '
        f'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_pr_id}"><hp:t>{escaped}</hp:t></hp:run>'
        f'{lineseg_xml}</hp:p>'
    )


def make_cell_content(text: str, char_pr_id: str = CHARPR_BLACK,
                      para_pr_id: str = "27",
                      style_id: str = "0",
                      lineseg_xml: str = DEFAULT_LINESEG,
                      blank_char_pr_id: str | None = None) -> str:
    """여러 줄 텍스트를 여러 <hp:p> 문단으로 변환.

    blank_char_pr_id 를 주면 **빈 줄**(엔터로 띄운 줄)만 그 글자모양(작은 글자)으로
    넣어 줄 높이를 줄인다 — 줄간격이 글자크기 비례(%)라 빈 줄 높이도 같이 준다.
    """
    lines = (text or "").splitlines() or [""]
    out = []
    for i, line in enumerate(lines):
        blank = blank_char_pr_id is not None and not line.strip()
        out.append(make_paragraph_xml("" if blank else line,
                                      char_pr_id=blank_char_pr_id if blank else char_pr_id,
                                      para_pr_id=para_pr_id,
                                      style_id=style_id,
                                      is_first=(i == 0), lineseg_xml=lineseg_xml))
    return "".join(out)


def _find_clean_lineseg_in_column(xml: str, col: int) -> str | None:
    """같은 col 의 다른 row 들에서 31508(DEFAULT 시그니처) 이 아닌
    정상 lineseg 를 찾아 반환. 없으면 None.

    셀 병합으로 이상하게 큰 horzsize(>50000) 는 col 폭이 안 맞으므로 제외.
    """
    for r in range(0, 35):  # 본문 테이블 row 범위 여유분
        s, e = find_cell_sublist(xml, col, r, nth=0)
        if s is None:
            continue
        m = re.search(r'<hp:linesegarray>.*?</hp:linesegarray>',
                      xml[s:e], re.DOTALL)
        if not m:
            continue
        candidate = m.group(0)
        if 'horzsize="31508"' in candidate:
            continue  # 오염된 동족
        # 셀 병합으로 폭이 큰 lineseg 제외 (col 폭과 안 맞음)
        hm = re.search(r'horzsize="(\d+)"', candidate)
        if hm and int(hm.group(1)) < 50000:
            return candidate
    return None


def extract_cell_lineseg(xml: str, col: int, row: int, nth: int = 0) -> str:
    """해당 셀의 원본 <hp:linesegarray> 를 추출 (셀 너비 정보 보존).
    없으면 DEFAULT_LINESEG 반환.

    오염 감지: 추출된 lineseg 의 horzsize 가 31508(DEFAULT 시그니처) 이면
    이전 generation 에서 우리 fallback 이 셀에 박혀버린 자기-오염 상태.
    같은 col 의 깨끗한 lineseg 로 자동 차용해 무한 누적을 끊음.
    """
    start, end = find_cell_sublist(xml, col, row, nth=nth)
    if start is None:
        return DEFAULT_LINESEG
    content = xml[start:end]
    m = re.search(r'<hp:linesegarray>.*?</hp:linesegarray>', content, re.DOTALL)
    if not m:
        return DEFAULT_LINESEG
    lineseg = m.group(0)
    if 'horzsize="31508"' in lineseg:
        clean = _find_clean_lineseg_in_column(xml, col)
        if clean:
            return clean
    return lineseg


def _extract_cell_paragraph_attrs(xml: str, col: int, row: int, nth: int = 0) -> tuple[str, str]:
    """셀 첫 문단의 paraPrIDRef/styleIDRef를 재사용해 원본 서식을 최대한 유지."""
    start, end = find_cell_sublist(xml, col, row, nth=nth)
    if start is None:
        return "27", "0"
    content = xml[start:end]
    m = re.search(r'<hp:p\b[^>]*paraPrIDRef="(\d+)"[^>]*styleIDRef="(\d+)"', content)
    if not m:
        return "27", "0"
    return m.group(1), m.group(2)


def _extract_cell_charpr(xml: str, col: int, row: int, nth: int = 0) -> str:
    """셀 첫 run의 charPrIDRef를 재사용해 글자 크기/폰트를 원본과 맞춘다."""
    start, end = find_cell_sublist(xml, col, row, nth=nth)
    if start is None:
        return CHARPR_BLACK
    content = xml[start:end]
    m = re.search(r'<hp:run\b[^>]*charPrIDRef="(\d+)"', content)
    if not m:
        return CHARPR_BLACK
    return m.group(1)


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


def replace_cell(xml, col, row, text, override_color_id=None, nth=0,
                 blank_char_pr_id=None):
    """셀 내용을 새 <hp:p> 블록으로 교체. lineseg 는 원본 셀에서 추출하여
    셀 너비에 맞는 자간 유지. blank_char_pr_id: 빈 줄용 작은 글자모양(선택)."""
    start, end = find_cell_sublist(xml, col, row, nth=nth)
    if start is None:
        return xml
    para_pr, style_id = _extract_cell_paragraph_attrs(xml, col, row, nth=nth)
    base_char_pr = _extract_cell_charpr(xml, col, row, nth=nth)
    char_pr = override_color_id if override_color_id is not None else base_char_pr
    lineseg = extract_cell_lineseg(xml, col, row, nth=nth)
    new_content = make_cell_content(text, char_pr_id=char_pr,
                                    para_pr_id=para_pr,
                                    style_id=style_id,
                                    lineseg_xml=lineseg,
                                    blank_char_pr_id=blank_char_pr_id)
    return xml[:start] + new_content + xml[end:]


def _charpr_xml(header_xml: str, char_pr_id: str) -> str | None:
    """id 가 char_pr_id 인 <hh:charPr>…</hh:charPr> 블록. 없으면 None."""
    m = re.search(rf'<hh:charPr\s+id="{char_pr_id}"[^>]*?>.*?</hh:charPr>',
                  header_xml, re.DOTALL)
    return m.group(0) if m else None


def normalize_charpr_ids(header_xml: str) -> str:
    """charPr 의 id 를 목록 순서(0,1,2…)와 같게 맞춘다.

    한글은 참조를 '순서'로 찾으므로, 옛 버그판이 만든 파일(중간에 끼운 charPr 때문에
    id 와 순서가 어긋남)을 템플릿으로 올려도 **한글이 보여주던 모양 그대로** 맞춰진다.
    이미 맞는 파일은 바뀌지 않는다.
    """
    seq = iter(range(1_000_000))
    header_xml = re.sub(r'(<hh:charPr\s+id=")\d+(")',
                        lambda m: f'{m.group(1)}{next(seq)}{m.group(2)}',
                        header_xml)
    n = len(re.findall(r'<hh:charPr\s+id=', header_xml))
    return re.sub(r'(<hh:charProperties[^>]*itemCnt=")\d+(")',
                  rf'\g<1>{n}\g<2>', header_xml, count=1)


def _append_charpr(header_xml: str, charpr_xml: str) -> tuple[str, str]:
    """charPr 를 목록 **맨 끝**에 붙이고 새 id(=순서 번호) 반환.

    ⚠️ 중간에 끼우면 한글이 그 뒤 참조를 한 칸씩 밀려 읽는다(파일 머리 설명 참고).
    """
    new_id = str(len(re.findall(r'<hh:charPr\s+id=', header_xml)))
    charpr_xml = re.sub(r'id="\d+"', f'id="{new_id}"', charpr_xml, count=1)
    header_xml = header_xml.replace('</hh:charProperties>',
                                    charpr_xml + '</hh:charProperties>', 1)
    header_xml = re.sub(
        r'(<hh:charProperties[^>]*itemCnt=")(\d+)(")',
        lambda m: f'{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}',
        header_xml, count=1,
    )
    return header_xml, new_id


def ensure_blue_charpr(header_xml: str, base_id: str,
                       cache: dict) -> tuple[str, str]:
    """base_id 글꼴·크기는 그대로 두고 **파랑 + 굵게**인 charPr id 반환(획득 데이터용).

    예전엔 헤더에서 처음 보이는 파란 charPr 를 그냥 썼는데, 템플릿에 따라
    그게 굵지 않은 것이어서 굵은 글씨가 안 나왔다.
    """
    if base_id in cache:
        return header_xml, cache[base_id]
    base_xml = _charpr_xml(header_xml, base_id)
    if base_xml is None:
        base_xml = _charpr_xml(header_xml, CHARPR_BLACK)
        if base_xml is None:
            raise RuntimeError("템플릿에 기본 검정 charPr(15)가 없습니다.")
    is_blue = 'textColor="#0000FF"' in base_xml.split('>', 1)[0]
    if is_blue and '<hh:bold/>' in base_xml:
        cache[base_id] = base_id          # 이미 파랑+굵게 → 그대로 사용
        return header_xml, base_id
    blue_xml = re.sub(r'textColor="#[0-9A-Fa-f]{6}"', 'textColor="#0000FF"',
                      base_xml, count=1)
    if '<hh:bold/>' not in blue_xml:
        # 스키마 순서상 bold 는 underline 바로 앞(italic 뒤)에 온다
        blue_xml = blue_xml.replace('<hh:underline', '<hh:bold/><hh:underline', 1)
    header_xml, new_id = _append_charpr(header_xml, blue_xml)
    cache[base_id] = new_id
    return header_xml, new_id


def ensure_black_charpr(header_xml: str, base_id: str,
                        cache: dict) -> tuple[str, str]:
    """base_id 글자속성(글꼴·크기)은 그대로 두고 **글자색만 검정**인 charPr id 반환.

    템플릿(지난 취합본)의 셀 글자색이 빨강 등으로 남아 있으면 새 본문까지
    그 색을 물려받는 문제가 있어, 같은 서식의 '검정 판'을 만들어 쓴다.
    이미 검정(또는 색 지정 없음)이면 base_id 를 그대로 쓴다.
    """
    if base_id in cache:
        return header_xml, cache[base_id]

    base_xml = _charpr_xml(header_xml, base_id)
    if base_xml is None:
        cache[base_id] = base_id
        return header_xml, base_id

    col_m = re.search(r'textColor="#([0-9A-Fa-f]{6})"', base_xml)
    if not col_m or col_m.group(1).upper() == "000000":
        cache[base_id] = base_id          # 이미 검정 → 그대로 사용
        return header_xml, base_id

    black_xml = re.sub(r'textColor="#[0-9A-Fa-f]{6}"',
                       'textColor="#000000"', base_xml, count=1)
    header_xml, new_id = _append_charpr(header_xml, black_xml)
    cache[base_id] = new_id
    return header_xml, new_id


def cell_size(xml: str, col: int, row: int, nth: int = 0):
    """셀의 (가로, 세로) 크기 — HWPUNIT(1/7200인치, 1pt=100). 못 찾으면 (None, None)."""
    addr_str = f'cellAddr colAddr="{col}" rowAddr="{row}"'
    pos = 0
    for _ in range(nth + 1):
        pos = xml.find(addr_str, pos)
        if pos == -1:
            return None, None
        addr_pos = pos
        pos += len(addr_str)
    # cellSz 는 cellAddr 바로 뒤에 온다
    m = re.search(r'<hp:cellSz\s+width="(\d+)"\s+height="(\d+)"',
                  xml[addr_pos:addr_pos + 600])
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def charpr_height(header_xml: str, char_pr_id: str):
    """charPr 의 글자 크기(HWPUNIT). 900 = 9pt. 못 찾으면 None."""
    m = re.search(rf'<hh:charPr\s+id="{char_pr_id}"[^>]*\bheight="(\d+)"',
                  header_xml)
    return int(m.group(1)) if m else None


def ensure_smaller_charpr(header_xml: str, base_id: str, cache: dict,
                          delta_pt: int = 1) -> tuple[str, str]:
    """base_id 와 같은 서식이되 글자 크기만 delta_pt 만큼 작은 charPr id 반환.

    칸 분량을 넘치는 긴 글이 다음 장으로 밀리는 것을 줄이려는 용도.
    ⚠️ 1pt 까지만 줄인다 — 더 줄이면 회의에서 안 보인다(사용자 요청).
    """
    key = (base_id, delta_pt)
    if key in cache:
        return header_xml, cache[key]
    base_xml = _charpr_xml(header_xml, base_id)
    if base_xml is None:
        cache[key] = base_id
        return header_xml, base_id
    h = re.search(r'\bheight="(\d+)"', base_xml)
    if not h:
        cache[key] = base_id
        return header_xml, base_id
    new_h = int(h.group(1)) - delta_pt * 100
    if new_h < 700:                       # 7pt 미만은 만들지 않음
        cache[key] = base_id
        return header_xml, base_id
    small = re.sub(r'\bheight="\d+"', f'height="{new_h}"', base_xml, count=1)
    header_xml, new_id = _append_charpr(header_xml, small)
    cache[key] = new_id
    return header_xml, new_id


BLANK_LINE_RATIO = 0.5   # 빈 줄 높이 = 본문 줄의 절반(사용자 요청 2026-10)


def ensure_blank_charpr(header_xml: str, base_id: str,
                        cache: dict) -> tuple[str, str]:
    """빈 줄(엔터로 띄운 줄)용 — base_id 와 같되 글자 크기만 BLANK_LINE_RATIO 배인
    charPr id. 줄간격이 글자크기 비례(%)라 빈 줄 높이가 그만큼 줄어든다."""
    if base_id in cache:
        return header_xml, cache[base_id]
    base_xml = _charpr_xml(header_xml, base_id)
    h = re.search(r'\bheight="(\d+)"', base_xml) if base_xml else None
    if not h:
        cache[base_id] = base_id
        return header_xml, base_id
    new_h = max(int(int(h.group(1)) * BLANK_LINE_RATIO), 100)
    small = re.sub(r'\bheight="\d+"', f'height="{new_h}"', base_xml, count=1)
    header_xml, new_id = _append_charpr(header_xml, small)
    cache[base_id] = new_id
    return header_xml, new_id


def overflows_cell(text: str, cell_w: int, cell_h: int, font_h: int) -> bool:
    """이 글이 칸을 넘치는지 어림 계산.

    한글은 글자 하나가 대략 글자크기(정사각)만큼, 영문·숫자는 절반쯤 차지한다.
    줄 높이는 글자크기의 약 1.25배로 본다. 여백을 감안해 안쪽 폭을 조금 줄여 잡는다.
    """
    if not (cell_w and cell_h and font_h):
        return False
    inner_w = max(cell_w - 500, font_h)          # 좌우 여백 대략 제외
    inner_h = max(cell_h - 300, font_h)
    per_line = max(int(inner_w / font_h), 1)     # 한 줄에 들어갈 한글 글자 수
    line_h = font_h * 1.25
    lines = 0
    for ln in (text or "").split("\n"):
        if not ln.strip():
            lines += BLANK_LINE_RATIO        # 빈 줄은 작은 글자로 들어간다
            continue
        w = sum(0.5 if ch.isascii() else 1.0 for ch in ln)
        lines += max(1, -(-int(w * 10) // (per_line * 10)))   # 올림
    return lines * line_h > inner_h


def strip_linesegarrays(xml: str) -> str:
    """모든 <hp:linesegarray>…</hp:linesegarray> 를 빈 껍데기로 만든다.

    linesegarray 는 '줄바꿈 위치 캐시'라서, 템플릿 값이 새 글자수와 안 맞으면
    글자가 셀 밖으로 삐져나온다. 비워 두면 한글이 열 때 스스로 다시 계산한다.
    (직접 줄 수를 추정해 만들어 넣는 방식은 페이지 배치가 밀려 실패했음)
    """
    return re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>',
                  '<hp:linesegarray/>', xml, flags=re.DOTALL)


def _calendar_bmp_name(files) -> str | None:
    """템플릿의 달력 그림(BinData 의 첫 BMP) 경로. 없으면 None."""
    for name in files:
        if name.startswith('BinData/') and name.lower().endswith('.bmp'):
            return name
    return None


def calendar_bmp_size(template_bytes: bytes):
    """템플릿 달력 BMP 의 (가로, 세로) 픽셀. 달력 그림이 없으면 None.

    템플릿마다 달력 크기가 다르다(1442×857, 1588×855, 2131×1202…). 새 달력을
    **같은 크기**로 그려야 원본과 구조가 같은 파일이 된다.
    """
    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as z:
        name = _calendar_bmp_name(z.namelist())
        if not name:
            return None
        head = z.read(name)[:26]
    if head[:2] != b'BM':
        return None
    w = int.from_bytes(head[18:22], 'little', signed=True)
    h = int.from_bytes(head[22:26], 'little', signed=True)
    return abs(w), abs(h)


def _manifest_item_id(hpf: bytes, href: str) -> str | None:
    """content.hpf 에서 href 에 해당하는 manifest id(예: image1)."""
    m = re.search(rf'<opf:item\s+id="([^"]+)"\s+href="{re.escape(href)}"',
                  hpf.decode('utf-8', errors='replace'))
    return m.group(1) if m else None


def _unclip_picture(xml: str, item_id: str) -> str:
    """그 그림의 자르기(imgClip)를 없앤다 — 템플릿 달력에 걸려 있던 자르기가
    새로 그린 달력의 양 끝(일·토요일 칸)을 잘라먹지 않게."""
    def fix(m):
        pic = m.group(0)
        if f'binaryItemIDRef="{item_id}"' not in pic:
            return pic
        o = re.search(r'<hp:orgSz\s+width="(\d+)"\s+height="(\d+)"', pic)
        if not o:
            return pic
        return re.sub(r'<hp:imgClip\b[^>]*/>',
                      f'<hp:imgClip left="0" right="{o.group(1)}" '
                      f'top="0" bottom="{o.group(2)}"/>', pic, count=1)
    return re.sub(r'<hp:pic\b.*?</hp:pic>', fix, xml, flags=re.DOTALL)


def build_report(template_bytes: bytes, submissions: dict,
                 title_date: str,
                 period_start: str, period_end: str,
                 plan_start: str, plan_end: str,
                 calendar_bmp: bytes | None = None,
                 relayout: bool = True,
                 calendar_ym: tuple | None = None,
                 shrink_overflow: bool = True,
                 shrunk_out: list | None = None) -> bytes:
    """submissions = {이름: {필드키: 텍스트, ...}}

    shrink_overflow=True 면 칸을 넘치는 긴 글만 **1pt 작게** 넣어 다음 장으로
    밀리는 것을 줄인다. 줄인 칸 목록은 shrunk_out 리스트에 담아 돌려준다.
    """
    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as zin:
        xml = zin.read('Contents/section0.xml').decode('utf-8')
        header = zin.read('Contents/header.xml').decode('utf-8')
        # 원본 ZipInfo 전체를 보존 (external_attr, create_system, create_version,
        # extract_version, flag_bits, date_time 등 한글이 검사할 가능성 있는 모든 메타)
        entry_order = [info.filename for info in zin.infolist()]
        original_infos = {info.filename: info for info in zin.infolist()}
        all_files = {name: zin.read(name) for name in zin.namelist()}

    header = normalize_charpr_ids(header)
    _blue_cache: dict = {}    # 원본 charPr id → 같은 서식의 '파랑+굵게 판' id
    _black_cache: dict = {}   # 원본 charPr id → 같은 서식의 '검정 판' id
    _small_cache: dict = {}   # (charPr id, 줄일 pt) → 1pt 작은 판 id
    _blank_cache: dict = {}   # charPr id → 빈 줄용(글자 절반) 판 id
    shrunk: list = []         # 실제로 작게 넣은 칸 목록(사용자 안내용)

    # 변경 추적(트랙 체인지) 설정 끄기 — 한글이 파일 열 때 "변경 내용 표시"
    # 모드로 자동 전환되어 글자가 겹쳐 보이는 착시 방지.
    # flags="56" (기본) → flags="0" 으로 비트 모두 해제.
    header = re.sub(
        r'<hh:trackchageConfig\s+flags="\d+"\s*/>',
        '<hh:trackchageConfig flags="0"/>',
        header,
    )

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
            # acquired_data 필드: "획득 데이터:" prefix 없으면 자동 추가
            if field == "acquired_data":
                stripped = text.strip()
                if stripped and not stripped.startswith("획득 데이터"):
                    text = f"획득 데이터: {stripped}"
                elif not stripped:
                    text = "획득 데이터:"
            # 원본 서식(글꼴·크기)은 유지하고 파랑은 '파랑+굵게', 그 외는 글자색만 검정으로.
            # (템플릿에 남아있던 빨간 글씨색이 새 본문에 물려지는 문제 방지)
            _base = _extract_cell_charpr(xml, col, row, nth=nth)
            if color == "blue":
                header, override = ensure_blue_charpr(header, _base, _blue_cache)
            else:
                header, override = ensure_black_charpr(header, _base, _black_cache)
            # 칸 분량을 넘치면 그 칸만 1pt 작게 — 다음 장으로 밀리는 것을 줄인다.
            # 1pt 까지만(더 줄이면 회의에서 안 보임). 그래도 넘치면 그냥 둔다.
            if shrink_overflow and text.strip():
                _w, _h = cell_size(xml, col, row, nth=nth)
                _fh = charpr_height(header, override)
                if overflows_cell(text, _w, _h, _fh):
                    header, override = ensure_smaller_charpr(
                        header, override, _small_cache, delta_pt=1)
                    shrunk.append(f"{m['name']}·{field}")
            # 엔터로 띄운 빈 줄은 글자 크기를 절반으로 — 띄운 간격이 너무 넓다는 요청
            blank_id = None
            if any(not ln.strip() for ln in text.splitlines()):
                header, blank_id = ensure_blank_charpr(header, override, _blank_cache)
            xml = replace_cell(xml, col, row, text,
                               override_color_id=override,
                               nth=nth, blank_char_pr_id=blank_id)

    # 달력 캡션 "…일정 (2026년 06월)" 도 보고 주차의 달로 갱신
    if calendar_ym:
        _y, _m = calendar_ym
        xml = re.sub(r'(일정\s*\()\d{4}년\s*\d{1,2}월(\))',
                     rf'\g<1>{_y}년 {_m:02d}월\g<2>', xml)

    # 표 밖 넘침 보정(선택): 줄바꿈 캐시를 비워 한글이 다시 계산하게 함
    if relayout:
        xml = strip_linesegarrays(xml)

    all_files['Contents/section0.xml'] = xml.encode('utf-8')
    all_files['Contents/header.xml'] = header.encode('utf-8')

    # 월간 달력 이미지 교체 — 템플릿에 박힌 옛 달력이 그대로 나오는 문제 해결.
    # 원본과 '같은 픽셀 크기'의 BMP를 넣는다(calendar_bmp_size 로 크기를 맞춰 그림).
    _bmp = _calendar_bmp_name(all_files)
    if calendar_bmp and _bmp:
        all_files[_bmp] = calendar_bmp
        _item = _manifest_item_id(all_files.get('Contents/content.hpf', b''), _bmp)
        if _item:
            xml = _unclip_picture(xml, _item)
            all_files['Contents/section0.xml'] = xml.encode('utf-8')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zout:
        for name in entry_order:
            data = all_files[name]
            orig = original_infos[name]
            zinfo = zipfile.ZipInfo(name, date_time=orig.date_time)
            zinfo.compress_type = orig.compress_type
            zinfo.external_attr = orig.external_attr
            zinfo.create_system = orig.create_system
            zinfo.create_version = orig.create_version
            zinfo.extract_version = orig.extract_version
            zinfo.flag_bits = orig.flag_bits
            zinfo.extra = orig.extra
            zout.writestr(zinfo, data)

    # Python zipfile 이 writestr 과정에서 flag_bits를 자동 변경(특히 0x04 clear)
    # 한글은 일부 엔트리의 flag_bits=0x04 를 기대하므로 바이너리 레벨에서 복원
    raw = buf.getvalue()
    raw = _patch_zip_flag_bits(raw, original_infos)
    if shrunk_out is not None:
        shrunk_out.extend(shrunk)
    return raw


def _patch_zip_flag_bits(zip_bytes: bytes, original_infos: dict) -> bytes:
    """ZIP 로컬 파일 헤더와 중앙 디렉토리 엔트리의 flag_bits 필드를
    원본 ZipInfo.flag_bits 값으로 복원."""
    data = bytearray(zip_bytes)
    LFH_SIG = b'PK\x03\x04'
    CD_SIG = b'PK\x01\x02'

    # 로컬 파일 헤더 스캔
    pos = 0
    while True:
        idx = data.find(LFH_SIG, pos)
        if idx == -1:
            break
        # LFH 구조: sig(4) ver(2) flag(2) method(2) time(2) date(2) crc(4) csize(4) usize(4) nlen(2) elen(2) name extra
        name_len = int.from_bytes(data[idx + 26:idx + 28], 'little')
        extra_len = int.from_bytes(data[idx + 28:idx + 30], 'little')
        name = data[idx + 30:idx + 30 + name_len].decode('utf-8', errors='replace')
        if name in original_infos:
            target_flag = original_infos[name].flag_bits
            data[idx + 6:idx + 8] = target_flag.to_bytes(2, 'little')
        # 다음으로
        comp_size = int.from_bytes(data[idx + 18:idx + 22], 'little')
        pos = idx + 30 + name_len + extra_len + comp_size

    # 중앙 디렉토리 스캔
    pos = 0
    while True:
        idx = data.find(CD_SIG, pos)
        if idx == -1:
            break
        # CD 구조: sig(4) vermade(2) verneeded(2) flag(2) method(2) ...
        name_len = int.from_bytes(data[idx + 28:idx + 30], 'little')
        extra_len = int.from_bytes(data[idx + 30:idx + 32], 'little')
        cmt_len = int.from_bytes(data[idx + 32:idx + 34], 'little')
        name = data[idx + 46:idx + 46 + name_len].decode('utf-8', errors='replace')
        if name in original_infos:
            target_flag = original_infos[name].flag_bits
            data[idx + 8:idx + 10] = target_flag.to_bytes(2, 'little')
        pos = idx + 46 + name_len + extra_len + cmt_len

    return bytes(data)


def load_template(template_path: str) -> bytes:
    with open(template_path, 'rb') as f:
        return f.read()
