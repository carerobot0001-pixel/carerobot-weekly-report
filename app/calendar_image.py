"""취합본 마지막 장의 '월간 달력' 이미지를 매주 새로 그려 끼우기 위한 생성기.

왜 필요한가: 취합본 HWPX는 **템플릿을 복사해 텍스트만 교체**하는 방식이라,
달력이 템플릿에 이미지(BinData/image1.bmp)로 박혀 있으면 영원히 옛날 달(月)이
남는다. 그래서 같은 픽셀 크기의 BMP를 새로 그려 그 자리에 바꿔 넣는다.
(크기를 같게 하면 section0.xml 의 orgSz/scaMatrix 를 손댈 필요가 없다.)

한글 폰트: 윈도우는 맑은고딕, 리눅스(Streamlit Cloud)는 나눔고딕을 쓴다.
클라우드에서 나눔고딕을 쓰려면 레포 루트 packages.txt 에 fonts-nanum 이 필요.
"""
import calendar as _cal
import io
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# 템플릿 image1.bmp 와 동일 크기 (다르면 HWPX 쪽 크기 정보도 고쳐야 함)
DEFAULT_W, DEFAULT_H = 1442, 857

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",       # Linux(나눔)
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgun.ttf",                            # Windows(맑은고딕)
    "C:/Windows/Fonts/malgunbd.ttf",
]
_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
] + _FONT_CANDIDATES


def has_korean_font() -> bool:
    """한글 렌더 가능한 폰트가 있는지. 없으면 달력 교체를 아예 건너뛴다
    (한글이 네모(두부)로 깨진 달력이 취합본에 박히는 것을 방지)."""
    return any(os.path.exists(p) for p in _FONT_CANDIDATES)


def _font(size: int, bold: bool = False):
    for p in (_FONT_BOLD_CANDIDATES if bold else _FONT_CANDIDATES):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# 구글 캘린더 이벤트 색상(colorId) → 실제 색. 지정 없으면 캘린더 기본색(빨강).
GOOGLE_COLORS = {
    "1": (121, 134, 203), "2": (51, 182, 121), "3": (142, 36, 170),
    "4": (230, 124, 115), "5": (246, 191, 38), "6": (244, 81, 30),
    "7": (3, 155, 229), "8": (97, 97, 97), "9": (63, 81, 181),
    "10": (11, 128, 67), "11": (213, 0, 0),
}
DEFAULT_EV_COLOR = (213, 0, 0)      # #D50000 — 사업단 캘린더 기본 빨강


def _ev_info(ev: dict):
    """이벤트 → (날짜, 표시문자열, 색, 종일여부). 실패 시 (None, '', ..., False)."""
    s = ev.get("start", {}) or {}
    color = GOOGLE_COLORS.get(str(ev.get("colorId", "")), DEFAULT_EV_COLOR)
    if "date" in s:                       # 종일
        d = s["date"][:10]
        label = ev.get("summary", "") or ""
        all_day = True
    else:
        dt = (s.get("dateTime", "") or "")[:16]
        d = dt[:10]
        label = f"{dt[11:16]} {ev.get('summary', '') or ''}".strip()
        all_day = False
    try:
        return int(d[8:10]), label, color, all_day
    except Exception:
        return None, "", color, all_day


def build_calendar_bmp(year: int, month: int, events: list,
                       width: int = DEFAULT_W, height: int = DEFAULT_H) -> bytes:
    """해당 월 달력을 그려 24bit BMP 바이트로 반환."""
    W, H = width, height
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)

    f_title = _font(34, bold=True)
    f_wd = _font(20, bold=True)
    f_day = _font(19, bold=True)
    f_ev = _font(15)

    # 제목
    dr.text((18, 12), f"{year}년 {month}월", font=f_title, fill=(30, 30, 30))

    top = 62
    head_h = 34
    grid_top = top + head_h
    cell_w = (W - 24) / 7.0
    # 일요일 시작 주 배열(firstweekday=6) — 월요일 기준을 재배치하면 날짜가 어긋난다
    weeks = _cal.Calendar(firstweekday=6).monthdayscalendar(year, month)
    rows = len(weeks)
    cell_h = (H - grid_top - 12) / max(rows, 1)

    wd_names = ["일", "월", "화", "수", "목", "금", "토"]
    wd_color = [(200, 40, 40), (40, 40, 40), (40, 40, 40), (40, 40, 40),
                (40, 40, 40), (40, 40, 40), (40, 80, 200)]

    # 요일 머리글
    for i, nm in enumerate(wd_names):
        x0 = 12 + i * cell_w
        dr.rectangle([x0, top, x0 + cell_w, top + head_h], fill=(245, 241, 235),
                     outline=(200, 190, 175))
        tw = dr.textlength(nm, font=f_wd)
        dr.text((x0 + cell_w / 2 - tw / 2, top + 7), nm, font=f_wd,
                fill=wd_color[i])

    # 날짜별 일정 모으기 (종일 일정을 위로 — 구글 캘린더와 같은 순서)
    by_day: dict = {}
    for ev in events or []:
        d, label, color, all_day = _ev_info(ev)
        if d and label:
            by_day.setdefault(d, []).append((label, color, all_day))
    for d in by_day:
        by_day[d].sort(key=lambda x: (not x[2],))

    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            x0 = 12 + c * cell_w
            y0 = grid_top + r * cell_h
            dr.rectangle([x0, y0, x0 + cell_w, y0 + cell_h],
                         outline=(200, 190, 175))
            if not day:
                continue
            dr.text((x0 + 7, y0 + 4), str(day), font=f_day, fill=wd_color[c])
            # 일정 텍스트 (칸 높이에 맞춰 잘라내기)
            ys = y0 + 28
            items = by_day.get(day, [])
            line_h = 21
            maxn = max(0, int((cell_h - 30) // line_h))
            for label, color, all_day in items[:maxn]:
                if all_day:
                    # 종일: 색 채운 막대 + 흰 글씨 (구글 캘린더와 동일)
                    avail = cell_w - 12
                    txt = label
                    while dr.textlength(txt, font=f_ev) > avail - 8 and len(txt) > 1:
                        txt = txt[:-1]
                    if txt != label:
                        txt = txt[:-1] + "…"
                    dr.rectangle([x0 + 5, ys, x0 + 5 + avail, ys + 18], fill=color)
                    dr.text((x0 + 9, ys + 1), txt, font=f_ev, fill=(255, 255, 255))
                else:
                    # 시간 지정: 색 점 + 글씨
                    cy = ys + 9
                    dr.ellipse([x0 + 7, cy - 3, x0 + 13, cy + 3], fill=color)
                    avail = cell_w - 24
                    txt = label
                    while dr.textlength(txt, font=f_ev) > avail and len(txt) > 1:
                        txt = txt[:-1]
                    if txt != label:
                        txt = txt[:-1] + "…"
                    dr.text((x0 + 18, ys + 1), txt, font=f_ev, fill=(50, 50, 50))
                ys += line_h
            if len(items) > maxn:
                dr.text((x0 + 7, ys), f"+{len(items) - maxn}건", font=f_ev,
                        fill=(150, 120, 90))

    buf = io.BytesIO()
    img.save(buf, format="BMP")          # 24bit BMP
    return buf.getvalue()


def build_for_week(week_str: str, events: list,
                   width: int = DEFAULT_W, height: int = DEFAULT_H) -> bytes:
    """'YYYY-MM-DD'(보고 주차) → 그 달의 달력 이미지."""
    d = datetime.strptime(week_str, "%Y-%m-%d")
    return build_calendar_bmp(d.year, d.month, events, width, height)
