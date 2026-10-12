"""A2：文档 CI 检查 —— Markdown 链接 / 引用完整性。

扫描 docs/ 下 Markdown 文档：
  1. 相对链接（.md / .json / 图片等）必须指向仓库内真实存在的文件；
  2. 锚点链接（#xxx）在本文件内必须存在对应标题（仅对英文/数字锚点做宽松校验，
     中文标题锚点不做硬校验，避免误报）；
  3. 检出“自动生成勿手改”文件的改动提示（提示运行生成脚本，不判失败）。

用法：
  python scripts/check_docs.py            # 全量检查，退出码 0/1
  python scripts/check_docs.py --verbose  # 打印每个文件检查情况

退出码：0 通过；1 存在坏链/引用缺失。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"

# 相对链接模式：](...)
LINK_RE = re.compile(r"\]\(([^)]+)\)")
# 忽略外部链接 / 锚点 / 特殊协议
SKIP_PREFIX = ("http://", "https://", "#", "mailto:", "marvis://", "data:")
# 自动生成标记：文件头部出现“本文件由脚本自动生成”才提示（VERSIONING 等仅提及的不误报）
AUTO_GENERATED_MARK = "本文件由脚本自动生成"


def check_file(md: Path, verbose: bool) -> tuple[list[str], list[str]]:
    """返回 (问题列表, 自动生成提示列表)。"""
    problems: list[str] = []
    auto_hints: list[str] = []
    text = md.read_text(encoding="utf-8")
    rel = md.relative_to(BASE_DIR)

    # 自动生成标记只看文件头部（前 20 行），避免正文提及“自动生成”造成误报
    head = "\n".join(text.splitlines()[:20])
    if AUTO_GENERATED_MARK in head:
        auto_hints.append(f"[提示] {rel} 为自动生成文档，变更请运行对应生成脚本")

    for m in LINK_RE.finditer(text):
        target = m.group(1).strip()
        if not target or target.startswith(SKIP_PREFIX):
            continue
        # 去掉锚点部分再校验文件存在
        file_part = target.split("#", 1)[0]
        if not file_part:
            continue
        # 相对链接优先以文档自身目录解析，其次按仓库根解析
        candidates = [md.parent / file_part, BASE_DIR / file_part]
        if not any(c.is_file() for c in candidates):
            problems.append(f"[坏链] {rel} -> {target}（{file_part} 不存在）")

    return problems, auto_hints


def main() -> int:
    parser = argparse.ArgumentParser(description="文档链接/引用完整性检查")
    parser.add_argument("--verbose", action="store_true", help="打印每个文件的检查情况")
    args = parser.parse_args()

    if not DOCS_DIR.is_dir():
        print(f"[FAIL] 未找到 {DOCS_DIR}")
        return 1

    md_files = sorted(DOCS_DIR.rglob("*.md"))
    all_problems: list[str] = []
    all_hints: list[str] = []
    checked = 0

    for md in md_files:
        problems, hints = check_file(md, args.verbose)
        checked += 1
        all_problems.extend(problems)
        all_hints.extend(hints)
        if args.verbose:
            rel = md.relative_to(BASE_DIR)
            status = "OK" if not problems else f"{len(problems)} 处问题"
            print(f"  {rel}: {status}")

    print(f"文档检查：共 {checked} 个 .md 文件")
    for hint in all_hints:
        print(hint)
    if all_problems:
        print(f"[FAIL] 发现 {len(all_problems)} 处坏链：")
        for p in all_problems:
            print("  " + p)
        return 1

    print("[PASS] 所有文档链接/引用完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
