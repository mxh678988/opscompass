"""统一身份治理 · 权限点注册中心（M3）。

职责（对应设计文档 3.5「权限点注册」）：
1. 内核权限点（既有 ``PERMISSION_DEFINITIONS``）与插件声明的权限点在此汇合，
   全库只有一份权威清单，避免两处维护导致编码漂移；
2. 插件权限点强制 ``<plugin>:<resource>:<action>`` 三段式，且必须落在插件清单
   声明的 ``namespace.permissions`` 前缀内，越界即拒绝（与 M2 的命名空间隔离口径一致）；
3. 注册具备原子性：任一条目非法，本次注册整体回滚，不留下半套权限点；
4. 提供幂等落库 ``sync_to_db``，把权威清单合并进 ``oc_permission``，
   **只新增不改写**，保证既有 45 个权限点编码不变（兼容红线）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.sdk.exceptions import NamespaceViolation

# 权限点来源
SOURCE_CORE = "core"

# 权限点编码规范：内核既有为 <module>:<action>（2 段），插件强制三段式 <plugin>:<resource>:<action>
PERMISSION_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)+$")
PLUGIN_PERMISSION_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*){2,}$")


class PermissionFormatError(ValueError):
    """权限点编码格式非法。"""


class PermissionConflictError(ValueError):
    """权限点编码与其它来源（内核或别的插件）冲突。"""


@dataclass(frozen=True)
class PermissionDef:
    """权限点定义（权威清单条目）。"""

    code: str
    name: str
    module: str = ""
    description: str = ""
    source: str = SOURCE_CORE

    @property
    def is_plugin(self) -> bool:
        return self.source != SOURCE_CORE

    @property
    def plugin_id(self) -> Optional[str]:
        """插件权限点返回 plugin_id，内核权限点返回 None。"""
        if not self.is_plugin:
            return None
        return self.source.split(":", 1)[1]


def plugin_source(plugin_id: str) -> str:
    return f"plugin:{plugin_id}"


def validate_permission_code(code: Any) -> str:
    """校验并归一化权限点编码。

    内核既有权限点为 ``<module>:<action>``（2 段），插件权限点强制
    ``<plugin>:<resource>:<action>``（≥3 段，由 ``validate_plugin_permission_code`` 把关）。
    """
    text = str(code or "").strip()
    if not PERMISSION_CODE_PATTERN.match(text):
        raise PermissionFormatError(
            f"权限点编码非法: {code!r}，须为 <module>:<action> 或 "
            f"<plugin>:<resource>:<action>（小写字母/数字/下划线）"
        )
    return text


def validate_plugin_permission_code(code: Any) -> str:
    """插件权限点编码校验：强制 ``<plugin>:<resource>:<action>`` 三段及以上。"""
    text = validate_permission_code(code)
    if not PLUGIN_PERMISSION_CODE_PATTERN.match(text):
        raise PermissionFormatError(
            f"插件权限点编码非法: {code!r}，须为 <plugin>:<resource>:<action>（≥3 段）"
        )
    return text


def _normalize(item: Any, *, source: str) -> PermissionDef:
    """把 str / dict / PermissionDef 归一化为 PermissionDef。"""
    if isinstance(item, PermissionDef):
        code = validate_permission_code(item.code)
        return PermissionDef(
            code=code,
            name=item.name or code,
            module=item.module or code.split(":", 1)[0],
            description=item.description,
            source=source,
        )
    if isinstance(item, str):
        code = validate_permission_code(item)
        return PermissionDef(code=code, name=code, module=code.split(":", 1)[0], source=source)
    if isinstance(item, dict):
        code = validate_permission_code(item.get("code"))
        name = str(item.get("name") or code)
        module = str(item.get("module") or code.split(":", 1)[0])
        description = str(item.get("description") or "")
        return PermissionDef(
            code=code, name=name, module=module, description=description, source=source
        )
    raise PermissionFormatError(f"不支持的权限点声明类型: {type(item).__name__}")


def load_core_permissions() -> list[PermissionDef]:
    """读取内核既有权限点定义（单一数据源在 ``app.services.auth_service``）。"""
    from app.services.auth_service import PERMISSION_DEFINITIONS  # 延迟导入，避免模块级反向依赖

    return [
        PermissionDef(code=code, name=name, module=module, description=desc)
        for code, name, module, desc in PERMISSION_DEFINITIONS
    ]


class PermissionRegistry:
    """权限点注册中心：内核 + 插件的权限点权威清单。"""

    def __init__(self, core_defs: Optional[Iterable[Any]] = None) -> None:
        self._defs: dict[str, PermissionDef] = {}
        if core_defs is None:
            core_defs = load_core_permissions()
        for item in core_defs:
            self.register_core([item])

    # ---- 查询 ----

    def __contains__(self, code: str) -> bool:
        return code in self._defs

    def __len__(self) -> int:
        return len(self._defs)

    def get(self, code: str) -> Optional[PermissionDef]:
        return self._defs.get(code)

    def codes(self, source: Optional[str] = None) -> list[str]:
        return sorted(c for c, d in self._defs.items() if source is None or d.source == source)

    def defs(self, source: Optional[str] = None) -> list[PermissionDef]:
        return [d for _, d in sorted(self._defs.items()) if source is None or d.source == source]

    def plugin_permissions(self, plugin_id: str) -> list[PermissionDef]:
        return self.defs(source=plugin_source(plugin_id))

    def modules(self) -> list[str]:
        return sorted({d.module for d in self._defs.values() if d.module})

    def stats(self) -> dict:
        plugin_ids = sorted({d.plugin_id for d in self._defs.values() if d.is_plugin})
        return {
            "total": len(self._defs),
            "core": sum(1 for d in self._defs.values() if not d.is_plugin),
            "plugin": sum(1 for d in self._defs.values() if d.is_plugin),
            "plugins": plugin_ids,
            "modules": len(self.modules()),
        }

    # ---- 注册 ----

    def register(self, items: Iterable[Any], *, source: str) -> list[PermissionDef]:
        """原子注册：全部条目合法才提交，否则抛错且注册中心保持原状。"""
        candidates: list[PermissionDef] = [_normalize(i, source=source) for i in items]

        # 1) 批次内自查重
        seen: set[str] = set()
        for cand in candidates:
            if cand.code in seen:
                raise PermissionConflictError(f"同批次权限点编码重复: {cand.code}")
            seen.add(cand.code)

        # 2) 与既有清单比对（同来源重复 → 幂等跳过；异来源 → 冲突）
        fresh: list[PermissionDef] = []
        for cand in candidates:
            existing = self._defs.get(cand.code)
            if existing is None:
                fresh.append(cand)
            elif existing.source != cand.source:
                raise PermissionConflictError(
                    f"权限点编码 {cand.code} 已被 {existing.source} 占用，{cand.source} 不得重复声明"
                )

        for cand in fresh:
            self._defs[cand.code] = cand
        return fresh

    def register_core(self, items: Iterable[Any]) -> list[PermissionDef]:
        return self.register(items, source=SOURCE_CORE)

    def register_plugin(
        self, plugin_id: str, items: Iterable[Any], *, namespace_prefix: str = ""
    ) -> list[PermissionDef]:
        """注册插件声明的权限点。

        ``namespace_prefix`` 非空时，全部权限点必须以其开头（插件不得声明他人命名空间）。
        """
        plugin_id = str(plugin_id or "").strip()
        if not plugin_id:
            raise PermissionFormatError("插件 ID 不能为空")
        candidates = list(items or [])
        prefix = str(namespace_prefix or "").strip()
        for item in candidates:
            raw = item.get("code") if isinstance(item, dict) else getattr(item, "code", item)
            code = validate_plugin_permission_code(raw)
            if prefix and not code.startswith(prefix):
                raise NamespaceViolation(
                    plugin_id, "权限点", code, f"{prefix}*"
                )
        return self.register(candidates, source=plugin_source(plugin_id))

    def unregister_plugin(self, plugin_id: str) -> int:
        """注销插件权限点（插件卸载时调用），返回移除条数。"""
        source = plugin_source(plugin_id)
        victims = [c for c, d in self._defs.items() if d.source == source]
        for code in victims:
            self._defs.pop(code, None)
        return len(victims)

    # ---- 落库 ----

    def sync_to_db(self, db) -> dict:
        """把权威清单幂等合并进 ``oc_permission``（只新增，不改写既有行）。"""
        from app.models.auth import Permission  # 局部导入，避免核心层与模型层循环

        existing = {p.code for p in db.query(Permission).all()}
        created = 0
        for definition in self.defs():
            if definition.code in existing:
                continue
            db.add(
                Permission(
                    code=definition.code,
                    name=definition.name,
                    module=definition.module,
                    description=definition.description,
                )
            )
            created += 1
        if created:
            db.commit()
        return {"created": created, "existing": len(existing), "total": len(self._defs)}
