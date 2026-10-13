"""M14 导入导出安全中心：压缩传输记录。

- ImportRecord：导入压缩包自动安全解压提取记录（zip-slip 路径穿越防护）；
- ExportRecord：导出压缩记录，加密压缩为付费插件能力（feature 门控），
  密码 AES 加密后引用存储，严禁明文。

"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

IMPORT_STATUSES = ("pending", "done", "failed")
EXPORT_STATUSES = ("pending", "done", "failed")
ARCHIVE_TYPES = ("zip", "tar.gz")


class ImportRecord(Base):
    """压缩包导入解压记录。"""

    __tablename__ = "oc_import_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="租户 ID")
    source_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="源压缩包文件名")
    archive_type: Mapped[str] = mapped_column(String(16), nullable=False, default="zip", comment="压缩类型 zip/tar.gz")
    target_dir: Mapped[str] = mapped_column(String(500), nullable=False, comment="解压目标目录")
    extracted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否已完成解压提取"
    )
    file_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="解压提取文件数"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending/done/failed"
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class ExportRecord(Base):
    """导出压缩记录（加密压缩为付费插件能力）。"""

    __tablename__ = "oc_export_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="租户 ID")
    target_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="导出压缩包文件名")
    encrypted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否加密压缩"
    )
    password_ref: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True, comment="密码密文引用（AES 加密，严禁明文）"
    )
    plugin_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否依赖付费插件（secure-export）"
    )
    file_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="导出文件数"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", comment="pending/done/failed"
    )
    target_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="导出文件落盘路径")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
