"""M15 响应式网站生成器：Pydantic Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SiteSection(BaseModel):
    type: str = Field(..., description="hero/features/contact/about 等")
    title: Optional[str] = None
    text: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None


class SiteContent(BaseModel):
    sections: List[SiteSection] = Field(default_factory=list)


class SiteProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: Optional[str] = Field(None, max_length=500)
    template: str = "default"
    seo_title: Optional[str] = Field(None, max_length=160)
    seo_description: Optional[str] = Field(None, max_length=320)
    seo_keywords: Optional[str] = Field(None, max_length=500)
    geo_enabled: bool = False
    geo_region: Optional[str] = Field(None, max_length=120)
    geo_org_type: Optional[str] = Field(None, max_length=120)
    host_mode: str = Field("link", description="link=链接网站空间；space=内置空间")
    content: Optional[SiteContent] = None


class SiteProjectPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    template: Optional[str] = None
    seo_title: Optional[str] = Field(None, max_length=160)
    seo_description: Optional[str] = Field(None, max_length=320)
    seo_keywords: Optional[str] = Field(None, max_length=500)
    geo_enabled: Optional[bool] = None
    geo_region: Optional[str] = Field(None, max_length=120)
    geo_org_type: Optional[str] = Field(None, max_length=120)
    host_mode: Optional[str] = None
    content: Optional[SiteContent] = None


class SiteProjectOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    slug: str
    description: Optional[str]
    template: str
    seo_title: Optional[str]
    seo_description: Optional[str]
    seo_keywords: Optional[str]
    geo_enabled: bool
    geo_region: Optional[str]
    geo_org_type: Optional[str]
    host_mode: str
    status: str
    content: Optional[Any]
    publish_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
