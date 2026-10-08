"""事件订阅注册表：订阅方声明与事件名匹配。

匹配规则：
- 精确匹配：``sentiment.alert.created`` 只匹配同名事件；
- 前缀通配：``sentiment.*`` 匹配 ``sentiment.`` 开头的全部事件；
- 全量通配：``*`` 匹配所有事件（仅内核审计类订阅方使用）。

订阅注册为进程内声明式注册，内核启动时由各模块与插件在 ``register`` 阶段调用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 事件处理函数签名：handler(ctx) -> None，失败即抛异常
EventHandler = Callable[[object], None]


@dataclass(frozen=True)
class Subscription:
    """一条订阅声明。"""

    event_name: str
    handler: EventHandler
    subscriber: str
    max_attempts: Optional[int] = None
    plugin_id: Optional[str] = None
    enabled: bool = True


_SUBSCRIBERS: dict[str, list[Subscription]] = {}


def subscribe(
    event_name: str,
    handler: EventHandler,
    *,
    subscriber: str,
    max_attempts: Optional[int] = None,
    plugin_id: Optional[str] = None,
) -> Subscription:
    """注册一个事件订阅。

    :param event_name: 事件名，支持 ``sentiment.*`` 前缀通配与 ``*`` 全量通配
    :param handler: 处理函数，接收 ``EventContext``
    :param subscriber: 订阅方标识（模块名或插件 ID），用于位点与日志
    :param max_attempts: 覆盖默认最大投递次数；None 表示沿用事件自带值
    :param plugin_id: 注册来源插件 ID，内核模块传 None
    """
    if not event_name:
        raise ValueError("event_name 不能为空")
    _validate_name(event_name, plugin_id=plugin_id)
    sub = Subscription(
        event_name=event_name,
        handler=handler,
        subscriber=subscriber,
        max_attempts=max_attempts,
        plugin_id=plugin_id,
    )
    _SUBSCRIBERS.setdefault(event_name, []).append(sub)
    logger.debug("事件订阅注册：%s -> %s", event_name, subscriber)
    return sub


def _validate_name(event_name: str, *, plugin_id: Optional[str]) -> None:
    """命名空间校验：插件只能订阅自身命名空间或内核事件，禁止订阅其它插件的事件。"""
    if plugin_id is None or event_name == "*":
        return
    prefix = f"{plugin_id}."
    if event_name.startswith(prefix) or event_name.startswith("core."):
        return
    raise PermissionError(
        f"插件 {plugin_id} 不得订阅 {event_name}：仅允许自身命名空间 {prefix}* 或 core.*"
    )


def unsubscribe(event_name: str, subscriber: str) -> int:
    """注销某订阅方在某事件名上的全部订阅，返回移除条数。"""
    subs = _SUBSCRIBERS.get(event_name, [])
    remain = [s for s in subs if s.subscriber != subscriber]
    removed = len(subs) - len(remain)
    if remain:
        _SUBSCRIBERS[event_name] = remain
    else:
        _SUBSCRIBERS.pop(event_name, None)
    return removed


def disable_plugin(plugin_id: str) -> int:
    """插件被禁用/卸载时摘除其全部订阅，禁止残留投递。"""
    removed = 0
    for name in list(_SUBSCRIBERS):
        subs = _SUBSCRIBERS[name]
        remain = [s for s in subs if s.plugin_id != plugin_id]
        removed += len(subs) - len(remain)
        if remain:
            _SUBSCRIBERS[name] = remain
        else:
            _SUBSCRIBERS.pop(name, None)
    return removed


def match(event_name: str) -> list[Subscription]:
    """返回该事件的全部匹配订阅。"""
    matched: list[Subscription] = []
    for pattern, subs in _SUBSCRIBERS.items():
        if pattern == "*" or pattern == event_name:
            matched.extend(subs)
        elif pattern.endswith(".*") and event_name.startswith(pattern[:-1]):
            matched.extend(subs)
    return [s for s in matched if s.enabled]


def registered_names() -> list[str]:
    """返回已登记的订阅模式，供内核状态页展示。"""
    return sorted(_SUBSCRIBERS)


def clear() -> None:
    """清空注册表（测试用）。"""
    _SUBSCRIBERS.clear()
