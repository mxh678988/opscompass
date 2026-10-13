"""电商/交易数据源连接器插件后端入口。

由内核 PluginRuntime 按清单 entry（backend.src.main:register）加载：
内核把自身实例传给 register()，插件在此把连接器引擎（create_for_plugin
工厂）注入内核；随后 SDK 的 connector.* 门面即经内核会话工厂调用
插件引擎，插件侧不直连任何内核模块（M2 设计约束）。
"""

from __future__ import annotations

from typing import Any

from .core import create_for_plugin


def register(runtime: Any) -> None:
    """插件注册入口：把连接器引擎注入内核 runtime。

    注入对象与内核 _make_connector 约定一致：
    engine(db, plugin_id, action, params, **kwargs) -> result。
    """
    runtime.inject_connector_engine(create_for_plugin)
