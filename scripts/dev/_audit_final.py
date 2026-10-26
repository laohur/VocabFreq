#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收尾验证：
1. 列出 fw2/ultra 中 R<1G 的语种及其 footer U（应为 R≈U）
2. 检查 fw2/ultra 语种目录是否存在 samples 类子目录
3. 抽查 2 个 fw2 R<1G 语种做精确解码对账
"""
import json
from pathlib import Path

import pyarrow.parquet as pq

CORPUS_FW2 = Path(r"F:\data\corpus\FineWeb2-HQ-plus")
CORPUS_ULTRA = Path(r"F:\data\corpus\Ultra-FineWeb-L3")
WF = Path(r"F:\data\WordFrequency\wordfreq")
ONE_GIB = 1024 ** 3

rows = json.loads((Path(__file__).parent / "_audit_suspects.json")
                  .read_text(encoding="utf-8"))
allrows = rows["suspects"] + rows["missing"] + rows["mismatch"]

# 1) fw2/ultra 中 R<1G 的
print("== fw2/ultra R<1G 语种 ==")
low = [r for r in allrows if r["src"] in ("fineweb2_hq_plus", "ultrafineweb_l3")
       and r["R"] is not None and r["R"] < ONE_GIB]
for r in sorted(low, key=lambda x: -x["U"]):
    print(f"  {r['src']:18} {r['lang']:22} U={r['U_gib']:.3f} R={r['R_gib']:.3f} "
          f"n_pq={r['n_pq']} U/R={r['U']/r['R']:.4f}")

# 2) 子目录检查
print("\n== 含子目录的 fw2/ultra 语种目录 ==")
n_nested = 0
for parent in (CORPUS_FW2, CORPUS_ULTRA):
    for d in sorted(parent.iterdir()):
        if not d.is_dir():
            continue
        subs = [s.name for s in d.iterdir() if s.is_dir()]
        if subs:
            n_nested += 1
            print(f"  {d.name}: {subs}")
print(f"  (共 {n_nested} 个)")

# 3) 抽查精确解码
def exact(lang):
    tot = 0
    for p in sorted((CORPUS_FW2 / lang).rglob("*.parquet")):
        tb = pq.read_table(p, columns=["text"])
        tot += sum(len(doc.encode("utf-8", "replace")) + 1
                   for doc in tb.column("text").to_pylist() if doc)
    return tot

for lang in [r["lang"] for r in low[:2]]:
    tot = exact(lang)
    R = json.loads((WF / "fineweb2_hq_plus" / lang / "meta.json")
                   .read_text(encoding="utf-8"))["text_bytes"]
    ok = "OK" if tot == R else "MISMATCH!"
    print(f"\nexact {lang}: {tot:,} vs meta {R:,} -> {ok}")
