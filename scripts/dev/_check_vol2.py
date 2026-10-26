import json, sys
from pathlib import Path

sys.path.insert(0, r'D:\code\河狸记词\data\WordFrequency\scripts')
from build_wordfreq import norm, BCP47

FF = Path(r'F:\data\WordFrequency\wordfreq')
GIB = 1024 ** 3
SRCS = ('wikipedia', 'ultrafineweb_l3', 'fineweb2_hq_plus')

langs = {}
for sn in SRCS:
    for d in sorted((FF / sn).iterdir()):
        if not d.is_dir() or not (d / 'meta.json').exists():
            continue
        m = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
        langs.setdefault(norm(d.name), []).append(
            dict(src=sn, dir=d.name, tb=m.get('text_bytes', 0), tt=m.get('total_tokens', 0)))

meta = json.loads(Path(r'D:\code\河狸记词\data\hf-upload\WordFrequency\meta.json').read_text(encoding='utf-8'))['languages']

print('=== A. 合计 >=1GiB 但没有任何单一来源 >=1GiB（按来源判定会漏掉）===')
miss = []
for iso, ents in langs.items():
    by_src = {}
    for e in ents:
        by_src[e['src']] = by_src.get(e['src'], 0) + e['tb']
    tot = sum(e['tb'] for e in ents)
    mx = max(by_src.values())
    if tot >= GIB and mx < GIB:
        miss.append((tot, iso, by_src))
for tot, iso, by_src in sorted(miss, reverse=True):
    print(f'  {iso:8} total={tot/GIB:5.2f} GiB  按来源: '
          + ', '.join(f'{s}={v/GIB:.2f}' for s, v in by_src.items())
          + f'   [{"in meta" if iso in meta else "NOT in meta"}]')

print()
print('=== B. 合计 <1GiB 但离 1GiB 很近 (0.9~1.0) ===')
near = []
for iso, ents in langs.items():
    tot = sum(e['tb'] for e in ents)
    if 0.9 * GIB <= tot < GIB:
        near.append((tot, iso, [(e['src'], e['dir'], e['tb']) for e in ents]))
for tot, iso, ents in sorted(near, reverse=True):
    print(f'  {iso:8} total={tot/GIB:.3f} GiB (差 {(GIB-tot)/1024**2:.0f} MiB)')
    for s, d, tb in ents:
        print(f'      {s:20} {d:16} {tb/GIB:.3f} GiB')

print()
print('=== C. 目录名 != iso 的映射（norm 改写了代码）===')
m = {}
for iso, ents in langs.items():
    for e in ents:
        if e['dir'] != iso:
            m.setdefault(iso, []).append(e['dir'])
for iso in sorted(m):
    print(f'  {iso:8} <- {m[iso]}')

print()
print('=== D. 一个 iso 收了多个不同语种代码（可能误合并）===')
for iso in sorted(m):
    if len(set(m[iso])) > 1 and iso in meta:
        print(f'  {iso:8} <- {m[iso]}')
