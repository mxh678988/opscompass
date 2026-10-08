"""插件加载器：按 entry 字段动态导入插件模块。

用法示例（供 M5 工作流引擎等内核组件调用）：
    from app.core.plugin.loader import load_plugin_module
    mod = load_plugin_module("sentiment")
    if hasattr(mod, "register"):
        mod.register()
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_plugin_module(plugin_id: str, plugins_dir: Path) -> Any | None:
    """加载指定插件的 Python 模块。

    按 entry 字段（如 "main:register"）找到模块并导入，
    然后调用入口函数。

    :param plugin_id: 插件 id
    :param plugins_dir: 插件目录基路径
    :returns: 模块对象，加载失败返回 None
    """
    meta = importlib.import_module(
        f"app.core.plugin.loader"
    )  # 占位，实际通过 registry 获取 meta

    plugin_dir = plugins_dir / plugin_id
    manifest_path = plugin_dir / "plugin.yaml"

    if not manifest_path.exists():
        logger.error("插件 %s 清单不存在: %s", plugin_id, manifest_path)
        return None

    try:
        import yaml
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("插件 %s 清单解析失败: %s", plugin_id, e)
        return None

    entry = data.get("entry", "")
    if not entry:
        logger.warning("插件 %s 未声明 entry", plugin_id)
        return None

    module_path, func_name = entry.rsplit(":", 1)

    # 将插件 backend 目录加入 sys.path
    backend_dir = plugin_dir / "backend"
    if backend_dir.is_dir():
        import sys
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))

    try:
        mod = importlib.import_module(module_path)
    except (ImportError, ModuleNotFoundError) as e:
        logger.error("插件 %s 模块 %s 导入失败: %s", plugin_id, module_path, e)
        return None
    except Exception as e:
        logger.error("插件 %s 模块 %s 加载异常: %s", plugin_id, module_path, e)
        return None

    func = getattr(mod, func_name, None)
    if func is None:
        logger.error("插件 %s 入口函数 %s 不存在于模块 %s", plugin_id, func_name, module_path)
        return None

    return func, mod
