"""M9 预测引擎接口：发起预测 / 查询预测任务与结果。

路由前缀 /predictive（见 app/api/v1/router.py，需 predictive 模块权限）：
- 读（任务列表与详情）：predictive:view
- 写（发起单主体/批量预测）：predictive:run
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.schemas.predictive import PredictionBatchIn, PredictionRunIn
from app.services import predictive_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/runs", response_model=ApiResponse[dict], summary="发起单主体预测任务（流失/转化概率）")
def create_run(
    payload: PredictionRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.run_job(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="预测任务已执行")


@router.post("/batch", response_model=ApiResponse[dict], summary="批量预测（直接给主体列表）")
def create_batch(
    payload: PredictionBatchIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        data = svc.run_job(db, tenant_id, payload, operator=user.username)
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="批量预测任务已执行")


@router.get("/runs", response_model=ApiResponse[dict], summary="预测任务列表")
def list_runs(
    keyword: str | None = Query(default=None, description="任务名称/发起方关键字"),
    target: str | None = Query(default=None, description="churn/conversion"),
    status: str | None = Query(default=None, description="pending/running/success/failed"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        data = svc.list_jobs(
            db, tenant_id, keyword=keyword, target=target, status=status, page=page, size=size
        )
    except Exception as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data)


@router.get("/runs/{job_id}", response_model=ApiResponse[dict], summary="预测任务详情（含结果明细）")
def read_run(
    job_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    data = svc.get_job(db, tenant_id, job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="预测任务不存在")
    return ApiResponse[dict](data=data)
