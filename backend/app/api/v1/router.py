"""API v1 总路由：各业务域子路由在此注册。

鉴权分层：
- 开放：/system/health、/auth/login
- 登录即可：/system/info、/auth/*、/rbac/*
- 登录 + 模块权限：/tenants、/datasources、/metrics、/ingest、/ai、/ops、/audit
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_module_access
from app.api.v1.endpoints import (
    ai,
    audit,
    auth,
    collect,
    commercial,
    datasources,
    digital_human,
    health,
    ingest,
    learning,
    marketing,
    metrics,
    model_hub,
    ops,
    rbac,
    storage,
    tenants,
)

api_router = APIRouter()

# 开放与认证路由
api_router.include_router(health.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 管理类路由（端点内已按权限点细粒度鉴权，此处强制登录）
api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])

# 业务路由：登录 + 模块权限（GET 需 *:view，写操作需对应写/删权限）
api_router.include_router(
    tenants.router,
    prefix="/tenants",
    tags=["tenants"],
    dependencies=[Depends(require_module_access("tenant"))],
)
api_router.include_router(
    datasources.router,
    prefix="/datasources",
    tags=["datasources"],
    dependencies=[Depends(require_module_access("datasource"))],
)
api_router.include_router(
    metrics.router,
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_module_access("metric"))],
)
api_router.include_router(
    ingest.router,
    prefix="/ingest",
    tags=["ingest"],
    dependencies=[Depends(require_module_access("ingest"))],
)
api_router.include_router(
    ops.router,
    tags=["ops"],
    dependencies=[Depends(require_module_access("ops"))],
)
api_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(require_module_access("ai"))],
)

# 营销全渠道接入：渠道授权 / 投放任务 / 事件日志
api_router.include_router(
    marketing.router,
    tags=["marketing"],
    dependencies=[Depends(require_module_access("marketing"))],
)

# 采集调度中心：采集任务 / 手动执行 / 调度启停 / 运行记录
api_router.include_router(
    collect.router,
    tags=["collect"],
    dependencies=[Depends(require_module_access("collect"))],
)

# 存储适配层：引擎总览 / 路由识别 / 全文检索 / 一致性对账
api_router.include_router(
    storage.router,
    prefix="/storage",
    tags=["storage"],
    dependencies=[Depends(require_module_access("storage"))],
)

# 模型中心（P9 硬件检测 + 模型自动适配）：硬件探测 / 模型推荐 / 端点接入与自检
api_router.include_router(
    model_hub.router,
    prefix="/model",
    tags=["model"],
    dependencies=[Depends(require_module_access("model"))],
)

# 学习进化闭环（P8）：决策反馈回流 / 策略权重自调 / 经验案例库 / A-B 对照实验
api_router.include_router(
    learning.router,
    prefix="/learning",
    tags=["learning"],
    dependencies=[Depends(require_module_access("learning"))],
)

# 数字人一键生成：形象库 / 音色库 / 生成项目 / 四阶段编排 / 工作流模板
api_router.include_router(
    digital_human.router,
    prefix="/digital-human",
    tags=["digital-human"],
    dependencies=[Depends(require_module_access("digital_human"))],
)

# 商业化中心（P10）：套餐定价 / 授权证书与数字签名校验 / 订单 / 用量配额
api_router.include_router(
    commercial.router,
    prefix="/commercial",
    tags=["commercial"],
    dependencies=[Depends(require_module_access("commercial"))],
)

