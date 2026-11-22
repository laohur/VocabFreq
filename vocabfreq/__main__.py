"""命令行入口：``python -m vocabfreq [langs ...]`` 或安装后 ``vocabfreq [langs ...]``。

不带参数下载全部语种；带语种代码只下载对应词表。文件已存在且校验通过时跳过。
"""
from __future__ import annotations

import argparse

from .download import download


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="vocabfreq",
        description="下载 VocabFreq 词频数据（端点自适应：默认镜像 hf-mirror.com，"
                    "不可达时自动回退 huggingface.co；环境变量 HF_ENDPOINT / "
                    "VOCABFREQ_DATA 可覆盖端点与目录）",
    )
    p.add_argument("langs", nargs="*",
                   help="语种代码（如 en zh）；缺省下载全部语种")
    p.add_argument("--data-dir", help="数据目录（缺省 ~/.vocabfreq）")
    p.add_argument("--endpoint", help="偏好 HF 端点（缺省 https://hf-mirror.com，"
                                      "不可达时自动回退 https://huggingface.co）")
    a = p.parse_args(argv)
    root = download(a.langs or None, a.data_dir, a.endpoint)
    print(f"数据目录: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
