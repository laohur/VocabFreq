#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fw2/ultra 全量：R<1G 语种列出 U/R，并抽查 2 个精确解码对账。"""
import json
from pathlib import Path

import pyarrow.parquet as pq

CORPUS_FW2 = Path(r"F:\data\corpus\FineWeb2-HQ-plus")
CORPUS_ULTRA = Path(r"F:\data\corpus\Ultra-FineWeb-L3")
WF = Path(r"F:\data\WordFrequency\wordfreq")
ONE_GIB = 1024 ** 3


def footer_text_bytes(d):
    tot = 0
    for p in sorted(d.rglob("*.parquet")):
        pf = pq.ParquetFile(p)
        md = pf.metadata
        for rg in range(md.num_row_groups):
            rgm = md.row_group(rg)
            for k in range(rgm.num_columns):
                if rgm.column(k).path_in_schema == "text":
                    tot += rgm.column(k).total_uncompressed_size
                elif rgm.column(k).path_in_schema == "content":
                    tot += rgm.column(k).total_uncompressed_size
    return tot


low = []
for parent, src in ((CORPUS_FW2, "fineweb2_hq_plus"),
                    (CORPUS_ULTRA, "ultrafineweb_l3")):
    for d in sorted(parent.iterdir()):
        if not d.is_dir():
            continue
        mp = WF / src / d.name / "meta.json"
        if not mp.exists():
            print(f"[no-meta] {src}/{d.name}")
            continue
        R = json.loads(mp.read_text(encoding="utf-8")).get("text_bytes")
        if R is None or R >= ONE_GIB:
            continue
        U = footer_text_bytes(d)
        low.append((src, d.name, U, R))
        print(f"{src:18} {d.name:22} U={U/ONE_GIB:.3f}G R={R/ONE_GIB:.3f}G "
              f"U/R={U/R:.4f}")
print(f"\nR<1G 语种数: {len(low)}")

for src, lang, U, R in low[:2]:
    tot = 0
    for p in sorted((CORPUS_FW2 / lang).rglob("*.parquet")):
        tb = pq.read_table(p, columns=["text"])
        tot += sum(len(doc.encode("utf-8", "replace")) + 1
                   for doc in tb.column("text").to_pylist() if doc)
    print(f"exact {lang}: {tot:,} vs meta {R:,} -> "
          f"{'OK' if tot == R else 'MISMATCH!'}")
