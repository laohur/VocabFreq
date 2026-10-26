#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys, msgpack, gzip as gz
from pathlib import Path
from collections import Counter, defaultdict

META = Path(r'D:\code\河狸记词\data\hf-upload\wordfreq\meta.json')
DATA = Path(r'D:\code\河狸记词\data\hf-upload\wordfreq\data')
FF   = Path(r'F:\data\WordFrequency\wordfreq')
ONE_GIB = 1024**3

meta = json.loads(META.read_text(encoding='utf-8'))
wf_kept = {iso: v['kept'] for iso, v in meta['languages'].items()}

sys.path.insert(0, str(Path(r'D:\code\河狸记词\data\WordFrequency\scripts')))
from build_wordfreq import (norm, load_counter, clean_one, LANG_SCRIPTS,
    DEFAULT_SCRIPTS, KEEP_DIACRITIC_SINGLE, SPACE_WORD_LANGS)

# 检查 top100k.txt 示例
def peek_top100k(path, n=15):
    with open(path, 'r', encoding='utf-8') as f:
        lines = []
        for i, line in enumerate(f):
            if i >= n: break
            parts = line.rstrip('\n').split('\t')
            lines.append(parts)
    return lines

# 试看 zh 和 ko 的 top100k.txt
for iso in ['zh', 'ko']:
    for src in ['wikipedia', 'ultrafineweb_l3']:
        d = FF / src / iso
        tk = d / 'top100k.txt'
        if tk.exists():
            print(f'\n=== {src}/{iso}/top100k.txt (first 15) ===')
            for row in peek_top100k(tk):
                print(f'  {row}')
            # 总行数
            with open(tk, 'r', encoding='utf-8') as f:
                lines = sum(1 for _ in f)
            print(f'  total lines: {lines}')

# 验证 wf msgpack 词数 vs meta kept
print('\n=== wordfreq msgpack 内词数 vs meta kept ===')
for iso in ['zh', 'ko']:
    p = DATA / f'small_{iso}.msgpack.gz'
    if p.exists():
        with gz.open(p, 'rb') as f:
            raw = msgpack.unpackb(f.read(), raw=False)
        n_bands = len(raw) - 1
        total_w = sum(len(b) for b in raw[1:])
        print(f'{iso}: meta_kept={wf_kept.get(iso, "?")}, msgpack_bands={n_bands}, sum_words={total_w}')

# 计算覆盖率时看 zh 的具体命中
print('\n=== zh 覆盖率计算细节 ===')
results = {}
for iso in ['zh', 'ko', 'vi', 'ar']:
    d_wiki = FF / 'wikipedia' / iso
    tk = d_wiki / 'top100k.txt'
    mj = d_wiki / 'meta.json'
    if not (tk.exists() and mj.exists()): continue
    m = json.loads(mj.read_text(encoding='utf-8'))

    src_types = []
    allowed = LANG_SCRIPTS.get(iso, DEFAULT_SCRIPTS)
    keep_diac = iso in KEEP_DIACRITIC_SINGLE
    merged = Counter()
    tb = m.get('text_bytes', 0)
    tt = m.get('total_tokens', 0)
    for w, c in load_counter(tk).items():
        wc, reason = clean_one(w, iso, allowed, keep_diac)
        if reason is None: merged[wc] += c
    src_types.append((merged, tb, tt))

    fw = {}
    for cc, tb_sum, tt_sum in src_types:
        if tt_sum <= 0 or tb_sum <= 0: continue
        inv = 1.0 / tt_sum
        for w, c in cc.items():
            fi = c * inv
            if w not in fw: fw[w] = [0.0, 0.0]
            fw[w][0] += fi * tb_sum
            fw[w][1] += tb_sum

    add_sp = 1 if iso in SPACE_WORD_LANGS else 0
    kept = set()
    for w, (fs, ws) in fw.items():
        if ws <= 0: continue
        fu = fs / ws
        if fu <= 1e-6: continue
        if fu / (len(w.encode('utf-8')) + add_sp) <= 2e-7: continue
        kept.add(w)

    wf_set = set()
    p = DATA / f'small_{iso}.msgpack.gz'
    if p.exists():
        with gz.open(p, 'rb') as f:
            raw = msgpack.unpackb(f.read(), raw=False)
        for band in raw[1:]:
            wf_set.update(band)

    wf_cnt = sum(merged.get(w, 0) for w in wf_set)
    cnt_2 = sum(merged.get(w, 0) for w in kept)
    print(f'{iso}: total_tokens={tt:,}, wf_hits={wf_cnt:,} ({wf_cnt/tt*100:.1f}%), 2e-7_hits={cnt_2:,} ({cnt_2/tt*100:.1f}%)')
    print(f'  top100k 中 wf 命中数: {len(wf_set & set(merged.keys())):,} / {len(wf_set):,}')
    print(f'  top100k 中 2e-7 命中数: {len(kept & set(merged.keys())):,} / {len(kept):,}')
