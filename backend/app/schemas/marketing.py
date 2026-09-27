"""营销全渠道接入：响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MarketingChannelOut(BaseModel):
    """渠道账号（凭据仅返回脱敏串）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    channel_type: str
    channel_name: str
    account_name: str
    auth_type: str
    credential_masked: str = ""
    api_base: str = ""
    scopes: str = ""
    status: str
    expires_at: str = ""
    last_sync_at: str = ""
    auto_publish: bool = False
    remark: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChannelCampaignOut(BaseModel):
    """渠道投放/分发任务。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    channel_id: int
    website_id: Optional[int] = None
    name: str
    campaign_type: str
    content_title: str = ""
    content_body: str = ""
    target_url: str = ""
    budget_cents: int = 0
    schedule_at: str = ""
    dispatch_mode: str = "manual"
    status: str
    result: str = ""
    error_message: str = ""
    reach_count: int = 0
    click_count: int = 0
    convert_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChannelEventOut(BaseModel):
    """渠道事件日志。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    channel_id: int
    campaign_id: Optional[int] = None
    event_type: str
    level: str = "info"
    message: str = ""
    payload: str = ""
    created_at: Optional[datetime] = None


class ChannelTypeOut(BaseModel):
    """渠道类型目录项：授权方式与平台能力。"""

    channel_type: str
    name: str
    category: str
    auth_modes: list[str] = []
    abilities: list[str] = []
    platform: str = ""
    connected: int = 0
    authorized: int = 0


class MarketingOverviewOut(BaseModel):
    """营销渠道接入概览。"""

    channels_total: int = 0
    channels_authorized: int = 0
    channels_unauthorized: int = 0
    channels_expired: int = 0
    channels_disabled: int = 0
    campaigns_total: int = 0
    campaigns_pending: int = 0
    campaigns_success: int = 0
    campaigns_failed: int = 0
    events_total: int = 0
    covered_types: list[str] = []
    type_coverage: list[ChannelTypeOut] = []
