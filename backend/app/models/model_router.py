"""M6 模型路由模型：能力声明、路由策略、降级开关、调用计量、结果缓存。

设计要点（对应 docs/os-kernel-design.md 3.6）：
- 能力声明：业务只声明「做什么」（如 emotion.classify），不指定模型；
- 路由策略：本地优先 → 本地不可用降级云端（默认关闭）→ 全不可用走规则兜底；
- 数据分级：敏感数据强制本地，禁止出网（配置项白名单控制）；
- 计量：记录调用量、耗时、失败率、tokens，供成本与容量分析；
- 缓存：相同输入指纹缓存结果，降低重复推理；
- 降级开关：一键全局降级到规则引擎，运维可在故障时快速止损；
- 硬件适配：复用既有 WMI + nvidia-smi 探测（model_hub_service），按显存分档推荐。

所有表统一 ``oc_core_`` 前缀，与既有 ``oc_`` 业务表隔离。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.kernel import ID_TYPE

# 能力类型：llm 对话补全 / embedding 向量 / classification 分类 / speech 语音
CAPABILITY_KINDS = ("llm", "embedding", "classification", "speech")
# 路由模式：local 本地 / api 云端 / rule 规则兜底
ROUTE_MODES = ("local", "api", "rule")


class CoreModelCapability(Base):
    """模型能力声明表：业务侧声明「做什么」，内核按此路由到具体模型。

    - sensitive=True：强制本地，禁止出网（数据分级红线）；
    - fallback_cloud：本地不可用时是否允许降级云端（默认 False，遵循设计文档）；
    - cost_cap：单次调用的 token 成本上限（0 表示不限制）。
    """

    __tablename__ = "oc_core_model_capability"
    __table_args__ = (
        UniqueConstraint("capability", name="uq_oc_core_model_capability_name"),
        Index("ix_oc_core_model_capability_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    capability: Mapped[str] = mapped_column(
        String(128), comment="能力标识，如 emotion.classify / text.summarize"
    )
    kind: Mapped[str] = mapped_column(
        String(32), comment="能力类型：llm / embedding / classification / speech"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), default=None, comment="能力说明"
    )
    sensitive: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否敏感数据（强制本地，禁止出网）"
    )
    fallback_cloud: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="本地不可用时是否允许降级云端"
    )
    cost_cap: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="单次调用 token 成本上限，0 表示不限制"
    )
    cache_ttl_seconds: Mapped[int] = mapped_column(
        Integer, default=300, server_default="300", comment="结果缓存 TTL（秒），0 表示不缓存"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否启用该能力"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class CoreModelRouteLog(Base):
    """模型调用计量表：记录每次路由决策与调用结果，供成本与容量分析。"""

    __tablename__ = "oc_core_model_route_log"
    __table_args__ = (
        Index("ix_oc_core_model_route_log_capability", "capability", "created_at"),
        Index("ix_oc_core_model_route_log_mode", "mode", "created_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    capability: Mapped[str] = mapped_column(
        String(128), comment="能力标识（与能力声明表对齐）"
    )
    mode: Mapped[str] = mapped_column(
        String(16), comment="本次实际路由模式：local / api / rule"
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="实际调用模型名（rule 模式为 None）"
    )
    sensitive: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="本次调用是否敏感数据"
    )
    ok: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否成功"
    )
    fallback: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否走了降级/兜底"
    )
    cached: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否命中结果缓存"
    )
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="调用耗时（毫秒）")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="输入 token 数")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="输出 token 数")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="总 token 数")
    error: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="失败原因（ok=False 时）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="调用时间"
    )


class CoreModelCache(Base):
    """模型结果缓存表：相同输入指纹（capability + input hash）命中直接返回。"""

    __tablename__ = "oc_core_model_cache"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_oc_core_model_cache_fp"),
        Index("ix_oc_core_model_cache_expire", "expires_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, comment="租户 ID")
    fingerprint: Mapped[str] = mapped_column(
        String(64), comment="输入指纹：capability + 输入内容哈希（MD5）"
    )
    capability: Mapped[str] = mapped_column(String(128), comment="能力标识")
    mode: Mapped[str] = mapped_column(String(16), comment="产生该结果的路由模式")
    model: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="产生该结果的模型名"
    )
    result: Mapped[dict] = mapped_column(JSON, comment="缓存结果（模型输出）")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="缓存时间"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, comment="过期时间（NULL 表示不过期）"
    )
