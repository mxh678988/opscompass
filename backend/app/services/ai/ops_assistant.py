"""运营参谋模块服务：网站/网店管理、SEO、GEO、内容生成、媒体库、自媒体管理。"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import urllib.request
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.ops_compass import (
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
from app.models.ai import (
    AiAnalysis,
    AiInsight,
    AiAuditLog,
)
from app.services.ai.analyzer import run_analysis as _run_ai_analysis
from app.services.ai.llm_client import LLMClient, LLMError, extract_json
from app.services.ai.grader import grade_object, resolve_level


def _loads_lenient(text: str) -> Any:
    """宽松解析模型输出：纯 JSON、```json 代码块、夹带说明文字、JSON 数组均可。"""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    data = extract_json(text)
    if data is not None:
        return data
    fenced = re.findall(r"```(?:json)?\s*(.+?)```", text, flags=re.S)
    for raw in fenced + [text]:
        raw = raw.strip()
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            continue
        try:
            arr = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(arr, list):
            return arr
    return None


# ---------------------------------------------------------------- 网站管理

def create_website(db: Session, tenant_id: int, **kw: Any) -> Website:
    website = Website(tenant_id=tenant_id, **kw)
    db.add(website)
    db.commit()
    db.refresh(website)
    return website


def list_websites(db: Session, tenant_id: int, site_type: Optional[str] = None) -> list[Website]:
    stmt = select(Website).where(Website.tenant_id == tenant_id)
    if site_type:
        stmt = stmt.where(Website.site_type == site_type)
    return list(db.execute(stmt.order_by(Website.id.desc())).scalars().all())


def update_website(db: Session, website_id: int, tenant_id: int, **kw: Any) -> Website:
    website = db.execute(
        select(Website).where(Website.id == website_id, Website.tenant_id == tenant_id)
    ).scalars().first()
    if not website:
        raise ValueError(f"网站不存在: {website_id}")
    for k, v in kw.items():
        setattr(website, k, v)
    db.commit()
    db.refresh(website)
    return website


# ---------------------------------------------------------------- 通用兜底工具

def _slugify(text: str) -> str:
    """标题 -> URL 友好 slug（保留中文，空格与符号折叠为连字符，最长 120 字符）。"""
    raw = (text or "").strip().lower()
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", raw)
    return re.sub(r"-{2,}", "-", slug).strip("-")[:120]


def _derive_page_seo(title: str, content: str, site_desc: str = "") -> dict[str, str]:
    """页面缺失 SEO 字段时的兜底派生：标题截 60 字，描述取正文纯文本前 155 字。"""
    body = re.sub(r"<[^>]+>", " ", content or "")
    body = re.sub(r"\s+", " ", body).strip()
    return {
        "seo_title": (title or "").strip()[:60],
        "seo_desc": (body[:155] or (site_desc or "").strip()),
    }


def _get_site(db: Session, website_id: int) -> Optional[Website]:
    return db.execute(select(Website).where(Website.id == website_id)).scalars().first()


def _probe_file_meta(file_url: str) -> dict[str, Any]:
    """探测媒体元信息：本地路径取真实字节数，远程 URL 尝试 HEAD（3 秒超时，失败静默）。"""
    meta: dict[str, Any] = {}
    if not file_url:
        return meta
    if file_url.startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(
                file_url, method="HEAD", headers={"User-Agent": "OpsCompass/1.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                size = resp.headers.get("Content-Length")
                if size and str(size).isdigit():
                    meta["file_size"] = int(size)
                ctype = resp.headers.get("Content-Type")
                if ctype:
                    meta["mime_type"] = ctype.split(";")[0].strip()
        except Exception:
            pass
    else:
        local_path = file_url.replace("file:///", "").replace("file://", "")
        if os.path.isfile(local_path):
            meta["file_size"] = os.path.getsize(local_path)
            guess, _ = mimetypes.guess_type(local_path)
            if guess:
                meta["mime_type"] = guess
    if "mime_type" not in meta:
        guess, _ = mimetypes.guess_type(file_url.split("?")[0])
        if guess:
            meta["mime_type"] = guess
    return meta


def _calc_geo_score(db: Session, website_id: int, site: Optional[Website]) -> int:
    """GEO 评分：页面描述完整度占比 60 + 站点描述 20 + sitemap 已生成 20。"""
    if site is None:
        return 0
    score = 0.0
    page_count = db.execute(
        select(func.count(WebsitePage.id)).where(WebsitePage.website_id == website_id)
    ).scalar_one()
    if page_count:
        described = db.execute(
            select(func.count(WebsitePage.id)).where(
                WebsitePage.website_id == website_id,
                WebsitePage.seo_desc != "",
            )
        ).scalar_one()
        score += 60.0 * described / page_count
    if (site.description or "").strip():
        score += 20
    if site.sitemap_generated:
        score += 20
    return int(min(100, round(score)))


# ---------------------------------------------------------------- 页面/文章管理

def create_page(db: Session, tenant_id: int, website_id: int, **kw: Any) -> WebsitePage:
    title = kw.get("title") or ""
    if not str(kw.get("slug") or "").strip():
        kw["slug"] = _slugify(title)
    site = _get_site(db, website_id)
    derived = _derive_page_seo(title, kw.get("content") or "", site.description if site else "")
    for field in ("seo_title", "seo_desc"):
        if not str(kw.get(field) or "").strip():
            kw[field] = derived[field]
    page = WebsitePage(tenant_id=tenant_id, website_id=website_id, **kw)
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


def update_page(db: Session, page_id: int, tenant_id: int, **kw: Any) -> WebsitePage:
    page = db.execute(
        select(WebsitePage).where(WebsitePage.id == page_id, WebsitePage.tenant_id == tenant_id)
    ).scalars().first()
    if not page:
        raise ValueError(f"页面不存在: {page_id}")
    for k, v in kw.items():
        setattr(page, k, v)
    site = _get_site(db, page.website_id)
    derived = _derive_page_seo(
        page.title or "", page.content or "", site.description if site else ""
    )
    if not (page.slug or "").strip():
        page.slug = _slugify(page.title or "")
    if not (page.seo_title or "").strip():
        page.seo_title = derived["seo_title"]
    if not (page.seo_desc or "").strip():
        page.seo_desc = derived["seo_desc"]
    db.commit()
    db.refresh(page)
    return page


# ---------------------------------------------------------------- 商品管理

def create_product(
    db: Session,
    tenant_id: int,
    website_id: int,
    name: str,
    price: float,
    **kw: Any,
) -> ProductItem:
    product = ProductItem(
        tenant_id=tenant_id,
        website_id=website_id,
        name=name,
        price=round(price * 100),
        **kw,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, tenant_id: int, **kw: Any) -> ProductItem:
    product = db.execute(
        select(ProductItem).where(ProductItem.id == product_id, ProductItem.tenant_id == tenant_id)
    ).scalars().first()
    if not product:
        raise ValueError(f"商品不存在: {product_id}")
    if kw.get("price") is not None:
        kw["price"] = round(float(kw["price"]) * 100)
    for k, v in kw.items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)
    return product


# ---------------------------------------------------------------- SEO 任务

def run_seo_task(
    db: Session,
    tenant_id: int,
    website_id: int,
    task_type: str,
    page_ids: Optional[list[int]] = None,
    ai_model: Optional[str] = None,
    ai_enabled: bool = True,
) -> SeoTask:
    title_map = {
        "audit": "SEO 全面审计",
        "generate_sitemap": "生成 Sitemap",
        "generate_robots": "生成 robots.txt",
        "content_audit": "内容审计",
        "keyword_analysis": "关键词分析",
        "link_audit": "外链审计",
    }
    task = SeoTask(
        tenant_id=tenant_id,
        website_id=website_id,
        task_type=task_type,
        title=title_map.get(task_type, task_type),
        status="running",
        ai_enabled=ai_enabled,
        ai_model=ai_model or "local",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        result = _execute_seo_task(db, task, page_ids)
        task.status = "success"
        task.result = json.dumps(result, ensure_ascii=False, default=str)
        task.duration_ms = result.get("duration_ms", 0)
    except Exception as e:
        task.status = "failed"
        task.result = str(e)

    db.commit()
    db.refresh(task)
    return task


def _execute_seo_task(db: Session, task: SeoTask, page_ids: Optional[list[int]] = None) -> dict[str, Any]:
    start = datetime.now()
    result = {"task_type": task.task_type, "task_id": task.id}

    if task.task_type == "audit":
        # 全面 SEO 审计
        site = db.execute(select(Website).where(Website.id == task.website_id)).scalars().first()
        page_count = db.execute(
            select(func.count(WebsitePage.id)).where(WebsitePage.website_id == task.website_id)
        ).scalar_one()
        pages_missing_seo = db.execute(
            select(func.count(WebsitePage.id)).where(
                WebsitePage.website_id == task.website_id,
                WebsitePage.seo_title == "",
            )
        ).scalar_one()
        pages_missing_desc = db.execute(
            select(func.count(WebsitePage.id)).where(
                WebsitePage.website_id == task.website_id,
                WebsitePage.seo_desc == "",
            )
        ).scalar_one()

        result.update({
            "page_count": page_count,
            "missing_seo_title": pages_missing_seo,
            "missing_seo_desc": pages_missing_desc,
            "seo_score": max(0, 100 - int((pages_missing_seo + pages_missing_desc) / max(page_count, 1) * 100)),
        })

        # 审计结果回写站点资产评分（此前长期停留在 0）
        if site:
            site.seo_score = result["seo_score"]
            db.commit()

        # AI 分析
        ai_result = ai_seo_analysis(db, task.tenant_id, task.website_id, page_ids)
        result["ai_analysis"] = ai_result

    elif task.task_type == "generate_sitemap":
        pages = db.execute(
            select(WebsitePage.slug).where(
                WebsitePage.website_id == task.website_id,
                WebsitePage.publish_status == "published",
            )
        ).scalars().all()
        site = db.execute(select(Website).where(Website.id == task.website_id)).scalars().first()
        base_url = site.site_url.rstrip("/") if site else ""
        lines = [f"<?xml version='1.0' encoding='UTF-8'?>", "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
        for slug in pages:
            if slug:
                url = f"{base_url}/{slug}"
                lines.append(f"  <url><loc>{url}</loc></url>")
        lines.append("</urlset>")
        sitemap = "\n".join(lines)
        result["sitemap"] = sitemap[:200000]
        result["urls"] = len(pages)
        if site:
            site.sitemap_generated = True
            site.geo_score = _calc_geo_score(db, task.website_id, site)
            db.commit()

    elif task.task_type == "generate_robots":
        site = db.execute(select(Website).where(Website.id == task.website_id)).scalars().first()
        base_url = site.site_url.rstrip("/") if site else ""
        sitemap_url = f"{base_url}/sitemap.xml"
        content = f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}"
        result["robots"] = content
        result["urls"] = 0

    elif task.task_type == "content_audit":
        pages = db.execute(
            select(WebsitePage).where(WebsitePage.website_id == task.website_id)
        ).scalars().all()
        issues = []
        for p in pages:
            if len(p.content or "") < 200:
                issues.append({"page_id": p.id, "title": p.title, "issue": "content_short", "severity": "warning"})
            if not p.seo_title:
                issues.append({"page_id": p.id, "title": p.title, "issue": "missing_seo_title", "severity": "warning"})
            if not p.seo_desc:
                issues.append({"page_id": p.id, "title": p.title, "issue": "missing_seo_desc", "severity": "info"})
            if not p.seo_keywords:
                issues.append({"page_id": p.id, "title": p.title, "issue": "missing_keywords", "severity": "info"})
        result["issues"] = issues
        result["total_pages"] = len(pages)
        result["total_issues"] = len(issues)

    elif task.task_type == "keyword_analysis":
        pages = db.execute(
            select(WebsitePage).where(WebsitePage.website_id == task.website_id)
        ).scalars().all()
        keywords_count = 0
        for p in pages:
            if p.seo_keywords:
                keywords_count += len([k for k in p.seo_keywords.split(",") if k.strip()])
        result["total_pages"] = len(pages)
        result["total_keywords"] = keywords_count

    elif task.task_type == "link_audit":
        pages = db.execute(
            select(WebsitePage).where(WebsitePage.website_id == task.website_id)
        ).scalars().all()
        broken_links = []
        internal_links = 0
        for p in pages:
            if p.content:
                import re
                links = re.findall(r'href=["\']([^"\']+)["\']', p.content or "")
                internal_links += len([l for l in links if not l.startswith("http")])
        result["pages"] = len(pages)
        result["internal_links"] = internal_links
        result["broken_links"] = broken_links

    result["duration_ms"] = (datetime.now() - start).total_seconds() * 1000
    return result


# ---------------------------------------------------------------- GEO 任务

def run_geo_task(
    db: Session,
    tenant_id: int,
    website_id: int,
    task_type: str,
    page_ids: Optional[list[int]] = None,
    ai_model: Optional[str] = None,
    ai_enabled: bool = True,
) -> GeoTask:
    title_map = {
        "content_optimize": "内容 GSE 优化",
        "schema_markup": "Schema 标记生成",
        "ai_snippet": "AI 摘要片段生成",
        "structured_data": "结构化数据生成",
        "local_seo": "本地 SEO 优化",
    }
    task = GeoTask(
        tenant_id=tenant_id,
        website_id=website_id,
        task_type=task_type,
        title=title_map.get(task_type, task_type),
        status="running",
        ai_enabled=ai_enabled,
        ai_model=ai_model or "local",
        target_page_ids=json.dumps(page_ids or []),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        result = _execute_geo_task(db, task)
        task.status = "success"
        task.result = json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        task.status = "failed"
        task.result = str(e)

    db.commit()
    db.refresh(task)
    return task


def _execute_geo_task(db: Session, task: GeoTask) -> dict[str, Any]:
    start = datetime.now()
    page_ids = json.loads(task.target_page_ids) if task.target_page_ids else []
    site = db.execute(select(Website).where(Website.id == task.website_id)).scalars().first()

    if task.task_type == "content_optimize":
        # AI 驱动的内容 GSE 优化（未指定页面时覆盖全站页面）
        conds = [WebsitePage.website_id == task.website_id]
        if page_ids:
            conds.append(WebsitePage.id.in_(page_ids))
        target_pages = db.execute(select(WebsitePage).where(*conds)).scalars().all()

        pages_data = []
        for page in target_pages:
            pages_data.append({"id": page.id, "title": page.title, "content": page.content[:5000]})

        ai_result = ai_content_optimize(db, task.tenant_id, site.site_name, pages_data)
        result = {"optimizations": ai_result, "total_pages": len(target_pages)}

    elif task.task_type == "schema_markup":
        pages = db.execute(
            select(WebsitePage).where(WebsitePage.website_id == task.website_id)
        ).scalars().all()
        markup = []
        for page in pages:
            schema = {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": page.title,
                "description": page.seo_desc or "",
                "url": f"{site.site_url.rstrip('/')}/{page.slug}" if page.slug else site.site_url,
            }
            markup.append(schema)
        result = {"schemas": markup, "total_pages": len(markup)}

    elif task.task_type == "ai_snippet":
        pages = db.execute(
            select(WebsitePage).where(WebsitePage.website_id == task.website_id)
        ).scalars().all()
        snippets = []
        for page in pages:
            snippets.append({
                "page_id": page.id,
                "title": page.title,
                "snippet": (page.seo_desc or page.title)[:160] + "...",
            })
        result = {"snippets": snippets, "total_pages": len(snippets)}

    elif task.task_type == "structured_data":
        # 结构化数据生成
        site_info = {
            "name": site.site_name,
            "url": site.site_url,
            "type": site.site_type,
            "language": site.language,
        }
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            **site_info,
        }
        result = {"schema": schema, "type": "organization"}

    elif task.task_type == "local_seo":
        # 本地 SEO 优化建议
        result = {
            "suggestions": [
                {"category": "gmb", "action": "优化 Google My Business 资料", "priority": "high"},
                {"category": "local_citation", "action": "统一 NAP 信息", "priority": "high"},
                {"category": "local_keywords", "action": "添加本地关键词", "priority": "medium"},
            ],
            "total_suggestions": 3,
        }

    # GEO 结果回写站点资产评分
    if site:
        site.geo_score = _calc_geo_score(db, task.website_id, site)
        result["geo_score"] = site.geo_score
        db.commit()

    result["duration_ms"] = (datetime.now() - start).total_seconds() * 1000
    return result


# ---------------------------------------------------------------- AI 智能设置

def save_ai_config(
    db: Session,
    tenant_id: int,
    website_id: int,
    setting_type: str,
    config_value: dict[str, Any],
    enabled: bool = True,
    ai_model: Optional[str] = None,
) -> WebsiteAiConfig:
    config = db.execute(
        select(WebsiteAiConfig).where(
            WebsiteAiConfig.tenant_id == tenant_id,
            WebsiteAiConfig.website_id == website_id,
            WebsiteAiConfig.setting_type == setting_type,
        )
    ).scalars().first()

    if config:
        config.config_value = json.dumps(config_value, ensure_ascii=False)
        config.enabled = enabled
        config.ai_model = ai_model or config.ai_model
    else:
        config = WebsiteAiConfig(
            tenant_id=tenant_id,
            website_id=website_id,
            setting_type=setting_type,
            config_value=json.dumps(config_value, ensure_ascii=False),
            enabled=enabled,
            ai_model=ai_model or "local",
        )
        db.add(config)

    db.commit()
    db.refresh(config)
    return config


def get_ai_config(
    db: Session,
    tenant_id: int,
    website_id: int,
    setting_type: Optional[str] = None,
) -> list[WebsiteAiConfig]:
    stmt = select(WebsiteAiConfig).where(
        WebsiteAiConfig.tenant_id == tenant_id,
        WebsiteAiConfig.website_id == website_id,
    )
    if setting_type:
        stmt = stmt.where(WebsiteAiConfig.setting_type == setting_type)
    return list(db.execute(stmt.order_by(WebsiteAiConfig.id.desc())).scalars().all())


def update_ai_config(
    db: Session,
    config_id: int,
    tenant_id: int,
    **kw: Any,
) -> WebsiteAiConfig:
    config = db.execute(
        select(WebsiteAiConfig).where(WebsiteAiConfig.id == config_id, WebsiteAiConfig.tenant_id == tenant_id)
    ).scalars().first()
    if not config:
        raise ValueError(f"AI 配置不存在: {config_id}")
    for k, v in kw.items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


# ---------------------------------------------------------------- AI 内容生成与优化

def ai_content_optimize(
    db: Session,
    tenant_id: int,
    site_name: str,
    pages: list[dict[str, Any]],
    mode: Optional[str] = None,
) -> list[dict[str, Any]]:
    """AI 内容 GSE 优化：生成优化建议和内容改写。"""
    client = LLMClient(mode=mode)

    prompt = (
        f"你是 {site_name} 的 SEO 和 GEO 专家。以下是 {len(pages)} 个页面的内容，"
        f"请对每个页面提供：1) 内容质量评分(0-100)；2) SEO 优化建议；3) GEO 优化建议；"
        f"4) 推荐的标题改写（不超过60字符）；5) 推荐的 meta description（不超过160字符）。"
        f"严格输出 JSON 数组："
        '[{"page_id": 0, "quality": 0, "seo_suggestions": [], "geo_suggestions": [], "title_suggestion": "", "meta_suggestion": ""}]'
    )

    results = []
    for page_data in pages:
        page_title = page_data.get("title", "无标题页面")
        page_content = page_data.get("content", "")[:8000]
        user_prompt = f"页面标题: {page_title}\n页面内容:\n{page_content}"

        try:
            result = client.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_prompt},
            ])
            parsed = _loads_lenient(result.text)
            if parsed is None:
                results.append({
                    "page_id": page_data.get("id", 0),
                    "quality": 0,
                    "seo_suggestions": ["AI 返回解析失败"],
                    "geo_suggestions": [],
                    "title_suggestion": page_title,
                    "meta_suggestion": page_title,
                })
            else:
                results.extend(parsed if isinstance(parsed, list) else [parsed])
        except LLMError:
            results.append({
                "page_id": page_data.get("id", 0),
                "quality": 0,
                "seo_suggestions": ["AI 服务不可用"],
                "geo_suggestions": [],
                "title_suggestion": page_title,
                "meta_suggestion": page_title,
            })

    return results


def ai_seo_analysis(
    db: Session,
    tenant_id: int,
    website_id: int,
    page_ids: Optional[list[int]] = None,
    mode: Optional[str] = None,
) -> dict[str, Any]:
    """AI SEO 深度分析。"""
    client = LLMClient(mode=mode)
    website = db.execute(select(Website).where(Website.id == website_id)).scalars().first()

    prompt = (
        f"你是 {website.site_name} 的 SEO 专家。以下是该网站的结构和信息，"
        f"请进行全面 SEO 分析并给出改进建议。严格输出 JSON："
        '{"score": 0, "issues": [{"category": "", "severity": "", "description": "", "fix": ""}], "suggestions": [], "ai_summary": ""}'
    )

    # 收集页面信息
    pages_query = select(WebsitePage).where(WebsitePage.website_id == website_id)
    if page_ids:
        pages_query = pages_query.where(WebsitePage.id.in_(page_ids))
    pages = db.execute(pages_query.limit(50)).scalars().all()

    page_info = []
    for p in pages:
        page_info.append({
            "id": p.id,
            "title": p.title,
            "seo_title": p.seo_title or p.title,
            "seo_desc": p.seo_desc or "",
            "content_length": len(p.content or ""),
            "slug": p.slug,
        })

    user_prompt = (
        f"网站: {website.site_name}\n网站类型: {website.site_type}\nURL: {website.site_url}\n"
        f"语言: {website.language}\n\n"
        f"页面 ({len(page_info)} 个):\n"
        + "\n".join(f"- {p['title']} | SEO Title: {p['seo_title']} | Description: {p['seo_desc'] or '无'} | 内容长度: {p['content_length']}" for p in page_info)
    )

    try:
        result = client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_prompt},
        ])
        parsed = _loads_lenient(result.text)
        if isinstance(parsed, dict):
            return parsed
        return {
            "score": 50,
            "issues": [{"category": "general", "severity": "warning", "description": "AI 返回解析失败", "fix": "重试"}],
            "suggestions": [],
            "ai_summary": "AI 返回格式异常，无法解析",
        }
    except LLMError:
        return {
            "score": 0,
            "issues": [{"category": "general", "severity": "critical", "description": "AI 服务不可用", "fix": "检查 AI 配置"}],
            "suggestions": [],
            "ai_summary": "AI 服务不可用",
        }


def ai_generate_content(
    db: Session,
    tenant_id: int,
    website_id: int,
    page_id: int,
    content_type: str = "article",
    keywords: Optional[list[str]] = None,
    tone: str = "professional",
    mode: Optional[str] = None,
) -> dict[str, Any]:
    """AI 生成/改写页面内容。"""
    client = LLMClient(mode=mode)
    page = db.execute(select(WebsitePage).where(WebsitePage.id == page_id)).scalars().first()
    if not page:
        raise ValueError(f"页面不存在: {page_id}")

    website = db.execute(select(Website).where(Website.id == website_id)).scalars().first()

    prompt = (
        f"你是 {website.site_name} 的内容专家。用户要求生成/改写 '{content_type}' 类型的内容，"
        f"风格为 {tone}。请生成高质量、SEO 优化的内容，并附带 meta description。"
        f"严格输出 JSON："
        '{"content": "", "title": "", "meta_description": "", "keyword_density": 0, "readability": 0}'
    )

    keywords_str = ", ".join(keywords) if keywords else ""
    user_prompt = (
        f"网站: {website.site_name}\n页面类型: {content_type}\n风格: {tone}\n"
        f"关键词: {keywords_str}\n\n现有内容（如需改写）:\n{page.content[:5000] if page.content else '（无）'}"
    )

    try:
        result = client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_prompt},
        ])
        parsed = _loads_lenient(result.text)
        if parsed is None:
            raise ValueError("AI 返回格式异常")
        return parsed
    except (ValueError, LLMError):
        return {
            "content": "生成失败，请重试",
            "title": page.title,
            "meta_description": page.seo_desc or "",
            "keyword_density": 0,
            "readability": 0,
        }


# ---------------------------------------------------------------- 媒体库服务

def create_media(
    db: Session,
    tenant_id: int,
    website_id: int,
    media_type: str,
    file_url: str,
    **kw: Any,
) -> MediaItem:
    if isinstance(kw.get("tags"), list):
        kw["tags"] = json.dumps(kw["tags"], ensure_ascii=False)
    probe = _probe_file_meta(file_url)
    if not kw.get("file_size") and probe.get("file_size"):
        kw["file_size"] = probe["file_size"]
    if not kw.get("mime_type") and probe.get("mime_type"):
        kw["mime_type"] = probe["mime_type"]
    if not str(kw.get("file_name") or "").strip():
        guessed_name = os.path.basename(file_url.split("?")[0].rstrip("/"))
        if guessed_name:
            kw["file_name"] = guessed_name[:256]
    media = MediaItem(
        tenant_id=tenant_id,
        website_id=website_id,
        media_type=media_type,
        file_url=file_url,
        **kw,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def list_media(
    db: Session,
    tenant_id: int,
    website_id: Optional[int] = None,
    media_type: Optional[str] = None,
    folder: Optional[str] = None,
) -> list[MediaItem]:
    stmt = select(MediaItem).where(MediaItem.tenant_id == tenant_id)
    if website_id:
        stmt = stmt.where(MediaItem.website_id == website_id)
    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    if folder:
        stmt = stmt.where(MediaItem.folder == folder)
    return list(db.execute(stmt.order_by(MediaItem.id.desc())).scalars().all())


def update_media(
    db: Session,
    media_id: int,
    tenant_id: int,
    **kw: Any,
) -> MediaItem:
    media = db.execute(
        select(MediaItem).where(MediaItem.id == media_id, MediaItem.tenant_id == tenant_id)
    ).scalars().first()
    if not media:
        raise ValueError(f"媒体不存在: {media_id}")
    if isinstance(kw.get("tags"), list):
        kw["tags"] = json.dumps(kw["tags"], ensure_ascii=False)
    if kw.get("file_url") and not kw.get("file_size"):
        probe = _probe_file_meta(kw["file_url"])
        if probe.get("file_size"):
            kw["file_size"] = probe["file_size"]
        if not kw.get("mime_type") and probe.get("mime_type"):
            kw["mime_type"] = probe["mime_type"]
    for k, v in kw.items():
        setattr(media, k, v)
    db.commit()
    db.refresh(media)
    return media


def delete_media(
    db: Session,
    media_id: int,
    tenant_id: int,
) -> bool:
    media = db.execute(
        select(MediaItem).where(MediaItem.id == media_id, MediaItem.tenant_id == tenant_id)
    ).scalars().first()
    if not media:
        return False
    db.delete(media)
    db.commit()
    return True


# ---------------------------------------------------------------- 自媒体管理

def create_social_post(
    db: Session,
    tenant_id: int,
    website_id: int,
    platform: str,
    content: str,
    media_ids: Optional[list[int]] = None,
    scheduled_at: Optional[str] = None,
    ai_enabled: bool = True,
    ai_model: Optional[str] = None,
) -> dict[str, Any]:
    """创建自媒体发布任务。"""
    return {"platform": platform, "content_length": len(content), "scheduled_at": scheduled_at}


def ai_social_optimize(
    db: Session,
    tenant_id: int,
    website_id: int,
    platform: str,
    content: str,
    tone: str = "professional",
    mode: Optional[str] = None,
) -> dict[str, Any]:
    """AI 优化自媒体内容。"""
    client = LLMClient(mode=mode)

    prompt = (
        f"你是 {platform} 的自媒体运营专家。请优化以下内容：\n{content[:3000]}\n"
        f"要求：1) 优化文案使其更具吸引力；2) 添加相关话题标签；3) 建议最佳发布时间。"
        f"严格输出 JSON："
        '{"optimized_content": "", "hashtags": [], "best_time": "", "engagement_score": 0}'
    )

    try:
        result = client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": content[:3000]},
        ])
        parsed = _loads_lenient(result.text)
        if parsed is None:
            raise ValueError("AI 返回格式异常")
        return parsed
    except (ValueError, LLMError):
        return {
            "optimized_content": content,
            "hashtags": [],
            "best_time": "09:00-11:00",
            "engagement_score": 0,
        }


def ai_social_schedule(
    db: Session,
    tenant_id: int,
    website_id: int,
    platform: str,
    posts: list[dict[str, Any]],
    mode: Optional[str] = None,
) -> dict[str, Any]:
    """AI 智能安排自媒体发布时间。"""
    return {
        "platform": platform,
        "scheduled_posts": len(posts),
        "schedule": [{"post_id": p.get("id", 0), "scheduled_at": p.get("time", "09:00")} for p in posts],
    }


def ai_social_analytics(
    db: Session,
    tenant_id: int,
    website_id: int,
    platform: str,
    mode: Optional[str] = None,
) -> dict[str, Any]:
    """AI 分析自媒体数据。"""
    client = LLMClient(mode=mode)

    # 收集平台数据
    posts_count = 0
    engagement_rate = 0.0
    best_performing_type = ""

    prompt = (
        f"你是 {platform} 的自媒体数据分析师。请根据以下数据进行分析：\n"
        f"发帖数: {posts_count}\n平均互动率: {engagement_rate}\n\n"
        f"请输出：1) 数据洞察；2) 改进建议；3) 内容策略建议。"
        f"严格输出 JSON："
        '{"insights": [], "suggestions": [], "strategy": ""}'
    )

    try:
        result = client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"平台: {platform}\n发帖数: {posts_count}\n平均互动率: {engagement_rate}%" },
        ])
        parsed = _loads_lenient(result.text)
        if parsed is None:
            raise ValueError("AI 返回格式异常")
        return parsed
    except (ValueError, LLMError):
        return {
            "insights": ["AI 服务不可用"],
            "suggestions": ["检查 AI 配置"],
            "strategy": "标准运营策略",
        }
