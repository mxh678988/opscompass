"""数据接入接口：文件上传 → 结构预览 → 映射导入 → 任务查询。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.models.base import get_db
from app.models.datasource import DataSource
from app.models.import_task import ImportTask
from app.models.metric import Metric
from app.schemas.common import ApiResponse, PageResult
from app.schemas.ingest import (
    ImportTaskOut,
    IngestPreviewIn,
    IngestPreviewOut,
    IngestRunIn,
    UploadOut,
)
from app.services import ingest_service as svc

router = APIRouter()


def _metric_options(db: Session, tenant_id: int) -> list[dict]:
    """当前租户已有指标，供前端映射时下拉选择。"""
    rows = db.execute(
        select(Metric).where(Metric.tenant_id == tenant_id).order_by(Metric.id.asc())
    ).scalars().all()
    return [
        {"code": m.code, "name": m.name, "unit": m.unit, "status": m.status}
        for m in rows
    ]


@router.post("/upload", response_model=ApiResponse[UploadOut], summary="上传数据文件")
async def upload_file(
    file: UploadFile = File(..., description="CSV / Excel 文件"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[UploadOut]:
    content = await file.read()
    try:
        info = svc.save_upload(file.filename or "upload.csv", content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ApiResponse[UploadOut](data=UploadOut(**info))


@router.get("/files", response_model=ApiResponse[dict], summary="可导入文件清单")
def list_files(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](
        data={"raw": svc.list_raw_files(), "samples": svc.list_sample_files()}
    )


@router.post("/samples/{file_name}/load", response_model=ApiResponse[UploadOut], summary="载入示例文件")
def load_sample(
    file_name: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[UploadOut]:
    try:
        info = svc.copy_sample_to_raw(file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse[UploadOut](data=UploadOut(**info))


@router.post("/preview", response_model=ApiResponse[IngestPreviewOut], summary="预览文件结构")
def preview_file(
    payload: IngestPreviewIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[IngestPreviewOut]:
    try:
        data = svc.preview(payload.file_name, payload.limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    metrics = _metric_options(db, tenant_id)
    suggested = svc.suggest_mapping(data["columns"], [m["code"] for m in metrics])
    return ApiResponse[IngestPreviewOut](
        data=IngestPreviewOut(**data, suggested=suggested, known_metrics=metrics)
    )


@router.post("/run", response_model=ApiResponse[ImportTaskOut], summary="执行导入")
def run_import(
    payload: IngestRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ImportTaskOut]:
    source_id: Optional[int] = None
    if payload.source_code:
        ds = db.execute(
            select(DataSource).where(
                DataSource.tenant_id == tenant_id, DataSource.code == payload.source_code
            )
        ).scalars().first()
        if ds is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"数据源不存在: {payload.source_code}"
            )
        source_id = ds.id

    try:
        task = svc.run_import(db, tenant_id, payload.file_name, payload.mapping, source_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ApiResponse[ImportTaskOut](data=ImportTaskOut.model_validate(task))


@router.get("/tasks", response_model=ApiResponse[PageResult[ImportTaskOut]], summary="导入任务列表")
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[ImportTaskOut]]:
    total, rows = svc.list_tasks(db, tenant_id, page, page_size)
    return ApiResponse[PageResult[ImportTaskOut]](
        data=PageResult[ImportTaskOut](
            total=total,
            page=page,
            page_size=page_size,
            items=[ImportTaskOut.model_validate(r) for r in rows],
        )
    )


@router.get("/tasks/{task_id}", response_model=ApiResponse[ImportTaskOut], summary="导入任务详情")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ImportTaskOut]:
    task = db.get(ImportTask, task_id)
    if task is None or task.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}")
    return ApiResponse[ImportTaskOut](data=ImportTaskOut.model_validate(task))
