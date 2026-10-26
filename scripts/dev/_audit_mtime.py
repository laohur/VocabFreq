#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 wiki 源 R<1G 且 R<0.95U 的语种，比对 parquet 与 meta 的 mtime。"""
import json
from pathlib import Path

J = Path(__file__).parent / "_audit_suspects.json"
WIKI = Path(r"F:\data\corpus\wikipedia-monthly\20261001")

j = json.loads(J.read_text(encoding="utf-8"))
mm = [m for m in j["mismatch"]
      if m["src"] == "wikipedia" and m["R"] and m["R"] < 1024 ** 3]
print("wiki R<1G mismatch:", len(mm))
later = []
for m in sorted(mm, key=lambda x: -(x["U"] - x["R"])):
    d = WIKI / m["lang"]
    pqs = sorted(d.rglob("*.parquet"))
    newest = max(p.stat().st_mtime for p in pqs) if pqs else 0
    gap_h = (newest - m["meta_mtime"]) / 3600 if m["meta_mtime"] else None
    flag = "PARQUET晚于meta" if gap_h and gap_h > 0.02 else ""
    if flag:
        later.append(m["lang"])
    print(f"{m['lang']:8} U={m['U_gib']:.3f} R={m['R_gib']:.3f} "
          f"n_pq={m['n_pq']} newest_pq-meta_h={gap_h:+.2f} {flag}")
print("parquet晚于meta的语种数:", len(later), later)
