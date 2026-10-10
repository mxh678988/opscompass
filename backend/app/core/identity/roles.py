"""统一身份治理 · 角色模板（M3）。

职责（对应设计文档 3.5「角色模板」）：
1. 内核基础角色（超管/管理员/运营/只读）以模板形式登记，与 ``auth_service`` 单一数据源；
2. 插件可在清单 ``roles`` 段声明「推荐角色」（如舆情分析师），安装时由内核提示管理员
   一键创建 —— 插件不得自行写权限表；
3. 模板只描述「应授予哪些权限」，实际创建/补齐由 ``materialize_role`` 幂等落库；
4. 权限点尚未落地时按缺失清单告警，不静默授予，也不因缺失而整体失败。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.models.auth import Permission, Role

# 角色来源
SOURCE_CORE = "core"


class RoleTemplateError(ValueError):
    """角色模板非法（编码冲突、命名空间越界等）。"""


@dataclass(frozen=True)
class RoleTemplate:
    """角色模板定义。"""

    code: str
    name: str
    description: str = ""
    permission_codes: tuple[str, ...] = ()
    source: str = SOURCE_CORE
    is_builtin: bool = False

    @property
    def is_plugin(self) -> bool:
        return self.source != SOURCE_CORE

    @property
    def plugin_id(self) -> Optional[str]:
        if not self.is_plugin:
            return None
        return self.source.split(":", 1)[1]


@dataclass(frozen=True)
class MaterializePlan:
    """角色物化结果：新建与否、实授权限、缺失权限。"""

    role_code: str
    created: bool
    granted: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def _template_source(plugin_id: str) -> str:
    return f"plugin:{plugin_id}"


def load_core_templates() -> list[RoleTemplate]:
    """从内核角色定义派生基础角色模板。"""
    from app.services.auth_service import ROLE_DEFINITIONS  # 延迟导入，避免模块级反向依赖

    return [
        RoleTemplate(
            code=code,
            name=name,
            description=desc,
            permission_codes=tuple(sorted(codes)),
            is_builtin=bool(builtin),
        )
        for code, name, desc, codes, builtin in ROLE_DEFINITIONS
    ]


class RoleTemplateRegistry:
    """角色模板注册中心。"""

    def __init__(self, core_templates: Optional[Iterable[RoleTemplate]] = None) -> None:
        self._templates: dict[str, RoleTemplate] = {}
        for template in core_templates if core_templates is not None else load_core_templates():
            self.register(template, source=SOURCE_CORE)

    # ---- 查询 ----

    def __contains__(self, code: str) -> bool:
        return code in self._templates

    def __len__(self) -> int:
        return len(self._templates)

    def get(self, code: str) -> Optional[RoleTemplate]:
        return self._templates.get(code)

    def all(self) -> list[RoleTemplate]:
        return [t for _, t in sorted(self._templates.items())]

    def for_plugin(self, plugin_id: str) -> list[RoleTemplate]:
        source = _template_source(plugin_id)
        return [t for t in self.all() if t.source == source]

    def codes(self) -> list[str]:
        return sorted(self._templates)

    # ---- 注册 ----

    def register(self, template: RoleTemplate, *, source: Optional[str] = None) -> RoleTemplate:
        if not template.code:
            raise RoleTemplateError("角色模板编码不能为空")
        normalized = RoleTemplate(
            code=template.code,
            name=template.name or template.code,
            description=template.description,
            permission_codes=tuple(sorted(set(template.permission_codes or ()))),
            source=source or template.source,
            is_builtin=template.is_builtin,
        )
        existing = self._templates.get(normalized.code)
        if existing is not None:
            if existing.source != normalized.source:
                raise RoleTemplateError(
                    f"角色编码 {normalized.code} 已被 {existing.source} 占用，"
                    f"{normalized.source} 不得重复声明"
                )
            return existing
        self._templates[normalized.code] = normalized
        return normalized

    def register_plugin_roles(
        self, plugin_id: str, roles: Iterable[Any], *, namespace_prefix: str = ""
    ) -> list[RoleTemplate]:
        """注册插件推荐角色。角色编码须落在插件命名空间内（``<plugin>:``）。"""
        plugin_id = str(plugin_id or "").strip()
        if not plugin_id:
            raise RoleTemplateError("插件 ID 不能为空")
        prefix = str(namespace_prefix or "").strip()
        registered: list[RoleTemplate] = []
        for item in roles or []:
            template = self._normalize(item)
            if prefix and not template.code.startswith(prefix):
                raise RoleTemplateError(
                    f"插件 {plugin_id!r} 推荐角色 {template.code!r} 越出自身命名空间（须以 {prefix!r} 开头）"
                )
            registered.append(self.register(template, source=_template_source(plugin_id)))
        return registered

    @staticmethod
    def _normalize(item: Any) -> RoleTemplate:
        if isinstance(item, RoleTemplate):
            return item
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            return RoleTemplate(
                code=code,
                name=str(item.get("name") or code),
                description=str(item.get("description") or ""),
                permission_codes=tuple(item.get("permissions") or item.get("permission_codes") or ()),
                is_builtin=bool(item.get("is_builtin", False)),
            )
        raise RoleTemplateError(f"不支持的角色模板声明类型: {type(item).__name__}")

    def unregister_plugin(self, plugin_id: str) -> int:
        source = _template_source(plugin_id)
        victims = [c for c, t in self._templates.items() if t.source == source]
        for code in victims:
            self._templates.pop(code, None)
        return len(victims)

    # ---- 物化 ----

    def plan(self, code: str, available_codes: Iterable[str]) -> MaterializePlan:
        """预演：角色是否已存在、将授予哪些权限、哪些权限点尚未落地。"""
        template = self.get(code)
        if template is None:
            raise RoleTemplateError(f"角色模板未注册: {code}")
        available = set(available_codes)
        missing = tuple(sorted(c for c in template.permission_codes if c not in available))
        granted = tuple(sorted(c for c in template.permission_codes if c in available))
        return MaterializePlan(role_code=code, created=True, granted=granted, missing=missing)


def materialize_role(db, template: RoleTemplate, *, available_codes: Optional[Iterable[str]] = None) -> MaterializePlan:
    """幂等创建/补齐角色：已存在则只补差权限，不删减管理员的手工调整。"""
    if available_codes is None:
        available_codes = [p.code for p in db.query(Permission).all()]
    available = set(available_codes)

    role = db.query(Role).filter(Role.code == template.code).one_or_none()
    created = role is None
    if role is None:
        role = Role(
            code=template.code,
            name=template.name,
            description=template.description,
            is_builtin=template.is_builtin,
        )
        db.add(role)
        db.flush()

    owned = {p.code for p in (role.permissions or [])}
    wanted = list(template.permission_codes)
    missing = sorted(c for c in wanted if c not in available)
    to_grant = [c for c in wanted if c in available and c not in owned]
    if to_grant:
        rows = db.query(Permission).filter(Permission.code.in_(to_grant)).all()
        role.permissions = list(role.permissions or []) + list(rows)

    db.commit()
    db.refresh(role)
    granted = tuple(sorted(c for c in wanted if c in available))
    return MaterializePlan(role_code=role.code, created=created, granted=granted, missing=tuple(missing))
