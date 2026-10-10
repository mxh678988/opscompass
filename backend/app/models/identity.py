"""OS 内核模型：统一身份治理（M3）。

设计要点（对应 docs/os-kernel-design.md 第 3.5 节）：
- 委派/代理是「临时授权」的持久化凭据，到期或撤销即失效，**不修改**被委托人的长期角色；
- 授权范围只允许委托人自身权限的子集（角色码 + 权限码双轨），越权委托由服务层拒绝；
- 失效采用「状态 + 时间窗」双保险：状态机 ``active → expired / revoked``，查询时再按
  ``start_at`` / ``end_at`` 过滤，避免时钟漂移导致误放行；
- 离职交接不单独建表：以「角色转移 + 委派撤销 + 审计留痕」在服务层一次完成；
- 所有表统一 ``oc_core_`` 前缀，与既有 ``oc_`` 业务表隔离（表前缀口径与 M1/M2 实现一致）。
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.kernel import ID_TYPE

# 委派状态：active 生效中 / expired 已过期 / revoked 已撤销
DELEGATION_STATUSES = ("active", "expired", "revoked")


class CoreDelegation(Base):
    """身份委派（临时授权 / 代理）。"""

    __tablename__ = "oc_core_delegation"
    __table_args__ = (
        Index("ix_core_delegation_delegatee", "delegatee_id", "status"),
        Index("ix_core_delegation_delegator", "delegator_id", "status"),
        Index("ix_core_delegation_window", "status", "end_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    delegator_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("oc_user.id", ondelete="CASCADE"), comment="委托人（权限来源）"
    )
    delegatee_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("oc_user.id", ondelete="CASCADE"), comment="被委托人（代理执行者）"
    )
    scope_roles: Mapped[list[Any]] = mapped_column(
        JSON, default=list, comment="委派角色码（须为委托人自身角色子集）"
    )
    scope_permissions: Mapped[list[Any]] = mapped_column(
        JSON, default=list, comment="委派权限码（须为委托人自身权限子集）"
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="委派事由")
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", index=True, comment="active/expired/revoked"
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="生效时间"
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="失效时间（必填，禁止无期限委派）"
    )
    created_by: Mapped[Optional[int]] = mapped_column(ID_TYPE, default=None, comment="操作人 ID")
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="撤销时间"
    )
    revoked_by: Mapped[Optional[int]] = mapped_column(ID_TYPE, default=None, comment="撤销人 ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="最近更新时间",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CoreDelegation {self.delegator_id}->{self.delegatee_id} {self.status}>"
