"""运营智脑后端服务入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import AuditMiddleware, IPAllowlistMiddleware

# 统一日志初始化：控制台 + app.log + 安全分级日志（security.log）
setup_logging()

logger = logging.getLogger(__name__)

# CORS 严格白名单：仅放行 .env 中显式配置的来源，方法与请求头按需收敛
ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "X-Requested-With",
    "X-Tenant-Id",
    "X-Request-Id",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时幂等初始化：权限点、内置角色、初始管理员账号。"""
    from app.models.base import SessionLocal
    from app.services import auth_service

    db = SessionLocal()
    try:
        result = auth_service.ensure_seed(db)
        logger.info("[startup] RBAC 初始化完成: %s", result)
    except Exception as exc:  # 表未建/数据库未就绪时不阻塞服务启动
        logger.warning(
            "[startup] RBAC 初始化跳过（请先执行 alembic upgrade head）: %s", exc
        )

    # P2 存储适配层：受管目录 + 内置路由规则 + 时序月分区（幂等，失败不阻塞启动）
    try:
        from app.storage.registry import bootstrap_storage

        storage_result = bootstrap_storage(db)
        logger.info("[startup] 存储适配层初始化完成: %s", storage_result)
    except Exception as exc:
        db.rollback()
        logger.warning(
            "[startup] 存储适配层初始化跳过（请先执行 alembic upgrade head）: %s", exc
        )
    finally:
        db.close()

    # P6 采集调度中心：启动内置调度线程（COLLECT_SCHEDULER_ENABLED=0 可关闭）
    try:
        from app.services import collect_service

        started = collect_service.start_scheduler()
        logger.info("[startup] 采集调度线程: %s", "已启动" if started else "未启动")
    except Exception as exc:  # 调度线程启动失败不阻塞服务
        logger.warning("[startup] 采集调度线程启动失败: %s", exc)

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.10.0",
        description="运营智脑 · 让数据自动做出最优决策 —— 后端 API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 中间件注册顺序与请求处理顺序相反：CORS -> IP 白名单 -> 审计 -> 路由
    app.add_middleware(AuditMiddleware)
    app.add_middleware(IPAllowlistMiddleware)

    origins = settings.cors_origins
    allow_credentials = True
    if "*" in origins:
        allow_credentials = False
        logger.warning("CORS 配置为通配来源，已关闭 credentials 透传，生产环境请改为具体域名")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
        expose_headers=["X-Request-Id"],
        max_age=600,
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        """健康检查（开放）。"""
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "slogan": settings.PROJECT_SLOGAN,
            "env": settings.ENV,
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )

