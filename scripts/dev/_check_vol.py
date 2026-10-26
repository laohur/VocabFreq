import json
from pathlib import Path

FF = Path(r'F:\data\WordFrequency\wordfreq')

print('=== is 相关目录 ===')
for sn in ('wikipedia', 'ultrafineweb_l3', 'fineweb2_hq_plus'):
    p = FF / sn
    for d in sorted(p.iterdir()):
        if not d.is_dir() or not (d / 'meta.json').exists():
            continue
        if d.name.startswith('is'):
            m = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
            print(f'{sn:20} {d.name:12}')
            print('   ', {k: v for k, v in m.items() if not isinstance(v, (list, dict))})
            print('    keys:', list(m.keys()))

print()
print('=== 所有 text_bytes 完全相同的目录（疑似重复记账）===')
seen = {}
for sn in ('wikipedia', 'ultrafineweb_l3', 'fineweb2_hq_plus'):
    for d in sorted((FF / sn).iterdir()):
        if not d.is_dir() or not (d / 'meta.json').exists():
            continue
        m = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
        seen.setdefault(m.get('text_bytes', 0), []).append((sn, d.name))
dups = {k: v for k, v in seen.items() if len(v) > 1}
print(f'{len(dups)} 个重复的 text_bytes 值')
for k, v in sorted(dups.items(), reverse=True)[:15]:
    print(f'  {k:>15,}  {v}')

print()
print('=== 同一 iso 跨来源分布（norm 后有多来源/多目录的语种）===')
import sys
sys.path.insert(0, r'D:\code\河狸记词\data\WordFrequency\scripts')
from build_wordfreq import norm

multi = {}
for sn in ('wikipedia', 'ultrafineweb_l3', 'fineweb2_hq_plus'):
    for d in sorted((FF / sn).iterdir()):
        if not d.is_dir() or not (d / 'meta.json').exists():
            continue
        m = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
        multi.setdefault(norm(d.name), []).append((sn, d.name, m.get('text_bytes', 0)))
for iso, ents in sorted(multi.items()):
    srcs = {s for s, _, _ in ents}
    tot = sum(tb for _, _, tb in ents)
    if len(ents) > 1:
        print(f'{iso:10} dirs={len(ents)} srcs={sorted(srcs)} total={tot/GiB if (GiB:=1024**3) else 0:.2f} GiB')
        for s, n, tb in ents:
            print(f'    {s:20} {n:18} {tb/1024**3:.3f} GiB')
