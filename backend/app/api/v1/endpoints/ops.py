"""运营参谋模块 API 路由：网站/网店管理、SEO、GEO、AI 智能设置、自媒体、媒体库。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_id
from app.models.base import get_db
from app.models import (
    Website,
    WebsitePage,
    ProductItem,
    SeoTask,
    PageSeoTask,
    GeoTask,
    WebsiteAiConfig,
    MediaItem,
    PageMediaRef,
)
from app.schemas.ops import (
    WebsiteOut,
    WebsitePageOut,
    ProductItemOut,
    SeoTaskOut,
    GeoTaskOut,
    WebsiteAiConfigOut,
    MediaItemOut,
    CrawlResultOut,
)
from app.services.ai.ops_assistant import (
    create_website,
    list_websites,
    update_website,
    create_page,
    update_page,
    create_product,
    update_product,
    run_seo_task,
    run_geo_task,
    save_ai_config,
    get_ai_config,
    update_ai_config,
    ai_content_optimize,
    ai_seo_analysis,
    ai_generate_content,
    create_media,
    list_media,
    update_media,
    delete_media,
    ai_social_optimize,
    ai_social_schedule,
    ai_social_analytics,
)
from app.services.ai.site_crawler import CrawlError, build_target_url, crawl
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/ops", tags=["运营参谋"])


# ====================== 网站/网店 ======================

class WebsiteCreate(BaseModel):
    site_name: str = Field(..., max_length=128, description="网站名称")
    site_url: str = Field(..., max_length=512, description="站点 URL")
    site_type: str = Field("cms", description="类型: cms|shop|blog|landing|custom")
    theme: str = Field("", max_length=128, description="主题名称")
    status: str = Field("draft", description="draft|published|archived")
    language: str = Field("zh-CN", description="站点语言")
    description: str = Field("", description="站点描述")
    ai_enabled: bool = Field(True, description="AI 运营开关")
    ai_mode: str = Field("local", description="ai/local")


class WebsiteUpdate(BaseModel):
    site_name: Optional[str] = None
    site_url: Optional[str] = None
    site_type: Optional[str] = None
    theme: Optional[str] = None
    status: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    ai_enabled: Optional[bool] = None
    ai_mode: Optional[str] = None


@router.post("/websites", response_model=ApiResponse[WebsiteOut], summary="创建网站/网店")
def create_new_website(
    payload: WebsiteCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsiteOut]:
    website = create_website(db, tenant_id, **payload.dict())
    return ApiResponse[WebsiteOut](data=website)


@router.get("/websites", response_model=ApiResponse[list[WebsiteOut]], summary="网站列表")
def list_websites_endpoint(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    site_type: Optional[str] = Query(None, description="筛选类型"),
) -> ApiResponse[list[WebsiteOut]]:
    sites = list_websites(db, tenant_id, site_type)
    return ApiResponse[list[WebsiteOut]](data=sites)


@router.get("/websites/{website_id}", response_model=ApiResponse[WebsiteOut], summary="网站详情")
def get_website(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsiteOut]:
    website = db.execute(
        select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
    ).scalars().first()
    if not website:
        raise HTTPException(status_code=404, detail=f"网站不存在: {website_id}")
    return ApiResponse[WebsiteOut](data=website)


@router.put("/websites/{website_id}", response_model=ApiResponse[WebsiteOut], summary="更新网站/网店")
def update_website_endpoint(
    website_id: int,
    payload: WebsiteUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsiteOut]:
    website = update_website(db, website_id, tenant_id, **payload.dict(exclude_none=True))
    return ApiResponse[WebsiteOut](data=website)


@router.delete("/websites/{website_id}", response_model=ApiResponse[dict], summary="删除网站/网店")
def delete_website(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    website = db.execute(
        select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
    ).scalars().first()
    if not website:
        raise HTTPException(status_code=404, detail=f"网站不存在: {website_id}")
    db.delete(website)
    db.commit()
    return ApiResponse[dict](data={"id": website_id, "deleted": True})


# ====================== 页面/文章 ======================

class PageCreate(BaseModel):
    title: str = Field(..., max_length=256, description="页面标题")
    slug: str = Field("", max_length=256, description="URL 路径")
    content: str = Field("", description="页面正文")
    seo_title: str = Field("", max_length=128, description="SEO title")
    seo_desc: str = Field("", max_length=512, description="SEO meta description")
    seo_keywords: str = Field("", max_length=256, description="SEO 关键词")
    publish_status: str = Field("draft", description="draft|scheduled|published|archived")
    ai_enabled: bool = Field(True, description="AI 内容生成")
    content_level: str = Field("L2", description="内容分级 L1-L4")


class PageUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    seo_title: Optional[str] = None
    seo_desc: Optional[str] = None
    seo_keywords: Optional[str] = None
    publish_status: Optional[str] = None
    ai_enabled: Optional[bool] = None
    content_level: Optional[str] = None


@router.post("/websites/{website_id}/pages", response_model=ApiResponse[WebsitePageOut], summary="创建页面/文章")
def create_new_page(
    website_id: int,
    payload: PageCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsitePageOut]:
    # 检查网站存在
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")

    page = create_page(db, tenant_id, website_id, **payload.dict())
    return ApiResponse[WebsitePageOut](data=page)


@router.get("/websites/{website_id}/pages", response_model=ApiResponse[list[WebsitePageOut]], summary="页面列表")
def list_pages(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    publish_status: Optional[str] = Query(None, description="筛选状态"),
) -> ApiResponse[list[WebsitePageOut]]:
    stmt = select(WebsitePage).where(WebsitePage.website_id == website_id, WebsitePage.tenant_id == tenant_id)
    if publish_status:
        stmt = stmt.where(WebsitePage.publish_status == publish_status)
    pages = list(db.execute(stmt.order_by(WebsitePage.id.desc())).scalars().all())
    return ApiResponse[list[WebsitePageOut]](data=pages)


@router.get("/websites/{website_id}/pages/{page_id}", response_model=ApiResponse[WebsitePageOut], summary="页面详情")
def get_page(
    website_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsitePageOut]:
    page = db.execute(
        select(WebsitePage).where(WebsitePage.id == page_id, WebsitePage.tenant_id == tenant_id)
    ).scalars().first()
    if not page:
        raise HTTPException(status_code=404, detail="页面不存在")
    return ApiResponse[WebsitePageOut](data=page)


@router.put("/websites/{website_id}/pages/{page_id}", response_model=ApiResponse[WebsitePageOut], summary="更新页面/文章")
def update_page_endpoint(
    website_id: int,
    page_id: int,
    payload: PageUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsitePageOut]:
    page = update_page(db, page_id, tenant_id, **payload.dict(exclude_none=True))
    return ApiResponse[WebsitePageOut](data=page)


@router.delete("/websites/{website_id}/pages/{page_id}", response_model=ApiResponse[dict], summary="删除页面/文章")
def delete_page(
    website_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    page = db.execute(
        select(WebsitePage).where(WebsitePage.id == page_id, WebsitePage.tenant_id == tenant_id)
    ).scalars().first()
    if not page:
        raise HTTPException(status_code=404, detail="页面不存在")
    db.delete(page)
    db.commit()
    return ApiResponse[dict](data={"id": page_id, "deleted": True})


# ====================== 站内预览与可控抓取（P3 内置浏览器） ======================

class CrawlRequest(BaseModel):
    page_id: Optional[int] = Field(None, description="页面 ID（与 path 二选一，优先 page_id）")
    path: str = Field("", max_length=256, description="站内相对路径，如 blog/hello")


@router.post(
    "/websites/{website_id}/crawl",
    response_model=ApiResponse[CrawlResultOut],
    summary="站内预览与可控抓取",
)
def crawl_site_page(
    website_id: int,
    payload: CrawlRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[CrawlResultOut]:
    """抓取本站同域页面并做 SEO 体检：仅同域、禁内网、限速限量，不跟随跨域重定向。"""
    site = db.execute(
        select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
    ).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="站点不存在")

    slug = ""
    if payload.page_id:
        page = db.execute(
            select(WebsitePage).where(
                WebsitePage.id == payload.page_id,
                WebsitePage.website_id == website_id,
                WebsitePage.tenant_id == tenant_id,
            )
        ).scalars().first()
        if not page:
            raise HTTPException(status_code=404, detail="页面不存在")
        slug = page.slug

    try:
        target = build_target_url(site.site_url, slug=slug, path=payload.path)
        result = crawl(target, site.site_url)
    except CrawlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse[CrawlResultOut](data=CrawlResultOut(**result))


# ====================== 商品 ======================

class ProductCreate(BaseModel):
    name: str = Field(..., max_length=256, description="商品名称")
    price: float = Field(..., ge=0, description="价格")
    currency: str = Field("CNY", max_length=8, description="货币")
    stock: int = Field(0, ge=0, description="库存")
    sku: str = Field("", max_length=64, description="SKU")
    description: str = Field("", description="商品描述")
    status: str = Field("draft", description="draft|active|inactive")
    seo_title: str = Field("", max_length=128, description="SEO title")
    seo_desc: str = Field("", max_length=512, description="SEO meta description")
    ai_enabled: bool = Field(True, description="AI 商品优化")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    stock: Optional[int] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    seo_title: Optional[str] = None
    seo_desc: Optional[str] = None
    ai_enabled: Optional[bool] = None


@router.post("/websites/{website_id}/products", response_model=ApiResponse[ProductItemOut], summary="创建商品")
def create_new_product(
    website_id: int,
    payload: ProductCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ProductItemOut]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    product = create_product(db, tenant_id, website_id, payload.name, payload.price, **payload.dict(exclude={"name", "price"}))
    return ApiResponse[ProductItemOut](data=product)


@router.get("/websites/{website_id}/products", response_model=ApiResponse[list[ProductItemOut]], summary="商品列表")
def list_products(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    status: Optional[str] = Query(None, description="筛选状态"),
) -> ApiResponse[list[ProductItemOut]]:
    stmt = select(ProductItem).where(ProductItem.website_id == website_id, ProductItem.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(ProductItem.status == status)
    products = list(db.execute(stmt.order_by(ProductItem.id.desc())).scalars().all())
    return ApiResponse[list[ProductItemOut]](data=products)


@router.put("/websites/{website_id}/products/{product_id}", response_model=ApiResponse[ProductItemOut], summary="更新商品")
def update_product_endpoint(
    website_id: int,
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[ProductItemOut]:
    product = update_product(db, product_id, tenant_id, **payload.dict(exclude_none=True))
    return ApiResponse[ProductItemOut](data=product)


@router.delete("/websites/{website_id}/products/{product_id}", response_model=ApiResponse[dict], summary="删除商品")
def delete_product(
    website_id: int,
    product_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    product = db.execute(
        select(ProductItem).where(ProductItem.id == product_id, ProductItem.tenant_id == tenant_id)
    ).scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    db.delete(product)
    db.commit()
    return ApiResponse[dict](data={"id": product_id, "deleted": True})


# ====================== SEO 任务 ======================

class SeoTaskCreate(BaseModel):
    task_type: str = Field(..., description="类型: audit|generate_sitemap|generate_robots|content_audit|keyword_analysis|link_audit")
    page_ids: Optional[list[int]] = Field(None, description="目标页面 ID")
    ai_enabled: bool = Field(True, description="AI 增强")
    ai_model: str = Field("", max_length=64, description="AI 模型")


@router.post("/websites/{website_id}/seo", response_model=ApiResponse[SeoTaskOut], summary="执行 SEO 任务")
def run_seo_task_endpoint(
    website_id: int,
    payload: SeoTaskCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[SeoTaskOut]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    task = run_seo_task(db, tenant_id, website_id, payload.task_type, payload.page_ids, payload.ai_model or None, payload.ai_enabled)
    return ApiResponse[SeoTaskOut](data=task)


@router.get("/websites/{website_id}/seo", response_model=ApiResponse[list[SeoTaskOut]], summary="SEO 任务列表")
def list_seo_tasks(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    status: Optional[str] = Query(None, description="筛选状态"),
) -> ApiResponse[list[SeoTaskOut]]:
    stmt = select(SeoTask).where(SeoTask.website_id == website_id, SeoTask.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(SeoTask.status == status)
    tasks = list(db.execute(stmt.order_by(SeoTask.id.desc())).scalars().all())
    return ApiResponse[list[SeoTaskOut]](data=tasks)


# ====================== GEO 任务 ======================

class GeoTaskCreate(BaseModel):
    task_type: str = Field(..., description="类型: content_optimize|schema_markup|ai_snippet|structured_data|local_seo")
    page_ids: Optional[list[int]] = Field(None, description="目标页面 ID")
    ai_enabled: bool = Field(True, description="AI 增强")
    ai_model: str = Field("", max_length=64, description="AI 模型")


@router.post("/websites/{website_id}/geo", response_model=ApiResponse[GeoTaskOut], summary="执行 GEO 任务")
def run_geo_task_endpoint(
    website_id: int,
    payload: GeoTaskCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[GeoTaskOut]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    task = run_geo_task(db, tenant_id, website_id, payload.task_type, payload.page_ids, payload.ai_model or None, payload.ai_enabled)
    return ApiResponse[GeoTaskOut](data=task)


@router.get("/websites/{website_id}/geo", response_model=ApiResponse[list[GeoTaskOut]], summary="GEO 任务列表")
def list_geo_tasks(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    status: Optional[str] = Query(None, description="筛选状态"),
) -> ApiResponse[list[GeoTaskOut]]:
    stmt = select(GeoTask).where(GeoTask.website_id == website_id, GeoTask.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(GeoTask.status == status)
    tasks = list(db.execute(stmt.order_by(GeoTask.id.desc())).scalars().all())
    return ApiResponse[list[GeoTaskOut]](data=tasks)


# ====================== AI 智能设置 ======================

class AiConfigCreate(BaseModel):
    setting_type: str = Field(..., description="类型: seo_auto|content_auto|seo_tone|content_tone|publish_schedule|auto_sitemap|media_auto_tag|auto_meta")
    config_value: dict = Field({}, description="配置值")
    enabled: bool = Field(True, description="启用")
    ai_model: str = Field("", max_length=64, description="AI 模型")


@router.post("/websites/{website_id}/ai-config", response_model=ApiResponse[WebsiteAiConfigOut], summary="创建/更新 AI 配置")
def create_ai_config(
    website_id: int,
    payload: AiConfigCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsiteAiConfigOut]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    config = save_ai_config(db, tenant_id, website_id, payload.setting_type, payload.config_value, payload.enabled, payload.ai_model)
    return ApiResponse[WebsiteAiConfigOut](data=config)


@router.get("/websites/{website_id}/ai-config", response_model=ApiResponse[list[WebsiteAiConfigOut]], summary="AI 配置列表")
def get_ai_configs(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    setting_type: Optional[str] = Query(None, description="筛选类型"),
) -> ApiResponse[list[WebsiteAiConfigOut]]:
    configs = get_ai_config(db, tenant_id, website_id, setting_type)
    return ApiResponse[list[WebsiteAiConfigOut]](data=configs)


@router.put("/ai-configs/{config_id}", response_model=ApiResponse[WebsiteAiConfigOut], summary="更新 AI 配置")
def update_ai_config_endpoint(
    config_id: int,
    payload: AiConfigCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[WebsiteAiConfigOut]:
    config = update_ai_config(db, config_id, tenant_id, config_value=payload.config_value, enabled=payload.enabled, ai_model=payload.ai_model)
    return ApiResponse[WebsiteAiConfigOut](data=config)


# ====================== 媒体库 ======================

class MediaCreate(BaseModel):
    media_type: str = Field(..., description="类型: image|video|audio|document|archive")
    file_url: str = Field(..., max_length=1024, description="文件 URL")
    file_name: str = Field("", max_length=256, description="文件名")
    file_size: int = Field(0, ge=0, description="文件大小")
    mime_type: str = Field("", max_length=128, description="MIME 类型")
    width: int = Field(0, ge=0, description="图片宽度")
    height: int = Field(0, ge=0, description="图片高度")
    description: str = Field("", description="描述")
    tags: Optional[list[str]] = Field(None, description="标签")
    folder: str = Field("", max_length=128, description="文件夹")
    content_level: str = Field("L2", description="内容分级 L1-L4")


@router.post("/websites/{website_id}/media", response_model=ApiResponse[MediaItemOut], summary="上传媒体")
def create_media_endpoint(
    website_id: int,
    payload: MediaCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MediaItemOut]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    media = create_media(db, tenant_id, website_id, payload.media_type, payload.file_url, **payload.dict(exclude={"media_type", "file_url"}))
    return ApiResponse[MediaItemOut](data=media)


@router.get("/websites/{website_id}/media", response_model=ApiResponse[list[MediaItemOut]], summary="媒体列表")
def list_media_endpoint(
    website_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    media_type: Optional[str] = Query(None, description="筛选类型"),
    folder: Optional[str] = Query(None, description="筛选文件夹"),
) -> ApiResponse[list[MediaItemOut]]:
    media = list_media(db, tenant_id, website_id, media_type, folder)
    return ApiResponse[list[MediaItemOut]](data=media)


@router.get("/websites/{website_id}/media/{media_id}", response_model=ApiResponse[MediaItemOut], summary="媒体详情")
def get_media(
    website_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MediaItemOut]:
    media = db.execute(
        select(MediaItem).where(MediaItem.id == media_id, MediaItem.tenant_id == tenant_id)
    ).scalars().first()
    if not media:
        raise HTTPException(status_code=404, detail="媒体不存在")
    return ApiResponse[MediaItemOut](data=media)


@router.put("/websites/{website_id}/media/{media_id}", response_model=ApiResponse[MediaItemOut], summary="更新媒体")
def update_media_endpoint(
    website_id: int,
    media_id: int,
    payload: MediaCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[MediaItemOut]:
    media = update_media(db, media_id, tenant_id, **payload.dict(exclude={"media_type", "file_url"}))
    return ApiResponse[MediaItemOut](data=media)


@router.delete("/websites/{website_id}/media/{media_id}", response_model=ApiResponse[dict], summary="删除媒体")
def delete_media_endpoint(
    website_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    success = delete_media(db, media_id, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="媒体不存在")
    return ApiResponse[dict](data={"id": media_id, "deleted": True})


# ====================== 自媒体 ======================

class SocialPostCreate(BaseModel):
    platform: str = Field(..., description="平台: wechat|weibo|douyin|xiaohongshu|zhihu|bilibili")
    content: str = Field(..., max_length=10000, description="内容")
    media_ids: Optional[list[int]] = Field(None, description="关联媒体 ID")
    scheduled_at: Optional[str] = Field(None, description="定时发布 YYYY-MM-DD HH:MM")
    ai_enabled: bool = Field(True, description="AI 优化")
    ai_model: str = Field("", max_length=64, description="AI 模型")


@router.post("/websites/{website_id}/social", response_model=ApiResponse[dict], summary="创建自媒体发布")
def create_social_post_endpoint(
    website_id: int,
    payload: SocialPostCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    result = {"platform": payload.platform, "content_length": len(payload.content), "scheduled_at": payload.scheduled_at}
    return ApiResponse[dict](data=result)


class SocialOptimizeRequest(BaseModel):
    platform: str = Field(..., description="平台")
    content: str = Field(..., max_length=3000, description="内容")
    tone: str = Field("professional", max_length=32, description="风格: professional|friendly|humorous|formal")
    mode: str = Field("local", max_length=16, description="ai/local")


@router.post("/websites/{website_id}/social/optimize", response_model=ApiResponse[dict], summary="AI 优化自媒体内容")
def optimize_social_content(
    website_id: int,
    payload: SocialOptimizeRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    result = ai_social_optimize(db, tenant_id, website_id, payload.platform, payload.content, payload.tone, payload.mode)
    return ApiResponse[dict](data=result)


@router.post("/websites/{website_id}/social/schedule", response_model=ApiResponse[dict], summary="AI 智能安排发布时间")
def schedule_social_posts(
    website_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    result = ai_social_schedule(db, tenant_id, website_id, payload.get("platform", "wechat"), payload.get("posts", []))
    return ApiResponse[dict](data=result)


@router.post("/websites/{website_id}/social/analytics", response_model=ApiResponse[dict], summary="AI 分析自媒体数据")
def analyze_social(
    website_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    site = db.execute(select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    result = ai_social_analytics(db, tenant_id, website_id, payload.get("platform", "wechat"))
    return ApiResponse[dict](data=result)


# ====================== AI 运营分析 ======================

class AiAnalysisRequest(BaseModel):
    scope: str = Field("seo", description="范围: seo|geo|content|analytics")
    website_id: int = Field(..., description="网站 ID")
    page_ids: Optional[list[int]] = Field(None, description="目标页面 ID")
    max_insights: int = Field(8, ge=1, le=20, description="最大洞察数")
    mode: str = Field("local", max_length=16, description="ai/local")


@router.post("/ai/analyze", response_model=ApiResponse[dict], summary="AI 全面运营分析")
def ai_full_analysis(
    payload: AiAnalysisRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    site = db.execute(select(Website).where(Website.id == payload.website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")

    result = {"website_id": payload.website_id, "site_name": site.site_name, "site_type": site.site_type}

    if payload.scope == "seo":
        analysis_result = ai_seo_analysis(db, tenant_id, payload.website_id, payload.page_ids, payload.mode)
        result["seo_analysis"] = analysis_result
    elif payload.scope == "content":
        pages = db.execute(
            select(WebsitePage).where(
                WebsitePage.website_id == payload.website_id,
                WebsitePage.tenant_id == tenant_id,
            )
        ).scalars().all()
        page_data = [{"id": p.id, "title": p.title, "content": p.content} for p in pages[:10]]
        content_result = ai_content_optimize(db, tenant_id, site.site_name, page_data, payload.mode)
        result["content_analysis"] = content_result
    elif payload.scope == "geo":
        geo_result = {"suggestions": ["优化 Schema 标记", "添加结构化数据", "提升本地 SEO"], "total_suggestions": 3}
        result["geo_analysis"] = geo_result
    elif payload.scope == "analytics":
        result["analytics"] = {"pages": len(list(db.execute(select(WebsitePage).where(WebsitePage.website_id == payload.website_id)).scalars())), "products": len(list(db.execute(select(ProductItem).where(ProductItem.website_id == payload.website_id)).scalars()))}

    result["status"] = "success"
    return ApiResponse[dict](data=result)


# ====================== AI 内容生成 ======================

class ContentGenerateRequest(BaseModel):
    website_id: int = Field(..., description="网站 ID")
    page_id: int = Field(..., description="页面 ID")
    content_type: str = Field("article", max_length=32, description="类型: article|blog|product|landing")
    keywords: Optional[list[str]] = Field(None, description="关键词")
    tone: str = Field("professional", max_length=32, description="风格: professional|friendly|humorous|formal")
    mode: str = Field("local", max_length=16, description="ai/local")


@router.post("/ai/generate-content", response_model=ApiResponse[dict], summary="AI 生成/改写内容")
def generate_content(
    payload: ContentGenerateRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ApiResponse[dict]:
    site = db.execute(select(Website).where(Website.id == payload.website_id, Website.tenant_id == tenant_id)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="网站不存在")
    page = db.execute(select(WebsitePage).where(WebsitePage.id == payload.page_id)).scalars().first()
    if not page:
        raise HTTPException(status_code=404, detail="页面不存在")

    result = ai_generate_content(db, tenant_id, payload.website_id, payload.page_id, payload.content_type, payload.keywords, payload.tone, payload.mode)
    result["page_id"] = payload.page_id
    result["page_title"] = page.title
    return ApiResponse[dict](data=result)
