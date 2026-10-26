#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_check_scripts.py — 找出 build meta 中非拉丁书写系统但 LANG_SCRIPTS 未配置的语种"""
import json
from pathlib import Path

SRC_META = Path(r"D:\code\河狸记词\data\WordFrequency\data\wordfreq\meta.json")
BUILD = Path(r"D:\code\河狸记词\data\WordFrequency\scripts\build_wordfreq.py")

NONLATIN = {
    # Arab
    "ar": "Arab", "arz": "Arab", "azb": "Arab", "ckb": "Arab", "ps": "Arab",
    "sd": "Arab", "ug": "Arab", "ur": "Arab", "pnb": "Arab", "skr": "Arab",
    "ms-arab": "Arab", "ku-arab": "Arab", "tt-arab": "Arab", "ha-arab": "Arab",
    # Beng / Deva / Brahmic
    "bn": "Beng", "as": "Beng",
    "hi": "Deva", "mr": "Deva", "ne": "Deva", "sa": "Deva", "kok": "Deva",
    "ks": "Deva", "doi": "Deva", "mni": "Deva", "mai": "Deva", "bho": "Deva",
    "ta": "Taml", "te": "Telu", "si": "Sinh", "gu": "Gujr", "pa": "Guru",
    "or": "Orya", "ml": "Mlym", "kn": "Knda",
    # Cyrl
    "be": "Cyrl", "bg": "Cyrl", "ce": "Cyrl", "ba": "Cyrl", "kk": "Cyrl",
    "ky": "Cyrl", "mk": "Cyrl", "mn": "Cyrl", "ru": "Cyrl", "sr": "Cyrl",
    "tg": "Cyrl", "tt": "Cyrl", "uk": "Cyrl", "av": "Cyrl", "os": "Cyrl",
    "ab": "Cyrl", "sah": "Cyrl", "cv": "Cyrl", "udm": "Cyrl", "ba-Latn": "Cyrl",
    # other
    "el": "Grek", "he": "Hebr", "yi": "Hebr", "dv": "Thaa",
    "ka": "Geor", "hy": "Armn",
    "zh": "Hani", "zh-Hant": "Hani", "ja": "Multi", "ko": "Hang",
    "th": "Thai", "lo": "Laoo", "my": "Mymr", "km": "Khmr", "bo": "Tibt",
    "am": "Ethi", "ti": "Ethi",
}

src = json.loads(SRC_META.read_text(encoding="utf-8"))["languages"]
block = BUILD.read_text(encoding="utf-8")
block = block[block.index("LANG_SCRIPTS = {"):block.index("DEFAULT_SCRIPTS")]

missing = []
for lang, m in src.items():
    exp = NONLATIN.get(lang)
    if exp and f'"{lang}"' not in block:
        missing.append((lang, exp, m["kept"], round(m["coverage"] * 100, 1)))
missing.sort(key=lambda r: -r[2])
print("非拉丁语种但 LANG_SCRIPTS 缺失（全部 350 语）:")
for lang, exp, kept, cov in missing:
    print(f"  {lang:10} expect={exp:5} kept={kept:>6} cov={cov:>5}%")
