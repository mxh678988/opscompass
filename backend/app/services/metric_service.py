"""指标中心核心服务：指标定义管理 + 指标值读写 + 总览/趋势聚合。"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.metric import Metric, MetricDimension, MetricValue
from app.schemas.metric import (
    BreakdownItem,
    CompassMetric,
    CompassOut,
    MetricCreate,
    MetricUpdate,
    MetricValueIn,
    OverviewItem,
    OverviewOut,
    TrendOut,
    TrendPoint,
)

logger = logging.getLogger(__name__)

TZ = ZoneInfo(settings.TIMEZONE)


# ------------------------------------------------------------------ 工具
def ensure_tz(dt: datetime) -> datetime:
    """无时区时间按平台默认时区（Asia/Shanghai）解释。"""
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt


def dims_hash(dims: Optional[dict[str, Any]]) -> str:
    """维度组合的稳定哈希：键排序后序列化，空维度返回空串。"""
    if not dims:
        return ""
    payload = json.dumps(dims, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def to_float(value: Any) -> float:
    """Decimal / None -> float。"""
    if value is None:
        return 0.0
    return float(value)


# ------------------------------------------------------------------ 指标定义
def _apply_metric_query(
    stmt: Select,
    tenant_id: int,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    category_id: Optional[int] = None,
) -> Select:
    stmt = stmt.where(Metric.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Metric.code.ilike(like), Metric.name.ilike(like)))
    if status:
        stmt = stmt.where(Metric.status == status)
    if category_id is not None:
        stmt = stmt.where(Metric.category_id == category_id)
    return stmt


def list_metrics(
    db: Session,
    tenant_id: int,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Metric]]:
    """分页查询指标定义。"""
    base = _apply_metric_query(select(Metric), tenant_id, keyword, status, category_id)
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    stmt = (
        base.options(selectinload(Metric.dimensions))
        .order_by(Metric.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return int(total), list(db.execute(stmt).scalars().all())


def get_metric(db: Session, tenant_id: int, code: str) -> Optional[Metric]:
    """按编码取指标（含维度）。"""
    stmt = (
        select(Metric)
        .options(selectinload(Metric.dimensions))
        .where(Metric.tenant_id == tenant_id, Metric.code == code)
    )
    return db.execute(stmt).scalars().first()


def list_online_metrics(db: Session, tenant_id: int) -> list[Metric]:
    """取上线中的指标，用于总览。"""
    stmt = (
        select(Metric)
        .where(Metric.tenant_id == tenant_id, Metric.status == "online")
        .order_by(Metric.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _resolve_dimensions(db: Session, tenant_id: int, payload: MetricCreate) -> list[MetricDimension]:
    """按 code 复用已有维度，不存在则新建。"""
    result: list[MetricDimension] = []
    for item in payload.dimensions:
        stmt = select(MetricDimension).where(
            MetricDimension.tenant_id == tenant_id, MetricDimension.code == item.code
        )
        dim = db.execute(stmt).scalars().first()
        if dim is None:
            dim = MetricDimension(
                tenant_id=tenant_id,
                code=item.code,
                name=item.name,
                dim_type=item.dim_type,
                source_field=item.source_field,
                value_scope=item.value_scope,
            )
            db.add(dim)
            db.flush()
        result.append(dim)
    return result


def create_metric(db: Session, tenant_id: int, payload: MetricCreate) -> Metric:
    """新建指标定义。"""
    metric = Metric(
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        metric_type=payload.metric_type,
        agg_func=payload.agg_func,
        formula=payload.formula,
        unit=payload.unit,
        precision=payload.precision,
        granularity=payload.granularity,
        owner=payload.owner,
        tags=payload.tags,
        category_id=payload.category_id,
        source_id=payload.source_id,
        status=payload.status,
    )
    metric.dimensions = _resolve_dimensions(db, tenant_id, payload)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def update_metric(db: Session, metric: Metric, payload: MetricUpdate) -> Metric:
    """局部更新指标定义。"""
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(metric, field, value)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def delete_metric(db: Session, metric: Metric) -> None:
    """删除指标定义及其指标值（级联）。"""
    db.delete(metric)
    db.commit()


# ------------------------------------------------------------------ 存储适配（写后一致性）
def _rows_for_ts(metric: Metric, pairs: list[tuple[datetime, str, Optional[dict], str, Decimal]]) -> list[dict]:
    """把待写入的指标值整理为时序适配层所需的行结构。"""
    return [
        {
            "tenant_id": metric.tenant_id,
            "metric_id": metric.id,
            "metric_code": metric.code,
            "stat_time": stat_time,
            "granularity": granularity,
            "dims": dims,
            "dims_hash": d_hash,
            "value": float(value),
            "source_id": metric.source_id,
            "origin": "write_through",
        }
        for stat_time, granularity, dims, d_hash, value in pairs
    ]


def mirror_metric_values(db: Session, metric: Metric, rows: list[dict]) -> dict:
    """把指标值镜像到时序分区表；失败时按 STRICT 配置决定是否向上抛出。"""
    outcome = {"enabled": bool(settings.STORAGE_MIRROR_ENABLED), "mirrored": 0, "error": None}
    if not settings.STORAGE_MIRROR_ENABLED or not rows:
        return outcome
    try:
        from app.storage.timeseries import timeseries_adapter

        outcome["mirrored"] = timeseries_adapter.write_points(db, rows, auto_partition=True)
    except Exception as exc:
        db.rollback()
        outcome["error"] = f"{type(exc).__name__}: {exc}"[:255]
        logger.warning("指标值镜像时序表失败（metric=%s）：%s", metric.code, outcome["error"])
        if settings.STORAGE_MIRROR_STRICT:
            raise
    return outcome


def invalidate_tenant_cache(tenant_id: int, namespaces: Sequence[str] = ("overview", "compass")) -> int:
    """写后失效租户热点缓存（缓存不可用时静默返回 0）。"""
    if not settings.STORAGE_CACHE_ENABLED:
        return 0
    from app.storage.cache import cache_adapter

    removed = 0
    for namespace in namespaces:
        removed += cache_adapter.delete_prefix(cache_adapter.build_key(namespace, tenant_id))
    return removed


def _read_cache(namespace: str, *parts: Any) -> Optional[Any]:
    if not settings.STORAGE_CACHE_ENABLED:
        return None
    from app.storage.cache import cache_adapter

    return cache_adapter.get_json(cache_adapter.build_key(namespace, *parts))


def _write_cache(namespace: str, payload: Any, *parts: Any) -> bool:
    if not settings.STORAGE_CACHE_ENABLED:
        return False
    from app.storage.cache import cache_adapter

    return cache_adapter.set_json(cache_adapter.build_key(namespace, *parts), payload)


# ------------------------------------------------------------------ 指标值
def upsert_values(
    db: Session, metric: Metric, items: Sequence[MetricValueIn]
) -> int:
    """批量写入指标值，按「指标+时间+粒度+维度」覆盖，并写后维护时序镜像与缓存。"""
    affected = 0
    pairs: list[tuple[datetime, str, Optional[dict], str, Decimal]] = []
    for item in items:
        stat_time = ensure_tz(item.stat_time)
        d_hash = dims_hash(item.dims)
        value = Decimal(str(item.value))
        stmt = select(MetricValue).where(
            MetricValue.metric_id == metric.id,
            MetricValue.stat_time == stat_time,
            MetricValue.granularity == item.granularity,
            MetricValue.dims_hash == d_hash,
        )
        row = db.execute(stmt).scalars().first()
        if row is None:
            row = MetricValue(
                tenant_id=metric.tenant_id,
                metric_id=metric.id,
                stat_time=stat_time,
                granularity=item.granularity,
                dims=item.dims,
                dims_hash=d_hash,
                value=value,
            )
            db.add(row)
        else:
            row.value = value
        pairs.append((stat_time, item.granularity, item.dims, d_hash, value))
        affected += 1
    db.commit()
    if affected:
        mirror_metric_values(db, metric, _rows_for_ts(metric, pairs))
        invalidate_tenant_cache(metric.tenant_id)
    return affected


def query_values(
    db: Session,
    metric: Metric,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    granularity: Optional[str] = None,
    dims: Optional[dict[str, Any]] = None,
    limit: int = 200,
) -> list[MetricValue]:
    """按时间区间查询指标值明细。"""
    stmt = select(MetricValue).where(MetricValue.metric_id == metric.id)
    if start is not None:
        stmt = stmt.where(MetricValue.stat_time >= ensure_tz(start))
    if end is not None:
        stmt = stmt.where(MetricValue.stat_time <= ensure_tz(end))
    if granularity:
        stmt = stmt.where(MetricValue.granularity == granularity)
    if dims is not None:
        stmt = stmt.where(MetricValue.dims_hash == dims_hash(dims))
    stmt = stmt.order_by(MetricValue.stat_time.asc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def _latest_two(db: Session, metric_id: int, granularity: Optional[str]) -> list[MetricValue]:
    """取未分维度（整体口径）的最近两条值；若不存在则退化为任意维度最新两条。"""
    stmt = select(MetricValue).where(MetricValue.metric_id == metric_id)
    if granularity:
        stmt = stmt.where(MetricValue.granularity == granularity)
    whole = (
        stmt.where(MetricValue.dims_hash == "")
        .order_by(MetricValue.stat_time.desc())
        .limit(2)
    )
    rows = list(db.execute(whole).scalars().all())
    if rows:
        return rows
    return list(db.execute(stmt.order_by(MetricValue.stat_time.desc()).limit(2)).scalars().all())


def overview(
    db: Session,
    tenant_id: int,
    granularity: str = "day",
    codes: Optional[list[str]] = None,
) -> OverviewOut:
    """指标总览：每个上线指标的最新值 + 环比。

    未落库任何指标的租户返回空列表（前端按 0 兜底展示）。
    缓存启用时优先读取 Redis 热点缓存（写指标值时按租户前缀失效）。
    """
    cache_parts = (tenant_id, granularity, ",".join(sorted(codes or [])))
    cached = _read_cache("overview", *cache_parts)
    if cached:
        try:
            return OverviewOut.model_validate(cached)
        except Exception:  # 缓存结构不兼容时回源
            logger.warning("总览缓存结构不兼容，已回源数据库")

    metrics = list_online_metrics(db, tenant_id)
    if codes:
        wanted = set(codes)
        metrics = [m for m in metrics if m.code in wanted]

    items: list[OverviewItem] = []
    latest_stat: Optional[datetime] = None
    for metric in metrics:
        rows = _latest_two(db, metric.id, granularity)
        if not rows:
            items.append(
                OverviewItem(code=metric.code, name=metric.name, unit=metric.unit, precision=metric.precision)
            )
            continue

        current = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        cur_val = to_float(current.value)
        prev_val = to_float(prev.value) if prev is not None else None
        delta = None
        if prev_val not in (None, 0.0):
            delta = round((cur_val - prev_val) / abs(prev_val), 6)

        if latest_stat is None or current.stat_time > latest_stat:
            latest_stat = current.stat_time

        items.append(
            OverviewItem(
                code=metric.code,
                name=metric.name,
                unit=metric.unit,
                precision=metric.precision,
                value=round(cur_val, metric.precision),
                prev_value=round(prev_val, metric.precision) if prev_val is not None else None,
                delta_ratio=delta,
                stat_time=current.stat_time,
                has_data=True,
            )
        )
    out = OverviewOut(stat_date=latest_stat, items=items)
    _write_cache("overview", out.model_dump(mode="json"), *cache_parts)
    return out


def trend(
    db: Session,
    metric: Metric,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    granularity: str = "day",
    dims: Optional[dict[str, Any]] = None,
    limit: int = 365,
) -> TrendOut:
    """指标趋势序列。"""
    if dims is None:
        stmt = select(MetricValue).where(
            MetricValue.metric_id == metric.id,
            MetricValue.granularity == granularity,
            MetricValue.dims_hash == "",
        )
    else:
        stmt = select(MetricValue).where(
            MetricValue.metric_id == metric.id,
            MetricValue.granularity == granularity,
            MetricValue.dims_hash == dims_hash(dims),
        )
    if start is not None:
        stmt = stmt.where(MetricValue.stat_time >= ensure_tz(start))
    if end is not None:
        stmt = stmt.where(MetricValue.stat_time <= ensure_tz(end))

    rows = list(db.execute(stmt.order_by(MetricValue.stat_time.asc()).limit(limit)).scalars().all())
    return TrendOut(
        code=metric.code,
        granularity=granularity,
        start=start,
        end=end,
        points=[TrendPoint(stat_time=r.stat_time, value=to_float(r.value)) for r in rows],
    )


# ------------------------------------------------------------------ 全景罗盘
def available_dim_keys(db: Session, tenant_id: int) -> list[str]:
    """列出指标值里出现过的维度键（仅对象型 dims）。"""
    sql = text(
        "select distinct k from ("
        " select json_object_keys(dims) as k from oc_metric_value"
        " where tenant_id = :tid and dims is not null and json_typeof(dims) = 'object'"
        ") t order by k"
    )
    return [str(k) for k in db.execute(sql, {"tid": tenant_id}).scalars().all()]


def _breakdown(
    db: Session, metric: Metric, granularity: str, dim_key: str, days: int = 180
) -> tuple[list[BreakdownItem], Optional[datetime]]:
    """按维度键拆解指标值：取最近一期各维度取值 + 环比 + 占比。"""
    key_expr = MetricValue.dims.op("->>")(dim_key)
    since = datetime.now(TZ) - timedelta(days=days)
    stmt = (
        select(MetricValue)
        .where(
            MetricValue.metric_id == metric.id,
            MetricValue.granularity == granularity,
            MetricValue.dims_hash != "",
            MetricValue.stat_time >= since,
            key_expr.isnot(None),
        )
        .order_by(MetricValue.stat_time.desc())
        .limit(2000)
    )
    rows = list(db.execute(stmt).scalars().all())
    if not rows:
        return [], None

    latest = max(r.stat_time for r in rows)
    grouped: dict[str, list[MetricValue]] = {}
    for row in rows:
        grouped.setdefault(row.dims_hash, []).append(row)

    raw: list[tuple[str, float, Optional[float]]] = []
    for seq in grouped.values():
        cur = next((r for r in seq if r.stat_time == latest), seq[0])
        prev = next((r for r in seq if r.stat_time < cur.stat_time), None)
        raw.append(
            (
                str((cur.dims or {}).get(dim_key) or "-"),
                to_float(cur.value),
                to_float(prev.value) if prev is not None else None,
            )
        )
    raw.sort(key=lambda item: item[1], reverse=True)
    total = sum(value for _, value, _ in raw)

    items: list[BreakdownItem] = []
    for dim_value, value, prev_value in raw:
        delta = None
        if prev_value not in (None, 0.0):
            delta = round((value - prev_value) / abs(prev_value), 6)
        items.append(
            BreakdownItem(
                dim_value=dim_value,
                value=round(value, metric.precision),
                prev_value=round(prev_value, metric.precision) if prev_value is not None else None,
                delta_ratio=delta,
                share=round(value / total, 6) if total else None,
            )
        )
    return items, latest


def compass(
    db: Session,
    tenant_id: int,
    granularity: str = "day",
    dim_key: Optional[str] = None,
    codes: Optional[list[str]] = None,
    trend_limit: int = 180,
) -> CompassOut:
    """全景罗盘：全部上线指标的整体值 + 环比，叠加指定维度拆解与趋势。"""
    metrics = list_online_metrics(db, tenant_id)
    if codes:
        wanted = set(codes)
        metrics = [m for m in metrics if m.code in wanted]

    available = available_dim_keys(db, tenant_id)
    dim_name: Optional[str] = None
    if dim_key:
        dim = db.execute(
            select(MetricDimension).where(
                MetricDimension.tenant_id == tenant_id, MetricDimension.code == dim_key
            )
        ).scalars().first()
        dim_name = dim.name if dim is not None else dim_key

    items: list[CompassMetric] = []
    latest_stat: Optional[datetime] = None
    dim_values: list[str] = []

    for metric in metrics:
        item = CompassMetric(
            code=metric.code, name=metric.name, unit=metric.unit, precision=metric.precision
        )
        rows = _latest_two(db, metric.id, granularity)
        if rows:
            current = rows[0]
            prev = rows[1] if len(rows) > 1 else None
            cur_val = to_float(current.value)
            prev_val = to_float(prev.value) if prev is not None else None
            item.has_data = True
            item.value = round(cur_val, metric.precision)
            item.prev_value = round(prev_val, metric.precision) if prev_val is not None else None
            if prev_val not in (None, 0.0):
                item.delta_ratio = round((cur_val - prev_val) / abs(prev_val), 6)
            item.stat_time = current.stat_time
            if latest_stat is None or current.stat_time > latest_stat:
                latest_stat = current.stat_time
            item.trend = trend(db, metric, granularity=granularity, limit=trend_limit).points

        if dim_key:
            breakdown, breakdown_stat = _breakdown(db, metric, granularity, dim_key)
            item.breakdown = breakdown
            if breakdown_stat is not None and (latest_stat is None or breakdown_stat > latest_stat):
                latest_stat = breakdown_stat
            for entry in breakdown:
                if entry.dim_value not in dim_values:
                    dim_values.append(entry.dim_value)

        items.append(item)

    return CompassOut(
        granularity=granularity,
        dim_key=dim_key,
        dim_name=dim_name,
        available_dim_keys=available,
        dim_values=dim_values,
        latest_stat=latest_stat,
        items=items,
    )
