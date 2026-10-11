"""舆情插件 backend 入口（插件市场 MVP 演示用）。

清单 entry 为 ``backend.src.main:register``，内核在安装/启用时调用
``register(runtime)``；插件通过 ``runtime.inject_*`` 回调把业务引擎
注入内核。MVP 阶段仅占位，真实舆情引擎由 M8 业务层提供。
"""

import logging

from backend.src import database  # noqa: F401  确保建表模块被导入

logger = logging.getLogger(__name__)


def register(runtime) -> None:
    """插件入口：注入业务引擎（MVP 下为空实现）。"""
    # 未来注入点示例：
    # runtime.inject_sentiment_engine(make_engine())
    logger.info("sentiment plugin backend registered (MVP placeholder)")
