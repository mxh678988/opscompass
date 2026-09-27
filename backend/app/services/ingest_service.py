"""数据接入服务：CSV / Excel 文件解析 → 清洗 → 写入指标值。

设计要点：
1. 文件先落盘到 data/raw，再按「列映射」解析，避免把大文件读进内存两次；
2. 支持两种布局：wide（一行多指标）/ long（一行一指标）；
3. 清洗规则：空值跳过、时间无法解析记失败、数值无法解析记失败，失败明细最多留存 100 条；
4. 指标值写入复用 metric_service.upsert_values，天然满足「同时间+粒度+维度」覆盖语义。
"""

import hashlib
import math
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, settings
from app.models.import_task import ImportTask
from app.models.metric import Metric
from app.schemas.ingest import IngestMapping
from app.schemas.metric import MetricValueIn
from app.services import metric_service
from app.utils.datetime_util import now as now_tz

def _resolve_data_dir() -> Path:
    """解析数据根目录。

    容器内 cwd 为 /app（data 已挂载到 /app/data），而 BASE_DIR 在容器内会解析为 /，
    因此优先用「配置的 DATA_DIR 相对 cwd」，不存在时回落到项目根目录下的 data。
    """
    candidate = Path(settings.DATA_DIR)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    if not candidate.exists():
        fallback = BASE_DIR / "data"
        if fallback.exists():
            return fallback
    return candidate


DATA_DIR = _resolve_data_dir()
RAW_DIR = DATA_DIR / "raw"
SAMPLE_DIR = DATA_DIR / "samples"

ALLOWED_SUFFIXES = (".csv", ".xlsx", ".xls")
MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_ERROR_DETAIL = 100
MAX_QUERY_ROWS = 200_000

_EMPTY_TOKENS = {"", "-", "--", "/", "null", "none", "nan", "na", "n/a", "无"}
_TIME_HINTS = ("date", "time", "day", "日期", "时间", "dt")
_METRIC_HINTS = ("metric", "metric_code", "指标", "指标编码", "code", "kpi")
_VALUE_HINTS = ("value", "val", "值", "数值", "amount")


# ------------------------------------------------------------------ 文件
def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def safe_raw_path(file_name: str) -> Path:
    """把文件名收敛到 data/raw 内，防止路径穿越。"""
    name = Path(file_name).name
    if not name:
        raise ValueError("文件名不能为空")
    path = (RAW_DIR / name).resolve()
    if RAW_DIR.resolve() != path.parent:
        raise ValueError(f"非法文件路径: {file_name}")
    return path


def save_upload(file_name: str, content: bytes) -> dict[str, Any]:
    """保存上传文件到 data/raw，返回落盘信息。"""
    ensure_dirs()
    name = Path(file_name).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"仅支持 {', '.join(ALLOWED_SUFFIXES)} 文件")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"文件超过 {MAX_FILE_SIZE // 1024 // 1024}MB 限制")
    if not content:
        raise ValueError("文件内容为空")

    stem = re.sub(r"[^\w\-.]", "_", Path(name).stem)[:60] or "upload"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    target = RAW_DIR / f"{stem}_{stamp}{suffix}"
    target.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    return {
        "file_name": target.name,
        "file_size": len(content),
        "file_hash": digest,
        "saved_path": str(target),
    }


def list_raw_files() -> list[dict[str, Any]]:
    """列出 data/raw 下可导入的文件。"""
    ensure_dirs()
    files: list[dict[str, Any]] = []
    for path in sorted(RAW_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES:
            stat = path.stat()
            files.append(
                {
                    "file_name": path.name,
                    "file_size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
    return files


def list_sample_files() -> list[dict[str, Any]]:
    """列出 data/samples 下的示例文件（供一键导入演示）。"""
    ensure_dirs()
    files: list[dict[str, Any]] = []
    for path in sorted(SAMPLE_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES:
            files.append({"file_name": path.name, "file_size": path.stat().st_size})
    return files


def copy_sample_to_raw(file_name: str) -> dict[str, Any]:
    """把示例文件复制（覆盖）到 data/raw，返回落盘信息。"""
    ensure_dirs()
    src = (SAMPLE_DIR / Path(file_name).name).resolve()
    if SAMPLE_DIR.resolve() not in src.parents or not src.is_file():
        raise FileNotFoundError(f"示例文件不存在: {file_name}")
    content = src.read_bytes()
    target = RAW_DIR / src.name
    target.write_bytes(content)
    return {
        "file_name": target.name,
        "file_size": len(content),
        "file_hash": hashlib.sha256(content).hexdigest(),
        "saved_path": str(target),
    }


# ------------------------------------------------------------------ 读取
def read_frame(path: Path) -> pd.DataFrame:
    """读取 CSV / Excel；CSV 自动兼容 utf-8-sig / gbk 编码。"""
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path.name}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV 编码无法识别，请另存为 UTF-8")
    frame = pd.read_excel(path)
    if len(frame) > MAX_QUERY_ROWS:
        raise ValueError(f"文件行数超过上限 {MAX_QUERY_ROWS}")
    return frame


def _jsonable(value: Any) -> Any:
    """把 numpy / pandas 标量转成可 JSON 序列化的值。"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def preview(file_name: str, limit: int = 20) -> dict[str, Any]:
    """读取文件前 N 行，给出列清单与建议映射。"""
    path = safe_raw_path(file_name)
    frame = read_frame(path)
    columns = [str(c) for c in frame.columns]
    rows = [
        {str(k): _jsonable(v) for k, v in record.items()}
        for record in frame.head(limit).to_dict(orient="records")
    ]
    return {
        "file_name": path.name,
        "columns": columns,
        "total_rows": int(len(frame)),
        "rows": rows,
    }


def suggest_mapping(columns: list[str], metric_codes: list[str]) -> dict[str, Any]:
    """按列名启发式给出建议映射。"""
    lowered = {c: str(c).strip().lower() for c in columns}

    time_column = ""
    for col, low in lowered.items():
        if any(hint in low for hint in _TIME_HINTS):
            time_column = col
            break
    if not time_column and columns:
        time_column = columns[0]

    metric_column = next((c for c, low in lowered.items() if low in _METRIC_HINTS), None)
    value_column = next((c for c, low in lowered.items() if low in _VALUE_HINTS), None)
    if not metric_column:
        metric_column = next((c for c, low in lowered.items() if "metric" in low or "指标" in low), None)
    if not value_column:
        value_column = next((c for c, low in lowered.items() if "value" in low or "值" in low), None)

    width_cols = {c for c in columns}
    matched = {c: c for c in metric_codes if c in width_cols}

    if metric_column and value_column and metric_column != time_column:
        layout = "long"
    else:
        layout = "wide"

    return {
        "layout": layout,
        "time_column": time_column,
        "granularity": "day",
        "metric_columns": matched,
        "metric_column": metric_column if layout == "long" else None,
        "value_column": value_column if layout == "long" else None,
        "dim_columns": [],
    }


# ------------------------------------------------------------------ 清洗
def _is_empty(raw: Any) -> bool:
    if raw is None:
        return True
    if isinstance(raw, float) and math.isnan(raw):
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return str(raw).strip().lower() in _EMPTY_TOKENS


def parse_number(raw: Any) -> Optional[float]:
    """数值清洗：去千分位 / 空格 / 货币符号，百分比去符号保留数值。"""
    if _is_empty(raw):
        return None
    if isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip().replace(",", "").replace("，", "").replace(" ", "")
    text = text.replace("¥", "").replace("￥", "").replace("$", "")
    text = text.rstrip("%")
    text = re.sub(r"[^\d.\-+eE]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_time(raw: Any, fmt: Optional[str] = None) -> Optional[datetime]:
    """时间清洗：支持日期字符串 / Excel 序列日期 / datetime。"""
    if _is_empty(raw):
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        # Excel 序列日期（1900 起算）
        if 20000 < float(raw) < 60000:
            return (datetime(1899, 12, 30) + pd.Timedelta(days=float(raw))).to_pydatetime()
        return None
    text = str(raw).strip()
    if fmt:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    ts = pd.to_datetime(text, errors="coerce")
    if ts is None or pd.isna(ts):
        return None
    return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts


# ------------------------------------------------------------------ 执行
def _resolve_metric(
    db: Session,
    tenant_id: int,
    code: str,
    mapping: IngestMapping,
    source_id: Optional[int],
    created_codes: list[str],
) -> Metric:
    metric = metric_service.get_metric(db, tenant_id, code)
    if metric is not None:
        return metric
    if not mapping.auto_create_metric:
        raise ValueError(f"指标不存在: {code}（可在映射中开启「自动创建指标」）")

    metric = Metric(
        tenant_id=tenant_id,
        code=code,
        name=code,
        description="由数据导入自动创建",
        metric_type="atomic",
        agg_func="sum",
        unit="",
        precision=2,
        granularity=mapping.granularity,
        source_id=source_id,
        status=mapping.auto_metric_status or "online",
        tags=["auto-imported"],
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    created_codes.append(code)
    return metric


def run_import(
    db: Session,
    tenant_id: int,
    file_name: str,
    mapping: IngestMapping,
    source_id: Optional[int] = None,
) -> ImportTask:
    """执行一次文件导入，返回落库的任务记录。"""
    started = time.perf_counter()
    path = safe_raw_path(file_name)

    task = ImportTask(
        tenant_id=tenant_id,
        source_id=source_id,
        file_name=path.name,
        file_path=str(path),
        file_size=path.stat().st_size if path.exists() else 0,
        file_hash=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "",
        layout=mapping.layout,
        granularity=mapping.granularity,
        status="running",
        mapping=mapping.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        frame = read_frame(path)
        task.total_rows = int(len(frame))
        if len(frame) > MAX_QUERY_ROWS:
            raise ValueError(f"文件行数超过上限 {MAX_QUERY_ROWS}")

        errors: list[dict[str, Any]] = []
        created_codes: list[str] = []
        metric_cache: dict[str, Metric] = {}
        success = failed = skipped = 0
        value_count = 0

        if mapping.time_column not in frame.columns:
            raise ValueError(f"时间列不存在: {mapping.time_column}")

        # ---------------- 宽表：一行多指标
        if mapping.layout == "wide":
            if not mapping.metric_columns:
                raise ValueError("宽表模式需至少配置一个「文件列 → 指标编码」映射")

            jobs: list[tuple[str, Metric]] = []
            for code, column in mapping.metric_columns.items():
                if column not in frame.columns:
                    raise ValueError(f"指标列不存在: {column}")
                jobs.append((column, _resolve_metric(db, tenant_id, code, mapping, source_id, created_codes)))

            for row_idx, row in enumerate(frame.to_dict(orient="records"), start=2):
                stat_time = parse_time(row.get(mapping.time_column), mapping.time_format)
                if stat_time is None:
                    failed += 1
                    if len(errors) < MAX_ERROR_DETAIL:
                        errors.append({"row": row_idx, "message": "时间列无法解析"})
                    continue
                row_written = 0
                row_skipped = 0
                for column, metric in jobs:
                    number = parse_number(row.get(column))
                    if number is None:
                        row_skipped += 1
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

        # ---------------- 长表：一行一指标
        else:
            if not mapping.metric_column or not mapping.value_column:
                raise ValueError("长表模式需配置「指标编码列」与「指标值列」")
            for column in (mapping.metric_column, mapping.value_column):
                if column not in frame.columns:
                    raise ValueError(f"列不存在: {column}")

            for row_idx, row in enumerate(frame.to_dict(orient="records"), start=2):
                code = str(row.get(mapping.metric_column) or "").strip()
                stat_time = parse_time(row.get(mapping.time_column), mapping.time_format)
                number = parse_number(row.get(mapping.value_column))
                if not code:
                    failed += 1
                    if len(errors) < MAX_ERROR_DETAIL:
                        errors.append({"row": row_idx, "message": "指标编码为空"})
                    continue
                if stat_time is None:
                    failed += 1
                    if len(errors) < MAX_ERROR_DETAIL:
                        errors.append({"row": row_idx, "message": "时间列无法解析"})
                    continue
                if number is None:
                    skipped += 1
                    continue
                dims = None
                if mapping.dim_columns:
                    dims = {
                        col: _jsonable(row.get(col))
                        for col in mapping.dim_columns
                        if col in frame.columns and not _is_empty(row.get(col))
                    } or None
                try:
                    metric = metric_cache.get(code)
                    if metric is None:
                        metric = _resolve_metric(
                            db, tenant_id, code, mapping, source_id, created_codes
                        )
                        metric_cache[code] = metric
                    metric_service.upsert_values(
                        db,
                        metric,
                        [
                            MetricValueIn(
                                stat_time=stat_time,
                                granularity=mapping.granularity,
                                dims=dims,
                                value=number,
                            )
                        ],
                    )
                    value_count += 1
                    success += 1
                except ValueError as exc:
                    failed += 1
                    if len(errors) < MAX_ERROR_DETAIL:
                        errors.append({"row": row_idx, "message": str(exc)})

        task.success_rows = success
        task.failed_rows = failed
        task.skipped_rows = skipped
        task.value_count = value_count
        task.metric_codes = (
            sorted(mapping.metric_columns.keys())
            if mapping.layout == "wide"
            else sorted(metric_cache.keys())
        )
        task.error_detail = errors or None
        if created_codes:
            task.metric_codes = sorted({*(task.metric_codes or []), *created_codes})
        if success == 0:
            task.status = "failed"
            task.error_msg = "没有任何数据行成功写入" + (
                f"；首个错误：{errors[0]['message']}" if errors else ""
            )
        elif failed > 0 or skipped > 0:
            task.status = "partial"
        else:
            task.status = "success"

    except Exception as exc:  # noqa: BLE001 - 任务型接口需要把失败落到记录里
        db.rollback()
        task = db.get(ImportTask, task.id)
        task.status = "failed"
        task.error_msg = f"{type(exc).__name__}: {exc}"

    task.elapsed_ms = int((time.perf_counter() - started) * 1000)
    task.finished_at = now_tz()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[int, list[ImportTask]]:
    """分页查询导入任务。"""
    base = select(ImportTask).where(ImportTask.tenant_id == tenant_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = (
        base.order_by(ImportTask.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return int(total), list(db.execute(stmt).scalars().all())
