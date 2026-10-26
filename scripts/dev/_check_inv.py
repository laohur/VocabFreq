import json
from pathlib import Path

base = Path(r'D:\code\河狸记词\data\WordFrequency')

def load(p):
    t = (base / p).read_text(encoding='utf-8')
    return json.loads(t)

for name in ('inventory.json', 'download_plan.json'):
    try:
        data = load(name)
    except Exception as e:
        print(name, 'ERR', e)
        continue
    print(f'=== {name}  type={type(data).__name__} len={len(data)}')
    recs = data if isinstance(data, list) else data.get('items', data)
    for r in recs:
        if not isinstance(r, dict):
            continue
        lang = r.get('lang') or r.get('language') or r.get('iso')
        if lang in ('is', 'isl', 'la', 'lat', 'fil', 'tl', 'gl', 'eu', 'arz'):
            print('  ', json.dumps(r, ensure_ascii=False))
    print()
