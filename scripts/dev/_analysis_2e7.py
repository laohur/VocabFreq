#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析 thres_cache.json：
1) 2e-7 vs wf-cov 的胜负统计（覆盖与词表规模）
2) 各阈值的边际收益
3) 合计≈0G 却有词频数字的语种明细
"""
import json
from pathlib import Path

C = json.loads(Path(r"d:\code\河狸记词\data\WordFrequency\thres_cache.json")
               .read_text(encoding="utf-8"))
rows = C["rows"]
L = ["1e-7", "2e-7", "5e-7", "1e-6"]

# ── 1) 2e-7 vs wf ────────────────────────────────────────────
both = [(iso, r) for iso, r in rows.items()
        if r.get("wf_cov") is not None and r.get("2e-7")]
win = lose = tie = 0
cov_gain = []
n_gain = []
for iso, r in both:
    wf_c, my_c = r["wf_cov"], r["2e-7"][1]
    d = my_c - wf_c
    cov_gain.append(d)
    if r.get("wf_kept"):
        n_gain.append(r["2e-7"][0] - r["wf_kept"])
    if d > 1e-9: win += 1
    elif d < -1e-9: lose += 1
    else: tie += 1

print(f"== 2e-7 vs wf (n={len(both)}) ==")
print(f"覆盖: 2e-7 胜 {win} / 负 {lose} / 平 {tie}")
if cov_gain:
    import statistics as st
    print(f"覆盖差均值 {st.mean(cov_gain)*100:+.2f}pp  中位 {st.median(cov_gain)*100:+.2f}pp  "
          f"最大 {max(cov_gain)*100:+.1f}pp  最小 {min(cov_gain)*100:+.1f}pp")
if n_gain:
    import statistics as st
    print(f"词表差(2e-7 n - wf_kept) 均值 {st.mean(n_gain):+.0f}  中位 {st.median(n_gain):+.0f}")
big_loss = sorted(((r["2e-7"][1]-r["wf_cov"])*100, iso, r.get("wf_kept"), r["2e-7"][0],
                   r.get("max_src", 0))
                  for iso, r in both)[:8]
print("2e-7 落后最多的语种:")
for d, iso, wk, mn, ms in big_loss:
    print(f"  {iso:8} wf={wk} 2e-7={mn} 覆盖差 {d:+.1f}pp 单源G={ms:.2f}")

# ── 2) 阈值边际 ──────────────────────────────────────────────
print("\n== 各阈值平均(有 corpus 的语种) ==")
for lab in L:
    cs = [r[lab][1] for r in rows.values() if r.get(lab)]
    ns = [r[lab][0] for r in rows.values() if r.get(lab)]
    import statistics as st
    print(f"  {lab}: n_lang={len(cs)} 平均覆盖 {st.mean(cs)*100:.1f}%  平均词表 {st.mean(ns):,.0f}")

# 69 达标语种上的对比（产品真正用的集合）
elig = {iso: r for iso, r in rows.items() if r.get("ok") and r.get("2e-7")}
print(f"\n== 仅 69 达标语种 (n={len(elig)}) ==")
import statistics as st
for lab in ("wf",) + tuple(L):
    if lab == "wf":
        cs = [r["wf_cov"] for r in elig.values() if r.get("wf_cov") is not None]
        ns = [r["wf_kept"] for r in elig.values() if r.get("wf_kept")]
        tag = "wf  "
    else:
        cs = [r[lab][1] for r in elig.values() if r.get(lab)]
        ns = [r[lab][0] for r in elig.values() if r.get(lab)]
        tag = lab
    if cs:
        print(f"  {tag}: n={len(cs)} 平均覆盖 {st.mean(cs)*100:.1f}%  平均词表 {st.mean(ns):,.0f}")

# ── 3) ≈0G 却有数字的语种 ────────────────────────────────────
tiny = [(iso, r) for iso, r in rows.items()
        if r.get("gib", 0) < 0.005 and any(r.get(l) for l in L)]
print(f"\n== 合计<0.005G 却有阈值数字的语种 (n={len(tiny)}) ==")
for iso, r in sorted(tiny, key=lambda x: x[0]):
    n1 = r["1e-7"][0] if r.get("1e-7") else None
    print(f"  {iso:10} gib={r['gib']:.4f} max_src={r.get('max_src',0):.4f} "
          f"tokens={r.get('tokens','?')} 1e-7n={n1}")
