"""M9 预测引擎服务：任务编排 / 结果落库 / 查询。

链路：端点 -> run_job（建任务）-> core.predictive.run_prediction（引擎路由，
规则兜底）-> 写 oc_prediction_result -> 更新任务状态。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.predictive import PredictiveEngineError, run_prediction
from app.models.predictive import (
    PREDICTION_BANDS,
    PREDICTION_MODES,
    PREDICTION_STATUSES,
    PREDICTION_TARGETS,
    PredictionJob,
    PredictionResult,
)
from app.schemas.predictive import PredictionBatchIn, PredictionRunIn

DEFAULT_THRESHOLD = 0.5


class PredictiveServiceError(RuntimeError):
    """预测服务业务异常（参数 / 状态非法）。"""


def _now() -> datetime:
    return datetime.now()


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validate_target(target: str) -> None:
    if target not in PREDICTION_TARGETS:
        raise PredictiveServiceError(
            f"不支持的预测目标: {target}（可选 {' / '.join(PREDICTION_TARGETS)}）"
        )


def _validate_mode(mode: str) -> None:
    if mode not in PREDICTION_MODES:
        raise PredictiveServiceError(
            f"不支持的模型路由模式: {mode}（可选 {' / '.join(PREDICTION_MODES)}）"
        )


def _subject_entries(payload: PredictionRunIn) -> list[dict[str, Any]]:
    """run 模式主体展开：subject_keys 与 features 顶层键互为补充。"""
    feats = payload.features or {}
    keys = list(payload.subject_keys or [])
    if not keys:
        # features 为 {subject_key: {特征...}} 时，用其顶层键作为主体键
        keys = [k for k, v in feats.items() if isinstance(v, dict)]
    if not keys:
        keys = ["default"]
    entries: list[dict[str, Any]] = []
    for key in keys:
        f = feats.get(key) if isinstance(feats.get(key), dict) else feats
        entries.append({"key": key, "name": key, "features": f or {}})
    return entries


def _batch_entries(payload: PredictionBatchIn) -> list[dict[str, Any]]:
    """batch 模式主体：直接使用 subjects 列表。"""
    entries: list[dict[str, Any]] = []
    for i, subject in enumerate(payload.subjects or []):
        entries.append(
            {
                "key": subject.get("key") or f"subject_{i + 1}",
                "name": subject.get("name"),
                "features": subject.get("features") or {},
            }
        )
    return entries


def run_job(
    db: Session,
    tenant_id: int,
    payload: PredictionRunIn | PredictionBatchIn,
    operator: str = "system",
) -> dict[str, Any]:
    """创建并执行一次预测任务，返回任务字典（含结果摘要）。"""
    _validate_target(payload.target)
    _validate_mode(payload.mode)

    entries = _batch_entries(payload) if isinstance(payload, PredictionBatchIn) else _subject_entries(payload)
    if not entries:
        raise PredictiveServiceError("预测主体列表为空")

    threshold = payload.threshold if payload.threshold is not None else DEFAULT_THRESHOLD
    job = PredictionJob(
        tenant_id=tenant_id,
        name=getattr(payload, "name", None) or f"{payload.target} 预测",
        target=payload.target,
        status="running",
        mode=payload.mode,
        source=payload.source if isinstance(payload, PredictionRunIn) else "batch",
        input_snapshot=payload.model_dump(mode="json"),
        feature_count=0,
        subject_count=len(entries),
        threshold=threshold,
        rule_fallback_used=False,
        created_by=operator,
    )
    db.add(job)
    db.flush()

    try:
        outcome = run_prediction(
            tenant_id=tenant_id,
            target=payload.target,
            subjects=entries,
            features=payload.features if isinstance(payload, PredictionRunIn) else None,
            mode=payload.mode,
            threshold=float(threshold),
            rule_fallback=payload.rule_fallback,
        )
    except (PredictiveEngineError, PredictiveServiceError) as exc:
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = _now()
        db.commit()
        return job_to_dict(job, results=[])

    # 主体键去重后落库（唯一约束 job_id + subject_key）
    seen: set[str] = set()
    rows: list[PredictionResult] = []
    for p in outcome.predictions:
        if p.subject_key in seen:
            continue
        seen.add(p.subject_key)
        rows.append(
            PredictionResult(
                tenant_id=tenant_id,
                job_id=job.id,
                target=payload.target,
                subject_key=p.subject_key,
                subject_name=p.subject_name,
                probability=p.probability,
                band=p.band,
                mode=p.mode,
                model=p.model,
                confidence=p.confidence,
                features=p.features,
                reasons=p.reasons,
            )
        )
    db.add_all(rows)

    # 特征数：取首个主体的特征数（或主体平均）
    feature_count = 0
    for p in outcome.predictions:
        feature_count = max(feature_count, len(p.features or {}))
    job.feature_count = feature_count
    job.subject_count = len(rows)
    job.model = outcome.model_used
    job.mode = outcome.mode_used
    job.rule_fallback_used = outcome.rule_fallback
    job.status = "success"
    job.finished_at = _now()
    db.commit()

    return job_to_dict(job, results=[result_to_dict(r) for r in rows])


def list_jobs(
    db: Session,
    tenant_id: int,
    *,
    keyword: Optional[str] = None,
    target: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    if target is not None:
        _validate_target(target)
    if status is not None and status not in PREDICTION_STATUSES:
        raise PredictiveServiceError(
            f"不支持的预测任务状态: {status}（可选 {' / '.join(PREDICTION_STATUSES)}）"
        )
    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    conditions = [PredictionJob.tenant_id == tenant_id]
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(PredictionJob.name.like(like), PredictionJob.created_by.like(like))
        )
    if target:
        conditions.append(PredictionJob.target == target)
    if status:
        conditions.append(PredictionJob.status == status)

    total = db.scalar(select(func.count()).select_from(PredictionJob).where(*conditions)) or 0
    rows = (
        db.execute(
            select(PredictionJob)
            .where(*conditions)
            .order_by(PredictionJob.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "page": page,
        "page_size": size,
        "items": [job_to_dict(j) for j in rows],
    }


def get_job(db: Session, tenant_id: int, job_id: int) -> Optional[dict[str, Any]]:
    job = db.scalar(
        select(PredictionJob).where(
            PredictionJob.id == job_id, PredictionJob.tenant_id == tenant_id
        )
    )
    if job is None:
        return None
    results = (
        db.execute(
            select(PredictionResult)
            .where(PredictionResult.job_id == job.id)
            .order_by(PredictionResult.probability.desc(), PredictionResult.id.asc())
        )
        .scalars()
        .all()
    )
    return job_to_dict(job, results=[result_to_dict(r) for r in results])


def job_to_dict(job: PredictionJob, results: Optional[list[dict]] = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "name": job.name,
        "target": job.target,
        "status": job.status,
        "mode": job.mode,
        "model": job.model,
        "source": job.source,
        "feature_count": job.feature_count,
        "subject_count": job.subject_count,
        "threshold": _f(job.threshold) if job.threshold is not None else None,
        "rule_fallback_used": bool(job.rule_fallback_used),
        "error": job.error,
        "created_by": job.created_by,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
    if results is not None:
        data["results"] = results
    return data


def result_to_dict(row: PredictionResult) -> dict[str, Any]:
    return {
        "id": row.id,
        "job_id": row.job_id,
        "target": row.target,
        "subject_key": row.subject_key,
        "subject_name": row.subject_name,
        "probability": _f(row.probability),
        "band": row.band,
        "mode": row.mode,
        "model": row.model,
        "confidence": _f(row.confidence) if row.confidence is not None else None,
        "features": row.features,
        "reasons": row.reasons,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
