"""插件 SDK：对外最小接口集（不含内核内部实现依赖）。

插件作者仅依赖本包，通过 ``PluginContext`` 使用内核能力：

| 分类 | 接口 | 落地阶段 |
|---|---|---|
| 数据 | ``ctx.db.session()`` | M2 |
| 事件 | ``ctx.bus.publish`` / ``ctx.bus.subscribe`` | M1/M2 |
| 权限 | ``ctx.auth.require`` / ``ctx.auth.check`` | M3 |
| 配置 | ``ctx.config.get`` / ``ctx.config.set`` | M2 |
| 模型 | ``ctx.model.run`` | M6 |
| 日志 | ``ctx.log.info/warn/error`` | M2 |
| 定时 | ``ctx.job.register`` | M4 |
| 存储 | ``ctx.storage.save`` / ``ctx.storage.read`` | M5 |
| 待办 | ``ctx.task.create`` | M4 |
| 前端 | ``ctx.ui.register_menu`` / ``ctx.ui.register_route`` | M2（登记）/ 前端接入另计 |

接口稳定性承诺：SDK 主版本内向后兼容；弃用项提前一个次版本标注，下个大版本移除。
"""

from app.sdk.context import (
    AuthFacade,
    ConfigFacade,
    ConfigStore,
    DbFacade,
    EventBusFacade,
    JobFacade,
    LogFacade,
    ModelFacade,
    PluginContext,
    PluginNamespace,
    StorageFacade,
    TaskFacade,
    UIFacade,
    SentimentFacade,
    create_context,
)
from app.sdk.exceptions import (
    ManifestError,
    NamespaceViolation,
    NotAvailableError,
    SdkError,
)

# SDK 主版本：插件清单的 min_kernel_version 与之对应的内核版本独立
SDK_VERSION = "1.0.0"

__all__ = [
    "SDK_VERSION",
    "PluginContext",
    "PluginNamespace",
    "create_context",
    "DbFacade",
    "EventBusFacade",
    "AuthFacade",
    "ConfigFacade",
    "ConfigStore",
    "ModelFacade",
    "LogFacade",
    "JobFacade",
    "StorageFacade",
    "TaskFacade",
    "UIFacade",
    "SdkError",
    "NamespaceViolation",
    "NotAvailableError",
    "ManifestError",
]
