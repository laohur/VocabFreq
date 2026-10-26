import json, sys
from pathlib import Path

sys.path.insert(0, r'D:\code\河狸记词\data\WordFrequency\scripts')
from build_wordfreq import norm

FF = Path(r'F:\data\WordFrequency\wordfreq')
GIB = 1024 ** 3
SRCS = ('wikipedia', 'ultrafineweb_l3', 'fineweb2_hq_plus')
meta = json.loads(Path(r'D:\code\河狸记词\data\hf-upload\WordFrequency\meta.json').read_text(encoding='utf-8'))['languages']

langs = {}
incomplete = []
for sn in SRCS:
    for d in sorted((FF / sn).iterdir()):
        if not d.is_dir():
            continue
        tk, mj = d / 'top100k.txt', d / 'meta.json'
        if not (tk.exists() and mj.exists()):
            incomplete.append((sn, d.name, tk.exists(), mj.exists()))
            continue
        m = json.loads(mj.read_text(encoding='utf-8'))
        langs.setdefault(norm(d.name), []).append(
            dict(src=sn, dir=d.name, tb=m.get('text_bytes', 0)))

print(f'=== 语料不完整（缺 top100k.txt 或 meta.json）: {len(incomplete)} ===')
for x in incomplete[:20]:
    print('  ', x)

print()
print('=== 同一语言被拆成多个 iso（体积被拆分/重复收录）===')
same = [('no', 'nb'), ('fil', 'tl'), ('arz', 'ar'), ('sh', 'hr'), ('sh', 'bs'), ('zh-Hant', 'zh'), ('ku', 'ckb')]
for a, b in same:
    ia, ib = a in meta, b in meta
    ta = sum(e['tb'] for e in langs.get(a, []))
    tb_ = sum(e['tb'] for e in langs.get(b, []))
    print(f'  {a:8} meta={ia!s:5} 语料={ta/GIB:5.2f} GiB | {b:8} meta={ib!s:5} 语料={tb_/GIB:5.2f} GiB')

print()
print('=== 语料被并入别的 iso 而造成原语种丢语料 ===')
for iso in ('tl', 'ar', 'fil', 'arz'):
    ents = langs.get(iso, [])
    print(f'  {iso:6} in_meta={iso in meta!s:5} 目录={[e["dir"] for e in ents]} '
          f'合计={sum(e["tb"] for e in ents)/GIB:.2f} GiB')

print()
print('=== 判定规则对比：单一来源>=1GiB vs 合并体积>=1GiB ===')
strict, merged = set(), set()
for iso, ents in langs.items():
    tot = sum(e['tb'] for e in ents)
    by_src = {}
    for e in ents:
        by_src[e['src']] = by_src.get(e['src'], 0) + e['tb']
    if tot >= GIB:
        merged.add(iso)
    if max(by_src.values()) >= GIB:
        strict.add(iso)
print(f'  单一来源判定: {len(strict)} 个')
print(f'  合并体积判定: {len(merged)} 个')
print(f'  仅合并判定会新增: {sorted(merged - strict)}')
print(f'  差异明细:')
for iso in sorted(merged - strict):
    ents = langs[iso]
    print(f'    {iso:6} total={sum(e["tb"] for e in ents)/GIB:.2f} GiB  '
          + ', '.join(f'{e["src"][:4]}={e["tb"]/GIB:.2f}' for e in ents))
print(f'  meta 里有但两套规则都没语料: {sorted(set(meta) - merged)}')
