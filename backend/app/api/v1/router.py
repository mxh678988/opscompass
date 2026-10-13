"""API v1 总路由：各业务域子路由在此注册。

鉴权分层：
- 开放：/system/health、/auth/login
- 登录即可：/system/info、/auth/*、/rbac/*
- 登录 + 模块权限：/tenants、/datasources、/metrics、/ingest、/ai、/ops、/audit
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_module_access
from app.api.v1.endpoints import (
    agent,
    ai,
    api_bridge,
    audience,
    audit,
    auth,
    collect,
    datasources,
    health,
    ingest,
    knowledge,
    learning,
    marketing,
    metrics,
    model_hub,
    ops,
    plugin_market,
    predictive,
    rbac,
    security_transfer,
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

# 插件市场（v0.12.0 MVP）：上架 / 安装 / 启停 / 卸载 / 签名校验
api_router.include_router(
    plugin_market.router,
    prefix="/plugins",
    tags=["plugins"],
    dependencies=[Depends(require_module_access("plugin"))],
)

# M9 预测引擎：流失/转化概率预测（本地优先、规则兜底、可插拔模型路由）
api_router.include_router(
    predictive.router,
    prefix="/predictive",
    tags=["predictive"],
    dependencies=[Depends(require_module_access("predictive"))],
)

# M10 人群包引擎：按预测概率区间圈选 / 复用 / 列表与详情
api_router.include_router(
    audience.router,
    prefix="/audience",
    tags=["audience"],
    dependencies=[Depends(require_module_access("audience"))],
)

# M11 企业知识库：知识沉淀 / 检索供 Agent 引用 / 引用热度登记
api_router.include_router(
    knowledge.router,
    prefix="/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(require_module_access("knowledge"))],
)

# M12 智能体编排：编排运行 / 分析洞察 / 人工确认闸门 / 执行动作闭环
api_router.include_router(
    agent.router,
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(require_module_access("agent"))],
)

# M13 API 申请助手：平台申请模板 / 凭据加密代申请任务状态机
api_router.include_router(
    api_bridge.router,
    prefix="/api-bridge",
    tags=["api-bridge"],
    dependencies=[Depends(require_module_access("api_bridge"))],
)

# M14 导入导出安全中心：压缩包安全解压 / 加密导出（付费插件门控）
api_router.include_router(
    security_transfer.router,
    prefix="/security",
    tags=["security-transfer"],
    dependencies=[Depends(require_module_access("security_transfer"))],
)

