"""租户接口：多租户根实体的查询与创建。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.tenant import Tenant
from app.schemas.common import ApiResponse
from app.schemas.tenant import TenantCreate, TenantOut

router = APIRouter()


@router.get("", response_model=ApiResponse[list[TenantOut]], summary="租户列表")
def list_tenants(db: Session = Depends(get_db)) -> ApiResponse[list[TenantOut]]:
    rows = db.execute(select(Tenant).order_by(Tenant.id.asc())).scalars().all()
    return ApiResponse[list[TenantOut]](data=[TenantOut.model_validate(r) for r in rows])


@router.post("", response_model=ApiResponse[TenantOut], summary="新建租户")
def create_tenant(
    payload: TenantCreate, db: Session = Depends(get_db)
) -> ApiResponse[TenantOut]:
    exists = db.execute(select(Tenant).where(Tenant.code == payload.code)).scalars().first()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"租户编码已存在: {payload.code}")
    tenant = Tenant(code=payload.code, name=payload.name, remark=payload.remark)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return ApiResponse[TenantOut](data=TenantOut.model_validate(tenant))
