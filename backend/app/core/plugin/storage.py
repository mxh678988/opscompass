"""插件私有文件空间（M5 剩余装配）：内核侧统一文件服务。

设计要点：
- 每个插件拥有独立 storage 根目录 ``<plugins_dir>/<plugin_id>/storage/``，
  插件只能访问自身根目录内的文件，互不可见；
- 路径约束：拒绝绝对路径、拒绝 ``..`` 穿越、相对路径统一正斜杠解析，
  访问解析后必须仍落在插件 storage 根目录内（防目录穿越）；
- 文本/二进制由调用方通过 ``binary`` 显式选择，写操作自动创建父目录；
- 纯文件系统实现，不依赖数据库，供 SDK ``storage`` 门面注入回调使用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

_TEXT_ENCODING = "utf-8"
_DATA = Union[str, bytes]


class StoragePathError(ValueError):
    """插件存储路径非法（绝对路径 / 越界 / 空路径）。"""


class PluginStorageEngine:
    """插件私有文件空间引擎。"""

    def __init__(self, plugins_dir: Union[str, Path]) -> None:
        self._plugins_dir = Path(plugins_dir)

    # ---- 路径约束 ----

    def _resolve(self, plugin_id: str, rel_path: str) -> Path:
        if not isinstance(rel_path, str) or not rel_path or not rel_path.strip():
            raise StoragePathError("存储路径不能为空")
        if rel_path.startswith(("/", "\\")):
            raise StoragePathError(f"存储路径不允许绝对路径: {rel_path!r}")
        root = (self._plugins_dir / plugin_id / "storage").resolve()
        # 拒绝 .. 穿越（resolve 前先挡一层，便于报错定位）
        parts = rel_path.replace("\\", "/").split("/")
        if any(p in ("", ".", "..") for p in parts[:-1]) or parts[-1] in ("", "."):
            raise StoragePathError(f"存储路径含非法段: {rel_path!r}")
        target = root.joinpath(*parts).resolve()
        if root not in target.parents and target != root:
            raise StoragePathError(f"存储路径越界: {rel_path!r}")
        return target

    # ---- 读写删列 ----

    def write(
        self,
        plugin_id: str,
        rel_path: str,
        data: _DATA,
        *,
        binary: bool = False,
    ) -> str:
        """写入文件（自动创建父目录），返回规范化相对路径。"""
        target = self._resolve(plugin_id, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            payload = data if isinstance(data, bytes) else data.encode(_TEXT_ENCODING)
            target.write_bytes(payload)
        else:
            payload = data if isinstance(data, str) else data.decode(_TEXT_ENCODING)
            target.write_text(payload, encoding=_TEXT_ENCODING)
        return _norm(rel_path)

    def read(
        self, plugin_id: str, rel_path: str, *, binary: bool = False
    ) -> _DATA:
        """读取文件；``binary=True`` 返回 bytes，否则返回 str。"""
        target = self._resolve(plugin_id, rel_path)
        if not target.is_file():
            raise FileNotFoundError(f"插件存储文件不存在: {rel_path!r}")
        if binary:
            return target.read_bytes()
        return target.read_text(encoding=_TEXT_ENCODING)

    def delete(self, plugin_id: str, rel_path: str) -> bool:
        """删除文件；文件不存在返回 False，删除成功返回 True。"""
        target = self._resolve(plugin_id, rel_path)
        if not target.is_file():
            return False
        target.unlink()
        return True

    def list(self, plugin_id: str, prefix: Optional[str] = None) -> list[str]:
        """列出插件 storage 根目录内全部文件（相对路径，正斜杠）。

        可选 ``prefix`` 过滤前缀；目录不存在返回空列表。
        """
        root = (self._plugins_dir / plugin_id / "storage").resolve()
        if not root.is_dir():
            return []
        result: list[str] = []
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = _norm(str(p.relative_to(root)))
            if prefix is not None and not rel.startswith(prefix):
                continue
            result.append(rel)
        return result


def _norm(path: str) -> str:
    """规范化相对路径：统一正斜杠。"""
    return path.replace("\\", "/")
