"""PluginRuntime：把内核能力装配到插件上下文并驱动生命周期。

内核调用方（应用启动 / 管理接口）持有本对象：

    runtime = PluginRuntime(registry, session_factory=..., bus=..., config_store=...)
    runtime.load_all()          # 发现 + 校验 + 注册
    ctx = runtime.activate("sentiment")   # 启用并返回上下文

设计约束（对应设计文档插件章节硬性要求）：
1. 插件不得直连其它模块 —— 只能拿 PluginContext
2. 插件不得自行建表 —— 表结构由插件迁移在内核监督下执行
3. 必须走内核鉴权 —— auth 门面统一注入（M3）
4. 官方/社区同接口 —— 不区分对待，仅清单签名策略不同
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.plugin.registry import PluginMeta, PluginRegistry, PluginState
from app.core.plugin.storage import PluginStorageEngine
from app.sdk.context import PluginContext, PluginNamespace, create_context

logger = logging.getLogger(__name__)


class PluginRuntime:
    """插件运行时装配器。"""

    def __init__(
        self,
        registry: PluginRegistry,
        *,
        session_factory: Optional[Callable[[], Any]] = None,
        bus: Any = None,
        config_store: Any = None,
        permissions: Any = None,
        role_templates: Any = None,
        authorizer: Optional[Callable[..., bool]] = None,
        sla_engine: Any = None,
        workflow_engine: Any = None,
        model_router: Any = None,
        signing_service: Any = None,
        storage_engine: Any = None,
        sentiment_engine: Any = None,
        connector_engine: Any = None,
    ) -> None:
        self.registry = registry
        self._session_factory = session_factory
        self._bus = bus
        self._config_store = config_store
        self._permissions = permissions
        self._role_templates = role_templates
        self._authorizer = authorizer
        self._sla_engine = sla_engine
        self._workflow_engine = workflow_engine
        self._model_router = model_router
        self._signing_service = signing_service
        self._storage_engine = storage_engine
        self._sentiment_engine = sentiment_engine
        self._connector_engine = connector_engine
        self._contexts: dict[str, PluginContext] = {}

    # ---- 装配：把内核能力包成 SDK 回调 ----

    def _make_publish(self, plugin_id: str) -> Callable[..., str]:
        def publish(name: str, payload: dict, **kwargs: Any) -> str:
            if self._bus is None:
                raise RuntimeError("事件总线未注入，无法发布事件")
            return self._bus.publish(name, payload, **kwargs)

        return publish

    def _make_subscribe(self, plugin_id: str) -> Callable[..., Any]:
        def subscribe(name: str, handler: Callable[[Any], None], **kwargs: Any) -> Any:
            if self._bus is None:
                raise RuntimeError("事件总线未注入，无法订阅事件")
            return self._bus.subscribe(name, handler, **kwargs)

        return subscribe

    def _make_authorize(self, plugin_id: str) -> Callable[..., bool]:
        """构造插件鉴权回调：优先注入的统一授权器，否则基于权限注册中心生成。"""
        if self._authorizer is not None:
            return self._authorizer
        if self._permissions is not None:
            from app.core.identity.delegation import make_permission_authorizer

            return make_permission_authorizer(self._permissions)
        raise RuntimeError(f"鉴权能力未注入，无法装配插件: {plugin_id}")

    def _make_task(self, plugin_id: str) -> Optional[Callable[..., Any]]:
        """构造待办/SLA 回调（M4）：优先显式注入的 SLA 引擎，否则基于会话工厂装配。

        返回的回调签名与 ``TaskFacade.create`` 一致：
        ``fn(plugin_id, title, sla, **kwargs)``；未注入引擎且无会话工厂时返回
        ``None``（插件侧 task.create 抛 NotAvailableError，不假装可用）。
        """
        if self._sla_engine is not None:
            engine = self._sla_engine
        elif self._session_factory is not None:
            from app.core.sla.engine import create_for_plugin

            engine = create_for_plugin
        else:
            return None

        def task_fn(pid: str, title: str, sla: Any, **kwargs: Any) -> Any:
            db = self._session_factory()
            try:
                return engine(db, pid, title, sla, **kwargs)
            finally:
                db.close()

        return task_fn

    def _make_signing(self, plugin_id: str) -> tuple[Optional[Callable[[], Any]], Optional[Callable[[], Any]]]:
        """构造签名门面回调（M7）：基于注入的签名服务返回 (verify_fn, key_query_fn)。

        verify_fn 校验插件目录发布包签名（按已登记公钥）；key_query_fn 返回
        插件当前启用公钥指纹。未注入签名服务时返回 (None, None)，插件侧
        signing.* 抛 NotAvailableError，不假装已签名受控。
        """
        if self._signing_service is None:
            return None, None
        service = self._signing_service
        plugin_dir = self.registry.plugins_dir / plugin_id

        def verify_fn() -> dict[str, Any]:
            status, message = service.verify_plugin(plugin_dir, plugin_id)
            return {"verified": status == "ok", "status": status, "message": message}

        def key_query_fn() -> Optional[str]:
            return service.get_fingerprint(plugin_id)

        return verify_fn, key_query_fn

    def _make_storage(self, plugin_id: str) -> Optional[Callable[..., Any]]:
        """构造存储门面回调（M5）：基于插件私有 storage 根目录的读写删列。

        未显式注入引擎时按 ``registry.plugins_dir`` 自动装配
        ``PluginStorageEngine``；registry 无插件目录时返回 None，
        插件侧 storage.* 抛 NotAvailableError，不假装有持久空间。
        """
        if self._storage_engine is None:
            base = getattr(self.registry, "plugins_dir", None)
            if base is None:
                return None
            self._storage_engine = PluginStorageEngine(base)
        engine = self._storage_engine

        def storage_fn(*, op: str, path: str, data: Any = None, prefix: Optional[str] = None) -> Any:
            if op == "save":
                return engine.write(plugin_id, path, data)
            if op == "read":
                return engine.read(plugin_id, path)
            if op == "delete":
                return engine.delete(plugin_id, path)
            if op == "list":
                return engine.list(plugin_id, prefix)
            raise ValueError(f"未知存储操作: {op}")

        return storage_fn

    def _make_sentiment(self, plugin_id: str) -> Optional[Callable[..., Any]]:
        """构造舆情门面回调（M8）：基于注入的舆情引擎返回 callable。

        舆情引擎属插件业务层（``plugins/sentiment/backend``），内核不
        感知插件代码路径：仅当外部显式注入 ``sentiment_engine`` 时才装配，
        否则返回 None，插件侧 sentiment.* 抛
        NotAvailableError("sentiment.*", "M8 装配完成")，不假装可用。
        """
        if self._sentiment_engine is None:
            return None
        engine = self._sentiment_engine

        def sentiment_fn(*, action: str, params: Optional[dict] = None, **kwargs: Any) -> Any:
            db = self._session_factory()
            try:
                return engine(db, plugin_id, action, params or {}, **kwargs)
            finally:
                db.close()

        return sentiment_fn

    def _make_connector(self, plugin_id: str) -> Optional[Callable[..., Any]]:
        """构造连接器门面回调（M17）：基于注入的连接器引擎返回 callable。

        连接器引擎属插件业务层（``plugins/crm_connector/backend``），内核
        不感知插件代码路径：仅当外部显式注入 ``connector_engine`` 时才装配，
        否则返回 None，插件侧 connector.* 抛
        NotAvailableError("connector.*", "M17 装配完成")，不假装可用。
        """
        if self._connector_engine is None:
            return None
        engine = self._connector_engine

        def connector_fn(*, action: str, params: Optional[dict] = None, **kwargs: Any) -> Any:
            db = self._session_factory()
            try:
                return engine(db, plugin_id, action, params or {}, **kwargs)
            finally:
                db.close()

        return connector_fn

    # ---- M8 插件 backend 加载与引擎注入 ----

    def inject_sentiment_engine(self, engine: Any) -> None:
        """插件 backend 通过本方法把舆情引擎注入内核（register 内调用）。

        注入对象与 ``_make_sentiment`` 约定一致：
        engine(db, plugin_id, action, params, **kwargs) -> result。
        """
        self._sentiment_engine = engine

    def inject_connector_engine(self, engine: Any) -> None:
        """插件 backend 通过本方法把连接器引擎注入内核（register 内调用）。

        注入对象与 ``_make_connector`` 约定一致：
        engine(db, plugin_id, action, params, **kwargs) -> result。
        """
        self._connector_engine = engine

    def load_backend(self, plugin_id: str) -> Any:
        """按清单 entry 加载插件 backend 并调用入口函数（幂等）。

        内核不感知插件内部结构：仅把自身传给入口函数（如
        ``register(runtime)``），插件通过 ``inject_*`` 回调把引擎注入
        内核；backend 模块须相对导入自身子模块（backend.src.*），加载
        期间仅临时把插件目录加入 sys.path，结束后移除。

        说明：当前按 backend.src.<mod> 包路径加载，适用于单官方插件；
        多插件同名 backend 包时需升级为插件专属模块命名空间。
        """
        meta = self.registry.get(plugin_id)
        if meta is None:
            raise KeyError(f"插件未注册: {plugin_id}")
        if not meta.entry:
            raise RuntimeError(f"插件 {plugin_id} 未声明 entry")
        mod_name, _, func_name = meta.entry.partition(":")
        if not mod_name or not func_name:
            raise RuntimeError(f"插件 {plugin_id} entry 非法: {meta.entry!r}")

        cache_key = f"__plugin_backend_{plugin_id}"
        if cache_key in sys.modules:
            # 模块复用缓存，但入口函数必须每次执行：register 把引擎注入
            # 的是“当前 runtime 实例”，跳过会导致新实例未装配（幂等约定：
            # 入口函数只做注入类副作用，重复调用安全）。
            mod = sys.modules[cache_key]
            func = getattr(mod, func_name, None)
            if func is not None:
                func(self)
                return mod

        plugin_dir = self.registry.plugins_dir / plugin_id
        backend_dir = plugin_dir / "backend"
        # 校验模块物理存在（entry 为相对插件根的包路径，如 backend.src.main）
        mod_rel = mod_name.replace(".", "/") + ".py"
        if not (plugin_dir / mod_rel).exists():
            raise RuntimeError(
                f"插件 {plugin_id} backend 模块不存在: {plugin_dir / mod_rel}"
            )

        # 插件专属命名空间加载：多插件共用 "backend.src.*" 包名时，直接
        # importlib.import_module 会把同名模块写入 sys.modules 并互相覆盖。
        # 这里把每个插件的 backend 包挂到 __plugin_ns__.<plugin_id> 下，使
        # 各插件拥有独立模块图（插件内部相对导入不受影响）。
        ns_root = "__plugin_ns__"
        ns_root_mod = sys.modules.get(ns_root)
        if ns_root_mod is None:
            ns_root_mod = types.ModuleType(ns_root)
            ns_root_mod.__path__ = []
            sys.modules[ns_root] = ns_root_mod
        ns_plugin_name = f"{ns_root}.{plugin_id}"
        ns_plugin = sys.modules.get(ns_plugin_name)
        if ns_plugin is None:
            ns_plugin = types.ModuleType(ns_plugin_name)
            ns_plugin.__path__ = [str(plugin_dir), str(backend_dir)]
            sys.modules[ns_plugin_name] = ns_plugin

        try:
            mod = importlib.import_module(f"{ns_plugin_name}.{mod_name}")
            sys.modules[cache_key] = mod
            func = getattr(mod, func_name, None)
            if func is None:
                raise RuntimeError(
                    f"插件 {plugin_id} 入口函数不存在: {meta.entry!r}"
                )
            func(self)
            return mod
        except Exception as e:
            raise RuntimeError(f"插件 {plugin_id} backend 加载失败: {e}") from e

    def provision_tables(self, plugin_id: str) -> list[str]:
        """内核监督下为插件建表（插件不得自行建表，M2 设计约束）。

        复用已加载 backend 的自有 database 模块 metadata，以内核会话
        bind 执行 create_all，返回已建表名列表。
        """
        if self._session_factory is None:
            raise RuntimeError("session_factory 未注入，无法建表")
        self.load_backend(plugin_id)  # 确保 backend 已加载（幂等）

        cache_key = f"__plugin_backend_{plugin_id}"
        mod = sys.modules.get(cache_key)
        if mod is None:
            raise RuntimeError(f"插件 {plugin_id} backend 未加载")
        # backend.src.<mod> → backend.src.database
        db_mod_name = mod.__name__.rsplit(".", 1)[0] + ".database"
        db_mod = sys.modules.get(db_mod_name)
        if db_mod is None or not hasattr(db_mod, "Base"):
            raise RuntimeError(f"插件 {plugin_id} 无可建表 database 模块")

        db = self._session_factory()
        try:
            engine = db.get_bind()
            db_mod.Base.metadata.create_all(engine)
        finally:
            db.close()
        return sorted(db_mod.Base.metadata.tables.keys())

    def build_context(self, plugin_id: str) -> PluginContext:
        """为指定插件装配上下文（不改变插件状态）。"""
        meta = self.registry.get(plugin_id)
        if meta is None:
            raise KeyError(f"插件未注册: {plugin_id}")

        ns_data = meta.namespace or {}
        namespace = PluginNamespace(
            tables=str(ns_data.get("tables", "")),
            events=str(ns_data.get("events", "")),
            permissions=str(ns_data.get("permissions", "")),
        )

        signing_verify, signing_query = self._make_signing(meta.plugin_id)

        ctx = create_context(
            plugin_id=meta.plugin_id,
            plugin_version=meta.version,
            namespace=namespace,
            session_factory=self._session_factory,
            publish_fn=self._make_publish(meta.plugin_id),
            subscribe_fn=self._make_subscribe(meta.plugin_id),
            config_store=self._config_store,
            authorize_fn=(
                self._make_authorize(meta.plugin_id)
                if (self._authorizer is not None or self._permissions is not None)
                else None
            ),
            task_fn=self._make_task(meta.plugin_id),
            workflow_engine=self._workflow_engine,
            model_router=self._model_router,
            storage_fn=self._make_storage(meta.plugin_id),
            signing_verify_fn=signing_verify,
            signing_key_query_fn=signing_query,
            sentiment_fn=self._make_sentiment(meta.plugin_id),
            connector_fn=self._make_connector(meta.plugin_id),
        )
        self._contexts[plugin_id] = ctx
        return ctx

    # ---- M3 统一身份治理：权限点 / 推荐角色同步 ----

    def sync_permissions(self, plugin_id: str) -> None:
        """把插件清单声明的权限点/推荐角色登记进身份注册中心（幂等）。

        ``_permissions`` / ``_role_templates`` 未注入（旧内核）时静默跳过，
        保证 M2 行为不被破坏；权限点强制三段式且须落在插件命名空间内，
        越界条目由注册中心拒绝并抛 ``NamespaceViolation``。
        """
        meta = self.registry.get(plugin_id)
        if meta is None:
            raise KeyError(f"插件未注册: {plugin_id}")
        ns_data = meta.namespace or {}
        prefix = str(ns_data.get("permissions", "") or f"{plugin_id}:")
        if self._permissions is not None:
            self._permissions.register_plugin(
                plugin_id,
                list(meta.permissions or []),
                namespace_prefix=prefix,
            )
        if self._role_templates is not None:
            self._role_templates.register_plugin_roles(
                plugin_id,
                list(meta.roles or []),
                namespace_prefix=prefix,
            )

    def _release_identity(self, plugin_id: str) -> None:
        """卸载插件：收回其登记的权限点与推荐角色（只删插件声明，不碰用户数据）。"""
        if self._permissions is not None:
            self._permissions.unregister_plugin(plugin_id)
        if self._role_templates is not None:
            self._role_templates.unregister_plugin(plugin_id)

    # ---- 生命周期 ----

    def load_all(self) -> list[str]:
        """发现并注册全部插件，返回成功注册的 id 列表。"""
        registered: list[str] = []
        for plugin_id in self.registry.discover():
            try:
                self.registry.register(plugin_id)
                registered.append(plugin_id)
            except Exception as e:  # noqa: BLE001 - 单个插件失败不应阻断整体
                logger.error("插件 %s 注册失败: %s", plugin_id, e)
        return registered

    def activate(self, plugin_id: str) -> PluginContext:
        """启用插件并返回其上下文（先强制验签，再登记权限点/装配上下文）。

        官方插件（kind=official）启用前强制验签：签名缺失/无效/内容被篡改、
        公钥未登记或内核未装配签名服务，均抛 ``PluginVerificationError``
        （403 语义）拒绝启用；社区插件不强制，登记公钥后同样可验。
        """
        meta = self.registry.get(plugin_id)
        if meta is None:
            raise KeyError(f"插件未注册: {plugin_id}")
        if meta.kind == "official":
            self._enforce_official_signature(plugin_id)
        self.sync_permissions(plugin_id)
        ctx = self.build_context(plugin_id)
        self.registry.enable(plugin_id)
        return ctx

    def _enforce_official_signature(self, plugin_id: str) -> None:
        """官方插件强制验签（S3）：验签未通过一律拒绝启用，报 403 语义。

        未注入签名服务视为“无法证明官方身份”，同样拒绝启用，绝不降级放行。
        """
        from app.core.plugin.signing import (
            VERIFY_OK,
            PluginVerificationError,
        )

        if self._signing_service is None:
            raise PluginVerificationError(
                f"官方插件 {plugin_id} 必须验签，但内核未装配签名服务，拒绝启用"
            )
        plugin_dir = self.registry.plugins_dir / plugin_id
        status, message = self._signing_service.verify_plugin(plugin_dir, plugin_id)
        if status != VERIFY_OK:
            raise PluginVerificationError(
                f"官方插件 {plugin_id} 验签失败，拒绝启用: {message}"
            )

    def deactivate(self, plugin_id: str) -> None:
        """禁用插件（保留数据与权限声明），回收上下文。"""
        self.registry.disable(plugin_id)
        self._contexts.pop(plugin_id, None)

    def uninstall(self, plugin_id: str) -> None:
        """卸载插件，回收上下文并收回权限点/推荐角色。数据清理由调用方按策略决定。"""
        self.registry.uninstall(plugin_id)
        self._release_identity(plugin_id)
        self._contexts.pop(plugin_id, None)

    def context(self, plugin_id: str) -> Optional[PluginContext]:
        return self._contexts.get(plugin_id)

    @property
    def active_plugins(self) -> list[str]:
        return [
            pid
            for pid, meta in self.registry.plugins.items()
            if meta.state == PluginState.ENABLED
        ]


def default_plugins_dir(app_root: Path | str) -> Path:
    """约定：插件目录位于后端工程根下 ``plugins/``。"""
    return Path(app_root) / "plugins"
