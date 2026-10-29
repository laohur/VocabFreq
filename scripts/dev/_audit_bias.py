#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_audit_bias.py — 彻查 README 累计覆盖率 >100%（bew 110.5%）的根因。

三层核查：
  A. 全量扫描：上传 110 语 band-sum 估计 vs meta 真实覆盖率，量化偏差
  B. 单语深挖（默认 bew）：从 F: 原始 top100k 复算两种 fu 合并口径
     - 现行 build：fu_w = Σ_{i∋w} fu_i·V_i / Σ_{i∋w} V_i（按"出现过该词的来源"逐词归一）
     - 全局分母：fu_w = Σ_{i∋w} fu_i·V_i / Σ_all V_i（缺失来源按 0 频计）
     并核对各来源 Σcounts vs 记录 tokens
  C. 全量复算：所有语种用两种口径重算 band-sum，评估修复影响面
"""
import gzip, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

import msgpack

SRC_BASE = Path(r"F:\data\WordFrequency\wordfreq")
SRC_META = Path(r"D:\code\河狸记词\data\WordFrequency\data\wordfreq\meta.json")
DST      = Path(r"D:\code\河狸记词\data\hf-upload\WordFrequency")
ONE_GIB  = 1024 ** 3
BCP47 = {
    "afr_Latn":"af","amh_Ethi":"am","arb_Arab":"ar","ars_Arab":"ar","ary_Arab":"ar",
    "arz_Arab":"ar","asm_Beng":"as","azj_Latn":"az","bel_Cyrl":"be","ben_Beng":"bn",
    "bew_Latn":"bew","bod_Tibt":"bo","bos_Latn":"bs","bul_Cyrl":"bg","cat_Latn":"ca",
    "ces_Latn":"cs","ckb_Arab":"ckb","cmn_Hani":"zh","cym_Latn":"cy","dan_Latn":"da",
    "deu_Latn":"de","div_Thaa":"dv","ell_Grek":"el","eng_Latn":"en","epo_Latn":"eo",
    "est_Latn":"et","eus_Latn":"eu","fao_Latn":"fo","fas_Arab":"fa","fil_Latn":"fil",
    "fin_Latn":"fi","fra_Latn":"fr","fry_Latn":"fy","gle_Latn":"ga","glg_Latn":"gl",
    "gmh_Latn":"gmh","guj_Gujr":"gu","heb_Hebr":"he","hif_Latn":"hif","hin_Deva":"hi",
    "hrv_Latn":"hr","hun_Latn":"hu","hye_Armn":"hy","ind_Latn":"id","isl_Latn":"is",
    "ita_Latn":"it","jav_Latn":"jv","jpn_Jpan":"ja","kan_Knda":"kn","kat_Geor":"ka",
    "kaz_Cyrl":"kk","khk_Cyrl":"mn","khm_Khmr":"km","kir_Cyrl":"ky","kmr_Latn":"ku",
    "kor_Hang":"ko","lao_Laoo":"lo","lat_Latn":"la","lav_Latn":"lv","lit_Latn":"lt",
    "ltz_Latn":"lb","lvs_Latn":"lv","mal_Mlym":"ml","mar_Deva":"mr","mkd_Cyrl":"mk",
    "mlt_Latn":"mt","mon_Cyrl":"mn","mri_Latn":"mi","msa_Latn":"ms","mya_Mymr":"my",
    "mya_Mmymr":"my","nep_Deva":"ne","nld_Latn":"nl","nno_Latn":"nn","nob_Latn":"nb",
    "npi_Deva":"ne","nrm_Latn":"nrm","ori_Orya":"or","ory_Orya":"or","pan_Guru":"pa",
    "pbt_Arab":"ps","plt_Latn":"mg","pol_Latn":"pl","por_Latn":"pt","pus_Arab":"ps",
    "ron_Latn":"ro","rus_Cyrl":"ru","sin_Sinh":"si","slk_Latn":"sk","slv_Latn":"sl",
    "sna_Latn":"sn","snd_Arab":"sd","som_Latn":"so","spa_Latn":"es","sqi_Latn":"sq",
    "srp_Cyrl":"sr","srp_Latn":"sr","swa_Latn":"sw","swe_Latn":"sv","swh_Latn":"sw",
    "tam_Taml":"ta","tat_Cyrl":"tt","tel_Telu":"te","tgk_Cyrl":"tg","tha_Thai":"th",
    "tgl_Latn":"fil","tur_Latn":"tr","uig_Arab":"ug","ukr_Cyrl":"uk","urd_Arab":"ur",
    "uzn_Cyrl":"uz","uzn_Latn":"uz","uzb_Latn":"uz","vie_Latn":"vi","xho_Latn":"xh",
    "ydd_Hebr":"yi","yid_Hebr":"yi","yor_Latn":"yo","zho_Hant":"zh-Hant","zsm_Latn":"ms",
    "zul_Latn":"zu","ultrafineweb_en_l3":"en","ultrafineweb_zh_l3":"zh","ekk_Latn":"et",
}
def norm(code): return BCP47.get(code, code)


def band_sum(path):
    with gzip.open(path, "rb") as f:
        bands = msgpack.unpackb(f.read(), raw=False)[1:]
    return sum(len(b) * 10 ** (-i / 100) for i, b in enumerate(bands) if b), sum(len(b) for b in bands)


def collect_candidates():
    cands = []
    wiki = SRC_BASE / "wikipedia"
    if wiki.is_dir():
        for d in sorted(wiki.iterdir()):
            tk, mj = d / "top100k.txt", d / "meta.json"
            if tk.exists() and mj.exists():
                m = json.loads(mj.read_text(encoding="utf-8"))
                cands.append((norm(d.name), tk, m.get("text_bytes", 0), m.get("total_tokens", 0), "wikipedia"))
    for src in ("ultrafineweb_l3", "fineweb2_hq_plus"):
        p = SRC_BASE / src
        if not p.is_dir():
            continue
        for d in sorted(p.iterdir()):
            tk, mj = d / "top100k.txt", d / "meta.json"
            if tk.exists() and mj.exists():
                m = json.loads(mj.read_text(encoding="utf-8"))
                cands.append((norm(d.name), tk, m.get("text_bytes", 0), m.get("total_tokens", 0), src))
    return cands


def load_counter(path):
    cc, n_lines = Counter(), 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            n_lines += 1
            parts = line.rstrip("\r\n").split("\t", 1)
            if len(parts) != 2:
                continue
            try:
                c = int(parts[0])
            except ValueError:
                continue
            cc[parts[1]] += c
    return cc, n_lines


def part_a():
    print("=" * 72)
    print("A. 上传 110 语：band-sum 估计 vs meta 真实覆盖率")
    meta = json.loads((DST / "meta.json").read_text(encoding="utf-8"))["languages"]
    rows = []
    for lang, m in meta.items():
        bs, kept = band_sum(DST / f"data/small_{lang}.msgpack.gz")
        assert kept == m["kept"], (lang, kept, m["kept"])
        rows.append((bs - m["coverage"], lang, bs, m["coverage"]))
    rows.sort(reverse=True)
    print(f"{'lang':8} {'band-sum':>9} {'real-cov':>9} {'bias(pp)':>9}")
    for d, lang, bs, cov in rows[:12]:
        print(f"{lang:8} {bs*100:8.1f}% {cov*100:8.1f}% {d*100:8.1f}")
    over = [(lang, bs) for d, lang, bs, cov in rows if bs > 1.0]
    print(f"\nband-sum > 100%: {over}")
    print(f"bias > 10pp: {[(l, round(d*100,1)) for d,l,_,_ in rows if d > 0.10]}")


def load_lang_groups(iso):
    """(iso, src) → [(counter, tb, tt, n_lines)]，并顺带核对 Σcounts vs tokens"""
    groups = defaultdict(list)
    for cand_iso, path, tb, tt, src in collect_candidates():
        if cand_iso != iso:
            continue
        cc, n_lines = load_counter(path)
        groups[src].append((cc, tb, tt, path.parent.name, n_lines))
    return groups


def probe_lang(iso):
    print("=" * 72)
    print(f"B. {iso} 深挖")
    groups = load_lang_groups(iso)
    meta = json.loads(SRC_META.read_text(encoding="utf-8"))["languages"][iso]
    print(f"build meta: kept={meta['kept']} coverage={meta['coverage']}")
    print(f"upload band-sum: {band_sum(DST / f'data/small_{iso}.msgpack.gz')[0]*100:.2f}%")

    v_all = 0
    src_info = []
    for src, entries in groups.items():
        tb = sum(e[1] for e in entries)
        tt = sum(e[2] for e in entries)
        sc = sum(sum(e[0].values()) for e in entries)
        nl = sum(e[4] for e in entries)
        v_all += tb
        src_info.append((src, tb, tt, sc, nl))
        flag = "  <-- Σcounts > tokens!" if sc > tt else ""
        print(f"  {src:18} dirs={len(entries)} bytes={tb/ONE_GIB:.3f}G tokens={tt:,} "
              f"Σcounts={sc:,} ({sc/tt:.3f}x tokens) lines={nl:,}{flag}")
        for e in entries:
            sc1 = sum(e[0].values())
            print(f"      - {e[3]:40} bytes={e[1]/ONE_GIB:.3f}G tokens={e[2]:,} "
                  f"Σcounts={sc1:,} ({sc1/e[2]:.3f}x)")

    # 现行口径 vs 全局分母口径
    w_cur, w_fix = {}, {}   # word -> [fu_sum, w_sum] / [fu_sum]
    tt_all = sum(tt for _, _, tt, _, _ in src_info)
    for src, entries in groups.items():
        cc = Counter()
        tb = sum(e[1] for e in entries)
        tt = sum(e[2] for e in entries)
        for e in entries:
            cc.update(e[0])
        inv = 1.0 / tt
        for w, c in cc.items():
            f = c * inv
            a = w_cur.get(w)
            if a is None:
                w_cur[w] = [f * tb, tb]
            else:
                a[0] += f * tb; a[1] += tb
            w_fix[w] = w_fix.get(w, 0.0) + f * tb
    s_cur = sum(a[0] / a[1] for a in w_cur.values())
    s_fix = sum(f / v_all for f in w_fix.values())
    # 现行口径下的门槛 kept（忽略 clean 规则，纯频率门槛 fu>1e-6 且 fu/wb>2e-7 近似 wb=2）
    k_cur = sum(1 for a in w_cur.values() if a[0] / a[1] > 1e-6)
    k_fix = sum(1 for f in w_fix.values() if f / v_all > 1e-6)
    print(f"\n  Σ_fu 现行(逐词归一) = {s_cur:.4f}   全局分母 = {s_fix:.4f}   (band-sum≈现行, real-cov≈全局)")
    print(f"  fu>1e-6 词数: 现行≈{k_cur:,}  全局分母≈{k_fix:,}")


def part_c():
    print("=" * 72)
    print("C. 全量复算（全局分母口径的 Σ_fu vs 现行 Σ_fu，纯频率口径，未过 clean 规则）")
    groups = defaultdict(lambda: defaultdict(list))
    for cand_iso, path, tb, tt, src in collect_candidates():
        groups[cand_iso][src].append((path, tb, tt))
    print(f"{'lang':10} {'n_src':>5} {'Σ_fu现':>8} {'Σ_fu全':>8} {'现行/全':>7}")
    worst = []
    for iso in sorted(groups):
        v_all = sum(tb for src in groups[iso].values() for _, tb, _ in src)
        if v_all <= 0:
            continue
        w_cur, w_fix = {}, {}
        for src, entries in groups[iso].items():
            tb = sum(e[1] for e in entries)
            tt = sum(e[2] for e in entries)
            cc = Counter()
            for p, _, _ in entries:
                c, _n = load_counter(p)
                cc.update(c)
            inv = 1.0 / tt
            for w, c in cc.items():
                f = c * inv
                a = w_cur.get(w)
                if a is None:
                    w_cur[w] = [f * tb, tb]
                else:
                    a[0] += f * tb; a[1] += tb
                w_fix[w] = w_fix.get(w, 0.0) + f * tb
        s_cur = sum(a[0] / a[1] for a in w_cur.values())
        s_fix = sum(f / v_all for f in w_fix.values())
        worst.append((s_cur - s_fix, iso, s_cur, s_fix))
    worst.sort(reverse=True)
    for d, iso, s_cur, s_fix in worst[:15]:
        print(f"{iso:10} {len(groups[iso]):>5} {s_cur:8.3f} {s_fix:8.3f} {s_cur/s_fix:7.2f}")


if __name__ == "__main__":
    part_a()
    probe_lang(sys.argv[1] if len(sys.argv) > 1 else "bew")
    if "--all" in sys.argv:
        part_c()
