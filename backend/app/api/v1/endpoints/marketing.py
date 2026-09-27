"""营销全渠道接入 API 路由：渠道授权、投放/分发任务、渠道事件日志。

说明：
- 渠道凭据以 Fernet 对称加密落库，接口仅返回脱敏串，不回显明文；
- 投放任务执行为「本地编排 + 演练记录」（dry-run），未调用真实平台 API，
  结果 JSON 中显式标注 simulated=true，指标位保持 0，不编造平台回传数据。
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.core.crypto import encrypt
from app.models import ChannelCampaign, ChannelEvent, MarketingChannel
from app.models.base import get_db
from app.schemas.common import ApiResponse, PageResult
from app.schemas.marketing import (
    ChannelCampaignOut,
    ChannelEventOut,
    ChannelTypeOut,
    MarketingChannelOut,
    MarketingOverviewOut,
)

router = APIRouter(prefix="/marketing", tags=["营销渠道"])

# ------------------------------------------------------ 渠道类型目录
# (type, 名称, 分类, 授权方式, 平台能力, 开放平台)
CHANNEL_TYPES: list[tuple[str, str, str, list[str], list[str], str]] = [
    ("douyin", "抖音", "video", ["oauth"], ["content_publish", "ad_delivery", "data_sync"], "抖音开放平台"),
    ("douyin_shop", "抖音小店", "shop", ["oauth"], ["product_sync", "ad_delivery", "data_sync"], "抖店开放平台"),
    ("xiaohongshu", "小红书", "social", ["oauth", "cookie"], ["content_publish", "data_sync"], "小红书开放平台"),
    ("wechat_official", "微信公众号", "content", ["apikey"], ["content_publish", "data_sync"], "微信公众平台"),
    ("wechat_channels", "微信视频号", "video", ["oauth"], ["content_publish", "data_sync"], "微信开放平台"),
    ("miniprogram", "微信小程序", "content", ["apikey"], ["content_publish", "data_sync"], "微信开放平台"),
    ("bilibili", "哔哩哔哩", "video", ["oauth"], ["content_publish", "data_sync"], "哔哩哔哩开放平台"),
    ("kuaishou", "快手", "video", ["oauth"], ["content_publish", "ad_delivery", "data_sync"], "快手开放平台"),
    ("weibo", "微博", "social", ["oauth"], ["content_publish", "ad_delivery", "data_sync"], "微博开放平台"),
    ("zhihu", "知乎", "content", ["oauth", "apikey"], ["content_publish", "data_sync"], "知乎开放平台"),
    ("taobao", "淘宝/天猫", "shop", ["oauth"], ["product_sync", "ad_delivery", "data_sync"], "淘宝开放平台"),
    ("jd", "京东", "shop", ["oauth"], ["product_sync", "ad_delivery", "data_sync"], "京东宙斯开放平台"),
    ("pdd", "拼多多", "shop", ["oauth"], ["product_sync", "ad_delivery", "data_sync"], "拼多多开放平台"),
    ("website", "自有网站", "self_hosted", ["apikey", "cookie"], ["content_publish", "data_sync"], "自有站点"),
]
CHANNEL_TYPE_MAP = {t[0]: t for t in CHANNEL_TYPES}

CAMPAIGN_TYPES = ["content_publish", "ad_delivery", "promotion", "data_sync"]

AUTH_TYPES = ["oauth", "apikey", "cookie"]

CHANNEL_STATUSES = ["unauthorized", "authorized", "expired", "disabled"]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _mask(value: str) -> str:
    """凭据脱敏：仅保留头尾少量字符。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}{'*' * 6}{value[-4:]}"


def _log_event(
    db: Session,
    tenant_id: int,
    channel_id: int,
    event_type: str,
    message: str,
    level: str = "info",
    campaign_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> ChannelEvent:
    """写入渠道事件日志。"""
    event = ChannelEvent(
        tenant_id=tenant_id,
        channel_id=channel_id,
        campaign_id=campaign_id,
        event_type=event_type,
        level=level,
        message=message[:512],
        payload=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(event)
    db.flush()
    return event


def _get_channel(db: Session, tenant_id: int, channel_id: int) -> MarketingChannel:
    channel = db.execute(
        select(MarketingChannel).where(
            MarketingChannel.id == channel_id, MarketingChannel.tenant_id == tenant_id
        )
    ).scalars().first()
    if channel is None:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return channel


def _get_campaign(db: Session, tenant_id: int, campaign_id: int) -> ChannelCampaign:
    campaign = db.execute(
        select(ChannelCampaign).where(
            ChannelCampaign.id == campaign_id, ChannelCampaign.tenant_id == tenant_id
        )
    ).scalars().first()
    if campaign is None:
        raise HTTPException(status_code=404, detail="投放任务不存在")
    return campaign


# ====================== 渠道类型目录 ======================

@router.get("/channel-types", response_model=ApiResponse[list[ChannelTypeOut]], summary="渠道类型目录")
def list_channel_types(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[list[ChannelTypeOut]]:
    """返回可接入的平台类型、授权方式与能力，并统计本租户已接入/已授权数量。"""
    rows = db.execute(
        select(MarketingChannel).where(MarketingChannel.tenant_id == tenant_id)
    ).scalars().all()
    connected: dict[str, int] = {}
    authorized: dict[str, int] = {}
    for row in rows:
        connected[row.channel_type] = connected.get(row.channel_type, 0) + 1
        if row.status == "authorized":
            authorized[row.channel_type] = authorized.get(row.channel_type, 0) + 1

    data = [
        ChannelTypeOut(
            channel_type=ctype,
            name=name,
            category=category,
            auth_modes=auth_modes,
            abilities=abilities,
            platform=platform,
            connected=connected.get(ctype, 0),
            authorized=authorized.get(ctype, 0),
        )
        for ctype, name, category, auth_modes, abilities, platform in CHANNEL_TYPES
    ]
    return ApiResponse[list[ChannelTypeOut]](data=data)


# ====================== 接入概览 ======================

@router.get("/overview", response_model=ApiResponse[MarketingOverviewOut], summary="渠道接入概览")
def marketing_overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MarketingOverviewOut]:
    channels = db.execute(
        select(MarketingChannel).where(MarketingChannel.tenant_id == tenant_id)
    ).scalars().all()
    campaigns = db.execute(
        select(ChannelCampaign).where(ChannelCampaign.tenant_id == tenant_id)
    ).scalars().all()

    def _count_status(items, status: str) -> int:
        return sum(1 for i in items if i.status == status)

    events_total = int(
        db.execute(
            select(func.count(ChannelEvent.id)).where(ChannelEvent.tenant_id == tenant_id)
        ).scalar()
        or 0
    )
    connected: dict[str, int] = {}
    authorized: dict[str, int] = {}
    for row in channels:
        connected[row.channel_type] = connected.get(row.channel_type, 0) + 1
        if row.status == "authorized":
            authorized[row.channel_type] = authorized.get(row.channel_type, 0) + 1

    coverage = [
        ChannelTypeOut(
            channel_type=ctype,
            name=name,
            category=category,
            auth_modes=auth_modes,
            abilities=abilities,
            platform=platform,
            connected=connected.get(ctype, 0),
            authorized=authorized.get(ctype, 0),
        )
        for ctype, name, category, auth_modes, abilities, platform in CHANNEL_TYPES
        if connected.get(ctype, 0) > 0
    ]

    data = MarketingOverviewOut(
        channels_total=len(channels),
        channels_authorized=_count_status(channels, "authorized"),
        channels_unauthorized=_count_status(channels, "unauthorized"),
        channels_expired=_count_status(channels, "expired"),
        channels_disabled=_count_status(channels, "disabled"),
        campaigns_total=len(campaigns),
        campaigns_pending=_count_status(campaigns, "pending") + _count_status(campaigns, "running"),
        campaigns_success=_count_status(campaigns, "success"),
        campaigns_failed=_count_status(campaigns, "failed"),
        events_total=events_total,
        covered_types=sorted(connected.keys()),
        type_coverage=coverage,
    )
    return ApiResponse[MarketingOverviewOut](data=data)


# ====================== 渠道账号 ======================

class ChannelCreate(BaseModel):
    channel_type: str = Field(..., description="平台类型，见 /channel-types")
    channel_name: str = Field(..., max_length=128, description="渠道显示名")
    account_name: str = Field(..., max_length=128, description="平台账号标识")
    auth_type: str = Field("apikey", description="oauth|apikey|cookie")
    api_base: str = Field("", max_length=256, description="接口网关地址（可选）")
    scopes: str = Field("", max_length=256, description="授权范围，逗号分隔")
    auto_publish: bool = Field(False, description="是否允许自动发布")
    remark: str = Field("", description="备注")
    credential: Optional[str] = Field(None, description="凭据明文，仅写入不回显；留空表示先建后授权")


class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    account_name: Optional[str] = None
    auth_type: Optional[str] = None
    api_base: Optional[str] = None
    scopes: Optional[str] = None
    auto_publish: Optional[bool] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class AuthorizePayload(BaseModel):
    credential: str = Field(..., description="Access Token / API Key / Cookie 明文")
    auth_type: Optional[str] = Field(None, description="覆盖授权方式")
    expires_at: str = Field("", description="授权过期时间（展示用）")
    scopes: str = Field("", max_length=256, description="授权范围")


@router.post("/channels", response_model=ApiResponse[MarketingChannelOut], summary="新增渠道账号")
def create_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MarketingChannelOut]:
    if payload.channel_type not in CHANNEL_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的渠道类型: {payload.channel_type}")
    if payload.auth_type not in AUTH_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的授权方式: {payload.auth_type}")

    exists = db.execute(
        select(MarketingChannel).where(
            MarketingChannel.tenant_id == tenant_id,
            MarketingChannel.channel_type == payload.channel_type,
            MarketingChannel.account_name == payload.account_name,
        )
    ).scalars().first()
    if exists is not None:
        raise HTTPException(status_code=400, detail="同类型下该账号已存在")

    channel = MarketingChannel(
        tenant_id=tenant_id,
        channel_type=payload.channel_type,
        channel_name=payload.channel_name,
        account_name=payload.account_name,
        auth_type=payload.auth_type,
        api_base=payload.api_base,
        scopes=payload.scopes,
        auto_publish=payload.auto_publish,
        remark=payload.remark,
        status="unauthorized",
    )
    if payload.credential:
        channel.credential_cipher = encrypt(payload.credential)
        channel.credential_masked = _mask(payload.credential)
        channel.status = "authorized"
    db.add(channel)
    db.flush()
    _log_event(
        db,
        tenant_id,
        channel.id,
        "create",
        f"新增渠道账号 {payload.channel_name}（{payload.account_name}）",
        payload={"channel_type": payload.channel_type, "authorized": bool(payload.credential)},
    )
    if payload.credential:
        _log_event(db, tenant_id, channel.id, "authorize", "创建时写入凭据，授权状态置为已授权")
    db.commit()
    db.refresh(channel)
    return ApiResponse[MarketingChannelOut](data=channel)


@router.get("/channels", response_model=ApiResponse[PageResult[MarketingChannelOut]], summary="渠道列表")
def list_channels(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    channel_type: Optional[str] = Query(None, description="按平台类型筛选"),
    status: Optional[str] = Query(None, description="按授权状态筛选"),
    keyword: Optional[str] = Query(None, description="名称/账号模糊匹配"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> ApiResponse[PageResult[MarketingChannelOut]]:
    stmt = select(MarketingChannel).where(MarketingChannel.tenant_id == tenant_id)
    if channel_type:
        stmt = stmt.where(MarketingChannel.channel_type == channel_type)
    if status:
        stmt = stmt.where(MarketingChannel.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            MarketingChannel.channel_name.like(like) | MarketingChannel.account_name.like(like)
        )

    total = int(
        db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    )
    rows = db.execute(
        stmt.order_by(MarketingChannel.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    data = PageResult[MarketingChannelOut](
        total=total,
        page=page,
        page_size=page_size,
        items=[MarketingChannelOut.model_validate(r) for r in rows],
    )
    return ApiResponse[PageResult[MarketingChannelOut]](data=data)


@router.put("/channels/{channel_id}", response_model=ApiResponse[MarketingChannelOut], summary="编辑渠道账号")
def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MarketingChannelOut]:
    channel = _get_channel(db, tenant_id, channel_id)
    fields = payload.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in CHANNEL_STATUSES:
        raise HTTPException(status_code=400, detail=f"不支持的状态: {fields['status']}")
    if "auth_type" in fields and fields["auth_type"] not in AUTH_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的授权方式: {fields['auth_type']}")

    disabled = fields.get("status") == "disabled"
    for key, value in fields.items():
        setattr(channel, key, value)
    db.flush()
    if disabled:
        _log_event(db, tenant_id, channel.id, "disable", "渠道已停用，不再参与投放编排", level="warning")
    db.commit()
    db.refresh(channel)
    return ApiResponse[MarketingChannelOut](data=channel)


@router.delete("/channels/{channel_id}", response_model=ApiResponse[dict], summary="删除渠道账号")
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    channel = _get_channel(db, tenant_id, channel_id)
    db.delete(channel)
    db.commit()
    return ApiResponse[dict](data={"id": channel_id, "deleted": True})


@router.post(
    "/channels/{channel_id}/authorize",
    response_model=ApiResponse[MarketingChannelOut],
    summary="写入凭据并授权",
)
def authorize_channel(
    channel_id: int,
    payload: AuthorizePayload,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MarketingChannelOut]:
    channel = _get_channel(db, tenant_id, channel_id)
    credential = payload.credential.strip()
    if not credential:
        raise HTTPException(status_code=400, detail="凭据不能为空")
    if payload.auth_type:
        if payload.auth_type not in AUTH_TYPES:
            raise HTTPException(status_code=400, detail=f"不支持的授权方式: {payload.auth_type}")
        channel.auth_type = payload.auth_type
    channel.credential_cipher = encrypt(credential)
    channel.credential_masked = _mask(credential)
    channel.status = "authorized"
    if payload.expires_at:
        channel.expires_at = payload.expires_at
    if payload.scopes:
        channel.scopes = payload.scopes
    _log_event(
        db,
        tenant_id,
        channel.id,
        "authorize",
        f"渠道 {channel.channel_name} 已完成授权（凭据已加密存储）",
        payload={"auth_type": channel.auth_type, "masked": channel.credential_masked},
    )
    db.commit()
    db.refresh(channel)
    return ApiResponse[MarketingChannelOut](data=channel)


@router.post(
    "/channels/{channel_id}/revoke",
    response_model=ApiResponse[MarketingChannelOut],
    summary="撤销授权",
)
def revoke_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MarketingChannelOut]:
    channel = _get_channel(db, tenant_id, channel_id)
    channel.credential_cipher = ""
    channel.credential_masked = ""
    channel.status = "unauthorized"
    _log_event(db, tenant_id, channel.id, "revoke", "已撤销授权并清除本地凭据", level="warning")
    db.commit()
    db.refresh(channel)
    return ApiResponse[MarketingChannelOut](data=channel)


@router.post(
    "/channels/{channel_id}/sync",
    response_model=ApiResponse[MarketingChannelOut],
    summary="触发渠道数据同步",
)
def sync_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MarketingChannelOut]:
    channel = _get_channel(db, tenant_id, channel_id)
    if channel.status != "authorized":
        raise HTTPException(status_code=400, detail="渠道未授权，无法同步数据")
    channel.last_sync_at = _now()
    _log_event(
        db,
        tenant_id,
        channel.id,
        "sync",
        "已触发渠道数据同步（接入骨架：等待平台 API 联调）",
        payload={"dry_run": True},
    )
    db.commit()
    db.refresh(channel)
    return ApiResponse[MarketingChannelOut](data=channel)


# ====================== 投放 / 分发任务 ======================

class CampaignCreate(BaseModel):
    channel_id: int = Field(..., description="目标渠道 ID")
    name: str = Field(..., max_length=128, description="任务名称")
    campaign_type: str = Field("content_publish", description="content_publish|ad_delivery|promotion|data_sync")
    website_id: Optional[int] = Field(None, description="关联站点 ID（可选）")
    content_title: str = Field("", max_length=256)
    content_body: str = Field("")
    target_url: str = Field("", max_length=512)
    budget_cents: int = Field(0, ge=0, description="预算（分）")
    schedule_at: str = Field("", description="计划执行时间")
    dispatch_mode: str = Field("manual", description="manual|auto")


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    campaign_type: Optional[str] = None
    website_id: Optional[int] = None
    content_title: Optional[str] = None
    content_body: Optional[str] = None
    target_url: Optional[str] = None
    budget_cents: Optional[int] = None
    schedule_at: Optional[str] = None
    dispatch_mode: Optional[str] = None
    status: Optional[str] = None


@router.post("/campaigns", response_model=ApiResponse[ChannelCampaignOut], summary="创建投放任务")
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ChannelCampaignOut]:
    _get_channel(db, tenant_id, payload.channel_id)
    if payload.campaign_type not in CAMPAIGN_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的任务类型: {payload.campaign_type}")
    campaign = ChannelCampaign(
        tenant_id=tenant_id,
        channel_id=payload.channel_id,
        website_id=payload.website_id,
        name=payload.name,
        campaign_type=payload.campaign_type,
        content_title=payload.content_title,
        content_body=payload.content_body,
        target_url=payload.target_url,
        budget_cents=payload.budget_cents,
        schedule_at=payload.schedule_at,
        dispatch_mode=payload.dispatch_mode,
        status="pending" if payload.dispatch_mode == "auto" else "draft",
    )
    db.add(campaign)
    db.flush()
    _log_event(
        db,
        tenant_id,
        payload.channel_id,
        "create",
        f"创建投放任务「{payload.name}」",
        campaign_id=campaign.id,
        payload={"campaign_type": payload.campaign_type},
    )
    db.commit()
    db.refresh(campaign)
    return ApiResponse[ChannelCampaignOut](data=campaign)


@router.get("/campaigns", response_model=ApiResponse[PageResult[ChannelCampaignOut]], summary="投放任务列表")
def list_campaigns(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    channel_id: Optional[int] = Query(None, description="按渠道筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> ApiResponse[PageResult[ChannelCampaignOut]]:
    stmt = select(ChannelCampaign).where(ChannelCampaign.tenant_id == tenant_id)
    if channel_id:
        stmt = stmt.where(ChannelCampaign.channel_id == channel_id)
    if status:
        stmt = stmt.where(ChannelCampaign.status == status)

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)
    rows = db.execute(
        stmt.order_by(ChannelCampaign.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    data = PageResult[ChannelCampaignOut](
        total=total,
        page=page,
        page_size=page_size,
        items=[ChannelCampaignOut.model_validate(r) for r in rows],
    )
    return ApiResponse[PageResult[ChannelCampaignOut]](data=data)


@router.put("/campaigns/{campaign_id}", response_model=ApiResponse[ChannelCampaignOut], summary="编辑投放任务")
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ChannelCampaignOut]:
    campaign = _get_campaign(db, tenant_id, campaign_id)
    if campaign.status in ("running", "success"):
        raise HTTPException(status_code=400, detail="任务已执行，不可编辑；请先取消或新建任务")
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("campaign_type") and fields["campaign_type"] not in CAMPAIGN_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的任务类型: {fields['campaign_type']}")
    for key, value in fields.items():
        setattr(campaign, key, value)
    db.commit()
    db.refresh(campaign)
    return ApiResponse[ChannelCampaignOut](data=campaign)


@router.delete("/campaigns/{campaign_id}", response_model=ApiResponse[dict], summary="删除投放任务")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    campaign = _get_campaign(db, tenant_id, campaign_id)
    db.delete(campaign)
    db.commit()
    return ApiResponse[dict](data={"id": campaign_id, "deleted": True})


@router.post(
    "/campaigns/{campaign_id}/execute",
    response_model=ApiResponse[ChannelCampaignOut],
    summary="执行投放任务（本地演练）",
)
def execute_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ChannelCampaignOut]:
    """执行投放编排。

    当前版本为接入骨架：仅校验渠道授权状态并记录演练结果（simulated=true），
    未调用任何平台真实 API，因此不写入曝光/点击/转化等平台回传指标。
    """
    campaign = _get_campaign(db, tenant_id, campaign_id)
    channel = _get_channel(db, tenant_id, campaign.channel_id)
    if channel.status != "authorized":
        campaign.status = "failed"
        campaign.error_message = "渠道未授权，无法执行投放"
        _log_event(
            db,
            tenant_id,
            channel.id,
            "error",
            f"投放任务「{campaign.name}」执行失败：渠道未授权",
            level="error",
            campaign_id=campaign.id,
        )
        db.commit()
        raise HTTPException(status_code=400, detail="渠道未授权，无法执行投放")

    campaign.status = "success"
    campaign.error_message = ""
    campaign.result = json.dumps(
        {
            "simulated": True,
            "stage": "local_orchestration",
            "note": "接入骨架：已完成本地编排与凭据校验，未调用平台真实 API",
            "channel_type": channel.channel_type,
            "campaign_type": campaign.campaign_type,
            "executed_at": _now(),
        },
        ensure_ascii=False,
    )
    _log_event(
        db,
        tenant_id,
        channel.id,
        "publish",
        f"投放任务「{campaign.name}」已完成本地编排（演练，未调用平台 API）",
        campaign_id=campaign.id,
        payload={"simulated": True, "campaign_type": campaign.campaign_type},
    )
    db.commit()
    db.refresh(campaign)
    return ApiResponse[ChannelCampaignOut](data=campaign)


# ====================== 事件日志 ======================

@router.get("/events", response_model=ApiResponse[list[ChannelEventOut]], summary="渠道事件日志")
def list_events(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    channel_id: Optional[int] = Query(None, description="按渠道筛选"),
    limit: int = Query(50, ge=1, le=200),
) -> ApiResponse[list[ChannelEventOut]]:
    stmt = select(ChannelEvent).where(ChannelEvent.tenant_id == tenant_id)
    if channel_id:
        stmt = stmt.where(ChannelEvent.channel_id == channel_id)
    rows = db.execute(stmt.order_by(ChannelEvent.id.desc()).limit(limit)).scalars().all()
    return ApiResponse[list[ChannelEventOut]](
        data=[ChannelEventOut.model_validate(r) for r in rows]
    )
