"""content.hpf / manifest 정합성 확인 + 원본 대비 구조 차이 검출"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import zipfile, glob, os, re

os.chdir('..')
new_path = sorted([f for f in glob.glob('*.hwpx') if '04.22' in f],
                  key=os.path.getmtime)[-1]
orig_path = [f for f in glob.glob('*.hwpx') if '04.24' in f][0]

print(f'생성본: {new_path}')
print(f'원본: {orig_path}\n')

for label, p in [('원본', orig_path), ('생성본', new_path)]:
    print(f'=== {label} 파일 내부 비교 ===')
    with zipfile.ZipFile(p, 'r') as z:
        for name in ['Contents/content.hpf', 'META-INF/manifest.xml',
                     'META-INF/container.xml', 'META-INF/container.rdf',
                     'version.xml', 'settings.xml']:
            if name in z.namelist():
                data = z.read(name).decode('utf-8', errors='replace')
                print(f'\n--- {name} ({len(data)} chars) ---')
                print(data[:1500])
    print('\n')
