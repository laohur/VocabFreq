# -*- coding: utf-8 -*-
"""三档语言词频表构建（build_datas）。

三来源各自独立成表，不合并：
  小 data_small  <- D:\\code\\河狸记词\\data\\hf-upload\\wordfreq\\data\\small_*.msgpack.gz
                    (wordfreq cBpack 格式，桶索引=centibels，freq=10^(-cB/100))
  中 data_middle <- F:\\data\\WordFrequency\\wordfreq\\wikipedia\\<lang>\\top100k.txt
                    (出现次数<TAB>word 两列，total_tokens 在 meta.json)
  大 data_large  <- F:\\data\\WordFrequency\\resource\\unilex-main\\data\\frequency\\<code>.txt
                    (UniLex TSV，Form\\tFrequency，Frequency=每十亿词出现次数)

输出：每语言一个 UTF-8 TSV：word<TAB>词频覆盖率（该词占语料的比例，8 位小数），
按覆盖率降序、同频按词升序。命名遵照来源：<code>.txt。

入选阈值：词频覆盖率 >= 百万分之一（1e-6）。
清洗规则（刻意从宽，只去确定垃圾，不误伤），规则命中数计入 meta：
  - unparsable: 空/表头/注释行，或列数不足、数值解析失败；
  - invalid:    词首尾去空白后不含任何字母/记号（L*/M*）——纯数字
                （ISBN、年份串等，任何文种）与纯标点都不成词；
  - duplicate:  同词重复，保留最高覆盖率；
  - below_threshold: 覆盖率 < 1e-6。
simple 不是语言，恒剔除。
"""

import csv
import gzip
import json
import unicodedata
from pathlib import Path

import msgpack

ROOT = Path(__file__).resolve().parents[1]  # data\\VocabFreq
SMALL_SRC = Path(r"D:\code\河狸记词\data\hf-upload\wordfreq\data")
MID_SRC = Path(r"F:\data\WordFrequency\wordfreq\wikipedia")
LARGE_SRC = Path(r"F:\data\WordFrequency\resource\unilex-main\data\frequency")
OUT_ROOT = ROOT
REPORT_DIR = ROOT / "reports" / "build_datas"

THRESH = 1e-6  # 词频覆盖率阈值 = 百万分之一
EXCLUDE_LANGS = {"simple"}  # 不是语言

# ---------------------------------------------------------------- helpers


def read_text_auto(path: Path) -> str:
    """按 utf-8 -> utf-8-sig -> latin-1 顺序读取。"""
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def has_text(word: str) -> bool:
    """至少含一个字母或记号（L*/M*）；纯数字（ISBN 等）与纯标点不成词。"""
    return any(unicodedata.category(ch)[0] in ("L", "M") for ch in word)


def clean(pairs):
    """(word, coverage) 迭代 -> (stats, kept_pairs)。

    stats = {"raw":..., "unparsable":..., "invalid":..., "duplicate":...,
             "below_threshold":..., "kept":..., "coverage": sum(kept)}
    恒等式 raw = unparsable + invalid + duplicate + below_threshold + kept
    """
    st = {"raw": 0, "unparsable": 0, "invalid": 0, "duplicate": 0,
          "below_threshold": 0, "kept": 0, "coverage": 0.0}
    best = {}
    for item in pairs:
        if item is None:
            st["unparsable"] += 1
            continue
        st["raw"] += 1
        w, cov = item
        w = w.strip()
        if not w or not has_text(w):
            st["invalid"] += 1
            continue
        if cov > best.get(w, -1.0):
            if w in best:
                st["duplicate"] += 1
            best[w] = cov
        else:
            st["duplicate"] += 1
    kept = []
    for w, cov in sorted(best.items(), key=lambda kv: (-kv[1], kv[0])):
        if cov >= THRESH:
            kept.append((w, cov))
        else:
            st["below_threshold"] += 1
    st["kept"] = len(kept)
    st["coverage"] = sum(c for _, c in kept)
    return st, kept


def write_table(tier: str, code: str, kept):
    out_dir = OUT_ROOT / f"data_{tier}"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{code}.txt"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(f"{w}\t{cov:.8f}\n" for w, cov in kept)
    return path


def report(tier: str, langs: dict):
    """langs: {code: stats} -> CSV + stats.json + 控制台汇总。"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / f"{tier}.csv").open("w", encoding="utf-8-sig",
                                           newline="") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["lang", "raw", "unparsable", "invalid", "duplicate",
                       "below_threshold", "kept", "coverage"])
        for code in sorted(langs):
            s = langs[code]
            wcsv.writerow([code, s["raw"], s["unparsable"], s["invalid"],
                           s["duplicate"], s["below_threshold"], s["kept"],
                           f'{s["coverage"]:.8f}'])
    tot = {k: sum(s[k] for s in langs.values())
           for k in ("raw", "unparsable", "invalid", "duplicate",
                     "below_threshold", "kept")}
    tot["coverage"] = sum(s["coverage"] for s in langs.values())
    print(f"[{tier}] {len(langs)} langs, raw={tot['raw']:,}, "
          f"kept={tot['kept']:,}, coverage={tot['coverage']:.4f}")


# ---------------------------------------------------------------- builders


def build_small():
    """wordfreq cBpack：data[1:] 桶索引即 cB，freq=10^(-cB/100)。"""
    langs = {}
    for f in sorted(SMALL_SRC.glob("small_*.msgpack.gz")):
        code = f.name.removeprefix("small_").removesuffix(".msgpack.gz")
        data = msgpack.loads(gzip.decompress(f.read_bytes()), raw=False)
        if not (isinstance(data, list) and isinstance(data[0], dict)
                and data[0].get("format") == "cB"):
            print(f"skip bad header: {code}")
            continue

        def gen():
            for cb, words in enumerate(data[1:]):
                if not words:
                    continue
                cov = 10 ** (-cb / 100)
                for w in words:
                    yield w, cov

        st, kept = clean(gen())
        write_table("small", code, kept)
        langs[code] = st
    return langs


def build_middle():
    langs = {}
    for d in sorted(MID_SRC.iterdir()):
        if not d.is_dir() or d.name in EXCLUDE_LANGS:
            continue
        meta_p, tf = d / "meta.json", d / "top100k.txt"
        if not (meta_p.exists() and tf.exists()):
            print(f"skip incomplete: {d.name}")
            continue
        total = json.loads(meta_p.read_text("utf-8"))["total_tokens"]
        if not total:
            print(f"skip no total_tokens: {d.name}")
            continue

        def gen():
            for line in read_text_auto(tf).splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    yield None
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    yield None
                    continue
                try:
                    yield parts[1], int(parts[0]) / total
                except (ValueError, OverflowError):
                    yield None

        st, kept = clean(gen())
        write_table("middle", d.name, kept)
        langs[d.name] = st
    return langs


def build_large():
    langs = {}
    for f in sorted(LARGE_SRC.glob("*.txt")):
        code = f.stem

        def gen():
            for line in read_text_auto(f).splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    yield None
                    continue
                parts = line.split("\t")
                if len(parts) < 2 or parts[0] == "Form":  # 表头 Form\tFrequency
                    yield None
                    continue
                try:
                    yield parts[0], float(parts[1]) / 1e9  # 每十亿 -> 比例
                except (ValueError, OverflowError):
                    yield None

        st, kept = clean(gen())
        write_table("large", code, kept)
        langs[code] = st
    return langs


# ---------------------------------------------------------------- main

def main():
    all_stats = {}
    for tier, fn in (("small", build_small), ("middle", build_middle),
                     ("large", build_large)):
        langs = fn()
        report(tier, langs)
        all_stats[tier] = langs
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "stats.json").write_text(
        json.dumps(all_stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print("done.")


if __name__ == "__main__":
    main()
