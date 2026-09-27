"""运营参谋模块响应模型：网站/页面/商品/SEO/GEO/AI 配置/媒体。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WebsiteOut(_ORMModel):
    id: int
    tenant_id: int
    site_name: str
    site_url: str
    site_type: str
    theme: str
    status: str
    language: str
    description: str
    sitemap_generated: bool
    seo_score: int
    geo_score: int
    ai_enabled: bool
    ai_mode: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WebsitePageOut(_ORMModel):
    id: int
    tenant_id: int
    website_id: int
    title: str
    slug: str
    content: str
    seo_title: str
    seo_desc: str
    seo_keywords: str
    og_image: str
    publish_status: str
    published_at: str
    ai_enabled: bool
    ai_generated: bool
    content_level: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProductItemOut(_ORMModel):
    id: int
    tenant_id: int
    website_id: int
    name: str
    slug: str
    price: int
    currency: str
    stock: int
    sku: str
    description: str
    status: str
    seo_title: str
    seo_desc: str
    ai_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SeoTaskOut(_ORMModel):
    id: int
    tenant_id: int
    website_id: int
    task_type: str
    title: str
    description: str
    status: str
    result: str
    ai_model: str
    duration_ms: int
    ai_enabled: bool
    created_at: Optional[datetime] = None


class PageSeoTaskOut(_ORMModel):
    id: int
    tenant_id: int
    page_id: int
    task_type: str
    title: str
    status: str
    result: str
    ai_enabled: bool
    created_at: Optional[datetime] = None


class GeoTaskOut(_ORMModel):
    id: int
    tenant_id: int
    website_id: int
    task_type: str
    title: str
    target_page_ids: str
    status: str
    result: str
    ai_model: str
    ai_enabled: bool
    created_at: Optional[datetime] = None


class WebsiteAiConfigOut(_ORMModel):
    id: int
    tenant_id: int
    website_id: int
    setting_type: str
    config_value: str
    enabled: bool
    ai_model: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MediaItemOut(_ORMModel):
    id: int
    tenant_id: int
    website_id: int
    media_type: str
    file_url: str
    file_name: str
    file_size: int
    mime_type: str
    width: int
    height: int
    tags: str
    description: str
    folder: str
    usage_count: int
    content_level: str
    ai_generated: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PageMediaRefOut(_ORMModel):
    id: int
    tenant_id: int
    page_id: int
    media_id: int
    media_type: str
    created_at: Optional[datetime] = None


class CrawlDiagnosticOut(BaseModel):
    level: str
    item: str
    message: str


class CrawlResultOut(BaseModel):
    """站内预览 / 可控抓取结果。"""

    url: str
    final_url: str
    status_code: int
    elapsed_ms: int
    content_type: str
    bytes: int
    title: str
    meta_description: str
    h1: list[str]
    h2_count: int
    word_count: int
    canonical: str
    og_title: str
    text_preview: str
    diagnostics: list[CrawlDiagnosticOut]
