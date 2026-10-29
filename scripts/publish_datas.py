# -*- coding: utf-8 -*-
"""发布三档词频表（publish_datas）。

把 build_datas.py 产出的 data_small / data_middle / data_large 整体同步到
D:\\code\\河狸记词\\data\\hf-upload\\VocabFreq，包结构参照 hf-upload\\wordfreq：
  data_<tier>/<code>.txt   词表（word<TAB>词频覆盖率，8 位小数，降序）
  README.md                HF 数据集卡片（YAML frontmatter + 说明 + 三档汇总表）
  meta.json                每档每语言的清洗统计（raw/规则命中/kept/coverage）
  files.json               全部发布文件的字节数 + SHA256 校验清单
  .gitattributes / .hfignore   照搬 wordfreq 发布包
"""

import datetime
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

import msgpack

ROOT = Path(__file__).resolve().parents[1]
REF = Path(r"D:\code\河狸记词\data\hf-upload\wordfreq")
DST = Path(r"D:\code\河狸记词\data\hf-upload\VocabFreq")
STATS = ROOT / "reports" / "build_datas" / "stats.json"
TIERS = ("data_small", "data_middle", "data_large")

TIER_DESC = {
    "data_small": ("wordfreq 3.0.2 small lists (cBpack msgpack.gz)",
                   "MIT (upstream wordfreq)"),
    "data_middle": ("Wikipedia top-100k token counts + meta.json total_tokens",
                    "CC BY-SA 3.0 / GFDL (Wikipedia)"),
    "data_large": ("Unicode UniLex frequency (per-billion scaled crawl counts)",
                   "Unicode DFS-2016"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def to_cBpack(pairs):
    """编码为 wordfreq cBpack 格式：data[0]=头部，data[1+cB]=该 centibel 桶的词表
    （桶内按字母序）。coverage=10^(-cB/100)，cB 600 即百万分之一阈值。
    可用 wordfreq 的 read_cBpack 直接读取。"""
    buckets = [[] for _ in range(601)]  # cB 0..600
    for w, cov in pairs:
        cb = round(-100.0 * math.log10(cov)) if cov > 0 else 600
        buckets[min(max(cb, 0), 600)].append(w)
    for b in buckets:
        b.sort()
    return [{"format": "cB", "version": 1}] + buckets


_NAME_CACHE: dict = {}


def lang_names(code: str) -> tuple[str, str]:
    """langcodes 尽力取英文名与本名，取不到回退 '-'。"""
    if code in _NAME_CACHE:
        return _NAME_CACHE[code]
    en = nat = "-"
    try:
        import langcodes
        l = langcodes.Language.get(code.replace("_", "-"))
        dn = l.display_name("en")
        if dn and dn.strip().lower() != code.lower():
            en = dn
        am = l.autonym()
        if am and am.strip() and am.strip().lower() != code.lower():
            nat = am
    except Exception:
        pass
    _NAME_CACHE[code] = (en, nat)
    return en, nat


def lang_table(tier: str, stats: dict) -> str:
    """wordfreq 卡片式逐语言表：code|language|native|first word|float|words|coverage。"""
    lines = [
        f"<!-- BEGIN GENERATED LANGUAGE TABLE:{tier} -->",
        f"`{tier}/{tier.removeprefix('data_')}_<code>.msgpack.gz`: wordfreq cBpack "
        "(coverage = 10^(-cB/100), kept if >= 1e-6 i.e. cB <= 600). "
        "Sorted by cumulative coverage; `float` is the top word's coverage.",
        "",
        "| code | language | native name | first word | float | words | cumulative coverage |",
        "|------|----------|-------------|------------|-------|-------|---------------------|",
    ]
    for code, s in sorted(stats.items(), key=lambda kv: -kv[1]["coverage"]):
        first, fl = "-", ""
        tf = ROOT / tier / f"{code}.txt"  # 构建侧 TSV 的首行 = 最高频词
        if tf.exists():
            with tf.open("r", encoding="utf-8") as fh:
                head = fh.readline().rstrip("\n").split("\t")
            if len(head) == 2:
                first, fl = head[0], f"{float(head[1]):.2e}"
        en, nat = lang_names(code)
        lines.append(
            f"| {code} | {en} | {nat} | {first} | {fl} "
            f"| {s['kept']:,} | {s['coverage']*100:.1f}% |")
    lines.append(f"<!-- END GENERATED LANGUAGE TABLE:{tier} -->")
    return "\n".join(lines)


def build_meta(stats: dict) -> dict:
    tiers = {}
    for tier in TIERS:
        src, lic = TIER_DESC[tier]
        tiers[tier] = {"source": src, "license": lic,
                       "languages": stats[tier]}
    return {
        "version": 1,
        "generatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        "format": "wordfreq cBpack msgpack.gz: bucket index = centibels, coverage = 10^(-cB/100), threshold cB <= 600 (1e-6)",
        "threshold": 1e-6,
        "cleaning": ["unparsable", "invalid", "duplicate", "below_threshold"],
        "tiers": tiers,
    }


def build_readme(stats: dict) -> str:
    small_codes = ",".join(sorted(stats["data_small"]))
    n_small = len(stats["data_small"])
    n_mid = len(stats["data_middle"])
    n_large = len(stats["data_large"])
    tot = {t: {"langs": len(stats[t]),
               "raw": sum(s["raw"] for s in stats[t].values()),
               "kept": sum(s["kept"] for s in stats[t].values())}
           for t in TIERS}
    rows_total = sum(t["kept"] for t in tot.values())

    md = ["""---
language: [%s]
license: other
multilinguality: multilingual
pretty_name: "Three-tier Word Frequency Lists (43/347/1000 languages) / 三档词频表"
size_categories:
- 10M<n<100M
---

# Three-tier Word Frequency Lists / 三档词频表

A [VocabRadar](https://huggingface.co/vocabradar) dataset — these lists power
the [`vocabfreq`](https://pypi.org/project/vocabfreq/) Python package, which
downloads them on first use.

Word-frequency tables in three tiers, built independently (no merging) from three
sources: wordfreq "small" lists (%d languages), Wikipedia top-100k counts (%d),
and Unicode UniLex frequency lists (%d). One gzip-compressed MessagePack file
per language in wordfreq cBpack format (`<tier>_<code>.msgpack.gz`, readable via
`wordfreq.read_cBpack`), where a word's coverage (share of corpus tokens) is
stored as centibels: coverage = 10^(-cB/100), bucket index = cB. A word is kept
only if its frequency is at least one per million tokens (coverage >= 1e-6,
i.e. cB <= 600). %s rows in total.
`language` above lists the small tier; data_middle/data_large keep their source
codes verbatim (see `meta.json`).

> **VocabRadar** 出品：本词表为 [`vocabfreq`](https://pypi.org/project/vocabfreq/)
> Python 包的数据源，首次使用时自动下载。
>
> 三档词频表，三个来源各自成表、互不合并：小档（wordfreq，%d 语）、中档
> （维基百科 top100k，%d 语，剔除 simple）、大档（Unicode UniLex，%d 语）。
> 每语言一个 msgpack.gz（wordfreq cBpack 格式，`<档位>_<code>.msgpack.gz`，
> 可用 wordfreq.read_cBpack 读取）：词频覆盖率以厘贝存储（覆盖率=10^(-cB/100)，
> 桶索引=cB），按覆盖率降序构建；仅收录词频达到百万分之一（覆盖率 >= 1e-6，
> 即 cB <= 600）的词。

## Files

```
├── README.md
├── meta.json                      # per-tier, per-language cleaning stats
├── files.json                     # per-file size (bytes) and SHA-256
├── data_small/  (%d files)        # small_<code>.msgpack.gz, wordfreq, MIT
├── data_middle/ (%d files)        # middle_<code>.msgpack.gz, Wikipedia, CC BY-SA 3.0 / GFDL
└── data_large/  (%d files)        # large_<code>.msgpack.gz, UniLex, Unicode DFS-2016
```

## Cleaning rules

Only clearly-safe rules are applied (no false positives intended):
`unparsable` (empty/header/comment/unparseable rows), `invalid` (tokens with no
letter or mark — pure digits such as ISBNs and pure punctuation), `duplicate`
(kept max coverage), `below_threshold` (coverage < 1e-6). Identity per language:
`raw = unparsable + invalid + duplicate + below_threshold + kept`.

## Tier summaries

| tier | languages | raw rows | kept rows | coverage range of kept words |
|---|---|---|---|---|
""" % (small_codes, n_small, n_mid, n_large, f"{rows_total:,}",
       n_small, n_mid, n_large, n_small, n_mid, n_large)]
    for t in TIERS:
        lg = stats[t]
        covs = [s["coverage"] for s in lg.values()]
        md.append("| %s | %d | %s | %s | %.1f%%–%.1f%% |\n" % (
            t, len(lg), f"{tot[t]['raw']:,}", f"{tot[t]['kept']:,}",
            min(covs) * 100, max(covs) * 100))
    md.append("\n## Vocabulary lists\n\n")
    for t in TIERS:
        md.append("### " + t + "\n\n")
        md.append(lang_table(t, stats[t]))
        md.append("\n\n")
    md.append("## Sources\n\n"
              "- data_small: [wordfreq](https://github.com/rspeer/wordfreq) 3.0.2 "
              'small lists (every word with frequency >= 1e-6), MIT.\n'
              "- data_middle: Wikipedia top-100k token counts with corpus "
              "total_tokens from meta.json, CC BY-SA 3.0 / GFDL.\n"
              "- data_large: [Unicode UniLex](https://github.com/unicode-org/unilex) "
              "frequency (Form\\tFrequency, per billion tokens), Unicode DFS-2016.\n")
    return "".join(md)


def main():
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    stats = {t if t.startswith("data_") else f"data_{t}": v
             for t, v in stats.items()}  # stats.json 键为 small/middle/large

    for tier in TIERS:
        src, dst = ROOT / tier, DST / tier
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        n = 0
        for tf in sorted(src.glob("*.txt")):
            code = tf.stem
            pairs = []
            for line in tf.read_text(encoding="utf-8").splitlines():
                w, _, cov = line.partition("\t")
                pairs.append((w, float(cov)))
            out = dst / f"{tier.removeprefix('data_')}_{code}.msgpack.gz"
            with gzip.open(out, "wb") as fh:
                msgpack.pack(to_cBpack(pairs), fh, use_bin_type=True)
            n += 1
        print(f"{tier}: {n} msgpack.gz -> {dst}")

    for name in (".gitattributes", ".hfignore"):
        shutil.copy2(REF / name, DST / name)

    meta = build_meta(stats)
    (DST / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DST / "README.md").write_text(build_readme(stats), encoding="utf-8")

    entries = []
    for f in sorted(DST.rglob("*")):
        if f.is_file() and f.name != "files.json":
            entries.append({"file": f.relative_to(DST).as_posix(),
                            "bytes": f.stat().st_size,
                            "sha256": sha256(f)})
    (DST / "files.json").write_text(
        json.dumps({"generatedAt": datetime.datetime.now().isoformat(timespec="milliseconds"),
                    "algorithm": "sha256", "files": entries},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"meta.json + README.md + files.json ({len(entries)} entries) -> {DST}")


if __name__ == "__main__":
    main()
