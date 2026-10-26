#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""包基本功能冒烟测试（需要本地数据目录，缺数据时自动跳过）"""
import pytest

import vocabfreq as wordfreq

try:
    wordfreq.get_data_dir()
    HAS_DATA = True
except FileNotFoundError:
    HAS_DATA = False

pytestmark = pytest.mark.skipif(not HAS_DATA, reason="WORDFREQ_DATA / 仓库数据目录不可用")


def test_bands_structure():
    wf = wordfreq.load("zh")
    assert len(wf.bands) == wordfreq.N_BANDS
    assert len(wf) > 10000


def test_top_n():
    assert wordfreq.top_n_list("zh", 3)[0] == "的"
    assert len(wordfreq.top_n_list("en", 50)) == 50


def test_word_frequency():
    f = wordfreq.word_frequency("的", "zh")
    assert 0.01 < f < 0.1
    assert wordfreq.word_frequency("qqqzzz", "zh") == 0.0
    assert "的" in wordfreq.load("zh")


def test_band_slice():
    wf = wordfreq.load("en")
    mid = wf.slice(100, 200)
    assert mid and all(10 ** (-199 / 100) <= f <= 10 ** (-100 / 100) for _, f in mid)
    assert wf.words(100, 200) == [w for w, _ in mid]
    assert wf[120:123] == wf.bands[120:123]
    assert len(wf.slice()) == len(wf)


def test_available_languages():
    langs = wordfreq.available_languages()
    assert {"zh", "en"} <= set(langs)
    assert langs["zh"]["kept"] > 0
