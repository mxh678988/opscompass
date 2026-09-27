"""系统健康与版本信息。"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_permissions
from app.core.config import settings
from app.schemas.auth import SecurityOverviewOut
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """服务健康检查（开放）。"""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "slogan": settings.PROJECT_SLOGAN,
        "env": settings.ENV,
    }


@router.get("/info", dependencies=[Depends(get_current_user)])
def info() -> dict:
    """服务基础信息（需登录）。"""
    return {
        "name": settings.PROJECT_NAME,
        "slogan": settings.PROJECT_SLOGAN,
        "version": "0.1.0",
        "env": settings.ENV,
        "timezone": settings.TIMEZONE,
    }


@router.get(
    "/security-overview",
    response_model=ApiResponse[SecurityOverviewOut],
    summary="安全配置概览",
    dependencies=[Depends(require_permissions("system:view"))],
)
def security_overview() -> ApiResponse[SecurityOverviewOut]:
    """当前安全配置概览：监听地址、CORS 白名单、IP 白名单、认证与审计策略。"""
    return ApiResponse[SecurityOverviewOut](
        data=SecurityOverviewOut(**settings.security_overview)
    )
