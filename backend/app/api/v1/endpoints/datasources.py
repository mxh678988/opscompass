"""数据源接口：连接配置的增删改查（密码密文存储、不回显）。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.core.crypto import encrypt
from app.models.base import get_db
from app.models.datasource import DS_TYPES, DataSource
from app.schemas.common import ApiResponse, PageResult
from app.schemas.datasource import DataSourceCreate, DataSourceOut, DataSourceUpdate

router = APIRouter()


def _get_or_404(db: Session, tenant_id: int, code: str) -> DataSource:
    stmt = select(DataSource).where(DataSource.tenant_id == tenant_id, DataSource.code == code)
    ds = db.execute(stmt).scalars().first()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"数据源不存在: {code}")
    return ds


@router.get("", response_model=ApiResponse[PageResult[DataSourceOut]], summary="数据源列表")
def list_datasources(
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[PageResult[DataSourceOut]]:
    stmt = select(DataSource).where(DataSource.tenant_id == tenant_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(DataSource.code.ilike(like) | DataSource.name.ilike(like))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(DataSource.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    result = PageResult[DataSourceOut](
        total=int(total),
        page=page,
        page_size=page_size,
        items=[DataSourceOut.model_validate(r) for r in rows],
    )
    return ApiResponse[PageResult[DataSourceOut]](data=result)


@router.post("", response_model=ApiResponse[DataSourceOut], summary="新建数据源")
def create_datasource(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[DataSourceOut]:
    if payload.ds_type not in DS_TYPES:
        raise HTTPException(status_code=422, detail=f"不支持的数据源类型: {payload.ds_type}")
    exists = db.execute(
        select(DataSource).where(DataSource.tenant_id == tenant_id, DataSource.code == payload.code)
    ).scalars().first()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"数据源编码已存在: {payload.code}")

    data = payload.model_dump(exclude={"password"})
    ds = DataSource(
        tenant_id=tenant_id,
        password_enc=encrypt(payload.password) if payload.password else None,
        **data,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ApiResponse[DataSourceOut](data=DataSourceOut.model_validate(ds))


@router.get("/{code}", response_model=ApiResponse[DataSourceOut], summary="数据源详情")
def get_datasource(
    code: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[DataSourceOut]:
    return ApiResponse[DataSourceOut](data=DataSourceOut.model_validate(_get_or_404(db, tenant_id, code)))


@router.put("/{code}", response_model=ApiResponse[DataSourceOut], summary="更新数据源")
def update_datasource(
    code: str,
    payload: DataSourceUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[DataSourceOut]:
    ds = _get_or_404(db, tenant_id, code)
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("password", None)
    if password:
        ds.password_enc = encrypt(password)
    for field, value in values.items():
        if value is not None:
            setattr(ds, field, value)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ApiResponse[DataSourceOut](data=DataSourceOut.model_validate(ds))


@router.delete("/{code}", response_model=ApiResponse[dict], summary="删除数据源")
def delete_datasource(
    code: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    ds = _get_or_404(db, tenant_id, code)
    db.delete(ds)
    db.commit()
    return ApiResponse[dict](data={"code": code, "deleted": True})
