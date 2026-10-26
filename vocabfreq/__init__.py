"""vocabfreq — 自建多语言词频表（700 centibel 频段，wordfreq 风格 msgpack 格式）。

数据不随包分发：首次使用时自动从 Hugging Face（默认 hf-mirror.com 镜像）
按需下载并缓存到 ``~/.vocabfreq``（环境变量 ``VOCABFREQ_DATA`` /
``VOCABFREQ_ENDPOINT`` 或 :func:`set_data_dir` / :func:`download` 可覆盖）。

    >>> import vocabfreq
    >>> vocabfreq.download(["zh"])               # 预下载（缺省全部语种）
    >>> vocabfreq.word_frequency("的", "zh") > 0
    True
    >>> vocabfreq.top_n_list("en", 3)
    ['the', ...]
    >>> vocabfreq.load("en").slice(100, 200)     # 频段切片
"""

from .data import (
    N_BANDS,
    BandList,
    available_languages,
    get_data_dir,
    get_frequency_dict,
    iter_wordlist,
    load,
    set_data_dir,
    slice_words,
    top_n_list,
    word_frequency,
)
from .download import download

__version__ = "7.1.0"

__all__ = [
    "N_BANDS",
    "BandList",
    "available_languages",
    "download",
    "get_data_dir",
    "get_frequency_dict",
    "iter_wordlist",
    "load",
    "set_data_dir",
    "slice_words",
    "top_n_list",
    "word_frequency",
    "__version__",
]
