"""语义层 SQL 执行：外部数据源只读查询，不可达时降级内部指标值表。

安全约束：
- 外部查询仅使用编译层白名单 SQL（compiler.CompiledQuery），参数化执行；
- 只读、带连接超时与行数上限；
- 密码解密仅用于数据源连接，不回显。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.models.metric import Metric, MetricValue
from app.semantic.compiler import CompiledQuery
from app.services import metric_service

logger = logging.getLogger(__name__)


class SemanticExecError(RuntimeError):
    """执行失败（连接失败 / 查询被拒 / 结果超限）。"""


@dataclass
class ExecutionResult:
    """执行结果 + 元信息。"""

    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    dialect: str = "internal"
    source_label: str = "内部指标值表"
    execution_ms: int = 0
    fallback_reason: str = ""
    row_limit_hit: bool = False


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _bucket_key(dt: datetime, granularity: str) -> str:
    """把统计时间点对齐到目标粒度的桶 key（字符串，便于排序与 JSON 输出）。"""
    if granularity == "hour":
        return dt.strftime("%Y-%m-%d %H:00:00")
    if granularity == "week":
        monday = dt - timedelta(days=dt.weekday())
        return monday.strftime("%Y-%m-%d")
    if granularity == "month":
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


def _aggregate_internal(
    db: Session,
    metric: Metric,
    *,
    granularity: str,
    start: Optional[datetime],
    end: Optional[datetime],
    dims_filter: Optional[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """内部模式：从 oc_metric_value 取数并按目标粒度/维度聚合。"""
    dims = {k: v for k, v in (dims_filter or {}).items() if v != "__group__"}
    values = metric_service.query_values(
        db, metric, start=start, end=end, dims=dims or None, limit=max(limit, 5000)
    )
    if not values:
        return []
    group_key = next(
        (k for k, v in (dims_filter or {}).items() if v == "__group__"), None
    )
    agg_func = (metric.agg_func or "sum").lower()
    buckets: dict[tuple, dict[str, Any]] = {}
    for mv in values:
        dt = mv.stat_time
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        bk = _bucket_key(dt, granularity)
        dim_val = mv.dims.get(group_key) if group_key and mv.dims else None
        key = (bk, dim_val) if group_key else (bk,)
        cell = buckets.setdefault(key, {"bucket": bk, "values": [], "dim_value": dim_val})
        cell["values"].append(_to_float(mv.value))

    rows: list[dict[str, Any]] = []
    for key in sorted(buckets.keys(), key=lambda x: (x[0], str(x[1] or "") if len(x) > 1 else "")):
        cell = buckets[key]
        vals = cell["values"]
        if agg_func in ("sum", "count"):
            value = sum(vals)
        elif agg_func == "avg":
            value = sum(vals) / len(vals)
        elif agg_func == "count_distinct":
            value = len(set(vals))
        elif agg_func == "max":
            value = max(vals)
        elif agg_func == "min":
            value = min(vals)
        else:
            value = sum(vals)
        row: dict[str, Any] = {"bucket": cell["bucket"], "value": round(value, metric.precision or 2)}
        if group_key:
            row[group_key] = cell["dim_value"] or "全部"
        rows.append(row)
    return rows[:limit]


def _external_engine(ds: Any) -> Any:
    """按数据源类型构造只读连接（超时受控）。"""
    host = ds.host or "127.0.0.1"
    port = ds.port or (5432 if ds.ds_type == "postgresql" else 3306)
    db_name = ds.db_name or ""
    username = ds.username or ""
    password = decrypt(ds.password_enc) if ds.password_enc else ""
    if ds.ds_type == "postgresql":
        url = f"postgresql+psycopg://{username}:{password}@{host}:{port}/{db_name}"
        connect_args = {"connect_timeout": 5}
    elif ds.ds_type == "mysql":
        url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"
        connect_args = {"connect_timeout": 5, "read_timeout": 15}
    else:
        raise SemanticExecError(f"外部执行暂不支持数据源类型: {ds.ds_type}")
    return create_engine(url, pool_pre_ping=True, pool_recycle=300, connect_args=connect_args)


def _execute_external(
    ds: Any,
    compiled: CompiledQuery,
    limit: int,
) -> list[dict[str, Any]]:
    """外部模式：参数化执行编译 SQL，仅取行数上限。"""
    engine = _external_engine(ds)
    try:
        with engine.connect() as conn:
            stmt = text(compiled.sql).execution_options(compiled=[])
            result = conn.execute(stmt, compiled.params)
            rows: list[dict[str, Any]] = []
            hit = False
            for i, row in enumerate(result):
                if i >= limit:
                    hit = True
                    break
                rows.append({key: row._mapping[key] for key in row._mapping.keys()})
            if hit:
                logger.info("语义层外部查询达到行数上限 %s，已截断", limit)
            return rows
    finally:
        engine.dispose()


def execute(
    db: Session,
    metric: Metric,
    compiled: CompiledQuery,
    *,
    granularity: str = "day",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    dims_filter: Optional[dict[str, Any]] = None,
    limit: int = 200,
) -> ExecutionResult:
    """执行总入口：内部模式走 Python 聚合，外部模式走参数化 SQL。"""
    started = time.perf_counter()
    if compiled.internal:
        rows = _aggregate_internal(
            db,
            metric,
            granularity=granularity,
            start=start,
            end=end,
            dims_filter=dims_filter,
            limit=limit,
        )
        return ExecutionResult(
            rows=rows,
            columns=["bucket", "value"] + [k for k, v in (dims_filter or {}).items() if v == "__group__"],
            dialect="internal",
            source_label="内部指标值表",
            execution_ms=int((time.perf_counter() - started) * 1000),
        )

    try:
        from app.models.datasource import DataSource

        ds = None
        if metric.source_id is not None:
            ds = db.get(DataSource, metric.source_id)
        if ds is None:
            raise SemanticExecError("指标未绑定可用数据源，已降级内部指标值表")
        rows = _execute_external(ds, compiled, limit)
        return ExecutionResult(
            rows=rows,
            columns=list(rows[0].keys()) if rows else ["bucket", "value"],
            dialect=compiled.dialect,
            source_label=f"{ds.name}（{ds.ds_type}）",
            execution_ms=int((time.perf_counter() - started) * 1000),
        )
    except SemanticExecError as exc:
        logger.warning("语义层外部执行失败，降级内部指标值表: %s", exc)
        rows = _aggregate_internal(
            db,
            metric,
            granularity=granularity,
            start=start,
            end=end,
            dims_filter=dims_filter,
            limit=limit,
        )
        return ExecutionResult(
            rows=rows,
            columns=["bucket", "value"] + [k for k, v in (dims_filter or {}).items() if v == "__group__"],
            dialect="internal",
            source_label="内部指标值表",
            execution_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 驱动缺失 / 连接异常统一降级
        logger.warning("语义层外部执行异常，降级内部指标值表: %s", exc)
        rows = _aggregate_internal(
            db,
            metric,
            granularity=granularity,
            start=start,
            end=end,
            dims_filter=dims_filter,
            limit=limit,
        )
        return ExecutionResult(
            rows=rows,
            columns=["bucket", "value"] + [k for k, v in (dims_filter or {}).items() if v == "__group__"],
            dialect="internal",
            source_label="内部指标值表",
            execution_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason=f"外部不可达: {exc}",
        )
