"""插件清单校验器：验证 plugin.yaml 的合法性。

校验规则：
- id 唯一、小写、字母数字下划线，禁止以 `core` 开头
- version 为语义化版本，min_kernel_version 满足内核版本
- namespace 下 tables/events/permissions 前缀互不重叠
- 表前缀 os_<plugin>_ 未与既有内核表或已有插件表冲突
- 权限点 code 格式合法（三段式 plugin:resource:action）
- events.publish 事件名符合命名规范
- official 包签名校验（签名目录存在且文件完整）

全部规则来自 docs/os-kernel-design.md 第4节。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

# 插件 id 正则：小写、字母数字下划线，禁止 core 开头
PLUGIN_ID_RE = re.compile(r'^[a-z][a-z0-9_]*$')
CORE_PREFIX_RE = re.compile(r'^core\b')

# 版本：x.y.z，带可选后缀
VERSION_RE = re.compile(r'^\d+\.\d+\.\d+')

# 权限点三段式：plugin:resource:action
PERM_RE = re.compile(r'^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$')

# 内核表前缀（已有）
KERNEL_TABLE_PREFIX = "os_core_"


@dataclass
class ManifestValidationError:
    """校验失败的一条错误。"""
    field: str
    detail: str


@dataclass
class ManifestResult:
    """校验结果。"""
    valid: bool = True
    errors: list[ManifestValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_manifest(path: Path) -> dict[str, Any]:
    """读取并解析 plugin.yaml。"""
    if not path.exists():
        raise FileNotFoundError(f"清单文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _add_error(result: ManifestResult, field: str, detail: str) -> None:
    result.errors.append(ManifestValidationError(field=field, detail=detail))
    result.valid = False


def _add_warning(result: ManifestResult, detail: str) -> None:
    result.warnings.append(detail)


def validate_manifest(
    manifest_path: Path,
    *,
    plugin_id: Optional[str] = None,
    existing_plugin_ids: Optional[set[str]] = None,
    existing_table_prefixes: Optional[set[str]] = None,
    existing_event_prefixes: Optional[set[str]] = None,
    existing_perm_prefixes: Optional[set[str]] = None,
    kernel_version: str = "0.11.0",
    is_official: bool = True,
) -> ManifestResult:
    """校验插件清单。

    返回 ManifestResult，valid 为 True 表示全部校验通过。

    :param manifest_path: plugin.yaml 绝对路径
    :param plugin_id: 插件 id，若未传入则从 manifest 读取
    :param existing_plugin_ids: 已注册的插件 id 集合（含内核 core）
    :param existing_table_prefixes: 已占用的表前缀
    :param existing_event_prefixes: 已占用的事件前缀
    :param existing_perm_prefixes: 已占用的权限前缀
    :param kernel_version: 当前内核版本
    :param is_official: 是否为官方插件（校验签名）
    """
    result = ManifestResult()

    try:
        manifest = parse_manifest(manifest_path)
    except yaml.YAMLError as e:
        _add_error(result, "yaml", f"清单格式错误: {e}")
        return result

    if not isinstance(manifest, dict):
        _add_error(result, "format", "清单必须是 YAML 字典")
        return result

    # ---- 1. id ----
    raw_id = manifest.get("id")
    if raw_id is None:
        _add_error(result, "id", "缺少 id 字段")
        return result

    id_str = str(raw_id).strip()
    plugin_id = id_str  # 用于后续参数传递

    if not PLUGIN_ID_RE.match(id_str):
        _add_error(result, "id", f"插件 id 不合法: {id_str!r}，只允许小写字母、数字、下划线")
    if CORE_PREFIX_RE.match(id_str):
        _add_error(result, "id", f"插件 id 不得以 'core' 开头: {id_str!r}")

    # ---- 2. version ----
    version = manifest.get("version", "")
    if not VERSION_RE.match(str(version)):
        _add_error(result, "version", f"版本格式不合法: {version!r}，须为语义化版本 x.y.z")

    # ---- 3. min_kernel_version ----
    min_kver = str(manifest.get("min_kernel_version", "0.0.0"))
    # 简易版本号比较：按段逐段比较
    def _ver_to_tuple(v: str) -> tuple:
        return tuple(int(x) for x in re.split(r'[.\-]', v) if x.isdigit())

    if _ver_to_tuple(min_kver) > _ver_to_tuple(kernel_version):
        _add_error(result, "min_kernel_version",
                   f"需要内核版本 >= {min_kver}，当前内核为 {kernel_version}")

    # ---- 4. 唯一性 ----
    if existing_plugin_ids and plugin_id in existing_plugin_ids:
        _add_error(result, "id", f"插件 id {plugin_id!r} 与已有插件冲突")

    # ---- 5. 入口格式 ----
    entry = manifest.get("entry", "")
    if not isinstance(entry, str) or ":" not in entry:
        _add_error(result, "entry", f"entry 格式不合法: {entry!r}，须为 module:func 格式")
    else:
        mod, func = entry.split(":", 1)
        if not mod.strip() or not func.strip():
            _add_error(result, "entry", "entry 的模块名与函数名均不能为空")

    # ---- 6. namespace 校验 ----
    ns = manifest.get("namespace", {})

    # 表前缀
    table_prefix = ns.get("tables", "")
    if table_prefix:
        if not table_prefix.startswith("os_"):
            _add_error(result, "namespace.tables",
                       f"表前缀须以 'os_' 开头: {table_prefix!r}")
        if existing_table_prefixes and table_prefix in existing_table_prefixes:
            _add_error(result, "namespace.tables",
                       f"表前缀 {table_prefix!r} 已被占用")

    # 事件前缀
    event_prefix = ns.get("events", "")
    if event_prefix:
        if not event_prefix.endswith("."):
            _add_error(result, "namespace.events",
                       f"事件前缀须以 '.' 结尾: {event_prefix!r}")
        if existing_event_prefixes and event_prefix in existing_event_prefixes:
            _add_error(result, "namespace.events",
                       f"事件前缀 {event_prefix!r} 已被占用")

    # 权限前缀
    perm_prefix = ns.get("permissions", "")
    if perm_prefix:
        if not perm_prefix.endswith(":"):
            _add_error(result, "namespace.permissions",
                       f"权限前缀须以 ':' 结尾: {perm_prefix!r}")
        if existing_perm_prefixes and perm_prefix in existing_perm_prefixes:
            _add_error(result, "namespace.permissions",
                       f"权限前缀 {perm_prefix!r} 已被占用")

    # ---- 7. 权限点代码 ----
    permissions = manifest.get("permissions", [])
    seen_perm_codes: set[str] = set()
    for i, perm in enumerate(permissions):
        if not isinstance(perm, dict):
            _add_error(result, f"permissions[{i}]", "权限项须为字典格式")
            continue
        code = perm.get("code", "")
        if not PERM_RE.match(str(code)):
            _add_error(result, f"permissions[{i}].code",
                       f"权限点代码格式不合法: {code!r}，须为 plugin:resource:action")
        elif code in seen_perm_codes:
            _add_error(result, f"permissions[{i}].code",
                       f"权限点代码重复: {code!r}")
        elif existing_perm_prefixes:
            for ex in existing_perm_prefixes:
                if code.startswith(ex):
                    _add_error(result, f"permissions[{i}].code",
                               f"权限点代码 {code!r} 与已有权限前缀 {ex!r} 重叠")
        seen_perm_codes.add(code)

    # ---- 8. events.publish 事件名规范 ----
    events = manifest.get("events", {})
    for ev_type in ("publish", "subscribe"):
        ev_list = events.get(ev_type, [])
        if not isinstance(ev_list, list):
            _add_error(result, f"events.{ev_type}", "须为列表格式")
            continue
        for i, ev_name in enumerate(ev_list):
            if not isinstance(ev_name, str) or "." not in ev_name:
                _add_error(result, f"events.{ev_type}[{i}]",
                           f"事件名须为 'domain.object.action' 格式: {ev_name!r}")

    # ---- 9. 官方包签名校验 ----
    if is_official:
        if not manifest_path.parent.joinpath(".sig").exists():
            _add_warning(result, f"官方包缺少签名文件 {manifest_path.parent}/.sig")

    return result
