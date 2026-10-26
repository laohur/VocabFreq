# VocabFreq

A self-built pipeline that produces word-frequency lists for 350 languages in
the [rspeer/wordfreq](https://github.com/rspeer/wordfreq) msgpack band format,
rebuilt from a single pyicu tokenization of three corpus sources:

- **FineWeb2 HQ+** (filtered web text, 1670+ language variants)
- **UltraFineWeb L3** (high-education web text, 20+ languages)
- **Wikipedia** (monthly dumps)

**Data is not included in this repository.** There is only one copy of the
data, at `data/wordfreq/` (gitignored); the published dataset and its card
live in `hf-upload/VocabFreq`.

自建多语言词频表构建管线，产出 rspeer/wordfreq 风格的 msgpack 频段词表
（700 个 centibel 频段）。**数据不纳入本仓库**——数据只有一份，位于
`data/wordfreq/`（已 gitignore）；发布数据集与说明卡片在 `hf-upload/VocabFreq`。

## Pipeline

    scripts/tokenize_one.py    # pyicu BreakIterator tokenization → top100k.txt per lang/source
    scripts/build_wordfreq.py  # band aggregation → data/wordfreq/data/small_<lang>.msgpack.gz + meta.json
    scripts/publish_data.py    # select (total source text_bytes > 100 MB) → sync hf-upload/VocabFreq + README tables

## Layout

    scripts/       core pipeline (3 scripts)
    scripts/dev/   one-off audit / threshold-sweep scripts (hardcoded local paths)
    vocabfreq/     runtime package (pip installable: `import vocabfreq`)
    tests/         package smoke tests
    docs/          plan.md (design), resource.md (source inventory)
    data/          gitignored: built data, logs, working files

## Installation

Requires Python 3.10+ and [PyICU][pyicu] (ICU libraries must be present; on
Debian/Ubuntu: `apt install libicu-dev`).

    pip install PyICU pyarrow msgpack

[pyicu]: https://gitlab.pyicu.org/main/pyicu

## Package usage

The runtime package (`import vocabfreq`, distribution name `vocabfreq`) only
needs `msgpack`. Install in editable mode from the repo (or set
`VOCABFREQ_DATA` to the data directory when installed elsewhere — the data
itself is not shipped with the package):

    pip install -e .

    >>> import vocabfreq
    >>> vocabfreq.word_frequency('的', 'zh')
    0.0427
    >>> vocabfreq.top_n_list('en', 3)
    ['the', 'of', 'and']
    >>> wf = vocabfreq.load('fr')         # BandList
    >>> wf.slice(100, 200)                # band slicing: cb in [100, 200) -> (word, freq)
    >>> wf.words(0, 100)                  # words only, freq >= 1e-1
    >>> wf.frequency('le'); len(wf); wf[120:130]

API: `word_frequency(word, lang)`, `top_n_list(lang, n)`,
`iter_wordlist(lang)`, `get_frequency_dict(lang, min_cb, max_cb)`,
`slice_words(lang, min_cb, max_cb)`, `available_languages()`,
`load(lang) -> BandList` (`.slice / .words / .top_n / .frequency / bands[i:j]`).

## Data format

Each file `data/wordfreq/data/small_<lang>.msgpack.gz` is a gzipped
MessagePack array `[header, band_0, …, band_699]`, where band *b* holds the
words whose frequency rounds to 10^(−b/100) (centibel *b*). The header
contains the build tag and language metadata. This matches the upstream
wordfreq layout, except that the band count is 700 instead of 699.

Selection rule: a language is published when its total source text volume
exceeds 100 MB (104,857,600 bytes) across sources.

## License

Code: MIT (see [LICENSE](./LICENSE)). The band-format design follows
rspeer/wordfreq (Apache-2.0); no upstream data or code is included.
