"""M10 人群包引擎接口：创建 / 复用 / 列表与详情查询。

路由前缀 /audience（见 app/api/v1/router.py，需 audience 模块权限）：
- 读（列表与详情）：audience:view
- 写（创建/复用/更新）：audience:create / audience:update
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.audience import AudienceReuseIn, AudienceSegmentIn, AudienceSegmentPatch
from app.schemas.common import ApiResponse
from app.services import audience_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/segments", response_model=ApiResponse[dict], summary="创建人群包（按预测概率区间圈选）")
def create_segment(
    payload: AudienceSegmentIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.create_segment(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="人群包已创建")


@router.post("/segments/reuse", response_model=ApiResponse[dict], summary="复用人群包（从既有包再圈选）")
def reuse_segment(
    payload: AudienceReuseIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.reuse_segment(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="人群包复用成功")


@router.get("/segments", response_model=ApiResponse[dict], summary="人群包列表")
def list_segments(
    keyword: str | None = Query(default=None, description="人群包名称/创建者关键字"),
    target: str | None = Query(default=None, description="churn/conversion"),
    status: str | None = Query(default=None, description="draft/ready/active/expired/failed"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.list_segments(
            db, tenant_id, keyword=keyword, target=target, status=status, page=page, size=size
        )
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data)


@router.get("/segments/{segment_id}", response_model=ApiResponse[dict], summary="人群包详情（含成员明细）")
def read_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.get_segment(db, tenant_id, segment_id)
    if data is None:
        raise HTTPException(status_code=404, detail="人群包不存在")
    return ApiResponse[dict](data=data)


@router.patch("/segments/{segment_id}", response_model=ApiResponse[dict], summary="更新人群包（状态流转/说明）")
def patch_segment(
    segment_id: int,
    payload: AudienceSegmentPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.update_segment(
            db,
            tenant_id,
            segment_id,
            status=payload.status,
            description=payload.description,
        )
    except Exception as exc:
        raise _fail(exc)
    if data is None:
        raise HTTPException(status_code=404, detail="人群包不存在")
    return ApiResponse[dict](data=data, message="人群包已更新")
