#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精确解码 wiki 语种 text 列，与 meta.text_bytes 对账。"""
import json, sys
from pathlib import Path

import pyarrow.parquet as pq

WIKI = Path(r"F:\data\corpus\wikipedia-monthly\20261001")
ONE_GIB = 1024 ** 3


def exact_decode(lang):
    d = WIKI / lang
    tot = 0
    n_docs = 0
    detail = []
    for p in sorted(d.rglob("*.parquet")):
        tb = pq.read_table(p, columns=["text"])
        docs = tb.column("text").to_pylist()
        n = sum(1 for doc in docs if doc)
        s = sum(len(doc.encode("utf-8", "replace")) + 1 for doc in docs if doc)
        tot += s
        n_docs += n
        detail.append((p.relative_to(d).as_posix(), len(docs), n, s))
    return tot, n_docs, detail


if __name__ == "__main__":
    for lang in sys.argv[1:]:
        tot, n_docs, detail = exact_decode(lang)
        mp = Path(r"F:\data\WordFrequency\wordfreq\wikipedia") / lang / "meta.json"
        R = json.loads(mp.read_text(encoding="utf-8"))["text_bytes"]
        print(f"\n== {lang} ==")
        for rel, nall, nne, s in detail:
            print(f"  {rel:40} rows={nall:>7} nonempty={nne:>7} bytes={s:>12,}")
        print(f"  exact={tot:,} ({tot/ONE_GIB:.3f} GiB)  meta.text_bytes={R:,} "
              f"({R/ONE_GIB:.3f} GiB)  diff={tot-R:,}")
