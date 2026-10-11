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
    """权限门面：统一鉴权，插件不得自行实现（M3 统一身份治理落地）。

    未注入 ``authorize_fn``（内核未装配）时，``require`` / ``check`` 一律抛
    ``NotAvailableError`` 并标注计划版本 M3，明确告知插件身份治理尚未就绪，
    防止插件误以为已受控；装配后先校验权限点落在插件自身命名空间内
    （越界抛 ``NamespaceViolation``），再交给内核注入的鉴权回调判定。
    """

    def __init__(
        self,
        plugin_id: str,
        namespace_permissions: str = "",
        authorize_fn: Optional[Callable[..., bool]] = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._prefix = namespace_permissions or f"{plugin_id}:"
        self._authorize = authorize_fn

    def _require_authorize(self, feature: str) -> Callable[..., bool]:
        if self._authorize is None:
            raise NotAvailableError(feature, "M3 装配完成")
        return self._authorize

    def _check_prefix(self, perm_code: str) -> None:
        if not perm_code.startswith(self._prefix):
            raise NamespaceViolation(
                self._plugin_id, "权限点", perm_code, f"{self._prefix}*"
            )

    def require(self, perm_code: str, user: Any = None) -> None:
        """校验当前用户是否具备权限点；不具备抛 PermissionError。"""
        authorize = self._require_authorize("auth.require")
        self._check_prefix(perm_code)
        if not authorize(perm_code, user, plugin_id=self._plugin_id):
            raise PermissionError(f"权限不足: {perm_code}")

    def check(self, user: Any, perm_code: str) -> bool:
        """布尔式鉴权（不抛权限异常）；未装配同样抛 NotAvailableError。"""
        authorize = self._require_authorize("auth.check")
        self._check_prefix(perm_code)
        return bool(authorize(perm_code, user, plugin_id=self._plugin_id))


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
    """模型门面：只声明能力，不指定模型（M6 模型路由落地）。

    内核在装载插件时注入 ``model_router``（``app.core.model_router.routing``
    模块）与会话工厂，插件调用 ``run`` 即在内核完成「能力声明 → 路由决策 →
    降级/兜底 → 计量/缓存」；未注入时抛 ``NotAvailableError`` 指明 M6，
    防止插件误以为已装配。敏感能力由内核强制本地，插件不可绕过。
    """

    def __init__(
        self,
        plugin_id: str,
        model_router: Any = None,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._router = model_router
        self._session_factory = session_factory

    def _require(self, feature: str) -> Any:
        if self._router is None or self._session_factory is None:
            raise NotAvailableError(feature, "M6 装配完成")
        return self._router

    def _db(self) -> Any:
        return self._session_factory()

    def run(self, capability: str, input: Any, **opts: Any) -> Any:
        """路由并执行一次模型调用，返回 ``ModelRouteResult``。

        可选参数（opts）：tenant_id / sensitive / force_local / model /
        temperature / max_tokens / skip_cache。
        """
        router = self._require("model.run")
        db = self._db()
        try:
            return router.route_model(db, capability, input, **opts)
        finally:
            db.close()

    def declare(self, capability: str, **opts: Any) -> Any:
        """登记/更新能力声明（kind/description/sensitive/fallback_cloud/
        cost_cap/cache_ttl_seconds/enabled）。"""
        router = self._require("model.declare")
        db = self._db()
        try:
            return router.upsert_capability(db, capability=capability, **opts)
        finally:
            db.close()

    def stats(self, **opts: Any) -> dict[str, Any]:
        """调用计量汇总（tenant_id/capability/since/limit_days 过滤）。"""
        router = self._require("model.stats")
        db = self._db()
        try:
            return router.route_log_stats(db, **opts)
        finally:
            db.close()

    def set_global_degrade(self, degrade_all: bool) -> None:
        """一键全局降级（进程内生效；运维故障时快速止损）。"""
        router = self._require("model.degrade")
        router.set_global_degrade(degrade_all)

    def is_degraded(self) -> bool:
        router = self._require("model.is_degraded")
        return router.is_degraded()


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


class SigningFacade:
    """签名门面：插件侧查询自身签名状态并校验发布包完整性（M7 插件签名密钥体系落地）。

    内核在装载插件时注入 ``verify_fn``（按已登记公钥验签自身发布包）与
    ``key_query_fn``（查询已登记公钥指纹）；未注入时抛 ``NotAvailableError``
    指明 M7，防止插件误以为已签名受控。
    """

    def __init__(
        self,
        plugin_id: str,
        verify_fn: Optional[Callable[[], Any]] = None,
        key_query_fn: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._verify = verify_fn
        self._key_query = key_query_fn

    def verify_self(self) -> dict[str, Any]:
        """校验插件自身发布包签名，返回 {"verified", "status", "message"}。"""
        if self._verify is None:
            raise NotAvailableError("signing.verify_self", "M7 装配完成")
        return self._verify()

    def key_fingerprint(self) -> Optional[str]:
        """查询插件当前启用公钥指纹；未登记返回 None。"""
        if self._key_query is None:
            raise NotAvailableError("signing.key_fingerprint", "M7 装配完成")
        return self._key_query()


class TaskFacade:
    """待办门面：自动挂 SLA 与升级链（M4 任务 SLA 落地）。

    内核在装载插件时注入 ``task_fn`` 回调（基于内核 ``create_for_plugin``
    构造），插件调用 ``create`` 即在内核创建带 SLA 的待办；未注入时抛
    ``NotAvailableError`` 指明 M4，防止插件误以为已装配。
    """

    def __init__(
        self,
        plugin_id: str,
        task_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._task_fn = task_fn

    def create(self, title: str, sla: Any = None, **kwargs: Any) -> Any:
        if self._task_fn is None:
            raise NotAvailableError("task.create", "M4 装配完成")
        return self._task_fn(self._plugin_id, title, sla, **kwargs)


class WorkflowFacade:
    """工作流门面：创建/推进/人工确认/暂停恢复取消实例（M5 工作流引擎落地）。

    内核在装载插件时注入 ``workflow_engine``（``app.core.workflow.engine``
    模块）与会话工厂，插件调用即在内核执行工作流操作；未注入时抛
    ``NotAvailableError`` 指明 M5，防止插件误以为已装配。
    """

    def __init__(
        self,
        plugin_id: str,
        workflow_engine: Any = None,
        session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._engine = workflow_engine
        self._session_factory = session_factory

    def _require(self, feature: str) -> Any:
        if self._engine is None or self._session_factory is None:
            raise NotAvailableError(feature, "M5 装配完成")
        return self._engine

    def _db(self) -> Any:
        return self._session_factory()

    def create_instance(
        self,
        defn: dict,
        *,
        title: Optional[str] = None,
        context: Optional[dict] = None,
        created_by: Optional[int] = None,
    ) -> Any:
        """创建实例并物化全部步骤（状态 created，未启动）。"""
        engine = self._require("workflow.create")
        db = self._db()
        try:
            return engine.create_instance(
                db, defn, title=title, context=context, created_by=created_by
            )
        finally:
            db.close()

    def run(self, instance_id: int, **kwargs: Any) -> Any:
        """启动/续跑实例：状态 created/running 时推进，返回最新实例状态。"""
        engine = self._require("workflow.run")
        db = self._db()
        try:
            return engine.run(db, instance_id, **kwargs)
        finally:
            db.close()

    def confirm_wait_step(self, instance_id: int, seq: int, **kwargs: Any) -> Any:
        """人工确认 wait 步骤：置 completed，写入确认信息，按 confirm 继续推进。"""
        engine = self._require("workflow.confirm")
        db = self._db()
        try:
            return engine.confirm_wait_step(db, instance_id, seq, **kwargs)
        finally:
            db.close()

    def timeout_wait_step(self, instance_id: int, seq: int, **kwargs: Any) -> Any:
        """wait 超时兜底：置 completed 并标记 timeout，按 timeout_next 继续推进。"""
        engine = self._require("workflow.timeout")
        db = self._db()
        try:
            return engine.timeout_wait_step(db, instance_id, seq, **kwargs)
        finally:
            db.close()

    def pause(self, instance_id: int, reason: Optional[str] = None) -> Any:
        """暂停实例（created/running/waiting 可暂停）。"""
        engine = self._require("workflow.pause")
        db = self._db()
        try:
            return engine.pause_instance(db, instance_id, reason=reason)
        finally:
            db.close()

    def resume(self, instance_id: int, **kwargs: Any) -> Any:
        """恢复暂停实例并继续推进。"""
        engine = self._require("workflow.resume")
        db = self._db()
        try:
            return engine.resume_instance(db, instance_id, **kwargs)
        finally:
            db.close()

    def cancel(self, instance_id: int, reason: Optional[str] = None) -> Any:
        """取消实例：pending/running 步骤标记 skipped，终态不可取消。"""
        engine = self._require("workflow.cancel")
        db = self._db()
        try:
            return engine.cancel_instance(db, instance_id, reason=reason)
        finally:
            db.close()

    def list_waiting_steps(self, **kwargs: Any) -> list[Any]:
        """待办查询：全部 waiting 步骤，可按 wait_key / assigned_to 过滤。"""
        engine = self._require("workflow.list_waiting")
        db = self._db()
        try:
            return engine.list_waiting_steps(db, **kwargs)
        finally:
            db.close()

    def step_status_counts(self, instance_id: int) -> dict[str, int]:
        """实例步骤状态统计（进度看板）。"""
        engine = self._require("workflow.status_counts")
        db = self._db()
        try:
            return engine.step_status_counts(db, instance_id)
        finally:
            db.close()


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
        authorize_fn: Optional[Callable[..., bool]] = None,
        task_fn: Optional[Callable[..., Any]] = None,
        workflow_engine: Any = None,
        model_router: Any = None,
        signing_verify_fn: Optional[Callable[[], Any]] = None,
        signing_key_query_fn: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.namespace = namespace or PluginNamespace()
        self._session_factory = session_factory
        self.log = LogFacade(plugin_id, trace_id)
        self.db = DbFacade(plugin_id, self.namespace.tables, session_factory)
        self.bus = EventBusFacade(
            plugin_id,
            self.namespace.events,
            publish_fn or _missing_publish,
            subscribe_fn or _missing_subscribe,
        )
        self.auth = AuthFacade(plugin_id, self.namespace.permissions, authorize_fn)
        self.config = ConfigFacade(plugin_id, config_store)
        self.job = JobFacade(plugin_id)
        self.storage = StorageFacade()
        self.task = TaskFacade(plugin_id, task_fn)
        self.workflow = WorkflowFacade(plugin_id, workflow_engine, session_factory)
        self.model = ModelFacade(plugin_id, model_router, session_factory)
        self.signing = SigningFacade(
            plugin_id, signing_verify_fn, signing_key_query_fn
        )
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
    authorize_fn: Optional[Callable[..., bool]] = None,
    task_fn: Optional[Callable[..., Any]] = None,
    workflow_engine: Any = None,
    model_router: Any = None,
    signing_verify_fn: Optional[Callable[[], Any]] = None,
    signing_key_query_fn: Optional[Callable[[], Any]] = None,
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
        authorize_fn=authorize_fn,
        task_fn=task_fn,
        workflow_engine=workflow_engine,
        model_router=model_router,
        signing_verify_fn=signing_verify_fn,
        signing_key_query_fn=signing_key_query_fn,
    )
