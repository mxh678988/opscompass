"""M15 响应式网站生成器：网站项目模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


SITE_STATUSES = ("draft", "published")
SITE_HOST_MODES = ("link", "space")


class SiteProject(Base):
    """网站项目：内容 + SEO/GEO 元数据 + 发布产物状态。"""

    __tablename__ = "oc_site_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    template: Mapped[str] = mapped_column(String(60), default="default", nullable=False)
    # SEO 元数据
    seo_title: Mapped[Optional[str]] = mapped_column(String(160))
    seo_description: Mapped[Optional[str]] = mapped_column(String(320))
    seo_keywords: Mapped[Optional[str]] = mapped_column(String(500))
    # GEO（生成引擎优化）：面向 AI 搜索的地理/组织语义标记
    geo_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    geo_region: Mapped[Optional[str]] = mapped_column(String(120))
    geo_org_type: Mapped[Optional[str]] = mapped_column(String(120))
    # 托管模式：link=用户选择网站空间后外链；space=内置空间发布
    host_mode: Mapped[str] = mapped_column(String(20), default="link", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    # 页面内容（JSON：sections 块），Text 存储
    content: Mapped[Optional[str]] = mapped_column(Text)
    publish_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
