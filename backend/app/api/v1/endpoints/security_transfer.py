"""M14 导入导出安全中心 REST 端点。

- POST /security/imports：导入压缩包自动安全解压提取
- GET /security/imports：导入记录列表
- POST /security/exports：导出压缩（encrypted=True 需 secure-export 插件启用）
- GET /security/exports：导出记录列表
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_db
from app.models.plugin import CorePlugin
from app.schemas.security_transfer import (
    ExportRecordOut,
    ExportRequest,
    ImportRecordOut,
    ImportRequest,
)
from app.services.security_transfer_service import (
    SECURE_EXPORT_PLUGIN_ID,
    SecurityTransferError,
    export_archive,
    import_archive,
    list_exports,
    list_imports,
)

router = APIRouter()


def _is_secure_export_enabled(db: Session) -> bool:
    plugin = (
        db.query(CorePlugin)
        .filter(
            CorePlugin.plugin_id == SECURE_EXPORT_PLUGIN_ID,
            CorePlugin.state == "enabled",
        )
        .first()
    )
    return plugin is not None


@router.post("/imports", response_model=ImportRecordOut, status_code=status.HTTP_201_CREATED)
def create_import(
    payload: ImportRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """导入压缩包自动解压提取（zip-slip 防护）。"""
    try:
        return import_archive(db, tenant_id=tenant_id, payload=payload)
    except SecurityTransferError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/imports", response_model=dict)
def get_imports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """导入记录列表。"""
    data = list_imports(db, tenant_id=tenant_id, page=page, page_size=page_size)
    return {
        "total": data["total"],
        "page": page,
        "page_size": page_size,
        "items": [ImportRecordOut.model_validate(i).model_dump() for i in data["items"]],
    }


@router.post("/exports", response_model=ExportRecordOut, status_code=status.HTTP_201_CREATED)
def create_export(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """导出压缩（加密导出需 secure-export 付费插件启用）。"""
    gate = None
    if payload.encrypted:
        gate = _is_secure_export_enabled(db)
    try:
        return export_archive(db, tenant_id=tenant_id, payload=payload, allow_encrypted=gate)
    except SecurityTransferError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/exports", response_model=dict)
def get_exports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """导出记录列表。"""
    data = list_exports(db, tenant_id=tenant_id, page=page, page_size=page_size)
    return {
        "total": data["total"],
        "page": page,
        "page_size": page_size,
        "items": [ExportRecordOut.model_validate(i).model_dump() for i in data["items"]],
    }
