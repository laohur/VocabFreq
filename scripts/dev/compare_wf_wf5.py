#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比 wordfreq (v4) 和 WordFrequency (v5) 所有语言的词表规模与词频覆盖率。
输出两张全覆盖 Markdown 表：wordfreq v4 全 43 语、WordFrequency 全语种（含 v5-only）。
覆盖率 = Σ n_b × 10^(-b/100)，其中 b = position - 1（header 在 [0]）。
"""
import gzip, json, math
from pathlib import Path

WF_DIR  = Path(r"D:\code\河狸记词\data\hf-upload\wordfreq")
WF5_DIR = Path(r"D:\code\河狸记词\data\hf-upload\WordFrequency")

LANG_NAMES = {
    "af": "Afrikaans", "ar": "Arabic", "arz": "Egyptian Arabic",
    "az": "Azerbaijani", "be": "Belarusian", "bg": "Bulgarian",
    "bn": "Bengali", "bs": "Bosnian", "ca": "Catalan",
    "ce": "Chechen", "ceb": "Cebuano", "cs": "Czech",
    "da": "Danish", "de": "German", "dv": "Dhivehi",
    "el": "Greek", "en": "English", "es": "Spanish",
    "et": "Estonian", "fa": "Persian", "fi": "Finnish",
    "fil": "Filipino", "fr": "French", "gu": "Gujarati",
    "he": "Hebrew", "hi": "Hindi", "hr": "Croatian",
    "hu": "Hungarian", "hy": "Armenian", "id": "Indonesian",
    "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "ka": "Georgian", "kk": "Kazakh", "km": "Khmer",
    "kn": "Kannada", "ko": "Korean", "lt": "Lithuanian",
    "lv": "Latvian", "mk": "Macedonian", "ml": "Malayalam",
    "mn": "Mongolian", "mr": "Marathi", "ms": "Malay",
    "my": "Myanmar", "nb": "Norwegian Bokmål", "ne": "Nepali",
    "nl": "Dutch", "no": "Norwegian", "pa": "Punjabi",
    "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sh": "Serbo-Croatian", "si": "Sinhala",
    "sk": "Slovak", "sl": "Slovenian", "sq": "Albanian",
    "sr": "Serbian", "sv": "Swedish", "ta": "Tamil",
    "te": "Telugu", "th": "Thai", "tr": "Turkish",
    "tt": "Tatar", "uk": "Ukrainian", "ur": "Urdu",
    "vi": "Vietnamese", "zh": "Chinese",
}

# ── 读 meta ─────────────────────────────────────────────
wf_meta  = json.loads((WF_DIR / "meta.json").read_text(encoding="utf-8"))
wf5_meta = json.loads((WF5_DIR / "meta.json").read_text(encoding="utf-8"))

wf_langs  = set(wf_meta["languages"].keys())
wf5_langs = set(wf5_meta["languages"].keys())

# ── 计算 cBpack 覆盖率 ──────────────────────────────────
def cBpack_coverage(data_path: Path):
    """读 [header, band_0, …] 格式 cBpack 文件，返回收积覆盖率。
    结构：list，len = 1 + N_BANDS，[0] = header dict，[1..N] = band 0..N-1。
    band b 对应频率 10^(-b/100)。
    """
    import msgpack
    with gzip.open(data_path, "rb") as f:
        raw = f.read()
    data = msgpack.unpackb(raw, raw=False)
    if not isinstance(data, (list, tuple)) or len(data) < 2:
        return 0.0
    cov = 0.0
    for i in range(1, len(data)):          # skip header at [0]
        band_idx = i - 1                    # band_0 at data[1]
        words = data[i]
        cov += len(words) * 10 ** (-band_idx / 100)
    return cov

# ── 收集 wordfreq v4 数据 ───────────────────────────────
wf_data = {}
for lang in sorted(wf_langs):
    kept = wf_meta["languages"][lang]["kept"]
    data_path = WF_DIR / "data" / f"small_{lang}.msgpack.gz"
    cov = cBpack_coverage(data_path) if data_path.exists() else None
    wf_data[lang] = {"kept": kept, "coverage": cov}

# ── 收集 WordFrequency v5 数据 ──────────────────────────
wf5_data = {}
for lang in sorted(wf5_langs):
    m = wf5_meta["languages"][lang]
    if "_previous_wf_meta" in m:
        cov = m["_previous_wf_meta"].get("coverage")
        kept = m["_previous_wf_meta"]["kept"]
    else:
        cov = m.get("coverage")
        kept = m["kept"]
    wf5_data[lang] = {"kept": kept, "coverage": cov}

# ── 辅助 ────────────────────────────────────────────────
def fmt_cov(v):
    return f"{v*100:.1f}%" if v is not None else "—"

def fmt_delta(v, suffix=""):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    if suffix == "%":
        return f"{sign}{v*100:.1f}%"
    return f"{sign}{v:,}"

def wf5_entry(code):
    """返回 (wf5_kept, wf5_cov_s, 是否来自wf5_only)"""
    wf5 = wf5_data[code]
    return wf5["kept"], wf5["coverage"]

# ── 输出 wordfreq v4 全 43 语表 ─────────────────────────
print("## wordfreq v4 — 全部 43 语种\n")
print("| code | language | wf 词数 | wf 覆盖率 | WF 词数 | WF 覆盖率 | Δ 词数 | Δ 覆盖率 |")
print("|------|----------|--------:|----------:|--------:|----------:|--------:|----------:|")

for code in sorted(wf_langs, key=lambda c: LANG_NAMES.get(c, c).lower()):
    name = LANG_NAMES.get(code, code)
    wf  = wf_data[code]
    wf5 = wf5_data.get(code)
    wf_kept_s = f"{wf['kept']:,}"
    wf_cov_s  = fmt_cov(wf["coverage"])
    if wf5 is not None:
        wf5_kept   = wf5["kept"]
        wf5_cov    = wf5["coverage"]
        delta_k    = wf5_kept - wf["kept"]
        delta_c    = (wf5_cov - wf["coverage"]) * 100 if (wf5_cov is not None and wf["coverage"] is not None) else None
        wf5_kept_s = f"{wf5_kept:,}"
        wf5_cov_s  = fmt_cov(wf5_cov)
        delta_k_s  = f"{delta_k:+,}"
        delta_c_s  = f"{delta_c:+.1f}%" if delta_c is not None else "—"
    else:
        wf5_kept_s = "—"
        wf5_cov_s  = "—"
        delta_k_s  = "—"
        delta_c_s  = "—"
    print(f"| {code} | {name} | {wf_kept_s} | {wf_cov_s} | {wf5_kept_s} | {wf5_cov_s} | {delta_k_s} | {delta_c_s} |")

# ── 输出 WordFrequency v5 全语种表 ──────────────────────
print("\n\n## WordFrequency v5 — 全部语种（含 v5-only）\n")
print("| code | language | wf 词数 | wf 覆盖率 | WF 词数 | WF 覆盖率 | Δ 词数 | Δ 覆盖率 |")
print("|------|----------|--------:|----------:|--------:|----------:|--------:|----------:|")

for code in sorted(wf5_langs, key=lambda c: LANG_NAMES.get(c, c).lower()):
    name = LANG_NAMES.get(code, code)
    wf5 = wf5_data[code]
    wf5_kept_s = f"{wf5['kept']:,}"
    wf5_cov_s  = fmt_cov(wf5["coverage"])
    wf  = wf_data.get(code)
    if wf is not None:
        wf_kept    = wf["kept"]
        wf_cov     = wf["coverage"]
        delta_k    = wf5["kept"] - wf_kept
        delta_c    = (wf5["coverage"] - wf_cov) * 100 if (wf5["coverage"] is not None and wf_cov is not None) else None
        wf_kept_s  = f"{wf_kept:,}"
        wf_cov_s   = fmt_cov(wf_cov)
        delta_k_s  = f"{delta_k:+,}"
        delta_c_s  = f"{delta_c:+.1f}%" if delta_c is not None else "—"
    else:
        wf_kept_s = "—"
        wf_cov_s  = "—"
        delta_k_s = "—"
        delta_c_s = "—"
    print(f"| {code} | {name} | {wf_kept_s} | {wf_cov_s} | {wf5_kept_s} | {wf5_cov_s} | {delta_k_s} | {delta_c_s} |")

# ── 输出 WordFrequency v5-only 表 ───────────────────────
print("\n\n## WordFrequency v5 — 仅 v5 独有语种\n")
print("| code | language | WF 词数 | WF 覆盖率 |")
print("|------|----------|--------:|----------:|")
for code in sorted(wf5_langs - wf_langs, key=lambda c: LANG_NAMES.get(c, c).lower()):
    name = LANG_NAMES.get(code, code)
    wf5 = wf5_data[code]
    print(f"| {code} | {name} | {wf5['kept']:,} | {fmt_cov(wf5['coverage'])} |")
