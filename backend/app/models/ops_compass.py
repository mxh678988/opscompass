"""运营参谋模块：网站/网店管理、SEO 运营、GEO 优化、AI 智能设置、媒体库、自媒体。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Website(Base):
    """网站/网店：支持 CMS、电商、SEO、GEO、媒体库集成。"""

    __tablename__ = "oc_website"
    __table_args__ = (UniqueConstraint("tenant_id", "site_url", name="uq_website_tenant_url"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    site_name: Mapped[str] = mapped_column(String(128), comment="网站名称")
    site_url: Mapped[str] = mapped_column(String(512), comment="站点 URL")
    site_type: Mapped[str] = mapped_column(
        String(32), default="cms", server_default="cms", comment="类型: cms|shop|blog|landing|custom"
    )
    theme: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="主题名称")
    status: Mapped[str] = mapped_column(
        String(32), default="draft", server_default="draft", comment="draft|published|archived"
    )
    language: Mapped[str] = mapped_column(String(16), default="zh-CN", server_default="zh-CN", comment="站点语言")
    description: Mapped[str] = mapped_column(Text, default="", server_default="", comment="站点描述")
    sitemap_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="Sitemap 是否已生成"
    )
    seo_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="SEO 评分 0-100")
    geo_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="GEO 评分 0-100")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", comment="AI 运营开关")
    ai_mode: Mapped[str] = mapped_column(String(16), default="local", server_default="local", comment="ai|local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list["WebsitePage"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    products: Mapped[list["ProductItem"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    seo_tasks: Mapped[list["SeoTask"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    geo_tasks: Mapped[list["GeoTask"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    ai_configs: Mapped[list["WebsiteAiConfig"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )
    media_items: Mapped[list["MediaItem"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )


class WebsitePage(Base):
    """网站页面：CMS 页面 / 文章 / 落地页。"""

    __tablename__ = "oc_website_page"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    website_id: Mapped[int] = mapped_column(ForeignKey("oc_website.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), comment="页面标题")
    slug: Mapped[str] = mapped_column(String(256), default="", server_default="", index=True, comment="URL 路径")
    content: Mapped[str] = mapped_column(Text, default="", server_default="", comment="页面正文")
    seo_title: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="SEO title")
    seo_desc: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="SEO meta description")
    seo_keywords: Mapped[str] = mapped_column(String(256), default="", server_default="", comment="SEO 关键词")
    og_image: Mapped[str] = mapped_column(String(512), default="", server_default="", comment="OG:image")
    publish_status: Mapped[str] = mapped_column(
        String(32), default="draft", server_default="draft", comment="draft|scheduled|published|archived"
    )
    published_at: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="发布时间")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    content_level: Mapped[str] = mapped_column(String(4), default="L2", server_default="L2", comment="内容分级 L1-L4")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    website: Mapped["Website"] = relationship(back_populates="pages")
    seo_tasks: Mapped[list["PageSeoTask"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )
    media_refs: Mapped[list["PageMediaRef"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class ProductItem(Base):
    """商品/产品：电商类站点。"""

    __tablename__ = "oc_product_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    website_id: Mapped[int] = mapped_column(ForeignKey("oc_website.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256), comment="商品名称")
    slug: Mapped[str] = mapped_column(String(256), default="", server_default="", index=True)
    price: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="价格(分)")
    currency: Mapped[str] = mapped_column(String(8), default="CNY", server_default="CNY")
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="库存")
    sku: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="SKU")
    description: Mapped[str] = mapped_column(Text, default="", server_default="", comment="商品描述")
    status: Mapped[str] = mapped_column(
        String(32), default="draft", server_default="draft", comment="draft|active|inactive"
    )
    seo_title: Mapped[str] = mapped_column(String(128), default="", server_default="")
    seo_desc: Mapped[str] = mapped_column(String(512), default="", server_default="")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    website: Mapped["Website"] = relationship(back_populates="products")


class SeoTask(Base):
    """SEO 任务（站点级）。"""

    __tablename__ = "oc_seo_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    website_id: Mapped[int] = mapped_column(ForeignKey("oc_website.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(
        String(32),
        comment="audit|generate_sitemap|generate_robots|content_audit|keyword_analysis|link_audit",
    )
    title: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="任务标题")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", comment="pending|running|success|failed"
    )
    result: Mapped[str] = mapped_column(Text, default="", server_default="", comment="结果 JSON")
    ai_model: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="使用的 AI 模型")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    website: Mapped["Website"] = relationship(back_populates="seo_tasks")


class PageSeoTask(Base):
    """页面级 SEO 任务。"""

    __tablename__ = "oc_page_seo_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    page_id: Mapped[int] = mapped_column(ForeignKey("oc_website_page.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128), default="", server_default="")
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    result: Mapped[str] = mapped_column(Text, default="", server_default="")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    page: Mapped["WebsitePage"] = relationship(back_populates="seo_tasks")


class GeoTask(Base):
    """GEO（Generative Engine Optimization）任务。"""

    __tablename__ = "oc_geo_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    website_id: Mapped[int] = mapped_column(ForeignKey("oc_website.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(
        String(32), comment="content_optimize|schema_markup|ai_snippet|structured_data|local_seo"
    )
    title: Mapped[str] = mapped_column(String(128), default="", server_default="")
    target_page_ids: Mapped[str] = mapped_column(Text, default="", server_default="", comment="目标页面 ID JSON")
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    result: Mapped[str] = mapped_column(Text, default="", server_default="")
    ai_model: Mapped[str] = mapped_column(String(64), default="", server_default="")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    website: Mapped["Website"] = relationship(back_populates="geo_tasks")


class WebsiteAiConfig(Base):
    """AI 智能设置（站点级）：SEO/内容/GEO 自动化的开关与参数。"""

    __tablename__ = "oc_website_ai_config"
    __table_args__ = (UniqueConstraint("website_id", "setting_type", name="uq_website_ai_setting"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    website_id: Mapped[int] = mapped_column(ForeignKey("oc_website.id", ondelete="CASCADE"), index=True)
    setting_type: Mapped[str] = mapped_column(
        String(32),
        comment="seo_auto|content_auto|seo_tone|content_tone|publish_schedule|auto_sitemap|media_auto_tag|auto_meta",
    )
    config_value: Mapped[str] = mapped_column(Text, default="{}", server_default="{}", comment="JSON 配置")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ai_model: Mapped[str] = mapped_column(String(64), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    website: Mapped["Website"] = relationship(back_populates="ai_configs")


class MediaItem(Base):
    """媒体库资源：图片 / 视频 / 音频 / 文档。"""

    __tablename__ = "oc_media_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    website_id: Mapped[int] = mapped_column(ForeignKey("oc_website.id", ondelete="CASCADE"), index=True)
    media_type: Mapped[str] = mapped_column(
        String(32), comment="image|video|audio|document|archive"
    )
    file_url: Mapped[str] = mapped_column(String(1024), comment="文件 URL")
    file_name: Mapped[str] = mapped_column(String(256), default="", server_default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="字节")
    mime_type: Mapped[str] = mapped_column(String(128), default="", server_default="")
    width: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    height: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tags: Mapped[str] = mapped_column(Text, default="", server_default="", comment="标签 JSON")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    folder: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="文件夹路径")
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    content_level: Mapped[str] = mapped_column(String(4), default="L2", server_default="L2", comment="内容分级")
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    website: Mapped["Website"] = relationship(back_populates="media_items")
    page_refs: Mapped[list["PageMediaRef"]] = relationship(
        back_populates="media", cascade="all, delete-orphan"
    )


class PageMediaRef(Base):
    """页面-媒体引用关系。"""

    __tablename__ = "oc_page_media_ref"
    __table_args__ = (UniqueConstraint("page_id", "media_id", name="uq_page_media"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    page_id: Mapped[int] = mapped_column(ForeignKey("oc_website_page.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("oc_media_item.id", ondelete="CASCADE"), index=True)
    media_type: Mapped[str] = mapped_column(String(32), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    page: Mapped["WebsitePage"] = relationship(back_populates="media_refs")
    media: Mapped["MediaItem"] = relationship(back_populates="page_refs")
