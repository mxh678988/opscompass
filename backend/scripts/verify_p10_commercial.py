"""P10 商业化中心容器内验证脚本。

覆盖：
1) 数据层：oc_com_* 五表建表与关键字段
2) 套餐：内置套餐种子、新建 / 修改 / 删除
3) 授权：签发（HMAC-SHA256 数字签名）、校验通过、篡改检出、激活、续期、吊销
4) 订单：下单 -> 支付 -> 自动签发授权
5) 用量：登记与告警判定
6) 权益：entitlement 汇总
7) 权限：模块权限码 commercial:view / commercial:manage 已注册

用法（容器内）：python scripts/verify_p10_commercial.py
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import quote

from sqlalchemy import text

from app.core.config import settings
from app.models.base import SessionLocal
from app.services import auth_service

logging.disable(logging.WARNING)

BASE = "http://127.0.0.1:8000/api/v1"
REPORT: list[tuple[str, bool, str]] = []
TOKEN: str = ""


def add(name: str, ok: bool, detail: str = "") -> None:
    REPORT.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" | {detail}" if detail else ""))


def req(method: str, path: str, body: dict | None = None, token: str | None = None):
    """发起 HTTP 请求，返回 (status_code, payload)。"""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def data_of(payload: dict):
    return (payload or {}).get("data")


# ============================================================ 1) 数据层
def step_structure(db) -> None:
    tables = [
        "oc_com_plan",
        "oc_com_license",
        "oc_com_order",
        "oc_com_usage",
        "oc_com_license_event",
    ]
    found = {
        r[0]
        for r in db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).fetchall()
    }
    missing = [t for t in tables if t not in found]
    add("五张商业化表已建", not missing, f"缺表: {missing}" if missing else f"库中总表数 {len(found)}")

    cols = {
        r[0]
        for r in db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'oc_com_license'"
            )
        ).fetchall()
    }
    need = {"license_key", "signature", "payload", "machine_code", "expires_at", "status"}
    add("授权表关键字段齐备", need.issubset(cols), f"缺字段: {sorted(need - cols)}")


# ============================================================ 2) 权限
def step_permissions(db) -> None:
    codes = set(auth_service.ALL_PERMISSION_CODES)
    need = {"commercial:view", "commercial:manage"}
    add("商业化权限码已定义", need.issubset(codes), f"缺: {sorted(need - codes)}")
    rows = db.execute(
        text("SELECT code FROM oc_permission WHERE code LIKE 'commercial:%'")
    ).fetchall()
    add("权限已落库", len(rows) >= 2, f"库中 {len(rows)} 条")


# ============================================================ 3) HTTP 全链路
def step_http() -> None:
    global TOKEN
    status, payload = req(
        "POST",
        "/auth/login",
        {"username": settings.SECURITY_ADMIN_USERNAME, "password": settings.SECURITY_ADMIN_PASSWORD},
    )
    data = data_of(payload) or {}
    TOKEN = data.get("access_token") or data.get("token") or ""
    add("管理员登录", bool(TOKEN), f"HTTP {status}")

    status, payload = req("GET", "/commercial/overview", token=TOKEN)
    overview = data_of(payload) or {}
    add(
        "商业化总览",
        status == 200 and "plans" in overview and "orders" in overview,
        f"HTTP {status} 套餐 {overview.get('plans')}",
    )

    # 套餐：种子 + 新建 + 修改
    status, payload = req("GET", "/commercial/plans", token=TOKEN)
    plans = (data_of(payload) or {}).get("items") or []
    codes = {p["code"] for p in plans}
    add("内置套餐已种入", {"community", "private_pro", "private_ent", "saas_std"}.issubset(codes), f"共 {len(plans)} 档")

    suffix = datetime.now().strftime("%H%M%S")
    custom_code = f"verify_pkg_{suffix}"
    status, payload = req(
        "POST",
        "/commercial/plans",
        {
            "code": custom_code,
            "name": "验证用套餐",
            "edition": "saas",
            "billing_cycle": "monthly",
            "price": 99,
            "seats_limit": 3,
            "store_limit": 1,
            "metric_limit": 80,
            "user_limit": 3,
            "features": ["验证特性"],
        },
        token=TOKEN,
    )
    created_plan = data_of(payload) or {}
    plan_id = created_plan.get("id")
    add("新建套餐", status == 200 and bool(plan_id), f"HTTP {status} id={plan_id}")

    status, payload = req("PATCH", f"/commercial/plans/{plan_id}", {"price": 129, "status": "off"}, token=TOKEN)
    patched = data_of(payload) or {}
    add("修改套餐", status == 200 and patched.get("price") == 129, f"HTTP {status} price={patched.get('price')}")

    # 授权：签发 + 校验
    status, payload = req(
        "POST",
        "/commercial/licenses",
        {
            "plan_id": plan_id,
            "license_type": "private",
            "seats": 3,
            "issued_to": "验证企业",
            "channel": "manual",
            "days": 365,
        },
        token=TOKEN,
    )
    license_row = data_of(payload) or {}
    license_id = license_row.get("id")
    license_key = license_row.get("license_key") or ""
    signature = license_row.get("signature") or ""
    add(
        "签发授权并写入签名",
        status == 200 and license_id is not None and len(signature) == 64,
        f"HTTP {status} key={license_key} sig={signature[:12]}...",
    )

    status, payload = req("POST", "/commercial/license/verify", {"license_key": license_key}, token=TOKEN)
    result = data_of(payload) or {}
    add("授权校验通过", status == 200 and result.get("valid") is True, f"HTTP {status} {result.get('reason')}")

    tampered = license_key[:-1] + ("0" if license_key[-1] != "0" else "1")
    status, payload = req("POST", "/commercial/license/verify", {"license_key": tampered}, token=TOKEN)
    result = data_of(payload) or {}
    add("篡改授权码被拒", result.get("valid") is False, f"reason={result.get('reason')}")

    status, payload = req(
        "POST", f"/commercial/licenses/{license_id}/activate?machine_code=PC-{suffix}", token=TOKEN
    )
    activated = data_of(payload) or {}
    add(
        "激活并绑定机器码",
        status == 200 and activated.get("status") == "active",
        f"HTTP {status} status={activated.get('status')}",
    )

    status, payload = req("POST", "/commercial/license/verify", {"license_key": license_key, "machine_code": "OTHER-PC"}, token=TOKEN)
    result = data_of(payload) or {}
    add("机器码不匹配被拒", result.get("valid") is False, f"reason={result.get('reason')}")

    status, payload = req("POST", f"/commercial/licenses/{license_id}/renew", {"days": 365}, token=TOKEN)
    renewed = data_of(payload) or {}
    add(
        "续期并重算签名",
        status == 200 and renewed.get("days_left") is not None and renewed.get("days_left") > 365,
        f"HTTP {status} days_left={renewed.get('days_left')}",
    )

    # 订单：下单 -> 支付 -> 自动发证
    status, payload = req(
        "POST",
        "/commercial/orders",
        {"plan_id": plan_id, "buyer": "验证企业", "contact": "13800000000", "pay_channel": "offline"},
        token=TOKEN,
    )
    order = data_of(payload) or {}
    order_id = order.get("id")
    add("创建订单", status == 200 and order.get("status") == "pending", f"HTTP {status} no={order.get('order_no')}")

    status, payload = req(
        "POST",
        f"/commercial/orders/{order_id}/pay",
        {"pay_channel": "wechat", "machine_code": f"PC-PAY-{suffix}", "days": 365},
        token=TOKEN,
    )
    paid = data_of(payload) or {}
    add(
        "订单支付并自动发证",
        status == 200 and paid.get("status") == "paid" and paid.get("license_id"),
        f"HTTP {status} license_id={paid.get('license_id')}",
    )

    # 用量
    status, payload = req(
        "POST",
        "/commercial/usage",
        {
            "metric_key": "seats",
            "period": datetime.now().strftime("%Y-%m"),
            "used": 8,
            "quota": 10,
            "unit": "count",
        },
        token=TOKEN,
    )
    usage_row = data_of(payload) or {}
    add("用量登记与告警判定", status == 200 and usage_row.get("status") == "warning", f"HTTP {status} status={usage_row.get('status')} ratio={usage_row.get('ratio')}")

    # 权益
    status, payload = req("GET", "/commercial/entitlement", token=TOKEN)
    ent = data_of(payload) or {}
    add(
        "当前权益汇总",
        status == 200 and ent.get("licensed") is True and ent.get("plan") is not None,
        f"HTTP {status} hint={ent.get('hint')}",
    )

    # 事件留痕
    status, payload = req("GET", "/commercial/events?limit=20", token=TOKEN)
    events = (data_of(payload) or {}).get("items") or []
    actions = {e["action"] for e in events}
    add(
        "授权事件留痕",
        {"issue", "activate", "renew", "verify_ok", "verify_failed"}.issubset(actions),
        f"共 {len(events)} 条 {sorted(actions)}",
    )

    # 吊销
    status, payload = req(
        "POST",
        f"/commercial/licenses/{license_id}/revoke?reason={quote('验证吊销')}",
        token=TOKEN,
    )
    revoked = data_of(payload) or {}
    add(
        "吊销授权",
        status == 200 and revoked.get("status") == "revoked",
        f"HTTP {status} {payload.get('error', '')}",
    )

    status, payload = req("POST", "/commercial/license/verify", {"license_key": license_key}, token=TOKEN)
    result = data_of(payload) or {}
    add("已吊销授权校验失败", result.get("valid") is False, f"reason={result.get('reason')}")

    # 删除套餐（无授权引用）
    status, payload = req("DELETE", f"/commercial/plans/{plan_id}", token=TOKEN)
    add("已签发授权的套餐不可删", status == 400, f"HTTP {status} {payload.get('detail')}")

    # 内置套餐不可删
    status, payload = req("GET", "/commercial/plans", token=TOKEN)
    plans = (data_of(payload) or {}).get("items") or []
    pro = next((p for p in plans if p["code"] == "private_pro"), None)
    if pro is not None:
        status, payload = req("DELETE", f"/commercial/plans/{pro['id']}", token=TOKEN)
        add("内置套餐不可删", status == 400, f"HTTP {status} {payload.get('detail')}")
    else:
        add("内置套餐不可删", False, "未找到 private_pro 套餐")

    # 无引用的自定义套餐可删
    status, payload = req(
        "POST",
        "/commercial/plans",
        {
            "code": f"verify_tmp_{suffix}",
            "name": "验证用临时套餐",
            "edition": "saas",
            "billing_cycle": "monthly",
            "price": 9,
            "seats_limit": 1,
            "store_limit": 1,
            "metric_limit": 10,
            "user_limit": 1,
            "features": [],
        },
        token=TOKEN,
    )
    tmp_plan_id = (data_of(payload) or {}).get("id")
    status, payload = req("DELETE", f"/commercial/plans/{tmp_plan_id}", token=TOKEN)
    add("删除未被引用的套餐", status == 200, f"HTTP {status}")


def main() -> int:
    print("=" * 72)
    print("P10 商业化中心验证")
    print("=" * 72)

    db = SessionLocal()
    try:
        step_structure(db)
        step_permissions(db)
    finally:
        db.close()

    step_http()

    passed = sum(1 for _, ok, _ in REPORT if ok)
    total = len(REPORT)
    print("-" * 72)
    print(f"结果：{passed}/{total} 通过")
    failed = [name for name, ok, _ in REPORT if not ok]
    if failed:
        print("未通过：" + "、".join(failed))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
