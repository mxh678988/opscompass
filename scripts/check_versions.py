"""五源版本一致性校验（跨平台，与 scripts/ci.ps1 第 1 项等价）。

版本唯一来源：``backend/app/core/config.py`` 的 ``APP_VERSION``。
以下五处必须完全一致：

  1) backend/app/core/config.py    APP_VERSION
  2) frontend/package.json         version
  3) docs/openapi.json             info.version
  4) docs/changelog.md             首个 "## [x.y.z]" 标题
  5) docker-compose.prod.yml       OPS_VERSION:-x.y.z 默认镜像版本（须存在且唯一）

设计说明：ci.ps1 面向 Windows + Docker 的本地全流程校验；本脚本只做其中的
版本一致性一项，零第三方依赖、跨平台，供 GitHub Actions 复用。两者判定口径
保持一致，升版时两处同时生效，无需额外维护。

退出码：0 五源一致；1 存在不一致 / 解析失败 / 缺失。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_PY = BASE_DIR / "backend" / "app" / "core" / "config.py"
PACKAGE_JSON = BASE_DIR / "frontend" / "package.json"
OPENAPI_JSON = BASE_DIR / "docs" / "openapi.json"
CHANGELOG_MD = BASE_DIR / "docs" / "changelog.md"
PROD_COMPOSE = BASE_DIR / "docker-compose.prod.yml"

SEMVER = r"\d+\.\d+\.\d+"


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def read_config_version() -> str:
    if not CONFIG_PY.is_file():
        fail(f"未找到 {CONFIG_PY.relative_to(BASE_DIR)}")
    match = re.search(r'APP_VERSION\s*:\s*str\s*=\s*"([^"]+)"', CONFIG_PY.read_text(encoding="utf-8"))
    if not match:
        fail("config.py 未找到 APP_VERSION 定义")
    return match.group(1)


def read_package_version() -> str:
    if not PACKAGE_JSON.is_file():
        fail(f"未找到 {PACKAGE_JSON.relative_to(BASE_DIR)}")
    return str(json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"])


def read_openapi_version() -> str:
    if not OPENAPI_JSON.is_file():
        fail(f"未找到 {OPENAPI_JSON.relative_to(BASE_DIR)}")
    return str(json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))["info"]["version"])


def read_changelog_version() -> str:
    if not CHANGELOG_MD.is_file():
        fail(f"未找到 {CHANGELOG_MD.relative_to(BASE_DIR)}")
    text = CHANGELOG_MD.read_text(encoding="utf-8")
    match = re.search(rf"^##\s*\[({SEMVER})\]", text, re.MULTILINE)
    if not match:
        fail("docs/changelog.md 未找到 '## [x.y.z]' 形式的版本标题")
    return match.group(1)


def read_prod_compose_version() -> str:
    """生产编排的默认镜像版本；文件不存在时返回 n/a（不计入一致性判定）。"""
    if not PROD_COMPOSE.is_file():
        return "n/a"
    hits = sorted(set(re.findall(rf"OPS_VERSION:-({SEMVER})", PROD_COMPOSE.read_text(encoding="utf-8"))))
    if not hits:
        fail("docker-compose.prod.yml 未找到 OPS_VERSION 默认版本号")
    if len(hits) > 1:
        fail(f"docker-compose.prod.yml 存在多个 OPS_VERSION 默认值：{', '.join(hits)}")
    return hits[0]


def main() -> int:
    config_ver = read_config_version()
    package_ver = read_package_version()
    openapi_ver = read_openapi_version()
    changelog_ver = read_changelog_version()
    prod_ver = read_prod_compose_version()

    print("版本一致性校验（五源）")
    print(f"  1) backend/app/core/config.py  APP_VERSION : {config_ver}")
    print(f"  2) frontend/package.json        version   : {package_ver}")
    print(f"  3) docs/openapi.json            info      : {openapi_ver}")
    print(f"  4) docs/changelog.md            首条标题  : {changelog_ver}")
    print(f"  5) docker-compose.prod.yml      OPS_VERSION: {prod_ver}")

    versions = {config_ver, package_ver, openapi_ver, changelog_ver}
    if prod_ver != "n/a":
        versions.add(prod_ver)

    if len(versions) != 1:
        fail(
            "版本不一致 -> "
            f"config={config_ver} / package={package_ver} / openapi={openapi_ver} / "
            f"changelog={changelog_ver} / prod-compose={prod_ver}"
        )

    print(f"[PASS] 五源一致：{config_ver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
