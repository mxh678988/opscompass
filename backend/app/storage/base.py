"""存储适配层公共契约：能力描述与适配器基类。

设计目标：把「接入数据类型」与「底层存储实现」解耦，
上层只依赖 kind（数据类型）+ engine（引擎标识），便于后续替换实现。
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class AdapterCapability:
    """适配器能力与健康状态。"""

    kind: str
    engine: str
    label: str = ""
    available: bool = True
    degraded: bool = False
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class StorageAdapter(ABC):
    """存储适配器基类。"""

    kind: str = ""
    engine: str = ""
    label: str = ""

    @abstractmethod
    def capability(self, db=None) -> AdapterCapability:
        """返回当前能力/健康状态（不得抛异常，异常需内部转成 available=False）。"""

    @abstractmethod
    def stats(self, db=None) -> dict:
        """返回存储规模等统计信息。"""

    # 通用容错入口：适配层不允许把底层异常直接抛给业务
    @staticmethod
    def safe(fn, default: Any = None, logger=None) -> Any:
        try:
            return fn()
        except Exception as exc:  # pragma: no cover
            if logger is not None:
                logger.warning("storage adapter fallback: %s", exc)
            return default


def summarize(kinds: list[str], rows: list[AdapterCapability]) -> dict:
    """汇总多个适配器状态。"""
    available = sum(1 for r in rows if r.available)
    degraded = sum(1 for r in rows if r.degraded)
    return {
        "kinds": kinds,
        "total": len(rows),
        "available": available,
        "degraded": degraded,
        "healthy": available == len(rows) and degraded == 0,
        "items": [r.to_dict() for r in rows],
    }
