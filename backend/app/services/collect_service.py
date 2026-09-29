"""采集调度服务：把「数据源 + 字段映射 + 调度计划」跑成真实的数据采集。

三种采集方式的能力边界（诚实标注，不编造结果）：
- csv：读取服务器 data/raw 下的文件，复用数据接入（ingest_service.run_import）解析链路，
  真实落库写入指标值，simulated=False；
- api：用标准库 urllib 拉取 HTTP(S) JSON 接口，按映射解析后真实写入指标值，
  simulated=False；带 SSRF 防护（禁内网/回环/保留地址）与超时/体积上限；
- sql：直连数据源执行受控 SELECT（表名白名单 + 行数上限 + 连接超时），按字段映射
  解析后真实写入指标值，simulated=False，已接入 PostgreSQL / MySQL / ClickHouse 驱动；
  Hive 驱动仍未接入，该类数据源仅做 TCP 连通性探测，simulated=True。

调度：内置轻量守护线程按 30 秒粒度扫描 interval 任务并执行；
可用环境变量 COLLECT_SCHEDULER_ENABLED=0 关闭（关闭后仅支持手动触发）。
"""

import importlib
import ipaddress
import json
import logging
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.models.collect import CollectRun, CollectTask
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.schemas.ingest import IngestMapping
from app.schemas.metric import MetricValueIn
from app.services import metric_service
from app.services.ingest_service import (
    MAX_ERROR_DETAIL,
    _resolve_metric,
    parse_number,
    parse_time,
    run_import,
)
from app.utils.datetime_util import now as now_tz

logger = logging.getLogger(__name__)

# API 采集防护参数
API_TIMEOUT_SECONDS = 10
API_MAX_BYTES = 5 * 1024 * 1024
API_MAX_RECORDS = 5000
API_USER_AGENT = "OpsCompass-Collector/0.9"

# 数据库直连采集参数
SQL_TIMEOUT_SECONDS = 10
SQL_MAX_ROWS = 5000
# 数据源类型 → (SQLAlchemy 驱动名, 运行时需校验的驱动模块)
SQL_SUPPORTED_TYPES: dict[str, tuple[str, str]] = {
    "postgresql": ("postgresql+psycopg", "psycopg"),
    "mysql": ("mysql+pymysql", "pymysql"),
    # ClickHouse 走 HTTP 接口（默认 8123 端口），驱动 clickhouse-connect + clickhouse-sqlalchemy
    "clickhouse": ("clickhousedb+connect", "clickhouse_connect"),
}
# 表名白名单：仅允许 schema.table / table 形式，杜绝拼接注入
SQL_TABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")

# 调度扫描间隔与最小调度间隔
SCHEDULER_TICK_SECONDS = 30
MIN_INTERVAL_MINUTES = 1


class CollectError(Exception):
    """采集过程中的可预期错误（对外返回为失败信息，不抛 500）。"""


# ---------------------------------------------------------------- 调度时间


def compute_next_run(
    base: Optional[datetime], schedule_type: str, interval_minutes: int
) -> Optional[datetime]:
    """计算下次计划执行时间；manual 或间隔非法时返回 None。"""
    if schedule_type != "interval" or interval_minutes < MIN_INTERVAL_MINUTES:
        return None
    anchor = base or now_tz()
    return anchor + timedelta(minutes=interval_minutes)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """统一为带时区时间，避免 DB 取回 naive 值参与比较时报错。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def scheduler_enabled() -> bool:
    """调度线程是否启用（默认启用，环境变量置 0/false 关闭）。"""
    raw = str(os.getenv("COLLECT_SCHEDULER_ENABLED", "1")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


# ---------------------------------------------------------------- 采集方式目录

COLLECT_MODE_CATALOG: list[dict[str, Any]] = [
    {
        "mode": "csv",
        "name": "本地文件采集",
        "target_label": "文件名（data/raw 下）",
        "target_hint": "如 sample_metrics.csv，文件需先通过「数据接入」上传",
        "real_fetch": True,
        "description": "读取服务器 data/raw 目录下的 CSV/Excel，按列映射解析后写入指标值，真实落库。",
    },
    {
        "mode": "api",
        "name": "HTTP 接口采集",
        "target_label": "接口 URL",
        "target_hint": "如 https://api.example.com/v1/metrics，返回 JSON",
        "real_fetch": True,
        "description": "拉取 JSON 接口，按 data_path 定位记录数组，按字段映射解析后写入指标值，真实落库。",
    },
    {
        "mode": "sql",
        "name": "数据库直连采集",
        "target_label": "库表名",
        "target_hint": "如 ods_daily_shop，需绑定 PostgreSQL / MySQL / ClickHouse 数据源",
        "real_fetch": True,
        "description": "直连 PostgreSQL / MySQL / ClickHouse 执行受控 SELECT（表名白名单 + 5000 行上限），按字段映射解析后写入指标值，真实落库；ClickHouse 走 HTTP 8123 端口（需已安装 clickhouse-connect），MySQL 需环境已安装 pymysql 驱动，Hive 驱动未接入仍为演练。",
    },
]


# ---------------------------------------------------------------- 目标安全校验


def _is_public_host(host: str) -> bool:
    """SSRF 防护：拒绝回环、私网、链路本地与保留地址。"""
    lowered = host.strip().strip("[]").lower()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return True  # 域名交由 DNS 解析，放行（DNS 重绑定风险由出网白名单在网络层收敛）
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _fetch_json(url: str, method: str = "GET", headers: Optional[dict] = None) -> Any:
    """拉取 JSON（仅 http/https，超时与体积受控）。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise CollectError("接口地址仅支持 http/https 协议")
    if not parsed.hostname:
        raise CollectError("接口地址缺少主机名")
    if not _is_public_host(parsed.hostname):
        raise CollectError("接口地址为内网/回环地址，出于安全考虑已拒绝采集")

    request_headers = {"User-Agent": API_USER_AGENT, "Accept": "application/json"}
    for key, value in (headers or {}).items():
        request_headers[str(key)] = str(value)
    req = urllib.request.Request(url, headers=request_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT_SECONDS) as resp:
            raw = resp.read(API_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise CollectError(f"接口返回 HTTP {exc.code}") from exc
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise CollectError(f"接口请求失败：{exc}") from exc
    if len(raw) > API_MAX_BYTES:
        raise CollectError(f"接口响应超过上限 {API_MAX_BYTES // 1024 // 1024}MB")
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise CollectError(f"接口响应不是合法 JSON：{exc}") from exc


def _extract_records(payload: Any, data_path: str) -> list[dict[str, Any]]:
    """按点号路径（如 data.items）定位记录数组。"""
    node = payload
    for part in [p for p in (data_path or "").split(".") if p]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                raise CollectError(f"数据路径不存在: {data_path}") from None
        else:
            raise CollectError(f"数据路径不存在: {data_path}")
    if isinstance(node, dict):
        inner_lists = [v for v in node.values() if isinstance(v, list)]
        if len(inner_lists) == 1:
            node = inner_lists[0]
        else:
            node = [node]
    if not isinstance(node, list):
        raise CollectError("未能从接口响应中定位记录数组（可用扩展配置 data_path 指定）")
    records = [item for item in node if isinstance(item, dict)]
    if not records:
        raise CollectError("接口返回的记录数组为空")
    if len(records) > API_MAX_RECORDS:
        raise CollectError(f"记录数 {len(records)} 超过单次采集上限 {API_MAX_RECORDS}")
    return records


def _mapping_of(task: CollectTask) -> IngestMapping:
    if not task.mapping:
        raise CollectError("任务缺少字段映射配置")
    try:
        return IngestMapping(**task.mapping)
    except Exception as exc:  # pydantic 校验失败
        raise CollectError(f"字段映射配置非法：{exc}") from exc


# ---------------------------------------------------------------- 采集执行


def _write_records(
    db: Session,
    task: CollectTask,
    mapping: IngestMapping,
    records: list[dict[str, Any]],
    created_codes: list[str],
) -> dict[str, Any]:
    """按 wide/long 布局把记录写入指标值，返回统计与错误明细。"""
    errors: list[dict[str, Any]] = []
    cache: dict[str, Metric] = {}
    success = failed = skipped = 0
    value_count = 0

    if mapping.layout == "wide":
        if not mapping.metric_columns:
            raise CollectError("宽表模式需至少配置一条「指标编码 → 字段名」映射")
        jobs: list[tuple[str, Metric]] = []
        for code, field in mapping.metric_columns.items():
            cache[code] = _resolve_metric(
                db, task.tenant_id, code, mapping, task.source_id, created_codes
            )
            jobs.append((field, cache[code]))
        for idx, row in enumerate(records, start=1):
            stat_time = parse_time(row.get(mapping.time_column), mapping.time_format)
            if stat_time is None:
                failed += 1
                if len(errors) < MAX_ERROR_DETAIL:
                    errors.append({"row": idx, "message": f"时间字段无法解析: {mapping.time_column}"})
                continue
            row_written = 0
            for field, metric in jobs:
                number = parse_number(row.get(field))
                if number is None:
                    continue
                metric_service.upsert_values(
                    db,
                    metric,
                    [MetricValueIn(stat_time=stat_time, granularity=mapping.granularity, value=number)],
                )
                row_written += 1
            value_count += row_written
            if row_written == 0:
                skipped += 1
            else:
                success += 1
    else:
        if not mapping.metric_column or not mapping.value_column:
            raise CollectError("长表模式需配置「指标编码字段」与「指标值字段」")
        for idx, row in enumerate(records, start=1):
            code = str(row.get(mapping.metric_column) or "").strip()
            if not code:
                failed += 1
                if len(errors) < MAX_ERROR_DETAIL:
                    errors.append({"row": idx, "message": "指标编码为空"})
                continue
            stat_time = parse_time(row.get(mapping.time_column), mapping.time_format)
            if stat_time is None:
                failed += 1
                if len(errors) < MAX_ERROR_DETAIL:
                    errors.append({"row": idx, "message": f"时间字段无法解析: {mapping.time_column}"})
                continue
            number = parse_number(row.get(mapping.value_column))
            if number is None:
                skipped += 1
                continue
            metric = cache.get(code) or _resolve_metric(
                db, task.tenant_id, code, mapping, task.source_id, created_codes
            )
            cache[code] = metric
            metric_service.upsert_values(
                db,
                metric,
                [MetricValueIn(stat_time=stat_time, granularity=mapping.granularity, value=number)],
            )
            value_count += 1
            success += 1

    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "value_count": value_count,
        "errors": errors,
        "metric_codes": sorted(cache.keys()),
    }


def _run_csv(
    db: Session, task: CollectTask, mapping: IngestMapping
) -> dict[str, Any]:
    """本地文件采集：复用数据接入链路，交由 ImportTask 留痕。"""
    import_task = run_import(
        db, task.tenant_id, file_name=task.target, mapping=mapping, source_id=task.source_id
    )
    status_map = {"success": "success", "partial": "partial", "failed": "failed"}
    return {
        "status": status_map.get(import_task.status, "partial"),
        "rows_in": import_task.total_rows,
        "rows_written": import_task.value_count,
        "rows_failed": import_task.failed_rows,
        "simulated": False,
        "message": import_task.error_msg
        or f"文件采集完成：解析成功 {import_task.success_rows} 行，写入 {import_task.value_count} 条指标值",
        "detail": {
            "import_task_id": import_task.id,
            "file_name": import_task.file_name,
            "file_hash": import_task.file_hash,
            "metric_codes": import_task.metric_codes or [],
            "skipped_rows": import_task.skipped_rows,
            "errors": (import_task.error_detail or [])[:20],
        },
    }


def _run_api(db: Session, task: CollectTask, mapping: IngestMapping) -> dict[str, Any]:
    """HTTP 接口采集：真实出网 + 真实落库。"""
    extra = task.extra_config or {}
    payload = _fetch_json(
        task.target,
        method=str(extra.get("method") or "GET"),
        headers=extra.get("headers") if isinstance(extra.get("headers"), dict) else None,
    )
    records = _extract_records(payload, str(extra.get("data_path") or ""))
    created_codes: list[str] = []
    stats = _write_records(db, task, mapping, records, created_codes)
    status = "success"
    if stats["failed"] and stats["value_count"]:
        status = "partial"
    elif stats["failed"] and not stats["value_count"]:
        status = "failed"
    message = (
        f"接口采集完成：读取 {len(records)} 条记录，写入 {stats['value_count']} 条指标值"
        + (f"，失败 {stats['failed']} 条" if stats["failed"] else "")
    )
    return {
        "status": status,
        "rows_in": len(records),
        "rows_written": stats["value_count"],
        "rows_failed": stats["failed"],
        "simulated": False,
        "message": message,
        "detail": {
            "url": task.target,
            "data_path": extra.get("data_path") or "",
            "sample": records[:3],
            "metric_codes": stats["metric_codes"],
            "created_metrics": created_codes,
            "skipped_rows": stats["skipped"],
            "errors": stats["errors"][:20],
        },
    }


def _jsonable(value: Any) -> Any:
    """把数据库列值转成可 JSON 序列化的形态，用于运行明细留痕。"""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def _build_sql_url(source: DataSource) -> str:
    """按数据源配置拼装 SQLAlchemy 连接串（口令解密后做 URL 编码）。"""
    entry = SQL_SUPPORTED_TYPES.get(source.ds_type)
    if entry is None:
        raise CollectError(
            f"{source.ds_type} 直连驱动尚未接入，当前支持 PostgreSQL / MySQL / ClickHouse"
        )
    driver, driver_module = entry
    try:
        importlib.import_module(driver_module)
    except ImportError as exc:  # 驱动缺失按可预期错误返回，不抛 500
        raise CollectError(
            f"{source.ds_type} 直连驱动 {driver_module} 未安装，请先安装该驱动后重试"
        ) from exc
    if not source.host or not source.port:
        raise CollectError(f"数据源 {source.code} 未配置主机/端口")
    if not source.db_name:
        raise CollectError(f"数据源 {source.code} 未配置库名")
    password = ""
    if source.password_enc:
        try:
            password = decrypt(source.password_enc)
        except Exception as exc:  # 口令解密失败按可预期错误返回，不抛 500
            raise CollectError(f"数据源 {source.code} 口令解密失败：{exc}") from exc
    user = urllib.parse.quote_plus(source.username or "")
    auth = f"{user}:{urllib.parse.quote_plus(password)}@" if user else ""
    return f"{driver}://{auth}{source.host}:{int(source.port)}/{source.db_name}"


def _connect_args(ds_type: str) -> dict[str, Any]:
    """按数据源类型分派驱动连接参数（各驱动对超时参数的命名不一致）。"""
    if ds_type == "clickhouse":
        return {
            "connect_timeout": SQL_TIMEOUT_SECONDS,
            "send_receive_timeout": SQL_TIMEOUT_SECONDS,
        }
    return {"connect_timeout": SQL_TIMEOUT_SECONDS}


def _probe_source(source: DataSource, task: CollectTask) -> dict[str, Any]:
    """驱动未接入的数据源：仅做 TCP 连通性探测，留演练记录。"""
    reachable = False
    probe_error = ""
    started = time.perf_counter()
    try:
        with socket.create_connection((source.host, int(source.port)), timeout=3):
            reachable = True
    except OSError as exc:
        probe_error = str(exc)
    probe_ms = int((time.perf_counter() - started) * 1000)
    if not reachable:
        raise CollectError(f"数据源连通性探测失败：{probe_error or '无法建立连接'}")

    return {
        "status": "skipped",
        "rows_in": 0,
        "rows_written": 0,
        "rows_failed": 0,
        "simulated": True,
        "message": (
            f"数据源 {source.code} 连通正常（{probe_ms}ms）；"
            f"{source.ds_type} 直连驱动尚未接入，本次未真实采集与写入"
        ),
        "detail": {
            "source_code": source.code,
            "ds_type": source.ds_type,
            "host": source.host,
            "port": source.port,
            "probe_ms": probe_ms,
            "table": task.target,
            "simulated": True,
        },
    }


def _run_sql(db: Session, task: CollectTask) -> dict[str, Any]:
    """数据库直连采集：受控 SELECT 真实拉取 + 真实落库。"""
    source: Optional[DataSource] = None
    if task.source_id:
        source = db.get(DataSource, task.source_id)
    if source is None:
        raise CollectError("数据库采集需绑定数据源后再执行")
    if not source.host or not source.port:
        raise CollectError(f"数据源 {source.code} 未配置主机/端口")

    if source.ds_type not in SQL_SUPPORTED_TYPES:
        return _probe_source(source, task)

    table = str(task.target or "").strip()
    if not SQL_TABLE_PATTERN.match(table):
        raise CollectError("表名非法：仅支持「表名」或「库名.表名」，且只含字母/数字/下划线")
    mapping = _mapping_of(task)

    extra = task.extra_config or {}
    try:
        row_limit = int(extra.get("limit") or SQL_MAX_ROWS)
    except (TypeError, ValueError):
        raise CollectError("扩展配置 limit 需为整数") from None
    row_limit = max(1, min(row_limit, SQL_MAX_ROWS))

    url = _build_sql_url(source)
    engine = create_engine(url, pool_pre_ping=True, connect_args=_connect_args(source.ds_type))
    query_started = time.perf_counter()
    truncated = False
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table} LIMIT {row_limit + 1}"))
            rows = [dict(row) for row in result.mappings().all()]
    except CollectError:
        raise
    except Exception as exc:
        raise CollectError(f"数据库查询失败：{exc}") from exc
    finally:
        engine.dispose()
    query_ms = int((time.perf_counter() - query_started) * 1000)

    if len(rows) > row_limit:
        rows = rows[:row_limit]
        truncated = True
    if not rows:
        return {
            "status": "failed",
            "rows_in": 0,
            "rows_written": 0,
            "rows_failed": 0,
            "simulated": False,
            "message": f"表 {table} 查询结果为空，未写入指标值",
            "detail": {
                "source_code": source.code,
                "table": table,
                "query_ms": query_ms,
                "row_count": 0,
            },
        }

    created_codes: list[str] = []
    stats = _write_records(db, task, mapping, rows, created_codes)
    status = "success"
    if stats["failed"] and stats["value_count"]:
        status = "partial"
    elif stats["failed"] and not stats["value_count"]:
        status = "failed"
    message = (
        f"数据库采集完成：读取 {len(rows)} 行，写入 {stats['value_count']} 条指标值"
        + (f"，失败 {stats['failed']} 行" if stats["failed"] else "")
        + ("；结果集超过上限已截断" if truncated else "")
    )
    return {
        "status": status,
        "rows_in": len(rows),
        "rows_written": stats["value_count"],
        "rows_failed": stats["failed"],
        "simulated": False,
        "message": message,
        "detail": {
            "source_code": source.code,
            "ds_type": source.ds_type,
            "host": source.host,
            "port": source.port,
            "table": table,
            "limit": row_limit,
            "query_ms": query_ms,
            "truncated": truncated,
            "sample": [{k: _jsonable(v) for k, v in r.items()} for r in rows[:3]],
            "metric_codes": stats["metric_codes"],
            "created_metrics": created_codes,
            "skipped_rows": stats["skipped"],
            "errors": stats["errors"][:20],
        },
    }


def run_collect(db: Session, task: CollectTask, trigger: str = "manual") -> CollectRun:
    """执行一次采集并落运行记录（异常转为 failed 记录，不抛出）。"""
    started_perf = time.perf_counter()
    run = CollectRun(
        tenant_id=task.tenant_id,
        task_id=task.id,
        task_code=task.code,
        collect_mode=task.collect_mode,
        trigger=trigger,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        if task.collect_mode == "csv":
            mapping = _mapping_of(task)
            outcome = _run_csv(db, task, mapping)
        elif task.collect_mode == "api":
            mapping = _mapping_of(task)
            outcome = _run_api(db, task, mapping)
        elif task.collect_mode == "sql":
            outcome = _run_sql(db, task)
        else:  # pragma: no cover
            raise CollectError(f"未知采集方式: {task.collect_mode}")
    except CollectError as exc:
        db.rollback()
        outcome = {
            "status": "failed",
            "rows_in": 0,
            "rows_written": 0,
            "rows_failed": 0,
            "simulated": False,
            "message": str(exc),
            "detail": {"error": str(exc)},
        }
    except Exception as exc:  # 兜底：不因单次采集异常影响服务
        db.rollback()
        logger.exception("[collect] 任务 %s 执行异常", task.code)
        outcome = {
            "status": "failed",
            "rows_in": 0,
            "rows_written": 0,
            "rows_failed": 0,
            "simulated": False,
            "message": f"执行异常：{exc}",
            "detail": {"error": str(exc)},
        }

    duration_ms = int((time.perf_counter() - started_perf) * 1000)
    finished = now_tz()

    run.status = outcome["status"]
    run.rows_in = int(outcome["rows_in"])
    run.rows_written = int(outcome["rows_written"])
    run.rows_failed = int(outcome["rows_failed"])
    run.simulated = bool(outcome["simulated"])
    run.message = outcome["message"]
    run.detail = outcome["detail"]
    run.duration_ms = duration_ms
    run.finished_at = finished

    task.last_run_at = finished
    task.last_status = run.status
    task.run_count = (task.run_count or 0) + 1
    if run.status in {"success", "partial"}:
        task.success_count = (task.success_count or 0) + 1
    elif run.status == "failed":
        task.fail_count = (task.fail_count or 0) + 1
    task.next_run_at = compute_next_run(
        finished, task.schedule_type, task.interval_minutes or 0
    )

    db.add(run)
    db.add(task)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------- 内置调度


def run_due_tasks(db: Session, limit: int = 20) -> list[int]:
    """扫描到期的 interval 任务并执行，返回已执行的任务 ID 列表。"""
    now = now_tz()
    stmt = (
        select(CollectTask)
        .where(
            CollectTask.status == "enabled",
            CollectTask.schedule_type == "interval",
            CollectTask.interval_minutes >= MIN_INTERVAL_MINUTES,
        )
        .order_by(CollectTask.next_run_at.asc().nullsfirst(), CollectTask.id.asc())
        .limit(limit)
    )
    executed: list[int] = []
    for task in db.execute(stmt).scalars().all():
        due = _as_aware(task.next_run_at)
        if task.last_run_at is None and due is None:
            # 新建任务尚未排期：以创建时间 + 间隔作为首次执行点
            created = _as_aware(task.created_at)
            due = compute_next_run(created, task.schedule_type, task.interval_minutes) if created else None
            task.next_run_at = due
            db.add(task)
            db.commit()
        if due is not None and due <= now:
            run_collect(db, task, trigger="schedule")
            executed.append(task.id)
    return executed


_SCHEDULER_STARTED = False
_SCHEDULER_LOCK = threading.Lock()


def start_scheduler() -> bool:
    """启动内置调度线程（幂等）。返回是否已启动。"""
    global _SCHEDULER_STARTED
    if not scheduler_enabled():
        logger.info("[collect] 调度线程已由配置关闭（COLLECT_SCHEDULER_ENABLED=0）")
        return False
    with _SCHEDULER_LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True

    def _loop() -> None:
        from app.models.base import SessionLocal

        logger.info("[collect] 采集调度线程启动，扫描间隔 %ss", SCHEDULER_TICK_SECONDS)
        while True:
            db = None
            try:
                db = SessionLocal()
                executed = run_due_tasks(db)
                if executed:
                    logger.info("[collect] 调度执行任务: %s", executed)
            except Exception as exc:  # 调度线程必须吞异常，避免线程退出
                logger.warning("[collect] 调度扫描异常: %s", exc)
                if db is not None:
                    try:
                        db.rollback()
                    except Exception:  # pragma: no cover
                        pass
            finally:
                if db is not None:
                    db.close()
            time.sleep(SCHEDULER_TICK_SECONDS)

    thread = threading.Thread(target=_loop, name="collect-scheduler", daemon=True)
    thread.start()
    return True


def task_stats(db: Session, tenant_id: int) -> dict[str, Any]:
    """任务维度统计，供总览使用。"""
    rows = db.execute(
        select(CollectTask.status, CollectTask.collect_mode, func.count())
        .where(CollectTask.tenant_id == tenant_id)
        .group_by(CollectTask.status, CollectTask.collect_mode)
    ).all()
    status_dist: dict[str, int] = {}
    mode_dist: dict[str, int] = {}
    total = 0
    for status, mode, count in rows:
        total += count
        status_dist[status] = status_dist.get(status, 0) + count
        mode_dist[mode] = mode_dist.get(mode, 0) + count
    return {"total": total, "status": status_dist, "mode": mode_dist}


def task_metric_map(tenant_id: int, db: Session) -> dict[int, tuple[str, str]]:
    """数据源 ID → (名称, 类型)，用于任务列表回显。"""
    sources = db.execute(select(DataSource).where(DataSource.tenant_id == tenant_id)).scalars().all()
    return {s.id: (s.name, s.ds_type) for s in sources}
