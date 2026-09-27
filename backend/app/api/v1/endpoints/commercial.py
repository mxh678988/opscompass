"""商业化中心接口：套餐定价 / 授权证书 / 订单 / 用量配额 / 授权校验。

路由前缀 /commercial（见 app/api/v1/router.py，需 commercial 模块权限）：
- 读（总览、权益、套餐/授权/订单/用量列表、授权事件）：commercial:view
- 写（套餐增改删、签发/激活/续期/吊销授权、下单/支付/取消、登记用量、校验授权）：commercial:manage

授权证书采用自有数字签名（HMAC-SHA256），可离线复算校验，服务于本地私有化部署场景。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user
from app.models.auth import User
from app.models.base import get_db
from app.schemas.commercial import (
    LicenseIn,
    LicenseRenewIn,
    LicenseVerifyIn,
    OrderIn,
    OrderPayIn,
    PlanIn,
    PlanPatch,
    UsageIn,
)
from app.schemas.common import ApiResponse
from app.services import commercial_service as svc

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _operator(user: User) -> str:
    return getattr(user, "username", "") or ""


# ============================================================ 总览 / 权益
@router.get(
    "/overview",
    response_model=ApiResponse[dict],
    summary="商业化总览（套餐/授权/订单/收入/用量告警/上架门槛清单）",
)
def read_overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.stats_overview(db, tenant_id))


@router.get(
    "/entitlement",
    response_model=ApiResponse[dict],
    summary="当前租户权益（生效授权 + 套餐限额 + 本月用量对账）",
)
def read_entitlement(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.entitlement(db, tenant_id))


# ============================================================ 套餐
@router.get("/plans", response_model=ApiResponse[dict], summary="套餐列表")
def list_plans(
    keyword: str | None = Query(default=None, description="名称或编码关键字"),
    edition: str | None = Query(default=None, description="private|saas|market|trial"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_plans(db, tenant_id, keyword, edition, page, size))


@router.post("/plans", response_model=ApiResponse[dict], summary="新建套餐")
def create_plan(
    payload: PlanIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](data=svc.create_plan(db, tenant_id, payload), message="套餐已创建")
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/plans/seed", response_model=ApiResponse[dict], summary="重建内置套餐（社区版/专业版/旗舰版/SaaS 订阅）")
def seed_plans(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    created = svc.ensure_default_plans(db, tenant_id)
    return ApiResponse[dict](data={"created": created}, message=f"内置套餐已就绪（新增 {created} 档）")


@router.patch("/plans/{plan_id}", response_model=ApiResponse[dict], summary="修改套餐")
def update_plan(
    plan_id: int,
    payload: PlanPatch,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](data=svc.update_plan(db, tenant_id, plan_id, payload), message="套餐已更新")
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.delete("/plans/{plan_id}", response_model=ApiResponse[dict], summary="删除套餐（已签发授权的套餐不可删）")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](data=svc.delete_plan(db, tenant_id, plan_id), message="套餐已删除")
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


# ============================================================ 授权
@router.get("/licenses", response_model=ApiResponse[dict], summary="授权列表")
def list_licenses(
    keyword: str | None = Query(default=None, description="授权码/授权对象/机器码关键字"),
    status: str | None = Query(default=None, description="pending|active|expired|revoked"),
    license_type: str | None = Query(default=None, description="private|saas|market|trial"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](
        data=svc.list_licenses(db, tenant_id, keyword, status, license_type, page, size)
    )


@router.post("/licenses", response_model=ApiResponse[dict], summary="签发授权证书（自动写入数字签名）")
def issue_license(
    payload: LicenseIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](
            data=svc.issue_license(db, tenant_id, payload, _operator(user)), message="授权已签发"
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/licenses/{license_id}/activate", response_model=ApiResponse[dict], summary="激活授权（绑定机器码）")
def activate_license(
    license_id: int,
    machine_code: str = Query(default="", description="机器码，留空则仅切换为生效态"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](
            data=svc.activate_license(db, tenant_id, license_id, machine_code, _operator(user)),
            message="授权已激活",
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/licenses/{license_id}/renew", response_model=ApiResponse[dict], summary="续期授权并重算签名")
def renew_license(
    license_id: int,
    payload: LicenseRenewIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](
            data=svc.renew_license(db, tenant_id, license_id, payload.days, _operator(user)),
            message="授权已续期",
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/licenses/{license_id}/revoke", response_model=ApiResponse[dict], summary="吊销授权")
def revoke_license(
    license_id: int,
    reason: str = Query(default="", description="吊销原因"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](
            data=svc.revoke_license(db, tenant_id, license_id, reason, _operator(user)),
            message="授权已吊销",
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/license/verify", response_model=ApiResponse[dict], summary="校验授权（签名/状态/有效期/机器码四重校验）")
def verify_license(
    payload: LicenseVerifyIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    result = svc.verify_license(db, tenant_id, payload.license_key, payload.machine_code)
    return ApiResponse[dict](data=result, message=result.get("reason", ""))


@router.get("/events", response_model=ApiResponse[dict], summary="授权事件留痕（签发/激活/续期/吊销/校验失败）")
def list_events(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data={"items": svc.list_license_events(db, tenant_id, limit)})


# ============================================================ 订单
@router.get("/orders", response_model=ApiResponse[dict], summary="订单列表")
def list_orders(
    keyword: str | None = Query(default=None, description="订单号/购买方/套餐名关键字"),
    status: str | None = Query(default=None, description="pending|paid|cancelled|refunded"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_orders(db, tenant_id, keyword, status, page, size))


@router.post("/orders", response_model=ApiResponse[dict], summary="创建订单")
def create_order(
    payload: OrderIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](data=svc.create_order(db, tenant_id, payload), message="订单已创建")
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/orders/{order_id}/pay", response_model=ApiResponse[dict], summary="订单支付（成功后自动签发授权）")
def pay_order(
    order_id: int,
    payload: OrderPayIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](
            data=svc.pay_order(db, tenant_id, order_id, payload, _operator(user)),
            message="订单已支付并发证",
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


@router.post("/orders/{order_id}/cancel", response_model=ApiResponse[dict], summary="取消订单")
def cancel_order(
    order_id: int,
    reason: str = Query(default="", description="取消原因"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](
            data=svc.cancel_order(db, tenant_id, order_id, reason, _operator(user)),
            message="订单已取消",
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)


# ============================================================ 用量与配额
@router.get("/usage", response_model=ApiResponse[dict], summary="用量列表（可按账期过滤）")
def list_usage(
    period: str | None = Query(default=None, description="账期 YYYY-MM，留空返回全部"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    return ApiResponse[dict](data=svc.list_usage(db, tenant_id, period, page, size))


@router.post("/usage", response_model=ApiResponse[dict], summary="登记/更新用量（自动判定告警与超额）")
def upsert_usage(
    payload: UsageIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
) -> ApiResponse[dict]:
    try:
        return ApiResponse[dict](data=svc.upsert_usage(db, tenant_id, payload), message="用量已更新")
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc)
