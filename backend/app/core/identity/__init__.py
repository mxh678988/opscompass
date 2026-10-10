"""OS 内核 · 统一身份治理（M3）。

对外能力（对应设计文档 3.5）：
- 权限点注册：``PermissionRegistry``（内核 + 插件权限点归口，越界/冲突拒绝）
- 角色模板：``RoleTemplateRegistry`` / ``materialize_role``（插件推荐角色一键创建）
- 数据权限：``DataScope`` / ``apply_data_scope``（行级隔离统一注入）
- 委派与代理：``create_delegation`` / ``effective_permissions`` / ``handover``（全程留痕）
- 鉴权回调：``make_permission_authorizer``（装配进插件 SDK 的 ``auth`` 门面）
"""

from app.core.identity.data_scope import (
    DATA_SCOPES,
    SCOPE_ALL,
    SCOPE_ORG,
    SCOPE_SELF,
    SCOPE_TENANT,
    DataScope,
    DataScopeError,
    DataScopeUnsupported,
    apply_data_scope,
    build_data_scope_condition,
    scope_from_user,
)
from app.core.identity.delegation import (
    MAX_DELEGATION_DAYS,
    DelegationError,
    active_delegations,
    create_delegation,
    delegated_permissions,
    effective_permissions,
    handover,
    make_permission_authorizer,
    refresh_status,
    revoke_delegation,
)
from app.core.identity.permissions import (
    PERMISSION_CODE_PATTERN,
    PLUGIN_PERMISSION_CODE_PATTERN,
    SOURCE_CORE,
    PermissionConflictError,
    PermissionDef,
    PermissionFormatError,
    PermissionRegistry,
    load_core_permissions,
    plugin_source,
    validate_permission_code,
    validate_plugin_permission_code,
)
from app.core.identity.roles import (
    MaterializePlan,
    RoleTemplate,
    RoleTemplateError,
    RoleTemplateRegistry,
    load_core_templates,
    materialize_role,
)

__all__ = [
    # 权限点
    "PermissionRegistry",
    "PermissionDef",
    "PermissionConflictError",
    "PermissionFormatError",
    "PERMISSION_CODE_PATTERN",
    "PLUGIN_PERMISSION_CODE_PATTERN",
    "SOURCE_CORE",
    "load_core_permissions",
    "plugin_source",
    "validate_permission_code",
    "validate_plugin_permission_code",
    # 角色模板
    "RoleTemplateRegistry",
    "RoleTemplate",
    "RoleTemplateError",
    "MaterializePlan",
    "load_core_templates",
    "materialize_role",
    # 数据权限
    "DataScope",
    "DataScopeError",
    "DataScopeUnsupported",
    "DATA_SCOPES",
    "SCOPE_ALL",
    "SCOPE_TENANT",
    "SCOPE_ORG",
    "SCOPE_SELF",
    "scope_from_user",
    "build_data_scope_condition",
    "apply_data_scope",
    # 委派代理
    "create_delegation",
    "revoke_delegation",
    "refresh_status",
    "active_delegations",
    "delegated_permissions",
    "effective_permissions",
    "handover",
    "make_permission_authorizer",
    "MAX_DELEGATION_DAYS",
    "DelegationError",
]
