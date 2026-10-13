"""M13 API 申请助手接口：平台模板管理 / 代申请任务。

路由前缀 /api-bridge（注册见 app/api/v1/router.py，需 api_bridge 模块权限）：
- 读操作（模板列表/详情、任务列表/详情）：api_bridge:view
- 写操作（模板增改、任务创建/状态更新）：api_bridge:create / api_bridge:update
- 删除：api_bridge:delete
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.schemas.api_bridge import (
    ApiApplyTaskIn,
    ApiApplyTaskPatch,
    ApiPlatformTemplateIn,
    ApiPlatformTemplatePatch,
)
from app.services import api_bridge_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------- 平台模板

@router.post("/templates", response_model=ApiResponse[dict], summary="新增平台申请模板")
def create_template(
    payload: ApiPlatformTemplateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.create_template(db, tenant_id, payload, operator=user.username)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={"id": data.id, "name": data.name}, message="平台模板已创建")


@router.patch("/templates/{template_id}", response_model=ApiResponse[dict], summary="更新平台申请模板")
def update_template(
    template_id: int,
    payload: ApiPlatformTemplatePatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.update_template(db, tenant_id, template_id, payload, operator=user.username)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={"id": data.id, "name": data.name, "enabled": data.enabled}, message="平台模板已更新")


@router.get("/templates", response_model=ApiResponse[dict], summary="平台模板列表（分页过滤）")
def list_templates(
    category: str | None = Query(default=None, description="分类 ecommerce/website/other"),
    enabled: bool | None = Query(default=None, description="启用状态"),
    keyword: str | None = Query(default=None, description="关键词（名称/地址）"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.list_templates(db, tenant_id, category=category, enabled=enabled, keyword=keyword, page=page, size=size)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="ok")


@router.get("/templates/{template_id}", response_model=ApiResponse[dict], summary="平台模板详情")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.get_template(db, tenant_id, template_id)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={
        "id": data.id,
        "name": data.name,
        "apply_url": data.apply_url,
        "field_schema": data.field_schema,
        "requires_manual": data.requires_manual,
        "category": data.category,
        "enabled": data.enabled,
        "created_at": data.created_at.isoformat() if data.created_at else None,
    }, message="ok")


@router.delete("/templates/{template_id}", response_model=ApiResponse[dict], summary="删除平台申请模板")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        svc.delete_template(db, tenant_id, template_id)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={"id": template_id}, message="平台模板已删除")


# ---------------------------------------------------------------- 申请任务

@router.post("/tasks", response_model=ApiResponse[dict], summary="创建 API 代申请任务")
def create_apply_task(
    payload: ApiApplyTaskIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.create_apply_task(db, tenant_id, payload, operator=user.username)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={
        "id": data.id,
        "platform": data.platform,
        "status": data.status,
        "progress": data.progress,
    }, message="申请任务已创建")


@router.patch("/tasks/{task_id}", response_model=ApiResponse[dict], summary="更新申请任务状态/进度")
def update_apply_task(
    task_id: int,
    payload: ApiApplyTaskPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.update_apply_task(db, tenant_id, task_id, payload, operator=user.username)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={
        "id": data.id,
        "status": data.status,
        "progress": data.progress,
    }, message="申请任务已更新")


@router.get("/tasks", response_model=ApiResponse[dict], summary="申请任务列表（分页过滤）")
def list_tasks(
    status: str | None = Query(default=None, description="pending/submitted/awaiting_manual/done/failed"),
    keyword: str | None = Query(default=None, description="关键词（平台/账号/结果）"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.list_tasks(db, tenant_id, status=status, keyword=keyword, page=page, size=size)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="ok")


@router.get("/tasks/{task_id}", response_model=ApiResponse[dict], summary="申请任务详情")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.get_task(db, tenant_id, task_id)
    except svc.ApiBridgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data={
        "id": data.id,
        "platform_id": data.platform_id,
        "platform": data.platform,
        "status": data.status,
        "account_masked": (data.account[:3] + "***") if len(data.account) > 3 else "***",
        "progress": data.progress,
        "result_message": data.result_message,
        "error": data.error,
        "created_by": data.created_by,
        "created_at": data.created_at.isoformat() if data.created_at else None,
        "updated_at": data.updated_at.isoformat() if data.updated_at else None,
        "finished_at": data.finished_at.isoformat() if data.finished_at else None,
    }, message="ok")
