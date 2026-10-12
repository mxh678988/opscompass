"""M11 企业知识库接口：知识文档沉淀 / 列表 / 详情 / 检索 / 引用热度登记。

路由前缀 /knowledge（注册见 app/api/v1/router.py，需 knowledge 模块权限）：
- 读操作（列表 / 详情 / 检索）：knowledge:view
- 写操作（沉淀 / 编辑 / 引用登记）：knowledge:create / knowledge:update
- 删除：knowledge:delete
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.common import ApiResponse
from app.schemas.knowledge import (
    KnowledgeDocIn,
    KnowledgeDocPatch,
    KnowledgeQueryIn,
    KnowledgeRefIn,
)
from app.services import knowledge_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/docs", response_model=ApiResponse[dict], summary="沉淀知识文档")
def create_doc(
    payload: KnowledgeDocIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
):
    try:
        data = svc.create_doc(db, tenant_id, payload, operator=user.username)
    except svc.KnowledgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="知识文档已沉淀")


@router.get("/docs", response_model=ApiResponse[dict], summary="知识文档列表（分页过滤）")
def list_docs(
    keyword: str | None = Query(default=None, description="关键词（标题/摘要/正文/场景）"),
    doc_type: str | None = Query(default=None, description="限定类型"),
    status: str | None = Query(default=None, description="限定状态"),
    scenario: str | None = Query(default=None, description="限定适用场景"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.list_docs(
            db,
            tenant_id,
            keyword=keyword,
            doc_type=doc_type,
            status=status,
            scenario=scenario,
            page=page,
            size=size,
        )
    except svc.KnowledgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data)


@router.get("/docs/{doc_id}", response_model=ApiResponse[dict], summary="知识文档详情")
def read_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = svc.get_doc(db, tenant_id, doc_id)
    if data is None:
        raise HTTPException(status_code=404, detail="知识文档不存在或不属于当前租户")
    return ApiResponse[dict](data=data)


@router.patch("/docs/{doc_id}", response_model=ApiResponse[dict], summary="修改知识文档")
def patch_doc(
    doc_id: int,
    payload: KnowledgeDocPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.update_doc(db, tenant_id, doc_id, payload)
    except svc.KnowledgeServiceError as exc:
        raise _fail(exc)
    if data is None:
        raise HTTPException(status_code=404, detail="知识文档不存在或不属于当前租户")
    return ApiResponse[dict](data=data, message="知识文档已更新")


@router.delete("/docs/{doc_id}", response_model=ApiResponse[dict], summary="删除知识文档")
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = svc.delete_doc(db, tenant_id, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识文档不存在或不属于当前租户")
    return ApiResponse[dict](data={"deleted": True}, message="知识文档已删除")


@router.get("/search", response_model=ApiResponse[dict], summary="检索知识库（Agent 引用入口）")
def search_docs(
    keyword: str = Query(default="", description="关键词（标题/正文/摘要/标签/场景）"),
    doc_type: str | None = Query(default=None, description="限定类型"),
    scenario: str | None = Query(default=None, description="限定适用场景"),
    limit: int = Query(default=5, ge=1, le=50, description="返回条数"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.search_docs(
            db,
            tenant_id,
            KnowledgeQueryIn(
                keyword=keyword,
                doc_type=doc_type,
                scenario=scenario,
                limit=limit,
            ),
        )
    except svc.KnowledgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data)


@router.post("/refs", response_model=ApiResponse[dict], summary="登记知识引用（累计热度）")
def register_refs(
    payload: KnowledgeRefIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        data = svc.register_refs(db, tenant_id, payload)
    except svc.KnowledgeServiceError as exc:
        raise _fail(exc)
    return ApiResponse[dict](data=data, message="引用已登记")
