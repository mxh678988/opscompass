"""M13 API 申请助手服务层：平台模板管理与代申请任务状态机。

- 模板 CRUD：电商/网站平台申请入口与表单字段映射沉淀；
- 创建申请任务：账号口令以 AES 密文（app/core/crypto.py）写入 credentials_ref，
  严禁明文密码落库；
- 状态机：pending -> submitted -> awaiting_manual -> done/failed，
  需人工验证/付费/资质审核的平台 submitted 后自动进入 awaiting_manual 等待用户介入；
  终态 done/failed 不可再流转。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt
from app.models.api_bridge import (
    API_TASK_STATUSES,
    ApiApplyTask,
    ApiPlatformTemplate,
)
from app.schemas.api_bridge import (
    ApiApplyTaskIn,
    ApiApplyTaskPatch,
    ApiPlatformTemplateIn,
    ApiPlatformTemplatePatch,
)


class ApiBridgeServiceError(Exception):
    """API 申请助手业务错误。"""


def _now() -> datetime:
    return datetime.now()


# ---------------------------------------------------------------- 平台模板

def create_template(
    db: Session, tenant_id: int, payload: ApiPlatformTemplateIn, operator: str = "system"
) -> ApiPlatformTemplate:
    if payload.category not in ("ecommerce", "website", "other"):
        raise ApiBridgeServiceError(f"非法平台分类: {payload.category}")
    tpl = ApiPlatformTemplate(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        apply_url=payload.apply_url.strip(),
        field_schema=payload.field_schema,
        requires_manual=payload.requires_manual,
        category=payload.category,
        enabled=payload.enabled,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def update_template(
    db: Session,
    tenant_id: int,
    template_id: int,
    payload: ApiPlatformTemplatePatch,
    operator: str = "system",
) -> ApiPlatformTemplate:
    tpl = db.get(ApiPlatformTemplate, template_id)
    if tpl is None or tpl.tenant_id != tenant_id:
        raise ApiBridgeServiceError("平台模板不存在或无权访问")
    if payload.category is not None and payload.category not in ("ecommerce", "website", "other"):
        raise ApiBridgeServiceError(f"非法平台分类: {payload.category}")
    if payload.name is not None:
        tpl.name = payload.name.strip()
    if payload.apply_url is not None:
        tpl.apply_url = payload.apply_url.strip()
    if payload.field_schema is not None:
        tpl.field_schema = payload.field_schema
    if payload.requires_manual is not None:
        tpl.requires_manual = payload.requires_manual
    if payload.category is not None:
        tpl.category = payload.category
    if payload.enabled is not None:
        tpl.enabled = payload.enabled
    tpl.updated_at = _now()
    db.commit()
    db.refresh(tpl)
    return tpl


def list_templates(
    db: Session,
    tenant_id: int,
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    stmt = select(ApiPlatformTemplate).where(ApiPlatformTemplate.tenant_id == tenant_id)
    if category:
        stmt = stmt.where(ApiPlatformTemplate.category == category)
    if enabled is not None:
        stmt = stmt.where(ApiPlatformTemplate.enabled == enabled)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(ApiPlatformTemplate.name.like(like), ApiPlatformTemplate.apply_url.like(like)))
    count_conds = [ApiPlatformTemplate.tenant_id == tenant_id]
    if category:
        count_conds.append(ApiPlatformTemplate.category == category)
    if enabled is not None:
        count_conds.append(ApiPlatformTemplate.enabled == enabled)
    if keyword:
        like = f"%{keyword.strip()}%"
        count_conds.append(
            or_(ApiPlatformTemplate.name.like(like), ApiPlatformTemplate.apply_url.like(like))
        )
    total = db.scalar(
        select(func.count()).select_from(ApiPlatformTemplate).where(*count_conds)
    )
    rows = db.scalars(stmt.order_by(ApiPlatformTemplate.id.desc()).offset((page - 1) * size).limit(size)).all()
    return {"items": [t for t in rows], "total": total or 0, "page": page, "size": size}


def get_template(db: Session, tenant_id: int, template_id: int) -> ApiPlatformTemplate:
    tpl = db.get(ApiPlatformTemplate, template_id)
    if tpl is None or tpl.tenant_id != tenant_id:
        raise ApiBridgeServiceError("平台模板不存在或无权访问")
    return tpl


def delete_template(db: Session, tenant_id: int, template_id: int) -> None:
    tpl = db.get(ApiPlatformTemplate, template_id)
    if tpl is None or tpl.tenant_id != tenant_id:
        raise ApiBridgeServiceError("平台模板不存在或无权访问")
    db.delete(tpl)
    db.commit()


# ---------------------------------------------------------------- 申请任务

def create_apply_task(
    db: Session, tenant_id: int, payload: ApiApplyTaskIn, operator: str = "system"
) -> ApiApplyTask:
    """创建代申请任务：密码 AES 加密落库，严禁明文。"""
    platform_name = payload.platform.strip()
    requires_manual = False
    if payload.platform_id is not None:
        tpl = db.get(ApiPlatformTemplate, payload.platform_id)
        if tpl is None or tpl.tenant_id != tenant_id:
            raise ApiBridgeServiceError("平台模板不存在或无权访问")
        if not tpl.enabled:
            raise ApiBridgeServiceError("平台模板已停用")
        platform_name = tpl.name
        requires_manual = tpl.requires_manual
    # 凭据密文：{account, password_enc} 的 JSON 整体加密
    import json

    cred_plain = json.dumps(
        {"account": payload.account.strip(), "password": payload.password}, ensure_ascii=False
    )
    cred_ref = encrypt(cred_plain)
    task = ApiApplyTask(
        tenant_id=tenant_id,
        platform_id=payload.platform_id,
        platform=platform_name,
        status="pending",
        credentials_ref=cred_ref,
        account=payload.account.strip(),
        progress=0,
        created_by=operator or payload.created_by,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    # 需人工介入的平台在提交后自动进入 awaiting_manual
    if requires_manual:
        task.status = "submitted"
        task.progress = 40
        db.commit()
        db.refresh(task)
    return task


_VALID_TRANSITIONS = {
    "pending": {"submitted", "failed"},
    "submitted": {"awaiting_manual", "done", "failed"},
    "awaiting_manual": {"done", "failed"},
    "done": set(),
    "failed": set(),
}


def update_apply_task(
    db: Session,
    tenant_id: int,
    task_id: int,
    payload: ApiApplyTaskPatch,
    operator: str = "system",
) -> ApiApplyTask:
    task = db.get(ApiApplyTask, task_id)
    if task is None or task.tenant_id != tenant_id:
        raise ApiBridgeServiceError("申请任务不存在或无权访问")
    if payload.status is not None:
        if payload.status not in API_TASK_STATUSES:
            raise ApiBridgeServiceError(f"非法状态: {payload.status}")
        if payload.status != task.status and payload.status not in _VALID_TRANSITIONS[task.status]:
            raise ApiBridgeServiceError(f"非法状态流转: {task.status} -> {payload.status}")
        task.status = payload.status
        if payload.status in ("done", "failed"):
            task.finished_at = _now()
    if payload.progress is not None:
        task.progress = payload.progress
    if payload.result_message is not None:
        task.result_message = payload.result_message
    if payload.error is not None:
        task.error = payload.error
    task.updated_at = _now()
    db.commit()
    db.refresh(task)
    return task


def list_tasks(
    db: Session,
    tenant_id: int,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    stmt = select(ApiApplyTask).where(ApiApplyTask.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(ApiApplyTask.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                ApiApplyTask.platform.like(like),
                ApiApplyTask.account.like(like),
                ApiApplyTask.result_message.like(like),
            )
        )
    total = db.scalar(
        select(func.count()).select_from(ApiApplyTask).where(
            (ApiApplyTask.tenant_id == tenant_id)
            & ((status is None) or (ApiApplyTask.status == status))
        )
    )
    rows = db.scalars(stmt.order_by(ApiApplyTask.id.desc()).offset((page - 1) * size).limit(size)).all()
    # 返回脱敏账号，绝不下发密码密文
    items = []
    for t in rows:
        masked = t.account[:3] + "***" if len(t.account) > 3 else "***"
        items.append(
            {
                "id": t.id,
                "platform_id": t.platform_id,
                "platform": t.platform,
                "status": t.status,
                "account_masked": masked,
                "progress": t.progress,
                "result_message": t.result_message,
                "error": t.error,
                "created_by": t.created_by,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            }
        )
    return {"items": items, "total": total or 0, "page": page, "size": size}


def get_task(db: Session, tenant_id: int, task_id: int) -> ApiApplyTask:
    task = db.get(ApiApplyTask, task_id)
    if task is None or task.tenant_id != tenant_id:
        raise ApiBridgeServiceError("申请任务不存在或无权访问")
    return task
