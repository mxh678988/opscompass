"""M16 网站资源管理器：服务层。

能力：扫描发布产物目录生成资源索引（sha256 校验）、资源清单与类型过滤、
资源重命名/归档/删除（删除限定在发布目录内，防路径穿越）、按项目统计。
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.site_resource import RESOURCE_STATUSES, RESOURCE_TYPES, SiteResource
from app.models.site_project import SiteProject


class SiteResourceError(Exception):
    pass


def _type_for_path(rel_path: str) -> str:
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in (".html", ".htm"):
        return "page"
    if ext in (".js", ".mjs"):
        return "script"
    if ext in (".css",):
        return "css"
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".avif"):
        return "image"
    if ext in (".mp4", ".webm", ".mp3", ".wav", ".ogg", ".pdf", ".zip"):
        return "media"
    return "other"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _project_publish_dir(proj: SiteProject) -> str:
    if proj.publish_path:
        return os.path.dirname(proj.publish_path)
    return os.path.join(os.getcwd(), "data", "sites", f"t{proj.tenant_id}", proj.slug)


def _ensure_inside(dir_path: str, base_dir: str) -> str:
    real_dir = os.path.realpath(dir_path)
    real_base = os.path.realpath(base_dir)
    if not real_dir.startswith(real_base + os.sep) and real_dir != real_base:
        raise SiteResourceError("资源路径越界，拒绝访问发布目录之外的文件")
    return real_dir


def get_project(db: Session, tenant_id: int, project_id: int) -> SiteProject:
    proj = db.query(SiteProject).filter(
        SiteProject.id == project_id, SiteProject.tenant_id == tenant_id
    ).first()
    if proj is None:
        raise SiteResourceError("网站项目不存在")
    return proj


def scan_project(db: Session, tenant_id: int, project_id: int) -> dict:
    """扫描发布目录，同步资源索引；已消失文件标记 missing。"""
    proj = get_project(db, tenant_id, project_id)
    base_dir = _project_publish_dir(proj)
    if not os.path.isdir(base_dir):
        raise SiteResourceError("网站尚未发布，无资源可扫描")

    created = updated = 0
    seen_paths: set[str] = set()
    for root, _dirs, files in os.walk(base_dir):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, base_dir).replace("\\", "/")
            seen_paths.add(rel)
            size = os.path.getsize(full)
            checksum = _sha256_file(full)
            rtype = _type_for_path(rel)
            exist = db.query(SiteResource).filter(
                SiteResource.tenant_id == tenant_id,
                SiteResource.project_id == project_id,
                SiteResource.path == rel,
            ).first()
            if exist is None:
                db.add(SiteResource(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    resource_type=rtype,
                    name=os.path.basename(full),
                    path=rel,
                    size_bytes=size,
                    checksum=checksum,
                    status="active",
                ))
                created += 1
            else:
                exist.resource_type = rtype
                exist.size_bytes = size
                exist.checksum = checksum
                exist.status = "active"
                updated += 1

    # 标记已消失资源为 missing
    stale = db.query(SiteResource).filter(
        SiteResource.tenant_id == tenant_id,
        SiteResource.project_id == project_id,
        SiteResource.status != "missing",
    ).all()
    marked_missing = 0
    for res in stale:
        if res.path not in seen_paths:
            res.status = "missing"
            marked_missing += 1

    db.commit()
    return {
        "project_id": project_id,
        "scanned": len(seen_paths),
        "created": created,
        "updated": updated,
        "marked_missing": marked_missing,
    }


def list_resources(
    db: Session,
    tenant_id: int,
    project_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[SiteResource]:
    q = db.query(SiteResource).filter(SiteResource.tenant_id == tenant_id)
    if project_id is not None:
        q = q.filter(SiteResource.project_id == project_id)
    if resource_type:
        q = q.filter(SiteResource.resource_type == resource_type)
    if status:
        q = q.filter(SiteResource.status == status)
    return q.order_by(SiteResource.id.desc()).offset(skip).limit(limit).all()


def get_resource(db: Session, tenant_id: int, resource_id: int) -> SiteResource:
    res = db.query(SiteResource).filter(
        SiteResource.id == resource_id, SiteResource.tenant_id == tenant_id
    ).first()
    if res is None:
        raise SiteResourceError("网站资源不存在")
    return res


def update_resource(db: Session, tenant_id: int, resource_id: int, payload) -> SiteResource:
    res = get_resource(db, tenant_id, resource_id)
    data = payload.model_dump(exclude_unset=True)
    if "resource_type" in data and data["resource_type"] not in RESOURCE_TYPES:
        raise SiteResourceError(f"resource_type 仅支持: {', '.join(RESOURCE_TYPES)}")
    if "status" in data and data["status"] not in RESOURCE_STATUSES:
        raise SiteResourceError(f"status 仅支持: {', '.join(RESOURCE_STATUSES)}")
    if "meta" in data and data["meta"] is not None:
        data["meta"] = json.dumps(data["meta"], ensure_ascii=False)
    for k, v in data.items():
        setattr(res, k, v)
    db.commit()
    db.refresh(res)
    return res


def delete_resource(db: Session, tenant_id: int, resource_id: int, force: bool = False) -> dict:
    """删除资源记录；force=True 时同时物理删除发布目录内对应文件。"""
    res = get_resource(db, tenant_id, resource_id)
    if force:
        proj = None
        if res.project_id is not None:
            proj = db.query(SiteProject).filter(
                SiteProject.id == res.project_id, SiteProject.tenant_id == tenant_id
            ).first()
        base_dir = _project_publish_dir(proj) if proj is not None else None
        if base_dir is None or not os.path.isdir(base_dir):
            raise SiteResourceError("资源所属发布目录不存在，无法物理删除")
        target = _ensure_inside(os.path.join(base_dir, res.path.replace("/", os.sep)), base_dir)
        if os.path.isfile(target):
            os.remove(target)
    db.delete(res)
    db.commit()
    return {"deleted": resource_id, "force": force}


def summary(db: Session, tenant_id: int, project_id: Optional[int] = None) -> dict:
    q = db.query(SiteResource).filter(SiteResource.tenant_id == tenant_id)
    if project_id is not None:
        q = q.filter(SiteResource.project_id == project_id)
    rows = q.all()
    by_type: dict = {}
    by_status: dict = {}
    total_size = 0
    for r in rows:
        by_type[r.resource_type] = by_type.get(r.resource_type, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
        total_size += r.size_bytes or 0
    return {
        "project_id": project_id,
        "total": len(rows),
        "total_size_bytes": total_size,
        "by_type": by_type,
        "by_status": by_status,
    }
