"""语义层编排服务：Text2Metric 全链路（意图 → 编译 → 执行 → 响应）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.metric import Metric
from app.semantic import compiler, executor, intent
from app.services import metric_service

logger = logging.getLogger(__name__)


def _metric_catalog(db: Session, tenant_id: int) -> list[dict[str, Any]]:
    metrics = (
        db.query(Metric)
        .filter(Metric.status == "online", Metric.tenant_id == tenant_id)
        .order_by(Metric.id.asc())
        .limit(200)
        .all()
    )
    from app.models.metric import MetricDimension

    dims_by_metric: dict[int, list[str]] = {}
    for d in (
        db.query(MetricDimension)
        .filter(MetricDimension.tenant_id == tenant_id)
        .all()
    ):
        dims_by_metric.setdefault(d.metric_id, []).append(d.code)
    return [
        {
            "code": m.code,
            "name": m.name,
            "agg_func": m.agg_func,
            "formula": m.formula,
            "source_id": m.source_id,
            "granularity": m.granularity,
            "dimensions": dims_by_metric.get(m.id) or [],
            "tags": [m.code, m.name] + [str(x) for x in (dims_by_metric.get(m.id) or [])],
        }
        for m in metrics
    ]


def _dim_dict(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    dims: list[dict[str, Any]] = []
    for item in catalog:
        for d in item.get("dimensions") or []:
            if d and d not in seen:
                seen.add(d)
                dims.append({"code": d, "name": d})
    return dims


def _fmt_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(sep=" ") if dt is not None else None


def ask(
    db: Session,
    tenant_id: int,
    question: str,
    limit: int = 200,
) -> dict[str, Any]:
    """Text2Metric 主入口：返回结构化问答结果。"""
    catalog = _metric_catalog(db, tenant_id)
    if not catalog:
        return {
            "question": question,
            "ok": False,
            "error": "指标中心暂无启用指标，请先登记指标",
            "metrics": [],
        }

    intent_result = intent.extract_intent(db, tenant_id, question, catalog, _dim_dict(catalog))
    metrics_by_code = {m["code"]: m for m in catalog}
    compiled_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for code in intent_result.metric_codes:
        meta = metrics_by_code.get(code)
        metric = (
            db.query(Metric)
            .filter(
                Metric.code == code,
                Metric.status == "online",
                Metric.tenant_id == tenant_id,
            )
            .first()
        )
        if metric is None:
            errors.append(f"指标 {code} 不存在或已停用")
            continue
        try:
            compiled = compiler.compile_for_metric(
                db,
                metric,
                tenant_id=tenant_id,
                granularity=intent_result.granularity,
                start=intent_result.start,
                end=intent_result.end,
                dims_filter=intent_result.dims_filter,
            )
        except compiler.SemanticCompileError as exc:
            db.rollback()
            errors.append(f"{code}: 编译失败 - {exc}")
            continue
        try:
            result = executor.execute(
                db,
                metric,
                compiled,
                granularity=intent_result.granularity,
                start=intent_result.start,
                end=intent_result.end,
                dims_filter=intent_result.dims_filter,
                limit=limit,
            )
        except executor.SemanticExecError as exc:
            db.rollback()
            errors.append(f"{code}: 执行失败 - {exc}")
            continue
        compiled_rows.append(
            {
                "code": code,
                "name": meta["name"],
                "agg_func": meta["agg_func"],
                "unit": metric.unit or "",
                "precision": metric.precision,
                "source_label": result.source_label,
                "dialect": result.dialect,
                "execution_ms": result.execution_ms,
                "fallback_reason": result.fallback_reason,
                "columns": result.columns,
                "rows": result.rows,
            }
        )

    return {
        "question": question,
        "ok": bool(compiled_rows),
        "intent": {
            "metric_codes": intent_result.metric_codes,
            "granularity": intent_result.granularity,
            "start": _fmt_dt(intent_result.start),
            "end": _fmt_dt(intent_result.end),
            "dims_filter": intent_result.dims_filter,
            "reason": intent_result.reason,
            "model": intent_result.model,
            "mode": intent_result.mode,
            "fallback": intent_result.fallback,
        },
        "metrics": compiled_rows,
        "errors": errors,
    }
