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

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.plugin.registry import PluginMeta, PluginRegistry, PluginState
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
    ) -> None:
        self.registry = registry
        self._session_factory = session_factory
        self._bus = bus
        self._config_store = config_store
        self._permissions = permissions
        self._role_templates = role_templates
        self._authorizer = authorizer
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
        """启用插件并返回其上下文（先登记权限点/推荐角色，再装配上下文）。"""
        self.sync_permissions(plugin_id)
        ctx = self.build_context(plugin_id)
        self.registry.enable(plugin_id)
        return ctx

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
