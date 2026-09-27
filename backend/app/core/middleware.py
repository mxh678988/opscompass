"""安全中间件：IP 白名单拦截 + 敏感操作审计。

- IPAllowlistMiddleware：白名单启用时，非白名单来源直接 403，并落审计日志。
- AuditMiddleware：对写操作（POST/PUT/PATCH/DELETE）落敏感操作审计日志。
"""

import ipaddress
import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core import security_log
from app.core.config import settings
from app.services import audit_service

logger = logging.getLogger(__name__)

# 由端点自行记录审计、无需中间件重复记录的路径
AUDIT_SKIP_PATHS = {
    f"{settings.API_V1_PREFIX}/auth/login",
    f"{settings.API_V1_PREFIX}/auth/logout",
    f"{settings.API_V1_PREFIX}/auth/password",
}

# 无需鉴权即可访问的路径（仅用于审计标注，不做拦截）
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    f"{settings.API_V1_PREFIX}/system/health",
    f"{settings.API_V1_PREFIX}/auth/login",
}


def _match_ip(client_ip: str, entries: list[str]) -> bool:
    """判断 IP 是否命中白名单（支持单 IP、CIDR 与通配符 *）。"""
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in entries:
        if entry in ("*", "0.0.0.0/0", "::/0"):
            return True
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            logger.warning("忽略非法白名单条目: %s", entry)
    return False


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """IP 白名单拦截中间件（默认关闭）。"""

    async def dispatch(self, request: Request, call_next):
        if not settings.ip_allowlist_active:
            return await call_next(request)

        client_ip = audit_service.get_client_ip(request)
        if client_ip and _match_ip(client_ip, settings.ip_allowlist):
            return await call_next(request)

        # 白名单未开启时的信任代理场景：无法解析 IP 时放行，避免误封
        if not client_ip:
            return await call_next(request)

        logger.warning("IP 白名单拦截: %s %s", client_ip, request.url.path)
        try:
            from app.models.base import SessionLocal

            db = SessionLocal()
            try:
                audit_service.record(
                    db,
                    audit_service.EVENT_ACCESS_DENIED,
                    action="IP 白名单拦截",
                    status="failure",
                    status_code=403,
                    request=request,
                    detail=f"来源 IP {client_ip} 不在白名单内",
                )
            finally:
                db.close()
        except Exception:  # pragma: no cover
            logger.exception("记录 IP 白名单拦截日志失败")
            security_log.emit(
                "audit_failure",
                ip=client_ip,
                path=request.url.path,
                method=request.method,
                status="failure",
                detail="IP 白名单拦截事件写入审计库失败",
            )

        return JSONResponse(
            status_code=403,
            content={"code": 403, "message": "来源 IP 不在白名单内，拒绝访问", "data": None},
        )


class AuditMiddleware(BaseHTTPMiddleware):
    """敏感操作审计中间件：记录写操作及其结果。"""

    async def dispatch(self, request: Request, call_next):
        if (
            not settings.SECURITY_AUDIT_ENABLED
            or not settings.SECURITY_AUDIT_WRITE_OPERATIONS
            or request.method not in audit_service.SENSITIVE_METHODS
            or request.url.path in AUDIT_SKIP_PATHS
        ):
            return await call_next(request)

        response = await call_next(request)

        try:
            from app.models.base import SessionLocal

            db = SessionLocal()
            try:
                state = getattr(request, "state", None)
                user_id = getattr(state, "user_id", None) if state else None
                username = getattr(state, "username", None) if state else None
                tenant_id = getattr(state, "tenant_id", None) if state else None
                audit_service.log_sensitive_operation(
                    db,
                    request=request,
                    user_id=user_id,
                    username=username,
                    tenant_id=tenant_id,
                    action=f"{request.method} {request.url.path}",
                    status_code=response.status_code,
                    status="success" if response.status_code < 400 else "failure",
                )
            finally:
                db.close()
        except Exception:  # pragma: no cover
            logger.exception("记录敏感操作审计日志失败")

        return response
