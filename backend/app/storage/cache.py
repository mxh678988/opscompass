"""缓存存储适配器：热点数据走 Redis，Redis 不可用时自动降级。

降级策略（熔断 + 自动恢复）：
1. 每次操作异常累加连续失败计数，达到阈值（STORAGE_CACHE_FAILURE_THRESHOLD）即进入降级窗口；
2. 降级窗口内所有读写直接 bypass 并返回 miss / False，业务自动回落到数据库直查；
3. 窗口到期后自动尝试一次探活，成功则恢复正常，失败则继续降级。

这样保证「缓存不可用不影响业务可用性」。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.core.config import settings
from app.storage.base import AdapterCapability

logger = logging.getLogger(__name__)


class CacheAdapter:
    """Redis 缓存适配器（含自动降级）。"""

    kind = "cache"
    engine = "redis"
    label = "Redis 热点缓存"

    def __init__(self) -> None:
        self._client = None
        self._consecutive_failures = 0
        self._degraded_until = 0.0
        self._last_error = ""
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0
        self._bypassed = 0
        self._degraded_events = 0
        self._recoveries = 0

    # ------------------------------------------------------------ 内部
    @property
    def enabled(self) -> bool:
        return bool(settings.STORAGE_CACHE_ENABLED)

    @property
    def degraded(self) -> bool:
        """当前是否处于降级窗口内。"""
        return time.monotonic() < self._degraded_until

    @property
    def prefix(self) -> str:
        return settings.STORAGE_CACHE_PREFIX or "oc:cache"

    def _mark_failure(self, exc: Exception) -> None:
        self._last_error = f"{type(exc).__name__}: {exc}"[:255]
        self._consecutive_failures += 1
        self._client = None
        threshold = max(1, settings.STORAGE_CACHE_FAILURE_THRESHOLD)
        if self._consecutive_failures >= threshold and not self.degraded:
            self._degraded_until = time.monotonic() + max(1, settings.STORAGE_CACHE_RECOVER_SECONDS)
            self._degraded_events += 1
            logger.warning("Redis 缓存进入降级窗口: %s", self._last_error)

    def _mark_success(self) -> None:
        if self._degraded_until:
            self._recoveries += 1
        self._degraded_until = 0.0
        self._consecutive_failures = 0

    def _should_bypass(self) -> bool:
        """是否需要跳过缓存：未启用 / 处于降级窗口 / 缺少 redis 依赖。"""
        if not self.enabled:
            self._bypassed += 1
            return True
        if self.degraded:
            # 窗口到期由 degraded 属性自动放行，这里只处理窗口内
            self._bypassed += 1
            return True
        return False

    def _connect(self):
        if self._client is not None:
            return self._client
        import redis  # 延迟导入：依赖缺失时直接降级，不影响服务启动

        self._client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return self._client

    # ------------------------------------------------------------ 健康
    def ping(self) -> bool:
        """探活：成功返回 True，失败触发降级计数。"""
        if not self.enabled:
            return False
        try:
            ok = bool(self._connect().ping())
            self._mark_success()
            return ok
        except Exception as exc:
            self._mark_failure(exc)
            return False

    def capability(self, db=None) -> AdapterCapability:
        ok = self.enabled and (not self.degraded) and self.ping()
        return AdapterCapability(
            kind=self.kind,
            engine=self.engine,
            label=self.label,
            available=ok,
            degraded=self.degraded,
            detail={
                "enabled": self.enabled,
                "url": f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                "degraded": self.degraded,
                "consecutive_failures": self._consecutive_failures,
                "degraded_events": self._degraded_events,
                "recoveries": self._recoveries,
                "last_error": self._last_error,
                "fallback": "缓存不可用时自动直连数据库（不影响业务可用性）",
            },
        )

    def stats(self, db=None) -> dict:
        info: dict = {}
        if self.enabled and not self.degraded:
            try:
                client = self._connect()
                info = {
                    "used_memory_human": client.info("memory").get("used_memory_human"),
                    "connected_clients": client.info("clients").get("connected_clients"),
                    "keys": client.dbsize(),
                }
                self._mark_success()
            except Exception as exc:
                self._mark_failure(exc)
        return {
            "kind": self.kind,
            "engine": self.engine,
            "enabled": self.enabled,
            "degraded": self.degraded,
            "prefix": self.prefix,
            "runtime": {
                "hits": self._hits,
                "misses": self._misses,
                "sets": self._sets,
                "deletes": self._deletes,
                "bypassed": self._bypassed,
                "degraded_events": self._degraded_events,
                "recoveries": self._recoveries,
                "last_error": self._last_error,
            },
            "redis": info,
        }

    # ------------------------------------------------------------ 键
    def build_key(self, namespace: str, *parts: Any) -> str:
        """构造缓存键：前缀:命名空间:片段。"""
        tail = ":".join("" if p is None else str(p) for p in parts)
        return f"{self.prefix}:{namespace}" + (f":{tail}" if tail else "")

    # ------------------------------------------------------------ 读写
    def get_json(self, key: str) -> Optional[Any]:
        """读缓存；未命中 / 降级 / 异常统一返回 None。"""
        if self._should_bypass():
            return None
        try:
            raw = self._connect().get(key)
            self._mark_success()
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as exc:
            self._mark_failure(exc)
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """写缓存；失败静默返回 False（不阻断业务）。"""
        if self._should_bypass():
            return False
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
            self._connect().set(key, payload, ex=int(ttl or settings.STORAGE_CACHE_TTL_SECONDS))
            self._mark_success()
            self._sets += 1
            return True
        except Exception as exc:
            self._mark_failure(exc)
            return False

    def delete(self, *keys: str) -> int:
        """删除指定键，返回删除数量；失败返回 0。"""
        if not keys or self._should_bypass():
            return 0
        try:
            removed = int(self._connect().delete(*keys))
            self._mark_success()
            self._deletes += removed
            return removed
        except Exception as exc:
            self._mark_failure(exc)
            return 0

    def delete_prefix(self, prefix: str) -> int:
        """按前缀批量失效（用于租户维度整体失效）。"""
        if self._should_bypass():
            return 0
        try:
            client = self._connect()
            removed = 0
            for key in client.scan_iter(match=f"{prefix}*", count=200):
                removed += int(client.delete(key))
            self._mark_success()
            self._deletes += removed
            return removed
        except Exception as exc:
            self._mark_failure(exc)
            return 0


# 全局单例（进程内共享熔断状态）
cache_adapter = CacheAdapter()
