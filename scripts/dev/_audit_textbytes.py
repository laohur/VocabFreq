#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 text_bytes 低记错误。

背景：tokenize_one.py 分词时若 parquet 尚未下载全，meta.json 的 text_bytes 会永久
偏低（如 isl_Latn 记 0.90 GiB，实际列数据 1.29 GiB）。本脚本：
  1. footer 快扫：只读 parquet 元数据，取 text 列 total_uncompressed_size 之和 U。
  2. 对 U >= 0.995 GiB 且 meta 记录 < 1 GiB 的语种（或缺 meta 的语种）标记 SUSPECT。
  3. 对 R 与 U 严重不符（R < 0.95*U）的语种也标记（影响 fu 体积权重）。
输出 suspects 列表供精确复核 / 重新分词。
"""
import json, sys, time
from pathlib import Path

import pyarrow.parquet as pq

CORPUS = Path(r"F:\data\corpus")
WF     = Path(r"F:\data\WordFrequency\wordfreq")
ONE_GIB = 1024 ** 3

SOURCES = [
    # (corpus 父目录, wordfreq 输出源名)
    (CORPUS / "FineWeb2-HQ-plus",            "fineweb2_hq_plus"),
    (CORPUS / "Ultra-FineWeb-L3",            "ultrafineweb_l3"),
    (CORPUS / "wikipedia-monthly" / "20261001", "wikipedia"),
]


def text_col_index(pf):
    """从 schema 找文本列名：优先 text，其次 content。"""
    names = pf.schema_arrow.names
    for cand in ("text", "content"):
        if cand in names:
            return cand
    return None


def footer_scan(d):
    """返回 (uncomp_text_bytes, n_parquet, col_name)。失败返回 None。"""
    files = sorted(d.rglob("*.parquet"))
    if not files:
        return None
    total = 0
    col = None
    for p in files:
        try:
            pf = pq.ParquetFile(p)
        except Exception as e:
            print(f"  [footer-fail] {p.name}: {e}", file=sys.stderr)
            continue
        c = text_col_index(pf)
        if c is None:
            print(f"  [no-text-col] {d.name}: {pf.schema_arrow.names}", file=sys.stderr)
            return None
        col = c
        md = pf.metadata
        ci = pf.schema_arrow.get_field_index(c)
        # parquet 物理列序可能与 arrow schema 一致，按名字查每列
        for rg in range(md.num_row_groups):
            rgm = md.row_group(rg)
            for k in range(rgm.num_columns):
                if rgm.column(k).path_in_schema == c:
                    total += rgm.column(k).total_uncompressed_size
    return total, len(files), col


def main():
    rows = []
    for parent, out_src in SOURCES:
        if not parent.is_dir():
            print(f"[skip] {parent} 不存在", file=sys.stderr)
            continue
        for d in sorted(parent.iterdir()):
            if not d.is_dir():
                continue
            sc = footer_scan(d)
            if sc is None:
                continue
            U, n_pq, col = sc
            meta_p = WF / out_src / d.name / "meta.json"
            R = None
            meta_mtime = None
            if meta_p.exists():
                try:
                    m = json.loads(meta_p.read_text(encoding="utf-8"))
                    R = m.get("text_bytes")
                    meta_mtime = meta_p.stat().st_mtime
                except Exception as e:
                    print(f"  [meta-fail] {meta_p}: {e}", file=sys.stderr)
            rows.append({
                "src": out_src, "lang": d.name, "col": col,
                "U_gib": round(U / ONE_GIB, 3), "U": U, "n_pq": n_pq,
                "R": R, "R_gib": (round(R / ONE_GIB, 3) if R is not None else None),
                "has_meta": meta_p.exists(),
                "meta_mtime": meta_mtime,
            })

    # 分类
    suspects, missing, mismatch = [], [], []
    for r in rows:
        if not r["has_meta"]:
            if r["U"] >= 0.995 * ONE_GIB:
                missing.append(r)
            continue
        R = r["R"]
        if R is None:
            continue
        if R < ONE_GIB and r["U"] >= 0.995 * ONE_GIB:
            suspects.append(r)          # 记录 <1G 但实际列数据 >=1G → 必然低记
        elif R < 0.95 * r["U"] and r["U"] >= 0.10 * ONE_GIB:
            mismatch.append(r)          # 即使都 <1G，体积权重也失真
        # 其余：R==cap 或 U<1G 且 R≈U → 正常

    def dump(title, lst):
        print(f"\n=== {title} ({len(lst)}) ===")
        for r in sorted(lst, key=lambda x: -x["U"]):
            rr = f"{r['R_gib']:.3f}" if r["R_gib"] is not None else "None"
            print(f"  {r['src']:20} {r['lang']:22} U={r['U_gib']:.3f}G R={rr}G "
                  f"n_pq={r['n_pq']}")

    dump("SUSPECT 记录<1G但实际>=1G", suspects)
    dump("MISSING 未分词但实际>=1G", missing)
    dump("MISMATCH R<0.95U", mismatch)

    n_cap = sum(1 for r in rows if r["R"] is not None and r["R"] >= ONE_GIB)
    print(f"\n统计: 扫描 {len(rows)} 语种目录, 已封顶(R>=1G) {n_cap}, "
          f"suspect {len(suspects)}, missing {len(missing)}, mismatch {len(mismatch)}",
          file=sys.stderr)

    out = Path(__file__).parent / "_audit_suspects.json"
    out.write_text(json.dumps({
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "suspects": suspects, "missing": missing, "mismatch": mismatch,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
