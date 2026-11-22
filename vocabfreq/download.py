"""数据下载：从 Hugging Face 数据集仓库获取词频文件。

数据不随 pip 包分发，运行时按需从数据集仓库
`vocabradar/VocabFreq <https://huggingface.co/datasets/vocabradar/VocabFreq>`_
下载。端点自适应：优先走国内镜像 **hf-mirror.com**（遵从 HF 惯例，环境变量
``HF_ENDPOINT`` 可指定偏好端点），不可达时自动回退官方
``https://huggingface.co``，两者互为备份。

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
# 三档词表：数据集内目录 data_<tier>/<tier>_<code>.msgpack.gz
TIERS = ("small", "middle", "large")
DEFAULT_ENDPOINT = "https://hf-mirror.com"
# 候选端点：交替尝试，任一失败立即换下一个
ENDPOINTS = (DEFAULT_ENDPOINT, "https://huggingface.co")
# 记忆本次进程内最近一次成功的端点，后续文件直接从它开始
_PREFERRED: str | None = None
ENV_ENDPOINT = "HF_ENDPOINT"  # HF 生态惯例变量（huggingface_hub 同款）
ENV_DATA = "VOCABFREQ_DATA"
DEFAULT_DATA_DIR = Path.home() / ".vocabfreq"


def rel_path(tier: str, code: str) -> str:
    """语种 ``code`` 在档位 ``tier`` 下的数据集相对路径。"""
    return f"data_{tier}/{tier}_{code}.msgpack.gz"


def get_endpoint(endpoint: str | None = None) -> str:
    """解析偏好下载端点：参数 > 环境变量 ``HF_ENDPOINT`` > 上次成功的端点 > hf-mirror 默认。"""
    return (endpoint or os.environ.get(ENV_ENDPOINT) or _PREFERRED
            or DEFAULT_ENDPOINT).rstrip("/")


def _candidates(preferred: str) -> list[str]:
    """尝试顺序：偏好端点优先，其余候选端点兜底。"""
    return [preferred, *(e for e in ENDPOINTS if e != preferred)]


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
           endpoint: str | None = None) -> Path:
    """下载单个文件（原子写入）；已存在且校验通过时跳过。

    端点自适应：在候选端点（参数 > ``HF_ENDPOINT`` > 默认镜像、官方）之间
    **交替尝试**——任一端点失败立即换下一个，不重试到底；每个端点各自
    指数退避。任一端点成功后，后续文件优先从它开始。
    """
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
    eps = _candidates(get_endpoint(endpoint))
    errors: list[str] = []
    fails: dict[str, int] = dict.fromkeys(eps, 0)
    ok = False
    for _round in range(4):
        for ep in eps:
            if fails[ep]:  # 该端点之前失败过，重试前指数退避
                time.sleep(min(2 ** (fails[ep] - 1), 8))
            req = urllib.request.Request(resolve_url(path, ep),
                                         headers={"User-Agent": "vocabfreq"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
                    h = hashlib.sha256()
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        h.update(chunk)
                        f.write(chunk)
                ok = True
                if ep in ENDPOINTS:
                    global _PREFERRED
                    _PREFERRED = ep
                break
            except urllib.error.HTTPError as e:
                tmp.unlink(missing_ok=True)
                if e.code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(
                        f"从 {ep} 下载 {path} 失败：HTTP {e.code}。请检查语种代码/路径，"
                        f"或设置 {ENV_ENDPOINT}=https://huggingface.co 切换官方端点。"
                    ) from e
                fails[ep] += 1
                errors.append(f"{ep}: HTTP {e.code}")  # 限流/5xx，交替换端点+退避
            except urllib.error.URLError as e:
                tmp.unlink(missing_ok=True)
                fails[ep] += 1
                errors.append(f"{ep}: {getattr(e, 'reason', e)}")  # 网络不通，立即换端点
        if ok:
            break
    else:
        raise RuntimeError(
            f"下载 {path} 失败（已交替尝试端点：{'、'.join(eps)}）：{'；'.join(errors)}。"
            f"请检查网络/代理，或设置 {ENV_ENDPOINT} 指定可达端点。"
        )
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

    - ``langs=None``：全部语种（三个档位 ``data_small/middle/large`` 下所有文件）
      + meta.json + README.md
    - ``langs=["en", "zh"]``：只下载这些语种（在三档中存在的全部词表）
    - ``langs=[]``：只要 meta.json + README.md
    - ``data_dir``：目标目录，缺省取 ``VOCABFREQ_DATA``，再缺省 ``~/.vocabfreq``
    """
    root = Path(data_dir) if data_dir else (
        Path(os.environ[ENV_DATA]) if os.environ.get(ENV_DATA) else DEFAULT_DATA_DIR
    )
    index = _files_index(root, endpoint)

    wanted = ["meta.json", "README.md"]
    if langs is None:
        wanted += sorted(f for f in index
                         if f.startswith(tuple(f"data_{t}/" for t in TIERS)))
    else:
        for code in langs:
            rels = [rel_path(t, code) for t in TIERS if rel_path(t, code) in index]
            if not rels:
                raise KeyError(f"{code}: 数据集中没有任何档位收录该语种")
            wanted.extend(rels)

    for rel in wanted:
        e = index.get(rel)
        _fetch(rel, root / rel, e and e.get("bytes"), e and e.get("sha256"), endpoint)
    return root
