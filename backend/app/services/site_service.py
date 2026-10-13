"""M15 响应式网站生成器：服务层 + 响应式 HTML 生成。

发布产物为移动优先的响应式单页 HTML：
- viewport + 媒体查询（<=768px 单列）
- 完整 SEO meta（title/description/keywords）
- GEO（生成引擎优化）：JSON-LD Organization/LocalBusiness + 地理区域语义标记
- 用户内容一律 HTML 转义，杜绝注入
"""
from __future__ import annotations

import html
import json
import os
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.site_project import SITE_HOST_MODES, SITE_STATUSES, SiteProject


class SiteError(Exception):
    pass


def _json_dumps(obj) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _parse_content(content: Optional[str]) -> dict:
    if not content:
        return {"sections": []}
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        return {"sections": []}
    if not isinstance(data, dict):
        return {"sections": []}
    return data


def _render_sections(content: dict) -> str:
    parts = []
    for sec in content.get("sections", []):
        stype = sec.get("type", "")
        if stype == "hero":
            title = html.escape(sec.get("title", "") or "")
            text = html.escape(sec.get("text", "") or "")
            parts.append(
                f'<section class="hero"><h1>{title}</h1><p>{text}</p></section>'
            )
        elif stype == "features":
            title = html.escape(sec.get("title", "") or "")
            items_html = "".join(
                '<div class="card"><h3>{}</h3><p>{}</p></div>'.format(
                    html.escape(str(it.get("title", "")) or ""),
                    html.escape(str(it.get("text", "")) or ""),
                )
                for it in sec.get("items", [])
            )
            parts.append(
                f'<section class="features"><h2>{title}</h2><div class="grid">{items_html}</div></section>'
            )
        elif stype == "about":
            title = html.escape(sec.get("title", "") or "")
            text = html.escape(sec.get("text", "") or "")
            parts.append(
                f'<section class="about"><h2>{title}</h2><p>{text}</p></section>'
            )
        elif stype == "contact":
            title = html.escape(sec.get("title", "") or "")
            text = html.escape(sec.get("text", "") or "")
            parts.append(
                f'<section class="contact"><h2>{title}</h2><p>{text}</p></section>'
            )
    return "\n".join(parts)


def _render_seo_meta(project: SiteProject) -> str:
    title = html.escape(project.seo_title or project.name)
    desc = html.escape(project.seo_description or "")
    keywords = html.escape(project.seo_keywords or "")
    return (
        f'<meta name="title" content="{title}">\n'
        f'<meta name="description" content="{desc}">\n'
        f'<meta name="keywords" content="{keywords}">\n'
    )


def _render_geo_jsonld(project: SiteProject) -> str:
    """GEO（生成引擎优化）：面向 AI 搜索的语义标记。"""
    if not project.geo_enabled:
        return ""
    org_type = project.geo_org_type or "Organization"
    address = {
        "@type": "PostalAddress",
        "addressRegion": project.geo_region or "",
    }
    data = {
        "@context": "https://schema.org",
        "@type": org_type,
        "name": project.name,
        "description": project.seo_description or project.description or "",
        "address": address,
    }
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


_BASE_CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;line-height:1.6;color:#1f2937;background:#f9fafb}
header{background:#111827;color:#fff;padding:1rem 2rem}
header .brand{font-weight:700;font-size:1.25rem}
main{max-width:1080px;margin:0 auto;padding:1.5rem}
.hero{padding:4rem 1rem;text-align:center;background:linear-gradient(135deg,#1d4ed8,#4f46e5);color:#fff;border-radius:16px;margin-bottom:2rem}
.hero h1{font-size:2.4rem;margin-bottom:.75rem}
.features h2,.about h2,.contact h2{margin:1.5rem 0 1rem;color:#111827}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:1.25rem;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card h3{margin-bottom:.5rem;color:#1d4ed8}
.about,.contact{background:#fff;border-radius:12px;padding:1.5rem;border:1px solid #e5e7eb;margin-bottom:1.5rem}
footer{text-align:center;padding:1.5rem;color:#6b7280;font-size:.875rem}
@media (max-width:768px){.hero h1{font-size:1.7rem}.hero{padding:2.5rem 1rem}.grid{grid-template-columns:1fr}}
@media (max-width:480px){.hero h1{font-size:1.4rem}}
"""


def _render_html(project: SiteProject) -> str:
    content = _parse_content(project.content)
    site_title = html.escape(project.seo_title or project.name)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_title}</title>
{_render_seo_meta(project)}
{_render_geo_jsonld(project)}
<style>{_BASE_CSS}</style>
</head>
<body>
<header><span class="brand">{html.escape(project.name)}</span></header>
<main>
{_render_sections(content)}
</main>
<footer>Generated by OpsCompass Site Generator</footer>
</body>
</html>
"""


def _ensure_unique_slug(db: Session, tenant_id: int, slug: str, exclude_id: Optional[int] = None):
    q = db.query(SiteProject).filter(
        SiteProject.tenant_id == tenant_id, SiteProject.slug == slug
    )
    if exclude_id is not None:
        q = q.filter(SiteProject.id != exclude_id)
    if q.first() is not None:
        raise SiteError(f"slug 已存在: {slug}")


def create_site(db: Session, tenant_id: int, payload) -> SiteProject:
    _ensure_unique_slug(db, tenant_id, payload.slug)
    if payload.host_mode not in SITE_HOST_MODES:
        raise SiteError(f"host_mode 仅支持: {', '.join(SITE_HOST_MODES)}")
    proj = SiteProject(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        slug=payload.slug.strip(),
        description=payload.description,
        template=payload.template or "default",
        seo_title=payload.seo_title,
        seo_description=payload.seo_description,
        seo_keywords=payload.seo_keywords,
        geo_enabled=payload.geo_enabled,
        geo_region=payload.geo_region,
        geo_org_type=payload.geo_org_type,
        host_mode=payload.host_mode,
        status="draft",
        content=_json_dumps(payload.content.model_dump() if payload.content else None),
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def list_sites(db: Session, tenant_id: int, skip: int = 0, limit: int = 50) -> List[SiteProject]:
    return (
        db.query(SiteProject)
        .filter(SiteProject.tenant_id == tenant_id)
        .order_by(SiteProject.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_site(db: Session, tenant_id: int, site_id: int) -> SiteProject:
    proj = db.query(SiteProject).filter(
        SiteProject.id == site_id, SiteProject.tenant_id == tenant_id
    ).first()
    if proj is None:
        raise SiteError("网站项目不存在")
    return proj


def update_site(db: Session, tenant_id: int, site_id: int, payload) -> SiteProject:
    proj = get_site(db, tenant_id, site_id)
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != proj.slug:
        _ensure_unique_slug(db, tenant_id, data["slug"], exclude_id=proj.id)
    if "content" in data and data["content"] is not None:
        data["content"] = _json_dumps(data["content"])
    if "host_mode" in data and data["host_mode"] not in SITE_HOST_MODES:
        raise SiteError(f"host_mode 仅支持: {', '.join(SITE_HOST_MODES)}")
    for k, v in data.items():
        setattr(proj, k, v)
    db.commit()
    db.refresh(proj)
    return proj


def delete_site(db: Session, tenant_id: int, site_id: int) -> None:
    proj = get_site(db, tenant_id, site_id)
    db.delete(proj)
    db.commit()


def publish_site(db: Session, tenant_id: int, site_id: int) -> SiteProject:
    """生成响应式 HTML 快照并落盘，标记已发布。"""
    proj = get_site(db, tenant_id, site_id)
    html_doc = _render_html(proj)
    # 发布目录按租户+slug 隔离（运行时产物，不入库）
    out_dir = os.path.join(os.getcwd(), "data", "sites", f"t{tenant_id}", proj.slug)
    os.makedirs(out_dir, exist_ok=True)
    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    proj.status = "published"
    proj.publish_path = index_path
    db.commit()
    db.refresh(proj)
    return proj


def get_preview_html(db: Session, tenant_id: int, site_id: int) -> str:
    """未发布也可取预览 HTML。"""
    proj = get_site(db, tenant_id, site_id)
    return _render_html(proj)
