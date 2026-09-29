"""采集调度 API 路由：采集任务管理、手动执行、调度启停与运行记录。

能力边界（与前端展示口径一致）：
- csv / api 两种采集方式真实执行并真实写入指标值；
- sql 方式：PostgreSQL / MySQL 已直连真实拉取并落库（运行记录 simulated=false）；
  ClickHouse / Hive 驱动未接入，仅做 TCP 连通性探测（simulated=true）；
- 内置调度线程默认启用，可用 COLLECT_SCHEDULER_ENABLED=0 关闭。
"""

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.models import CollectRun, CollectTask, DataSource
from app.models.base import get_db
from app.schemas.collect import (
    CollectModeOut,
    CollectOverviewOut,
    CollectRunOut,
    CollectSourceOut,
    CollectTaskIn,
    CollectTaskOut,
    CollectTaskUpdateIn,
    CollectTrendPoint,
)
from app.schemas.common import ApiResponse, PageResult
from app.services import collect_service
from app.utils.datetime_util import now as now_tz

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collect", tags=["采集调度"])


# ---------------------------------------------------------------- 序列化辅助


def _task_out(db: Session, task: CollectTask, source_names: dict[int, tuple[str, str]]) -> CollectTaskOut:
    out = CollectTaskOut.model_validate(task)
    if task.source_id and task.source_id in source_names:
        name, ds_type = source_names[task.source_id]
        out.source_name = name
        out.source_type = ds_type
    return out


def _run_out(run: CollectRun, task_names: dict[int, str]) -> CollectRunOut:
    out = CollectRunOut.model_validate(run)
    out.task_name = task_names.get(run.task_id, "")
    return out


def _source_names(db: Session, tenant_id: int) -> dict[int, tuple[str, str]]:
    rows = db.execute(select(DataSource).where(DataSource.tenant_id == tenant_id)).scalars().all()
    return {row.id: (row.name, row.ds_type) for row in rows}


def _get_task(db: Session, tenant_id: int, task_id: int) -> CollectTask:
    task = db.execute(
        select(CollectTask).where(
            CollectTask.id == task_id, CollectTask.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="采集任务不存在")
    return task


# ---------------------------------------------------------------- 目录与总览


@router.get("/modes", response_model=ApiResponse[list[CollectModeOut]])
def list_modes() -> ApiResponse[list[CollectModeOut]]:
    """采集方式目录：三种方式的能力与目标格式说明。"""
    return ApiResponse(
        data=[CollectModeOut(**item) for item in collect_service.COLLECT_MODE_CATALOG]
    )


@router.get("/sources", response_model=ApiResponse[list[CollectSourceOut]])
def list_sources(
    db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)
) -> ApiResponse[list[CollectSourceOut]]:
    """可绑定的数据源下拉项。"""
    rows = (
        db.execute(select(DataSource).where(DataSource.tenant_id == tenant_id).order_by(DataSource.id))
        .scalars()
        .all()
    )
    return ApiResponse(
        data=[
            CollectSourceOut(
                id=row.id, code=row.code, name=row.name, ds_type=row.ds_type, status=row.status
            )
            for row in rows
        ]
    )


@router.get("/overview", response_model=ApiResponse[CollectOverviewOut])
def overview(
    db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)
) -> ApiResponse[CollectOverviewOut]:
    """采集调度总览：任务态势、近 24 小时运行质量、执行趋势与最近记录。"""
    now = now_tz()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=6)

    stats = collect_service.task_stats(db, tenant_id)
    scheduled = (
        db.execute(
            select(func.count()).select_from(CollectTask).where(
                CollectTask.tenant_id == tenant_id,
                CollectTask.status == "enabled",
                CollectTask.schedule_type == "interval",
            )
        ).scalar()
        or 0
    )
    due = (
        db.execute(
            select(func.count()).select_from(CollectTask).where(
                CollectTask.tenant_id == tenant_id,
                CollectTask.status == "enabled",
                CollectTask.schedule_type == "interval",
                CollectTask.next_run_at.is_not(None),
                CollectTask.next_run_at <= now,
            )
        ).scalar()
        or 0
    )

    total_runs = (
        db.execute(
            select(func.count()).select_from(CollectRun).where(CollectRun.tenant_id == tenant_id)
        ).scalar()
        or 0
    )
    run_rows = db.execute(
        select(CollectRun.status, func.count(), func.coalesce(func.sum(CollectRun.rows_written), 0), func.coalesce(func.avg(CollectRun.duration_ms), 0))
        .where(CollectRun.tenant_id == tenant_id, CollectRun.started_at >= since_24h)
        .group_by(CollectRun.status)
    ).all()
    runs_24h = sum(int(row[1]) for row in run_rows)
    success_24h = sum(int(row[1]) for row in run_rows if row[0] in {"success", "partial"})
    failed_24h = sum(int(row[1]) for row in run_rows if row[0] == "failed")
    rows_written_24h = sum(int(row[2]) for row in run_rows)
    durations = [float(row[3]) for row in run_rows if row[3]]
    avg_duration = int(sum(durations) / len(durations)) if durations else 0
    total_rows_written = (
        db.execute(
            select(func.coalesce(func.sum(CollectRun.rows_written), 0)).where(
                CollectRun.tenant_id == tenant_id
            )
        ).scalar()
        or 0
    )

    trend_rows = db.execute(
        select(
            func.date(CollectRun.started_at),
            func.count(),
            func.count().filter(CollectRun.status.in_(["success", "partial"])),
            func.count().filter(CollectRun.status == "failed"),
        )
        .where(CollectRun.tenant_id == tenant_id, CollectRun.started_at >= since_7d)
        .group_by(func.date(CollectRun.started_at))
        .order_by(func.date(CollectRun.started_at))
    ).all()
    trend_map = {
        str(row[0]): (int(row[1]), int(row[2]), int(row[3])) for row in trend_rows
    }
    trend: list[CollectTrendPoint] = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        total, success, failed = trend_map.get(day, (0, 0, 0))
        trend.append(CollectTrendPoint(day=day, total=total, success=success, failed=failed))

    recent = (
        db.execute(
            select(CollectRun)
            .where(CollectRun.tenant_id == tenant_id)
            .order_by(CollectRun.started_at.desc(), CollectRun.id.desc())
            .limit(8)
        )
        .scalars()
        .all()
    )
    names = {
        task.id: task.name
        for task in db.execute(
            select(CollectTask).where(CollectTask.tenant_id == tenant_id)
        ).scalars()
    }

    return ApiResponse(
        data=CollectOverviewOut(
            total_tasks=stats["total"],
            enabled_tasks=stats["status"].get("enabled", 0),
            paused_tasks=stats["status"].get("paused", 0),
            scheduled_tasks=int(scheduled),
            due_tasks=int(due),
            total_runs=int(total_runs),
            runs_24h=runs_24h,
            success_24h=success_24h,
            failed_24h=failed_24h,
            success_rate_24h=round(success_24h / runs_24h * 100, 1) if runs_24h else 0.0,
            rows_written_24h=rows_written_24h,
            total_rows_written=int(total_rows_written),
            avg_duration_ms=avg_duration,
            mode_distribution=stats["mode"],
            status_distribution=stats["status"],
            trend=trend,
            recent_runs=[_run_out(run, names) for run in recent],
            scheduler_enabled=collect_service.scheduler_enabled(),
        )
    )


# ---------------------------------------------------------------- 任务 CRUD


@router.get("/tasks", response_model=ApiResponse[PageResult[CollectTaskOut]])
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(None, description="enabled/paused"),
    collect_mode: Optional[str] = Query(None, description="csv/api/sql"),
    keyword: Optional[str] = Query(None, max_length=64),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[CollectTaskOut]]:
    """采集任务列表（支持状态 / 方式 / 关键词筛选）。"""
    conditions = [CollectTask.tenant_id == tenant_id]
    if status:
        conditions.append(CollectTask.status == status)
    if collect_mode:
        conditions.append(CollectTask.collect_mode == collect_mode)
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(or_(CollectTask.code.ilike(like), CollectTask.name.ilike(like)))

    total = (
        db.execute(select(func.count()).select_from(CollectTask).where(*conditions)).scalar() or 0
    )
    rows = (
        db.execute(
            select(CollectTask)
            .where(*conditions)
            .order_by(CollectTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    names = _source_names(db, tenant_id)
    return ApiResponse(
        data=PageResult[CollectTaskOut](
            total=int(total),
            page=page,
            page_size=page_size,
            items=[_task_out(db, task, names) for task in rows],
        )
    )


@router.post("/tasks", response_model=ApiResponse[CollectTaskOut])
def create_task(
    payload: CollectTaskIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CollectTaskOut]:
    """新建采集任务（interval 模式自动排期下次执行时间）。"""
    if payload.source_id:
        source = db.execute(
            select(DataSource).where(
                DataSource.id == payload.source_id, DataSource.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if source is None:
            raise HTTPException(status_code=400, detail="关联数据源不存在")

    task = CollectTask(
        tenant_id=tenant_id,
        code=payload.code,
        name=payload.name,
        source_id=payload.source_id,
        collect_mode=payload.collect_mode,
        target=payload.target,
        mapping=payload.mapping.model_dump() if payload.mapping else None,
        extra_config=payload.extra_config or {},
        schedule_type=payload.schedule_type,
        interval_minutes=payload.interval_minutes,
        cron_expr=payload.cron_expr,
        status=payload.status,
        remark=payload.remark,
    )
    task.next_run_at = collect_service.compute_next_run(
        now_tz(), task.schedule_type, task.interval_minutes or 0
    )
    db.add(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"任务编码已存在: {payload.code}") from None
    db.refresh(task)
    return ApiResponse(data=_task_out(db, task, _source_names(db, tenant_id)))


@router.get("/tasks/{task_id}", response_model=ApiResponse[CollectTaskOut])
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CollectTaskOut]:
    """采集任务详情。"""
    task = _get_task(db, tenant_id, task_id)
    return ApiResponse(data=_task_out(db, task, _source_names(db, tenant_id)))


@router.put("/tasks/{task_id}", response_model=ApiResponse[CollectTaskOut])
def update_task(
    task_id: int,
    payload: CollectTaskUpdateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CollectTaskOut]:
    """编辑采集任务（编码不可改；改动调度策略会重排下次执行时间）。"""
    task = _get_task(db, tenant_id, task_id)
    data = payload.model_dump(exclude_unset=True)
    if "source_id" in data and data["source_id"]:
        source = db.execute(
            select(DataSource).where(
                DataSource.id == data["source_id"], DataSource.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if source is None:
            raise HTTPException(status_code=400, detail="关联数据源不存在")
    if "mapping" in data:
        task.mapping = data.pop("mapping")
    schedule_changed = "schedule_type" in data or "interval_minutes" in data
    for key, value in data.items():
        setattr(task, key, value)
    if schedule_changed:
        task.next_run_at = collect_service.compute_next_run(
            now_tz(), task.schedule_type, task.interval_minutes or 0
        )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ApiResponse(data=_task_out(db, task, _source_names(db, tenant_id)))


@router.delete("/tasks/{task_id}", response_model=ApiResponse[dict])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    """删除采集任务（运行记录随任务级联清理）。"""
    task = _get_task(db, tenant_id, task_id)
    db.delete(task)
    db.commit()
    return ApiResponse(data={"deleted": task_id, "code": task.code})


# ---------------------------------------------------------------- 执行与调度


@router.post("/tasks/{task_id}/run", response_model=ApiResponse[CollectRunOut])
def run_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CollectRunOut]:
    """手动执行一次采集，返回本次运行记录。"""
    task = _get_task(db, tenant_id, task_id)
    run = collect_service.run_collect(db, task, trigger="manual")
    return ApiResponse(data=_run_out(run, {task.id: task.name}))


@router.post("/tasks/{task_id}/toggle", response_model=ApiResponse[CollectTaskOut])
def toggle_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CollectTaskOut]:
    """启用 / 暂停任务；启用时重排下次执行时间。"""
    task = _get_task(db, tenant_id, task_id)
    if task.status == "enabled":
        task.status = "paused"
        task.next_run_at = None
        message = "任务已暂停"
    else:
        task.status = "enabled"
        task.next_run_at = collect_service.compute_next_run(
            now_tz(), task.schedule_type, task.interval_minutes or 0
        )
        message = "任务已启用"
    db.add(task)
    db.commit()
    db.refresh(task)
    out = _task_out(db, task, _source_names(db, tenant_id))
    return ApiResponse(message=message, data=out)


@router.post("/scheduler/scan", response_model=ApiResponse[dict])
def scan_due(
    db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)
) -> ApiResponse[dict]:
    """立即扫描并执行到期任务（手动兜底调度，便于无后台线程环境使用）。"""
    executed = collect_service.run_due_tasks(db)
    return ApiResponse(data={"executed": executed, "count": len(executed)})


@router.get("/runs", response_model=ApiResponse[PageResult[CollectRunOut]])
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    task_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[CollectRunOut]]:
    """运行记录（可按任务、状态筛选）。"""
    conditions = [CollectRun.tenant_id == tenant_id]
    if task_id:
        conditions.append(CollectRun.task_id == task_id)
    if status:
        conditions.append(CollectRun.status == status)

    total = (
        db.execute(select(func.count()).select_from(CollectRun).where(*conditions)).scalar() or 0
    )
    rows = (
        db.execute(
            select(CollectRun)
            .where(*conditions)
            .order_by(CollectRun.started_at.desc(), CollectRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    names = {
        task.id: task.name
        for task in db.execute(select(CollectTask).where(CollectTask.tenant_id == tenant_id)).scalars()
    }
    return ApiResponse(
        data=PageResult[CollectRunOut](
            total=int(total),
            page=page,
            page_size=page_size,
            items=[_run_out(run, names) for run in rows],
        )
    )
