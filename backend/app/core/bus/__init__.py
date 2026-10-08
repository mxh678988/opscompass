"""内核能力：事件总线。

注意导入顺序：先加载 ``registry`` 子模块，再加载 ``bus``，
避免 ``bus`` 内部 ``from app.core.bus import registry`` 触发循环导入。
"""

from app.core.bus import registry  # noqa: F401  （必须先于 bus 导入）
from app.core.bus.bus import (  # noqa: F401
    DEFAULT_CONCURRENCY,
    EventBus,
    EventContext,
    bus,
    disable_plugin_subscriptions,
    subscribe,
    unsubscribe,
)

__all__ = [
    "bus",
    "EventBus",
    "EventContext",
    "subscribe",
    "unsubscribe",
    "disable_plugin_subscriptions",
    "DEFAULT_CONCURRENCY",
    "registry",
]
