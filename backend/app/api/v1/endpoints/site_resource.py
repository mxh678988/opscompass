"""M16 网站资源管理器：/sites/{site_id}/resources 路由。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id, require_module_access
from app.schemas.site_resource import (
    ResourceScanOut,
    ResourceSummaryOut,
    SiteResourceOut,
    SiteResourcePatch,
)
from app.services import site_resource_service as svc
from app.services.site_resource_service import SiteResourceError

router = APIRouter()


def _err_msg(e: Exception) -> str:
    return str(e)


@router.post("/{site_id}/resources/scan", response_model=ResourceScanOut)
def scan_site_resources(
    site_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    _=Depends(require_module_access("sites")),
):
    try:
        return svc.scan_project(db, tenant_id, site_id)
    except SiteResourceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=_err_msg(e))


@router.get("/{site_id}/resources", response_model=List[SiteResourceOut])
def list_site_resources(
    site_id: int,
    resource_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    _=Depends(require_module_access("sites")),
):
    return svc.list_resources(
        db, tenant_id, project_id=site_id,
        resource_type=resource_type, status=status, skip=skip, limit=limit,
    )


@router.get("/{site_id}/resources/summary", response_model=ResourceSummaryOut)
def site_resources_summary(
    site_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    _=Depends(require_module_access("sites")),
):
    return svc.summary(db, tenant_id, project_id=site_id)


@router.get("/resources/{resource_id}", response_model=SiteResourceOut)
def get_site_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    _=Depends(require_module_access("sites")),
):
    try:
        return svc.get_resource(db, tenant_id, resource_id)
    except SiteResourceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=_err_msg(e))


@router.patch("/resources/{resource_id}", response_model=SiteResourceOut)
def update_site_resource(
    resource_id: int,
    payload: SiteResourcePatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    _=Depends(require_module_access("sites")),
):
    try:
        return svc.update_resource(db, tenant_id, resource_id, payload)
    except SiteResourceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=_err_msg(e))


@router.delete("/resources/{resource_id}")
def delete_site_resource(
    resource_id: int,
    force: bool = Query(False, description="同时物理删除发布目录内文件"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    _=Depends(require_module_access("sites")),
):
    try:
        return svc.delete_resource(db, tenant_id, resource_id, force=force)
    except SiteResourceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=_err_msg(e))
