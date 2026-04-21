"""사용자 최신 파일 진단 - 한글 못여는 원인 집중 분석"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import zipfile, glob, re, os

os.chdir('..')
new_path = [f for f in sorted(glob.glob('*.hwpx'), key=os.path.getmtime)
            if '04.22' in f][-1]
orig_path = [f for f in glob.glob('*.hwpx') if '04.24' in f][0]
print(f'최신 생성본: {new_path}')
print(f'원본 템플릿: {orig_path}\n')

# 생성본 ZIP 메타
print('--- 생성본 ZIP 메타 (원본과 일치해야 함) ---')
import time
with zipfile.ZipFile(new_path, 'r') as z:
    for info in z.infolist():
        print(f'  {info.filename:30s} fb={info.flag_bits} cs={info.create_system} cv={info.create_version} m={info.compress_type}')
    new_xml = z.read('Contents/section0.xml').decode('utf-8')
    new_hdr = z.read('Contents/header.xml').decode('utf-8')

with zipfile.ZipFile(orig_path, 'r') as z:
    orig_xml = z.read('Contents/section0.xml').decode('utf-8')
    orig_hdr = z.read('Contents/header.xml').decode('utf-8')

# header.xml 비교
print(f'\n--- header.xml ---')
print(f'원본 {len(orig_hdr)} bytes, 생성본 {len(new_hdr)} bytes')
if orig_hdr == new_hdr:
    print('  완전 일치')
else:
    # diff 위치
    for i in range(min(len(orig_hdr), len(new_hdr))):
        if orig_hdr[i] != new_hdr[i]:
            print(f'  첫 차이 위치: {i}')
            print(f'  원본: ...{orig_hdr[max(0,i-50):i+100]!r}')
            print(f'  생성: ...{new_hdr[max(0,i-50):i+100]!r}')
            break
    print(f'  길이 차이: {len(new_hdr) - len(orig_hdr)}')

# 태그 쌍 일치
print(f'\n--- section0.xml 태그 쌍 ---')
for tag in ['hp:tbl','hp:tc','hp:p','hp:run','hp:subList','hp:t']:
    o = len(re.findall(f'<{tag}\\b[^>]*[^/]>', new_xml))
    c = len(re.findall(f'</{tag}>', new_xml))
    sc = len(re.findall(f'<{tag}\\b[^>]*/>', new_xml))
    status = 'OK' if (o == c) else 'MISMATCH'
    print(f'  {tag}: 열림={o}, 닫힘={c}, self-close={sc}  {status}')

# XML 유효성
from xml.etree import ElementTree as ET
try: ET.fromstring(new_xml); print('\nsection0 XML: 유효')
except ET.ParseError as e: print(f'\nsection0 XML 에러: {e}')
try: ET.fromstring(new_hdr); print('header XML: 유효')
except ET.ParseError as e: print(f'header XML 에러: {e}')

# 가짜 닫힘이 없는지, 특이한 패턴 확인
if '<hp:run' in new_xml:
    # self-closing 없는 run 몇 개인지
    runs_open = re.findall(r'<hp:run\b[^>]*[^/]>', new_xml)
    runs_close = re.findall(r'</hp:run>', new_xml)
    runs_sc = re.findall(r'<hp:run\b[^>]*/>', new_xml)
    print(f'\nrun 상세: 열림 {len(runs_open)}, 닫힘 {len(runs_close)}, self-close {len(runs_sc)}')

# 김건양 r14 c4 셀 완전한 dump
tbls = re.findall(r'<hp:tbl\b[^>]*>.*?</hp:tbl>', new_xml, re.DOTALL)
main = [t for t in tbls if '최혜민' in t and '정지수' in t][0]
pos = main.find('cellAddr colAddr="4" rowAddr="14"')
tc_s = main.rfind('<hp:tc ', 0, pos)
tc_e = main.find('</hp:tc>', pos) + len('</hp:tc>')
tc = main[tc_s:tc_e]
print(f'\n--- 김건양 r14 c4 전체 셀 (길이 {len(tc)}) ---')
print(tc[:2000])
if len(tc) > 2000:
    print(f'\n[...중간 생략 {len(tc)-4000}자...]\n')
    print(tc[-2000:])
