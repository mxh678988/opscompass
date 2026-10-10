"""统一身份治理 · 数据权限（行级隔离，M3）。

职责（对应设计文档 3.5「数据权限」）：
- 行级可见范围统一由内核注入过滤条件，插件与业务模块**不得自行拼接** where 条件；
- 范围四级：``all``（全局）/ ``tenant``（本租户）/ ``org``（本组织 + 本人）/ ``self``（仅本人）；
- 默认列名约定 ``tenant_id`` / ``org_id`` / ``owner_id``，可按模型覆盖；
- 失败策略为「显式失败」：模型缺少所需列或范围参数不全时抛错，
  绝不放行全表（避免静默越权）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from sqlalchemy import and_, or_

# 数据权限范围
SCOPE_ALL = "all"
SCOPE_TENANT = "tenant"
SCOPE_ORG = "org"
SCOPE_SELF = "self"
DATA_SCOPES = (SCOPE_ALL, SCOPE_TENANT, SCOPE_ORG, SCOPE_SELF)

# 默认列名约定
DEFAULT_COLUMNS: dict[str, str] = {
    "tenant": "tenant_id",
    "org": "org_id",
    "owner": "owner_id",
}


class DataScopeError(ValueError):
    """数据权限范围参数非法（缺 tenant_id / user_id 等）。"""


class DataScopeUnsupported(RuntimeError):
    """目标模型缺少该范围所需列，无法安全注入过滤条件。"""


@dataclass(frozen=True)
class DataScope:
    """一次查询的行级可见范围。"""

    level: str = SCOPE_SELF
    tenant_id: Optional[int] = None
    org_ids: tuple[int, ...] = ()
    user_id: Optional[int] = None

    @property
    def is_global(self) -> bool:
        return self.level == SCOPE_ALL

    def describe(self) -> str:
        if self.level == SCOPE_ALL:
            return "全局可见"
        if self.level == SCOPE_TENANT:
            return f"本租户（tenant_id={self.tenant_id}）"
        if self.level == SCOPE_ORG:
            return f"本组织（org_ids={list(self.org_ids)}）+ 本人（user_id={self.user_id}）"
        return f"仅本人（user_id={self.user_id}）"


def scope_from_user(
    user: Any,
    *,
    level: Optional[str] = None,
    tenant_id: Optional[int] = None,
    org_ids: Iterable[int] = (),
    user_id: Optional[int] = None,
) -> DataScope:
    """由用户对象推导数据权限范围；超管恒为全局。

    ``level`` 显式给出时以其为准（用于按角色配置的范围），否则按用户属性推断：
    有租户 → tenant，有组织 → org，否则 self。
    """
    if user is not None and getattr(user, "is_superuser", False):
        return DataScope(level=SCOPE_ALL)

    pid = getattr(user, "id", None) if user is not None else None
    resolved_user_id = pid if user_id is None else user_id
    resolved_tenant = getattr(user, "tenant_id", None) if user is not None else None
    if tenant_id is not None:
        resolved_tenant = tenant_id
    resolved_orgs = tuple(org_ids) if org_ids else tuple(getattr(user, "org_ids", None) or ())

    if level is None:
        if resolved_tenant is not None:
            level = SCOPE_TENANT
        elif resolved_orgs:
            level = SCOPE_ORG
        else:
            level = SCOPE_SELF
    if level not in DATA_SCOPES:
        raise DataScopeError(f"未知的数据权限范围: {level!r}")

    return DataScope(
        level=level,
        tenant_id=resolved_tenant,
        org_ids=resolved_orgs,
        user_id=resolved_user_id,
    )


def _column(model: Any, name: str) -> Any:
    """取模型列，不存在返回 None。"""
    return getattr(model, name, None) if name else None


def build_data_scope_condition(
    model: Any,
    scope: Optional[DataScope],
    *,
    columns: Optional[dict[str, str]] = None,
) -> Any:
    """构造行级过滤条件；全局范围返回 None。"""
    if scope is None or scope.is_global:
        return None

    cols = dict(DEFAULT_COLUMNS)
    cols.update(columns or {})

    tenant_col = _column(model, cols["tenant"])
    org_col = _column(model, cols["org"])
    owner_col = _column(model, cols["owner"])

    if scope.level == SCOPE_TENANT:
        if tenant_col is None:
            raise DataScopeUnsupported(
                f"{model.__name__} 缺少列 {cols['tenant']!r}，无法按租户隔离"
            )
        if scope.tenant_id is None:
            raise DataScopeError("租户范围缺少 tenant_id，拒绝放行")
        return tenant_col == scope.tenant_id

    if scope.level == SCOPE_ORG:
        conditions = []
        if scope.org_ids:
            if org_col is None:
                raise DataScopeUnsupported(
                    f"{model.__name__} 缺少列 {cols['org']!r}，无法按组织隔离"
                )
            conditions.append(org_col.in_(list(scope.org_ids)))
        if scope.user_id is not None:
            if owner_col is None:
                raise DataScopeUnsupported(
                    f"{model.__name__} 缺少列 {cols['owner']!r}，无法按所属人隔离"
                )
            conditions.append(owner_col == scope.user_id)
        if not conditions:
            raise DataScopeError("组织范围缺少 org_ids 与 user_id，拒绝放行")
        return or_(*conditions)

    if scope.level == SCOPE_SELF:
        if owner_col is None:
            raise DataScopeUnsupported(
                f"{model.__name__} 缺少列 {cols['owner']!r}，无法按所属人隔离"
            )
        if scope.user_id is None:
            raise DataScopeError("本人范围缺少 user_id，拒绝放行")
        return owner_col == scope.user_id

    raise DataScopeError(f"未知的数据权限范围: {scope.level!r}")


def apply_data_scope(
    stmt: Any,
    model: Any,
    scope: Optional[DataScope],
    *,
    columns: Optional[dict[str, str]] = None,
) -> Any:
    """把行级过滤条件注入查询语句（插件与业务模块的唯一入口）。"""
    condition = build_data_scope_condition(model, scope, columns=columns)
    if condition is None:
        return stmt
    return stmt.where(condition)
