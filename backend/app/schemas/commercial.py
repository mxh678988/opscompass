"""商业化模块（P10）请求/响应模型：套餐 / 授权 / 订单 / 用量。"""

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- 套餐
class PlanIn(BaseModel):
    """新建套餐。"""

    code: str = Field(..., max_length=64, description="套餐编码")
    name: str = Field(..., max_length=128, description="套餐名称")
    edition: str = Field(default="private", max_length=32, description="private|saas|market|trial")
    billing_cycle: str = Field(default="one_time", max_length=16, description="one_time|monthly|yearly")
    price: float = Field(default=0, ge=0, description="价格（元）")
    currency: str = Field(default="CNY", max_length=8)
    seats_limit: int = Field(default=5, ge=0, description="账号数上限")
    store_limit: int = Field(default=1, ge=0, description="站点/门店数上限")
    metric_limit: int = Field(default=50, ge=0, description="指标数上限")
    user_limit: int = Field(default=5, ge=0, description="并发用户上限")
    ai_quota: int = Field(default=0, ge=0, description="AI 调用配额（0=不限）")
    features: list[str] = Field(default_factory=list, description="权益特性数组")
    is_public: bool = True
    sort: int = 0
    status: str = Field(default="on", max_length=16, description="on|off")
    remark: str = ""


class PlanPatch(BaseModel):
    """修改套餐（仅传需变更字段）。"""

    name: Optional[str] = Field(default=None, max_length=128)
    edition: Optional[str] = Field(default=None, max_length=32)
    billing_cycle: Optional[str] = Field(default=None, max_length=16)
    price: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=8)
    seats_limit: Optional[int] = Field(default=None, ge=0)
    store_limit: Optional[int] = Field(default=None, ge=0)
    metric_limit: Optional[int] = Field(default=None, ge=0)
    user_limit: Optional[int] = Field(default=None, ge=0)
    ai_quota: Optional[int] = Field(default=None, ge=0)
    features: Optional[list[str]] = None
    is_public: Optional[bool] = None
    sort: Optional[int] = None
    status: Optional[str] = Field(default=None, max_length=16)
    remark: Optional[str] = None


# ---------------------------------------------------------------- 授权
class LicenseIn(BaseModel):
    """签发授权证书。"""

    plan_id: Optional[int] = None
    license_type: str = Field(default="private", max_length=16, description="private|saas|market|trial")
    seats: int = Field(default=1, ge=1, description="授权账号数")
    machine_code: str = Field(default="", max_length=128, description="绑定机器码（空=不绑定）")
    issued_to: str = Field(default="", max_length=128, description="授权对象")
    channel: str = Field(default="manual", max_length=32)
    days: int = Field(default=365, ge=0, description="有效期天数（0=永久）")
    remark: str = ""


class LicenseRenewIn(BaseModel):
    """续期授权。"""

    days: int = Field(default=365, ge=1, description="续期天数")
    remark: str = ""


class LicenseVerifyIn(BaseModel):
    """授权校验（本地/离线场景由调用方直接提交授权码）。"""

    license_key: str = Field(..., max_length=128)
    machine_code: str = Field(default="", max_length=128)


# ---------------------------------------------------------------- 订单
class OrderIn(BaseModel):
    """创建订单。"""

    plan_id: int
    buyer: str = Field(default="", max_length=128)
    contact: str = Field(default="", max_length=128)
    pay_channel: str = Field(default="offline", max_length=32)
    remark: str = ""


class OrderPayIn(BaseModel):
    """订单支付（支付后自动签发授权）。"""

    pay_channel: str = Field(default="offline", max_length=32)
    machine_code: str = Field(default="", max_length=128, description="下单方机器码（用于绑定授权）")
    days: int = Field(default=365, ge=0, description="授权有效期天数（0=永久）")
    remark: str = ""


# ---------------------------------------------------------------- 用量
class UsageIn(BaseModel):
    """登记/更新用量。"""

    metric_key: str = Field(..., max_length=64)
    period: str = Field(..., max_length=16, description="账期 YYYY-MM")
    used: Optional[int] = Field(default=None, ge=0, description="已用量（为空时按 delta 累加）")
    delta: int = Field(default=0, description="增量（used 为空时生效）")
    quota: Optional[int] = Field(default=None, ge=0, description="配额（0=不限）")
    unit: str = Field(default="count", max_length=16)
    note: str = ""
