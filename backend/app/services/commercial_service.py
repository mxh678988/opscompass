"""商业化服务（P10）：套餐定价 / 授权签发与校验 / 订单 / 用量配额 / 商业化总览。

设计要点：
- 授权证书使用自有数字签名（HMAC-SHA256）：签名载荷由授权码 + 套餐编码 + 授权对象 + 机器码 +
  到期时间规范化拼装，密钥取 settings.COMMERCIAL_LICENSE_SECRET（未配置时回落 SECRET_KEY）；
  校验失败一律写入 verify_failed 事件，保证「发布包 / 授权包完整性可校验」；
- 授权形态三选：本地私有化一次性授权（private）、SaaS 订阅（saas）、应用市场轻量版（market）；
- 定价分档维度：账号数（seats）、站点/门店数（store）、指标数（metric）、AI 配额；
- 全部能力由模块权限 commercial:view / commercial:manage 收口（见 app/api/deps.py）。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import SessionLocal
from app.models.commercial import (
    ComLicense,
    ComLicenseEvent,
    ComOrder,
    ComPlan,
    ComUsage,
)

# 授权即将到期阈值（天）
EXPIRING_SOON_DAYS = 30
# 用量告警阈值（占比）
WARNING_RATIO = 0.8


# ---------------------------------------------------------------- 内置套餐
# 四档定价：社区版 / 私有化专业版 / 私有化旗舰版 / SaaS 标准订阅
DEFAULT_PLANS: list[dict] = [
    {
        "code": "community",
        "name": "社区版",
        "edition": "trial",
        "billing_cycle": "one_time",
        "price": 0,
        "seats_limit": 3,
        "store_limit": 1,
        "metric_limit": 50,
        "user_limit": 3,
        "ai_quota": 200,
        "features": ["本地部署", "单站点运营", "基础指标与决策", "社区支持"],
        "sort": 10,
        "remark": "免费试用档，用于本地验证与功能体验",
    },
    {
        "code": "private_pro",
        "name": "私有化专业版",
        "edition": "private",
        "billing_cycle": "one_time",
        "price": 3980,
        "seats_limit": 20,
        "store_limit": 3,
        "metric_limit": 300,
        "user_limit": 10,
        "ai_quota": 0,
        "features": [
            "本地私有化部署 · 数据不出内网",
            "多站点运营与营销渠道接入",
            "数字人一键生成",
            "学习进化闭环",
            "自有数字签名授权 + 一年版本升级",
        ],
        "sort": 20,
        "remark": "本地私有化一次性授权，按账号数 / 站点数分档",
    },
    {
        "code": "private_ent",
        "name": "私有化旗舰版",
        "edition": "private",
        "billing_cycle": "one_time",
        "price": 12800,
        "seats_limit": 100,
        "store_limit": 10,
        "metric_limit": 2000,
        "user_limit": 50,
        "ai_quota": 0,
        "features": [
            "私有化专业版全部能力",
            "多租户隔离与租户级配额",
            "集群部署与备份恢复演练支持",
            "模型自动适配（本地 / 云端混合）",
            "专属支持通道 + 三年版本升级",
        ],
        "sort": 30,
        "remark": "面向多门店 / 多品牌集团的旗舰档",
    },
    {
        "code": "saas_std",
        "name": "SaaS 标准订阅",
        "edition": "saas",
        "billing_cycle": "monthly",
        "price": 299,
        "seats_limit": 10,
        "store_limit": 2,
        "metric_limit": 200,
        "user_limit": 10,
        "ai_quota": 5000,
        "features": ["云端开箱即用", "按月订阅可随时升降档", "含 5000 次 AI 调用 / 月", "自动备份"],
        "sort": 40,
        "remark": "订阅制，按账号数与 AI 用量分档",
    },
]


def _now() -> datetime:
    return datetime.now()


def _t(value: Any, default: str = "") -> str:
    return (value or "").strip() if isinstance(value, str) else default


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_dt(value: Any) -> Optional[datetime]:
    """解析 ISO 时间字符串；仅支持 YYYY-MM-DD 或 ISO8601。"""
    text = _t(value)
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.strptime(text, "%Y-%m-%d")
        return datetime.fromisoformat(text.replace("Z", ""))
    except ValueError:
        return None


def _period(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%Y-%m")


def _paginate(
    db: Session, model, conditions: list, page: int = 1, size: int = 20, order_by=None
) -> tuple[int, list]:
    """通用分页查询，返回 (total, rows)。"""
    page = max(1, int(page or 1))
    size = min(200, max(1, int(size or 20)))
    total = db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    order = order_by if order_by is not None else model.id.desc()
    if not isinstance(order, (tuple, list)):
        order = [order]
    rows = (
        db.execute(
            select(model).where(*conditions).order_by(*order).offset((page - 1) * size).limit(size)
        )
        .scalars()
        .all()
    )
    return int(total), list(rows)


# ============================================================ 数字签名
def _sign_secret() -> bytes:
    """签名密钥：优先专用配置，未配置时回落系统密钥。"""
    from app.core.config import settings

    raw = _t(getattr(settings, "COMMERCIAL_LICENSE_SECRET", "")) or _t(
        getattr(settings, "SECRET_KEY", "")
    ) or "opscompass-license"
    return raw.encode("utf-8")


def license_payload(
    license_key: str,
    plan_code: str,
    issued_to: str,
    machine_code: str,
    expires_at: Optional[datetime],
) -> dict:
    """规范化签名载荷（顺序固定，保证可复算）。"""
    return {
        "license_key": license_key,
        "plan_code": plan_code,
        "issued_to": issued_to,
        "machine_code": machine_code,
        "expires_at": expires_at.strftime("%Y-%m-%d") if expires_at else "forever",
    }


def sign_payload(payload: dict) -> str:
    """对载荷做 HMAC-SHA256 签名，返回十六进制串。"""
    canonical = "|".join(
        [
            str(payload.get("license_key", "")),
            str(payload.get("plan_code", "")),
            str(payload.get("issued_to", "")),
            str(payload.get("machine_code", "")),
            str(payload.get("expires_at", "")),
        ]
    )
    return hmac.new(_sign_secret(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def make_license_key(license_type: str, plan_code: str) -> str:
    """生成授权码：OC-<形态>-<套餐>-<随机段>。"""
    body = secrets.token_hex(8).upper()
    return f"OC-{license_type.upper()}-{plan_code.upper()}-{body}"


def _log_event(
    db: Session,
    tenant_id: int,
    license_row: Optional[ComLicense],
    action: str,
    detail: str = "",
    operator: str = "",
) -> None:
    db.add(
        ComLicenseEvent(
            tenant_id=tenant_id,
            license_id=getattr(license_row, "id", None),
            license_key=getattr(license_row, "license_key", "") or "",
            action=action,
            detail=detail,
            operator=operator,
        )
    )
    db.commit()


# ============================================================ 套餐
def plan_to_dict(row: ComPlan) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "code": row.code,
        "name": row.name,
        "edition": row.edition,
        "billing_cycle": row.billing_cycle,
        "price": _f(row.price),
        "currency": row.currency,
        "seats_limit": row.seats_limit,
        "store_limit": row.store_limit,
        "metric_limit": row.metric_limit,
        "user_limit": row.user_limit,
        "ai_quota": row.ai_quota,
        "features": list(row.features or []),
        "is_public": bool(row.is_public),
        "sort": row.sort,
        "status": row.status,
        "remark": row.remark,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_plan(db: Session, tenant_id: int, plan_id: int) -> Optional[ComPlan]:
    row = db.get(ComPlan, plan_id)
    if row is None or row.tenant_id != tenant_id:
        return None
    return row


def list_plans(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    edition: str | None = None,
    page: int = 1,
    size: int = 50,
) -> dict:
    conditions = [ComPlan.tenant_id == tenant_id]
    if _t(keyword):
        like = f"%{_t(keyword)}%"
        conditions.append(ComPlan.name.like(like) | ComPlan.code.like(like))
    if _t(edition):
        conditions.append(ComPlan.edition == _t(edition))
    total, rows = _paginate(
        db, ComPlan, conditions, page, size, order_by=[ComPlan.sort.asc(), ComPlan.id.asc()]
    )
    return {"total": total, "page": page, "page_size": size, "items": [plan_to_dict(r) for r in rows]}


def create_plan(db: Session, tenant_id: int, payload: Any) -> dict:
    code = _t(payload.code)
    if not code:
        raise ValueError("套餐编码不能为空")
    exists = db.execute(
        select(ComPlan).where(ComPlan.tenant_id == tenant_id, ComPlan.code == code)
    ).scalars().first()
    if exists is not None:
        raise ValueError(f"套餐编码已存在: {code}")
    row = ComPlan(
        tenant_id=tenant_id,
        code=code,
        name=_t(payload.name) or code,
        edition=_t(payload.edition, "private"),
        billing_cycle=_t(payload.billing_cycle, "one_time"),
        price=_f(payload.price),
        currency=_t(payload.currency, "CNY"),
        seats_limit=payload.seats_limit,
        store_limit=payload.store_limit,
        metric_limit=payload.metric_limit,
        user_limit=payload.user_limit,
        ai_quota=payload.ai_quota,
        features=list(payload.features or []),
        is_public=bool(payload.is_public),
        sort=payload.sort,
        status=_t(payload.status, "on"),
        remark=_t(payload.remark),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return plan_to_dict(row)


def update_plan(db: Session, tenant_id: int, plan_id: int, payload: Any) -> dict:
    row = get_plan(db, tenant_id, plan_id)
    if row is None:
        raise ValueError("套餐不存在")
    data = payload.model_dump(exclude_unset=True)
    for field in (
        "name",
        "edition",
        "billing_cycle",
        "currency",
        "seats_limit",
        "store_limit",
        "metric_limit",
        "user_limit",
        "ai_quota",
        "is_public",
        "sort",
        "status",
        "remark",
    ):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])
    if "price" in data and data["price"] is not None:
        row.price = _f(data["price"])
    if "features" in data and data["features"] is not None:
        row.features = list(data["features"] or [])
    db.commit()
    db.refresh(row)
    return plan_to_dict(row)


def delete_plan(db: Session, tenant_id: int, plan_id: int) -> dict:
    row = get_plan(db, tenant_id, plan_id)
    if row is None:
        raise ValueError("套餐不存在")
    if row.code in {item["code"] for item in DEFAULT_PLANS}:
        raise ValueError("内置套餐不可删除；如需停售请改为「下架」")
    used = db.scalar(
        select(func.count()).select_from(ComLicense).where(ComLicense.plan_id == plan_id)
    ) or 0
    if int(used) > 0:
        raise ValueError(f"该套餐已签发 {int(used)} 张授权，不可删除；如需停售请改为「下架」")
    db.delete(row)
    db.commit()
    return {"id": plan_id, "deleted": True}


def ensure_default_plans(db: Session, tenant_id: int) -> int:
    """幂等写入内置套餐，返回新增数量。"""
    existing = {
        row.code
        for row in db.execute(select(ComPlan).where(ComPlan.tenant_id == tenant_id)).scalars().all()
    }
    created = 0
    for item in DEFAULT_PLANS:
        if item["code"] in existing:
            continue
        db.add(ComPlan(tenant_id=tenant_id, **item))
        created += 1
    if created:
        db.commit()
    return created


# ============================================================ 授权
def _naive(value: Optional[datetime]) -> Optional[datetime]:
    """统一为 naive 本地时间，便于与 _now() 比较。"""
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def is_expired(expires_at: Optional[datetime]) -> bool:
    exp = _naive(expires_at)
    return exp is not None and exp < _now()


def days_left(expires_at: Optional[datetime]) -> Optional[int]:
    exp = _naive(expires_at)
    if exp is None:
        return None
    return (exp.date() - _now().date()).days


def license_to_dict(row: ComLicense, plan: Optional[ComPlan] = None) -> dict:
    left = days_left(row.expires_at)
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "plan_id": row.plan_id,
        "plan_code": getattr(plan, "code", "") or "",
        "plan_name": getattr(plan, "name", "") or "",
        "license_key": row.license_key,
        "license_type": row.license_type,
        "edition": row.edition,
        "status": row.status,
        "seats": row.seats,
        "machine_code": row.machine_code,
        "issued_to": row.issued_to,
        "channel": row.channel,
        "signature": row.signature,
        "payload": row.payload or {},
        "issued_at": row.issued_at,
        "activated_at": row.activated_at,
        "expires_at": row.expires_at,
        "days_left": left,
        "expiring_soon": bool(left is not None and 0 <= left <= EXPIRING_SOON_DAYS),
        "expired": is_expired(row.expires_at),
        "remark": row.remark,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_license(db: Session, tenant_id: int, license_id: int) -> Optional[ComLicense]:
    row = db.get(ComLicense, license_id)
    if row is None or row.tenant_id != tenant_id:
        return None
    return row


def list_licenses(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    status: str | None = None,
    license_type: str | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    conditions = [ComLicense.tenant_id == tenant_id]
    if _t(keyword):
        like = f"%{_t(keyword)}%"
        conditions.append(
            ComLicense.license_key.like(like)
            | ComLicense.issued_to.like(like)
            | ComLicense.machine_code.like(like)
        )
    if _t(status):
        conditions.append(ComLicense.status == _t(status))
    if _t(license_type):
        conditions.append(ComLicense.license_type == _t(license_type))
    total, rows = _paginate(db, ComLicense, conditions, page, size)
    plan_map = {
        p.id: p for p in db.execute(select(ComPlan).where(ComPlan.tenant_id == tenant_id)).scalars().all()
    }
    return {
        "total": total,
        "page": page,
        "page_size": size,
        "items": [license_to_dict(r, plan_map.get(r.plan_id)) for r in rows],
    }


def issue_license(db: Session, tenant_id: int, payload: Any, operator: str = "") -> dict:
    """签发授权证书：落地自有数字签名，绑定机器码时进入待激活态。"""
    plan: Optional[ComPlan] = None
    if payload.plan_id:
        plan = get_plan(db, tenant_id, payload.plan_id)
        if plan is None:
            raise ValueError("套餐不存在")
    license_type = _t(payload.license_type, "private")
    plan_code = getattr(plan, "code", "") or "custom"
    days = int(getattr(payload, "days", 365) or 0)
    expires_at = _now() + timedelta(days=days) if days > 0 else None
    machine_code = _t(getattr(payload, "machine_code", ""))
    issued_to = _t(getattr(payload, "issued_to", "")) or "未指定"

    license_key = make_license_key(license_type, plan_code)
    snapshot = license_payload(license_key, plan_code, issued_to, machine_code, expires_at)
    signature = sign_payload(snapshot)

    row = ComLicense(
        tenant_id=tenant_id,
        plan_id=payload.plan_id,
        license_key=license_key,
        license_type=license_type,
        edition=getattr(plan, "name", "") or license_type,
        status="pending" if machine_code else "active",
        seats=int(getattr(payload, "seats", 1) or 1),
        machine_code=machine_code,
        issued_to=issued_to,
        channel=_t(getattr(payload, "channel", "") or "manual"),
        signature=signature,
        payload=snapshot,
        issued_at=_now(),
        activated_at=None if machine_code else _now(),
        expires_at=expires_at,
        remark=_t(getattr(payload, "remark", "")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _log_event(db, tenant_id, row, "issue", f"签发授权（{license_type} / {plan_code}）", operator)
    return license_to_dict(row, plan)


def activate_license(
    db: Session, tenant_id: int, license_id: int, machine_code: str, operator: str = ""
) -> dict:
    """激活授权：绑定机器码并转为生效态。"""
    row = get_license(db, tenant_id, license_id)
    if row is None:
        raise ValueError("授权不存在")
    if row.status == "revoked":
        raise ValueError("授权已被吊销，无法激活")
    if is_expired(row.expires_at):
        row.status = "expired"
        db.commit()
        raise ValueError("授权已过期，请先续期")
    code = _t(machine_code)
    if row.machine_code and code and code != row.machine_code:
        raise ValueError("该授权已绑定其他机器码，无法在当前设备激活")
    if row.signature:
        expect = sign_payload(row.payload or {})
        if not hmac.compare_digest(expect, row.signature):
            _log_event(db, tenant_id, row, "verify_failed", "激活时签名不一致", operator)
            raise ValueError("授权签名校验失败，证书可能被篡改")
    if code:
        row.machine_code = code
    row.status = "active"
    row.activated_at = _now()
    db.commit()
    db.refresh(row)
    _log_event(db, tenant_id, row, "activate", f"激活设备 {row.machine_code or '未绑定'}", operator)
    return license_to_dict(row, get_plan(db, tenant_id, row.plan_id) if row.plan_id else None)


def renew_license(db: Session, tenant_id: int, license_id: int, days: int, operator: str = "") -> dict:
    """续期：以「到期日或今天」较晚者为基准顺延，并重算签名。"""
    row = get_license(db, tenant_id, license_id)
    if row is None:
        raise ValueError("授权不存在")
    if row.status == "revoked":
        raise ValueError("授权已被吊销，无法续期")
    if days <= 0:
        raise ValueError("续期天数必须大于 0")
    base = _naive(row.expires_at)
    now = _now()
    if base is None:  # 永久授权无需续期
        raise ValueError("该授权为永久有效，无需续期")
    base = base if base > now else now
    row.expires_at = base + timedelta(days=int(days))
    row.status = "active"
    plan = get_plan(db, tenant_id, row.plan_id) if row.plan_id else None
    snapshot = license_payload(
        row.license_key,
        getattr(plan, "code", "") or "custom",
        row.issued_to,
        row.machine_code,
        row.expires_at,
    )
    row.payload = snapshot
    row.signature = sign_payload(snapshot)
    db.commit()
    db.refresh(row)
    _log_event(db, tenant_id, row, "renew", f"续期 {days} 天，至 {row.expires_at:%Y-%m-%d}", operator)
    return license_to_dict(row, plan)


def revoke_license(db: Session, tenant_id: int, license_id: int, reason: str = "", operator: str = "") -> dict:
    """吊销授权。"""
    row = get_license(db, tenant_id, license_id)
    if row is None:
        raise ValueError("授权不存在")
    if row.status == "revoked":
        return license_to_dict(row)
    row.status = "revoked"
    db.commit()
    db.refresh(row)
    _log_event(db, tenant_id, row, "revoke", _t(reason) or "管理员吊销", operator)
    return license_to_dict(row)


def verify_license(
    db: Session, tenant_id: int, license_key: str, machine_code: str = ""
) -> dict:
    """校验授权：签名 / 状态 / 有效期 / 机器码四重校验，全程留痕。"""
    key = _t(license_key)
    if not key:
        return {"valid": False, "reason": "授权码不能为空"}
    row = db.execute(
        select(ComLicense).where(ComLicense.license_key == key)
    ).scalars().first()
    if row is None:
        _log_event(db, tenant_id, None, "verify_failed", f"授权码不存在: {key}")
        return {"valid": False, "reason": "授权码不存在"}
    if row.signature:
        expect = sign_payload(row.payload or {})
        if not hmac.compare_digest(expect, row.signature):
            _log_event(db, tenant_id, row, "verify_failed", "签名不一致", "")
            return {"valid": False, "reason": "授权签名校验失败，证书可能被篡改"}
    if row.status == "revoked":
        _log_event(db, tenant_id, row, "verify_failed", "授权已吊销", "")
        return {"valid": False, "reason": "授权已被吊销"}
    if is_expired(row.expires_at):
        row.status = "expired"
        db.commit()
        _log_event(db, tenant_id, row, "verify_failed", "授权已过期", "")
        return {"valid": False, "reason": "授权已过期", "expires_at": row.expires_at}
    code = _t(machine_code)
    if row.machine_code and code and code != row.machine_code:
        _log_event(db, tenant_id, row, "verify_failed", "机器码不匹配", "")
        return {"valid": False, "reason": "授权与当前设备不匹配"}
    plan = get_plan(db, tenant_id, row.plan_id) if row.plan_id else None
    _log_event(db, tenant_id, row, "verify_ok", "校验通过", "")
    return {
        "valid": True,
        "reason": "ok",
        "license": license_to_dict(row, plan),
        "plan": plan_to_dict(plan) if plan is not None else None,
    }


def list_license_events(db: Session, tenant_id: int, limit: int = 20) -> list[dict]:
    rows = (
        db.execute(
            select(ComLicenseEvent)
            .where(ComLicenseEvent.tenant_id == tenant_id)
            .order_by(ComLicenseEvent.id.desc())
            .limit(min(100, max(1, int(limit))))
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "license_id": r.license_id,
            "license_key": r.license_key,
            "action": r.action,
            "detail": r.detail,
            "operator": r.operator,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ============================================================ 订单
def _order_no() -> str:
    return f"OC{_now():%Y%m%d%H%M%S}{secrets.token_hex(3).upper()}"


def order_to_dict(row: ComOrder) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "order_no": row.order_no,
        "plan_id": row.plan_id,
        "license_id": row.license_id,
        "plan_code": row.plan_code,
        "plan_name": row.plan_name,
        "amount": _f(row.amount),
        "currency": row.currency,
        "status": row.status,
        "pay_channel": row.pay_channel,
        "buyer": row.buyer,
        "contact": row.contact,
        "paid_at": row.paid_at,
        "remark": row.remark,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_orders(
    db: Session,
    tenant_id: int,
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    conditions = [ComOrder.tenant_id == tenant_id]
    if _t(keyword):
        like = f"%{_t(keyword)}%"
        conditions.append(
            ComOrder.order_no.like(like) | ComOrder.buyer.like(like) | ComOrder.plan_name.like(like)
        )
    if _t(status):
        conditions.append(ComOrder.status == _t(status))
    total, rows = _paginate(db, ComOrder, conditions, page, size)
    return {"total": total, "page": page, "page_size": size, "items": [order_to_dict(r) for r in rows]}


def create_order(db: Session, tenant_id: int, payload: Any, operator: str = "") -> dict:
    plan = get_plan(db, tenant_id, payload.plan_id)
    if plan is None:
        raise ValueError("套餐不存在")
    row = ComOrder(
        tenant_id=tenant_id,
        order_no=_order_no(),
        plan_id=plan.id,
        plan_code=plan.code,
        plan_name=plan.name,
        amount=_f(plan.price),
        currency=plan.currency,
        status="pending",
        pay_channel=_t(getattr(payload, "pay_channel", "") or "offline"),
        buyer=_t(getattr(payload, "buyer", "")),
        contact=_t(getattr(payload, "contact", "")),
        remark=_t(getattr(payload, "remark", "")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return order_to_dict(row)


def pay_order(db: Session, tenant_id: int, order_id: int, payload: Any, operator: str = "") -> dict:
    """支付订单：标记已支付并自动签发对应授权证书。"""
    from app.schemas.commercial import LicenseIn  # 局部导入避免循环依赖

    row = db.get(ComOrder, order_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("订单不存在")
    if row.status == "paid":
        raise ValueError("订单已支付，请勿重复操作")
    if row.status in ("cancelled", "refunded"):
        raise ValueError(f"订单当前状态为 {row.status}，不可支付")

    row.status = "paid"
    row.paid_at = _now()
    channel = _t(getattr(payload, "pay_channel", "")) or row.pay_channel
    row.pay_channel = channel
    db.commit()

    plan = get_plan(db, tenant_id, row.plan_id) if row.plan_id else None
    if plan is not None and row.license_id is None:
        issued = issue_license(
            db,
            tenant_id,
            LicenseIn(
                plan_id=plan.id,
                license_type=plan.edition if plan.edition in ("private", "saas", "market", "trial") else "private",
                seats=plan.seats_limit or 1,
                machine_code=_t(getattr(payload, "machine_code", "")),
                issued_to=row.buyer or "未指定",
                channel=channel if channel in ("wechat", "alipay", "market", "offline", "manual") else "manual",
                days=int(getattr(payload, "days", 365) or 0),
                remark=f"由订单 {row.order_no} 自动签发",
            ),
            operator=operator,
        )
        row.license_id = issued["id"]
        db.commit()

    db.refresh(row)
    return order_to_dict(row)


def cancel_order(db: Session, tenant_id: int, order_id: int, reason: str = "", operator: str = "") -> dict:
    row = db.get(ComOrder, order_id)
    if row is None or row.tenant_id != tenant_id:
        raise ValueError("订单不存在")
    if row.status == "paid":
        raise ValueError("订单已支付，如需终止请走退款流程")
    row.status = "cancelled"
    if _t(reason):
        row.remark = f"{row.remark} | 取消原因：{_t(reason)}".strip(" |")
    db.commit()
    db.refresh(row)
    return order_to_dict(row)


# ============================================================ 用量与配额
def _usage_status(used: int, quota: int) -> str:
    if quota and quota > 0:
        if used >= quota:
            return "exceeded"
        if used >= quota * WARNING_RATIO:
            return "warning"
    return "normal"


def usage_to_dict(row: ComUsage) -> dict:
    ratio = round(row.used / row.quota, 4) if row.quota else None
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "metric_key": row.metric_key,
        "period": row.period,
        "used": row.used,
        "quota": row.quota,
        "unit": row.unit,
        "status": row.status,
        "ratio": ratio,
        "note": row.note,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_usage(
    db: Session, tenant_id: int, period: str | None = None, page: int = 1, size: int = 50
) -> dict:
    conditions = [ComUsage.tenant_id == tenant_id]
    if _t(period):
        conditions.append(ComUsage.period == _t(period))
    total, rows = _paginate(
        db, ComUsage, conditions, page, size, order_by=[ComUsage.period.desc(), ComUsage.id.asc()]
    )
    items = [usage_to_dict(r) for r in rows]
    return {
        "total": total,
        "page": page,
        "page_size": size,
        "items": items,
        "summary": {
            "warning": sum(1 for i in items if i["status"] == "warning"),
            "exceeded": sum(1 for i in items if i["status"] == "exceeded"),
        },
    }


def upsert_usage(db: Session, tenant_id: int, payload: Any) -> dict:
    """按租户 + 指标 + 账期登记用量（覆盖或用增量累加）。"""
    key = _t(payload.metric_key)
    period = _t(payload.period) or _period()
    if not key:
        raise ValueError("指标标识不能为空")
    row = db.execute(
        select(ComUsage).where(
            ComUsage.tenant_id == tenant_id,
            ComUsage.metric_key == key,
            ComUsage.period == period,
        )
    ).scalars().first()
    if row is None:
        row = ComUsage(
            tenant_id=tenant_id,
            metric_key=key,
            period=period,
            used=0,
            quota=0,
            unit=_t(getattr(payload, "unit", "") or "count"),
        )
        db.add(row)
        db.flush()
    used = getattr(payload, "used", None)
    if used is not None:
        row.used = max(0, int(used))
    else:
        row.used = max(0, int(row.used or 0) + int(getattr(payload, "delta", 0) or 0))
    quota = getattr(payload, "quota", None)
    if quota is not None:
        row.quota = max(0, int(quota))
    unit = _t(getattr(payload, "unit", ""))
    if unit:
        row.unit = unit
    note = _t(getattr(payload, "note", ""))
    if note:
        row.note = note
    row.status = _usage_status(int(row.used or 0), int(row.quota or 0))
    db.commit()
    db.refresh(row)
    return usage_to_dict(row)


# ============================================================ 商业化总览
# 上架前硬门槛（静态清单，供前端展示与人工确认，不做自动判定以免虚报）
LAUNCH_CHECKLIST = [
    {"key": "tenant_isolation", "label": "多租户隔离验收", "hint": "各业务表均带 tenant_id 并在接口层按租户过滤"},
    {"key": "backup_drill", "label": "备份恢复演练", "hint": "pg_dump 全量备份 -> 空库恢复 -> 一致性核对"},
    {"key": "load_test", "label": "并发压测", "hint": "登录 / 总览 / 列表接口并发基线，记录 P95 与错误率"},
    {"key": "signed_package", "label": "一键安装包与数字签名", "hint": "发布包签名校验，与 LMSL 一套签名策略"},
    {"key": "compliance", "label": "合规底座", "hint": "软著登记 + 授权专利 + 在审专利，EULA 与隐私政策配套"},
]

LICENSE_MODES = [
    {"key": "private", "name": "本地私有化一次性授权", "desc": "数据不出内网，按账号数 / 站点数分档，一次性买断 + 版本升级期"},
    {"key": "saas", "name": "SaaS 订阅", "desc": "云端开箱即用，按月 / 按年订阅，含 AI 调用配额"},
    {"key": "market", "name": "应用市场轻量版", "desc": "上架应用市场，轻量档位，适合单店与小团队试用转付费"},
]


def stats_overview(db: Session, tenant_id: int) -> dict:
    """商业化总览：套餐 / 授权 / 订单 / 用量 / 事件 一屏汇总。"""
    ensure_default_plans(db, tenant_id)

    plans = db.execute(select(ComPlan).where(ComPlan.tenant_id == tenant_id)).scalars().all()
    licenses = (
        db.execute(select(ComLicense).where(ComLicense.tenant_id == tenant_id)).scalars().all()
    )
    orders = db.execute(select(ComOrder).where(ComOrder.tenant_id == tenant_id)).scalars().all()

    active = [r for r in licenses if r.status == "active" and not is_expired(r.expires_at)]
    expiring = [
        r
        for r in active
        if (days_left(r.expires_at) is not None and 0 <= (days_left(r.expires_at) or 0) <= EXPIRING_SOON_DAYS)
    ]
    paid = [r for r in orders if r.status == "paid"]
    current_period = _period()
    month_paid = [r for r in paid if _naive(r.paid_at or r.created_at) and _period(_naive(r.paid_at or r.created_at)) == current_period]

    usage_rows = (
        db.execute(
            select(ComUsage).where(ComUsage.tenant_id == tenant_id, ComUsage.period == current_period)
        )
        .scalars()
        .all()
    )
    recent_orders = sorted(orders, key=lambda r: r.id or 0, reverse=True)[:5]

    return {
        "plans": {
            "total": len(plans),
            "on_sale": sum(1 for r in plans if r.status == "on" and r.is_public),
        },
        "licenses": {
            "total": len(licenses),
            "active": len(active),
            "pending": sum(1 for r in licenses if r.status == "pending"),
            "expiring_soon": len(expiring),
            "expired": sum(1 for r in licenses if r.status == "expired" or (r.status == "active" and is_expired(r.expires_at))),
            "revoked": sum(1 for r in licenses if r.status == "revoked"),
        },
        "orders": {
            "total": len(orders),
            "paid": len(paid),
            "pending": sum(1 for r in orders if r.status == "pending"),
            "revenue_total": round(sum(_f(r.amount) for r in paid), 2),
            "revenue_month": round(sum(_f(r.amount) for r in month_paid), 2),
            "recent": [order_to_dict(r) for r in recent_orders],
        },
        "usage": {
            "period": current_period,
            "warning": sum(1 for r in usage_rows if r.status == "warning"),
            "exceeded": sum(1 for r in usage_rows if r.status == "exceeded"),
            "items": [usage_to_dict(r) for r in usage_rows],
        },
        "events": list_license_events(db, tenant_id, limit=8),
        "modes": LICENSE_MODES,
        "launch_checklist": LAUNCH_CHECKLIST,
        "currency": "CNY",
    }


def entitlement(db: Session, tenant_id: int) -> dict:
    """当前租户权益：生效授权 + 套餐权益 + 本月用量对账 + 提示。"""
    licenses = (
        db.execute(
            select(ComLicense).where(
                ComLicense.tenant_id == tenant_id, ComLicense.status == "active"
            )
        )
        .scalars()
        .all()
    )
    valid = [r for r in licenses if not is_expired(r.expires_at)]

    def _rank(row: ComLicense):
        exp = _naive(row.expires_at)
        return (0 if exp is None else 1, -(exp.timestamp() if exp else 0), -(row.id or 0))

    valid.sort(key=_rank)
    current = valid[0] if valid else None
    plan = get_plan(db, tenant_id, current.plan_id) if (current and current.plan_id) else None
    period = _period()
    usage = (
        db.execute(
            select(ComUsage).where(ComUsage.tenant_id == tenant_id, ComUsage.period == period)
        )
        .scalars()
        .all()
    )

    if current is None:
        hint = "当前租户无生效授权，功能按社区版限额运行；如需解锁请在「商业化中心」下单或导入授权码"
    elif days_left(current.expires_at) is not None and (days_left(current.expires_at) or 0) <= EXPIRING_SOON_DAYS:
        hint = f"授权将于 {current.expires_at:%Y-%m-%d} 到期，建议尽快续期"
    else:
        hint = "授权正常"

    return {
        "licensed": current is not None,
        "license": license_to_dict(current, plan) if current is not None else None,
        "plan": plan_to_dict(plan) if plan is not None else None,
        "limits": {
            "seats": getattr(plan, "seats_limit", 0) or 0,
            "stores": getattr(plan, "store_limit", 0) or 0,
            "metrics": getattr(plan, "metric_limit", 0) or 0,
            "users": getattr(plan, "user_limit", 0) or 0,
            "ai_quota": getattr(plan, "ai_quota", 0) or 0,
        },
        "usage": {"period": period, "items": [usage_to_dict(r) for r in usage]},
        "hint": hint,
    }
