#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_sample_scripts.py — 对 LANG_SCRIPTS 缺失语种，从 F: top100k 实测主流书写系统"""
import json
from pathlib import Path

SRC_BASE = Path(r"F:\data\WordFrequency\wordfreq")
TARGETS = ["udm", "azb", "av", "mni", "mai", "ks", "cv", "pnb", "os", "sa",
           "ab", "sd", "arz", "sah", "ug", "ba", "tt", "skr", "ce"]

RANGES = [
    ("Cyrl", 0x0400, 0x04FF), ("Arab", 0x0600, 0x06FF), ("Deva", 0x0900, 0x097F),
    ("Beng", 0x0980, 0x09FF), ("Guru", 0x0A00, 0x0A7F), ("Gujr", 0x0A80, 0x0AFF),
    ("Orya", 0x0B00, 0x0B7F), ("Taml", 0x0B80, 0x0BFF), ("Telu", 0x0C00, 0x0C7F),
    ("Knda", 0x0C80, 0x0CFF), ("Mlym", 0x0D00, 0x0D7F), ("Sinh", 0x0D80, 0x0DFF),
    ("Thai", 0x0E00, 0x0E7F), ("Laoo", 0x0E80, 0x0EFF), ("Tibt", 0x0F00, 0x0FFF),
    ("Mymr", 0x1000, 0x109F), ("Geor", 0x10A0, 0x10FF), ("Armn", 0x0530, 0x058F),
    ("Hebr", 0x0590, 0x05FF), ("Armn2", 0x0530, 0x058F), ("Mtei", 0xABC0, 0xABFF),
    ("Ethi", 0x1200, 0x137F), ("Khmr", 0x1780, 0x17FF),
    ("Latn", 0x0041, 0x005A), ("Latn2", 0x0061, 0x007A),
]
def script_of(ch):
    o = ord(ch)
    for name, lo, hi in RANGES:
        if lo <= o <= hi:
            return name.rstrip("2")
    return None

def dirs_for(iso):
    out = []
    for root in ("wikipedia", "ultrafineweb_l3", "fineweb2_hq_plus"):
        p = SRC_BASE / root
        if not p.is_dir():
            continue
        for d in p.iterdir():
            if d.is_dir() and (d.name == iso or d.name.split("_")[0].lower() == iso):
                if (d / "top100k.txt").exists():
                    out.append((root, d))
    return out

for iso in TARGETS:
    bucket = {}
    for root, d in dirs_for(iso):
        wc = {}
        with (d / "top100k.txt").open(encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= 5000:
                    break
                parts = line.rstrip("\n").split("\t", 1)
                if len(parts) != 2 or not parts[0].isdigit():
                    continue
                c = int(parts[0])
                sc = {}
                for ch in parts[1]:
                    s = script_of(ch)
                    if s:
                        sc[s] = sc.get(s, 0) + 1
                if sc:
                    best = max(sc, key=sc.get)
                    wc[best] = wc.get(best, 0) + c
        tot = sum(wc.values()) or 1
        top = sorted(wc.items(), key=lambda kv: -kv[1])[:4]
        bucket[d.name] = (root, [(s, f"{c/tot:.1%}") for s, c in top])
    print(f"{iso:8} " + "  |  ".join(
        f"{dn}({r}): {', '.join(f'{s} {p}' for s, p in v)}" for dn, (r, v) in bucket.items())
        if bucket else f"{iso:8} <no corpus dirs>")
