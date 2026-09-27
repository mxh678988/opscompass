"""安全审计日志服务：登录、鉴权失败与敏感操作的落库与查询。"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core import security_log
from app.core.config import settings
from app.models.auth import AuditLog

logger = logging.getLogger(__name__)

# 事件类型常量
EVENT_LOGIN_SUCCESS = "login_success"
EVENT_LOGIN_FAILED = "login_failed"
EVENT_LOGOUT = "logout"
EVENT_PASSWORD_CHANGE = "password_change"
EVENT_ACCESS_DENIED = "access_denied"
EVENT_SENSITIVE_OPERATION = "sensitive_operation"

# 敏感操作（写操作）事件名映射，供中间件判断
SENSITIVE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    """解析客户端 IP；仅在信任代理头时读取 X-Forwarded-For / X-Real-IP。"""
    if request is None:
        return None
    if settings.SECURITY_TRUST_FORWARDED_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def record(
    db: Session,
    event_type: str,
    *,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    tenant_id: Optional[int] = None,
    action: Optional[str] = None,
    status: str = "success",
    status_code: Optional[int] = None,
    request: Optional[Request] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    detail: Any = None,
    commit: bool = True,
) -> Optional[AuditLog]:
    """写入一条审计日志；失败不抛出，避免影响主流程。"""
    if not settings.SECURITY_AUDIT_ENABLED:
        return None
    try:
        if request is not None:
            method = method or request.method
            path = path or request.url.path
        if detail is not None and not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False, default=str)
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            event_type=event_type,
            action=action,
            status=status,
            status_code=status_code,
            method=method,
            path=path,
            client_ip=get_client_ip(request),
            user_agent=(request.headers.get("user-agent") if request is not None else None),
            detail=detail,
        )
        db.add(log)
        if commit:
            db.commit()
            db.refresh(log)
        else:
            db.flush()
        # 分级安全日志：同一事件同时进入独立 security.log（级别由事件+上下文判定）
        security_log.emit(
            event_type,
            username=username,
            user_id=user_id,
            tenant_id=tenant_id,
            ip=log.client_ip,
            method=log.method,
            path=log.path,
            status_code=status_code,
            status=status,
            detail=detail,
            extra={"action": action} if action else None,
        )
        return log
    except Exception:  # pragma: no cover - 审计失败不应影响业务
        logger.exception("写入审计日志失败: event=%s", event_type)
        security_log.emit(
            "audit_failure",
            username=username,
            ip=get_client_ip(request),
            method=method,
            path=path,
            status="failure",
            detail=f"审计日志写入失败，事件类型 {event_type}",
        )
        try:
            db.rollback()
        except Exception:  # pragma: no cover
            pass
        return None


# ------------------------------------------------------------ 便捷方法
def log_login_success(
    db: Session, user: Any, request: Optional[Request] = None
) -> Optional[AuditLog]:
    return record(
        db,
        EVENT_LOGIN_SUCCESS,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        tenant_id=getattr(user, "tenant_id", None),
        action="用户登录成功",
        status="success",
        status_code=200,
        request=request,
    )


def log_login_failed(
    db: Session,
    username: str,
    reason: str,
    request: Optional[Request] = None,
    status_code: int = 401,
) -> Optional[AuditLog]:
    return record(
        db,
        EVENT_LOGIN_FAILED,
        username=username,
        action="用户登录失败",
        status="failure",
        status_code=status_code,
        request=request,
        detail=reason,
    )


def log_logout(db: Session, user: Any, request: Optional[Request] = None) -> Optional[AuditLog]:
    return record(
        db,
        EVENT_LOGOUT,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
        tenant_id=getattr(user, "tenant_id", None),
        action="用户登出",
        status="success",
        request=request,
    )


def log_access_denied(
    db: Session,
    *,
    request: Optional[Request],
    reason: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    status_code: int = 403,
) -> Optional[AuditLog]:
    return record(
        db,
        EVENT_ACCESS_DENIED,
        user_id=user_id,
        username=username,
        action="访问被拒绝",
        status="failure",
        status_code=status_code,
        request=request,
        detail=reason,
    )


def log_sensitive_operation(
    db: Session,
    *,
    request: Request,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    tenant_id: Optional[int] = None,
    action: Optional[str] = None,
    status_code: Optional[int] = None,
    status: str = "success",
    detail: Any = None,
) -> Optional[AuditLog]:
    return record(
        db,
        EVENT_SENSITIVE_OPERATION,
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        action=action or f"敏感操作 {request.method} {request.url.path}",
        status=status,
        status_code=status_code,
        request=request,
        detail=detail,
    )


# ------------------------------------------------------------ 查询
def query_logs(
    db: Session,
    *,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    keyword: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[AuditLog]]:
    """按条件分页查询审计日志，返回 (总数, 列表)。"""
    conditions = []
    if event_type:
        conditions.append(AuditLog.event_type == event_type)
    if status:
        conditions.append(AuditLog.status == status)
    if username:
        conditions.append(AuditLog.username.ilike(f"%{username}%"))
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if tenant_id is not None:
        conditions.append(AuditLog.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(
                AuditLog.path.ilike(like),
                AuditLog.action.ilike(like),
                AuditLog.detail.ilike(like),
                AuditLog.client_ip.ilike(like),
            )
        )
    if start_time is not None:
        conditions.append(AuditLog.created_at >= start_time)
    if end_time is not None:
        conditions.append(AuditLog.created_at <= end_time)

    base = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    for cond in conditions:
        base = base.where(cond)
        count_stmt = count_stmt.where(cond)

    total = int(db.execute(count_stmt).scalar() or 0)
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    stmt = (
        base.order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return total, items


def stats(
    db: Session,
    *,
    days: int = 7,
    tenant_id: Optional[int] = None,
) -> dict:
    """近 N 天审计统计：总量、按事件类型、按结果。"""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    base_conditions = [AuditLog.created_at >= since]
    if tenant_id is not None:
        base_conditions.append(AuditLog.tenant_id == tenant_id)

    total = int(
        db.execute(
            select(func.count(AuditLog.id)).where(*base_conditions)
        ).scalar()
        or 0
    )
    type_rows = db.execute(
        select(AuditLog.event_type, func.count(AuditLog.id))
        .where(*base_conditions)
        .group_by(AuditLog.event_type)
    ).all()
    status_rows = db.execute(
        select(AuditLog.status, func.count(AuditLog.id))
        .where(*base_conditions)
        .group_by(AuditLog.status)
    ).all()
    return {
        "total": total,
        "by_event_type": {str(k): int(v) for k, v in type_rows},
        "by_status": {str(k): int(v) for k, v in status_rows},
    }
