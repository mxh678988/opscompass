"""P2 存储适配层容器内验证脚本。

覆盖：
1) 建表 / 分区表 / 全文索引结构
2) 路由识别（数据源类型 -> 存储引擎）
3) 读写：关系型写入 -> 时序分区镜像 + Redis 缓存读写与失效 + 缓存降级
4) 全文检索索引重建与检索
5) 跨存储一致性对账（含人为制造漂移 + 自动修复）

用法（容器内）：python scripts/verify_p2_storage.py
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.core.config import settings
from app.models.base import SessionLocal
from app.schemas.metric import MetricCreate, MetricValueIn
from app.services import metric_service
from app.storage import cache as cache_adapter
from app.storage import consistency as consistency_adapter
from app.storage import routing as routing_adapter
from app.storage import search as search_adapter
from app.storage import timeseries as ts_adapter
from app.storage.registry import (
    backfill_metric_values,
    bootstrap_storage,
    reindex_documents,
    search_documents,
    storage_overview,
)

logging.disable(logging.WARNING)

REPORT: dict = {}
TS_TABLE = "oc_ts_metric_point"


def _default_tenant_id(db) -> int:
    row = db.execute(text("SELECT id FROM oc_tenant WHERE code = 'default' LIMIT 1")).first()
    if row is None:
        row = db.execute(text("SELECT id FROM oc_tenant ORDER BY id LIMIT 1")).first()
    return int(row[0])


def step_structure(db) -> None:
    """1) 建表与分区、索引结构。"""
    tables = {}
    for name in (
        "oc_storage_route_rule",
        "oc_doc_index",
        TS_TABLE,
        "oc_storage_consistency_check",
    ):
        row = db.execute(
            text(
                "SELECT c.relkind::text FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname = :n AND n.nspname = 'public'"
            ),
            {"n": name},
        ).first()
        tables[name] = {"exists": row is not None, "relkind": row[0] if row else None}

    partitions = [
        r[0]
        for r in db.execute(
            text(
                "SELECT c.relname FROM pg_inherits i "
                "JOIN pg_class c ON c.oid = i.inhrelid "
                "JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = :t ORDER BY c.relname"
            ),
            {"t": TS_TABLE},
        ).fetchall()
    ]

    indexes = [
        r[0]
        for r in db.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename IN "
                "('oc_doc_index', :t) ORDER BY indexname"
            ),
            {"t": TS_TABLE},
        ).fetchall()
    ]

    fts_rows = db.execute(
        text("SELECT count(*), count(tsv) FROM oc_doc_index")
    ).first()

    REPORT["1_structure"] = {
        "tables": tables,
        "ts_partitioned": tables[TS_TABLE]["relkind"] == "p",
        "ts_partitions": partitions,
        "indexes": indexes,
        "doc_index_rows": int(fts_rows[0] or 0),
        "doc_index_tsv_filled": int(fts_rows[1] or 0),
    }


def step_bootstrap(db) -> None:
    """2) 幂等初始化：目录 / 内置规则 / 月分区。"""
    result = bootstrap_storage(db)
    REPORT["2_bootstrap"] = {
        "created_dirs": result.get("created_dirs"),
        "created_rules": result.get("created_rules"),
        "created_partitions": result.get("created_partitions"),
        "realigned_partitions": result.get("realigned_partitions"),
        "dirs_error": result.get("dirs_error"),
        "partitions_error": result.get("partitions_error"),
        "partition_tz_offset_hours": settings.STORAGE_TS_PARTITION_UTC_OFFSET_HOURS,
    }
    caps = storage_overview(db)["capabilities"]
    REPORT["2_bootstrap"]["engines"] = [
        {"kind": c["kind"], "engine": c["engine"], "available": c["available"]} for c in caps
    ]


def step_routing(db, tenant_id: int) -> None:
    """3) 数据源类型识别与引擎路由。"""
    REPORT["3_routing"] = {
        "rules_total": routing_adapter.route_overview(db, tenant_id=tenant_id)["rule_count"],
        "samples": routing_adapter.example_identifications(db, tenant_id=tenant_id),
    }


def step_backfill(db, tenant_id: int) -> None:
    """3.5) 存量指标值回填时序表（幂等）。

    先绕过服务层直接往关系型表写一条"历史数据"（模拟 P2 上线前的存量），
    再执行回填，验证存量数据能被补齐进时序分区表。
    """
    metric_id = db.execute(text("SELECT id FROM oc_metric ORDER BY id LIMIT 1")).scalar()
    legacy_time = "2026-07-01 00:00:00+00"
    db.execute(
        text("DELETE FROM oc_metric_value WHERE dims_hash = 'verifylegacy'")
    )
    db.execute(
        text("DELETE FROM " + TS_TABLE + " WHERE dims_hash = 'verifylegacy'")
    )
    db.commit()
    if metric_id is not None:
        db.execute(
            text(
                "INSERT INTO oc_metric_value (tenant_id, metric_id, stat_time, granularity, dims, dims_hash, value) "
                "VALUES (:t, :m, CAST(:s AS timestamptz), 'day', CAST(:d AS json), 'verifylegacy', 888.88) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": tenant_id, "m": int(metric_id), "s": legacy_time, "d": '{"channel": "legacy"}'},
        )
        db.commit()

    first = backfill_metric_values(db)
    mirrored = db.execute(
        text("SELECT count(*) FROM " + TS_TABLE + " WHERE dims_hash = 'verifylegacy'")
    ).scalar()
    second = backfill_metric_values(db)
    REPORT["3_5_backfill"] = {
        "legacy_row_inserted": metric_id is not None,
        "first_run": first,
        "legacy_mirrored_rows": int(mirrored or 0),
        "second_run_idempotent": second,
    }


def step_boundary(db, tenant_id: int) -> None:
    """3.6) 分区边界口径校验 + 跨月边界窗口写入（此前为空洞区间）。"""
    ranges = ts_adapter.timeseries_adapter.partition_ranges(db)
    offset_hours = settings.STORAGE_TS_PARTITION_UTC_OFFSET_HOURS
    tz = timezone(timedelta(hours=offset_hours))
    layout = []
    for name, (low, high) in sorted(ranges.items()):
        l = low.astimezone(tz) if low else None
        h = high.astimezone(tz) if high else None
        layout.append(
            {
                "name": name,
                "low": l.strftime("%Y-%m-%d %H:%M %z") if l else None,
                "high": h.strftime("%Y-%m-%d %H:%M %z") if h else None,
                "aligned": bool(l and h and l.day == 1 and l.hour == 0 and h.day == 1 and h.hour == 0),
            }
        )
    gaps = []
    ordered = sorted([(v[0], v[1], k) for k, v in ranges.items() if v[0] and v[1]])
    for i in range(1, len(ordered)):
        prev_high = ordered[i - 1][1]
        cur_low = ordered[i][0]
        if prev_high != cur_low:
            gaps.append(
                {
                    "between": [ordered[i - 1][2], ordered[i][2]],
                    "prev_high": str(prev_high),
                    "cur_low": str(cur_low),
                }
            )

    # 边界窗口写入：2026-12-01 00:30(+08) 曾落在无分区空洞
    code = "p2_verify_gmv"
    boundary_ts = datetime(2026, 12, 1, 0, 30, tzinfo=tz)
    inserted = 0
    metric = metric_service.get_metric(db, tenant_id, code)
    if metric is not None:
        inserted = metric_service.upsert_values(
            db,
            metric,
            [
                MetricValueIn(
                    stat_time=boundary_ts,
                    granularity="day",
                    dims={"channel": "boundary"},
                    value=321.0,
                )
            ],
        )
    ts_found = db.execute(
        text(
            "SELECT tableoid::regclass::text FROM " + TS_TABLE +
            " WHERE metric_code = :c AND stat_time = :s AND dims_hash = :h"
        ),
        {"c": code, "s": boundary_ts, "h": metric_service.dims_hash({"channel": "boundary"})},
    ).scalar()

    REPORT["3_6_boundary"] = {
        "partition_tz_offset_hours": offset_hours,
        "partitions": layout,
        "all_aligned": all(p["aligned"] for p in layout),
        "gaps_or_overlaps": gaps,
        "boundary_write_ts": boundary_ts.isoformat(),
        "boundary_rows_affected": int(inserted or 0),
        "boundary_landed_partition": ts_found,
    }


def _safe_drop_partition(db, name: str) -> None:
    """安全移除一个（空）测试分区：先摘除再删除，不存在则跳过。"""
    if db.execute(text("SELECT to_regclass(:n)"), {"n": name}).scalar() is None:
        return
    try:
        db.execute(text(f"ALTER TABLE {TS_TABLE} DETACH PARTITION {name}"))
    except Exception:
        db.rollback()
    db.execute(text(f"DROP TABLE IF EXISTS {name}"))
    db.commit()


def step_realign_proof(db) -> None:
    """3.7) 回归用例：模拟「历史迁移遗留的口径不一致分区」，验证自动安全校正。

    仅针对本步骤自行创建的 2099 年空分区（无任何业务数据），不触碰真实分区。
    """
    name = "oc_ts_metric_point_p209901"
    adapter = ts_adapter.timeseries_adapter
    proof: dict = {}
    try:
        _safe_drop_partition(db, name)
        # 故意用「东八区 08:00」这种错误口径建分区，模拟迁移脚本历史遗留
        db.execute(
            text(
                f"CREATE TABLE {name} PARTITION OF {TS_TABLE} "
                f"FOR VALUES FROM ('2099-01-01 08:00+08') TO ('2099-02-01 08:00+08')"
            )
        )
        db.commit()
        before = adapter.partition_ranges(db).get(name)
        anchor = datetime(2099, 1, 15, tzinfo=timezone(timedelta(hours=8)))
        created = adapter.ensure_partitions(db, extra_times=[anchor])
        after = adapter.partition_ranges(db).get(name)
        proof = {
            "simulated_partition": name,
            "before_low_utc": str(before[0]) if before else None,
            "realign_status": dict(getattr(adapter, "last_realigned", {}) or {}).get(name),
            "created_in_run": created,
            "after_low_utc": str(after[0]) if after else None,
            "after_aligned_to_business_month": bool(
                after
                and after[0].astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
                == "2099-01-01 00:00"
            ),
        }
    except Exception as exc:  # pragma: no cover
        db.rollback()
        proof = {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        # 清理回归用例产生的空分区，避免污染实际分区布局
        try:
            _safe_drop_partition(db, name)
        except Exception:
            db.rollback()
    REPORT["3_7_realign_proof"] = proof


def step_readwrite(db, tenant_id: int) -> None:
    """4) 关系型写入 -> 时序镜像 + 缓存读写/失效/降级。"""
    code = "p2_verify_gmv"
    db.execute(text("DELETE FROM oc_metric_value WHERE metric_id IN (SELECT id FROM oc_metric WHERE code = :c)"), {"c": code})
    db.execute(text("DELETE FROM oc_metric WHERE code = :c"), {"c": code})
    db.execute(text(f"DELETE FROM {TS_TABLE} WHERE metric_code = :c"), {"c": code})
    db.commit()

    metric = metric_service.create_metric(
        db,
        tenant_id,
        MetricCreate(code=code, name="P2验证-GMV", unit="元", status="online"),
    )

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    items = []
    for offset, value in ((0, 1000.0), (1, 1200.5)):
        items.append(
            MetricValueIn(
                stat_time=now - timedelta(days=offset),
                granularity="day",
                dims={"channel": "app"},
                value=value,
            )
        )
    # 跨月写入，验证分区路由
    items.append(
        MetricValueIn(
            stat_time=(now.replace(day=1) + timedelta(days=40)).replace(day=1),
            granularity="day",
            dims={"channel": "web"},
            value=2400.0,
        )
    )

    affected = metric_service.upsert_values(db, metric, items)
    db.commit()

    rel_rows = db.execute(
        text("SELECT count(*) FROM oc_metric_value WHERE metric_id = :m"), {"m": metric.id}
    ).scalar()
    ts_rows = db.execute(
        text(f"SELECT count(*) FROM {TS_TABLE} WHERE metric_code = :c"), {"c": code}
    ).scalar()
    ts_partitions = [
        r[0]
        for r in db.execute(
            text(
                "SELECT DISTINCT tableoid::regclass::text FROM " + TS_TABLE + " WHERE metric_code = :c"
            ),
            {"c": code},
        ).fetchall()
    ]
    agg = ts_adapter.timeseries_adapter.aggregate(db, tenant_id, code, bucket="month", agg="sum")
    points = ts_adapter.timeseries_adapter.query_points(db, tenant_id, metric_code=code, limit=10)

    # 缓存：写后应已失效，重新读取后命中
    key = cache_adapter.cache_adapter.build_key("overview", tenant_id, "day", "")
    cache_adapter.cache_adapter.delete_prefix(cache_adapter.cache_adapter.build_key("overview", tenant_id))
    stats_before = cache_adapter.cache_adapter.stats(db).get("runtime", {})
    first = metric_service.overview(db, tenant_id, granularity="day")
    stats_mid = cache_adapter.cache_adapter.stats(db).get("runtime", {})
    hit_after_first = cache_adapter.cache_adapter.get_json(key) is not None
    second = metric_service.overview(db, tenant_id, granularity="day")
    stats_after = cache_adapter.cache_adapter.stats(db).get("runtime", {})

    # 缓存降级：关闭缓存后仍可正常返回
    original = settings.STORAGE_CACHE_ENABLED
    settings.STORAGE_CACHE_ENABLED = False
    try:
        degraded = metric_service.overview(db, tenant_id, granularity="day")
        degraded_ok = degraded is not None
        _cap = cache_adapter.cache_adapter.capability(db)
        degraded_cap = {
            "available": getattr(_cap, "available", None),
            "engine": getattr(_cap, "engine", None),
            "detail": getattr(_cap, "detail", None),
        }
        degraded_stats = cache_adapter.cache_adapter.stats(db)
    finally:
        settings.STORAGE_CACHE_ENABLED = original

    REPORT["4_readwrite"] = {
        "metric_id": metric.id,
        "relation_rows": int(rel_rows or 0),
        "ts_mirror_rows": int(ts_rows or 0),
        "ts_affected_partitions": ts_partitions,
        "ts_monthly_aggregate": agg,
        "ts_query_points": len(points),
        "cache_key": key,
        "cache_key_written": hit_after_first,
        "cache_stats_first_read": stats_mid,
        "cache_stats_second_read": stats_after,
        "cache_hit_gain": int((stats_after.get("hits", 0) or 0) - (stats_mid.get("hits", 0) or 0)),
        "cache_miss_gain_first": int((stats_mid.get("misses", 0) or 0) - (stats_before.get("misses", 0) or 0)),
        "overview_first_items": len(first.items),
        "overview_second_items": len(second.items),
        "cache_degraded_ok": bool(degraded_ok),
        "cache_capability_when_disabled": degraded_cap,
        "cache_stats_when_disabled": degraded_stats,
    }


def step_search(db, tenant_id: int) -> None:
    """5) 全文检索索引与检索。"""
    result = reindex_documents(db, tenant_id=tenant_id)
    hits = search_documents(db, tenant_id=tenant_id, q="P2验证", limit=5)
    generic = search_documents(db, tenant_id=tenant_id, q="指标", limit=5)
    tsv = db.execute(
        text("SELECT count(*) FROM oc_doc_index WHERE tenant_id = :t AND tsv IS NOT NULL"),
        {"t": tenant_id},
    ).scalar()
    REPORT["5_search"] = {
        "reindex": result,
        "query_P2验证": {"total": hits.get("total"), "top": (hits.get("items") or [{}])[0].get("title") if hits.get("items") else None},
        "query_指标": {"total": generic.get("total")},
        "tsv_filled": int(tsv or 0),
        "adapter": search_adapter.search_adapter.capabilities(db),
    }


def step_consistency(db, tenant_id: int) -> None:
    """6) 一致性对账：正常 -> 人为漂移 -> 自动修复。"""
    clean = consistency_adapter.run_checks(db, tenant_id, auto_repair=False, operator="verify")
    db.commit()

    # 人为制造漂移：删除一条时序镜像
    drift_id = db.execute(
        text(
            "SELECT metric_id, stat_time, granularity, dims_hash FROM " + TS_TABLE +
            " WHERE tenant_id = :t ORDER BY stat_time LIMIT 1"
        ),
        {"t": tenant_id},
    ).first()
    if drift_id:
        db.execute(
            text(
                "DELETE FROM " + TS_TABLE +
                " WHERE tenant_id = :t AND metric_id = :m AND stat_time = :s AND granularity = :g AND dims_hash = :d"
            ),
            {"t": tenant_id, "m": drift_id[0], "s": drift_id[1], "g": drift_id[2], "d": drift_id[3]},
        )
        db.commit()

    drifted = consistency_adapter.run_checks(db, tenant_id, scopes=["metric_ts"], operator="verify")
    db.commit()
    repaired = consistency_adapter.run_checks(
        db, tenant_id, scopes=["metric_ts"], auto_repair=True, operator="verify"
    )
    db.commit()
    after = consistency_adapter.run_checks(db, tenant_id, scopes=["metric_ts"], operator="verify")
    db.commit()

    # 人为制造索引漂移：写入一条指向不存在指标的脏索引条目，验证自动清理
    db.execute(
        text(
            "INSERT INTO oc_doc_index (tenant_id, doc_type, doc_id, title, content, keywords, indexed_at)"
            " VALUES (:t, 'metric', '999999', '脏索引条目', 'verify drift', 'drift', now())"
        ),
        {"t": tenant_id},
    )
    db.commit()
    index_drift = consistency_adapter.reconcile_search_index(db, tenant_id, auto_repair=False)
    db.rollback()
    index_fixed = consistency_adapter.reconcile_search_index(db, tenant_id, auto_repair=True)
    db.commit()
    index_after = consistency_adapter.reconcile_search_index(db, tenant_id, auto_repair=False)
    db.rollback()
    remaining_dirty = db.execute(
        text(
            "SELECT count(*) FROM oc_doc_index WHERE tenant_id = :t AND doc_type = 'metric' AND doc_id = '999999'"
        ),
        {"t": tenant_id},
    ).scalar()

    REPORT["6_consistency"] = {
        "initial_scopes": [
            {"scope": r["scope"], "status": r["status"], "checked": r["checked"], "mismatched": r["mismatched"]}
            for r in clean.get("results", [])
        ],
        "drift_scope": {k: drifted.get(k) for k in ("scope", "status", "checked", "matched", "missing", "mismatched")} if "scope" in drifted else drifted.get("results"),
        "repair": {k: repaired.get(k) for k in ("scope", "status", "repaired", "missing")} if "scope" in repaired else repaired.get("results"),
        "after_repair": {k: after.get(k) for k in ("scope", "status", "checked", "matched", "missing")} if "scope" in after else after.get("results"),
        "index_drift": {
            "before": {k: index_drift.get(k) for k in ("status", "checked", "missing", "extra")},
            "auto_repair": {k: index_fixed.get(k) for k in ("status", "repaired", "pruned", "missing", "extra")},
            "after": {k: index_after.get(k) for k in ("status", "missing", "extra")},
            "dirty_rows_remaining": int(remaining_dirty or 0),
        },
        "recent_records": len(consistency_adapter.recent_checks(db, tenant_id, limit=10)),
    }


def main() -> None:
    db = SessionLocal()
    try:
        tenant_id = _default_tenant_id(db)
        REPORT["tenant_id"] = tenant_id
        step_structure(db)
        step_bootstrap(db)
        step_routing(db, tenant_id)
        step_backfill(db, tenant_id)
        step_readwrite(db, tenant_id)
        step_boundary(db, tenant_id)
        step_realign_proof(db)
        step_search(db, tenant_id)
        step_consistency(db, tenant_id)
    finally:
        db.close()
    print(json.dumps(REPORT, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
