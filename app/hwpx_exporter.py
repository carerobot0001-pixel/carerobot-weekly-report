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
                      lineseg_xml: str = DEFAULT_LINESEG) -> str:
    """여러 줄 텍스트를 여러 <hp:p> 문단으로 변환."""
    lines = (text or "").splitlines() or [""]
    return "".join(
        make_paragraph_xml(line, char_pr_id=char_pr_id,
                           para_pr_id=para_pr_id,
                           style_id=style_id,
                           is_first=(i == 0), lineseg_xml=lineseg_xml)
        for i, line in enumerate(lines)
    )


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


def replace_cell(xml, col, row, text, override_color_id=None, nth=0):
    """셀 내용을 새 <hp:p> 블록으로 교체. lineseg 는 원본 셀에서 추출하여
    셀 너비에 맞는 자간 유지."""
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
                                    lineseg_xml=lineseg)
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


def ensure_black_charpr(header_xml: str, base_id: str,
                        cache: dict) -> tuple[str, str]:
    """base_id 글자속성(글꼴·크기)은 그대로 두고 **글자색만 검정**인 charPr id 반환.

    템플릿(지난 취합본)의 셀 글자색이 빨강 등으로 남아 있으면 새 본문까지
    그 색을 물려받는 문제가 있어, 같은 서식의 '검정 판'을 만들어 쓴다.
    이미 검정(또는 색 지정 없음)이면 base_id 를 그대로 쓴다.
    """
    if base_id in cache:
        return header_xml, cache[base_id]

    m = re.search(rf'<hh:charPr\s+id="{base_id}"[^>]*?>.*?</hh:charPr>',
                  header_xml, re.DOTALL)
    if not m:
        cache[base_id] = base_id
        return header_xml, base_id
    base_xml = m.group(0)

    col_m = re.search(r'textColor="#([0-9A-Fa-f]{6})"', base_xml)
    if not col_m or col_m.group(1).upper() == "000000":
        cache[base_id] = base_id          # 이미 검정 → 그대로 사용
        return header_xml, base_id

    max_id = max(int(x) for x in re.findall(r'<hh:charPr\s+id="(\d+)"', header_xml))
    new_id = str(max_id + 1)
    black_xml = re.sub(r'id="\d+"', f'id="{new_id}"', base_xml, count=1)
    black_xml = re.sub(r'textColor="#[0-9A-Fa-f]{6}"',
                       'textColor="#000000"', black_xml, count=1)
    header_xml = header_xml.replace(base_xml, base_xml + black_xml)
    header_xml = re.sub(
        r'(<hh:charProperties[^>]*itemCnt=")(\d+)(")',
        lambda mm: f'{mm.group(1)}{int(mm.group(2)) + 1}{mm.group(3)}',
        header_xml, count=1,
    )
    cache[base_id] = new_id
    return header_xml, new_id


def strip_linesegarrays(xml: str) -> str:
    """모든 <hp:linesegarray>…</hp:linesegarray> 를 빈 껍데기로 만든다.

    linesegarray 는 '줄바꿈 위치 캐시'라서, 템플릿 값이 새 글자수와 안 맞으면
    글자가 셀 밖으로 삐져나온다. 비워 두면 한글이 열 때 스스로 다시 계산한다.
    (직접 줄 수를 추정해 만들어 넣는 방식은 페이지 배치가 밀려 실패했음)
    """
    return re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>',
                  '<hp:linesegarray/>', xml, flags=re.DOTALL)


def build_report(template_bytes: bytes, submissions: dict,
                 title_date: str,
                 period_start: str, period_end: str,
                 plan_start: str, plan_end: str,
                 calendar_bmp: bytes | None = None,
                 relayout: bool = False) -> bytes:
    """submissions = {이름: {필드키: 텍스트, ...}}"""
    with zipfile.ZipFile(io.BytesIO(template_bytes), 'r') as zin:
        xml = zin.read('Contents/section0.xml').decode('utf-8')
        header = zin.read('Contents/header.xml').decode('utf-8')
        # 원본 ZipInfo 전체를 보존 (external_attr, create_system, create_version,
        # extract_version, flag_bits, date_time 등 한글이 검사할 가능성 있는 모든 메타)
        entry_order = [info.filename for info in zin.infolist()]
        original_infos = {info.filename: info for info in zin.infolist()}
        all_files = {name: zin.read(name) for name in zin.namelist()}

    header, blue_id = ensure_blue_charpr(header)
    color_to_id = {"black": CHARPR_BLACK, "blue": blue_id}
    _black_cache: dict = {}   # 원본 charPr id → 같은 서식의 '검정 판' id

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
            # 파란색은 파란 charPr, 그 외(검정)는 원본 서식 유지하되 글자색만 검정으로.
            # (템플릿에 남아있던 빨간 글씨색이 새 본문에 물려지는 문제 방지)
            if color == "blue":
                override = color_to_id["blue"]
            else:
                _base = _extract_cell_charpr(xml, col, row, nth=nth)
                header, override = ensure_black_charpr(header, _base, _black_cache)
            xml = replace_cell(xml, col, row, text,
                               override_color_id=override,
                               nth=nth)

    # 표 밖 넘침 보정(선택): 줄바꿈 캐시를 비워 한글이 다시 계산하게 함
    if relayout:
        xml = strip_linesegarrays(xml)

    all_files['Contents/section0.xml'] = xml.encode('utf-8')
    all_files['Contents/header.xml'] = header.encode('utf-8')

    # 월간 달력 이미지 교체 — 템플릿에 박힌 옛 달력이 그대로 나오는 문제 해결.
    # 원본과 '같은 픽셀 크기'의 BMP만 넣으면 section0.xml 의 크기 정보는 그대로 OK.
    if calendar_bmp:
        for _name in list(all_files):
            if _name.startswith('BinData/') and _name.lower().endswith('.bmp'):
                all_files[_name] = calendar_bmp
                break

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
