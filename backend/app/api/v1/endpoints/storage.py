"""存储适配层运维接口：引擎总览、路由识别、全文检索、一致性对账。

路由前缀：/storage（见 app/api/v1/router.py，需 storage 模块权限）
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.storage import consistency as consistency_adapter
from app.storage import routing as routing_adapter
from app.storage.registry import (
    backfill_metric_values,
    bootstrap_storage,
    reindex_documents,
    search_documents,
    storage_overview,
)

router = APIRouter()


# ============================================================ 请求模型
class IdentifyIn(BaseModel):
    """数据源类型识别请求。"""

    ds_type: Optional[str] = Field(
        default=None,
        description="数据源类型，如 mysql / clickhouse / csv（兼容别名 data_source_type / type）",
        validation_alias=AliasChoices("ds_type", "data_source_type", "type", "source_type"),
    )
    file_ext: Optional[str] = Field(default=None, description="文件后缀，如 csv / pdf / png")
    content: Optional[str] = Field(default=None, description="内容特征描述或样本文本")


class SearchIn(BaseModel):
    """全文检索请求。"""

    q: str = Field(..., description="检索关键词")
    doc_type: Optional[str] = Field(default=None, description="限定文档类型，如 metric / datasource")
    limit: Optional[int] = Field(default=None, ge=1, le=200, description="返回条数上限")


class ReindexIn(BaseModel):
    """重建全文索引请求。"""

    scope: Optional[list[str]] = Field(default=None, description="限定重建范围，如 ['metric','datasource']")


class ConsistencyIn(BaseModel):
    """一致性对账请求。"""

    scopes: Optional[list[str]] = Field(default=None, description="对账范围，缺省为全部 scope")
    auto_repair: bool = Field(default=False, description="是否自动修复缺失/不一致条目")


# ============================================================ 总览
@router.get("/overview", response_model=ApiResponse[dict], summary="存储适配层总览")
def overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    """引擎能力矩阵 + 各类型规模统计 + 路由规则 + 样例识别。"""
    return ApiResponse[dict](data=storage_overview(db, tenant_id=tenant_id))


@router.post("/bootstrap", response_model=ApiResponse[dict], summary="幂等初始化存储适配层")
def bootstrap(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    """受管目录 + 内置路由规则 + 时序月分区，可在容器内重复执行。"""
    result = bootstrap_storage(db)
    result["overview"] = storage_overview(db, tenant_id=tenant_id)
    return ApiResponse[dict](data=result)


# ============================================================ 路由识别
@router.get("/routing/rules", response_model=ApiResponse[dict], summary="路由规则列表")
def list_rules(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    """内置规则 + 当前租户自定义规则 + 各类型引擎映射。"""
    return ApiResponse[dict](data=routing_adapter.route_overview(db, tenant_id=tenant_id))


@router.post("/routing/identify", response_model=ApiResponse[dict], summary="识别数据类型并给出目标存储引擎")
def identify(
    payload: IdentifyIn = Body(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](
        data=routing_adapter.identify(
            db,
            ds_type=payload.ds_type,
            file_ext=payload.file_ext,
            content=payload.content,
            tenant_id=tenant_id,
        )
    )


# ============================================================ 全文检索
@router.get("/search", response_model=ApiResponse[dict], summary="全文检索")
def search(
    q: str = Query(..., min_length=1, description="检索关键词"),
    doc_type: Optional[str] = Query(default=None, description="限定文档类型"),
    limit: Optional[int] = Query(default=None, ge=1, le=200, description="返回条数上限"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](
        data=search_documents(db, tenant_id=tenant_id, q=q, doc_type=doc_type, limit=limit)
    )


@router.post("/search/reindex", response_model=ApiResponse[dict], summary="重建全文检索索引")
def reindex(
    payload: ReindexIn = Body(default=ReindexIn()),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    result = reindex_documents(db, tenant_id=tenant_id, scope=payload.scope)
    probe = search_documents(db, tenant_id=tenant_id, q="指标", limit=5)
    return ApiResponse[dict](data={"reindex": result, "probe": probe})


# ============================================================ 存量回填
@router.post("/backfill", response_model=ApiResponse[dict], summary="回填存量指标值到时序分区表")
def backfill(
    batch_size: Optional[int] = Query(default=None, ge=100, le=10000, description="单批行数"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    """幂等回填：仅补时序表中缺失的指标值，已有记录不覆盖。"""
    return ApiResponse[dict](data=backfill_metric_values(db, batch_size=batch_size))


# ============================================================ 一致性对账
@router.post("/consistency/run", response_model=ApiResponse[dict], summary="执行跨存储一致性对账")
def run_consistency(
    request: Request,
    payload: ConsistencyIn = Body(default=ConsistencyIn()),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    operator = getattr(request.state, "username", None)
    return ApiResponse[dict](
        data=consistency_adapter.run_checks(
            db,
            tenant_id=tenant_id,
            scopes=payload.scopes,
            auto_repair=payload.auto_repair,
            operator=operator,
            persist=True,
        )
    )


@router.get("/consistency/recent", response_model=ApiResponse[list[dict]], summary="最近对账记录")
def recent_consistency(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[list[dict]]:
    return ApiResponse[list[dict]](
        data=consistency_adapter.recent_checks(db, tenant_id=tenant_id, limit=limit)
    )
