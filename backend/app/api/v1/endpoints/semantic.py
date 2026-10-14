"""语义层接口：Text2Metric 自然语言问数 + 编译 SQL 调试。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.models.base import get_db
from app.models.metric import Metric
from app.schemas.common import ApiResponse
from app.semantic import compiler, service
from app.semantic.schemas.semantic import (
    SemanticAskRequest,
    SemanticAskResponse,
    SemanticCompileRequest,
    SemanticCompileResponse,
)

router = APIRouter()


@router.post("/ask", response_model=ApiResponse[SemanticAskResponse], summary="自然语言问数（Text2Metric）")
def ask(
    payload: SemanticAskRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[SemanticAskResponse]:
    """把自然语言问题编译为指标查询并执行，返回各指标时序结果。"""
    data = service.ask(db, tenant_id, payload.question, limit=payload.limit)
    return ApiResponse[SemanticAskResponse](data=SemanticAskResponse.model_validate(data))


@router.post("/compile", response_model=ApiResponse[SemanticCompileResponse], summary="编译指标 SQL（调试）")
def compile_sql(
    payload: SemanticCompileRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[SemanticCompileResponse]:
    """仅编译不执行：返回指标将被翻译成的 SQL（内部/外部/派生模式）。"""
    metric = (
        db.query(Metric)
        .filter(
            Metric.code == payload.metric_code,
            Metric.status == "online",
            Metric.tenant_id == tenant_id,
        )
        .first()
    )
    if metric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"指标不存在或已停用: {payload.metric_code}")
    try:
        compiled = compiler.compile_for_metric(db, metric, tenant_id=tenant_id)
    except compiler.SemanticCompileError as exc:
        return ApiResponse[SemanticCompileResponse](
            data=SemanticCompileResponse(ok=False, error=str(exc), metric_code=payload.metric_code)
        )
    mode = "derived" if compiled.derived else ("external" if not compiled.internal else "internal")
    return ApiResponse[SemanticCompileResponse](
        data=SemanticCompileResponse(
            ok=True,
            metric_code=payload.metric_code,
            mode=mode,
            dialect=compiled.dialect,
            sql=compiled.sql,
            params=compiled.params,
        )
    )
