"""HWPX diff - from app dir."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import zipfile, glob, re, os

os.chdir('..')
files = sorted(glob.glob('*.hwpx'))
print(f'전체 HWPX 개수: {len(files)}')
# 04.22 포함 파일 찾기
candidates = [f for f in files if '04.22' in f]
print(f'04.22 파일: {candidates}')

if not candidates:
    print('04.22 파일 없음 - 모든 파일:')
    for f in files: print(f'  {f}')
    sys.exit()

new_path = candidates[0]

# 원본 템플릿 - 04.15 또는 04.24 중
orig_candidates = [f for f in files if '04.24' in f]
if not orig_candidates:
    orig_candidates = [f for f in files if '04.15' in f and '취합완료' in f]
orig_path = orig_candidates[0]

print(f'\n원본 template: {orig_path}')
print(f'사용자 생성본: {new_path}\n')

with zipfile.ZipFile(orig_path, 'r') as z:
    orig = z.read('Contents/section0.xml').decode('utf-8')
    orig_hdr = z.read('Contents/header.xml').decode('utf-8')
with zipfile.ZipFile(new_path, 'r') as z:
    new = z.read('Contents/section0.xml').decode('utf-8')
    new_hdr = z.read('Contents/header.xml').decode('utf-8')

print(f'원본 section0: {len(orig):,} bytes')
print(f'생성본 section0: {len(new):,} bytes')
print(f'원본 header: {len(orig_hdr):,} bytes')
print(f'생성본 header: {len(new_hdr):,} bytes')

# header 차이 유무
if orig_hdr == new_hdr:
    print('header.xml 완전 동일')
else:
    print('header.xml 차이 있음')

# XML 검증
from xml.etree import ElementTree as ET
try:
    ET.fromstring(new)
    print('생성본 section0 XML 유효')
except ET.ParseError as e:
    print(f'생성본 XML 에러: {e}')
try:
    ET.fromstring(new_hdr)
    print('생성본 header XML 유효')
except ET.ParseError as e:
    print(f'생성본 header 에러: {e}')

# 첫 차이 위치
min_len = min(len(orig), len(new))
diff = 0
for i in range(min_len):
    if orig[i] != new[i]:
        diff = i
        break
if diff > 0:
    print(f'\n첫 차이 위치 (section0): {diff}')
    print(f'원본 앞: ...{orig[max(0,diff-60):diff]}')
    print(f'다른 부분 원본 (100자): {orig[diff:diff+100]!r}')
    print(f'다른 부분 생성본 (100자): {new[diff:diff+100]!r}')

# 메인 본문 테이블 검증
print(f'\n최혜민 포함: {"최혜민" in new}')
print(f'정지수 포함: {"정지수" in new}')
print(f'김건양 포함: {"김건양" in new}')
print(f'획득 데이터 포함: {"획득 데이터" in new}')

# 모든 테이블 닫힘 확인
open_tbl = len(re.findall(r'<hp:tbl\b', new))
close_tbl = len(re.findall(r'</hp:tbl>', new))
print(f'\n<hp:tbl 개수: {open_tbl}, </hp:tbl> 개수: {close_tbl}')

# 모든 tc 쌍 확인
open_tc = len(re.findall(r'<hp:tc\b', new))
close_tc = len(re.findall(r'</hp:tc>', new))
print(f'<hp:tc 개수: {open_tc}, </hp:tc> 개수: {close_tc}')

open_p = len(re.findall(r'<hp:p\b', new))
close_p = len(re.findall(r'</hp:p>', new))
print(f'<hp:p 개수: {open_p}, </hp:p> 개수: {close_p}')
