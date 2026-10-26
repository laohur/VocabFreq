import gzip, json
from pathlib import Path
import msgpack

WF = Path(r'D:\code\河狸记词\data\hf-upload\WordFrequency')
meta = json.loads((WF / 'meta.json').read_text(encoding='utf-8'))['languages']

print('lang  meta.kept  prev.kept  actual_vocab  consistent')
bad = []
for iso in sorted(meta):
    f = WF / 'data' / f'small_{iso}.msgpack.gz'
    n = 0
    if f.exists():
        raw = msgpack.unpackb(gzip.decompress(f.read_bytes()), raw=False)
        n = sum(len(b) for b in raw[1:])
    kept = meta[iso].get('kept')
    prev = meta[iso].get('_previous_wf_meta', {}).get('kept')
    ok = (n == kept)
    if not ok:
        bad.append((iso, kept, prev, n))
print(f'不一致语种数: {len(bad)} / {len(meta)}')
for iso, kept, prev, n in bad:
    print(f'  {iso:6} meta.kept={kept:>7,} prev={str(prev):>8} vocab={n:>7,} '
          f'{"=prev" if prev == n else ""}')
