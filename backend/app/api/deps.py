"""接口公共依赖：租户上下文解析与 RBAC 鉴权。"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.models.auth import User
from app.models.base import SessionLocal, get_db
from app.models.tenant import Tenant
from app.services import audit_service, auth_service

DEFAULT_TENANT_CODE = "default"


def get_tenant_id(
    x_tenant_id: Optional[int] = Header(default=None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
) -> int:
    """解析当前租户 ID。

    优先取请求头 X-Tenant-Id；未传时回落到编码为 default 的租户。
    """
    if x_tenant_id is not None:
        if db.get(Tenant, x_tenant_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="租户不存在")
        return x_tenant_id

    tenant = db.execute(
        select(Tenant).where(Tenant.code == DEFAULT_TENANT_CODE)
    ).scalars().first()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="默认租户不存在，请先执行初始化脚本或 POST /api/v1/tenants 创建租户",
        )
    return tenant.id


# ============================================================ 鉴权依赖
security_scheme = HTTPBearer(auto_error=False, description="Bearer JWT 访问令牌")


def _client_ip(request: Request) -> Optional[str]:
    return audit_service.get_client_ip(request)


def _audit_denied(
    db: Session,
    request: Request,
    reason: str,
    user: Optional[User] = None,
    status_code: int = 403,
) -> None:
    """记录鉴权失败审计日志。"""
    audit_service.log_access_denied(
        db,
        request=request,
        reason=reason,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        status_code=status_code,
    )


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer Token 并返回当前用户；失败抛 401 并记录审计。"""
    if credentials is None or not credentials.credentials:
        _audit_denied(db, request, "缺少访问令牌", status_code=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = security.try_decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        _audit_denied(db, request, "访问令牌无效或已过期", status_code=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        _audit_denied(db, request, "访问令牌主体非法", status_code=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问令牌非法",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if user is None:
        _audit_denied(db, request, "令牌对应的用户不存在", status_code=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        _audit_denied(db, request, "账号已停用", user=user, status_code=403)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员"
        )

    # 供审计中间件读取当前操作人
    try:
        request.state.user_id = user.id
        request.state.username = user.username
        request.state.tenant_id = user.tenant_id
    except Exception:  # pragma: no cover
        pass
    return user


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """宽容版：无令牌或令牌无效时返回 None，不抛异常。"""
    if credentials is None or not credentials.credentials:
        return None
    payload = security.try_decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    try:
        user = db.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        return None
    if user is None or not user.is_active:
        return None
    try:
        request.state.user_id = user.id
        request.state.username = user.username
        request.state.tenant_id = user.tenant_id
    except Exception:  # pragma: no cover
        pass
    return user


def require_roles(*role_codes: str):
    """角色鉴权依赖工厂：任一角色命中即通过。"""

    def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not security.has_role(user, role_codes):
            reason = f"需要角色 {' / '.join(role_codes)}"
            _audit_denied(db, request, reason, user=user)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
        return user

    return _dependency


def require_permissions(*permission_codes: str, require_all: bool = False):
    """权限鉴权依赖工厂：默认任一权限命中即通过，require_all=True 时需全部命中。"""

    def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        owned = set(auth_service.user_permission_codes(user))
        needed = set(permission_codes)
        ok = needed.issubset(owned) if require_all else bool(owned & needed)
        if not ok:
            reason = f"缺少权限 {' + '.join(sorted(needed))}"
            _audit_denied(db, request, reason, user=user)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
        return user

    return _dependency


# 模块级权限矩阵：按 HTTP 方法映射所需权限码（任一命中即通过）
MODULE_PERMISSION_MAP: dict = {
    "tenant": {
        "read": ["tenant:view"],
        "write": ["tenant:create", "tenant:update"],
        "delete": ["tenant:delete"],
    },
    "datasource": {
        "read": ["datasource:view"],
        "write": ["datasource:create", "datasource:update", "datasource:sync"],
        "delete": ["datasource:delete"],
    },
    "metric": {
        "read": ["metric:view"],
        "write": ["metric:create", "metric:update"],
        "delete": ["metric:delete"],
    },
    "ingest": {
        "read": ["ingest:view"],
        "write": ["ingest:run"],
        "delete": ["ingest:run"],
    },
    "ai": {
        "read": ["ai:view"],
        "write": ["ai:analyze", "ai:config"],
        "delete": ["ai:config"],
    },
    "ops": {
        "read": ["ops:view"],
        "write": ["ops:create", "ops:update"],
        "delete": ["ops:delete"],
    },
    "marketing": {
        "read": ["marketing:view"],
        "write": ["marketing:create", "marketing:update", "marketing:authorize"],
        "delete": ["marketing:delete"],
    },
    "collect": {
        "read": ["collect:view"],
        "write": ["collect:create", "collect:update", "collect:run"],
        "delete": ["collect:delete"],
    },
    "model": {
        "read": ["model:view"],
        "write": ["model:config"],
        "delete": [],
    },
    # 存储适配层：读复用指标/运营资产查看权限，写复用其创建/编辑权限
    "storage": {
        "read": ["metric:view", "ops:view"],
        "write": ["metric:create", "ops:create"],
        "delete": ["metric:delete", "ops:delete"],
    },
    # 模型中心（P9 硬件检测 + 模型自动适配）：读复用 ai:view，写复用 ai:config
    "model": {
        "read": ["ai:view", "ops:view"],
        "write": ["ai:config", "ops:create"],
        "delete": ["ai:config"],
    },
    # 学习进化闭环（P8）：反馈回流 / 策略权重 / 案例库 / A-B 实验
    "learning": {
        "read": ["learning:view"],
        "write": ["learning:manage"],
        "delete": ["learning:manage"],
    },
}


def require_module_access(module: str):
    """模块级鉴权依赖工厂：GET 需读权限，写操作需对应写/删权限。"""
    rules = MODULE_PERMISSION_MAP.get(module)
    if not rules:  # pragma: no cover
        raise ValueError(f"未定义权限矩阵的模块: {module}")

    def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        method = request.method.upper()
        if method in ("GET", "HEAD", "OPTIONS"):
            codes = rules["read"]
        elif method == "DELETE":
            codes = rules.get("delete") or rules["write"]
        else:
            codes = rules["write"]

        owned = set(auth_service.user_permission_codes(user))
        if not (owned & set(codes)):
            reason = f"缺少 {module} 模块操作权限（需要 {' / '.join(codes)} 之一）"
            _audit_denied(db, request, reason, user=user)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=reason
            )
        return user

    return _dependency


def get_current_tenant_id(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[int]:
    """当前用户所属租户；未绑定租户时回落到 X-Tenant-Id/默认租户。"""
    if user.tenant_id is not None:
        return user.tenant_id
    raw = request.headers.get("x-tenant-id")
    tenant_id = int(raw) if raw and raw.isdigit() else None
    return get_tenant_id(x_tenant_id=tenant_id, db=db)
