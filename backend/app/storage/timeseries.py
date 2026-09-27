"""时序指标适配器：PostgreSQL 分区表 + 时间索引。

落地方式（不引入新镜像 / 新依赖）：
- oc_ts_metric_point 按 stat_time 做 RANGE 分区（月分区），分区边界统一使用
  业务时区（默认东八区，见 STORAGE_TS_PARTITION_UTC_OFFSET_HOURS），
  边界 DDL 必须带显式时区偏移，避免与 PostgreSQL 会话时区口径不一致导致分区重叠；
- 写入前自动补建缺失分区（当前月前后按配置冗余创建），避免插入落到无分区报错；
  对历史遗留的边界口径不一致分区做安全校正（仅空分区摘除重建）；
- 提供时间区间查询与按时间桶聚合（date_trunc）能力。

与关系型表 oc_metric_value 的关系：由镜像写入保证最终一致，由一致性对账校验。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import text

from app.core.config import settings
from app.storage.base import AdapterCapability

logger = logging.getLogger(__name__)

TS_TABLE = "oc_ts_metric_point"
PARTITION_PREFIX = "oc_ts_metric_point_p"

AGG_FUNCS = {"sum": "SUM", "avg": "AVG", "max": "MAX", "min": "MIN", "count": "COUNT"}
BUCKETS = {"hour": "hour", "day": "day", "week": "week", "month": "month"}


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}{dt.month:02d}"


def _partition_tz() -> timezone:
    """分区边界时区：默认东八区（业务月按本地时间切分）。"""
    offset = int(getattr(settings, "STORAGE_TS_PARTITION_UTC_OFFSET_HOURS", 8) or 0)
    return timezone(timedelta(hours=offset))


def _month_bounds(dt: datetime) -> tuple[str, str]:
    """返回该月分区的下界/上界（带显式时区偏移的 ISO 字符串）。

    注意：下界/上界必须带时区偏移，否则 PostgreSQL 会按会话时区解析，
    与运行时代码口径不一致会导致分区互相重叠（无法再建相邻月份分区）。
    """
    tz = _partition_tz()
    start = datetime(dt.year, dt.month, 1, tzinfo=tz)
    end = datetime(dt.year + (dt.month // 12), (dt.month % 12) + 1, 1, tzinfo=tz)
    return start.isoformat(), end.isoformat()


def _month_shift(base: datetime, months: int) -> datetime:
    total = base.year * 12 + (base.month - 1) + months
    return datetime(total // 12, total % 12 + 1, 1, tzinfo=_partition_tz())


def _month_start(dt: datetime) -> datetime:
    """归一到分区时区下的当月 1 日 00:00。"""
    local = _ensure_aware(dt).astimezone(_partition_tz())
    return datetime(local.year, local.month, 1, tzinfo=_partition_tz())


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TimeSeriesAdapter:
    """时序指标适配器（分区表）。"""

    kind = "timeseries"
    engine = "postgresql_partitioned"
    label = "时序分区表存储"

    # ------------------------------------------------------------ 分区管理
    def existing_partitions(self, db) -> list[str]:
        try:
            rows = db.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "JOIN pg_inherits i ON i.inhrelid = c.oid "
                    "JOIN pg_class p ON p.oid = i.inhparent "
                    "WHERE p.relname = :parent ORDER BY c.relname"
                ),
                {"parent": TS_TABLE},
            ).all()
            return [r[0] for r in rows]
        except Exception as exc:
            logger.warning("list partitions failed: %s", exc)
            return []

    def is_partitioned(self, db) -> bool:
        try:
            return bool(
                db.execute(
                    text("SELECT relkind = 'p' FROM pg_class WHERE relname = :n"),
                    {"n": TS_TABLE},
                ).scalar()
            )
        except Exception:
            return False

    def partition_ranges(self, db) -> dict[str, tuple[Optional[datetime], Optional[datetime]]]:
        """返回 {分区名: (下界, 上界)}，边界统一换算为 UTC 时间戳。

        借助 PostgreSQL 自身解析分区边界，规避字符串口径差异（+00 / +08）。
        """
        try:
            rows = db.execute(
                text(
                    "SELECT c.relname,"
                    " substring(pg_get_expr(c.relpartbound, c.oid) from 'FROM \\(''([^'']+)''\\)')::timestamptz AS low,"
                    " substring(pg_get_expr(c.relpartbound, c.oid) from 'TO \\(''([^'']+)''\\)')::timestamptz AS high"
                    " FROM pg_class c"
                    " JOIN pg_inherits i ON i.inhrelid = c.oid"
                    " JOIN pg_class p ON p.oid = i.inhparent"
                    " WHERE p.relname = :parent ORDER BY c.relname"
                ),
                {"parent": TS_TABLE},
            ).all()
            return {r[0]: (r[1], r[2]) for r in rows}
        except Exception as exc:
            logger.warning("read partition ranges failed: %s", exc)
            return {}

    def _realign_partition(self, db, name: str) -> str:
        """校正边界口径不一致的分区。

        仅当该分区为空时执行「摘除 + 重建」，避免任何数据丢失；
        非空分区保持原样并返回 skipped，由上层告警。
        """
        try:
            rows = int(db.execute(text(f"SELECT count(*) FROM ONLY {name}")).scalar() or 0)
        except Exception as exc:
            return f"skipped(count failed: {type(exc).__name__})"
        if rows:
            return "skipped(not empty)"
        try:
            db.execute(text(f"ALTER TABLE {TS_TABLE} DETACH PARTITION {name}"))
            db.execute(text(f"DROP TABLE IF EXISTS {name}"))
            db.commit()
            return "recreated"
        except Exception as exc:
            db.rollback()
            logger.warning("realign partition %s failed: %s", name, exc)
            return f"failed({type(exc).__name__})"

    def ensure_partitions(
        self,
        db,
        anchor: Optional[datetime] = None,
        behind_months: Optional[int] = None,
        ahead_months: Optional[int] = None,
        extra_times: Optional[Iterable[datetime]] = None,
    ) -> list[str]:
        """按需补建月分区，返回本次新建的分区名。

        对已存在但边界口径不一致的分区（历史迁移遗留）做安全校正：
        空分区摘除重建，非空分区保留并跳过，避免分区重叠报错。
        """
        if not self.is_partitioned(db):
            self.last_realigned = {}
            return []
        base = _month_start(anchor or datetime.now(timezone.utc))
        offsets = set(range(-(behind_months if behind_months is not None else settings.STORAGE_TS_PARTITION_BEHIND_MONTHS),
                           (ahead_months if ahead_months is not None else settings.STORAGE_TS_PARTITION_AHEAD_MONTHS) + 1))
        if extra_times:
            for dt in extra_times:
                extra = _month_start(dt)
                offsets.add((extra.year - base.year) * 12 + (extra.month - base.month))
        created: list[str] = []
        realigned: dict[str, str] = {}
        self.last_realigned = realigned
        existing = set(self.existing_partitions(db))
        ranges = self.partition_ranges(db)
        for offset in sorted(offsets):
            month = _month_shift(base, offset)
            name = f"{PARTITION_PREFIX}{_month_key(month)}"
            low, high = _month_bounds(month)
            if name in existing:
                low_dt = datetime.fromisoformat(low).astimezone(timezone.utc)
                high_dt = datetime.fromisoformat(high).astimezone(timezone.utc)
                actual = ranges.get(name)
                aligned = actual is not None and actual[0] is not None and (
                    _ensure_aware(actual[0]).astimezone(timezone.utc) == low_dt
                    and _ensure_aware(actual[1]).astimezone(timezone.utc) == high_dt
                )
                if actual is None or aligned:
                    continue
                # 边界口径不一致（历史迁移遗留）-> 仅空分区可安全校正
                status = self._realign_partition(db, name)
                realigned[name] = status
                if status != "recreated":
                    continue
            try:
                db.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {TS_TABLE} "
                        f"FOR VALUES FROM ('{low}') TO ('{high}')"
                    )
                )
            except Exception as exc:
                db.rollback()
                logger.warning("create partition %s failed: %s", name, exc)
                realigned[name] = f"failed({type(exc).__name__})"
                continue
            created.append(name)
        if created:
            db.commit()
        if realigned:
            self.last_realigned = realigned
        return created

    # ------------------------------------------------------------ 写入
    def write_points(self, db, rows: list[dict], auto_partition: bool = True) -> int:
        """批量写入时序点（按主键覆盖）。"""
        if not rows:
            return 0
        if auto_partition and settings.STORAGE_TS_AUTO_PARTITION:
            self.ensure_partitions(db, extra_times=[_ensure_aware(r["stat_time"]) for r in rows])
        sql = text(
            f"""
            INSERT INTO {TS_TABLE}
                (tenant_id, metric_id, metric_code, stat_time, granularity,
                 dims_hash, dims, value, source_id, origin)
            VALUES
                (:tenant_id, :metric_id, :metric_code, :stat_time, :granularity,
                 :dims_hash, CAST(:dims AS JSONB), :value, :source_id, :origin)
            ON CONFLICT (tenant_id, metric_id, stat_time, granularity, dims_hash)
            DO UPDATE SET
                metric_code = EXCLUDED.metric_code,
                dims = EXCLUDED.dims,
                value = EXCLUDED.value,
                source_id = EXCLUDED.source_id,
                origin = EXCLUDED.origin
            """
        )
        payload = []
        for row in rows:
            payload.append(
                {
                    "tenant_id": row["tenant_id"],
                    "metric_id": row["metric_id"],
                    "metric_code": row.get("metric_code") or "",
                    "stat_time": row["stat_time"],
                    "granularity": row.get("granularity") or "day",
                    "dims_hash": row.get("dims_hash") or "",
                    "dims": None
                    if row.get("dims") is None
                    else __import__("json").dumps(row["dims"], ensure_ascii=False),
                    "value": row.get("value") or 0,
                    "source_id": row.get("source_id"),
                    "origin": row.get("origin") or "mirror",
                }
            )
        db.execute(sql, payload)
        db.commit()
        return len(payload)

    # ------------------------------------------------------------ 查询
    def query_points(
        self,
        db,
        tenant_id: int,
        metric_code: Optional[str] = None,
        metric_id: Optional[int] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        granularity: Optional[str] = None,
        dims_hash: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        conditions = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": int(limit)}
        if metric_code:
            conditions.append("metric_code = :metric_code")
            params["metric_code"] = metric_code
        if metric_id is not None:
            conditions.append("metric_id = :metric_id")
            params["metric_id"] = metric_id
        if start is not None:
            conditions.append("stat_time >= :start")
            params["start"] = start
        if end is not None:
            conditions.append("stat_time <= :end")
            params["end"] = end
        if granularity:
            conditions.append("granularity = :granularity")
            params["granularity"] = granularity
        if dims_hash:
            conditions.append("dims_hash = :dims_hash")
            params["dims_hash"] = dims_hash
        sql = text(
            f"SELECT tenant_id, metric_id, metric_code, stat_time, granularity, dims_hash,"
            f" dims, value, origin FROM {TS_TABLE} WHERE {' AND '.join(conditions)}"
            f" ORDER BY stat_time DESC LIMIT :limit"
        )
        return [dict(r._mapping) for r in db.execute(sql, params).all()]

    def aggregate(
        self,
        db,
        tenant_id: int,
        metric_code: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        bucket: str = "day",
        agg: str = "sum",
        granularity: Optional[str] = None,
    ) -> list[dict]:
        """按时间桶聚合。bucket: hour/day/week/month；agg: sum/avg/max/min/count。"""
        bucket_expr = BUCKETS.get(bucket, "day")
        agg_expr = AGG_FUNCS.get(agg, "SUM")
        conditions = ["tenant_id = :tenant_id", "metric_code = :metric_code"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "metric_code": metric_code}
        if start is not None:
            conditions.append("stat_time >= :start")
            params["start"] = start
        if end is not None:
            conditions.append("stat_time <= :end")
            params["end"] = end
        if granularity:
            conditions.append("granularity = :granularity")
            params["granularity"] = granularity
        sql = text(
            f"SELECT date_trunc('{bucket_expr}', stat_time) AS bucket,"
            f" {agg_expr}(value) AS value, COUNT(*) AS points"
            f" FROM {TS_TABLE} WHERE {' AND '.join(conditions)}"
            f" GROUP BY 1 ORDER BY 1"
        )
        return [dict(r._mapping) for r in db.execute(sql, params).all()]

    # ------------------------------------------------------------ 状态
    def capability(self, db=None) -> AdapterCapability:
        detail: dict = {}
        available = False
        if db is not None:
            try:
                partitioned = self.is_partitioned(db)
                partitions = self.existing_partitions(db) if partitioned else []
                detail = {
                    "table": TS_TABLE,
                    "partitioned": partitioned,
                    "partition_count": len(partitions),
                    "auto_partition": settings.STORAGE_TS_AUTO_PARTITION,
                    "ahead_months": settings.STORAGE_TS_PARTITION_AHEAD_MONTHS,
                    "behind_months": settings.STORAGE_TS_PARTITION_BEHIND_MONTHS,
                }
                available = partitioned
            except Exception as exc:
                detail = {"error": f"{type(exc).__name__}: {exc}"[:255]}
        return AdapterCapability(
            kind=self.kind,
            engine=self.engine,
            label=self.label,
            available=available,
            detail=detail,
        )

    def stats(self, db=None) -> dict:
        points = 0
        partitions: list[dict] = []
        size = ""
        if db is not None:
            try:
                points = int(db.execute(text(f"SELECT count(*) FROM {TS_TABLE}")).scalar() or 0)
                rows = db.execute(
                    text(
                        "SELECT c.relname, pg_total_relation_size(c.oid) AS bytes,"
                        " c.reltuples::bigint AS est_rows"
                        " FROM pg_class c JOIN pg_inherits i ON i.inhrelid = c.oid"
                        " JOIN pg_class p ON p.oid = i.inhparent"
                        " WHERE p.relname = :parent ORDER BY c.relname"
                    ),
                    {"parent": TS_TABLE},
                ).all()
                partitions = [
                    {"name": r.relname, "size": f"{int(r.bytes) / 1024:.1f} KB", "est_rows": int(r.est_rows or 0)}
                    for r in rows
                ]
                size = str(
                    db.execute(
                        text("SELECT pg_size_pretty(pg_total_relation_size(:t))"), {"t": TS_TABLE}
                    ).scalar()
                    or ""
                )
            except Exception as exc:
                logger.warning("timeseries stats failed: %s", exc)
        latest = None
        if db is not None:
            try:
                latest = db.execute(text(f"SELECT max(stat_time) FROM {TS_TABLE}")).scalar()
            except Exception:
                latest = None
        return {
            "kind": self.kind,
            "engine": self.engine,
            "table": TS_TABLE,
            "points": points,
            "total_size": size,
            "latest_stat_time": latest.strftime("%Y-%m-%d %H:%M:%S") if latest else None,
            "partitions": partitions,
            "retention_hint": f"分区按月创建，配置冗余 ±{settings.STORAGE_TS_PARTITION_AHEAD_MONTHS} 个月",
        }


timeseries_adapter = TimeSeriesAdapter()
