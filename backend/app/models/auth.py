"""认证与权限（RBAC）模型 + 安全审计日志模型。

- 主体：User / Role / Permission
- 关联：oc_user_role / oc_role_permission
- 审计：登录、鉴权失败与敏感操作统一落 oc_audit_log
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# 用户-角色关联表
user_role = Table(
    "oc_user_role",
    Base.metadata,
    Column("user_id", ForeignKey("oc_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("oc_role.id", ondelete="CASCADE"), primary_key=True),
    comment="用户角色关联",
)

# 角色-权限关联表
role_permission = Table(
    "oc_role_permission",
    Base.metadata,
    Column("role_id", ForeignKey("oc_role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("oc_permission.id", ondelete="CASCADE"), primary_key=True),
    comment="角色权限关联",
)


class User(Base):
    """用户。"""

    __tablename__ = "oc_user"
    __table_args__ = (Index("ix_user_tenant_status", "tenant_id", "is_active"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_tenant.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属租户",
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="登录名")
    full_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="姓名")
    email: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="邮箱")
    hashed_password: Mapped[str] = mapped_column(String(255), comment="密码哈希（bcrypt）")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否启用"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否超级管理员"
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="连续登录失败次数"
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="锁定截止时间"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="最近登录时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_role, lazy="selectin", back_populates="users"
    )

    @property
    def role_codes(self) -> list:
        return [r.code for r in self.roles]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"


class Role(Base):
    """角色。"""

    __tablename__ = "oc_role"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="角色编码")
    name: Mapped[str] = mapped_column(String(128), comment="角色名称")
    description: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="描述")
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否内置角色"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )

    users: Mapped[list["User"]] = relationship(secondary=user_role, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permission, lazy="selectin", back_populates="roles"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Role {self.code}>"


class Permission(Base):
    """权限点。"""

    __tablename__ = "oc_permission"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True, comment="权限编码")
    name: Mapped[str] = mapped_column(String(128), comment="权限名称")
    module: Mapped[str] = mapped_column(String(64), comment="所属模块")
    description: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="描述")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary=role_permission, back_populates="permissions"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Permission {self.code}>"


class AuditLog(Base):
    """安全审计日志：登录、鉴权失败、敏感操作。"""

    __tablename__ = "oc_audit_log"
    __table_args__ = (
        Index("ix_audit_tenant_time", "tenant_id", "created_at"),
        Index("ix_audit_event_time", "event_type", "created_at"),
        Index("ix_audit_user_time", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="租户")
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="操作人 ID")
    username: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="操作人登录名")
    event_type: Mapped[str] = mapped_column(
        String(32),
        index=True,
        comment="事件类型：login_success/login_failed/logout/password_change/"
        "access_denied/permission_denied/sensitive_operation",
    )
    action: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="动作摘要")
    status: Mapped[str] = mapped_column(
        String(16), default="success", server_default="success", comment="结果：success/failure"
    )
    status_code: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="HTTP 状态码")
    method: Mapped[Optional[str]] = mapped_column(String(16), default=None, comment="请求方法")
    path: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="请求路径")
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="客户端 IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="客户端 UA")
    detail: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="详细信息")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, comment="发生时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.event_type} {self.path}>"
