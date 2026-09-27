"""P9 模型中心接口：硬件探测 / 模型推荐 / 接入端点管理 / 连通性自检 / 一键接入。

路由前缀 /model（见 app/api/v1/router.py，需 model 模块权限）：
- 读（探测、推荐、概览、列表、详情）：module="model", action="read"
- 写（新增、修改、自检、激活、同步 .env、一键接入）：module="model", action="write"
- 删：module="model", action="delete"
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.schemas.model_hub import ApplyIn, EndpointIn, EndpointPatch, EndpointTestIn, SyncIn
from app.services import model_hub_service as svc

router = APIRouter()


def _raise(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ============================================================ 硬件探测与推荐
@router.get("/hardware", response_model=ApiResponse[dict], summary="本机硬件探测（CPU/内存/GPU 显存/磁盘/网络出口）")
def read_hardware(
    refresh: bool = Query(default=True, description="是否重新探测；false 时优先复用宿主机快照"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    """CPU / 内存 / GPU 与显存 / 磁盘 / 网络出口；探测不可用时返回降级原因。"""
    data = svc.hardware_and_recommend(refresh=refresh)
    probe = data.get("probe") or {}
    return ApiResponse[dict](
        data={
            "environment": probe.get("environment") or {},
            "cpu": probe.get("cpu") or {},
            "memory": probe.get("memory") or {},
            "disks": probe.get("disks") or [],
            "gpus": probe.get("gpus") or [],
            "gpu_vram": probe.get("gpu_vram") or {},
            "network": probe.get("network") or {},
            "degradations": probe.get("degradations") or [],
            "sources": probe.get("sources") or [],
            "host_snapshot": probe.get("host_snapshot") or {},
            "probed_at": probe.get("probed_at"),
            "probe_ms": probe.get("probe_ms"),
            "recommendation": data.get("recommendation") or {},
        }
    )


@router.get("/recommend", response_model=ApiResponse[dict], summary="按显存分档推荐可跑的本地模型量级与接入后端")
def read_recommend(
    include_hardware: bool = Query(default=True, description="是否附带回硬件探测原始结果"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.hardware_and_recommend(refresh=True)
    payload: dict[str, Any] = {"recommendation": data.get("recommendation") or {}}
    if include_hardware:
        payload["probe"] = data.get("probe") or {}
    return ApiResponse[dict](data=payload)


# ============================================================ 概览
@router.get("/overview", response_model=ApiResponse[dict], summary="模型中心概览")
def read_overview(
    db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.overview(db, tenant_id))


# ============================================================ 端点 CRUD
@router.get("/endpoints", response_model=ApiResponse[dict], summary="接入端点列表")
def list_endpoints(
    db: Session = Depends(get_db), tenant_id: int = Depends(get_current_tenant_id)
) -> ApiResponse[dict]:
    rows = svc.list_endpoints(db, tenant_id)
    active = svc.active_endpoint(db, tenant_id)
    active_id = active.id if active else None
    return ApiResponse[dict](
        data={
            "items": [svc.serialize(r, active_id=active_id) for r in rows],
            "total": len(rows),
            "active_endpoint_id": active_id,
            "runtime": svc.runtime_snapshot(),
        }
    )


@router.post("/endpoints", response_model=ApiResponse[dict], summary="新增接入端点")
def create_endpoint(
    payload: EndpointIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.create_endpoint(db, tenant_id, payload.model_dump())
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message="端点已保存")


@router.get("/endpoints/{endpoint_id}", response_model=ApiResponse[dict], summary="端点详情")
def get_endpoint_detail(
    endpoint_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        row = svc.get_endpoint(db, tenant_id, endpoint_id)
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    active = svc.active_endpoint(db, tenant_id)
    return ApiResponse[dict](
        data={
            "endpoint": svc.serialize(row, active_id=(active.id if active else None)),
            "runtime": svc.runtime_snapshot(),
        }
    )


@router.put("/endpoints/{endpoint_id}", response_model=ApiResponse[dict], summary="修改接入端点")
def update_endpoint(
    endpoint_id: int,
    payload: EndpointPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.update_endpoint(
            db, tenant_id, endpoint_id, payload.model_dump(exclude_unset=True)
        )
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message="端点已更新")


@router.delete("/endpoints/{endpoint_id}", response_model=ApiResponse[dict], summary="删除接入端点")
def delete_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.delete_endpoint(db, tenant_id, endpoint_id)
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message="端点已删除")


# ============================================================ 连通性自检
@router.post("/test", response_model=ApiResponse[dict], summary="连通性自检（支持未保存配置）")
def test_endpoint(
    payload: EndpointTestIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.test_endpoint(
            db=db,
            tenant_id=tenant_id,
            endpoint_id=payload.id,
            kind=payload.kind,
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
        )
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message=data.get("message") or "自检完成")


@router.post("/endpoints/{endpoint_id}/test", response_model=ApiResponse[dict], summary="对已保存端点做连通性自检")
def test_saved_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.test_endpoint(db=db, tenant_id=tenant_id, endpoint_id=endpoint_id, kind=None)
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message=data.get("message") or "自检完成")


# ============================================================ 生效与运行配置
@router.post("/endpoints/{endpoint_id}/activate", response_model=ApiResponse[dict], summary="设为当前生效端点")
def activate_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.activate_endpoint(db, tenant_id, endpoint_id)
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message="已切换生效端点")


@router.post("/endpoints/{endpoint_id}/sync-env", response_model=ApiResponse[dict], summary="生效端点回写 .env 持久化")
def sync_env(
    endpoint_id: int,
    payload: SyncIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.sync_endpoint_to_env(
            db, tenant_id, endpoint_id, apply_to_env=payload.apply_to_env
        )
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    return ApiResponse[dict](data=data, message="运行配置已同步")


# ============================================================ 一键接入
@router.post("/apply", response_model=ApiResponse[dict], summary="一键接入（落库 + 自检 + 生效）")
def apply_endpoint(
    payload: ApplyIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.apply_endpoint(db, tenant_id, payload.model_dump())
    except svc.ModelHubError as exc:
        raise _raise(exc) from exc
    tested = data.get("test") or {}
    message = (
        "已一键接入并生效"
        if tested.get("ok", True)
        else f"已落库，但自检未通过：{tested.get('message') or '未知原因'}"
    )
    return ApiResponse[dict](data=data, message=message)
