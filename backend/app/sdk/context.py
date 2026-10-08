"""PluginContext：插件与内核之间的唯一交互面。

设计原则（依赖倒置）：SDK 不 import 任何内核内部模块，内核在装载插件时把
能力回调注入进来。这样 SDK 可独立发布（插件作者依赖 ``opscompass-sdk``），
内核也能自由重构实现而不破坏插件。

分期实现：接口一次性冻结，未落地能力调用时抛 ``NotAvailableError`` 并指明
计划版本，避免插件作者误用半成品。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from app.sdk.exceptions import NamespaceViolation, NotAvailableError

# 内核事件前缀：任何插件都可订阅
KERNEL_EVENT_PREFIX = "core."


@dataclass(frozen=True)
class PluginNamespace:
    """插件命名空间声明（来自 plugin.yaml）。"""

    tables: str = ""
    events: str = ""
    permissions: str = ""


@runtime_checkable
class ConfigStore(Protocol):
    """配置存储协议：由内核实现（独立配置分区）。"""

    def get(self, plugin_id: str, key: str, default: Any = None) -> Any: ...

    def set(self, plugin_id: str, key: str, value: Any) -> None: ...

    def all(self, plugin_id: str) -> dict[str, Any]: ...


class LogFacade:
    """日志门面：自动携带 plugin_id，可选 trace_id。"""

    def __init__(self, plugin_id: str, trace_id: Optional[str] = None) -> None:
        self._logger = logging.getLogger(f"plugin.{plugin_id}")
        self._extra = {"plugin_id": plugin_id}
        if trace_id:
            self._extra["trace_id"] = trace_id

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        extra = dict(kwargs.pop("extra", {}))
        extra.update(self._extra)
        self._logger.log(level, msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def bind(self, trace_id: str) -> "LogFacade":
        """派生一个带 trace_id 的日志门面。"""
        facade = LogFacade(self._extra["plugin_id"], trace_id)
        return facade


class EventBusFacade:
    """事件门面：强制插件只能在自身命名空间发布、在自身命名空间或 core.* 订阅。"""

    def __init__(
        self,
        plugin_id: str,
        events_prefix: str,
        publish_fn: Callable[..., str],
        subscribe_fn: Callable[..., Any],
    ) -> None:
        self._plugin_id = plugin_id
        self._prefix = events_prefix or f"{plugin_id}."
        self._publish = publish_fn
        self._subscribe = subscribe_fn

    def _check_publish(self, name: str) -> None:
        if not name.startswith(self._prefix):
            raise NamespaceViolation(
                self._plugin_id, "事件名", name, f"{self._prefix}*"
            )

    def _check_subscribe(self, name: str) -> None:
        if name.startswith(self._prefix) or name.startswith(KERNEL_EVENT_PREFIX):
            return
        raise NamespaceViolation(
            self._plugin_id,
            "订阅事件名",
            name,
            f"{self._prefix}* 或 {KERNEL_EVENT_PREFIX}*",
        )

    def publish(self, name: str, payload: Optional[dict] = None, **kwargs: Any) -> str:
        """发布事件，返回 event_id。"""
        self._check_publish(name)
        return self._publish(name, payload or {}, **kwargs)

    def subscribe(self, name: str, handler: Callable[[Any], None], **kwargs: Any) -> Any:
        """订阅事件；仅允许自身命名空间或 core.*。"""
        self._check_subscribe(name)
        return self._subscribe(name, handler, **kwargs)


class DbFacade:
    """数据门面：只能访问自身命名空间表（前缀校验 + M3 起行级隔离）。"""

    def __init__(
        self,
        plugin_id: str,
        tables_prefix: str,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._prefix = tables_prefix
        self._session_factory = session_factory

    def session(self) -> Any:
        """打开一个数据库会话（由内核注入的会话工厂创建）。"""
        if self._session_factory is None:
            raise NotAvailableError("db.session", "M2 装配完成")
        return self._session_factory()

    def assert_table(self, table_name: str) -> None:
        """校验表名落在插件自身命名空间内。"""
        if not self._prefix or not table_name.startswith(self._prefix):
            raise NamespaceViolation(
                self._plugin_id, "表名", table_name, f"{self._prefix}*"
            )


class AuthFacade:
    """权限门面：统一鉴权，插件不得自行实现（M3 统一身份治理落地）。"""

    def require(self, perm_code: str) -> None:
        raise NotAvailableError("auth.require", "M3")

    def check(self, user: Any, perm_code: str) -> bool:
        raise NotAvailableError("auth.check", "M3")


class ConfigFacade:
    """配置门面：插件独立配置分区，键值互不可见。"""

    def __init__(self, plugin_id: str, store: Optional[ConfigStore] = None) -> None:
        self._plugin_id = plugin_id
        self._store = store

    def _require_store(self) -> ConfigStore:
        if self._store is None:
            raise NotAvailableError("config", "M2 装配完成")
        return self._store

    def get(self, key: str, default: Any = None) -> Any:
        return self._require_store().get(self._plugin_id, key, default)

    def set(self, key: str, value: Any) -> None:
        self._require_store().set(self._plugin_id, key, value)

    def all(self) -> dict[str, Any]:
        return self._require_store().all(self._plugin_id)


class ModelFacade:
    """模型门面：只声明能力，不指定模型（M6 模型路由落地）。"""

    def run(self, capability: str, input: Any, **opts: Any) -> Any:
        raise NotAvailableError("model.run", "M6")


class JobFacade:
    """定时门面：只登记声明，由内核统一调度，插件不得自行起进程。"""

    def __init__(self, plugin_id: str) -> None:
        self._plugin_id = plugin_id
        self.declarations: list[dict[str, Any]] = []

    def register(self, job_id: str, cron: str, handler: Callable[[], Any], **kwargs: Any) -> dict[str, Any]:
        declaration = {
            "plugin_id": self._plugin_id,
            "id": job_id,
            "schedule": cron,
            "handler": handler,
            **kwargs,
        }
        self.declarations.append(declaration)
        return declaration


class StorageFacade:
    """存储门面：插件私有空间（M5 统一文件服务落地）。"""

    def save(self, path: str, data: Any) -> Any:
        raise NotAvailableError("storage.save", "M5")

    def read(self, path: str) -> Any:
        raise NotAvailableError("storage.read", "M5")


class TaskFacade:
    """待办门面：自动挂 SLA 与升级链（M4 任务 SLA 落地）。"""

    def create(self, title: str, sla: Any = None, **kwargs: Any) -> Any:
        raise NotAvailableError("task.create", "M4")


class UIFacade:
    """前端门面：菜单与路由声明，由内核动态注入。"""

    def __init__(self, plugin_id: str) -> None:
        self._plugin_id = plugin_id
        self.menus: list[dict[str, Any]] = []
        self.routes: list[dict[str, Any]] = []

    def register_menu(self, path: str, title: str, icon: str = "", **kwargs: Any) -> dict[str, Any]:
        item = {"plugin_id": self._plugin_id, "path": path, "title": title, "icon": icon, **kwargs}
        self.menus.append(item)
        return item

    def register_route(self, path: str, component: str, **kwargs: Any) -> dict[str, Any]:
        item = {"plugin_id": self._plugin_id, "path": path, "component": component, **kwargs}
        self.routes.append(item)
        return item


class PluginContext:
    """插件上下文：插件与内核交互的唯一入口。"""

    def __init__(
        self,
        *,
        plugin_id: str,
        plugin_version: str = "0.0.0",
        namespace: Optional[PluginNamespace] = None,
        session_factory: Optional[Callable[[], Any]] = None,
        publish_fn: Optional[Callable[..., str]] = None,
        subscribe_fn: Optional[Callable[..., Any]] = None,
        config_store: Optional[ConfigStore] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.namespace = namespace or PluginNamespace()
        self.log = LogFacade(plugin_id, trace_id)
        self.db = DbFacade(plugin_id, self.namespace.tables, session_factory)
        self.bus = EventBusFacade(
            plugin_id,
            self.namespace.events,
            publish_fn or _missing_publish,
            subscribe_fn or _missing_subscribe,
        )
        self.auth = AuthFacade()
        self.config = ConfigFacade(plugin_id, config_store)
        self.model = ModelFacade()
        self.job = JobFacade(plugin_id)
        self.storage = StorageFacade()
        self.task = TaskFacade()
        self.ui = UIFacade(plugin_id)

    def declarations(self) -> dict[str, list[dict[str, Any]]]:
        """返回插件登记的全部声明（供内核统一执行）。"""
        return {"jobs": list(self.job.declarations), "menus": list(self.ui.menus), "routes": list(self.ui.routes)}


def _missing_publish(name: str, payload: dict, **kwargs: Any) -> str:
    raise NotAvailableError("bus.publish", "M2 装配完成")


def _missing_subscribe(name: str, handler: Callable[[Any], None], **kwargs: Any) -> Any:
    raise NotAvailableError("bus.subscribe", "M2 装配完成")


def create_context(
    *,
    plugin_id: str,
    plugin_version: str = "0.0.0",
    namespace: Optional[PluginNamespace] = None,
    session_factory: Optional[Callable[[], Any]] = None,
    publish_fn: Optional[Callable[..., str]] = None,
    subscribe_fn: Optional[Callable[..., Any]] = None,
    config_store: Optional[ConfigStore] = None,
    trace_id: Optional[str] = None,
) -> PluginContext:
    """内核侧创建插件上下文（插件作者通常不直接调用）。"""
    return PluginContext(
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        namespace=namespace,
        session_factory=session_factory,
        publish_fn=publish_fn,
        subscribe_fn=subscribe_fn,
        config_store=config_store,
        trace_id=trace_id,
    )
