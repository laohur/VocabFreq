"""词频数据加载与 BandList。

数据布局：三档词表（small/middle/large），每档每语种一个 gzip 压缩的
MessagePack 数组 ``[header, band_0, ..., band_600]``，band b 内的词频约为
``10^(-b/100)``（centibel b）；收录阈值为百万分之一（1e-6，即 cB <= 600，
共 601 个频段）。文件路径为 ``data_<tier>/<tier>_<lang>.msgpack.gz``。
数据不随包分发，按需从 Hugging Face 下载并缓存（端点自适应：默认
hf-mirror.com 镜像，不可达时自动回退 huggingface.co，见
:mod:`vocabfreq.download`），目录解析顺序：

1. :func:`set_data_dir` 显式指定
2. 环境变量 ``VOCABFREQ_DATA``（指向含 ``meta.json`` 的目录）
3. 仓库内默认路径（源码 / editable 安装时可用）
4. 缓存目录 ``~/.vocabfreq``（缺失的文件在 :func:`load` /
   :func:`available_languages` 时自动按需下载）
"""
from __future__ import annotations

import gzip
import os
from pathlib import Path

import msgpack

from .download import DEFAULT_DATA_DIR, TIERS, download as _download

N_BANDS = 601  # cB 0..600：覆盖率 1e0..1e-6，收录阈值 1e-6（cB 600 桶）

_DATA_DIR: Path | None = None
_CACHE: dict[tuple[str, str, str], "BandList"] = {}


class BandList:
    """单语种词表。

    - ``wf[i]`` / ``wf[i:j]``：按频段索引或切片，返回词列表
    - :meth:`slice`：按 centibel 区间取词及频率
    - :meth:`top_n`：取最高频的前 n 个词
    - :meth:`frequency`：查询单词频率（缺席为 0.0）
    """

    def __init__(self, lang: str, obj: list):
        self.lang = lang
        self.header = obj[0]
        self.bands: list[list[str]] = obj[1:]
        if len(self.bands) != N_BANDS:
            raise ValueError(f"{lang}: 期望 {N_BANDS} 个频段，实际 {len(self.bands)}")
        self._index: dict[str, int] | None = None

    # ── 基本协议 ──

    def __len__(self) -> int:
        return sum(len(b) for b in self.bands)

    def __contains__(self, word: str) -> bool:
        return word in self._build_index()

    def __iter__(self):
        """按频段升序迭代 ``(word, freq)``。"""
        for w, f in self.slice():
            yield w, f

    def __getitem__(self, key):
        """频段索引/切片（``wf[120]``、``wf[120:180]``），返回词列表。"""
        return self.bands[key]

    def __repr__(self) -> str:
        return f"<BandList {self.lang!r}: {len(self):,} words>"

    # ── 查询 ──

    def _build_index(self) -> dict[str, int]:
        if self._index is None:
            self._index = {
                w: b for b, words in enumerate(self.bands) for w in words
            }
        return self._index

    def frequency(self, word: str) -> float:
        """单词频率；不在词表中返回 0.0。"""
        b = self._build_index().get(word)
        return 10 ** (-b / 100) if b is not None else 0.0

    # ── 切片 ──

    def slice(self, min_cb: int = 0, max_cb: int = N_BANDS) -> list[tuple[str, float]]:
        """频段切片：返回 centibel ∈ [min_cb, max_cb) 的 ``(word, freq)``
        列表，按频段升序（即频率从高到低）。"""
        lo = max(0, min_cb)
        hi = min(N_BANDS, max_cb)
        return [
            (w, 10 ** (-b / 100))
            for b in range(lo, hi)
            for w in self.bands[b]
        ]

    def words(self, min_cb: int = 0, max_cb: int = N_BANDS) -> list[str]:
        """仅返回切片区间内的词。"""
        return [w for w, _ in self.slice(min_cb, max_cb)]

    def top_n(self, n: int) -> list[str]:
        """最高频的前 n 个词。"""
        out: list[str] = []
        for words in self.bands:
            out.extend(words)
            if len(out) >= n:
                return out[:n]
        return out


# ── 数据目录解析 ──


def set_data_dir(path: str | Path) -> None:
    """显式指定数据目录（含 ``meta.json`` 与 ``data_<tier>/<tier>_*.msgpack.gz``）。"""
    global _DATA_DIR
    _DATA_DIR = Path(path)
    _CACHE.clear()


def get_data_dir() -> Path:
    """解析当前数据目录。前三级找不到时回落到缓存目录 ``~/.vocabfreq``
    （其中的文件会在 :func:`load` / :func:`available_languages` 时按需下载）。"""
    if _DATA_DIR is not None:
        return _DATA_DIR
    env = os.environ.get("VOCABFREQ_DATA")
    if env:
        return Path(env)
    default = Path(__file__).resolve().parent.parent / "data" / "wordfreq"
    # 仅当为新结构（三档目录 + meta.json）时才使用仓库内默认路径
    if (default / "meta.json").exists() and (default / "data_small").exists():
        return default
    return DEFAULT_DATA_DIR


def available_languages(tier: str = "small") -> dict[str, dict]:
    """返回 ``meta.json`` 中该档位（small/middle/large）的语种记录
    （raw / kept / coverage 等清洗统计）；本地缺失时自动从 HF 下载。"""
    d = get_data_dir()
    if not (d / "meta.json").exists():
        _download(langs=[], data_dir=d)
    return json_load(d / "meta.json")["tiers"][f"data_{tier}"]["languages"]


# ── 加载与查询 ──


def load(lang: str, wordlist: str = "small") -> BandList:
    """加载语种词表（``wordlist`` ∈ small/middle/large，按 (数据目录, 语种,
    wordlist) 缓存）；本地缺失时自动从 HF 下载该语种。"""
    if wordlist not in TIERS:
        raise ValueError(f"wordlist 必须是 {'/'.join(TIERS)}，得到 {wordlist!r}")
    d = get_data_dir()
    path = d / f"data_{wordlist}" / f"{wordlist}_{lang}.msgpack.gz"
    if not path.exists():
        _download([lang], data_dir=d)
    if not path.exists():
        raise KeyError(
            f"{lang}: {wordlist} 档未收录该语种"
            f"（可用 available_languages('{wordlist}') 查看已收录语种）")
    root = str(d.resolve())
    key = (root, lang, wordlist)
    if key not in _CACHE:
        with gzip.open(path, "rb") as f:
            obj = msgpack.unpackb(f.read(), raw=False)
        _CACHE[key] = BandList(lang, obj)
    return _CACHE[key]


def word_frequency(word: str, lang: str) -> float:
    """单词在语种中的频率估计（0.0 表示不在词表）。

    自动选档：small → middle → large，取第一个收录该语种的档位。"""
    return _load_auto(lang).frequency(word)


def top_n_list(lang: str, n: int) -> list[str]:
    """语种最高频的前 n 个词（自动选档，同 :func:`word_frequency`）。"""
    return _load_auto(lang).top_n(n)


def iter_wordlist(lang: str):
    """按频率从高到低迭代 ``(word, freq)``（自动选档）。"""
    yield from _load_auto(lang)


def get_frequency_dict(lang: str, min_cb: int = 0, max_cb: int = N_BANDS) -> dict[str, float]:
    """语种词频字典（自动选档；可用 centibel 区间截取）。"""
    return dict(_load_auto(lang).slice(min_cb, max_cb))


def slice_words(lang: str, min_cb: int = 0, max_cb: int = N_BANDS) -> list[str]:
    """频段切片（自动选档）：返回 cb ∈ [min_cb, max_cb) 的词。"""
    return _load_auto(lang).words(min_cb, max_cb)


def _load_auto(lang: str) -> BandList:
    """自动选档加载：small → middle → large，取第一个收录该语种的档；
    本地缺失时先按需下载。三档均未收录则抛 :class:`KeyError`。"""
    d = get_data_dir()
    for _ in range(2):  # 第二轮 = 触发下载后再找
        for t in TIERS:
            if (d / f"data_{t}" / f"{t}_{lang}.msgpack.gz").exists():
                return load(lang, t)
        _download([lang], data_dir=d)
    raise KeyError(f"{lang}: 三档均未收录该语种"
                   f"（可用 available_languages 查看各档语种表）")


def json_load(path: Path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))
