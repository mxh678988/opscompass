"""插件运行时：发现、加载、生命周期管理。

插件目录包结构：
- plugin.yaml 清单
- backend/ 服务端代码
- frontend/ 前端产物（可选）
- migrations/ 迁移脚本（可选）

本模块只注册插件生命周期状态（已安装/已启用/已禁用/已卸载），
具体的插件加载、事件路由、权限注入由 M3（身份治理）和 M5（工作流引擎）
在 M2 冻结后逐步接入。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Sequence

from app.core.plugin.manifest_validator import (
    ManifestResult,
    validate_manifest,
)

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """插件生命周期状态。"""
    INSTALLED = auto()
    ENABLED = auto()
    DISABLED = auto()
    UNINSTALLED = auto()


@dataclass
class PluginMeta:
    """插件元信息（从 plugin.yaml 解析后缓存）。"""
    plugin_id: str
    name: str
    version: str
    kind: str  # official / community
    min_kernel_version: str
    entry: str
    namespace: dict[str, str]  # tables / events / permissions 前缀
    permissions: list[dict[str, str]]
    state: PluginState = PluginState.UNINSTALLED


class PluginRegistry:
    """插件注册表。

    负责：
    1. 发现：扫描 `plugins/` 目录下的 plugin.yaml
    2. 加载：校验 manifest + 注册到内存注册表
    3. 生命周期：enable / disable / uninstall / reenable
    """

    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir = plugins_dir
        self._plugins: dict[str, PluginMeta] = {}
        self._errors: dict[str, str] = {}

    def discover(self) -> list[str]:
        """扫描 plugins 目录，返回发现的插件 id 列表。

        每个插件目录内必须有 plugin.yaml，且校验通过。
        """
        if not self.plugins_dir.exists():
            logger.info("插件目录不存在: %s", self.plugins_dir)
            return []

        ids: list[str] = []
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest_path = plugin_dir / "plugin.yaml"
            if not manifest_path.exists():
                logger.debug("跳过（无 plugin.yaml）: %s", plugin_dir.name)
                continue

            result = validate_manifest(manifest_path)
            if not result.valid:
                self._errors[plugin_dir.name] = "; ".join(
                    f"{e.field}: {e.detail}" for e in result.errors
                )
                logger.error("插件 %s 清单校验失败: %s", plugin_dir.name, result.errors)
                continue

            ids.append(plugin_dir.name)

        return ids

    def register(self, plugin_id: str) -> PluginMeta:
        """将已发现的插件注册到运行时。"""
        plugin_dir = self.plugins_dir / plugin_id
        manifest_path = plugin_dir / "plugin.yaml"

        result = validate_manifest(manifest_path)
        if not result.valid:
            self._errors[plugin_id] = "; ".join(
                f"{e.field}: {e.detail}" for e in result.errors
            )
            raise RuntimeError(f"清单校验失败: {result.errors}")

        manifest = manifest_path.read_text(encoding="utf-8")
        import yaml
        data = yaml.safe_load(manifest)

        meta = PluginMeta(
            plugin_id=plugin_id,
            name=str(data.get("name", plugin_id)),
            version=str(data.get("version", "0.0.0")),
            kind=str(data.get("kind", "community")),
            min_kernel_version=str(data.get("min_kernel_version", "0.0.0")),
            entry=str(data.get("entry", "")),
            namespace=data.get("namespace", {}),
            permissions=data.get("permissions", []),
            state=PluginState.INSTALLED,
        )

        self._plugins[plugin_id] = meta
        logger.info("插件已注册: %s (v%s, %s)", plugin_id, meta.version, meta.kind)
        return meta

    @property
    def plugins(self) -> dict[str, PluginMeta]:
        return dict(self._plugins)

    def get(self, plugin_id: str) -> Optional[PluginMeta]:
        return self._plugins.get(plugin_id)

    def enable(self, plugin_id: str) -> None:
        """启用插件：INSTALLED → ENABLED。"""
        meta = self._plugins.get(plugin_id)
        if not meta:
            raise KeyError(f"插件不存在: {plugin_id}")
        if meta.state not in (PluginState.INSTALLED, PluginState.DISABLED):
            raise RuntimeError(
                f"插件 {plugin_id} 当前状态 {meta.state.name}，无法启用"
            )
        meta.state = PluginState.ENABLED
        logger.info("插件已启用: %s", plugin_id)

    def disable(self, plugin_id: str) -> None:
        """禁用插件：ENABLED → DISABLED，数据保留。"""
        meta = self._plugins.get(plugin_id)
        if not meta:
            raise KeyError(f"插件不存在: {plugin_id}")
        if meta.state != PluginState.ENABLED:
            raise RuntimeError(
                f"插件 {plugin_id} 当前状态 {meta.state.name}，无法禁用"
            )
        meta.state = PluginState.DISABLED
        logger.info("插件已禁用: %s", plugin_id)

    def uninstall(self, plugin_id: str) -> None:
        """卸载插件：ENABLED/DISABLED → UNINSTALLED。"""
        meta = self._plugins.get(plugin_id)
        if not meta:
            raise KeyError(f"插件不存在: {plugin_id}")
        if meta.state in (PluginState.INSTALLED, PluginState.UNINSTALLED):
            raise RuntimeError(
                f"插件 {plugin_id} 当前状态 {meta.state.name}，无法卸载"
            )
        meta.state = PluginState.UNINSTALLED
        logger.info("插件已卸载: %s", plugin_id)
        self._plugins.pop(plugin_id)

    @property
    def errors(self) -> dict[str, str]:
        return dict(self._errors)
