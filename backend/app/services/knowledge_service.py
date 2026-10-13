"""M11 企业知识库服务：知识文档 CRUD / 检索 / 引用热度登记 / 知识库管理 / 问答。

链路：端点 -> create_doc / update_doc / list_docs / ... -> 校验类型/状态/来源 ->
写入 oc_knowledge_doc；search_docs 供 Agent（M12）检索引用（仅已发布）；
register_refs 登记引用轨迹到 oc_knowledge_ref_log 并累计 ref_count 热度，
形成「知识沉淀 → 引用 → 反馈」的进化闭环。
知识库（KnowledgeBase）挂载一批文档与上传文件，ask_base 做检索式问答：
先在库内文件与已发布文档中召回片段，再交给 LLM 生成回答；LLM 不可用时降级返回片段拼装。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, settings
from app.models.knowledge import (
    KB_FILE_STATUSES,
    KB_STATUSES,
    KNOWLEDGE_STATUSES,
    KNOWLEDGE_TYPES,
    REF_SOURCES,
    KnowledgeBase,
    KnowledgeBaseFile,
    KnowledgeDoc,
    KnowledgeRefLog,
)
from app.schemas.knowledge import (
    KnowledgeAskIn,
    KnowledgeBaseIn,
    KnowledgeBasePatch,
    KnowledgeDocIn,
    KnowledgeDocPatch,
    KnowledgeQueryIn,
    KnowledgeRefIn,
)
from app.services.ai.llm_client import LLMClient, LLMError

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


# ============ 知识库管理 / 文件 / 问答（M11 补全，追加于文件末尾） ============


def _base_dir(tenant_id: int, base_id: int) -> Path:
    """知识库文件根目录：data/knowledge/{tenant}/{base}/。"""
    return BASE_DIR / "data" / "knowledge" / str(tenant_id) / str(base_id)


def _base_to_dict(base: KnowledgeBase) -> dict[str, Any]:
    return {
        "id": base.id,
        "tenant_id": base.tenant_id,
        "name": base.name,
        "description": base.description,
        "config": base.config or {},
        "status": base.status,
        "created_at": base.created_at.isoformat() if base.created_at else None,
        "updated_at": base.updated_at.isoformat() if base.updated_at else None,
    }


def _file_to_dict(f: KnowledgeBaseFile) -> dict[str, Any]:
    return {
        "id": f.id,
        "base_id": f.base_id,
        "file_name": f.file_name,
        "file_type": f.file_type,
        "size_bytes": f.size_bytes,
        "uploader": f.uploader,
        "status": f.status,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def create_base(db: Session, tenant_id: int, payload: KnowledgeBaseIn) -> dict[str, Any]:
    """新建知识库。"""
    name = payload.name.strip()
    if not name:
        raise KnowledgeServiceError("知识库名称不能为空")
    exists = db.scalar(
        select(KnowledgeBase.id).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.name == name,
            KnowledgeBase.status == "active",
        )
    )
    if exists is not None:
        raise KnowledgeServiceError("同名知识库已存在")
    base = KnowledgeBase(
        tenant_id=tenant_id,
        name=name,
        description=payload.description,
        config=payload.config,
        status="active",
    )
    db.add(base)
    db.commit()
    db.refresh(base)
    _base_dir(tenant_id, base.id).mkdir(parents=True, exist_ok=True)
    return _base_to_dict(base)


def list_bases(
    db: Session,
    tenant_id: int,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    """列出知识库，支持名称关键词与状态过滤，附带文档/文件计数。"""
    stmt = select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    if status:
        if status not in KB_STATUSES:
            raise KnowledgeServiceError(f"status 仅支持 {KB_STATUSES}")
        stmt = stmt.where(KnowledgeBase.status == status)
    if keyword:
        stmt = stmt.where(KnowledgeBase.name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(KnowledgeBase.created_at.desc())
    rows = db.scalars(stmt).all()
    result: list[dict[str, Any]] = []
    for base in rows:
        item = _base_to_dict(base)
        item["doc_count"] = int(
            db.scalar(
                select(func.count(KnowledgeDoc.id)).where(
                    KnowledgeDoc.tenant_id == tenant_id,
                    KnowledgeDoc.status == "published",
                )
            )
            or 0
        )
        item["file_count"] = int(
            db.scalar(
                select(func.count(KnowledgeBaseFile.id)).where(
                    KnowledgeBaseFile.base_id == base.id,
                    KnowledgeBaseFile.status == "active",
                )
            )
            or 0
        )
        result.append(item)
    return result


def get_base(db: Session, tenant_id: int, base_id: int) -> dict[str, Any]:
    """获取单个知识库详情（含文件列表与文档数）。"""
    base = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if base is None:
        raise KnowledgeServiceError("知识库不存在")
    item = _base_to_dict(base)
    item["doc_count"] = int(
        db.scalar(
            select(func.count(KnowledgeDoc.id)).where(
                KnowledgeDoc.tenant_id == tenant_id,
                KnowledgeDoc.status == "published",
            )
        )
        or 0
    )
    item["files"] = [
        _file_to_dict(f)
        for f in db.scalars(
            select(KnowledgeBaseFile)
            .where(
                KnowledgeBaseFile.base_id == base_id,
                KnowledgeBaseFile.status == "active",
            )
            .order_by(KnowledgeBaseFile.created_at.desc())
        ).all()
    ]
    return item


def update_base(
    db: Session, tenant_id: int, base_id: int, patch: KnowledgeBasePatch
) -> dict[str, Any]:
    """更新知识库名称/描述/配置/状态。"""
    base = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if base is None:
        raise KnowledgeServiceError("知识库不存在")
    if patch.name is not None:
        name = patch.name.strip()
        if not name:
            raise KnowledgeServiceError("知识库名称不能为空")
        dup = db.scalar(
            select(KnowledgeBase.id).where(
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.name == name,
                KnowledgeBase.status == "active",
                KnowledgeBase.id != base_id,
            )
        )
        if dup is not None:
            raise KnowledgeServiceError("同名知识库已存在")
        base.name = name
    if patch.description is not None:
        base.description = patch.description
    if patch.config is not None:
        base.config = patch.config
    if patch.status is not None:
        if patch.status not in KB_STATUSES:
            raise KnowledgeServiceError(f"status 仅支持 {KB_STATUSES}")
        base.status = patch.status
    db.commit()
    db.refresh(base)
    return _base_to_dict(base)


def delete_base(db: Session, tenant_id: int, base_id: int) -> None:
    """删除知识库（软删状态 disabled，保留历史记录）。"""
    base = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if base is None:
        raise KnowledgeServiceError("知识库不存在")
    base.status = "disabled"
    db.commit()


def upload_base_file(
    db: Session,
    tenant_id: int,
    base_id: int,
    file_name: str,
    content: bytes,
    uploader: str = "system",
) -> dict[str, Any]:
    """上传文件到知识库：写入磁盘 data/knowledge/{tenant}/{base}/，登记元数据。"""
    base = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if base is None:
        raise KnowledgeServiceError("知识库不存在")
    if not file_name or not content:
        raise KnowledgeServiceError("文件名与文件内容不能为空")
    name = Path(file_name).name
    ext = Path(name).suffix.lstrip(".").lower() or "other"
    digest = hashlib.sha256(content).hexdigest()
    root = _base_dir(tenant_id, base_id)
    root.mkdir(parents=True, exist_ok=True)
    # 同名文件覆盖：先软删旧记录，再落新文件
    old = db.scalars(
        select(KnowledgeBaseFile).where(
            KnowledgeBaseFile.base_id == base_id,
            KnowledgeBaseFile.file_name == name,
            KnowledgeBaseFile.status == "active",
        )
    ).all()
    for o in old:
        o.status = "removed"
    dest = root / f"{base_id}_{int(datetime.now().timestamp() * 1000)}_{name}"
    dest.write_bytes(content)
    f = KnowledgeBaseFile(
        tenant_id=tenant_id,
        base_id=base_id,
        file_name=name,
        file_path=str(dest),
        file_type=ext,
        size_bytes=len(content),
        uploader=uploader,
        status="active",
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return _file_to_dict(f)


def list_base_files(
    db: Session, tenant_id: int, base_id: int
) -> list[dict[str, Any]]:
    """列出知识库内文件。"""
    base = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if base is None:
        raise KnowledgeServiceError("知识库不存在")
    rows = db.scalars(
        select(KnowledgeBaseFile)
        .where(
            KnowledgeBaseFile.base_id == base_id,
            KnowledgeBaseFile.status == "active",
        )
        .order_by(KnowledgeBaseFile.created_at.desc())
    ).all()
    return [_file_to_dict(f) for f in rows]


def delete_base_file(
    db: Session, tenant_id: int, base_id: int, file_id: int
) -> None:
    """删除知识库文件（软删 + 移除磁盘文件）。"""
    f = db.scalar(
        select(KnowledgeBaseFile).where(
            KnowledgeBaseFile.id == file_id,
            KnowledgeBaseFile.base_id == base_id,
            KnowledgeBaseFile.tenant_id == tenant_id,
            KnowledgeBaseFile.status == "active",
        )
    )
    if f is None:
        raise KnowledgeServiceError("文件不存在")
    f.status = "removed"
    db.commit()
    try:
        path = Path(f.file_path)
        if path.is_file():
            path.unlink(missing_ok=True)
    except OSError:
        pass  # 磁盘清理失败不影响登记状态


_TEXT_EXTS = {"txt", "md", "csv", "json", "yaml", "yml", "log", "html", "xml", "py", "ts", "js", "vue"}


def _collect_base_chunks(db: Session, base_id: int, top_k: int) -> list[dict[str, Any]]:
    """从库内 active 文件与已发布文档中召回文本片段（简单截断分段）。"""
    chunks: list[dict[str, Any]] = []
    files = db.scalars(
        select(KnowledgeBaseFile).where(
            KnowledgeBaseFile.base_id == base_id,
            KnowledgeBaseFile.status == "active",
        )
    ).all()
    for f in files:
        if f.file_type not in _TEXT_EXTS:
            continue
        try:
            text = Path(f.file_path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue
        # 每 1200 字符切成一段
        for i in range(0, len(text), 1200):
            seg = text[i : i + 1200].strip()
            if seg:
                chunks.append({"kind": "file", "title": f.file_name, "content": seg})
    base_tenant = db.scalar(
        select(KnowledgeBase.tenant_id).where(KnowledgeBase.id == base_id)
    )
    docs = db.scalars(
        select(KnowledgeDoc).where(
            KnowledgeDoc.tenant_id == base_tenant,
            KnowledgeDoc.status == "published",
        )
    ).all()
    # 文档召回：仅取该库租户下的全部已发布文档，按标题/摘要做简单相关排序（片段截断）
    scored: list[tuple[int, KnowledgeDoc]] = []
    for doc in docs:
        hay = f"{doc.title} {doc.summary or ''} {doc.content or ''}"
        # 简单关键词命中计分：与文件名无关，按片段长度兜底
        scored.append((min(len(doc.content or ""), 4000), doc))
    for _, doc in sorted(scored, key=lambda x: x[0], reverse=True)[: max(top_k, 3)]:
        text = (doc.summary or "") if (doc.summary or "").strip() else (doc.content or "")[:2000]
        if text.strip():
            chunks.append(
                {
                    "kind": "doc",
                    "title": doc.title,
                    "content": text[:2000],
                    "doc_id": doc.id,
                }
            )
    return chunks[: max(top_k * 2, 6)]


def ask_base(
    db: Session, tenant_id: int, base_id: int, payload: KnowledgeAskIn
) -> dict[str, Any]:
    """知识库检索式问答：库内文件 + 已发布文档召回片段，交给 LLM 生成回答；不可用则降级拼装。"""
    base = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if base is None:
        raise KnowledgeServiceError("知识库不存在")
    chunks = _collect_base_chunks(db, base_id, payload.top_k)
    sources = [
        {
            "title": c.get("title", ""),
            "kind": c.get("kind", ""),
            "content": c.get("content", "")[:400],
        }
        for c in chunks
    ]
    fallback = True
    model_name: Optional[str] = None
    if chunks:
        context = "\n\n".join(
            f"[{c['kind']}] {c['title']}：\n{c['content'][:800]}" for c in chunks[: payload.top_k]
        )
        messages = [
            {
                "role": "system",
                "content": "你是运营智脑（OpsCompass）企业知识库问答助手。仅依据给定的知识片段作答；"
                "片段不足时明确说明，不要编造。回答使用中文，简洁、结构化。",
            },
            {
                "role": "user",
                "content": f"知识库《{base.name}》内检索到的片段：\n{context}\n\n问题：{payload.question}",
            },
        ]
        try:
            result = LLMClient().chat(messages)
            answer = result.text
            model_name = result.model
            fallback = False
        except LLMError:
            parts = [f"（来自「{c['title']}」）{c['content'][:200]}" for c in chunks[: payload.top_k]]
            answer = "模型暂不可用，以下为知识库检索到的相关片段：\n" + "\n".join(parts)
    else:
        answer = "知识库内暂无可用内容，请先上传文件或发布知识文档后再提问。"
    return {
        "answer": answer,
        "fallback": fallback,
        "model": model_name,
        "sources": sources,
    }

