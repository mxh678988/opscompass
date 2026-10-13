"""M16 网站资源管理器：网站资源清单模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


RESOURCE_TYPES = ("page", "media", "script", "css", "image", "other")
RESOURCE_STATUSES = ("active", "archived", "missing")


class SiteResource(Base):
    """网站资源：发布产物内的页面/媒体/脚本/样式等资产的索引与状态。"""

    __tablename__ = "oc_site_resource"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    resource_type: Mapped[str] = mapped_column(String(20), default="other", nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(600), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    meta: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
