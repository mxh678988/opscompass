"""营销全渠道接入模块：渠道账号授权、投放/分发任务、渠道事件日志。

设计要点：
- 渠道凭据（API Key / Cookie / Access Token）一律经 app.core.crypto 加密后落库，
  仅保存脱敏展示串用于前端回显，绝不明文持久化、绝不明文回传。
- 投放任务记录为「本地编排记录」，真实平台 API 调用在后续版本接入（当前 dry-run）。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MarketingChannel(Base):
    """营销渠道账号：一个平台账号 = 一条记录（含授权状态与凭据密文）。"""

    __tablename__ = "oc_marketing_channel"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "channel_type", "account_name", name="uq_channel_tenant_type_account"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    channel_type: Mapped[str] = mapped_column(
        String(32),
        index=True,
        comment="douyin|xiaohongshu|wechat_official|wechat_channels|bilibili|kuaishou|weibo|zhihu|taobao|jd|pdd|douyin_shop|miniprogram|website",
    )
    channel_name: Mapped[str] = mapped_column(String(128), comment="渠道显示名（如 官方旗舰店）")
    account_name: Mapped[str] = mapped_column(String(128), comment="平台账号标识")
    auth_type: Mapped[str] = mapped_column(
        String(16), default="apikey", server_default="apikey", comment="oauth|apikey|cookie"
    )
    credential_cipher: Mapped[str] = mapped_column(
        Text, default="", server_default="", comment="凭据密文（Fernet）"
    )
    credential_masked: Mapped[str] = mapped_column(
        String(128), default="", server_default="", comment="凭据脱敏展示串"
    )
    api_base: Mapped[str] = mapped_column(
        String(256), default="", server_default="", comment="接口网关地址（可选）"
    )
    scopes: Mapped[str] = mapped_column(
        String(256), default="", server_default="", comment="授权范围，逗号分隔"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="unauthorized",
        server_default="unauthorized",
        index=True,
        comment="unauthorized|authorized|expired|disabled",
    )
    expires_at: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="授权过期时间"
    )
    last_sync_at: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="最近一次数据回传/同步时间"
    )
    auto_publish: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否允许自动发布"
    )
    remark: Mapped[str] = mapped_column(Text, default="", server_default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    campaigns: Mapped[list["ChannelCampaign"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    events: Mapped[list["ChannelEvent"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class ChannelCampaign(Base):
    """渠道投放/分发任务：内容发布、广告投放、活动推广、数据回传。"""

    __tablename__ = "oc_channel_campaign"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("oc_marketing_channel.id", ondelete="CASCADE"), index=True
    )
    website_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="关联站点 ID（可选）"
    )
    name: Mapped[str] = mapped_column(String(128), comment="任务名称")
    campaign_type: Mapped[str] = mapped_column(
        String(32), comment="content_publish|ad_delivery|promotion|data_sync"
    )
    content_title: Mapped[str] = mapped_column(String(256), default="", server_default="")
    content_body: Mapped[str] = mapped_column(Text, default="", server_default="")
    target_url: Mapped[str] = mapped_column(String(512), default="", server_default="")
    budget_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="预算（分）"
    )
    schedule_at: Mapped[str] = mapped_column(
        String(64), default="", server_default="", comment="计划执行时间"
    )
    dispatch_mode: Mapped[str] = mapped_column(
        String(16), default="manual", server_default="manual", comment="manual|auto"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="draft",
        server_default="draft",
        index=True,
        comment="draft|pending|running|success|failed|cancelled",
    )
    result: Mapped[str] = mapped_column(Text, default="", server_default="", comment="执行结果 JSON")
    error_message: Mapped[str] = mapped_column(Text, default="", server_default="")
    reach_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="曝光量")
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="点击量")
    convert_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="转化量")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    channel: Mapped["MarketingChannel"] = relationship(back_populates="campaigns")


class ChannelEvent(Base):
    """渠道事件日志：授权、发布、回调、异常。"""

    __tablename__ = "oc_channel_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True, comment="租户 ID")
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("oc_marketing_channel.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="关联投放任务 ID（可选）"
    )
    event_type: Mapped[str] = mapped_column(
        String(32), comment="create|authorize|revoke|disable|publish|sync|error"
    )
    level: Mapped[str] = mapped_column(
        String(16), default="info", server_default="info", comment="info|warning|error"
    )
    message: Mapped[str] = mapped_column(String(512), default="", server_default="")
    payload: Mapped[str] = mapped_column(Text, default="", server_default="", comment="附加 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    channel: Mapped["MarketingChannel"] = relationship(back_populates="events")
