"""存储适配层注册表与统一编排入口。

对外提供：
- capability/stats 汇总：供概览接口展示各存储引擎状态；
- bootstrap：启动时准备受管目录、内置路由规则、时序分区、存量数据回填；
- mirror_metric_values / backfill_metric_values：指标值镜像与回填（跨存储一致性基础）；
- cached(…)   ：热点数据 Redis 缓存读透 + 自动降级；
- search/reindex：全文检索读写入口。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from sqlalchemy import text

from app.core.config import settings
from app.models.storage import DATA_KINDS
from app.storage.cache import cache_adapter
from app.storage.files import file_adapter
from app.storage.routing import (
    ADAPTERS,
    ensure_default_rules,
    example_identifications,
    get_adapter,
    route_overview,
)
from app.storage.search import search_adapter
from app.storage.timeseries import timeseries_adapter

logger = logging.getLogger(__name__)


# ------------------------------------------------------------ 能力与统计
def adapter_capabilities(db=None) -> list[dict]:
    """所有适配器的能力/健康状态。"""
    return [get_adapter(kind).capability(db).to_dict() for kind in DATA_KINDS]


def storage_overview(db, tenant_id: Optional[int] = None) -> dict:
    """存储适配层总览：引擎状态 + 规模统计 + 路由规则 + 样例识别。"""
    capabilities = adapter_capabilities(db)
    stats = {}
    for kind in DATA_KINDS:
        try:
            stats[kind] = get_adapter(kind).stats(db)
        except Exception as exc:  # pragma: no cover
            stats[kind] = {"error": f"{type(exc).__name__}: {exc}"[:255]}
    healthy = all(item["available"] for item in capabilities)
    return {
        "healthy": healthy,
        "storage_routing_enabled": settings.STORAGE_ROUTING_ENABLED,
        "cache_enabled": settings.STORAGE_CACHE_ENABLED,
        "capabilities": capabilities,
        "stats": stats,
        "routing": route_overview(db, tenant_id),
        "examples": example_identifications(db, tenant_id),
    }


# ------------------------------------------------------------ 初始化
def backfill_metric_values(db, batch_size: Optional[int] = None) -> dict:
    """把存量关系型指标值（oc_metric_value）回填到时序分区表。

    幂等：默认只补时序表中缺失的 (metric_id, stat_time, granularity, dims_hash)，
    已存在的记录不覆盖，因此可安全地每次启动执行。
    返回 {"scanned": 扫描行数, "written": 实际写入行数, "skipped": 跳过行数, "batches": 批次数}。
    """
    stats = {"scanned": 0, "written": 0, "skipped": 0, "batches": 0}
    if not settings.STORAGE_BACKFILL_ENABLED or not settings.STORAGE_MIRROR_ENABLED:
        stats["disabled"] = True
        return stats

    size = batch_size or settings.STORAGE_BACKFILL_BATCH_SIZE
    base_sql = """
        SELECT v.tenant_id, v.metric_id, COALESCE(m.code, '') AS metric_code,
               v.stat_time, v.granularity, v.dims_hash, v.dims, v.value, m.source_id
        FROM oc_metric_value v
        LEFT JOIN oc_metric m ON m.id = v.metric_id
        WHERE NOT EXISTS (
            SELECT 1 FROM oc_ts_metric_point t
            WHERE t.metric_id = v.metric_id
              AND t.stat_time = v.stat_time
              AND t.granularity = v.granularity
              AND t.dims_hash = v.dims_hash
        )
        ORDER BY v.id
        LIMIT :limit
    """
    while True:
        try:
            rows = db.execute(text(base_sql), {"limit": size}).mappings().all()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            stats["error"] = f"{type(exc).__name__}: {exc}"[:255]
            return stats
        if not rows:
            break
        stats["batches"] += 1
        stats["scanned"] += len(rows)
        payload = [
            {
                "tenant_id": int(r["tenant_id"]),
                "metric_id": int(r["metric_id"]),
                "metric_code": r["metric_code"] or "",
                "stat_time": r["stat_time"],
                "granularity": r["granularity"],
                "dims_hash": r["dims_hash"] or "",
                "dims": r["dims"],
                "value": r["value"],
                "source_id": r["source_id"],
                "origin": "backfill",
            }
            for r in rows
        ]
        try:
            written = timeseries_adapter.write_points(db, payload)
        except Exception as exc:  # pragma: no cover
            logger.warning("存量指标值回填失败：%s", exc)
            db.rollback()
            stats["error"] = f"{type(exc).__name__}: {exc}"[:255]
            return stats
        stats["written"] += written
        stats["skipped"] += len(rows) - written
        if len(rows) < size:
            break
    return stats


def bootstrap_storage(db) -> dict:
    """启动/首次初始化：受管目录 + 内置路由规则 + 时序分区 + 存量数据回填。"""
    result: dict = {"created_dirs": [], "created_rules": 0, "created_partitions": []}
    try:
        result["created_dirs"] = file_adapter.ensure_dirs()
    except Exception as exc:  # pragma: no cover
        result["dirs_error"] = str(exc)[:255]
    try:
        result["created_rules"] = ensure_default_rules(db, tenant_id=None)
    except Exception as exc:  # pragma: no cover
        db.rollback()
        result["rules_error"] = str(exc)[:255]
    try:
        result["created_partitions"] = timeseries_adapter.ensure_partitions(db)
        result["realigned_partitions"] = dict(
            getattr(timeseries_adapter, "last_realigned", {}) or {}
        )
    except Exception as exc:  # pragma: no cover
        db.rollback()
        result["partitions_error"] = str(exc)[:255]
    try:
        result["backfill"] = backfill_metric_values(db)
    except Exception as exc:  # pragma: no cover
        db.rollback()
        result["backfill_error"] = str(exc)[:255]
    return result


# ------------------------------------------------------------ 时序镜像
def mirror_metric_values(db, rows: list, origin: str = "mirror") -> int:
    """把关系型指标值（oc_metric_value 行）镜像写入时序分区表。

    rows 元素需含：tenant_id/metric_id/metric_code/stat_time/granularity/dims/dims_hash/value/source_id。
    镜像失败不影响主流程（STORAGE_MIRROR_STRICT=True 时改为抛出）。
    """
    if not settings.STORAGE_MIRROR_ENABLED or not rows:
        return 0
    payload = [
        {
            "tenant_id": r.tenant_id,
            "metric_id": r.metric_id,
            "metric_code": getattr(r, "metric_code", "") or "",
            "stat_time": r.stat_time,
            "granularity": r.granularity,
            "dims_hash": r.dims_hash or "",
            "dims": r.dims,
            "value": r.value,
            "source_id": getattr(r, "source_id", None),
            "origin": origin,
        }
        for r in rows
    ]
    try:
        return timeseries_adapter.write_points(db, payload)
    except Exception as exc:
        logger.warning("指标值镜像写入时序表失败：%s", exc)
        db.rollback()
        if settings.STORAGE_MIRROR_STRICT:
            raise
        return 0


# ------------------------------------------------------------ 缓存读透
def cached(db, namespace: str, parts: tuple, loader: Callable[[], Any], ttl: Optional[int] = None):
    """热点数据缓存读透：命中返回 (value, True)，未命中回源并写缓存。"""
    key = cache_adapter.build_key(namespace, *parts)
    hit = cache_adapter.get_json(key)
    if hit is not None:
        return hit, True
    value = loader()
    if value is not None:
        cache_adapter.set_json(key, value, ttl)
    return value, False


def invalidate_tenant_cache(tenant_id: Optional[int] = None) -> int:
    """失效租户维度缓存（指标写入后调用）。"""
    prefix = cache_adapter.build_key("metric", tenant_id if tenant_id is not None else "")
    return cache_adapter.delete_prefix(prefix)


def cache_payload(tenant_id: int, granularity: str, codes: Optional[list[str]] = None) -> tuple:
    return (tenant_id, granularity, ",".join(sorted(codes)) if codes else "-")


# ------------------------------------------------------------ 全文检索
def search_documents(db, tenant_id: int, q: str, doc_type: Optional[str] = None, limit: Optional[int] = None) -> dict:
    """全文检索入口：返回命中列表与检索元信息。"""
    if not settings.STORAGE_SEARCH_ENABLED:
        return {"query": q, "total": 0, "items": [], "note": "全文检索已关闭（STORAGE_SEARCH_ENABLED=False）"}
    try:
        items = search_adapter.search(db, tenant_id, q, doc_type, limit or settings.STORAGE_SEARCH_LIMIT)
    except Exception as exc:
        db.rollback()
        logger.warning("全文检索失败：%s", exc)
        items = []
    caps = search_adapter.capabilities(db)
    return {
        "query": q,
        "doc_type": doc_type,
        "total": len(items),
        "items": items,
        "engine": "postgresql_gin",
        "pg_trgm": caps.get("pg_trgm", False),
        "note": None if caps.get("pg_trgm") else "pg_trgm 扩展不可用，已退化为 tsvector + ILIKE 匹配",
    }


def reindex_documents(db, tenant_id: Optional[int] = None, scope: Optional[list[str]] = None) -> dict:
    """重建全文检索索引（指标 / 数据源 / 分类）。"""
    return ADAPTERS["fulltext"].reindex(db, tenant_id=tenant_id, scope=scope)
