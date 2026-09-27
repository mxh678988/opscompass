"""认证与权限业务服务：初始化种子数据、登录校验、用户/角色装配。"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    collect_permission_codes,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.auth import AuditLog, Permission, Role, User
from app.models.tenant import Tenant
from app.schemas.auth import RoleOut, UserOut

logger = logging.getLogger(__name__)

# ------------------------------------------------------ 权限点定义
# (code, name, module, description)
PERMISSION_DEFINITIONS: list[tuple[str, str, str, str]] = [
    ("system:view", "查看系统信息", "system", "查看系统健康与安全概览"),
    ("tenant:view", "查看租户", "tenant", "查看租户列表"),
    ("tenant:create", "新建租户", "tenant", "创建租户"),
    ("tenant:update", "编辑租户", "tenant", "修改租户信息"),
    ("tenant:delete", "删除租户", "tenant", "删除租户"),
    ("datasource:view", "查看数据源", "datasource", "查看数据源列表与详情"),
    ("datasource:create", "新建数据源", "datasource", "创建数据源"),
    ("datasource:update", "编辑数据源", "datasource", "修改数据源配置"),
    ("datasource:delete", "删除数据源", "datasource", "删除数据源"),
    ("datasource:sync", "同步数据源", "datasource", "触发数据源同步"),
    ("metric:view", "查看指标", "metric", "查看指标与指标值"),
    ("metric:create", "新建指标", "metric", "创建指标"),
    ("metric:update", "编辑指标", "metric", "修改指标与口径版本"),
    ("metric:delete", "删除指标", "metric", "删除指标"),
    ("ingest:view", "查看采集任务", "ingest", "查看数据采集任务"),
    ("ingest:run", "执行采集任务", "ingest", "触发数据采集"),
    ("ai:view", "查看 AI 能力", "ai", "查看 AI 分析与洞察"),
    ("ai:analyze", "触发 AI 分析", "ai", "发起 AI 分析任务"),
    ("ai:config", "配置 AI", "ai", "修改 AI 模型与策略配置"),
    ("ops:view", "查看运营资产", "ops", "查看站点/页面/商品等运营资产"),
    ("ops:create", "新建运营资产", "ops", "创建运营资产"),
    ("ops:update", "编辑运营资产", "ops", "修改运营资产"),
    ("ops:delete", "删除运营资产", "ops", "删除运营资产"),
    ("user:view", "查看用户", "user", "查看用户列表与详情"),
    ("user:create", "新建用户", "user", "创建用户"),
    ("user:update", "编辑用户", "user", "修改用户信息与角色"),
    ("user:delete", "删除用户", "user", "删除用户"),
    ("user:reset_password", "重置密码", "user", "重置他人密码"),
    ("role:view", "查看角色", "role", "查看角色与权限"),
    ("role:create", "新建角色", "role", "创建角色"),
    ("role:update", "编辑角色", "role", "修改角色与权限绑定"),
    ("role:delete", "删除角色", "role", "删除角色"),
    ("marketing:view", "查看营销渠道", "marketing", "查看渠道账号、投放任务与渠道事件"),
    ("marketing:create", "新增营销渠道", "marketing", "新增渠道账号与投放任务"),
    ("marketing:update", "编辑营销渠道", "marketing", "修改渠道配置与任务内容"),
    ("marketing:authorize", "渠道授权", "marketing", "写入渠道凭据、授权/撤销与数据同步"),
    ("marketing:delete", "删除营销渠道", "marketing", "删除渠道账号与投放任务"),
    ("collect:view", "查看采集任务", "collect", "查看采集调度任务与运行记录"),
    ("collect:create", "新建采集任务", "collect", "创建采集任务与调度计划"),
    ("collect:update", "编辑采集任务", "collect", "修改采集配置与启停调度"),
    ("collect:run", "执行采集任务", "collect", "手动执行采集任务"),
    ("collect:delete", "删除采集任务", "collect", "删除采集任务与运行记录"),
    ("audit:view", "查看审计日志", "audit", "查询安全审计日志"),
    ("audit:export", "导出审计日志", "audit", "导出安全审计日志"),
    ("model:view", "查看模型中心", "model", "查看模型中心概览与硬件检测"),
    ("model:config", "配置模型", "model", "配置 AI 模型端点、连通性自检与一键接入"),
    ("learning:view", "查看学习进化", "learning", "查看学习进化总览、反馈、策略权重、案例与实验"),
    ("learning:manage", "管理学习进化", "learning", "登记反馈、重算权重、维护案例与 A/B 对照实验"),
    ("digital_human:view", "查看数字人", "digital_human", "查看数字人形象库、音色库、生成项目与工作流模板"),
    ("digital_human:manage", "管理数字人", "digital_human", "维护形象与音色、生成口播稿、执行一键生成与工作流"),
    ("commercial:view", "查看商业化", "commercial", "查看套餐定价、授权证书、订单与用量配额"),
    ("commercial:manage", "管理商业化", "commercial", "维护套餐、签发/激活/续期/吊销授权、下单支付与登记用量"),
]

ALL_PERMISSION_CODES: list[str] = [c for c, _, _, _ in PERMISSION_DEFINITIONS]

_VIEW_ONLY = [c for c in ALL_PERMISSION_CODES if c.endswith(":view")]
_OPERATOR_CODES = set(_VIEW_ONLY) | {
    "datasource:create",
    "datasource:update",
    "datasource:sync",
    "metric:create",
    "metric:update",
    "ingest:run",
    "ai:analyze",
    "ops:create",
    "ops:update",
    "marketing:create",
    "marketing:update",
    "marketing:authorize",
    "collect:run",
    "digital_human:manage",
}
_ADMIN_CODES = set(ALL_PERMISSION_CODES) - {"role:delete", "user:delete", "audit:export"}

# ------------------------------------------------------ 角色定义
# (code, name, description, permission_codes, is_builtin)
ROLE_DEFINITIONS: list[tuple[str, str, str, Iterable[str], bool]] = [
    ("super_admin", "超级管理员", "拥有全部权限，含用户/角色管理与审计导出", ALL_PERMISSION_CODES, True),
    (
        "admin",
        "管理员",
        "日常管理账号：除删除角色/用户与审计导出外的全部权限",
        sorted(_ADMIN_CODES),
        True,
    ),
    (
        "operator",
        "运营人员",
        "可查看并维护数据源、指标与运营资产，不可管理用户与角色",
        sorted(_OPERATOR_CODES),
        True,
    ),
    ("viewer", "只读用户", "仅可查看业务数据，不可进行任何写操作", sorted(set(_VIEW_ONLY)), True),
]


# ------------------------------------------------------ 装配转换
def role_to_out(role: Role) -> RoleOut:
    """角色 -> 响应模型。"""
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_builtin=bool(role.is_builtin),
        permissions=sorted(p.code for p in (role.permissions or [])),
        created_at=role.created_at,
    )


def user_to_out(user: User) -> UserOut:
    """用户 -> 响应模型（含角色码）。"""
    return UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        is_active=bool(user.is_active),
        is_superuser=bool(user.is_superuser),
        roles=sorted(user.role_codes),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def user_permission_codes(user: User) -> list[str]:
    """用户经由角色获得的权限码（超管返回全部）。"""
    if user.is_superuser:
        return sorted(ALL_PERMISSION_CODES)
    return sorted(collect_permission_codes(user))


# ------------------------------------------------------ 登录
def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.execute(select(User).where(User.username == username)).scalars().first()


def authenticate(db: Session, username: str, password: str) -> tuple[Optional[User], str]:
    """校验账号密码。

    返回 (user, reason)。user 为 None 时 reason 说明失败原因。
    """
    user = get_user_by_username(db, username)
    if user is None:
        return None, "用户名或密码错误"
    if not user.is_active:
        return None, "账号已被停用，请联系管理员"

    now = datetime.now(timezone.utc)
    if user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            remain = int((locked_until - now).total_seconds() // 60) + 1
            return None, f"账号已被锁定，请 {remain} 分钟后重试"

    if not verify_password(password, user.hashed_password):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= settings.SECURITY_LOGIN_MAX_FAILURES:
            user.locked_until = now + timedelta(minutes=settings.SECURITY_LOGIN_LOCK_MINUTES)
            user.failed_login_count = 0
            db.commit()
            return (
                None,
                f"连续失败次数过多，账号已锁定 {settings.SECURITY_LOGIN_LOCK_MINUTES} 分钟",
            )
        db.commit()
        remain = settings.SECURITY_LOGIN_MAX_FAILURES - user.failed_login_count
        return None, f"用户名或密码错误（剩余尝试次数 {max(remain, 0)}）"

    # 登录成功：清零失败计数并记录登录时间
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    db.refresh(user)
    return user, "ok"


def change_password(db: Session, user: User, old_password: str, new_password: str) -> str:
    """修改密码，返回错误信息；成功返回空串。"""
    if not verify_password(old_password, user.hashed_password):
        return "原密码不正确"
    err = validate_password_strength(new_password)
    if err:
        return err
    user.hashed_password = hash_password(new_password)
    db.commit()
    return ""


def reset_password(db: Session, user: User, new_password: str) -> str:
    """管理员重置密码，返回错误信息；成功返回空串。"""
    err = validate_password_strength(new_password)
    if err:
        return err
    user.hashed_password = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return ""


# ------------------------------------------------------ 角色绑定
def get_roles_by_codes(db: Session, codes: Iterable[str]) -> tuple[list[Role], list[str]]:
    """按角色码查询角色，返回 (命中的角色, 未找到的编码)。"""
    codes = [c for c in codes or [] if c]
    if not codes:
        return [], []
    rows = db.execute(select(Role).where(Role.code.in_(codes))).scalars().all()
    found = {r.code: r for r in rows}
    missing = [c for c in codes if c not in found]
    return list(found.values()), missing


def set_permissions(db: Session, role: Role, codes: Iterable[str]) -> list[str]:
    """覆盖式设置角色权限，返回未找到的权限码。"""
    codes = [c for c in codes or [] if c]
    perms: list[Permission] = []
    missing: list[str] = []
    if codes:
        rows = db.execute(select(Permission).where(Permission.code.in_(codes))).scalars().all()
        found = {p.code: p for p in rows}
        missing = [c for c in codes if c not in found]
        perms = list(found.values())
    role.permissions = perms
    db.commit()
    db.refresh(role)
    return missing


# ------------------------------------------------------ 初始化种子
def ensure_seed(db: Session) -> dict:
    """幂等初始化：权限点、内置角色、默认管理员与默认租户。"""
    created = {"permissions": 0, "roles": 0, "admin": False, "tenant": None}

    # 1) 权限点
    existing_perms = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
    for code, name, module, desc in PERMISSION_DEFINITIONS:
        if code not in existing_perms:
            perm = Permission(code=code, name=name, module=module, description=desc)
            db.add(perm)
            db.flush()
            existing_perms[code] = perm
            created["permissions"] += 1
    db.commit()

    # 2) 内置角色（补充缺失权限，不覆盖自定义调整）
    existing_roles = {r.code: r for r in db.execute(select(Role)).scalars().all()}
    for code, name, desc, codes, builtin in ROLE_DEFINITIONS:
        role = existing_roles.get(code)
        if role is None:
            role = Role(code=code, name=name, description=desc, is_builtin=builtin)
            db.add(role)
            db.flush()
            existing_roles[code] = role
            created["roles"] += 1
        perms = [
            existing_perms[c]
            for c in codes
            if c in existing_perms
        ]
        owned = {p.code for p in (role.permissions or [])}
        missing = [p for p in perms if p.code not in owned]
        if missing:
            role.permissions = list(role.permissions or []) + missing
    db.commit()

    # 3) 默认租户
    tenant = db.execute(select(Tenant).where(Tenant.code == "default")).scalars().first()
    if tenant is None:
        tenant = Tenant(code="default", name="默认租户", remark="系统初始化自动创建")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

    # 4) 默认管理员
    admin = get_user_by_username(db, settings.SECURITY_ADMIN_USERNAME)
    if admin is None:
        admin_role = existing_roles.get("super_admin")
        admin = User(
            username=settings.SECURITY_ADMIN_USERNAME,
            full_name="系统管理员",
            hashed_password=hash_password(settings.SECURITY_ADMIN_PASSWORD),
            is_active=True,
            is_superuser=True,
            tenant_id=tenant.id,
        )
        if admin_role is not None:
            admin.roles = [admin_role]
        db.add(admin)
        db.commit()
        created["admin"] = True

    created["tenant"] = tenant.code if tenant else None
    logger.info("P0 权限体系初始化完成: %s", created)
    return created


def count_users(db: Session) -> int:
    """用户总数。"""
    return int(db.execute(select(func.count(User.id))).scalar() or 0)


def purge_old_audit_logs(db: Session, retention_days: Optional[int] = None) -> int:
    """按保留期清理历史审计日志（敏感操作，需显式调用）。"""
    days = retention_days or settings.SECURITY_AUDIT_RETENTION_DAYS
    if days <= 0:
        return 0
    deadline = datetime.now(timezone.utc) - timedelta(days=days)
    result = db.query(AuditLog).filter(AuditLog.created_at < deadline).delete()
    db.commit()
    return int(result or 0)
