"""插件运行时包（M2）。

对外导出：
- ``PluginRegistry`` / ``PluginMeta`` / ``PluginState``：插件注册与生命周期
- ``PluginRuntime``：装配内核能力到插件上下文
- ``validate_manifest``：清单校验
"""

from app.core.plugin.registry import (
    PluginMeta,
    PluginRegistry,
    PluginState,
)

__all__ = ["PluginRegistry", "PluginMeta", "PluginState"]
