"""依赖清单可复现性校验：逐条 pin 校验版本是否真实存在于 PyPI。

背景：backend/requirements.txt 中的 pin 若指向不存在的版本，镜像构建
（Dockerfile.backend 的 pip install -r）会直接失败，导致基线不可复现。
本脚本在提交 / 升版前做一次静态校验，把这类问题拦在构建之前。

只读网络查询：不安装、不下载、不修改任何环境。
退出码：0 全部有效；1 存在无效版本；2 清单文件缺失。
网络不可用时相关条目记为 UNKNOWN，不计入失败。

用法：
    python scripts/verify_requirements.py
    python scripts/verify_requirements.py --file backend/requirements.txt
    python scripts/verify_requirements.py --offline   # 仅解析清单结构，不联网
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DEFAULT_FILE = os.path.join("backend", "requirements.txt")
PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?\s*==\s*([^\s;#]+)")
PYPI_URL = "https://pypi.org/pypi/{name}/json"
TIMEOUT_SECONDS = 25


def parse_requirements(path: str) -> list[tuple[int, str | None, str | None, str]]:
    """返回 [(行号, 包名, 版本, 原始行)]；非 pin 行包名/版本为 None。"""
    items: list[tuple[int, str | None, str | None, str]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = PIN_RE.match(line)
            if match:
                items.append((lineno, match.group(1), match.group(3), line))
            else:
                items.append((lineno, None, None, line))
    return items


def fetch_releases(name: str) -> tuple[set[str] | None, str | None, str | None]:
    """返回 (版本集合, PyPI 最新版, 错误信息)。"""
    try:
        with urllib.request.urlopen(PYPI_URL.format(name=name), timeout=TIMEOUT_SECONDS) as resp:
            data = json.load(resp)
        return set(data["releases"].keys()), data["info"]["version"], None
    except Exception as exc:  # noqa: BLE001 网络/JSON 异常统一降级为 UNKNOWN
        return None, None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="依赖清单 pin 版本可复现性校验")
    parser.add_argument("--file", default=DEFAULT_FILE, help="requirements 文件路径")
    parser.add_argument("--offline", action="store_true", help="不联网，仅校验清单结构")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"[ERROR] 清单文件不存在：{args.file}")
        return 2

    items = parse_requirements(args.file)
    names = sorted({name for _, name, _, _ in items if name})

    releases: dict[str, tuple[set[str] | None, str | None, str | None]] = {}
    if args.offline:
        releases = {name: (None, None, "offline") for name in names}
    else:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for name, payload in zip(names, pool.map(fetch_releases, names)):
                releases[name] = payload

    print("=" * 74)
    print(f"依赖清单可复现性校验：{args.file}")
    print("=" * 74)

    ok = invalid = unknown = 0
    invalid_rows: list[str] = []
    for lineno, name, version, raw in items:
        if name is None:
            print(f"L{lineno:<4}[非 pin 行] {raw}")
            continue
        available, latest, error = releases[name]
        if available is None:
            print(f"L{lineno:<4}[UNKNOWN] {name}=={version}（未能校验：{error}）")
            unknown += 1
        elif version in available:
            print(f"L{lineno:<4}[OK]      {name}=={version}")
            ok += 1
        else:
            print(f"L{lineno:<4}[无效]    {name}=={version}  <- PyPI 不存在该版本，最新为 {latest}")
            invalid_rows.append(f"L{lineno} {name}=={version} (最新 {latest})")
            invalid += 1

    print("-" * 74)
    print(f"有效 {ok} / 无效 {invalid} / 未确认 {unknown}")
    if invalid_rows:
        print("需修正：")
        for row in invalid_rows:
            print(f"  - {row}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
