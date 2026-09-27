"""安全审计日志接口：查询、统计、按保留期清理。"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core import security_log
from app.api.deps import get_current_user, require_permissions
from app.models.auth import User
from app.models.base import get_db
from app.schemas.auth import AuditLogOut, AuditStatsOut
from app.schemas.common import ApiResponse, PageResult
from app.services import audit_service, auth_service

logger = logging.getLogger(__name__)

router = APIRouter()

EVENT_TYPES = [
    audit_service.EVENT_LOGIN_SUCCESS,
    audit_service.EVENT_LOGIN_FAILED,
    audit_service.EVENT_LOGOUT,
    audit_service.EVENT_PASSWORD_CHANGE,
    audit_service.EVENT_ACCESS_DENIED,
    audit_service.EVENT_SENSITIVE_OPERATION,
]


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """统一为带时区的 UTC 时间，避免与数据库时区比较不一致。"""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.get(
    "/logs",
    response_model=ApiResponse[PageResult[AuditLogOut]],
    summary="审计日志查询",
    dependencies=[Depends(require_permissions("audit:view"))],
)
def list_audit_logs(
    event_type: Optional[str] = Query(default=None, description="事件类型"),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="结果：success / failure"
    ),
    username: Optional[str] = Query(default=None, description="操作人用户名（模糊）"),
    keyword: Optional[str] = Query(default=None, description="路径/动作/详情/IP 关键词"),
    start_time: Optional[datetime] = Query(default=None, description="起始时间 ISO8601"),
    end_time: Optional[datetime] = Query(default=None, description="结束时间 ISO8601"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """分页查询审计日志，默认按时间倒序。"""
    if event_type and event_type not in EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的事件类型，可选值：{', '.join(EVENT_TYPES)}",
        )
    total, rows = audit_service.query_logs(
        db,
        event_type=event_type,
        status=status_filter,
        username=username,
        keyword=keyword,
        start_time=_to_utc(start_time),
        end_time=_to_utc(end_time),
        page=page,
        page_size=page_size,
    )
    return ApiResponse[PageResult[AuditLogOut]](
        data=PageResult[AuditLogOut](
            total=total,
            page=page,
            page_size=page_size,
            items=[AuditLogOut.model_validate(r) for r in rows],
        )
    )


@router.get(
    "/stats",
    response_model=ApiResponse[AuditStatsOut],
    summary="审计统计",
    dependencies=[Depends(require_permissions("audit:view"))],
)
def audit_stats(
    days: int = Query(default=7, ge=1, le=365, description="统计最近 N 天"),
    db: Session = Depends(get_db),
):
    """近 N 天审计概览：总量、按事件类型、按结果分布。"""
    data = audit_service.stats(db, days=days)
    return ApiResponse[AuditStatsOut](data=AuditStatsOut(**data))


@router.get(
    "/event-types",
    response_model=ApiResponse[list[str]],
    summary="审计事件类型",
    dependencies=[Depends(require_permissions("audit:view"))],
)
def list_event_types():
    """返回可用的事件类型枚举，供前端筛选器使用。"""
    return ApiResponse[list[str]](data=EVENT_TYPES)


@router.post(
    "/purge",
    response_model=ApiResponse[dict],
    summary="清理过期审计日志",
    dependencies=[Depends(require_permissions("audit:export"))],
)
def purge_audit_logs(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按 SECURITY_AUDIT_RETENTION_DAYS 清理历史日志（敏感操作）。"""
    removed = auth_service.purge_old_audit_logs(db)
    audit_service.log_sensitive_operation(
        db,
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        tenant_id=current_user.tenant_id,
        action=f"清理过期审计日志（保留 {audit_service.settings.SECURITY_AUDIT_RETENTION_DAYS} 天）",
        status_code=200,
        detail={"removed": removed},
    )
    return ApiResponse[dict](data={"removed": removed})


# ------------------------------------------------------------ 安全日志分级
@router.get(
    "/security-log/levels",
    response_model=ApiResponse[dict],
    summary="安全日志分级字典",
    dependencies=[Depends(require_permissions("audit:view"))],
)
def security_log_levels():
    """返回级别定义、事件默认级别与当前分级配置，供前端筛选与说明展示。"""
    return ApiResponse[dict](data=security_log.catalog())


@router.get(
    "/security-log/entries",
    response_model=ApiResponse[dict],
    summary="安全日志分级查询",
    dependencies=[Depends(require_permissions("audit:view"))],
)
def security_log_entries(
    level: Optional[str] = Query(
        default=None, description="级别：INFO / WARNING / CRITICAL"
    ),
    event_type: Optional[str] = Query(default=None, description="事件类型"),
    days: int = Query(default=7, ge=1, le=365, description="统计近 N 天"),
    limit: int = Query(default=20, ge=1, le=200, description="返回条数"),
):
    """按级别/事件筛选安全日志条目，并返回分级统计与最近高危事件。"""
    normalized = level.upper() if level else None
    if normalized and normalized not in security_log.LEVELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的级别，可选值：{', '.join(security_log.LEVELS)}",
        )
    items = security_log.recent(
        limit=limit, level=normalized, event_type=event_type, days=days
    )
    return ApiResponse[dict](
        data={
            "level": normalized,
            "event_type": event_type,
            "days": days,
            "items": items,
            "stats": security_log.stats(days=days),
        }
    )
