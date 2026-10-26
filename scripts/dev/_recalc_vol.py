import json, sys
from pathlib import Path

sys.path.insert(0, r'D:\code\河狸记词\data\WordFrequency\scripts')
from build_wordfreq import norm

FF = Path(r'F:\data\WordFrequency\wordfreq')
SRCS = ('wikipedia', 'ultrafineweb_l3', 'fineweb2_hq_plus')
GiB = 1024 ** 3
GB = 1000 ** 3

# 逐个目录读 meta.json，保留字节级原始值
dirs = []
for sn in SRCS:
    for d in sorted((FF / sn).iterdir()):
        if not d.is_dir() or not (d / 'meta.json').exists():
            continue
        m = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
        dirs.append(dict(iso=norm(d.name), src=sn, dir=d.name,
                         tb=m['text_bytes'], tt=m['total_tokens'], rows=m['rows'],
                         uw=m['unique_words']))

print('=== is / la / isv 逐目录字节 ===')
for iso in ('is', 'la', 'isv'):
    print(f'--- {iso}')
    tot = 0
    by_src = {}
    for x in dirs:
        if x['iso'] != iso:
            continue
        tot += x['tb']
        by_src[x['src']] = by_src.get(x['src'], 0) + x['tb']
        print(f"  {x['src']:20} {x['dir']:10} bytes={x['tb']:>13,}  "
              f"= {x['tb']/GiB:.6f} GiB = {x['tb']/GB:.6f} GB  "
              f"rows={x['rows']:>9,} tokens={x['tt']:>11,}  "
              f"B/row={x['tb']/x['rows']:6.1f} tok/B={x['tt']/x['tb']:.4f}")
    print(f"  合计 bytes={tot:>13,} = {tot/GiB:.6f} GiB = {tot/GB:.6f} GB")
    for s, v in by_src.items():
        print(f"    {s:20} {v:>13,} = {v/GiB:.6f} GiB  距1GiB {GiB - v:>12,} B ({(GiB-v)/1024**2:.2f} MiB)")

print()
print('=== 全量：合计 与 最大单源（按目录 meta.json 原值）===')
agg = {}
for x in dirs:
    a = agg.setdefault(x['iso'], {'tot': 0, 'src': {}})
    a['tot'] += x['tb']
    a['src'][x['src']] = a['src'].get(x['src'], 0) + x['tb']

print(f"{'lang':8} {'合计GiB':>9} {'最大单源GiB':>12} {'达标':>4}  最大单源")
for iso in sorted(agg):
    a = agg[iso]
    mx_src = max(a['src'], key=a['src'].get)
    mx = a['src'][mx_src]
    print(f"{iso:8} {a['tot']/GiB:9.3f} {mx/GiB:12.3f} {'是' if mx >= GiB else '否':>4}  {mx_src}")
