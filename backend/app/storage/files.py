"""文件对象适配器：本地受管目录（导入原始文件 / 导出产物）+ 校验哈希。

职责：为「文件类数据」提供统一读写与校验入口，供导入任务与一致性对账复用。
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from app.core.config import BASE_DIR, settings
from app.storage.base import AdapterCapability

logger = logging.getLogger(__name__)

CHUNK = 1024 * 1024


def resolve_dir(raw: str) -> Path:
    """把配置目录解析为绝对路径（相对路径基于项目根目录）。"""
    path = Path(raw)
    if not path.is_absolute():
        path = (BASE_DIR / raw).resolve()
    return path


class FileStorageAdapter:
    """文件存储适配器（本地文件系统）。"""

    kind = "file"
    engine = "local_fs"
    label = "文件对象存储"

    # ------------------------------------------------------------ 目录
    @property
    def root(self) -> Path:
        return resolve_dir(settings.DATA_DIR)

    @property
    def export_root(self) -> Path:
        return resolve_dir(settings.EXPORT_DIR)

    def resolve(self, rel_path: str) -> Path:
        """把受管相对路径解析为绝对路径，并阻止越权跳出数据根目录。"""
        target = (self.root / rel_path.lstrip("/\\")).resolve()
        root = self.root.resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"路径越界: {rel_path}")
        return target

    def ensure_dirs(self) -> list[str]:
        created = []
        for path in (self.root, self.root / "raw", self.export_root):
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created.append(str(path))
        return created

    # ------------------------------------------------------------ 读写
    def write_bytes(self, rel_path: str, content: bytes) -> dict:
        target = self.resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return self.stat(rel_path)

    def read_bytes(self, rel_path: str) -> bytes:
        return self.resolve(rel_path).read_bytes()

    @staticmethod
    def hash_file(path: Path) -> Optional[str]:
        if not path.exists() or not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def stat(self, rel_path: str) -> dict:
        path = self.resolve(rel_path)
        if not path.exists() or not path.is_file():
            return {"path": str(path), "exists": False, "size": 0, "sha256": None}
        return {
            "path": str(path),
            "exists": True,
            "size": path.stat().st_size,
            "modified": path.stat().st_mtime,
            "sha256": self.hash_file(path),
        }

    def list_files(self, rel_dir: str = "raw", limit: int = 500) -> list[dict]:
        base = self.resolve(rel_dir)
        if not base.exists():
            return []
        items = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                items.append(
                    {
                        "rel_path": str(path.relative_to(self.root)).replace("\\", "/"),
                        "size": path.stat().st_size,
                    }
                )
            if len(items) >= limit:
                break
        return items

    # ------------------------------------------------------------ 校验
    def verify(self, expected: list[dict]) -> dict:
        """按期望清单校验文件存在性与哈希。

        expected: [{"path": 相对/绝对路径, "sha256": 期望哈希（可空）}]
        """
        missing, mismatch, ok = [], [], 0
        for item in expected:
            raw = item.get("path") or ""
            try:
                path = Path(raw)
                if not path.is_absolute():
                    path = self.resolve(raw)
            except Exception:
                missing.append({"path": raw, "reason": "路径非法"})
                continue
            if not path.exists() or not path.is_file():
                missing.append({"path": str(path), "reason": "文件不存在"})
                continue
            expect_hash = item.get("sha256")
            actual = self.hash_file(path)
            if expect_hash and actual and expect_hash != actual:
                mismatch.append(
                    {"path": str(path), "expected": expect_hash, "actual": actual}
                )
            else:
                ok += 1
        return {
            "checked": len(expected),
            "matched": ok,
            "missing": missing,
            "mismatched": mismatch,
        }

    def cleanup_candidates(self, rel_dir: str = "raw") -> dict:
        """统计受管目录规模（只读，不删除）。"""
        base = self.resolve(rel_dir)
        if not base.exists():
            return {"dir": str(base), "exists": False, "files": 0, "bytes": 0}
        files = [p for p in base.rglob("*") if p.is_file()]
        return {
            "dir": str(base),
            "exists": True,
            "files": len(files),
            "bytes": sum(p.stat().st_size for p in files),
        }

    # ------------------------------------------------------------ 状态
    def capability(self, db=None) -> AdapterCapability:
        root, export = self.root, self.export_root
        detail = {
            "root": str(root),
            "root_exists": root.exists(),
            "root_writable": root.exists() and root.is_dir() and _writable(root),
            "export_dir": str(export),
            "export_exists": export.exists(),
            "raw_files": self.cleanup_candidates("raw")["files"],
        }
        return AdapterCapability(
            kind=self.kind,
            engine=self.engine,
            label=self.label,
            available=bool(detail["root_exists"] and detail["root_writable"]),
            detail=detail,
        )

    def stats(self, db=None) -> dict:
        raw = self.cleanup_candidates("raw")
        exports = self.cleanup_candidates(str(self.export_root.relative_to(self.root)).replace("\\", "/")) if self.export_root.is_relative_to(self.root) else {"files": 0, "bytes": 0}
        return {
            "kind": self.kind,
            "engine": self.engine,
            "root": str(self.root),
            "raw": raw,
            "exports": exports,
        }


def _writable(path: Path) -> bool:
    try:
        probe = path / ".oc_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


file_adapter = FileStorageAdapter()
