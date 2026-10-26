#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比不同 fu/byte 阈值下各语种的保留词数与覆盖率。

v2 相对 v1：
  1. 增加 wf-cov：用 hf-upload 里 wordfreq 自己的词表（data/small_*.msgpack.gz）
     在本机同一批语料上按同一公式重算覆盖率，与各阈值列严格同口径。
  2. 出行规则改为「任一方有值就列出」：
        - wf 有词表（meta.json / data/*.msgpack.gz）
        - 本机有 top100k 语料（不论是否达到 1 GiB）
     不足 1 GiB 的语种也照算，只是标注 达标=否。
  3. 每个 (iso, src) 的 top100k.txt 只加载 + clean 一次，四档阈值共享。
  4. 直接由脚本写出 .md / .csv，显式 CRLF，避免管道重定向造成编码/换行损坏。
"""
import csv, gzip, json, sys, time
from pathlib import Path
from collections import Counter, defaultdict

import msgpack

FF      = Path(r"F:\data\WordFrequency\wordfreq")
WF_DIR  = Path(r"D:\code\河狸记词\data\hf-upload\WordFrequency")
OUT_MD  = Path(r"D:\code\河狸记词\data\WordFrequency\thres_table.md")
OUT_CSV = Path(r"D:\code\河狸记词\data\WordFrequency\thres_table.csv")
ONE_GIB = 1024 ** 3
SRC_ORDER = ("wikipedia", "ultrafineweb_l3", "fineweb2_hq_plus")

sys.path.insert(0, r"D:\code\河狸记词\data\WordFrequency\scripts")
from build_wordfreq import (
    norm, load_counter, clean_one, LANG_SCRIPTS, DEFAULT_SCRIPTS,
    KEEP_DIACRITIC_SINGLE, SPACE_WORD_LANGS,
)


# ── 语料发现 ────────────────────────────────────────────────
def collect_groups():
    """(iso, src) → [(path, text_bytes, total_tokens)]"""
    groups = defaultdict(list)
    for sn in SRC_ORDER:
        p = FF / sn
        if not p.is_dir():
            continue
        for d in sorted(p.iterdir()):
            if not d.is_dir():
                continue
            tk, mj = d / "top100k.txt", d / "meta.json"
            if not (tk.exists() and mj.exists()):
                continue
            m = json.loads(mj.read_text(encoding="utf-8"))
            groups[(norm(d.name), sn)].append(
                (tk, m.get("text_bytes", 0), m.get("total_tokens", 0)))
    return groups


def load_lang(iso, groups, allowed, keep_diac):
    """某语种所有来源各加载/清洗一次 → [(merged_counter, tb_sum, tt_sum)]"""
    src_types = []
    for sn in SRC_ORDER:
        ents = groups.get((iso, sn), [])
        if not ents:
            continue
        merged = Counter()
        tb_sum = tt_sum = 0
        for path, tb, tt in ents:
            for w, c in load_counter(path).items():
                wc, reason = clean_one(w, iso, allowed, keep_diac)
                if reason is None:
                    merged[wc] += c
            tb_sum += tb
            tt_sum += tt
        if merged:
            src_types.append((merged, tb_sum, tt_sum))
    return src_types


def merge_fu(src_types):
    """体积加权 fu：{word: [fu_sum, weight_sum]}"""
    fw = {}
    for cc, tb_sum, tt_sum in src_types:
        if tt_sum <= 0 or tb_sum <= 0:
            continue
        inv = 1.0 / tt_sum
        for w, c in cc.items():
            slot = fw.get(w)
            if slot is None:
                slot = fw[w] = [0.0, 0.0]
            slot[0] += (c * inv) * tb_sum
            slot[1] += tb_sum
    return fw


def coverage_of(vocab, src_types):
    """体积加权覆盖率：同一批语料上，vocab 命中的 token 占比（按来源体积加权）"""
    cov_wt_sum = 0.0
    tb_sum_all = 0
    for cc, tb_sum, tt_sum in src_types:
        if tt_sum <= 0 or tb_sum <= 0:
            continue
        hits = 0
        for w in vocab:
            hits += cc.get(w, 0)
        cov_wt_sum += (hits / tt_sum) * tb_sum
        tb_sum_all += tb_sum
    return cov_wt_sum / tb_sum_all if tb_sum_all > 0 else 0.0


def select(fw, thr, add_sp):
    kept = set()
    for w, (fs, ws) in fw.items():
        if ws <= 0:
            continue
        fu = fs / ws
        if fu <= 1e-6:
            continue
        if fu / (len(w.encode("utf-8")) + add_sp) <= thr:
            continue
        kept.add(w)
    return kept


# ── wf 词表（msgpack bands） ────────────────────────────────
def load_wf_vocab(iso):
    f = WF_DIR / "data" / f"small_{iso}.msgpack.gz"
    if not f.exists():
        return None
    raw = msgpack.unpackb(gzip.decompress(f.read_bytes()), raw=False)
    vocab = set()
    for band in raw[1:]:
        vocab.update(band)
    return vocab


# ── 主流程 ──────────────────────────────────────────────────
THRESHOLDS = [1e-7, 2e-7, 5e-7, 1e-6]
LABELS     = ["1e-7", "2e-7", "5e-7", "1e-6"]

t_all = time.time()
groups = collect_groups()
print(f"corpus langs: {len({iso for iso, _ in groups})}", file=sys.stderr)

WF_META = json.loads((WF_DIR / "meta.json").read_text(encoding="utf-8"))["languages"]
wf_kept = {iso: v["kept"] for iso, v in WF_META.items() if "kept" in v}
wf_meta_cov = {iso: v["coverage"] for iso, v in WF_META.items() if "coverage" in v}

# 任一方有值就列出
all_iso = sorted({iso for iso, _ in groups} | set(wf_kept), key=str.lower)

rows = {}
wf_cov_check = []
for i, iso in enumerate(all_iso, 1):
    t0 = time.time()
    allowed = LANG_SCRIPTS.get(iso, DEFAULT_SCRIPTS)
    keep_diac = iso in KEEP_DIACRITIC_SINGLE
    src_types = load_lang(iso, groups, allowed, keep_diac)

    rec = {"iso": iso, "gib": 0.0, "max_src": 0.0, "ok": False,
           "ok_strict": False, "wf_kept": wf_kept.get(iso), "wf_cov": None}
    tb_all = sum(tb for _, tb, _ in src_types)
    rec["gib"] = tb_all / ONE_GIB
    # 来源内先合并同语种的多目录，再取最大来源
    by_src = {}
    for sn in SRC_ORDER:
        tb_src = sum(tb for _, tb, _ in groups.get((iso, sn), []))
        if tb_src:
            by_src[sn] = tb_src
    rec["max_src"] = max(by_src.values(), default=0) / ONE_GIB
    rec["gib"] = sum(by_src.values()) / ONE_GIB  # 合计仅供参照，不做判定
    # 产品规则：单一来源 >= 1 GiB 才算达标（不把不同来源体积相加）
    rec["ok"] = rec["ok_strict"] = rec["max_src"] >= 1.0
    rec["sum_gib"] = rec["gib"]

    if src_types:
        fw = merge_fu(src_types)
        add_sp = 1 if iso in SPACE_WORD_LANGS else 0
        vocab = load_wf_vocab(iso)
        if vocab is not None:
            rec["wf_cov"] = coverage_of(vocab, src_types)
            if iso in wf_meta_cov:
                wf_cov_check.append((iso, rec["wf_cov"], wf_meta_cov[iso]))
        for T, L in zip(THRESHOLDS, LABELS):
            kept = select(fw, T, add_sp)
            rec[L] = (len(kept), coverage_of(kept, src_types))
    rows[iso] = rec
    print(f"[{i}/{len(all_iso)}] {iso}: giB={rec['gib']:.2f} "
          f"{time.time()-t0:.1f}s (total {time.time()-t_all:.0f}s)", file=sys.stderr)


# ── 一致性校验 ──────────────────────────────────────────────
print("\n=== 校验 ===", file=sys.stderr)
bad = 0
for iso, rec in rows.items():
    if not rec["ok"] or "1e-7" not in rec or iso not in wf_kept:
        continue
    if rec["1e-7"][0] != wf_kept[iso]:
        bad += 1
        print(f"[warn] {iso}: 1e-7={rec['1e-7'][0]} meta.kept={wf_kept[iso]} "
              f"prev={WF_META[iso].get('_previous_wf_meta', {}).get('kept')}", file=sys.stderr)
print(f"1e-7 与 meta.kept 不一致语种数: {bad}", file=sys.stderr)

# 语种代码错配审计：目录原始代码本身是已知语种，却被 norm() 改写并并入别的 iso
suspect = []
for (iso, sn), ents in groups.items():
    for path, tb, tt in ents:
        base = path.parent.name.split("_")[0]
        if base in wf_kept and norm(path.parent.name) != base:
            suspect.append((sn, path.parent.name, norm(path.parent.name), base, tb / ONE_GIB))
if suspect:
    print(f"\n[audit] {len(suspect)} 个目录的语种代码被改写到别的 iso，且原代码本身是已知语种:", file=sys.stderr)
    for sn, d, to, base, gib in sorted(suspect, key=lambda x: -x[4]):
        print(f"  {sn:20} {d:18} → {to:6} (本应是 {base}, {gib:.2f} GiB)", file=sys.stderr)
if wf_cov_check:
    devs = [(abs(a - b) * 100, iso, a, b) for iso, a, b in wf_cov_check]
    devs.sort(reverse=True)
    print(f"wf-cov 与 meta.coverage 对比 (n={len(devs)}): 最大偏差 "
          f"{devs[0][0]:.2f}pp ({devs[0][1]})", file=sys.stderr)


# ── 输出 ────────────────────────────────────────────────────
def fmt_cell(v):
    return "—" if v is None else f"{v[0]:,} ({v[1]*100:.1f}%)"


def pct(v):
    return "—" if v is None else f"{v*100:.1f}%"


hdr = ["lang", "最大单源GiB", "合计GiB", "达标", "wf-kept", "wf-cov"] + [f"{L} n (cov)" for L in LABELS]
md = ["| " + " | ".join(hdr) + " |",
      "|:--|--:|--:|:-:|--:|--:|" + "--:|" * len(LABELS)]
csv_rows = []
for iso in all_iso:
    r = rows[iso]
    md.append("| " + " | ".join([
        iso,
        f"{r['max_src']:.2f}",
        f"{r['gib']:.2f}",
        "是" if r["ok"] else "否",
        "—" if r["wf_kept"] is None else f"{r['wf_kept']:,}",
        pct(r["wf_cov"]),
    ] + [fmt_cell(r.get(L)) for L in LABELS]) + " |")
    csv_rows.append([iso, f"{r['max_src']:.2f}", f"{r['gib']:.2f}",
                     "1" if r["ok"] else "0",
                     "" if r["wf_kept"] is None else r["wf_kept"],
                     "" if r["wf_cov"] is None else round(r["wf_cov"], 6)]
                    + [x for L in LABELS
                       for x in (("" if r.get(L) is None else r[L][0]),
                                 "" if r.get(L) is None else round(r[L][1], 6))])

OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\r\n")
with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh, lineterminator="\r\n")
    w.writerow(["lang", "giB", "eligible_1gib", "wf_kept", "wf_cov"]
               + [x for L in LABELS for x in (f"{L}_n", f"{L}_cov")])
    w.writerows(csv_rows)

n_ok = sum(1 for r in rows.values() if r["ok"] and "1e-7" in r)
near = sorted(((1.0 - r["max_src"], iso) for iso, r in rows.items()
               if not r["ok"] and r["max_src"] >= 0.9), key=lambda x: x[0])
print(f"\n{len(all_iso)} langs total, 单源>=1GiB 达标={n_ok}  {time.time()-t_all:.1f}s", file=sys.stderr)
if near:
    print("差一点(最大单源 0.90~1.00 GiB):", file=sys.stderr)
    for d, iso in near:
        print(f"  {iso:6} 最大单源={1.0-d:.3f} GiB  差 {d*1024:.0f} MiB", file=sys.stderr)
print(f"{OUT_MD}\n{OUT_CSV}", file=sys.stderr)

# 缓存，便于改动规则后免重算
CACHE = OUT_MD.with_name("thres_cache.json")
CACHE.write_text(json.dumps({
    "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "thresholds": THRESHOLDS,
    "rows": {iso: {k: v for k, v in r.items() if k != "iso"} for iso, r in rows.items()},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"cache: {CACHE}", file=sys.stderr)
