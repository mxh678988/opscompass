"""商业化模块（P10）：套餐定价 / 授权证书 / 订单 / 用量配额 / 授权事件留痕。

设计要点：
- 套餐 oc_com_plan：本地私有化一次性授权、SaaS 订阅、应用市场轻量版三形态统一建模，
  按门店数 / 指标量 / 账号数分档，权益以 features(JSON) 与各 *_limit 字段表达；
- 授权 oc_com_license：一次售出对应一张授权证书，落地自有数字签名（HMAC-SHA256），
  支持机器码绑定、激活、续期、吊销，是「本地部署 · 数据不出内网」的校验凭据；
- 订单 oc_com_order：从下单到支付的状态机（待支付 / 已支付 / 已取消 / 已退款）；
- 用量 oc_com_usage：按租户 + 指标 + 账期记录用量与配额，用于超额告警与续费提醒；
- 授权事件 oc_com_license_event：签发 / 激活 / 续期 / 吊销 / 校验失败全量留痕，可审计。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# ---------------------------------------------------------------- 枚举常量
# 授权形态：本地私有化 / SaaS 订阅 / 应用市场轻量版 / 试用
COM_LICENSE_TYPES = ("private", "saas", "market", "trial")
# 计费周期：一次性 / 按月 / 按年
COM_BILLING_CYCLES = ("one_time", "monthly", "yearly")
# 授权状态：待激活 / 生效 / 已过期 / 已吊销
COM_LICENSE_STATUSES = ("pending", "active", "expired", "revoked")
# 订单状态
COM_ORDER_STATUSES = ("pending", "paid", "cancelled", "refunded")
# 用量状态
COM_USAGE_STATUSES = ("normal", "warning", "exceeded")
# 授权事件动作
COM_LICENSE_ACTIONS = ("issue", "activate", "renew", "revoke", "verify_ok", "verify_failed")


class ComPlan(Base):
    """套餐/版本：定价与权益档位。"""

    __tablename__ = "oc_com_plan"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_com_plan_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    code: Mapped[str] = mapped_column(String(64), comment="套餐编码")
    name: Mapped[str] = mapped_column(String(128), comment="套餐名称")
    edition: Mapped[str] = mapped_column(
        String(32), default="private", server_default="private", comment="private|saas|market|trial"
    )
    billing_cycle: Mapped[str] = mapped_column(
        String(16), default="one_time", server_default="one_time", comment="one_time|monthly|yearly"
    )
    price: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0, server_default="0", comment="价格（元）"
    )
    currency: Mapped[str] = mapped_column(String(8), default="CNY", server_default="CNY", comment="币种")
    seats_limit: Mapped[int] = mapped_column(Integer, default=5, server_default="5", comment="账号数上限")
    store_limit: Mapped[int] = mapped_column(Integer, default=1, server_default="1", comment="站点/门店数上限")
    metric_limit: Mapped[int] = mapped_column(Integer, default=50, server_default="50", comment="指标数上限")
    user_limit: Mapped[int] = mapped_column(Integer, default=5, server_default="5", comment="并发用户上限")
    ai_quota: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="AI 调用配额（0=不限）")
    features: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="权益特性数组")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", comment="是否对外可售")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="展示排序")
    status: Mapped[str] = mapped_column(String(16), default="on", server_default="on", comment="on|off")
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ComLicense(Base):
    """授权证书：自有数字签名 + 机器码绑定，支持激活/续期/吊销。"""

    __tablename__ = "oc_com_license"
    __table_args__ = (UniqueConstraint("license_key", name="uq_com_license_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_com_plan.id", ondelete="SET NULL"), index=True, comment="套餐 ID"
    )
    license_key: Mapped[str] = mapped_column(String(128), comment="授权码")
    license_type: Mapped[str] = mapped_column(
        String(16), default="private", server_default="private", comment="private|saas|market|trial"
    )
    edition: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="版本标签")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending|active|expired|revoked"
    )
    seats: Mapped[int] = mapped_column(Integer, default=1, server_default="1", comment="授权账号数")
    machine_code: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="绑定机器码")
    issued_to: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="授权对象")
    channel: Mapped[str] = mapped_column(
        String(32), default="manual", server_default="manual", comment="manual|offline|wechat|alipay|market"
    )
    signature: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="数字签名（HMAC-SHA256）")
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="签名载荷快照")
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="签发时间")
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="激活时间")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="到期时间（空=永久）")
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ComOrder(Base):
    """订单：下单 -> 支付 -> 出证 的状态机。"""

    __tablename__ = "oc_com_order"
    __table_args__ = (UniqueConstraint("order_no", name="uq_com_order_no"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    order_no: Mapped[str] = mapped_column(String(64), comment="订单号")
    plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_com_plan.id", ondelete="SET NULL"), index=True, comment="套餐 ID"
    )
    license_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_com_license.id", ondelete="SET NULL"), index=True, comment="支付后签发的授权 ID"
    )
    plan_code: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="套餐编码快照")
    plan_name: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="套餐名称快照")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0", comment="订单金额（元）")
    currency: Mapped[str] = mapped_column(String(8), default="CNY", server_default="CNY", comment="币种")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending|paid|cancelled|refunded"
    )
    pay_channel: Mapped[str] = mapped_column(
        String(32), default="offline", server_default="offline", comment="offline|wechat|alipay|manual|market"
    )
    buyer: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="购买方")
    contact: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="联系方式")
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付时间")
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ComUsage(Base):
    """用量与配额：按租户 + 指标 + 账期对账，用于超额告警与续费提醒。"""

    __tablename__ = "oc_com_usage"
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric_key", "period", name="uq_com_usage_tk"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    metric_key: Mapped[str] = mapped_column(String(64), comment="seats|stores|metrics|api_calls|ai_tokens|storage_mb")
    period: Mapped[str] = mapped_column(String(16), comment="账期 YYYY-MM")
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="已用量")
    quota: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="配额（0=不限）")
    unit: Mapped[str] = mapped_column(String(16), default="count", server_default="count", comment="单位")
    status: Mapped[str] = mapped_column(
        String(16), default="normal", server_default="normal", comment="normal|warning|exceeded"
    )
    note: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ComLicenseEvent(Base):
    """授权事件留痕：签发 / 激活 / 续期 / 吊销 / 校验失败。"""

    __tablename__ = "oc_com_license_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    license_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("oc_com_license.id", ondelete="CASCADE"), index=True, comment="授权 ID"
    )
    license_key: Mapped[str] = mapped_column(String(128), default="", server_default="", comment="授权码快照")
    action: Mapped[str] = mapped_column(
        String(24), comment="issue|activate|renew|revoke|verify_ok|verify_failed"
    )
    detail: Mapped[str] = mapped_column(Text, default="", server_default="", comment="事件说明")
    operator: Mapped[str] = mapped_column(String(64), default="", server_default="", comment="操作人")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
