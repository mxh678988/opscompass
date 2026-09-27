"""租户模型：多租户数据隔离的根实体。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Tenant(Base):
    """租户（业务方）。

    全域运营决策平台默认按租户隔离所有业务数据，
    后续所有表统一携带 tenant_id 字段。
    """

    __tablename__ = "oc_tenant"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="租户编码")
    name: Mapped[str] = mapped_column(String(128), comment="租户名称")
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active", comment="状态：active/disabled"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tenant {self.code}>"
