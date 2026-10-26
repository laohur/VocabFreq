#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唯一分词脚本。冻结。

用法：
  模式 A (shard, web 预下载 txt):  python tokenize_one.py <source> <lang>
                                    读 corpus/<source>/<lang>/part-00000.txt

  模式 B (wiki parquet):          python tokenize_one.py --wiki <lang>
                                    读 ...wikipedia-monthly/20261001/<lang>/train/*.parquet, col=text

  模式 C (ultra/web parquet):     python tokenize_one.py --parquet <dir> <lang> <text_col> <out_source>
                                    读 <dir>/<lang>/multi_style/*.parquet, col=<text_col>
                                    输出到 wordfreq/<out_source>/<lang>/

分词：按 /\r\n|\n|\r/ 切行 → pyicu BreakIterator 逐行分词
      getRuleStatus()!=0 → lower() → counter

每个语种上限：1 GiB 纯文本（达到即停，边界在文档级，可微超）
"""
import os, sys, json, time, re, glob
from pathlib import Path
from collections import Counter

for _v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_v, None)

import icu
import pyarrow.parquet as pq

BASE      = Path(r"F:\data\WordFrequency")
CORPUS    = BASE / "corpus"
OUT       = BASE / "wordfreq"
ONE_GIB   = 1024 ** 3

SPLIT_RE  = re.compile(r"\r\n|\n|\r")

# ── locale maps ──────────────────────────────────────────────
# wiki iso2 / web BCP-47 / ultra lang_code → ICU locale
LOCALE_MAP = {
    # wiki iso2
    "en":"en","de":"de","fr":"fr","ru":"ru","ja":"ja","es":"es",
    "it":"it","pt":"pt","zh":"zh","ar":"ar","pl":"pl","nl":"nl",
    "uk":"uk","he":"he","id":"id","tr":"tr","ko":"ko","cs":"cs",
    "sv":"sv","fi":"fi","hu":"hu","ro":"ro","fa":"fa","vi":"vi",
    "bg":"bg","sr":"sr","hr":"hr","ca":"ca","el":"el","bn":"bn",
    "hi":"hi","ta":"ta","te":"te","ml":"ml","kn":"kn","mr":"mr",
    "gu":"gu","pa":"pa","ur":"ur","th":"th","da":"da","no":"no",
    "sk":"sk","sl":"sl","lv":"lv","lt":"lt","et":"et","is":"is",
    "ga":"ga","cy":"cy","sw":"sw","am":"am","ha":"ha","ig":"ig",
    "yo":"yo","zu":"zu","af":"af","so":"so","mg":"mg","sn":"sn",
    "st":"st","xh":"xh","gl":"gl","eu":"eu","hy":"hy","ka":"ka",
    "az":"az","mk":"mk","be":"be","tt":"tt","kk":"kk","uz":"uz",
    "ne":"ne","si":"si","km":"km","lo":"lo","my":"my","ti":"ti",
    "or":"or","as":"as","sa":"sa","dv":"dv","sd":"sd","ps":"ps",
    "ky":"ky","mn":"mn","bo":"bo","la":"la",
    # web BCP-47 (fineweb2 / general shard)
    "arb_Arab":"ar","ary_Arab":"ar","ben_Beng":"bn","bul_Cyrl":"bg",
    "cat_Latn":"ca","ces_Latn":"cs","cmn_Hani":"zh","deu_Latn":"de",
    "ell_Grek":"el","eng_Latn":"en","fas_Arab":"fa","fin_Latn":"fi",
    "fra_Latn":"fr","heb_Hebr":"he","hun_Latn":"hu","hye_Armn":"hy",
    "ind_Latn":"id","ita_Latn":"it","jpn_Jpan":"ja","kor_Hang":"ko",
    "nld_Latn":"nl","nob_Latn":"no","pol_Latn":"pl","por_Latn":"pt",
    "rus_Cyrl":"ru","spa_Latn":"es","srp_Cyrl":"sr","swe_Latn":"sv",
    "tel_Telu":"te","tha_Thai":"th","tur_Latn":"tr","ukr_Cyrl":"uk",
    "vie_Latn":"vi",
    # ultra lang prefix → iso_map: stripped in make_bi
}
ROOT = icu.Locale.getRoot()


def make_bi(lang):
    """lang may be 'en' (wiki), 'eng_Latn' (web), 'ultrafineweb_en_l3' (ultra)."""
    key = lang
    if key.startswith("ultrafineweb_"):
        key = key.split("_")[1]   # e.g. en_l3 → en
    loc = LOCALE_MAP.get(key)
    try:
        bi = icu.BreakIterator.createWordInstance(icu.Locale(loc)) if loc \
             else icu.BreakIterator.createWordInstance(ROOT)
        return bi, loc or "root"
    except Exception:
        return icu.BreakIterator.createWordInstance(ROOT), "root"


def tokenize_line(line, bi, counter):
    s = icu.UnicodeString(line)
    bi.setText(s)
    st = bi.first()
    en = bi.nextBoundary()
    while en != icu.BreakIterator.DONE:
        if bi.getRuleStatus() != 0:
            counter[str(s[st:en]).lower()] += 1
        st = en
        en = bi.nextBoundary()


# ── mode A: shard txt ──────────────────────────────────────
def run_shard(source, lang):
    t0 = time.time()
    shard = CORPUS / source / lang / "part-00000.txt"
    if not shard.exists():
        print(f"SKIP {source}/{lang}: no shard", flush=True); return

    bi, used = make_bi(lang)
    counter = Counter()
    rows = 0
    BUF = 8 * 1024 * 1024
    tail = ""

    with shard.open("r", encoding="utf-8", errors="replace") as fh:
        for chunk in iter(lambda: fh.read(BUF), ""):
            if tail:
                chunk = tail + chunk; tail = ""
            last = -1
            for m in SPLIT_RE.finditer(chunk):
                last = m.end()
            if last == -1:
                tail = chunk; continue
            if last < len(chunk):
                tail = chunk[last:]; chunk = chunk[:last]
            for line in SPLIT_RE.split(chunk):
                if not line: continue
                tokenize_line(line, bi, counter)
                rows += 1
        if tail:
            for line in SPLIT_RE.split(tail):
                if not line: continue
                tokenize_line(line, bi, counter)
                rows += 1

    elapsed = time.time() - t0
    out = OUT / source / lang
    out.mkdir(parents=True, exist_ok=True)
    _write(counter, elapsed, rows, {
        "source": source, "lang": lang, "locale_used": used,
        "text_gib": round(shard.stat().st_size / 1024**3, 3),
    }, out)


# ── mode B: wiki parquet ───────────────────────────────────
def run_wiki(lang):
    wiki_src = Path(r"F:\data\corpus\wikipedia-monthly\20261001")
    lang_dir = wiki_src / lang
    _run_parquet(lang_dir, lang, "wikipedia", "text")


# ── mode C: ultra / fw2 / web parquet ───────────────────────
def run_parquet(lang, text_col, out_source, corpus_parent=None):
    """
    lang:           子目录名 (e.g. 'ultrafineweb_en_l3', 'deu_Latn')
    text_col:       parquet 文本列名 ('content' / 'text')
    out_source:      wordfreq/<out_source>/<lang>
    corpus_parent:  F:\data\corpus 下的父目录
                    None → 'Ultra-FineWeb-L3' if lang.startswith('ultrafineweb_') else 'FineWeb2-HQ-plus'
    """
    if corpus_parent is None:
        corpus_parent = "Ultra-FineWeb-L3" if lang.startswith("ultrafineweb_") else "FineWeb2-HQ-plus"
    dirpath = Path(r"F:\data\corpus") / corpus_parent / lang
    _run_parquet(dirpath, lang, out_source, text_col)


def _run_parquet(lang_dir, lang, out_source, text_col):
    t0 = time.time()
    if not lang_dir.is_dir():
        print(f"SKIP {out_source}/{lang}: no dir {lang_dir}", flush=True); return

    bi, used = make_bi(lang)
    counter = Counter()
    rows = 0
    text_bytes = 0

    pqt_files = sorted(lang_dir.rglob("*.parquet"))
    if not pqt_files:
        pqt_files = sorted(lang_dir.glob("*.parquet"))
    if not pqt_files:
        print(f"SKIP {out_source}/{lang}: no parquet in {lang_dir}", flush=True); return

    for pqt in pqt_files:
        table = pq.read_table(pqt, columns=[text_col])
        texts = table.column(text_col).to_pylist()
        for doc in texts:
            if not doc: continue
            if text_bytes >= ONE_GIB: break
            b = len(doc.encode("utf-8", "replace")) + 1
            if text_bytes + b > ONE_GIB and text_bytes > 0:
                text_bytes = ONE_GIB
                break
            for line in SPLIT_RE.split(doc):
                if not line: continue
                tokenize_line(line, bi, counter)
                rows += 1
            text_bytes += b
        if text_bytes >= ONE_GIB: break

    elapsed = time.time() - t0
    out = OUT / out_source / lang
    out.mkdir(parents=True, exist_ok=True)
    _write(counter, elapsed, rows, {
        "source": out_source,
        "lang": lang,
        "locale_used": used,
        "text_bytes": text_bytes,
        "text_gib": round(text_bytes / 1024**3, 3),
    }, out)


def _write(counter, elapsed, rows, meta, out):
    with (out / "top100k.txt").open("w", encoding="utf-8") as f:
        for w, c in counter.most_common(100_000):
            f.write(f"{c}\t{w}\n")
    meta["total_tokens"]   = counter.total()
    meta["unique_words"]   = len(counter)
    meta["rows"]           = rows
    meta["elapsed_sec"]    = round(elapsed, 1)
    meta["top1_repr"]      = [w for w, _ in counter.most_common(5)]
    (out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{meta['source']}/{meta['lang']:<16} {meta.get('text_gib', 0):.3f} GiB "
          f"tok={counter.total():>10} uniq={len(counter):>7} {elapsed:.0f}s "
          f"top1={meta['top1_repr']}", flush=True)


def main():
    if sys.argv[1] == "--wiki":
        run_wiki(sys.argv[2])
    elif sys.argv[1] == "--parquet":
        # <lang> <text_col> <out_source>
        run_parquet(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "--shard":
        run_shard(sys.argv[2], sys.argv[3])
    else:
        run_shard(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
