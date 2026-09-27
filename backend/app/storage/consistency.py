"""跨存储数据一致性对账。

覆盖范围：
- metric_ts    ：关系型指标值 oc_metric_value ⟷ 时序分区表 oc_ts_metric_point
- search_index ：源表 oc_metric / oc_data_source ⟷ 全文索引 oc_doc_index
- files        ：导入任务登记的原始文件 ⟷ 受管文件目录（存在性与 sha256）

自动修复能力（auto_repair=True）：
- metric_ts    ：缺失/不一致的聚合组按源表明细回写时序表
- search_index ：缺失的索引条目重建；源记录已删除的脏索引条目安全清理（pruned）
- files        ：不自动修复（不擅自改写/重建用户原始文件）

对账结论：passed 一致 / warning 存在差异未修复 / failed 差异且修复失败 / skipped 前置条件不满足。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import bindparam, text

from app.core.config import settings
from app.models.storage import ConsistencyCheck
from app.storage.timeseries import timeseries_adapter

logger = logging.getLogger(__name__)

SCOPES = ("metric_ts", "search_index", "files")
VALUE_EPS = Decimal("0.000001")


# ------------------------------------------------------------ 明细查询
def _value_groups(db, table: str, tenant_id: int, start=None, end=None) -> dict[tuple, dict]:
    conditions = ["tenant_id = :tid"]
    params: dict[str, Any] = {"tid": tenant_id}
    if start is not None:
        conditions.append("stat_time >= :start")
        params["start"] = start
    if end is not None:
        conditions.append("stat_time <= :end")
        params["end"] = end
    sql = text(
        f"SELECT metric_id, granularity, coalesce(dims_hash, '') AS dims_hash,"
        f" count(*) AS cnt, coalesce(sum(value), 0) AS total"
        f" FROM {table} WHERE {' AND '.join(conditions)} GROUP BY 1, 2, 3"
    )
    groups: dict[tuple, dict] = {}
    for row in db.execute(sql, params).all():
        key = (int(row.metric_id), row.granularity or "", row.dims_hash or "")
        groups[key] = {"cnt": int(row.cnt), "total": Decimal(row.total or 0)}
    return groups


def _load_source_values(db, tenant_id: int, key: tuple, start=None, end=None) -> list[dict]:
    """按聚合键拉取源表明细（用于修复时序表）。"""
    metric_id, granularity, dims_hash = key
    conditions = [
        "v.metric_id = :metric_id",
        "v.granularity = :granularity",
        "coalesce(v.dims_hash, '') = :dims_hash",
        "v.tenant_id = :tid",
    ]
    params: dict[str, Any] = {
        "metric_id": metric_id,
        "granularity": granularity,
        "dims_hash": dims_hash,
        "tid": tenant_id,
    }
    if start is not None:
        conditions.append("v.stat_time >= :start")
        params["start"] = start
    if end is not None:
        conditions.append("v.stat_time <= :end")
        params["end"] = end
    sql = text(
        "SELECT v.tenant_id, v.metric_id, m.code AS metric_code, v.stat_time, v.granularity,"
        " v.dims, coalesce(v.dims_hash, '') AS dims_hash, v.value, m.source_id"
        f" FROM oc_metric_value v JOIN oc_metric m ON m.id = v.metric_id"
        f" WHERE {' AND '.join(conditions)}"
    )
    return [dict(r._mapping) for r in db.execute(sql, params).all()]


# ------------------------------------------------------------ 指标值对账
def reconcile_metric_values(
    db,
    tenant_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    auto_repair: bool = False,
    sample_limit: Optional[int] = None,
) -> dict:
    """关系型指标值 ⟷ 时序分区表 对账（支持自动修复）。"""
    sample_limit = sample_limit or settings.STORAGE_CONSISTENCY_SAMPLE_LIMIT
    source = _value_groups(db, "oc_metric_value", tenant_id, start, end)
    target = _value_groups(db, "oc_ts_metric_point", tenant_id, start, end)

    missing_keys = [k for k in source if k not in target]
    extra_keys = [k for k in target if k not in source]
    mismatch_keys = [
        k
        for k in source
        if k in target
        and (
            source[k]["cnt"] != target[k]["cnt"]
            or abs(source[k]["total"] - target[k]["total"]) > VALUE_EPS
        )
    ]

    repaired = 0
    repair_errors: list[str] = []
    if auto_repair and (missing_keys or mismatch_keys):
        for key in missing_keys + mismatch_keys:
            try:
                rows = _load_source_values(db, tenant_id, key, start, end)
                if rows:
                    repaired += timeseries_adapter.write_points(db, rows, auto_partition=True)
            except Exception as exc:  # pragma: no cover
                db.rollback()
                repair_errors.append(f"{key}: {type(exc).__name__}: {exc}"[:255])
        if repaired:
            target = _value_groups(db, "oc_ts_metric_point", tenant_id, start, end)
            missing_keys = [k for k in source if k not in target]
            mismatch_keys = [
                k
                for k in source
                if k in target
                and (
                    source[k]["cnt"] != target[k]["cnt"]
                    or abs(source[k]["total"] - target[k]["total"]) > VALUE_EPS
                )
            ]

    diff_count = len(missing_keys) + len(extra_keys) + len(mismatch_keys)
    if diff_count == 0:
        status = "passed"
    elif auto_repair and not repair_errors and repaired:
        status = "passed" if not missing_keys and not mismatch_keys else "warning"
    else:
        status = "warning" if repaired or extra_keys else "failed"
    if repair_errors and not repaired:
        status = "failed"

    return {
        "scope": "metric_ts",
        "status": status,
        "checked": len(source),
        "matched": len(source) - len(missing_keys) - len(mismatch_keys),
        "missing": len(missing_keys),
        "extra": len(extra_keys),
        "mismatched": len(mismatch_keys),
        "repaired": repaired,
        "auto_repair": auto_repair,
        "samples": {
            "missing": [_fmt_key(k) for k in missing_keys[:sample_limit]],
            "extra": [_fmt_key(k) for k in extra_keys[:sample_limit]],
            "mismatched": [
                {
                    "key": _fmt_key(k),
                    "source": {"cnt": source[k]["cnt"], "total": float(source[k]["total"])},
                    "target": {"cnt": target[k]["cnt"], "total": float(target[k]["total"])},
                }
                for k in mismatch_keys[:sample_limit]
            ],
        },
        "errors": repair_errors[:sample_limit],
        "detail": {
            "source_table": "oc_metric_value",
            "target_table": "oc_ts_metric_point",
            "source_groups": len(source),
            "target_groups": len(target),
        },
    }


def _fmt_key(key: tuple) -> dict:
    metric_id, granularity, dims_hash = key
    return {
        "metric_id": metric_id,
        "granularity": granularity,
        "dims_hash": (dims_hash or "")[:12],
    }


# ------------------------------------------------------------ 检索索引对账
def reconcile_search_index(db, tenant_id: int, auto_repair: bool = False) -> dict:
    """源表记录 ⟷ 全文索引 对账。"""
    metric_total, datasource_total = 0, 0
    try:
        metric_ids = {
            str(r[0])
            for r in db.execute(
                text("SELECT id FROM oc_metric WHERE tenant_id = :t"), {"t": tenant_id}
            ).all()
        }
        datasource_ids = {
            str(r[0])
            for r in db.execute(
                text("SELECT id FROM oc_data_source WHERE tenant_id = :t"), {"t": tenant_id}
            ).all()
        }
        metric_total, datasource_total = len(metric_ids), len(datasource_ids)
        rows = db.execute(
            text(
                "SELECT doc_type, doc_id FROM oc_doc_index WHERE tenant_id = :t AND doc_type IN ('metric','datasource')"
            ),
            {"t": tenant_id},
        ).all()
        indexed_map: dict[str, set[str]] = {"metric": set(), "datasource": set()}
        for r in rows:
            indexed_map.setdefault(r[0], set()).add(str(r[1]))
    except Exception as exc:
        db.rollback()
        return {
            "scope": "search_index",
            "status": "skipped",
            "checked": 0,
            "matched": 0,
            "missing": 0,
            "extra": 0,
            "mismatched": 0,
            "repaired": 0,
            "auto_repair": auto_repair,
            "samples": {},
            "errors": [f"{type(exc).__name__}: {exc}"[:255]],
            "detail": {},
        }

    missing_metrics = sorted(metric_ids - indexed_map.get("metric", set()))
    missing_datasources = sorted(datasource_ids - indexed_map.get("datasource", set()))
    extra_metrics = sorted(indexed_map.get("metric", set()) - metric_ids)
    extra_datasources = sorted(indexed_map.get("datasource", set()) - datasource_ids)
    missing = len(missing_metrics) + len(missing_datasources)
    extra = len(extra_metrics) + len(extra_datasources)

    repaired = 0
    pruned = 0
    errors: list[str] = []
    if auto_repair and missing:
        try:
            from app.storage.registry import reindex_documents

            result = reindex_documents(db, tenant_id=tenant_id, scope=["metric", "datasource"])
            repaired = int(result.get("indexed", 0))
            rows = db.execute(
                text(
                    "SELECT doc_type, doc_id FROM oc_doc_index WHERE tenant_id = :t AND doc_type IN ('metric','datasource')"
                ),
                {"t": tenant_id},
            ).all()
            indexed_map = {"metric": set(), "datasource": set()}
            for r in rows:
                indexed_map.setdefault(r[0], set()).add(str(r[1]))
            missing_metrics = sorted(metric_ids - indexed_map.get("metric", set()))
            missing_datasources = sorted(datasource_ids - indexed_map.get("datasource", set()))
            missing = len(missing_metrics) + len(missing_datasources)
        except Exception as exc:  # pragma: no cover
            db.rollback()
            errors.append(f"{type(exc).__name__}: {exc}"[:255])

    # 索引是「源表的派生结构」，源记录已删除时其索引条目即为脏数据，可安全清理
    if auto_repair and (extra_metrics or extra_datasources):
        try:
            delete_stmt = text(
                "DELETE FROM oc_doc_index"
                " WHERE tenant_id = :t AND doc_type = :dt AND doc_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True))
            for doc_type, stale_ids in (("metric", extra_metrics), ("datasource", extra_datasources)):
                if not stale_ids:
                    continue
                pruned += (
                    db.execute(
                        delete_stmt, {"t": tenant_id, "dt": doc_type, "ids": list(stale_ids)}
                    ).rowcount
                    or 0
                )
            db.commit()
            stale_rows = db.execute(
                text(
                    "SELECT doc_type, doc_id FROM oc_doc_index WHERE tenant_id = :t AND doc_type IN ('metric','datasource')"
                ),
                {"t": tenant_id},
            ).all()
            indexed_map = {"metric": set(), "datasource": set()}
            for r in stale_rows:
                indexed_map.setdefault(r[0], set()).add(str(r[1]))
            extra_metrics = sorted(indexed_map.get("metric", set()) - metric_ids)
            extra_datasources = sorted(indexed_map.get("datasource", set()) - datasource_ids)
            extra = len(extra_metrics) + len(extra_datasources)
        except Exception as exc:  # pragma: no cover
            db.rollback()
            errors.append(f"{type(exc).__name__}: {exc}"[:255])

    checked = metric_total + datasource_total
    matched = checked - missing
    if errors and not repaired and not pruned:
        status = "failed"
    elif missing == 0 and extra == 0:
        status = "passed"
    else:
        status = "warning"

    sample_limit = settings.STORAGE_CONSISTENCY_SAMPLE_LIMIT
    return {
        "scope": "search_index",
        "status": status,
        "checked": checked,
        "matched": matched,
        "missing": missing,
        "extra": extra,
        "mismatched": 0,
        "repaired": repaired,
        "pruned": pruned,
        "auto_repair": auto_repair,
        "samples": {
            "missing_metric_ids": missing_metrics[:sample_limit],
            "missing_datasource_ids": missing_datasources[:sample_limit],
            "extra_metric_ids": extra_metrics[:sample_limit],
            "extra_datasource_ids": extra_datasources[:sample_limit],
        },
        "errors": errors,
        "detail": {
            "source_tables": ["oc_metric", "oc_data_source"],
            "target_table": "oc_doc_index",
            "source_counts": {"metric": metric_total, "datasource": datasource_total},
        },
    }


# ------------------------------------------------------------ 文件对账
def reconcile_files(db, tenant_id: int, auto_repair: bool = False) -> dict:
    """导入任务登记文件 ⟷ 受管目录文件 对账（存在性 + sha256）。"""
    from app.storage.files import file_adapter

    try:
        rows = db.execute(
            text(
                "SELECT id, file_name, file_path, file_hash FROM oc_import_task"
                " WHERE tenant_id = :t ORDER BY id DESC LIMIT 500"
            ),
            {"t": tenant_id},
        ).all()
    except Exception as exc:
        db.rollback()
        return {
            "scope": "files",
            "status": "skipped",
            "checked": 0,
            "matched": 0,
            "missing": 0,
            "extra": 0,
            "mismatched": 0,
            "repaired": 0,
            "auto_repair": auto_repair,
            "samples": {},
            "errors": [f"{type(exc).__name__}: {exc}"[:255]],
            "detail": {},
        }

    from pathlib import Path

    missing, mismatched, matched = [], [], 0
    for r in rows:
        path = Path(r.file_path) if r.file_path else None
        if path is None or not path.is_absolute():
            try:
                path = file_adapter.resolve(str(r.file_path or ""))
            except Exception:
                path = None
        if path is None or not path.exists() or not path.is_file():
            missing.append({"task_id": r.id, "file_name": r.file_name, "path": r.file_path})
            continue
        actual = file_adapter.hash_file(path)
        if r.file_hash and actual and r.file_hash != actual:
            mismatched.append(
                {"task_id": r.id, "file_name": r.file_name, "expected": r.file_hash, "actual": actual}
            )
        else:
            matched += 1

    sample_limit = settings.STORAGE_CONSISTENCY_SAMPLE_LIMIT
    checked = len(rows)
    if not missing and not mismatched:
        status = "passed"
    elif missing:
        status = "warning"
    else:
        status = "warning"
    return {
        "scope": "files",
        "status": status,
        "checked": checked,
        "matched": matched,
        "missing": len(missing),
        "extra": 0,
        "mismatched": len(mismatched),
        "repaired": 0,
        "auto_repair": False,
        "samples": {
            "missing": missing[:sample_limit],
            "mismatched": mismatched[:sample_limit],
        },
        "errors": [],
        "detail": {
            "managed_raw": file_adapter.cleanup_candidates("raw"),
            "note": "文件类差异不自动修复（不擅自改写/重建用户原始文件）",
        },
    }


# ------------------------------------------------------------ 编排
def run_checks(
    db,
    tenant_id: int,
    scopes: Optional[list[str]] = None,
    auto_repair: bool = False,
    operator: Optional[str] = None,
    persist: bool = True,
) -> dict:
    """执行一致性对账，按 scope 落库记录并返回汇总。"""
    selected = [s for s in (scopes or list(SCOPES)) if s in SCOPES] or list(SCOPES)
    started = time.time()
    results: list[dict] = []

    for scope in selected:
        if scope == "metric_ts":
            result = reconcile_metric_values(db, tenant_id, auto_repair=auto_repair)
        elif scope == "search_index":
            result = reconcile_search_index(db, tenant_id, auto_repair=auto_repair)
        else:
            result = reconcile_files(db, tenant_id, auto_repair=False)
        results.append(result)
        if persist:
            _persist(db, tenant_id, result, operator)

    statuses = [r["status"] for r in results]
    overall = "passed"
    if any(s == "failed" for s in statuses):
        overall = "failed"
    elif any(s == "warning" for s in statuses):
        overall = "warning"
    elif all(s == "skipped" for s in statuses):
        overall = "skipped"

    return {
        "overall": overall,
        "scopes": selected,
        "auto_repair": auto_repair,
        "elapsed_ms": int((time.time() - started) * 1000),
        "checked": sum(r["checked"] for r in results),
        "matched": sum(r["matched"] for r in results),
        "repaired": sum(r["repaired"] for r in results),
        "pruned": sum(r.get("pruned", 0) for r in results),
        "results": results,
    }


def _persist(db, tenant_id: int, result: dict, operator: Optional[str]) -> None:
    try:
        db.add(
            ConsistencyCheck(
                tenant_id=tenant_id,
                scope=result["scope"],
                status=result["status"],
                checked=result["checked"],
                matched=result["matched"],
                missing=result["missing"],
                extra=result["extra"],
                mismatched=result["mismatched"],
                repaired=result["repaired"],
                auto_repair=bool(result.get("auto_repair")),
                elapsed_ms=0,
                report={k: v for k, v in result.items() if k not in ("errors",)} | {"errors": result.get("errors", [])[:5]},
                operator=operator,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover
        db.rollback()
        logger.warning("一致性对账记录落库失败：%s", exc)


def recent_checks(db, tenant_id: int, limit: int = 10) -> list[dict]:
    """最近对账记录。"""
    rows = (
        db.query(ConsistencyCheck)
        .filter(ConsistencyCheck.tenant_id == tenant_id)
        .order_by(ConsistencyCheck.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "scope": r.scope,
            "status": r.status,
            "checked": r.checked,
            "matched": r.matched,
            "missing": r.missing,
            "extra": r.extra,
            "mismatched": r.mismatched,
            "repaired": r.repaired,
            "auto_repair": r.auto_repair,
            "operator": r.operator,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        }
        for r in rows
    ]
