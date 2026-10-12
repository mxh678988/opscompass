"""M11 企业知识库服务：知识文档 CRUD / 检索 / 引用热度登记。

链路：端点 -> create_doc / update_doc / list_docs / ... -> 校验类型/状态/来源 ->
写入 oc_knowledge_doc；search_docs 供 Agent（M12）检索引用（仅已发布）；
register_refs 登记引用轨迹到 oc_knowledge_ref_log 并累计 ref_count 热度，
形成「知识沉淀 → 引用 → 反馈」的进化闭环。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from app.models.knowledge import (
    KNOWLEDGE_STATUSES,
    KNOWLEDGE_TYPES,
    REF_SOURCES,
    KnowledgeDoc,
    KnowledgeRefLog,
)
from app.schemas.knowledge import (
    KnowledgeDocIn,
    KnowledgeDocPatch,
    KnowledgeQueryIn,
    KnowledgeRefIn,
)

# 文档来源（区别于引用来源 REF_SOURCES）
DOC_SOURCES = ("manual", "insight", "learning", "agent")


class KnowledgeServiceError(RuntimeError):
    """知识库服务业务异常（参数 / 状态非法）。"""


def _now() -> datetime:
    return datetime.now()


def _check_doc_type(doc_type: str) -> None:
    if doc_type not in KNOWLEDGE_TYPES:
        raise KnowledgeServiceError(
            f"不支持的知识类型: {doc_type}（可选 {' / '.join(KNOWLEDGE_TYPES)}）"
        )


def _check_status(status: str) -> None:
    if status not in KNOWLEDGE_STATUSES:
        raise KnowledgeServiceError(
            f"不支持的文档状态: {status}（可选 {' / '.join(KNOWLEDGE_STATUSES)}）"
        )


def _check_doc_source(source: str) -> None:
    if source not in DOC_SOURCES:
        raise KnowledgeServiceError(
            f"不支持的文档来源: {source}（可选 {' / '.join(DOC_SOURCES)}）"
        )


def _check_ref_source(source: str) -> None:
    if source not in REF_SOURCES:
        raise KnowledgeServiceError(
            f"不支持的引用来源: {source}（可选 {' / '.join(REF_SOURCES)}）"
        )


def _apply_status_ts(doc: KnowledgeDoc, status: str) -> None:
    """状态流转时维护发布时间。"""
    if status == "published" and doc.published_at is None:
        doc.published_at = _now()


def create_doc(
    db: Session,
    tenant_id: int,
    payload: KnowledgeDocIn,
    operator: str = "system",
) -> dict[str, Any]:
    """沉淀一条知识文档。"""
    _check_doc_type(payload.doc_type)
    _check_status(payload.status)
    _check_doc_source(payload.source)

    doc = KnowledgeDoc(
        tenant_id=tenant_id,
        title=payload.title,
        doc_type=payload.doc_type,
        status=payload.status,
        content=payload.content,
        summary=payload.summary,
        tags=payload.tags,
        scenario=payload.scenario,
        source=payload.source,
        ref_count=0,
        author=payload.author or operator,
    )
    _apply_status_ts(doc, doc.status)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc_to_dict(doc)


def update_doc(
    db: Session,
    tenant_id: int,
    doc_id: int,
    payload: KnowledgeDocPatch,
) -> Optional[dict[str, Any]]:
    """修改知识文档（部分字段）。"""
    doc = db.scalar(
        select(KnowledgeDoc).where(
            KnowledgeDoc.id == doc_id,
            KnowledgeDoc.tenant_id == tenant_id,
        )
    )
    if doc is None:
        return None

    if payload.title is not None:
        doc.title = payload.title
    if payload.doc_type is not None:
        _check_doc_type(payload.doc_type)
        doc.doc_type = payload.doc_type
    if payload.status is not None:
        _check_status(payload.status)
        _apply_status_ts(doc, payload.status)
        doc.status = payload.status
    if payload.content is not None:
        doc.content = payload.content
    if payload.summary is not None:
        doc.summary = payload.summary
    if payload.tags is not None:
        doc.tags = payload.tags
    if payload.scenario is not None:
        doc.scenario = payload.scenario
    db.commit()
    db.refresh(doc)
    return doc_to_dict(doc)


def get_doc(db: Session, tenant_id: int, doc_id: int) -> Optional[dict[str, Any]]:
    doc = db.scalar(
        select(KnowledgeDoc).where(
            KnowledgeDoc.id == doc_id,
            KnowledgeDoc.tenant_id == tenant_id,
        )
    )
    if doc is None:
        return None
    return doc_to_dict(doc)


def list_docs(
    db: Session,
    tenant_id: int,
    *,
    keyword: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    scenario: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """知识文档列表：分页 + doc_type/status/keyword/scenario 过滤。"""
    if doc_type is not None:
        _check_doc_type(doc_type)
    if status is not None:
        _check_status(status)

    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    conditions = [KnowledgeDoc.tenant_id == tenant_id]
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(
                KnowledgeDoc.title.like(like),
                KnowledgeDoc.summary.like(like),
                KnowledgeDoc.content.like(like),
                KnowledgeDoc.scenario.like(like),
            )
        )
    if doc_type:
        conditions.append(KnowledgeDoc.doc_type == doc_type)
    if status:
        conditions.append(KnowledgeDoc.status == status)
    if scenario:
        conditions.append(KnowledgeDoc.scenario.like(f"%{scenario}%"))

    total = (
        db.scalar(
            select(func.count()).select_from(KnowledgeDoc).where(*conditions)
        )
        or 0
    )
    rows = (
        db.execute(
            select(KnowledgeDoc)
            .where(*conditions)
            .order_by(KnowledgeDoc.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "page": page,
        "page_size": size,
        "items": [doc_to_dict(d) for d in rows],
    }


def delete_doc(db: Session, tenant_id: int, doc_id: int) -> bool:
    """删除知识文档；引用日志随外键 CASCADE 清理（生产库）。"""
    doc = db.scalar(
        select(KnowledgeDoc).where(
            KnowledgeDoc.id == doc_id,
            KnowledgeDoc.tenant_id == tenant_id,
        )
    )
    if doc is None:
        return False
    db.delete(doc)
    db.commit()
    return True


def search_docs(
    db: Session,
    tenant_id: int,
    payload: KnowledgeQueryIn,
) -> dict[str, Any]:
    """检索知识库（Agent 引用入口）。

    仅返回已发布（published）文档，避免 Agent 引用草稿/归档内容；
    按热度（ref_count）优先排序，兼顾关键词/类型/场景过滤。
    """
    if payload.doc_type is not None:
        _check_doc_type(payload.doc_type)

    conditions = [
        KnowledgeDoc.tenant_id == tenant_id,
        KnowledgeDoc.status == "published",
    ]
    if payload.keyword:
        like = f"%{payload.keyword}%"
        conditions.append(
            or_(
                KnowledgeDoc.title.like(like),
                KnowledgeDoc.summary.like(like),
                KnowledgeDoc.content.like(like),
                KnowledgeDoc.tags.cast(String).like(like),
                KnowledgeDoc.scenario.like(like),
            )
        )
    if payload.doc_type:
        conditions.append(KnowledgeDoc.doc_type == payload.doc_type)
    if payload.scenario:
        conditions.append(KnowledgeDoc.scenario.like(f"%{payload.scenario}%"))

    total = (
        db.scalar(
            select(func.count()).select_from(KnowledgeDoc).where(*conditions)
        )
        or 0
    )
    rows = (
        db.execute(
            select(KnowledgeDoc)
            .where(*conditions)
            .order_by(KnowledgeDoc.ref_count.desc(), KnowledgeDoc.id.desc())
            .limit(payload.limit)
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "limit": payload.limit,
        "items": [doc_to_dict(d) for d in rows],
    }


def register_refs(
    db: Session,
    tenant_id: int,
    payload: KnowledgeRefIn,
) -> dict[str, Any]:
    """登记一次知识引用：写引用日志并累计 ref_count 热度。

    只统计当前租户下存在（且未归档）的文档；缺失文档计入 missing 并跳过；
    全部缺失时抛错，避免无效引用。
    """
    _check_ref_source(payload.source)

    docs: list[KnowledgeDoc] = []
    missing: list[int] = []
    seen: set[int] = set()
    for doc_id in payload.doc_ids:
        if doc_id in seen:
            continue
        seen.add(doc_id)
        doc = db.scalar(
            select(KnowledgeDoc).where(
                KnowledgeDoc.id == doc_id,
                KnowledgeDoc.tenant_id == tenant_id,
            )
        )
        if doc is None:
            missing.append(doc_id)
            continue
        docs.append(doc)

    if not docs:
        raise KnowledgeServiceError(
            "引用的知识文档不存在或不属于当前租户"
        )

    for doc in docs:
        doc.ref_count = int(doc.ref_count or 0) + 1
        db.add(
            KnowledgeRefLog(
                tenant_id=tenant_id,
                doc_id=doc.id,
                source=payload.source,
                ref_key=payload.ref_key,
                note=payload.note,
            )
        )
    db.commit()

    items = [
        {"doc_id": d.id, "title": d.title, "ref_count": int(d.ref_count or 0)}
        for d in docs
    ]
    return {
        "referenced": len(items),
        "missing": missing,
        "items": items,
    }


def doc_to_dict(doc: KnowledgeDoc) -> dict[str, Any]:
    return {
        "id": doc.id,
        "tenant_id": doc.tenant_id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "content": doc.content,
        "summary": doc.summary,
        "tags": doc.tags,
        "scenario": doc.scenario,
        "source": doc.source,
        "ref_count": int(doc.ref_count or 0),
        "author": doc.author,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
