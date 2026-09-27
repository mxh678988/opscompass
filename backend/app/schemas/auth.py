"""认证与权限（RBAC）相关的请求/响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------ 登录
class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., min_length=1, max_length=64, description="登录名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class PasswordChangeRequest(BaseModel):
    """修改密码请求。"""

    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


# ------------------------------------------------------------ 权限
class PermissionOut(BaseModel):
    """权限点。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    module: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class RoleOut(BaseModel):
    """角色。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_builtin: bool = False
    permissions: list[str] = Field(default_factory=list, description="权限码列表")
    created_at: Optional[datetime] = None


class RoleCreate(BaseModel):
    """新建角色。"""

    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list, description="权限码列表")


class RoleUpdate(BaseModel):
    """更新角色。"""

    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=255)
    permissions: Optional[list[str]] = None


# ------------------------------------------------------------ 用户
class UserOut(BaseModel):
    """用户。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: Optional[int] = None
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    roles: list[str] = Field(default_factory=list, description="角色码列表")
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UserCreate(BaseModel):
    """新建用户。"""

    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    tenant_id: Optional[int] = None
    is_active: bool = True
    is_superuser: bool = False
    roles: list[str] = Field(default_factory=list, description="角色码列表")


class UserUpdate(BaseModel):
    """更新用户（不允许改密码，改密走独立接口）。"""

    full_name: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    tenant_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    roles: Optional[list[str]] = None


class ResetPasswordRequest(BaseModel):
    """管理员重置他人密码。"""

    new_password: str = Field(..., min_length=6, max_length=128)


# ------------------------------------------------------------ 令牌
class TokenOut(BaseModel):
    """登录响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="有效期（秒）")
    user: UserOut


# ------------------------------------------------------------ 审计
class AuditLogOut(BaseModel):
    """审计日志。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    event_type: str
    action: Optional[str] = None
    status: str = "success"
    status_code: Optional[int] = None
    method: Optional[str] = None
    path: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    detail: Optional[str] = None
    created_at: Optional[datetime] = None


class AuditStatsOut(BaseModel):
    """审计统计。"""

    total: int = 0
    by_event_type: dict = Field(default_factory=dict)
    by_status: dict = Field(default_factory=dict)


class SecurityOverviewOut(BaseModel):
    """安全配置概览。"""

    listen: dict = Field(default_factory=dict)
    cors_origins: list[str] = Field(default_factory=list)
    ip_allowlist: dict = Field(default_factory=dict)
    auth: dict = Field(default_factory=dict)
    audit: dict = Field(default_factory=dict)
