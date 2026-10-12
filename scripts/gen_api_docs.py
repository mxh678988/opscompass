"""A1：从 OpenAPI 快照自动生成 API 参考文档（docs/api-reference.md）。

与 scripts/check_openapi.py 配套：
  - check_openapi.py 保证 docs/openapi.json 与代码契约一致；
  - 本脚本把 docs/openapi.json 渲染成可读的 Markdown 参考文档，非手写。

用法：
  python scripts/gen_api_docs.py            # 生成 docs/api-reference.md
  python scripts/gen_api_docs.py --check    # 仅校验文档已是最新（CI 用）

生成规则：
  - 按 tag 分组输出端点表 + 参数表 + 响应说明；
  - 文件头标注生成时间与源快照版本，提醒"自动生成勿手改"。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT = BASE_DIR / "docs" / "openapi.json"
OUTPUT = BASE_DIR / "docs" / "api-reference.md"

# 需要展示的请求体 / 参数说明优先级：以描述为准，无描述时回退字段名
METHOD_STYLE = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
}


def _schema_ref(schema: dict) -> str:
    """把 $ref 转成可读的组件名。"""
    ref = schema.get("$ref", "")
    return ref.rsplit("/", 1)[-1] if ref else schema.get("type", "object")


def _fmt_params(params: list[dict] | None) -> str:
    """渲染路径 / 查询 / 请求头参数表格。"""
    if not params:
        return "无"
    rows = []
    for p in params:
        required = "是" if p.get("required") else "否"
        rows.append(
            f"| `{p.get('name')}` | {p.get('in')} | {required} | "
            f"{_schema_ref(p.get('schema', {}))} | {p.get('description', '')} |"
        )
    return "| 参数 | 位置 | 必填 | 类型 | 说明 |\n|---|---|---|---|---|\n" + "\n".join(rows)


def _fmt_request_body(body: dict | None) -> str:
    """渲染请求体摘要。"""
    if not body:
        return "无"
    content = body.get("content", {})
    if not content:
        return "无"
    schema = list(content.values())[0].get("schema", {})
    return f"`{_schema_ref(schema)}`（JSON 对象）"


def _fmt_responses(responses: dict) -> str:
    """渲染响应摘要：状态码 + 说明 + 引用组件。"""
    if not responses:
        return "无"
    rows = []
    for code in sorted(responses, key=lambda c: int(c) if c.isdigit() else 999):
        resp = responses[code]
        desc = resp.get("description", "")
        schema = resp.get("content", {}).get("application/json", {}).get("schema")
        detail = f"`{_schema_ref(schema)}`" if schema else ""
        rows.append(f"| {code} | {desc} | {detail} |")
    return "| 状态码 | 说明 | 响应体 |\n|---|---|---|\n" + "\n".join(rows)


def render(spec: dict, with_timestamp: bool = True) -> str:
    paths = spec.get("paths", {})
    info = spec.get("info", {})
    version = info.get("version", "?")
    title = info.get("title", "API 参考")

    # tag -> [(method, path, item)]
    tags: dict[str, list[tuple[str, str, dict]]] = {}
    for path, item in paths.items():
        for method, op in item.items():
            if method not in METHOD_STYLE:
                continue
            for tag in op.get("tags", ["未分类"]):
                tags.setdefault(tag, []).append((method, path, op))

    stamp = (
        datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
        if with_timestamp
        else "生成时间戳（--check 忽略）"
    )
    lines = [
        f"# {title}（自动生成）",
        "",
        f"> 适用产品：运营智脑（让数据自动做出最优决策）",
        f">",
        f"> 源快照：`docs/openapi.json`（v{version}）｜ 生成时间：{stamp}",
        f"> 统一前缀：`/api/v1` ｜ 在线文档：`http://localhost:8000/docs`（Swagger UI）",
        f"> **本文件由脚本自动生成，禁止手改**；接口变更后运行 `python scripts/gen_api_docs.py`。",
        "",
        f"共 {len(paths)} 条路径。",
        "",
    ]

    for tag in sorted(tags):
        lines.append(f"## {tag}")
        lines.append("")
        lines.append("| 方法 | 路径 | 说明 |")
        lines.append("|---|---|---|")
        for method, path, op in sorted(tags[tag], key=lambda x: x[1]):
            lines.append(f"| {METHOD_STYLE[method]} | `{path}` | {op.get('summary', op.get('description', ''))} |")
        lines.append("")
        for method, path, op in sorted(tags[tag], key=lambda x: x[1]):
            lines.append(f"### {METHOD_STYLE[method]} `{path}`")
            lines.append("")
            if op.get("description"):
                lines.append(op["description"].strip())
                lines.append("")
            lines.append("**请求参数**")
            lines.append("")
            lines.append(_fmt_params(op.get("parameters")))
            lines.append("")
            lines.append("**请求体**")
            lines.append("")
            lines.append(_fmt_request_body(op.get("requestBody")))
            lines.append("")
            lines.append("**响应**")
            lines.append("")
            lines.append(_fmt_responses(op.get("responses", {})))
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAPI 快照 -> Markdown API 参考")
    parser.add_argument("--check", action="store_true", help="仅校验文档与快照一致，不写文件")
    args = parser.parse_args()

    if not SNAPSHOT.is_file():
        print(f"[FAIL] 未找到快照 {SNAPSHOT.relative_to(BASE_DIR)}")
        return 1

    spec = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rendered = render(spec)
    rendered_no_ts = render(spec, with_timestamp=False)

    if args.check:
        if OUTPUT.is_file():
            on_disk = OUTPUT.read_text(encoding="utf-8")
            # 剥离磁盘文件的时间戳行，与无时间戳渲染比较
            on_disk_no_ts = "\n".join(
                line if not line.startswith("> 源快照：") else
                f"> 源快照：`docs/openapi.json`（v{spec['info']['version']}）｜ 生成时间：生成时间戳（--check 忽略）"
                for line in on_disk.splitlines()
            )
            if on_disk_no_ts.rstrip("\n") == rendered_no_ts.rstrip("\n"):
                print(f"[PASS] docs/api-reference.md 与快照一致")
                return 0
        print(f"[FAIL] docs/api-reference.md 过期，请运行 python scripts/gen_api_docs.py")
        return 1

    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"[OK] 已生成 {OUTPUT.relative_to(BASE_DIR)}（v{spec['info']['version']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
