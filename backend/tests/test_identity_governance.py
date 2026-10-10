"""OS 内核 · 统一身份治理（M3）测试。

覆盖：
- 权限点注册：三段式校验、命名空间越界、原子注册、异源冲突、sync_to_db 幂等
- 角色模板：注册/冲突、materialize_role 幂等创建与补差
- 数据权限：四级范围（all/tenant/org/self）、缺列显式失败、scope_from_user 推导
- 委派代理：创建/越权拦截/撤销/过期刷新/生效权限合并/离职交接
- 鉴权回调：make_permission_authorizer 装配语义
- SDK 门面：AuthFacade 未装配报 NotAvailableError、越界报 NamespaceViolation
- 运行时：PluginRuntime.sync_permissions 登记插件权限点与推荐角色

无外部依赖，直接执行：``pytest tests/test_identity_governance.py -v``。
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.identity import (
    DataScope,
    DataScopeError,
    DataScopeUnsupported,
    DelegationError,
    MAX_DELEGATION_DAYS,
    PermissionConflictError,
    PermissionFormatError,
    PermissionRegistry,
    RoleTemplate,
    RoleTemplateError,
    RoleTemplateRegistry,
    SCOPE_ALL,
    SCOPE_ORG,
    SCOPE_SELF,
    SCOPE_TENANT,
    active_delegations,
    apply_data_scope,
    build_data_scope_condition,
    create_delegation,
    delegated_permissions,
    effective_permissions,
    handover,
    make_permission_authorizer,
    materialize_role,
    refresh_status,
    revoke_delegation,
    scope_from_user,
    validate_permission_code,
    validate_plugin_permission_code,
)
from app.core.identity.delegation import own_permission_codes, own_role_codes
from app.core.plugin.registry import PluginRegistry
from app.core.plugin.runtime import PluginRuntime
from app.models.auth import AuditLog, Permission, Role, User, role_permission, user_role
from app.models.base import Base
from app.models.identity import CoreDelegation
from app.sdk.context import PluginNamespace, create_context
from app.sdk.exceptions import NamespaceViolation, NotAvailableError

IDENTITY_TABLES = [
    User.__table__,
    Role.__table__,
    Permission.__table__,
    user_role,
    role_permission,
    AuditLog.__table__,
    CoreDelegation.__table__,
]


@pytest.fixture()
def db():
    """独立内存库会话（仅建身份治理所需表）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine, tables=IDENTITY_TABLES)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_permission(db, code: str, module: str = "metric") -> Permission:
    p = Permission(code=code, name=code, module=module)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_role(db, code: str, permission_codes=()) -> Role:
    perms = []
    for c in permission_codes:
        p = db.query(Permission).filter(Permission.code == c).one_or_none()
        if p is None:
            p = _make_permission(db, c)
        perms.append(p)
    role = Role(code=code, name=code, description="", is_builtin=False)
    role.permissions = perms
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def _make_user(db, username: str, *, roles=(), is_superuser: bool = False) -> User:
    user = User(username=username, hashed_password="x", is_superuser=is_superuser)
    user.roles = list(roles)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ============================================================ 权限点注册


def test_permission_code_validation() -> None:
    assert validate_permission_code("core:view") == "core:view"
    assert validate_plugin_permission_code("sentiment:task:create") == "sentiment:task:create"

    with pytest.raises(PermissionFormatError):
        validate_plugin_permission_code("sentiment:create")  # 插件权限点必须三段及以上
    with pytest.raises(PermissionFormatError):
        validate_permission_code("UPPER:bad")  # 必须小写开头
    with pytest.raises(PermissionFormatError):
        validate_permission_code("core")  # 单段非法
    with pytest.raises(PermissionFormatError):
        validate_permission_code("")  # 空编码非法


def test_plugin_namespace_violation_rejected() -> None:
    reg = PermissionRegistry(core_defs=[])
    with pytest.raises(NamespaceViolation):
        reg.register_plugin(
            "sentiment", [{"code": "billing:invoice:create"}], namespace_prefix="sentiment:"
        )


def test_atomic_register_rolls_back() -> None:
    reg = PermissionRegistry(core_defs=[])
    before = set(reg.codes())
    # 批次内重复 → 整体回滚
    with pytest.raises(PermissionConflictError):
        reg.register_plugin(
            "p1",
            [{"code": "p1:a:read"}, {"code": "p1:a:read"}],
            namespace_prefix="p1:",
        )
    assert set(reg.codes()) == before
    # 非法格式 → 整体回滚
    with pytest.raises(PermissionFormatError):
        reg.register_plugin("p1", [{"code": "bad_code"}], namespace_prefix="p1:")
    assert set(reg.codes()) == before


def test_cross_source_conflict_and_idempotent() -> None:
    reg = PermissionRegistry(core_defs=["core:view"])
    reg.register_core(["p1:a:read"])  # 内核先占用三段码
    with pytest.raises(PermissionConflictError):
        reg.register_plugin("p1", [{"code": "p1:a:read"}], namespace_prefix="p1:")

    # 同源重复注册幂等
    reg.register_plugin("p1", [{"code": "p1:a:write"}], namespace_prefix="p1:")
    fresh = reg.register_plugin("p1", [{"code": "p1:a:write"}], namespace_prefix="p1:")
    assert fresh == []
    assert reg.stats()["plugins"] == ["p1"]
    assert reg.plugin_permissions("p1")[0].code == "p1:a:write"
    assert reg.unregister_plugin("p1") == 1


def test_sync_to_db_idempotent(db) -> None:
    reg = PermissionRegistry(core_defs=["core:view", "core:edit"])
    first = reg.sync_to_db(db)
    assert first["created"] == 2
    assert first["existing"] == 0

    second = reg.sync_to_db(db)
    assert second["created"] == 0
    assert second["existing"] == 2
    assert db.query(Permission).count() == 2


# ============================================================ 角色模板


def test_role_template_registry_register_and_conflict() -> None:
    tpl = RoleTemplate(code="operator", name="运营", permission_codes=("metric:read", "metric:write"))
    reg = RoleTemplateRegistry(core_templates=[tpl])
    assert "operator" in reg and len(reg) == 1

    # 同源重复注册幂等
    reg.register(tpl)
    assert len(reg) == 1

    # 异源冲突
    other = RoleTemplate(code="operator", name="运营", permission_codes=(), source="plugin:xxx")
    with pytest.raises(RoleTemplateError):
        reg.register(other)

    # 空编码拒绝
    with pytest.raises(RoleTemplateError):
        reg.register(RoleTemplate(code="", name="空"))


def test_materialize_role_creates_and_fills(db) -> None:
    _make_permission(db, "metric:read")
    _make_permission(db, "metric:write")
    _make_permission(db, "dashboard:view")

    tpl = RoleTemplate(
        code="operator", name="运营", permission_codes=("metric:read", "metric:write", "dashboard:view")
    )
    plan = materialize_role(db, tpl)
    assert plan.created is True
    assert plan.granted == ("dashboard:view", "metric:read", "metric:write")
    assert plan.missing == ()

    # 已存在 → 幂等不重建，只补差
    tpl2 = RoleTemplate(code="operator", name="运营", permission_codes=("metric:read",))
    plan2 = materialize_role(db, tpl2)
    assert plan2.created is False
    assert plan2.granted == ("metric:read",)
    assert db.query(Role).filter(Role.code == "operator").count() == 1

    # 缺失权限点不静默授予
    tpl3 = RoleTemplate(code="analyst", name="分析师", permission_codes=("not:exist:read", "metric:read"))
    plan3 = materialize_role(db, tpl3)
    assert plan3.created is True
    assert plan3.missing == ("not:exist:read",)
    role = db.query(Role).filter(Role.code == "analyst").one()
    assert {p.code for p in role.permissions} == {"metric:read"}


# ============================================================ 数据权限


def _model_with(name: str, **cols):
    """构造仿 ORM 假模型：列用 sqlalchemy Column，保证 ``==`` / ``in_`` 可用。"""
    return type(name, (), {"__name__": name, **{k: Column(Integer) for k in cols}})


def test_data_scope_all_is_global() -> None:
    Row = _model_with("Row", tenant_id=1, org_id=2, owner_id=3)
    assert build_data_scope_condition(Row, DataScope(level=SCOPE_ALL)) is None
    stmt = select()
    out = apply_data_scope(stmt, Row, DataScope(level=SCOPE_ALL))
    assert out.whereclause is None


def test_data_scope_tenant() -> None:
    Row = _model_with("Row", tenant_id=1, org_id=2, owner_id=3)
    cond = build_data_scope_condition(Row, DataScope(level=SCOPE_TENANT, tenant_id=7))
    assert cond is not None

    with pytest.raises(DataScopeError):
        build_data_scope_condition(Row, DataScope(level=SCOPE_TENANT, tenant_id=None))

    NoTenant = _model_with("NoTenant", owner_id=3)
    with pytest.raises(DataScopeUnsupported):
        build_data_scope_condition(NoTenant, DataScope(level=SCOPE_TENANT, tenant_id=7))


def test_data_scope_org() -> None:
    Row = _model_with("Row", tenant_id=1, org_id=2, owner_id=3)
    cond = build_data_scope_condition(Row, DataScope(level=SCOPE_ORG, org_ids=(2, 5), user_id=9))
    assert cond is not None

    with pytest.raises(DataScopeError):
        build_data_scope_condition(Row, DataScope(level=SCOPE_ORG, org_ids=(), user_id=None))

    NoOrg = _model_with("NoOrg", owner_id=3)
    with pytest.raises(DataScopeUnsupported):
        build_data_scope_condition(NoOrg, DataScope(level=SCOPE_ORG, org_ids=(1,), user_id=9))


def test_data_scope_self() -> None:
    Row = _model_with("Row", tenant_id=1, org_id=2, owner_id=3)
    cond = build_data_scope_condition(Row, DataScope(level=SCOPE_SELF, user_id=9))
    assert cond is not None

    with pytest.raises(DataScopeError):
        build_data_scope_condition(Row, DataScope(level=SCOPE_SELF, user_id=None))

    NoOwner = _model_with("NoOwner", tenant_id=1)
    with pytest.raises(DataScopeUnsupported):
        build_data_scope_condition(NoOwner, DataScope(level=SCOPE_SELF, user_id=9))


def test_scope_from_user_inference() -> None:
    # 用哑对象验证推导逻辑（不依赖数据库）
    class FakeUser:
        is_superuser = False
        id = 1
        tenant_id = 10
        org_ids = (2,)

    super_user = type("Super", (), {"is_superuser": True, "id": 1})()
    assert scope_from_user(super_user).is_global is True

    u = FakeUser()
    assert scope_from_user(u).level == SCOPE_TENANT
    assert scope_from_user(u, level=SCOPE_ORG).level == SCOPE_ORG
    with pytest.raises(DataScopeError):
        scope_from_user(u, level="bogus")

    tenantless = type("Plain", (), {"is_superuser": False, "id": 5, "tenant_id": None, "org_ids": ()})()
    assert scope_from_user(tenantless).level == SCOPE_SELF


# ============================================================ 委派与代理


def test_create_delegation_validation(db) -> None:
    operator_role = _make_role(db, "operator", ("metric:read",))
    alice = _make_user(db, "alice", roles=[operator_role])
    bob = _make_user(db, "bob")

    with pytest.raises(DelegationError):
        create_delegation(db, delegator=alice, delegatee=alice, role_codes=["operator"])  # 自我委派
    with pytest.raises(DelegationError):
        create_delegation(db, delegator=alice, delegatee=bob)  # 范围为空
    with pytest.raises(DelegationError):
        create_delegation(db, delegator=alice, delegatee=bob, role_codes=["operator"], end_at=None)  # 无期限
    with pytest.raises(DelegationError):
        create_delegation(
            db, delegator=alice, delegatee=bob, role_codes=["operator"],
            end_at=_utcnow() - timedelta(days=1),
        )  # 失效早于生效
    with pytest.raises(DelegationError):
        create_delegation(
            db, delegator=alice, delegatee=bob, role_codes=["operator"],
            end_at=_utcnow() + timedelta(days=MAX_DELEGATION_DAYS + 1),
        )  # 超 90 天
    with pytest.raises(DelegationError):
        create_delegation(db, delegator=alice, delegatee=bob, role_codes=["admin"])  # 越权角色
    with pytest.raises(DelegationError):
        create_delegation(db, delegator=alice, delegatee=bob, permission_codes=["metric:write"])  # 越权权限


def test_delegation_lifecycle_and_effective(db) -> None:
    operator_role = _make_role(db, "operator", ("metric:read",))
    alice = _make_user(db, "alice", roles=[operator_role])
    bob = _make_user(db, "bob")

    # 委派自身持有的角色与权限
    delegation = create_delegation(
        db,
        delegator=alice,
        delegatee=bob,
        role_codes=["operator"],
        permission_codes=["metric:read"],
        end_at=_utcnow() + timedelta(days=30),
    )
    assert delegation.status == "active"
    assert active_delegations(db, bob.id) == [delegation]

    # 生效权限 = 自身(空) ∪ 委派
    assert effective_permissions(db, bob) == ["metric:read"]

    # 撤销
    revoke_delegation(db, delegation, revoked_by=alice)
    assert delegation.status == "revoked"
    assert active_delegations(db, bob.id) == []
    with pytest.raises(DelegationError):
        revoke_delegation(db, delegation)  # 非 active 不可撤销

    # 过期刷新：先建未来到期的委派，再模拟时间流逝拨回过去
    d2 = create_delegation(
        db,
        delegator=alice,
        delegatee=bob,
        role_codes=["operator"],
        end_at=_utcnow() + timedelta(days=1),
    )
    d2.end_at = _utcnow() - timedelta(days=1)
    db.commit()
    assert refresh_status(db) == 1
    db.refresh(d2)
    assert d2.status == "expired"
    assert active_delegations(db, bob.id) == []


def test_delegated_permissions_expand_roles(db) -> None:
    _make_permission(db, "metric:read")
    _make_permission(db, "metric:write")
    _make_permission(db, "dashboard:view")
    metric_role = _make_role(db, "metric_reader", ("metric:read", "metric:write"))
    dashboard_role = _make_role(db, "dashboard_viewer", ("dashboard:view",))
    alice = _make_user(db, "alice", roles=[metric_role, dashboard_role])
    bob = _make_user(db, "bob")

    create_delegation(
        db, delegator=alice, delegatee=bob, role_codes=["dashboard_viewer"], end_at=_utcnow() + timedelta(days=7)
    )
    # 委派角色码展开为权限码
    assert delegated_permissions(db, bob.id) == {"dashboard:view"}
    assert effective_permissions(db, bob) == ["dashboard:view"]

    # 超管恒为全部内核权限点
    super_user = _make_user(db, "root", is_superuser=True)
    eff = effective_permissions(db, super_user)
    assert eff  # 超管返回全部内核权限点清单
    assert sorted(eff) == eff


def test_handover_transfers_and_revokes(db) -> None:
    operator_role = _make_role(db, "operator", ("metric:read",))
    alice = _make_user(db, "alice", roles=[operator_role])
    bob = _make_user(db, "bob")
    carol = _make_user(db, "carol")

    create_delegation(
        db, delegator=alice, delegatee=carol, role_codes=["operator"], end_at=_utcnow() + timedelta(days=7)
    )
    result = handover(db, from_user=alice, to_user=bob, reason="离职")
    assert result["transferred_roles"] == ["operator"]
    assert result["missing_roles"] == []
    assert result["revoked_delegations"] == 1

    db.refresh(bob)
    assert {r.code for r in bob.roles} == {"operator"}
    assert active_delegations(db, carol.id) == []


def test_handover_missing_role_reported(db) -> None:
    alice = _make_user(db, "alice")
    bob = _make_user(db, "bob")
    result = handover(db, from_user=alice, to_user=bob, role_codes=["ghost_role"])
    assert result["transferred_roles"] == []
    assert result["missing_roles"] == ["ghost_role"]


def test_handover_same_user_rejected(db) -> None:
    alice = _make_user(db, "alice")
    with pytest.raises(DelegationError):
        handover(db, from_user=alice, to_user=alice)


# ============================================================ 鉴权回调


def test_make_permission_authorizer() -> None:
    reg = PermissionRegistry(core_defs=[])
    reg.register_plugin("sentiment", [{"code": "sentiment:task:create"}], namespace_prefix="sentiment:")
    authorize = make_permission_authorizer(reg)

    class FakeUser:
        is_superuser = False
        roles = ()

    # 未注册权限点 → 拒绝（抛错，防插件使用未声明权限点）
    with pytest.raises(PermissionError):
        authorize("sentiment:task:delete", FakeUser())

    # user 为空（内核/后台任务）放行
    assert authorize("sentiment:task:create", None) is True

    # 超管放行
    super_user = type("Super", (), {"is_superuser": True, "roles": ()})()
    assert authorize("sentiment:task:create", super_user) is True

    # 无权限用户拒绝；on_denied 在构造时注入
    assert authorize("sentiment:task:create", FakeUser()) is False
    denied = []
    authorize_with_hook = make_permission_authorizer(reg, on_denied=lambda *a: denied.append(a))
    assert authorize_with_hook("sentiment:task:create", FakeUser()) is False
    assert len(denied) == 1

    # 有权限用户放行
    class OwnerUser:
        is_superuser = False
        roles = ()
        delegated_permission_codes = ["sentiment:task:create"]

    assert authorize("sentiment:task:create", OwnerUser()) is True


# ============================================================ SDK AuthFacade


def test_auth_facade_not_assembled() -> None:
    ctx = create_context(plugin_id="sentiment", namespace=PluginNamespace(permissions="sentiment:"))
    with pytest.raises(NotAvailableError) as e1:
        ctx.auth.require("sentiment:task:create")
    assert e1.value.planned_in == "M3 装配完成"

    with pytest.raises(NotAvailableError):
        ctx.auth.check(None, "sentiment:task:create")


def test_auth_facade_assembled_guards_namespace() -> None:
    reg = PermissionRegistry(core_defs=[])
    reg.register_plugin("sentiment", [{"code": "sentiment:task:create"}], namespace_prefix="sentiment:")
    authorize = make_permission_authorizer(reg)

    ctx = create_context(
        plugin_id="sentiment",
        namespace=PluginNamespace(permissions="sentiment:"),
        authorize_fn=authorize,
    )

    class FakeUser:
        is_superuser = False
        roles = ()
        delegated_permission_codes = ["sentiment:task:create"]

    with pytest.raises(NamespaceViolation):
        ctx.auth.require("billing:invoice:create", FakeUser())

    ctx.auth.require("sentiment:task:create", FakeUser())  # 不抛即通过
    assert ctx.auth.check(FakeUser(), "sentiment:task:create") is True

    class NoPermUser:
        is_superuser = False
        roles = ()

    with pytest.raises(PermissionError):
        ctx.auth.require("sentiment:task:create", NoPermUser())
    assert ctx.auth.check(NoPermUser(), "sentiment:task:create") is False


# ============================================================ PluginRuntime 装配


MANIFEST_M3 = """\
id: sentiment
name: 舆情插件
version: 0.1.0
kind: community
min_kernel_version: 0.11.0
entry: main:register
namespace:
  tables: os_sentiment_
  events: "sentiment."
  permissions: "sentiment:"
permissions:
  - code: sentiment:task:create
    name: 创建舆情任务
  - code: sentiment:task:delete
    name: 删除舆情任务
roles:
  - code: sentiment:analyst
    name: 舆情分析师
    permissions:
      - sentiment:task:create
events:
  publish:
    - sentiment.task.created
  subscribe:
    - core.metric.written
"""

MANIFEST_M3_BAD = """\
id: rogue
name: 越界插件
version: 0.1.0
kind: community
min_kernel_version: 0.11.0
entry: main:register
namespace:
  tables: os_rogue_
  events: "rogue."
  permissions: "rogue:"
permissions:
  - code: billing:invoice:create
    name: 越界权限点
"""


@pytest.fixture()
def m3_plugins_dir(tmp_path: Path) -> Path:
    root = tmp_path / "plugins"
    (root / "sentiment").mkdir(parents=True)
    (root / "sentiment" / "plugin.yaml").write_text(MANIFEST_M3, encoding="utf-8")
    (root / "rogue").mkdir(parents=True)
    (root / "rogue" / "plugin.yaml").write_text(MANIFEST_M3_BAD, encoding="utf-8")
    return root


def test_runtime_sync_permissions_registers_identity(m3_plugins_dir: Path) -> None:
    registry = PluginRegistry(m3_plugins_dir)
    perms = PermissionRegistry(core_defs=[])
    roles = RoleTemplateRegistry(core_templates=[])
    runtime = PluginRuntime(registry, permissions=perms, role_templates=roles)

    assert set(runtime.load_all()) == {"rogue", "sentiment"}  # 目录内插件全部登记（越界留待 sync 阶段拦截）
    runtime.sync_permissions("sentiment")

    assert "sentiment:task:create" in perms
    assert "sentiment:task:delete" in perms
    assert "sentiment:analyst" in roles
    assert roles.get("sentiment:analyst").permission_codes == ("sentiment:task:create",)

    # 越界插件登记被拒，且不影响已登记内容
    with pytest.raises(NamespaceViolation):
        runtime.sync_permissions("rogue")
    assert "billing:invoice:create" not in perms


def test_runtime_activate_wires_auth_facade(m3_plugins_dir: Path) -> None:
    registry = PluginRegistry(m3_plugins_dir)
    perms = PermissionRegistry(core_defs=[])
    runtime = PluginRuntime(registry, permissions=perms)
    runtime.load_all()

    ctx = runtime.activate("sentiment")
    # 鉴权门面已装配：不再抛 NotAvailableError
    class FakeUser:
        is_superuser = False
        roles = ()
        delegated_permission_codes = ["sentiment:task:create"]

    ctx.auth.require("sentiment:task:create", FakeUser())

    # 未装配授权的旧内核行为保持：不注入 permissions 时 auth 门面未装配
    registry2 = PluginRegistry(m3_plugins_dir)
    runtime2 = PluginRuntime(registry2)
    runtime2.load_all()
    ctx2 = runtime2.activate("sentiment")
    with pytest.raises(NotAvailableError):
        ctx2.auth.require("sentiment:task:create")


def test_runtime_uninstall_releases_identity(m3_plugins_dir: Path) -> None:
    registry = PluginRegistry(m3_plugins_dir)
    perms = PermissionRegistry(core_defs=[])
    roles = RoleTemplateRegistry(core_templates=[])
    runtime = PluginRuntime(registry, permissions=perms, role_templates=roles)
    runtime.load_all()

    runtime.activate("sentiment")
    assert "sentiment:task:create" in perms

    runtime.uninstall("sentiment")
    assert "sentiment:task:create" not in perms
    assert "sentiment:analyst" not in roles
