"""M15 响应式网站生成器：HTTP 端点。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id, require_module_access
from app.schemas.site_project import SiteProjectIn, SiteProjectOut, SiteProjectPatch
from app.services import site_service

router = APIRouter(prefix="/sites", tags=["site-generator"])


@router.post("", response_model=SiteProjectOut)
def create_site(
    payload: SiteProjectIn,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    return site_service.create_site(db, tenant_id, payload)


@router.get("", response_model=list[SiteProjectOut])
def list_sites(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    return site_service.list_sites(db, tenant_id, skip, limit)


@router.get("/{site_id}", response_model=SiteProjectOut)
def get_site(
    site_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    return site_service.get_site(db, tenant_id, site_id)


@router.patch("/{site_id}", response_model=SiteProjectOut)
def update_site(
    site_id: int,
    payload: SiteProjectPatch,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    return site_service.update_site(db, tenant_id, site_id, payload)


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    site_service.delete_site(db, tenant_id, site_id)


@router.post("/{site_id}/publish", response_model=SiteProjectOut)
def publish_site(
    site_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    return site_service.publish_site(db, tenant_id, site_id)


@router.get("/{site_id}/preview")
def preview_site(
    site_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    _: None = Depends(require_module_access("sites")),
):
    html_doc = site_service.get_preview_html(db, tenant_id, site_id)
    return Response(content=html_doc, media_type="text/html; charset=utf-8")
