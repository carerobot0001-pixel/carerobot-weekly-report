"""HWPX diff - from Downloads folder."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import zipfile, glob, re, os

downloads = 'C:/Users/carer/Downloads'
candidates = sorted(glob.glob(os.path.join(downloads, '*04.22*.hwpx')))
print('04.22 다운로드 파일들 (수정시간 순):')
for c in candidates:
    mtime = os.path.getmtime(c)
    import time
    print(f'  {time.strftime("%H:%M:%S", time.localtime(mtime))}  {os.path.basename(c)}')

# 가장 최근 파일
new_path = max(candidates, key=os.path.getmtime)
print(f'\n최신 파일: {new_path}')

# 원본 04.24 (레포 루트의)
root_hwpx = sorted(glob.glob('../*.hwpx'))
orig_path = [f for f in root_hwpx if '04.24' in f][0]
print(f'원본 template: {orig_path}\n')

with zipfile.ZipFile(orig_path, 'r') as z:
    orig = z.read('Contents/section0.xml').decode('utf-8')
with zipfile.ZipFile(new_path, 'r') as z:
    new = z.read('Contents/section0.xml').decode('utf-8')
    hdr = z.read('Contents/header.xml').decode('utf-8')

print(f'원본 section0: {len(orig):,} bytes')
print(f'생성본 section0: {len(new):,} bytes')

# XML 검증
from xml.etree import ElementTree as ET
try:
    ET.fromstring(new); print('section0 XML 유효')
except ET.ParseError as e: print(f'section0 XML 에러: {e}')
try:
    ET.fromstring(hdr); print('header XML 유효')
except ET.ParseError as e: print(f'header XML 에러: {e}')

# 태그 쌍 확인
for tag in ['hp:tbl', 'hp:tc', 'hp:p', 'hp:run', 'hp:subList']:
    open_ = len(re.findall(f'<{tag}\\b', new))
    close = len(re.findall(f'</{tag}>', new))
    self_close = len(re.findall(f'<{tag}\\b[^>]*/>', new))
    print(f'  {tag}: open={open_}, close={close}, self-close={self_close}')

# 첫 차이점 찾기
min_len = min(len(orig), len(new))
for i in range(min_len):
    if orig[i] != new[i]:
        print(f'\n첫 차이 위치: {i}')
        print(f'원본: ...{orig[max(0,i-50):i+100]!r}')
        print(f'생성본: ...{new[max(0,i-50):i+100]!r}')
        break

# 김건양 연구실적 셀 내용
for label, data in [('원본', orig), ('생성본', new)]:
    tbls = re.findall(r'<hp:tbl\b[^>]*>.*?</hp:tbl>', data, re.DOTALL)
    main_body = [t for t in tbls if '최혜민' in t and '정지수' in t]
    if main_body:
        mb = main_body[0]
        pos = mb.find('cellAddr colAddr="4" rowAddr="14"')
        if pos > 0:
            tc_start = mb.rfind('<hp:tc ', 0, pos)
            tc_end = mb.find('</hp:tc>', pos) + len('</hp:tc>')
            tc = mb[tc_start:tc_end]
            p_count = tc.count('<hp:p')
            t_count = tc.count('<hp:t>')
            print(f'\n{label} 김건양 r14 c4: 문단={p_count}, hp:t={t_count}')
            # 첫 hp:t 내용
            t_m = re.search(r'<hp:t>([^<]*)</hp:t>', tc)
            if t_m:
                print(f'  첫 hp:t 내용: {t_m.group(1)[:80]!r}')
