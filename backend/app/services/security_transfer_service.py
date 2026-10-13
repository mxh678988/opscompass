"""M14 导入导出安全中心：安全解压提取 / 加密导出（付费插件门控）。

安全要点：
- 导入解压做 zip-slip 路径穿越防护：拒绝绝对路径、``..`` 跳转、符号链接，
  所有成员规范化后必须落在目标目录之内；
- 导出加密使用标准库 zipfile 密码压缩，密码经 AES 加密后引用存储，严禁明文；
- 加密导出为付费插件能力，仅在 ``secure-export`` 插件启用（state=enabled）时可用。
"""

import os
import posixpath
import shutil
import tarfile
import zipfile
from typing import Optional

import pyzipper
from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.models.plugin import CorePlugin, PLUGIN_STATES
from app.models.security_transfer import ExportRecord, ImportRecord
from app.schemas.security_transfer import ExportRequest, ImportRequest

SECURE_EXPORT_PLUGIN_ID = "secure-export"

IMPORT_STATUSES = ("pending", "done", "failed")
EXPORT_STATUSES = ("pending", "done", "failed")


class SecurityTransferError(Exception):
    """M14 传输安全业务错误。"""


def _normalize_member(name: str) -> str:
    """将压缩包成员名规范化为相对路径，发现穿越痕迹即抛错。"""
    # 统一分隔符
    cleaned = name.replace("\\", "/")
    # 拒绝绝对路径（根路径或盘符）
    if cleaned.startswith("/") or cleaned.startswith("//") or posixpath.isabs(cleaned):
        raise SecurityTransferError(f"拒绝绝对路径成员: {name}")
    if len(cleaned) >= 2 and cleaned[1] == ":":
        raise SecurityTransferError(f"拒绝盘符路径成员: {name}")
    norm = posixpath.normpath(cleaned)
    # normpath 后若回到根或包含 ..，即存在跳转
    if norm in ("", ".") or norm.startswith("..") or norm.startswith("/") or ".." in norm.split("/"):
        raise SecurityTransferError(f"拒绝路径穿越成员: {name}")
    return norm


def _safe_join(target_dir: str, member: str) -> str:
    """安全拼接目标路径，确保最终绝对路径落在目标目录内。"""
    target_abs = os.path.abspath(target_dir)
    rel = _normalize_member(member)
    dest = os.path.abspath(os.path.join(target_abs, rel))
    if not dest.startswith(target_abs + os.sep):
        raise SecurityTransferError(f"成员越出目标目录: {member}")
    return dest


def _safe_extract_zip(zip_path: str, target_dir: str) -> int:
    """安全解压 zip，返回提取文件数（仅普通文件）。"""
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            dest = _safe_join(target_dir, info.filename)
            if info.is_dir():
                os.makedirs(dest, exist_ok=True)
                continue
            # 拒绝符号链接（zip 外部属性标记），极端场景兜底
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and (unix_mode & 0o170000) == 0o120000:
                raise SecurityTransferError(f"拒绝符号链接成员: {info.filename}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def _safe_extract_tar(tar_path: str, target_dir: str) -> int:
    """安全解压 tar.gz，拒绝链接成员与路径穿越，返回提取文件数。"""
    count = 0
    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            if member.islnk() or member.issym():
                raise SecurityTransferError(f"拒绝链接成员: {member.name}")
            dest = _safe_join(target_dir, member.name)
            if member.isdir():
                os.makedirs(dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            src = tf.extractfile(member)
            if src is None:
                continue
            with src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def _extract_archive(source_path: str, target_dir: str, archive_type: str) -> int:
    """按类型安全解压，返回文件数。"""
    if not os.path.isfile(source_path):
        raise SecurityTransferError(f"源压缩包不存在: {source_path}")
    if archive_type == "zip":
        return _safe_extract_zip(source_path, target_dir)
    if archive_type == "tar.gz":
        return _safe_extract_tar(source_path, target_dir)
    raise SecurityTransferError(f"不支持的压缩类型: {archive_type}")


def import_archive(
    db: Session,
    tenant_id: int,
    payload: ImportRequest,
) -> ImportRecord:
    """导入压缩包自动安全解压提取。"""
    record = ImportRecord(
        tenant_id=tenant_id,
        source_name=os.path.basename(payload.source_path),
        archive_type=payload.archive_type,
        target_dir=payload.target_dir,
        status="pending",
    )
    db.add(record)
    try:
        db.flush()
        os.makedirs(payload.target_dir, exist_ok=True)
        count = _extract_archive(payload.source_path, payload.target_dir, payload.archive_type)
        record.extracted = True
        record.file_count = count
        record.status = "done"
    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.error = str(exc)
        db.rollback()
        # 失败也要留痕：重新挂载记录
        db.add(record)
        db.commit()
    else:
        db.commit()
        db.refresh(record)
    return record


def _is_secure_export_enabled(db: Session) -> bool:
    """付费门控：secure-export 插件是否已启用。"""
    plugin = (
        db.query(CorePlugin)
        .filter(
            CorePlugin.plugin_id == SECURE_EXPORT_PLUGIN_ID,
            CorePlugin.state == "enabled",
        )
        .first()
    )
    return plugin is not None


def export_archive(
    db: Session,
    tenant_id: int,
    payload: ExportRequest,
    allow_encrypted: Optional[bool] = None,
) -> ExportRecord:
    """导出压缩（加密需付费插件 secure-export 启用）。

    allow_encrypted：由端点做插件门控判定后传入；为 None 时服务内自检。
    """
    if not os.path.isdir(payload.source_dir):
        raise SecurityTransferError(f"待导出目录不存在: {payload.source_dir}")

    if payload.encrypted and payload.password is None:
        raise SecurityTransferError("加密导出必须提供密码")

    plugin_required = payload.encrypted

    record = ExportRecord(
        tenant_id=tenant_id,
        target_name=payload.target_name,
        encrypted=payload.encrypted,
        plugin_required=plugin_required,
        status="pending",
    )
    if payload.encrypted:
        record.password_ref = encrypt(payload.password or "")

    # 导出落盘目录：按租户隔离存放（中间产物），文件名防路径注入
    safe_name = os.path.basename(payload.target_name)
    out_dir = os.path.join(os.getcwd(), "exports", f"t{tenant_id}")
    os.makedirs(out_dir, exist_ok=True)
    target_path = os.path.join(out_dir, safe_name)

    db.add(record)
    try:
        db.flush()
        # 付费插件门控：加密导出需 secure-export 插件启用
        gate = allow_encrypted if allow_encrypted is not None else _is_secure_export_enabled(db)
        if payload.encrypted and not gate:
            raise SecurityTransferError(
                f"加密导出为付费插件功能，请先安装并启用 {SECURE_EXPORT_PLUGIN_ID} 插件"
            )

        count = 0
        if payload.encrypted:
            # AES-256 加密压缩（pyzipper），密码仅用于本次加密，密文引用已入库
            with pyzipper.AESZipFile(
                target_path,
                "w",
                compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES,
            ) as zf:
                zf.setpassword((payload.password or "").encode("utf-8"))
                for root, _dirs, files in os.walk(payload.source_dir):
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, payload.source_dir)
                        zf.write(full, arcname=rel)
                        count += 1
        else:
            with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _dirs, files in os.walk(payload.source_dir):
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, payload.source_dir)
                        zf.write(full, arcname=rel)
                        count += 1
        record.file_count = count
        record.target_path = target_path
        record.status = "done"
    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.error = str(exc)
        db.rollback()
        db.add(record)
        db.commit()
    else:
        db.commit()
        db.refresh(record)
    return record


def list_imports(db: Session, tenant_id: int, page: int = 1, page_size: int = 20) -> dict:
    """导入记录分页列表。"""
    q = db.query(ImportRecord).filter(ImportRecord.tenant_id == tenant_id)
    total = q.count()
    items = (
        q.order_by(ImportRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": items, "page": page, "page_size": page_size}


def list_exports(db: Session, tenant_id: int, page: int = 1, page_size: int = 20) -> dict:
    """导出记录分页列表。"""
    q = db.query(ExportRecord).filter(ExportRecord.tenant_id == tenant_id)
    total = q.count()
    items = (
        q.order_by(ExportRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": items, "page": page, "page_size": page_size}
