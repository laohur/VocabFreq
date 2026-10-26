"""数据下载：从 Hugging Face 数据集仓库获取词频文件。

数据不随 pip 包分发，运行时按需从数据集仓库
`vocabradar/VocabFreq <https://huggingface.co/datasets/vocabradar/VocabFreq>`_
下载。默认走国内镜像 **hf-mirror.com**（环境变量 ``VOCABFREQ_ENDPOINT``
可切换为 ``https://huggingface.co`` 等官方端点）。

所有文件按数据集自带的 ``files.json`` 校验清单逐文件核对字节数与
SHA-256；已存在且校验通过的文件自动跳过，因此可重复执行、增量补齐。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ID = "vocabradar/VocabFreq"
REVISION = "main"
DEFAULT_ENDPOINT = "https://hf-mirror.com"
ENV_ENDPOINT = "VOCABFREQ_ENDPOINT"
ENV_DATA = "VOCABFREQ_DATA"
DEFAULT_DATA_DIR = Path.home() / ".vocabfreq"


def get_endpoint(endpoint: str | None = None) -> str:
    """解析下载端点：参数 > 环境变量 ``VOCABFREQ_ENDPOINT`` > hf-mirror 默认。"""
    return (endpoint or os.environ.get(ENV_ENDPOINT) or DEFAULT_ENDPOINT).rstrip("/")


def resolve_url(path: str, endpoint: str | None = None) -> str:
    """数据集内相对路径 ``path`` 的下载 URL。"""
    return f"{get_endpoint(endpoint)}/datasets/{REPO_ID}/resolve/{REVISION}/{path}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(path: str, dest: Path, expect_bytes: int | None, expect_sha: str | None,
           endpoint: str) -> Path:
    """下载单个文件（原子写入）；已存在且校验通过时跳过。"""
    if dest.exists() and (
        expect_sha is None or _sha256_file(dest) == expect_sha
    ) and (
        expect_bytes is None or dest.stat().st_size == expect_bytes
    ):
        return dest
    if dest.exists():
        dest.unlink()  # 损坏或过期，重新下载
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(resolve_url(path, endpoint),
                                 headers={"User-Agent": "vocabfreq"})
    # 镜像站对匿名请求限流（429），指数退避重试
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
                h = hashlib.sha256()
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    h.update(chunk)
                    f.write(chunk)
            break
        except urllib.error.HTTPError as e:
            tmp.unlink(missing_ok=True)
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(
                    f"从 {endpoint} 下载 {path} 失败：HTTP {e.code}。请稍后重试，"
                    f"或设置 {ENV_ENDPOINT}=https://huggingface.co 切换官方端点。"
                ) from e
            time.sleep(2 ** attempt)
        except urllib.error.URLError as e:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"从 {endpoint} 下载 {path} 失败：{e}。请检查网络/代理，"
                f"或设置 {ENV_ENDPOINT}=https://huggingface.co 切换官方端点。"
            ) from e
    if expect_bytes is not None and tmp.stat().st_size != expect_bytes:
        size = tmp.stat().st_size
        tmp.unlink()
        raise IOError(f"{path}: 字节数不符（期望 {expect_bytes}，实际 {size}）")
    if expect_sha is not None and h.hexdigest() != expect_sha:
        tmp.unlink()
        raise IOError(f"{path}: SHA-256 校验失败")
    tmp.replace(dest)
    return dest


def _files_index(data_dir: Path, endpoint: str) -> dict[str, dict]:
    """获取校验清单 files.json，返回 ``{仓库相对路径: {bytes, sha256}}``。"""
    p = _fetch("files.json", data_dir / "files.json", None, None, endpoint)
    idx = json.loads(p.read_text(encoding="utf-8"))
    if idx.get("algorithm") != "sha256":
        raise IOError(f"files.json: 未知校验算法 {idx.get('algorithm')!r}")
    return {e["file"]: e for e in idx["files"]}


def download(langs: list[str] | None = None, data_dir: str | Path | None = None,
             endpoint: str | None = None) -> Path:
    """下载数据，返回数据目录。

    - ``langs=None``：全部语种（``data/`` 下所有文件）+ meta.json + README.md
    - ``langs=["en", "zh"]``：只下载这些语种的词表
    - ``langs=[]``：只要 meta.json + README.md
    - ``data_dir``：目标目录，缺省取 ``VOCABFREQ_DATA``，再缺省 ``~/.vocabfreq``
    """
    root = Path(data_dir) if data_dir else (
        Path(os.environ[ENV_DATA]) if os.environ.get(ENV_DATA) else DEFAULT_DATA_DIR
    )
    ep = get_endpoint(endpoint)
    index = _files_index(root, ep)

    wanted = ["meta.json", "README.md"]
    if langs is None:
        wanted += sorted(f for f in index if f.startswith("data/"))
    else:
        for code in langs:
            rel = f"data/small_{code}.msgpack.gz"
            if rel not in index:
                raise KeyError(f"{code}: 数据集中没有该语种（{rel} 不在 files.json）")
            wanted.append(rel)

    for rel in wanted:
        e = index.get(rel)
        _fetch(rel, root / rel, e and e.get("bytes"), e and e.get("sha256"), ep)
    return root
