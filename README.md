# VocabFreq

## About VocabRadar

This dataset is a **VocabRadar** project — the vocabulary radar. The
[VocabRadar browser extension](https://vocabradar.com) marks up the words you do not know
yet while you watch videos or browse the web: definitions in place, translation, bilingual
subtitles and annotated subtitles. Whatever you looked up can go on to
[vocabradar.com](https://vocabradar.com), which turns it into related exercises and games
so the words actually stick.

Three-tier multi-language word-frequency lists in wordfreq cBpack band format, built
independently (no merging) from three sources:

- **small — [wordfreq](https://github.com/rspeer/wordfreq) 3.0.2 "small" lists**
  (43 languages, coverage ≥ 1e-6), MIT
- **middle — Wikipedia top-100k token counts** (347 languages, `simple`
  excluded), CC BY-SA 3.0 / GFDL
- **large — [Unicode UniLex](https://github.com/unicode-org/unilex) frequency
  lists** (1000 languages), Unicode DFS-2016

**Data is not included in this repository.** Build outputs live in
`data_small/ data_middle/ data_large/` (gitignored); the release package
lives in `../hf-upload/VocabFreq` and is published as the HF dataset
[vocabradar/VocabFreq](https://huggingface.co/datasets/vocabradar/VocabFreq).

这项工作是 **VocabRadar**（词汇雷达）的工作：[VocabRadar 浏览器扩展](https://vocabradar.com)
让你在看视频、刷网页时把还不认识的生词就地标注出来 —— 释义、翻译、双语字幕、注释字幕；
查过的词还能送到 [vocabradar.com](https://vocabradar.com)，自动生成相关习题与游戏，把词真正记住。

三档词频表，三个来源各自成表、互不合并：小档 wordfreq（43 语）、中档维基
百科 top100k（347 语，剔除 simple）、大档 Unicode UniLex（1000 语）。
**数据不纳入本仓库**——构建产物在 `data_small/ data_middle/ data_large/`
（已 gitignore）；发布包在 `../hf-upload/VocabFreq`，已推送为 HF 数据集
vocabradar/VocabFreq。

## Pipeline

    scripts/build_datas.py     # three sources → per-language TSV (word \t coverage) in data_<tier>/
    scripts/publish_datas.py   # TSV → cBpack msgpack.gz release in ../hf-upload/VocabFreq (+ README / meta.json / files.json)

Legacy FineWeb2-tokenize pipeline kept under `scripts/` (`tokenize_one.py`,
`build_wordfreq.py`, `publish_data.py`) and `scripts/dev/` (one-off audit
scripts with hardcoded local paths).

## Layout

    scripts/       build_datas.py + publish_datas.py (current pipeline); legacy scripts
    scripts/dev/   one-off audit / threshold-sweep scripts (hardcoded local paths)
    vocabfreq/     runtime package (pip installable: `import vocabfreq`)
    tests/         package smoke tests
    docs/          plan.md (design), resource.md (source inventory)
    data_small/    built TSVs, small tier (gitignored)
    data_middle/   built TSVs, middle tier (gitignored)
    data_large/    built TSVs, large tier (gitignored)
    reports/       build reports (stats.json, per-tier CSVs)

## Package usage

The runtime package (`import vocabfreq`, distribution name `vocabfreq`) only
needs `msgpack`. The data is not shipped with the package: on first use it is
downloaded from the HF dataset `vocabradar/VocabFreq` — default mirror
`https://hf-mirror.com` (override with `VOCABFREQ_ENDPOINT`), cached in
`~/.vocabfreq` (override with `VOCABFREQ_DATA` or `set_data_dir`).
`load(lang)` fetches just that language (all tiers that have it);
`vocabfreq.download()` prefetches everything. Every file is byte-size and
SHA-256 verified against the dataset's `files.json`, so downloads are
resumable and repeatable.

    pip install vocabfreq            # or: pip install -e . from the repo

    >>> import vocabfreq
    >>> vocabfreq.word_frequency('的', 'zh')   # auto-tier: small → middle → large
    0.0617
    >>> vocabfreq.top_n_list('en', 3)
    ['the', 'to', 'and']
    >>> wf = vocabfreq.load('fr')                      # default small tier (43 langs)
    >>> wf = vocabfreq.load('aai', wordlist='large')   # UniLex tier (1000 langs)
    >>> wf.slice(100, 200)                # band slicing: cb in [100, 200) -> (word, freq)
    >>> wf.words(0, 100)                  # words only, freq >= 1e-1
    >>> wf.frequency('le'); len(wf); wf[120:130]

Command line (after install, or `python -m vocabfreq`):

    vocabfreq                # download all languages (three tiers)
    vocabfreq en zh de       # download selected languages (all tiers that have them)
    vocabfreq --endpoint https://huggingface.co

API: `download(langs=None, data_dir=None, endpoint=None)`,
`word_frequency(word, lang)`, `top_n_list(lang, n)`,
`iter_wordlist(lang)`, `get_frequency_dict(lang, min_cb, max_cb)`,
`slice_words(lang, min_cb, max_cb)`, `available_languages(tier='small')`,
`load(lang, wordlist='small') -> BandList`
(`.slice / .words / .top_n / .frequency / bands[i:j]`).

## Data format

Each file `data_<tier>/<tier>_<lang>.msgpack.gz` is a wordfreq cBpack: a
gzipped MessagePack array `[header, band_0, …, band_600]`, where band *b*
holds the words whose coverage rounds to 10^(−b/100) (centibel *b*) and the
header is `{"format": "cB", "version": 1}`. Files are readable with
`wordfreq.read_cBpack`. Only words with coverage ≥ 1e-6 (cB ≤ 600) are kept,
so each list has 601 bands. Cleaning rules (`unparsable` / `invalid` /
`duplicate` / `below_threshold`) and per-language stats are in the dataset
`meta.json`; every file is listed with size + SHA-256 in `files.json`.

## License

Code: MIT (see [LICENSE](./LICENSE)). Dataset licenses differ per tier:
wordfreq small — MIT; Wikipedia middle — CC BY-SA 3.0 / GFDL; UniLex large —
Unicode DFS-2016. See the HF dataset card for details.
