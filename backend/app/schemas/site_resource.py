"""M16 网站资源管理器：Pydantic Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SiteResourceIn(BaseModel):
    resource_type: str = Field(..., description="page/media/script/css/image/other")
    name: str = Field(..., min_length=1, max_length=200)
    path: str = Field(..., min_length=1, max_length=600)
    size_bytes: int = 0
    checksum: Optional[str] = Field(None, max_length=64)
    meta: Optional[Dict[str, Any]] = None


class SiteResourcePatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    resource_type: Optional[str] = None
    status: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class SiteResourceOut(BaseModel):
    id: int
    tenant_id: int
    project_id: Optional[int]
    resource_type: str
    name: str
    path: str
    size_bytes: int
    checksum: Optional[str]
    status: str
    meta: Optional[Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResourceScanOut(BaseModel):
    project_id: int
    scanned: int
    created: int
    updated: int
    marked_missing: int


class ResourceSummaryOut(BaseModel):
    project_id: int
    total: int
    total_size_bytes: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]
