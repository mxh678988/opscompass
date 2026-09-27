"""指标中心接口：指标定义 CRUD、指标值读写、总览与趋势。"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.models.base import get_db
from app.models.metric import Metric
from app.schemas.common import ApiResponse, PageResult
from app.schemas.metric import (
    CompassOut,
    MetricCreate,
    MetricOut,
    MetricUpdate,
    MetricValueBatchIn,
    MetricValueOut,
    OverviewOut,
    TrendOut,
)
from app.services import metric_service as svc

router = APIRouter()


def _get_metric_or_404(db: Session, tenant_id: int, code: str) -> Metric:
    metric = svc.get_metric(db, tenant_id, code)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"指标不存在: {code}")
    return metric


# ----------------------------------------------------- 总览（须先于 /{code} 注册）
@router.get("/overview", response_model=ApiResponse[OverviewOut], summary="指标总览")
def overview(
    granularity: str = Query("day", description="统计粒度 hour/day/week/month"),
    codes: Optional[str] = Query(None, description="指标编码，多个用逗号分隔；不传返回全部上线指标"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[OverviewOut]:
    """返回各指标最新值及环比，供首页指标卡消费。"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    data = svc.overview(db, tenant_id, granularity=granularity, codes=code_list)
    return ApiResponse[OverviewOut](data=data)


# ----------------------------------------------------- 全景罗盘（须先于 /{code} 注册）
@router.get("/dim-keys", response_model=ApiResponse[list[str]], summary="可用维度键")
def dim_keys(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[str]]:
    """返回已接入数据中出现过的维度键，供全景罗盘维度切换使用。"""
    return ApiResponse[list[str]](data=svc.available_dim_keys(db, tenant_id))


@router.get("/compass", response_model=ApiResponse[CompassOut], summary="全景罗盘")
def compass(
    granularity: str = Query("day", description="统计粒度 hour/day/week/month"),
    dim_key: Optional[str] = Query(None, description="拆解维度键，如 channel；不传只返回整体口径"),
    codes: Optional[str] = Query(None, description="指标编码，多个用逗号分隔；不传返回全部上线指标"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CompassOut]:
    """全景罗盘：全部上线指标的整体值、环比、趋势，叠加维度拆解与占比。"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    data = svc.compass(db, tenant_id, granularity=granularity, dim_key=dim_key, codes=code_list)
    return ApiResponse[CompassOut](data=data)


# ----------------------------------------------------- 指标定义 CRUD
@router.get("", response_model=ApiResponse[PageResult[MetricOut]], summary="指标列表")
def list_metrics(
    keyword: Optional[str] = Query(None, description="按编码/名称模糊搜索"),
    metric_status: Optional[str] = Query(None, alias="status", description="draft/online/offline"),
    category_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[MetricOut]]:
    total, rows = svc.list_metrics(db, tenant_id, keyword, metric_status, category_id, page, page_size)
    result = PageResult[MetricOut](
        total=total,
        page=page,
        page_size=page_size,
        items=[MetricOut.model_validate(r) for r in rows],
    )
    return ApiResponse[PageResult[MetricOut]](data=result)


@router.post("", response_model=ApiResponse[MetricOut], summary="新建指标")
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MetricOut]:
    if svc.get_metric(db, tenant_id, payload.code) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"指标编码已存在: {payload.code}")
    metric = svc.create_metric(db, tenant_id, payload)
    return ApiResponse[MetricOut](data=MetricOut.model_validate(metric))


@router.get("/{code}", response_model=ApiResponse[MetricOut], summary="指标详情")
def get_metric(
    code: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MetricOut]:
    metric = _get_metric_or_404(db, tenant_id, code)
    return ApiResponse[MetricOut](data=MetricOut.model_validate(metric))


@router.put("/{code}", response_model=ApiResponse[MetricOut], summary="更新指标")
def update_metric(
    code: str,
    payload: MetricUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MetricOut]:
    metric = _get_metric_or_404(db, tenant_id, code)
    metric = svc.update_metric(db, metric, payload)
    return ApiResponse[MetricOut](data=MetricOut.model_validate(metric))


@router.delete("/{code}", response_model=ApiResponse[dict], summary="删除指标")
def delete_metric(
    code: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    metric = _get_metric_or_404(db, tenant_id, code)
    svc.delete_metric(db, metric)
    return ApiResponse[dict](data={"code": code, "deleted": True})


# ----------------------------------------------------- 指标值
@router.post("/{code}/values", response_model=ApiResponse[dict], summary="写入指标值（覆盖）")
def upsert_values(
    code: str,
    payload: MetricValueBatchIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """批量写入。同一「时间+粒度+维度」重复写入即为覆盖。"""
    metric = _get_metric_or_404(db, tenant_id, code)
    count = svc.upsert_values(db, metric, payload.items)
    return ApiResponse[dict](data={"code": code, "affected": count})


@router.get("/{code}/values", response_model=ApiResponse[list[MetricValueOut]], summary="查询指标值明细")
def query_values(
    code: str,
    start: Optional[datetime] = Query(None, description="开始时间，ISO8601"),
    end: Optional[datetime] = Query(None, description="结束时间，ISO8601"),
    granularity: Optional[str] = Query(None, description="统计粒度"),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[MetricValueOut]]:
    metric = _get_metric_or_404(db, tenant_id, code)
    rows = svc.query_values(db, metric, start, end, granularity, None, limit)
    return ApiResponse[list[MetricValueOut]](data=[MetricValueOut.model_validate(r) for r in rows])


@router.get("/{code}/trend", response_model=ApiResponse[TrendOut], summary="指标趋势")
def metric_trend(
    code: str,
    start: Optional[datetime] = Query(None, description="开始时间，ISO8601"),
    end: Optional[datetime] = Query(None, description="结束时间，ISO8601"),
    granularity: str = Query("day", description="统计粒度 hour/day/week/month"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[TrendOut]:
    metric = _get_metric_or_404(db, tenant_id, code)
    data = svc.trend(db, metric, start=start, end=end, granularity=granularity)
    return ApiResponse[TrendOut](data=data)
